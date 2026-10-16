from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from ml_features import answer_features, FEATURE_COLUMNS, resume_match

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "30000"))
MODEL_PATH = ROOT / "artifacts" / "answer_scorer.joblib"

app = FastAPI(
    title="InterviewIQ.AI ML Service",
    version="0.1.0",
    description="Local ML endpoints for resume matching and interview answer evaluation.",
)
_model_bundle = None


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

    @field_validator("question", "candidate_answer", "reference_answer")
    @classmethod
    def limit_text(cls, value: str) -> str:
        value = (value or "").strip()
        if len(value) > MAX_TEXT_CHARS:
            raise ValueError(f"Text exceeds {MAX_TEXT_CHARS} characters")
        return value


def load_model():
    global _model_bundle
    if _model_bundle is None:
        if not MODEL_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail="Model artifacts missing. Run `python train.py` inside ml-service first.",
            )
        _model_bundle = joblib.load(MODEL_PATH)
    return _model_bundle


@app.get("/health")
def health():
    return {"status": "ok", "service": "interviewiq-ml", "model_ready": MODEL_PATH.exists()}


@app.post("/resume/match")
def match_resume(payload: ResumeMatchRequest):
    result = resume_match(payload.resume_text, payload.job_description)
    return {"success": True, **result, "method": "tfidf_cosine_similarity_and_keyword_overlap"}


@app.post("/answer/evaluate")
def evaluate_answer(payload: AnswerEvaluationRequest):
    bundle = load_model()
    features = answer_features(
        payload.question, payload.reference_answer, payload.candidate_answer
    )
    X = pd.DataFrame([[features[name] for name in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
    score = float(bundle["model"].predict(X)[0])
    score = max(0.0, min(10.0, score))

    feedback = []
    if features["question_term_coverage"] < 0.25:
        feedback.append("Your answer may not address enough terms from the question. Directly answer what was asked.")
    if payload.reference_answer and features["reference_term_coverage"] < 0.35:
        feedback.append("Compare your answer with the key concepts in the reference answer.")
    if features["word_count"] < 0.08:
        feedback.append("Add more explanation, steps, or a concrete example where relevant.")
    if not feedback:
        feedback.append("Review the score alongside the feedback and make sure the answer is technically accurate.")

    return {
        "success": True,
        "score": round(score, 1),
        "max_score": 10,
        "feedback": feedback,
        "signals": {
            "question_term_coverage": round(features["question_term_coverage"], 3),
            "reference_term_coverage": round(features["reference_term_coverage"], 3),
            "reference_similarity": round(features["reference_similarity"], 3),
            "word_count_normalized": round(features["word_count"], 3),
        },
        "model_version": bundle.get("version", "unknown"),
        "caveat": "Experimental ML estimate. Validate against human-labelled answers; do not use as a sole hiring decision.",
    }
