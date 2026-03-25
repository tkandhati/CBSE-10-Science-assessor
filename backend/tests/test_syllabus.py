"""
test_syllabus.py — data integrity tests for question bank and syllabus.
Tests 1–10 use production DB and files (no test DB) — they are data integrity checks.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
QUESTIONS_DIR = ROOT / "data" / "questions"
SYLLABUS_PATH = ROOT / "data" / "config" / "syllabus.json"
PROD_DB_PATH  = ROOT / "data" / "science_assessor.db"

ALL_CHAPTER_FILES = [
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


def _load_syllabus() -> dict:
    return json.loads(SYLLABUS_PATH.read_text(encoding="utf-8"))


def _prod_conn():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── Test 1 ────────────────────────────────────────────────────────────────────

def test_all_chapter_json_files_exist():
    """All 13 chapter JSON files must be present in data/questions/."""
    missing = [f for f in ALL_CHAPTER_FILES if not (QUESTIONS_DIR / f).exists()]
    assert missing == [], f"Missing chapter files: {missing}"


# ── Test 2 ────────────────────────────────────────────────────────────────────

def test_syllabus_chapters_have_json_files():
    """Every chapter listed in syllabus.json has a corresponding JSON file."""
    syllabus = _load_syllabus()
    missing = []
    for chapter in syllabus.get("chapters", []):
        expected_file = f"{chapter['id']}.json"
        if not (QUESTIONS_DIR / expected_file).exists():
            missing.append(expected_file)
    assert missing == [], f"Syllabus chapters missing JSON files: {missing}"


# ── Test 3 ────────────────────────────────────────────────────────────────────

def test_every_question_has_required_fields():
    """
    Every question must have: id, text, type (or in question_index), rubric present.
    Only checks rubric key existence — not its contents.
    """
    errors = []
    for filename in ALL_CHAPTER_FILES:
        fpath = QUESTIONS_DIR / filename
        if not fpath.exists():
            continue
        data = json.loads(fpath.read_text(encoding="utf-8"))
        for q in data.get("questions", []):
            qid = q.get("id", "<unknown>")
            if not q.get("id"):
                errors.append(f"{filename}: question missing 'id'")
            if not q.get("text"):
                errors.append(f"{filename}/{qid}: missing 'text'")
            if "rubric" not in q:
                errors.append(f"{filename}/{qid}: missing 'rubric' key")

    assert errors == [], "Questions with missing required fields:\n" + "\n".join(errors[:20])


# ── Test 4 ────────────────────────────────────────────────────────────────────

def test_no_duplicate_question_ids():
    """No duplicate question IDs across all 13 chapter JSON files."""
    seen: dict = {}
    duplicates = []
    for filename in ALL_CHAPTER_FILES:
        fpath = QUESTIONS_DIR / filename
        if not fpath.exists():
            continue
        data = json.loads(fpath.read_text(encoding="utf-8"))
        for q in data.get("questions", []):
            qid = q.get("id")
            if qid:
                if qid in seen:
                    duplicates.append(f"{qid} in {filename} and {seen[qid]}")
                else:
                    seen[qid] = filename
    assert duplicates == [], f"Duplicate question IDs: {duplicates}"


# ── Test 5 ────────────────────────────────────────────────────────────────────

def test_question_index_ids_match_json_files():
    """Every question_id in question_index has a matching entry in a chapter JSON file."""
    # Load all JSON IDs
    json_ids: set = set()
    for filename in ALL_CHAPTER_FILES:
        fpath = QUESTIONS_DIR / filename
        if not fpath.exists():
            continue
        data = json.loads(fpath.read_text(encoding="utf-8"))
        for q in data.get("questions", []):
            if q.get("id"):
                json_ids.add(q["id"])

    conn = _prod_conn()
    db_ids = {row["id"] for row in conn.execute("SELECT id FROM question_index").fetchall()}
    conn.close()

    missing_in_json = db_ids - json_ids
    assert len(missing_in_json) == 0, (
        f"{len(missing_in_json)} question_index IDs have no JSON content: "
        f"{list(missing_in_json)[:10]}"
    )


# ── Test 6 ────────────────────────────────────────────────────────────────────

def test_board_weightage_sums_per_chapter():
    """
    For each chapter, the sum of board_weightage across all questions should be
    a reasonable non-zero number (each question has a positive weightage).
    """
    conn = _prod_conn()
    rows = conn.execute(
        "SELECT chapter, SUM(board_weightage) as total_w, COUNT(*) as cnt "
        "FROM question_index WHERE approved=1 GROUP BY chapter"
    ).fetchall()
    conn.close()

    problems = []
    for row in rows:
        if row["total_w"] is None or row["total_w"] <= 0:
            problems.append(f"{row['chapter']}: sum(board_weightage)={row['total_w']}")

    assert problems == [], f"Chapters with bad board_weightage sums: {problems}"


# ── Test 7 ────────────────────────────────────────────────────────────────────

def test_syllabus_total_marks_is_84():
    """syllabus.json total_marks must equal 84."""
    syllabus = _load_syllabus()
    total = syllabus.get("total_marks")
    assert total == 84, f"Expected total_marks=84, got {total}"


# ── Test 8 ────────────────────────────────────────────────────────────────────

def test_our_environment_exists_sources_of_energy_does_not():
    """
    ch15_our_environment.json MUST exist.
    sources_of_energy.json must NOT exist (old name removed).
    """
    assert (QUESTIONS_DIR / "ch15_our_environment.json").exists(), \
        "ch15_our_environment.json is missing"
    assert not (QUESTIONS_DIR / "sources_of_energy.json").exists(), \
        "sources_of_energy.json should not exist (use ch15_our_environment.json)"


# ── Test 9 ────────────────────────────────────────────────────────────────────

def test_physics_chapter_files_use_correct_prefix():
    """
    Physics chapter files must use ch10-ch13 prefixes.
    Old unprefixed names must not exist.
    """
    physics_files = [
        "ch10_light.json",
        "ch11_human_eye.json",
        "ch12_electricity.json",
        "ch13_magnetic_effects.json",
    ]
    old_names = [
        "light.json",
        "human_eye.json",
        "electricity.json",
        "magnetic_effects.json",
    ]

    for f in physics_files:
        assert (QUESTIONS_DIR / f).exists(), f"Missing required file: {f}"

    for f in old_names:
        assert not (QUESTIONS_DIR / f).exists(), f"Old file still present: {f}"


# ── Test 10 ───────────────────────────────────────────────────────────────────

def test_question_index_has_850_approved_questions():
    """question_index must have exactly 850 approved questions."""
    conn = _prod_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM question_index WHERE approved=1"
    ).fetchone()[0]
    conn.close()
    assert count == 850, f"Expected 850 approved questions, found {count}"
