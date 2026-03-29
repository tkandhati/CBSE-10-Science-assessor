"""
3-Layer evaluation engine (TDD Section 5).

Layer 1 — Deterministic:  MCQ exact match, numerical tolerance check
Layer 2 — Keyword match:  short answers scored by rubric keywords + key_points
Layer 3 — AI (Call 2):    anything Layer 1/2 cannot score confidently
"""
import re
from typing import Optional


# ── helpers ──────────────────────────────────────────────────────────────────

def _empty_feedback(comment: str = "") -> dict:
    return {"keywords_found": [], "points_covered": [], "points_missed": [], "comment": comment}


def _extract_number(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.findall(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?", text)
    return float(m[0]) if m else None


# ── Layer 1: Deterministic ───────────────────────────────────────────────────

def score_mcq(question: dict, selected_option: Optional[int]) -> dict:
    max_marks = question.get("marks", 1)
    options = question.get("options") or []

    if selected_option is None or selected_option < 0 or selected_option >= len(options):
        return {
            "score": 0, "max_marks": max_marks, "is_correct": False,
            "evaluation_layer": "deterministic",
            "feedback": _empty_feedback("No option selected."),
        }

    is_correct = bool(options[selected_option].get("is_correct", False))
    correct_text = next((o["text"] for o in options if o.get("is_correct")), "N/A")

    return {
        "score": max_marks if is_correct else 0,
        "max_marks": max_marks,
        "is_correct": is_correct,
        "evaluation_layer": "deterministic",
        "feedback": _empty_feedback(
            "Correct!" if is_correct else f"Incorrect. Correct answer: {correct_text}"
        ),
    }


def score_numerical(question: dict, answer_text: str, generated_params: Optional[dict]) -> dict:
    max_marks = question.get("marks", 1)

    # Try generated_params first (Understanding sessions), then rubric (Chapter Tests)
    expected: Optional[float] = None
    units = ""
    precision = 2

    if generated_params and generated_params.get("expected_answer") is not None:
        expected = float(generated_params["expected_answer"])
        units = generated_params.get("units", "")
        precision = generated_params.get("answer_precision", 2)
    else:
        # Fallback: extract a number from rubric.expected_answer string
        rubric = question.get("rubric") or {}
        rubric_ans = str(rubric.get("expected_answer") or "")
        nums = re.findall(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?", rubric_ans)
        if nums:
            expected = float(nums[0])

    if expected is None:
        return {
            "score": 0, "max_marks": max_marks, "is_correct": False,
            "evaluation_layer": "deterministic",
            "feedback": _empty_feedback("Could not verify — expected answer not in rubric."),
        }

    tolerance = max(10 ** (-precision), abs(expected) * 0.01)  # 1% or 1e-precision

    student_val = _extract_number(answer_text)
    if student_val is None:
        return {
            "score": 0, "max_marks": max_marks, "is_correct": False,
            "evaluation_layer": "deterministic",
            "feedback": _empty_feedback("No number found in answer."),
        }

    is_correct = abs(student_val - expected) <= tolerance
    comment = (
        f"Correct! {expected} {units}".strip()
        if is_correct
        else f"Incorrect. Expected {expected} {units}, got {student_val}.".strip()
    )
    return {
        "score": max_marks if is_correct else 0,
        "max_marks": max_marks,
        "is_correct": is_correct,
        "evaluation_layer": "deterministic",
        "feedback": {
            "keywords_found": [str(student_val)],
            "points_covered": [f"Answer: {expected} {units}"] if is_correct else [],
            "points_missed": [] if is_correct else [f"Expected {expected} {units}"],
            "comment": comment,
        },
    }


# ── Layer 2: Keyword match ───────────────────────────────────────────────────

def score_keyword(question: dict, answer_text: str) -> Optional[dict]:
    """
    Returns a result dict if enough rubric data exists, else None (→ escalate to Layer 3).
    Requires at least 2 keywords OR 1 key_point to attempt Layer 2.
    """
    rubric = question.get("rubric") or {}
    keywords = [k.lower() for k in (rubric.get("keywords") or [])]
    key_points = rubric.get("key_points") or []
    max_marks = question.get("marks", 1)

    if len(keywords) < 2 and len(key_points) < 1:
        return None  # insufficient rubric — escalate to Claude

    answer_lower = (answer_text or "").lower()

    found_kws = [k for k in keywords if k in answer_lower]
    kw_density = len(found_kws) / len(keywords) if keywords else 1.0

    covered, missed = [], []
    for point in key_points:
        significant = [w for w in point.lower().split() if len(w) > 4]
        if not significant:
            covered.append(point)
            continue
        hit_ratio = sum(1 for w in significant if w in answer_lower) / len(significant)
        if hit_ratio >= 0.5:
            covered.append(point)
        else:
            missed.append(point)

    pt_coverage = len(covered) / len(key_points) if key_points else kw_density
    coverage = (kw_density + pt_coverage) / 2
    score = round(coverage * max_marks, 1)

    # If student got the right final answer but skipped steps, floor score at 35%
    expected_answer = (rubric.get("expected_answer") or "").lower().strip()
    answer_has_correct_result = bool(
        expected_answer and len(expected_answer) > 2 and expected_answer in answer_lower
    )
    min_partial = round(max_marks * 0.35, 1)
    if answer_has_correct_result and score < min_partial:
        score = min_partial

    is_correct = score >= max_marks * 0.8

    if score >= max_marks:
        comment = "Excellent! All key points covered."
    elif score >= max_marks * 0.6:
        hint = missed[0][:60] if missed else "some detail"
        comment = f"Good attempt. Also mention: {hint}."
    elif answer_has_correct_result and missed:
        hints = "; ".join(m[:40] for m in missed[:2])
        comment = f"Correct answer, but show your steps. Missing: {hints}."
    else:
        hints = "; ".join(m[:40] for m in missed[:2])
        comment = f"Needs more detail. Key points missed: {hints}."

    return {
        "score": score,
        "max_marks": max_marks,
        "is_correct": is_correct,
        "evaluation_layer": "keyword",
        "feedback": {
            "keywords_found": found_kws,
            "points_covered": covered,
            "points_missed": missed,
            "comment": comment,
        },
    }


# ── Dispatcher ───────────────────────────────────────────────────────────────

def evaluate_answer(
    question: dict,
    q_type: str,
    answer_text: Optional[str],
    selected_option: Optional[int],
    generated_params: Optional[dict],
) -> tuple[Optional[dict], bool]:
    """
    Try Layer 1 then Layer 2.
    Returns (result_dict | None, needs_ai).
    If needs_ai is True, caller must send to Claude (Layer 3).
    """
    if q_type == "mcq":
        return score_mcq(question, selected_option), False

    if q_type == "numerical":
        return score_numerical(question, answer_text or "", generated_params), False

    # short / long / diagram / assertion_reason → try Layer 2
    result = score_keyword(question, answer_text or "")
    if result is not None:
        return result, False

    # Not enough rubric data — needs Layer 3
    return None, True
