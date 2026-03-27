"""
index_questions.py — Index pre-built question JSON files into SQLite.

Reads from:  data/questions/{chapter_id}.json  (already built, all 13 chapters)
Writes to:   SQLite question_index table

Use this instead of import_questions.py when data/uploads/ does not exist.

Run:  python -m backend.scripts.index_questions
Safe to re-run — uses INSERT OR REPLACE.
"""
import json
import os
import re
import sys
import glob
import sqlite3

ROOT          = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUESTIONS_DIR = os.path.join(ROOT, "data", "questions")
DB_PATH       = os.path.join(ROOT, "data", "science_assessor.db")

CHAPTER_REGISTRY = [
    {"chapter_id": "ch01_chemical_reactions",   "title": "Chemical Reactions and Equations"},
    {"chapter_id": "ch02_acids_bases_salts",     "title": "Acids, Bases and Salts"},
    {"chapter_id": "ch03_metals_non_metals",     "title": "Metals and Non-Metals"},
    {"chapter_id": "ch04_carbon_compounds",      "title": "Carbon and its Compounds"},
    {"chapter_id": "ch05_life_processes",        "title": "Life Processes"},
    {"chapter_id": "ch06_control_coordination",  "title": "Control and Coordination"},
    {"chapter_id": "ch07_reproduction",          "title": "How do Organisms Reproduce?"},
    {"chapter_id": "ch08_heredity",              "title": "Heredity and Evolution"},
    {"chapter_id": "ch10_light",                 "title": "Light — Reflection and Refraction"},
    {"chapter_id": "ch11_human_eye",             "title": "The Human Eye and the Colourful World"},
    {"chapter_id": "ch12_electricity",           "title": "Electricity"},
    {"chapter_id": "ch13_magnetic_effects",      "title": "Magnetic Effects of Electric Current"},
    {"chapter_id": "ch15_our_environment",       "title": "Our Environment"},
]

# Marks by type
MARKS_BY_TYPE = {
    "mcq": 1,
    "assertion_reason": 1,
    "short": 2,
    "numerical": 2,
    "long": 5,
    "case_based": 4,
    "diagram": 3,
}


_DRAW_PATTERN = re.compile(
    r'\b(draw|sketch|label|labelled diagram|ray diagram|circuit diagram|draw the)\b',
    re.IGNORECASE,
)

def requires_diagram(q: dict) -> bool:
    """True if question has a diagram image OR asks the student to draw/sketch."""
    if q.get("diagram_path"):
        return True
    text = q.get("text") or ""
    return bool(_DRAW_PATTERN.search(text))


def infer_type(q: dict) -> str:
    """Infer question type from ID pattern and options presence."""
    qid = q.get("id", "").lower()
    has_options = bool(q.get("options"))
    has_formula = bool((q.get("rubric") or {}).get("formula"))

    # ID-based patterns first
    if re.search(r"_mcq_|[_\-]mcq\d|mcq_", qid):
        return "mcq"
    if re.search(r"_ar_|_assert|assert_reason", qid):
        return "assertion_reason"
    if re.search(r"_num_|_num\d|numerical", qid):
        return "numerical"
    if re.search(r"_long_|_la_|_la\d|_long\d", qid):
        return "long"
    if re.search(r"_case_|case_based", qid):
        return "case_based"
    if re.search(r"_sa_|_short_|_sht_|_sa\d|short\d", qid):
        return "short"

    # Fallback on content
    if has_options:
        return "mcq"
    if has_formula:
        return "numerical"
    return "short"


def run_index():
    sys.path.insert(0, ROOT)
    from backend.database import init_db
    init_db()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()

    total = 0
    summary = []

    for ch in CHAPTER_REGISTRY:
        chapter_id = ch["chapter_id"]
        json_path  = os.path.join(QUESTIONS_DIR, f"{chapter_id}.json")

        if not os.path.exists(json_path):
            print(f"[SKIP] {chapter_id} — file not found")
            continue

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        questions = data.get("questions", [])
        count = 0

        for q in questions:
            qid = q.get("id")
            if not qid:
                continue

            qtype   = infer_type(q)
            marks   = MARKS_BY_TYPE.get(qtype, 2)
            rubric  = q.get("rubric") or {}
            use_for = q.get("use_for", "")

            # Infer use_for from ID if not set in JSON
            if not use_for:
                qid_lower = qid.lower()
                if "_und_" in qid_lower or "und_" in qid_lower:
                    use_for = "understanding"
                elif "_test_" in qid_lower or qid_lower.startswith("t_"):
                    use_for = "test"

            cur.execute("""
                INSERT OR REPLACE INTO question_index
                (id, chapter, topic, type, difficulty, marks, board_weightage,
                 source, board_years, has_diagram, has_template,
                 times_served, last_served_at, approved, tags, use_for)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                qid,
                chapter_id,
                q.get("topic", rubric.get("topic", "")),  # topic from question or rubric
                qtype,
                2,                             # default mid difficulty
                marks,
                0.0,
                "ncert",
                "",
                1 if requires_diagram(q) else 0,
                1 if q.get("template_params") else 0,
                0,
                None,
                1,                             # approved
                "",
                use_for,
            ))
            count += 1

        total += count
        summary.append((chapter_id, ch["title"], count))

    conn.commit()
    conn.close()

    print()
    print(f"{'Chapter ID':<35} {'Title':<45} {'Questions':>10}")
    print("-" * 93)
    for chapter_id, title, c in summary:
        print(f"{chapter_id:<35} {title[:44]:<45} {c:>10}")
    print("-" * 93)
    print(f"{'TOTAL':<35} {'':<45} {total:>10}")
    print()
    print(f"Indexed {total} questions into SQLite question_index.")


if __name__ == "__main__":
    run_index()
