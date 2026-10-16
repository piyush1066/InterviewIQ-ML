from __future__ import annotations

import re
from typing import Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
    "were", "will", "with", "you", "your", "what", "how", "why", "when",
}


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9+#.\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def terms(text: str) -> List[str]:
    tokens = re.findall(r"[a-z][a-z0-9+#.-]{1,}", normalize_text(text))
    return sorted({t.strip(".-") for t in tokens if t not in STOPWORDS and len(t.strip(".-")) > 1})


def text_similarity(left: str, right: str) -> float:
    left, right = normalize_text(left), normalize_text(right)
    if not left or not right:
        return 0.0
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    try:
        matrix = vectorizer.fit_transform([left, right])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0, 0])
    except ValueError:
        return 0.0


def answer_features(question: str, reference_answer: str, candidate_answer: str) -> Dict[str, float]:
    candidate = normalize_text(candidate_answer)
    question_terms = set(terms(question))
    reference_terms = set(terms(reference_answer))
    candidate_terms = set(terms(candidate_answer))

    q_coverage = len(question_terms & candidate_terms) / max(1, len(question_terms))
    ref_coverage = len(reference_terms & candidate_terms) / max(1, len(reference_terms))
    words = candidate.split()
    unique_ratio = len(set(words)) / max(1, len(words))
    sentence_count = max(1, len(re.findall(r"[.!?]+", candidate_answer)))
    return {
        "question_similarity": text_similarity(question, candidate_answer),
        "reference_similarity": text_similarity(reference_answer, candidate_answer) if reference_answer.strip() else 0.0,
        "question_term_coverage": q_coverage,
        "reference_term_coverage": ref_coverage,
        "word_count": min(len(words), 300) / 300.0,
        "unique_word_ratio": unique_ratio,
        "sentence_count": min(sentence_count, 10) / 10.0,
        "has_example_signal": float(any(x in candidate for x in ("for example", "for instance", "e.g."))),
        "has_reasoning_signal": float(any(x in candidate for x in ("because", "therefore", "so that", "which means"))),
    }


FEATURE_COLUMNS = [
    "question_similarity",
    "reference_similarity",
    "question_term_coverage",
    "reference_term_coverage",
    "word_count",
    "unique_word_ratio",
    "sentence_count",
    "has_example_signal",
    "has_reasoning_signal",
]


def resume_match(resume_text: str, job_description: str) -> Dict[str, object]:
    resume_terms = set(terms(resume_text))
    job_terms = set(terms(job_description))
    matched = sorted(resume_terms & job_terms)
    missing = sorted(job_terms - resume_terms)
    score = round(text_similarity(resume_text, job_description) * 100, 1)
    coverage = round((len(matched) / max(1, len(job_terms))) * 100, 1)
    return {
        "match_score": score,
        "keyword_coverage": coverage,
        "matched_terms": matched[:40],
        "missing_terms": missing[:40],
        "explanation": "Similarity and keyword overlap are heuristic signals, not a hiring recommendation.",
    }
