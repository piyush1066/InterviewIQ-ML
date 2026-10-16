
from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from pypdf import PdfReader

from ml_features import (
    FEATURE_COLUMNS,
    answer_evidence,
    answer_features,
    calibrated_answer_score,
    resume_match,
)


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "30000"))
MAX_PDF_BYTES = int(os.getenv("MAX_PDF_BYTES", str(5 * 1024 * 1024)))
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
MODEL_PATH = ROOT / "artifacts" / "answer_scorer.joblib"

app = FastAPI(
    title="InterviewIQ-ML",
    version="0.2.0",
    description="Offline resume-driven interview practice and evaluation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model_bundle = None


# -------------------- Request Models --------------------

class ResumeMatchRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)

    @field_validator("resume_text", "job_description")
    @classmethod
    def limit_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) > MAX_TEXT_CHARS:
            raise ValueError(f"Text exceeds {MAX_TEXT_CHARS} characters")
        return value


class AnswerEvaluationRequest(BaseModel):
    question: str = Field(min_length=1)
    candidate_answer: str = Field(min_length=1)
    reference_answer: str = ""
    topic: str = ""

    @field_validator("question", "candidate_answer", "reference_answer", "topic")
    @classmethod
    def limit_text(cls, value: str) -> str:
        value = (value or "").strip()
        if len(value) > MAX_TEXT_CHARS:
            raise ValueError(f"Text exceeds {MAX_TEXT_CHARS} characters")
        return value


class QuestionGenerationRequest(BaseModel):
    resume_text: str = Field(min_length=1)
    number_of_questions: int = Field(default=10, ge=1, le=30)

    @field_validator("resume_text")
    @classmethod
    def validate_resume(cls, value: str) -> str:
        value = value.strip()
        if len(value) > MAX_TEXT_CHARS:
            raise ValueError(f"Text exceeds {MAX_TEXT_CHARS} characters")
        return value


# -------------------- ML Model --------------------

def load_model():
    global _model_bundle

    if _model_bundle is None:
        if not MODEL_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Answer scoring model is missing. "
                    "Run your existing training script first."
                ),
            )

        try:
            _model_bundle = joblib.load(MODEL_PATH)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Could not load the answer scoring model.",
            ) from exc

    return _model_bundle


# -------------------- Resume Processing --------------------

SKILL_BANK = [
    "Java",
    "Python",
    "JavaScript",
    "TypeScript",
    "C",
    "C++",
    "React",
    "Node.js",
    "Express",
    "FastAPI",
    "Django",
    "MongoDB",
    "MySQL",
    "PostgreSQL",
    "SQL",
    "Redis",
    "HTML",
    "CSS",
    "Git",
    "Docker",
    "AWS",
    "Firebase",
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "scikit-learn",
    "TensorFlow",
    "PyTorch",
    "REST API",
    "Data Structures",
    "Algorithms",
    "Spring Boot",
    "Next.js",
]


SECTION_HEADINGS = {
    "education": {
        "education",
        "academic background",
        "educational qualifications",
    },
    "projects": {
        "projects",
        "personal projects",
        "academic projects",
        "project experience",
    },
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "internships",
    },
    "summary": {"summary", "professional summary", "profile", "objective"},
    "certifications": {"certifications", "certificates", "licenses"},
}


def extract_resume_details(text: str) -> dict:
    text = re.sub(r"[ \t]+", " ", text)
    lines = [
        line.strip(" •-\t")
        for line in text.splitlines()
        if line.strip()
    ]

    skills = []

    for skill in SKILL_BANK:
        pattern = r"(?<!\w)" + re.escape(skill) + r"(?!\w)"

        if re.search(pattern, text, flags=re.IGNORECASE):
            skills.append(skill)

    sections = {
        "education": [],
        "projects": [],
        "experience": [],
        "summary": [],
        "certifications": [],
    }

    current_section = None

    other_headings = {
        "skills",
        "technical skills",
        "certifications",
        "achievements",
        "contact",
        "technical summary",
    }

    for line in lines:
        normalized = line.lower().strip(" :|-")

        matched_section = next(
            (
                section
                for section, headings in SECTION_HEADINGS.items()
                if normalized in headings
            ),
            None,
        )

        if matched_section:
            current_section = matched_section
            continue

        if normalized in other_headings:
            current_section = None
            continue

        if current_section:
            sections[current_section].append(line)

    return {
        "skills": skills,
        **{key: sections[key][:20] for key in sections},
    }


# -------------------- Offline Question Generation --------------------

QUESTION_TEMPLATES = [
    (
        "technical",
        "Explain {skill} and describe how you have used it in a project.",
    ),
    (
        "technical",
        "What are the main concepts of {skill} that a developer should understand?",
    ),
    (
        "practical",
        "Describe a real problem you could solve using {skill}. Explain your approach.",
    ),
    (
        "problem_solving",
        "What common challenges arise when working with {skill}, and how would you debug them?",
    ),
]

SKILL_QUESTION_OVERRIDES = {
    "data structures": (
        "algorithms",
        "Which data structure from your experience would you choose for a fast lookup problem, and what tradeoffs would you consider?",
    ),
    "algorithms": (
        "algorithms",
        "How would you analyze the time and space complexity of an algorithm you used? Walk through an example.",
    ),
    "rest api": (
        "api_design",
        "How would you design a REST API for one of your projects, including resources, validation, and error responses?",
    ),
    "sql": (
        "database_design",
        "How would you model related data in a relational database and keep common queries efficient?",
    ),
    "mysql": (
        "database_design",
        "How would you design and index MySQL tables for a project with related records and frequent lookups?",
    ),
    "mongodb": (
        "database_design",
        "How would you decide what to embed or reference when modeling project data in MongoDB?",
    ),
}


def generate_questions(
    resume_text: str,
    details: dict,
    count: int,
) -> list[dict]:
    questions = []
    seen = set()

    def add_question(category: str, question: str, topic: str):
        normalized = question.lower().strip()

        if normalized in seen or len(questions) >= count:
            return

        seen.add(normalized)

        questions.append({
            "id": f"q-{len(questions) + 1:03d}",
            "category": category,
            "question": question,
            "topic": topic,
            "reference_answer": "",
        })

    skills = details["skills"]
    # Start with one question per detected skill, then make room for resume
    # project and experience questions before adding further skill prompts.
    for skill in skills:
        category, question = SKILL_QUESTION_OVERRIDES.get(
            skill.lower(),
            ("technical", QUESTION_TEMPLATES[0][1].format(skill=skill)),
        )
        add_question(category, question, skill)
        if len(questions) >= count:
            return questions

    for project in details["projects"]:
        if len(project) < 15:
            continue

        project_prompts = [
            ("project_architecture", "Walk through the architecture and data flow of this project. What did you build? " + project),
            ("project_challenge", "Describe a difficult implementation or debugging challenge in this project and how you handled it: " + project),
            ("project_decisions", "Which technical choice would you revisit in this project, and why? " + project),
        ]
        for category, question in project_prompts:
            add_question(category, question, "Project")
            if len(questions) >= count:
                return questions

    for experience in details["experience"]:
        if len(experience) < 15:
            continue

        question = (
            "Describe your responsibilities, technical contributions, "
            f"and key learning from this experience: {experience}"
        )

        add_question("experience", question, "Experience")

        if len(questions) >= count:
            return questions

    for skill in skills:
        for category, template in QUESTION_TEMPLATES[1:]:
            add_question(category, template.format(skill=skill), skill)
            if len(questions) >= count:
                return questions

    follow_up_questions = [
        ("behavioral", "Tell me about a difficult technical problem you solved. What did you try, and what was the outcome?"),
        ("problem_solving", "How do you investigate a bug that you cannot reproduce consistently?"),
        ("behavioral", "Describe a time you had to learn a new tool or concept quickly. How did you approach it?"),
        ("teamwork", "How do you handle a technical disagreement with a teammate? Give an example."),
        ("technical", "How would you test a feature you built and decide it is ready to release?"),
        ("reflection", "Which project or skill on your resume best represents your strengths, and why?"),
        ("behavioral", "Describe a mistake or setback and what you changed afterward."),
        ("communication", "How would you explain one of your technical projects to a non-technical stakeholder?"),
    ]
    for category, question in follow_up_questions:
        add_question(category, question, "General interview")
        if len(questions) >= count:
            return questions

    if not questions:
        add_question(
            "general",
            (
                "Choose a technical skill or project from your resume "
                "and explain what you learned and how you applied it."
            ),
            "Resume",
        )

    return questions


# -------------------- Health Check --------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "interviewiq-ml",
        "model_ready": MODEL_PATH.exists(),
        "external_api_calls": False,
    }


# -------------------- Resume Upload --------------------

@app.post("/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF resume.",
        )

    content = await file.read(MAX_PDF_BYTES + 1)
    await file.close()

    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail="PDF is too large. Maximum size is 5 MB.",
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid PDF.",
        )

    try:
        reader = PdfReader(BytesIO(content), strict=False)

        if reader.is_encrypted:
            raise HTTPException(
                status_code=400,
                detail="Password-protected PDFs are not supported.",
            )

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not read this PDF. Try another PDF resume.",
        ) from exc

    text = text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail=(
                "No selectable text was found. "
                "Scanned PDFs require local OCR support."
            ),
        )

    text = text[:MAX_TEXT_CHARS]
    details = extract_resume_details(text)

    return {
        "success": True,
        "filename": Path(file.filename).name,
        "resume_text": text,
        "details": details,
        "message": "Resume processed locally. No external API was called.",
    }


# -------------------- Generate Interview --------------------

@app.post("/interview/generate")
def create_interview(payload: QuestionGenerationRequest):
    details = extract_resume_details(payload.resume_text)

    questions = generate_questions(
        payload.resume_text,
        details,
        payload.number_of_questions,
    )

    return {
        "success": True,
        "resume_details": details,
        "total_questions": len(questions),
        "questions": questions,
        "method": "local_resume_extraction_and_template_question_engine",
    }


# -------------------- Resume Matching --------------------

@app.post("/resume/match")
def match_resume(payload: ResumeMatchRequest):
    result = resume_match(
        payload.resume_text,
        payload.job_description,
    )

    return {
        "success": True,
        **result,
        "method": "tfidf_cosine_similarity_and_keyword_overlap",
    }


# -------------------- Answer Evaluation --------------------

@app.post("/answer/evaluate")
def evaluate_answer(payload: AnswerEvaluationRequest):
    features = answer_features(
        payload.question,
        payload.reference_answer,
        payload.candidate_answer,
    )

    X = pd.DataFrame(
        [[features[name] for name in FEATURE_COLUMNS]],
        columns=FEATURE_COLUMNS,
    )

    evidence = answer_evidence(
        payload.question,
        payload.reference_answer,
        payload.candidate_answer,
        payload.topic,
    )
    model_score = None
    model_version = "not_applied_reference_free"
    method = "tfidf_focus_relevance_and_completeness"
    if payload.reference_answer.strip() and MODEL_PATH.exists():
        bundle = load_model()
        model_score = float(bundle["model"].predict(X)[0])
        model_version = bundle.get("version", "unknown")
        method = "trained_random_forest_with_relevance_calibration"

    score = calibrated_answer_score(evidence, model_score)

    feedback = []

    if evidence["answer_relevance"] < 0.22:
        feedback.append(
            "This response has little text overlap with the question topic. "
            "Start with a direct answer and include the key terms or concepts you mean."
        )
    elif evidence["answer_relevance"] < 0.4:
        feedback.append(
            "Connect your explanation more directly to the question and its specific topic."
        )

    if payload.reference_answer and evidence["reference_term_coverage"] < 0.35:
        feedback.append(
            "Compare your answer with the reference concepts and address the ones you missed."
        )

    if evidence["answer_completeness"] < 0.2:
        feedback.append(
            "Add a little more explanation: describe your approach and one relevant detail or example."
        )

    if not evidence["has_reasoning_signal"] and evidence["word_count"] >= 15:
        feedback.append("Explain why your approach works or what tradeoff it addresses.")

    if not feedback:
        feedback.append(
            "Review the score alongside the feedback and verify "
            "that your answer is technically accurate."
        )

    strengths = []
    if evidence["answer_relevance"] >= 0.45:
        strengths.append("Your response is connected to the question topic.")
    if evidence["answer_completeness"] >= 0.55:
        strengths.append("You provided enough detail to explain your thinking.")
    if evidence["has_example_signal"]:
        strengths.append("You included an example to make the explanation concrete.")
    if evidence["has_reasoning_signal"]:
        strengths.append("You explained reasoning or cause and effect.")
    if payload.reference_answer and evidence["reference_term_coverage"] >= 0.5:
        strengths.append("Your answer covers several concepts from the provided reference.")

    return {
        "success": True,
        "score": round(score, 1),
        "max_score": 10,
        "strengths": strengths,
        "feedback": feedback,
        "signals": {
            "answer_relevance": round(evidence["answer_relevance"], 3),
            "focus_term_coverage": round(evidence["focus_term_coverage"], 3),
            "answer_completeness": round(evidence["answer_completeness"], 3),
            "question_term_coverage": round(
                features["question_term_coverage"], 3
            ),
            "reference_term_coverage": round(
                features["reference_term_coverage"], 3
            ),
            "reference_similarity": round(
                features["reference_similarity"], 3
            ),
            "word_count_normalized": round(
                features["word_count"], 3
            ),
            "has_example_signal": evidence["has_example_signal"],
            "has_reasoning_signal": evidence["has_reasoning_signal"],
        },
        "model_version": model_version,
        "scoring_method": method,
        "caveat": (
            "Experimental ML estimate. Validate against human-labelled answers; "
            "do not use as a sole hiring decision."
        ),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8011")),
    )
