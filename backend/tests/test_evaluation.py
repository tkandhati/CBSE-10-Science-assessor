"""
test_evaluation.py — Tests 23-33.
Tests the 3-layer evaluation engine directly (no DB required).
"""
import pytest
from backend.services.evaluator import (
    evaluate_answer,
    score_mcq,
    score_numerical,
    score_keyword,
)


# ── Fixtures / helpers ────────────────────────────────────────────────────────

def _mcq_question(correct_index: int = 1, marks: int = 1) -> dict:
    """Build a minimal MCQ question dict."""
    options = [
        {"text": "Option A", "is_correct": i == correct_index}
        for i in range(4)
    ]
    return {
        "id": "test_mcq",
        "text": "Test MCQ question",
        "type": "mcq",
        "marks": marks,
        "options": options,
        "rubric": {},
    }


def _numerical_question(expected: float = 10.0, marks: int = 3, units: str = "m/s") -> dict:
    return {
        "id": "test_num",
        "text": "Calculate velocity",
        "type": "numerical",
        "marks": marks,
        "rubric": {"expected_answer": f"{expected} {units}"},
    }


def _short_question(keywords: list = None, key_points: list = None, marks: int = 2) -> dict:
    return {
        "id": "test_short",
        "text": "Explain reflection of light",
        "type": "short",
        "marks": marks,
        "rubric": {
            "keywords": keywords or [],
            "key_points": key_points or [],
        },
    }


# ── Test 23 ──────────────────────────────────────────────────────────────────

def test_mcq_correct_option_full_marks():
    """MCQ correct option → full marks, deterministic layer."""
    q = _mcq_question(correct_index=2, marks=1)
    result = score_mcq(q, 2)
    assert result["score"] == 1
    assert result["max_marks"] == 1
    assert result["is_correct"] is True
    assert result["evaluation_layer"] == "deterministic"


# ── Test 24 ──────────────────────────────────────────────────────────────────

def test_mcq_wrong_option_zero_marks():
    """MCQ wrong option → 0 marks."""
    q = _mcq_question(correct_index=1, marks=1)
    result = score_mcq(q, 0)  # selecting option 0, correct is 1
    assert result["score"] == 0
    assert result["is_correct"] is False
    assert result["evaluation_layer"] == "deterministic"


# ── Test 25 ──────────────────────────────────────────────────────────────────

def test_numerical_correct_answer_full_marks():
    """Numerical correct answer → full marks."""
    q = _numerical_question(expected=10.0, marks=3)
    result = score_numerical(q, "10.0 m/s", None)
    assert result["score"] == 3
    assert result["is_correct"] is True
    assert result["evaluation_layer"] == "deterministic"


# ── Test 26 ──────────────────────────────────────────────────────────────────

def test_numerical_wrong_answer_zero_marks():
    """Numerical clearly wrong answer → 0 marks."""
    q = _numerical_question(expected=10.0, marks=3)
    result = score_numerical(q, "999 m/s", None)
    assert result["score"] == 0
    assert result["is_correct"] is False


# ── Test 27 ──────────────────────────────────────────────────────────────────

def test_numerical_correct_value_no_units_in_question():
    """Numerical correct value even when question has no units → full marks."""
    q = {
        "id": "test_num_nounits",
        "text": "Calculate current",
        "type": "numerical",
        "marks": 2,
        "rubric": {"expected_answer": "5.0"},
    }
    # Student just writes the number without units
    result = score_numerical(q, "5.0", None)
    assert result["score"] == 2
    assert result["is_correct"] is True


# ── Test 28 ──────────────────────────────────────────────────────────────────

def test_short_answer_all_keywords_high_score():
    """Short answer with ALL keywords present → high score (>=80%)."""
    q = _short_question(
        keywords=["reflection", "angle", "normal", "incident", "mirror"],
        marks=2,
    )
    answer = "The angle of reflection equals the angle of incidence, both measured from the normal to the mirror surface."
    result = score_keyword(q, answer)
    assert result is not None
    assert result["score"] >= 2 * 0.8, f"Expected >=1.6, got {result['score']}"
    assert result["evaluation_layer"] == "keyword"


# ── Test 29 ──────────────────────────────────────────────────────────────────

def test_short_answer_partial_keywords_partial_score():
    """Short answer with partial keywords (~50%) → partial score."""
    q = _short_question(
        keywords=["reflection", "angle", "normal", "incident", "mirror"],
        marks=2,
    )
    # Only 2-3 of the 5 keywords present
    answer = "reflection occurs at angle"
    result = score_keyword(q, answer)
    assert result is not None
    # Score should be less than full marks
    assert result["score"] < 2.0, f"Expected partial score < 2.0, got {result['score']}"
    assert result["score"] > 0, "Expected some partial credit"


# ── Test 30 ──────────────────────────────────────────────────────────────────

def test_short_answer_no_keywords_zero_score():
    """Short answer with none of the keywords → 0 score."""
    q = _short_question(
        keywords=["reflection", "angle", "normal", "incident", "mirror"],
        marks=2,
    )
    answer = "I do not know the answer"
    result = score_keyword(q, answer)
    assert result is not None
    assert result["score"] == 0.0 or result["score"] < 0.4, (
        f"Expected near-zero score for irrelevant answer, got {result['score']}"
    )


# ── Test 31 ──────────────────────────────────────────────────────────────────

def test_short_answer_insufficient_rubric_needs_ai():
    """Short answer with insufficient rubric (<2 keywords, no key_points) → None (needs AI)."""
    q = _short_question(keywords=["reflection"], key_points=[], marks=3)
    result = score_keyword(q, "some answer about reflection")
    assert result is None, (
        "Expected None (escalate to AI) for insufficient rubric"
    )


# ── Test 32 ──────────────────────────────────────────────────────────────────

def test_evaluate_answer_dispatcher():
    """evaluate_answer dispatcher routes correctly."""
    # MCQ → deterministic, no AI
    mcq_q = _mcq_question(correct_index=0, marks=1)
    r, needs_ai = evaluate_answer(mcq_q, "mcq", None, 0, None)
    assert r is not None
    assert needs_ai is False

    # Numerical → deterministic, no AI
    num_q = _numerical_question(expected=5.0, marks=2)
    r, needs_ai = evaluate_answer(num_q, "numerical", "5.0", None, None)
    assert r is not None
    assert needs_ai is False

    # Short with good rubric → keyword scored, no AI
    short_q = _short_question(
        keywords=["current", "resistance", "voltage", "ohm"],
        marks=2,
    )
    r, needs_ai = evaluate_answer(short_q, "short", "current equals voltage divided by resistance (ohm's law)", None, None)
    assert r is not None
    assert needs_ai is False

    # Short with minimal rubric → needs AI
    minimal_q = _short_question(keywords=["reflection"], key_points=[], marks=2)
    r, needs_ai = evaluate_answer(minimal_q, "short", "some answer", None, None)
    assert r is None
    assert needs_ai is True


# ── Test 33 ──────────────────────────────────────────────────────────────────

def test_evaluation_layer_labels():
    """evaluation_layer is 'deterministic' for MCQ/numerical, 'keyword' for keyword-scored."""
    # MCQ
    mcq_q = _mcq_question(correct_index=1, marks=1)
    r, _ = evaluate_answer(mcq_q, "mcq", None, 1, None)
    assert r["evaluation_layer"] == "deterministic"

    # Numerical
    num_q = _numerical_question(expected=10.0, marks=3)
    r, _ = evaluate_answer(num_q, "numerical", "10.0", None, None)
    assert r["evaluation_layer"] == "deterministic"

    # Short answer with good rubric
    short_q = _short_question(
        keywords=["reflection", "angle", "normal", "incidence"],
        key_points=["Angle of incidence equals angle of reflection"],
        marks=2,
    )
    r, _ = evaluate_answer(short_q, "short", "reflection angle equals incidence angle at normal", None, None)
    assert r is not None
    assert r["evaluation_layer"] == "keyword"


# ── Bonus: generated_params path ─────────────────────────────────────────────

def test_numerical_uses_generated_params_when_available():
    """score_numerical uses generated_params expected_answer over rubric when available."""
    q = _numerical_question(expected=99.0, marks=2)  # rubric says 99.0
    gen_params = {
        "expected_answer": 5.0,
        "units": "A",
        "answer_precision": 1,
    }
    # Student answers 5.0 — correct per gen_params (not rubric)
    result = score_numerical(q, "5.0 A", gen_params)
    assert result["score"] == 2
    assert result["is_correct"] is True


def test_numerical_no_expected_answer_returns_zero():
    """If no expected answer in rubric or gen_params, score is 0."""
    q = {
        "id": "num_empty",
        "text": "Find x",
        "type": "numerical",
        "marks": 2,
        "rubric": {"expected_answer": ""},
    }
    result = score_numerical(q, "42", None)
    assert result["score"] == 0
    assert result["is_correct"] is False


def test_mcq_no_option_selected_zero_marks():
    """MCQ with None selected_option → 0 marks."""
    q = _mcq_question(correct_index=0, marks=1)
    result = score_mcq(q, None)
    assert result["score"] == 0
    assert result["is_correct"] is False
