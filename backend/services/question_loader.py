"""
Loads ALL chapter question JSON files into an in-memory dictionary at startup.
Key: question_id  Value: full question content object (normalised to standard schema).
"""
import json
import os

QUESTIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "questions")

# All 13 chapter JSON files
CHAPTER_FILES = [
    "ch01_chemical_reactions.json",
    "ch02_acids_bases_salts.json",
    "ch03_metals_non_metals.json",
    "ch04_carbon_compounds.json",
    "ch05_life_processes.json",
    "ch06_control_coordination.json",
    "ch07_reproduction.json",
    "ch08_heredity.json",
    "ch10_light.json",
    "ch11_human_eye.json",
    "ch12_electricity.json",
    "ch13_magnetic_effects.json",
    "ch15_our_environment.json",
]

_question_store: dict[str, dict] = {}


def _normalise_options(options, rubric: dict) -> list | None:
    """
    Normalise Ch09 old-format options dict  →  standard list-of-dicts.
    Old format: {"A": "text", "B": "text", ...}
    New format: [{"text": "...", "is_correct": bool}, ...]
    Correct option identified from rubric.key_points[0] (e.g. "B").
    """
    if options is None:
        return None
    if isinstance(options, list):
        return options  # already correct format

    # Dict format (Ch09)
    key_points = rubric.get("key_points") or []
    correct_key = key_points[0].strip() if key_points else None

    result = []
    for key, text in options.items():
        result.append({
            "text": text,
            "is_correct": (key.strip() == correct_key) if correct_key else False,
        })
    return result


def load_all_questions() -> dict[str, dict]:
    """Load all chapter JSON files into the in-memory store. Called once at startup."""
    global _question_store
    _question_store = {}
    for filename in CHAPTER_FILES:
        path = os.path.join(QUESTIONS_DIR, filename)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for q in data.get("questions", []):
            rubric = q.get("rubric") or {}
            # Normalise options to list-of-dicts if needed
            if q.get("options") is not None:
                q = dict(q)  # shallow copy so we don't mutate the parsed JSON
                q["options"] = _normalise_options(q["options"], rubric)
            _question_store[q["id"]] = q
    return _question_store


def get_question(question_id: str) -> dict | None:
    return _question_store.get(question_id)


def get_all() -> dict[str, dict]:
    return _question_store
