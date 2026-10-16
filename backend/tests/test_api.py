from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfWriter

import app as backend


client = TestClient(backend.app)
SAMPLE_PDF = Path(__file__).resolve().parents[2] / "frontend" / "public" / "sample-resume.pdf"


def test_health_reports_service_and_model_state():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["external_api_calls"] is False
    assert response.json()["model_ready"] == backend.MODEL_PATH.exists()


def test_local_vite_origin_is_allowed_by_cors():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_sample_pdf_upload_extracts_resume_sections_and_skills():
    assert SAMPLE_PDF.is_file()
    with SAMPLE_PDF.open("rb") as sample:
        response = client.post("/resume/upload", files={"file": (SAMPLE_PDF.name, sample, "application/pdf")})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["success"] is True
    assert "Alex Morgan" in result["resume_text"]
    assert {"Java", "Python", "React", "FastAPI", "scikit-learn"}.issubset(result["details"]["skills"])
    assert result["details"]["education"]
    assert result["details"]["projects"]
    assert result["details"]["experience"]


def test_non_pdf_and_malformed_pdf_are_rejected():
    non_pdf = client.post("/resume/upload", files={"file": ("resume.txt", b"resume", "text/plain")})
    malformed = client.post("/resume/upload", files={"file": ("resume.pdf", b"%PDF-not-a-real-document", "application/pdf")})
    assert non_pdf.status_code == 400
    assert "PDF" in non_pdf.json()["detail"]
    assert malformed.status_code == 400


def test_oversized_pdf_is_rejected():
    too_large = b"%PDF-1.4\n" + b"x" * (5 * 1024 * 1024)
    response = client.post("/resume/upload", files={"file": ("large.pdf", too_large, "application/pdf")})
    assert response.status_code == 413
    assert "5 MB" in response.json()["detail"]


def test_empty_text_pdf_reports_scanned_or_empty_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    from io import BytesIO

    buffer = BytesIO()
    writer.write(buffer)
    response = client.post("/resume/upload", files={"file": ("blank.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 400
    assert "selectable text" in response.json()["detail"]


def test_encrypted_pdf_is_rejected():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.encrypt("sample-password")
    from io import BytesIO

    buffer = BytesIO()
    writer.write(buffer)
    response = client.post("/resume/upload", files={"file": ("locked.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 400
    assert "Password-protected" in response.json()["detail"]


def test_questions_matching_and_fallback_answer_scoring(monkeypatch):
    with SAMPLE_PDF.open("rb") as sample:
        resume = client.post("/resume/upload", files={"file": (SAMPLE_PDF.name, sample, "application/pdf")}).json()
    questions = client.post("/interview/generate", json={"resume_text": resume["resume_text"], "number_of_questions": 20})
    assert questions.status_code == 200
    assert len(questions.json()["questions"]) == 20
    assert len({q["id"] for q in questions.json()["questions"]}) == 20
    assert any("project" in q["category"] for q in questions.json()["questions"])

    match = client.post("/resume/match", json={"resume_text": resume["resume_text"], "job_description": "Python FastAPI React MongoDB API design"})
    assert match.status_code == 200
    assert match.json()["match_score"] >= 0
    assert "recommendations" in match.json()

    monkeypatch.setattr(backend, "MODEL_PATH", SAMPLE_PDF.with_name("missing-answer-model.joblib"))
    monkeypatch.setattr(backend, "_model_bundle", None)
    evaluated = client.post("/answer/evaluate", json={
        "question": "How did you build an API with Python and FastAPI?",
        "candidate_answer": "I used Python and FastAPI to build the API. For example, I validated requests and added tests because reliable inputs help prevent errors.",
    })
    assert evaluated.status_code == 200
    assert 0 <= evaluated.json()["score"] <= 10
    assert evaluated.json()["scoring_method"] == "tfidf_focus_relevance_and_completeness"
    assert "signals" in evaluated.json()


def test_answer_score_rewards_relevant_answers_and_caps_unrelated_verbosity():
    question = "What is a HashMap in Java and how does it handle collisions?"
    unrelated = client.post("/answer/evaluate", json={
        "question": question,
        "topic": "HashMap in Java",
        "candidate_answer": (
            "I enjoy sunny weather and music. The beach is relaxing and the sky is blue. "
            "I like walking outside with friends and listening to songs. "
        ) * 5,
    })
    relevant = client.post("/answer/evaluate", json={
        "question": question,
        "topic": "HashMap in Java",
        "candidate_answer": (
            "A HashMap stores key-value pairs and uses hashing for fast lookup. "
            "In Java, collisions are handled by keeping entries in the same bucket; "
            "when there are many collisions, the bucket can become a tree. "
            "The average lookup is O(1), though collisions can make it slower."
        ),
    })

    assert unrelated.status_code == relevant.status_code == 200
    assert unrelated.json()["score"] <= 3.5
    assert relevant.json()["score"] >= 6.0
    assert relevant.json()["score"] > unrelated.json()["score"]
    assert unrelated.json()["signals"]["answer_relevance"] < relevant.json()["signals"]["answer_relevance"]


def test_reference_model_score_cannot_override_weak_relevance():
    unrelated = client.post("/answer/evaluate", json={
        "question": "What is a HashMap in Java?",
        "topic": "HashMap",
        "reference_answer": "A HashMap stores key-value pairs and uses hashing for fast lookup.",
        "candidate_answer": "The weather is sunny and I enjoy music, beaches, blue skies, and long walks. " * 5,
    })
    relevant = client.post("/answer/evaluate", json={
        "question": "What is a HashMap in Java?",
        "topic": "HashMap",
        "reference_answer": "A HashMap stores key-value pairs and uses hashing for fast lookup.",
        "candidate_answer": "A HashMap stores key-value pairs and uses hashing for fast lookup. "
        "It provides average constant time lookup by key.",
    })

    assert unrelated.status_code == relevant.status_code == 200
    assert unrelated.json()["score"] <= 3.5
    assert relevant.json()["score"] >= 6.0
    assert relevant.json()["score"] > unrelated.json()["score"]


def test_direct_question_match_is_not_diluted_by_a_broader_topic_label():
    response = client.post("/answer/evaluate", json={
        "question": "What is polymorphism?",
        "topic": "OOP",
        "reference_answer": (
            "Polymorphism allows one interface or method name to represent different "
            "implementations, such as overloading and overriding."
        ),
        "candidate_answer": (
            "Polymorphism means many forms. In Java, overriding lets a subclass "
            "provide its own implementation of a method. Overloading is another form."
        ),
    })

    assert response.status_code == 200
    assert response.json()["score"] >= 6.0
    assert response.json()["signals"]["answer_relevance"] >= 0.7
