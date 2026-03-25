"""
Numerical question parameter generation.
Generates fresh variable values within template_params ranges.
Uses numerical_mastery to decide whether to reuse last params (if student got wrong)
or generate fresh ones (after correct answer or first attempt).
"""
import random
import math
import re
from typing import Optional


def generate_params(template_params: dict, numerical_mastery: dict, question_id: str) -> dict:
    """
    Return params dict: variables + expected_answer + expected_answer_str.
    Rules:
      - If last attempt was wrong (correct_streak == 0 and last_params exists) → reuse last_params
      - Otherwise → generate fresh values within ranges
    """
    mastery = numerical_mastery.get(question_id, {})
    last_params = mastery.get("last_params")
    correct_streak = mastery.get("correct_streak", 0)

    if last_params and correct_streak == 0:
        # Last attempt was wrong — reuse same numbers so student can learn from feedback
        return last_params

    return _generate_fresh(template_params)


def _generate_fresh(template_params: dict) -> dict:
    variables_spec = template_params.get("variables", {})
    formula = template_params.get("formula_expression", "")
    precision = template_params.get("answer_precision", 2)
    units = template_params.get("units", "")

    generated: dict[str, float] = {}
    for var_name, cfg in variables_spec.items():
        if cfg.get("locked"):
            generated[var_name] = cfg["value"]
        else:
            lo = float(cfg.get("min", 1))
            hi = float(cfg.get("max", 10))
            step = float(cfg.get("step", 1))
            steps = max(int(round((hi - lo) / step)), 1)
            generated[var_name] = round(lo + random.randint(0, steps) * step, 6)

    expected: Optional[float] = None
    expected_str: Optional[str] = None
    if formula:
        try:
            safe_env = {**generated, "math": math, "sqrt": math.sqrt, "pi": math.pi}
            raw = eval(formula, {"__builtins__": {}}, safe_env)  # noqa: S307
            expected = round(float(raw), precision)
            expected_str = f"{expected} {units}".strip()
        except Exception:
            expected = None

    return {
        "variables": generated,
        "expected_answer": expected,
        "expected_answer_str": expected_str,
        "formula_expression": formula,
        "units": units,
        "answer_precision": precision,
    }


def extract_student_number(answer_text: str) -> Optional[float]:
    """Pull the first number out of a student's typed answer."""
    if not answer_text:
        return None
    matches = re.findall(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?", answer_text)
    return float(matches[0]) if matches else None


def check_numerical_answer(student_answer: str, generated: dict) -> tuple[bool, str]:
    """
    Returns (is_correct, comment).
    Tolerates rounding to answer_precision significant digits.
    """
    expected = generated.get("expected_answer")
    units = generated.get("units", "")
    precision = generated.get("answer_precision", 2)

    if expected is None:
        return False, "Could not verify — no expected answer computed."

    val = extract_student_number(student_answer)
    if val is None:
        return False, "No numerical value found in answer."

    tolerance = 10 ** (-(precision - 1)) if precision > 0 else 0.5
    is_correct = abs(val - expected) <= tolerance
    if is_correct:
        return True, f"Correct! Answer: {expected} {units}".strip()
    return False, f"Incorrect. Expected {expected} {units}, got {val}.".strip()
