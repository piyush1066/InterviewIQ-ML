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

QUESTION_FILLER_TERMS = {
    "explain", "describe", "tell", "give", "provide", "discuss", "outline",
    "would", "could", "should", "main", "common", "real", "using", "used",
    "use", "working", "work", "approach", "experience", "project", "projects",
    "problem", "challenges", "challenge", "arise", "developer", "understand",
    "learned", "learning", "contribution", "contributions", "responsibilities",
    "key", "technical", "skill", "skills", "resume", "example", "examples",
    "faced", "facing", "handle", "handled", "debug", "debugging", "solve",
    "solved", "consider", "considered", "choice", "choices", "decision",
    "decisions", "build", "built", "implement", "implemented", "tell",
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


def answer_evidence(
    question: str,
    reference_answer: str,
    candidate_answer: str,
    topic: str = "",
) -> Dict[str, float]:
    """Calibrate answer scores around topical evidence and bounded completeness.

    The training set is too small for the regressor to generalize safely to
    reference-free generated questions, so this signal is also used as a
    relevance guard when the trained model is available.
    """
    question_focus = {
        term for term in terms(question) if term not in QUESTION_FILLER_TERMS
    }
    topic_focus = {
        term for term in terms(topic) if term not in QUESTION_FILLER_TERMS
    }
    # A topic label adds context, but must not dilute a direct match to the
    # actual question (for example, "polymorphism" when the topic is "OOP").
    focus = question_focus | topic_focus
    answer_terms = set(terms(candidate_answer))
    question_coverage = len(question_focus & answer_terms) / max(1, len(question_focus))
    topic_coverage = len(topic_focus & answer_terms) / max(1, len(topic_focus))
    focus_coverage = max(question_coverage, topic_coverage)
    focus_similarity = text_similarity(" ".join(sorted(focus)), candidate_answer)
    question_relevance = max(
        focus_coverage,
        min(1.0, focus_similarity / 0.24),
    )

    reference_terms = set(terms(reference_answer))
    if reference_terms:
        reference_coverage = len(reference_terms & answer_terms) / len(reference_terms)
        reference_similarity = text_similarity(reference_answer, candidate_answer)
        reference_relevance = max(
            reference_coverage,
            min(1.0, reference_similarity / 0.30),
        )
        # Reference answers often contain optional details; reward a correct
        # direct response even when it does not repeat every reference phrase.
        relevance = 0.75 * question_relevance + 0.25 * reference_relevance
    else:
        reference_coverage = 0.0
        reference_similarity = 0.0
        relevance = question_relevance

    word_count = len(normalize_text(candidate_answer).split())
    sentence_count = max(1, len(re.findall(r"[.!?]+", candidate_answer)))
    completeness = min(word_count / 70.0, 1.0)
    structure = min(sentence_count / 4.0, 1.0)
    normalized_answer = normalize_text(candidate_answer)
    return {
        "focus_term_coverage": focus_coverage,
        "focus_similarity": focus_similarity,
        "question_relevance": question_relevance,
        "reference_term_coverage": reference_coverage,
        "reference_similarity": reference_similarity,
        "answer_relevance": relevance,
        "answer_completeness": completeness,
        "answer_structure": structure,
        "has_example_signal": float(any(x in normalized_answer for x in ("for example", "for instance", "e.g."))),
        "has_reasoning_signal": float(any(x in normalized_answer for x in ("because", "therefore", "so that", "which means"))),
        "word_count": float(word_count),
    }


def calibrated_answer_score(evidence: Dict[str, float], model_score: float | None = None) -> float:
    """Score textual evidence while capping answers with weak topical relevance."""
    score = 10.0 * (
        0.68 * evidence["answer_relevance"]
        + 0.20 * evidence["answer_completeness"]
        + 0.07 * evidence["answer_structure"]
        + 0.025 * evidence["has_example_signal"]
        + 0.025 * evidence["has_reasoning_signal"]
    )
    if model_score is not None:
        # The small training set provides a weak calibration signal, not a
        # reliable judge; keep it from pulling a clearly relevant answer down.
        score = 0.10 * model_score + 0.90 * score

    relevance = evidence["answer_relevance"]
    if relevance < 0.12:
        score = min(score, 2.0)
    elif relevance < 0.22:
        score = min(score, 3.5)
    elif relevance < 0.32:
        score = min(score, 5.0)
    if evidence["word_count"] < 10:
        score = min(score, 6.0)
    return max(0.0, min(10.0, score))


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
    recommendations = []
    if missing:
        recommendations.append(
            "Review the missing terms and add only skills or experience you can support with evidence: "
            + ", ".join(missing[:8])
            + "."
        )
    if not matched:
        recommendations.append(
            "Make relevant tools, methods, and outcomes explicit in your resume where accurate."
        )
    return {
        "match_score": score,
        "keyword_coverage": coverage,
        "matched_terms": matched[:40],
        "missing_terms": missing[:40],
        "recommendations": recommendations,
        "explanation": "Match score is TF-IDF cosine similarity (0-100), not hiring probability. Keyword coverage is the fraction of job-description terms found in the resume.",
    }
