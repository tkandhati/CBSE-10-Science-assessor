"""
LEGACY import script — reads raw source files from data/uploads/.

DO NOT run this script. The pre-built question JSON files in data/questions/
are the authoritative source. Running this script will OVERWRITE those files
with raw source data from data/uploads/ (which may contain mismatched chapter
folder mappings and is not committed to git).

Use index_questions.py instead:
    python -m backend.scripts.index_questions

This file is kept only as a reference for how the original import worked.
"""
import sys
print("ERROR: Do not run import_questions.py.")
print("Use instead:  python -m backend.scripts.index_questions")
sys.exit(1)

# ---- original code below (disabled) ----
if False:
    pass
import json
import os
import sys
import glob
import sqlite3

ROOT         = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UPLOADS_DIR  = os.path.join(ROOT, "data", "uploads")
QUESTIONS_DIR = os.path.join(ROOT, "data", "questions")
DB_PATH      = os.path.join(ROOT, "data", "science_assessor.db")

# All 13 NCERT Class 10 Science chapters
# chapter_id  : used as filename key and SQLite chapter column
# ncert_ch    : chapter number in NCERT book
# folder      : subfolder name under data/uploads/
# title       : fallback title if metadata.json absent
CHAPTER_REGISTRY = [
    {"chapter_id": "ch01_chemical_reactions",   "ncert_ch":  1, "folder": "Chapter01", "title": "Chemical Reactions and Equations"},
    {"chapter_id": "ch02_acids_bases_salts",    "ncert_ch":  2, "folder": "Chapter02", "title": "Acids, Bases and Salts"},
    {"chapter_id": "ch03_metals_non_metals",    "ncert_ch":  3, "folder": "Chapter03", "title": "Metals and Non-Metals"},
    {"chapter_id": "ch04_carbon_compounds",     "ncert_ch":  4, "folder": "Chapter04", "title": "Carbon and its Compounds"},
    {"chapter_id": "ch05_life_processes",       "ncert_ch":  6, "folder": "Chapter05", "title": "Life Processes"},
    {"chapter_id": "ch06_control_coordination", "ncert_ch":  7, "folder": "Chapter06", "title": "Control and Coordination"},
    {"chapter_id": "ch07_reproduction",         "ncert_ch":  8, "folder": "Chapter07", "title": "How do Organisms Reproduce?"},
    {"chapter_id": "ch08_heredity",             "ncert_ch":  9, "folder": "Chapter08", "title": "Heredity and Evolution"},
    {"chapter_id": "ch10_light",                "ncert_ch": 10, "folder": "Chapter10", "title": "Light -- Reflection and Refraction"},
    {"chapter_id": "ch11_human_eye",            "ncert_ch": 11, "folder": "Chapter11", "title": "The Human Eye and the Colourful World"},
    {"chapter_id": "ch12_electricity",          "ncert_ch": 12, "folder": "Chapter12", "title": "Electricity"},
    {"chapter_id": "ch13_magnetic_effects",     "ncert_ch": 13, "folder": "Chapter13", "title": "Magnetic Effects of Electric Current"},
    {"chapter_id": "ch15_our_environment",      "ncert_ch": 15, "folder": "Chapter15", "title": "Our Environment"},
]

DIFFICULTY_MAP = {"L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5}

TYPE_MAP = {
    "short_answer":     "short",
    "long_answer":      "long",
    "mcq":              "mcq",
    "numerical":        "numerical",
    "diagram":          "diagram",
    "assertion_reason": "assertion_reason",
    "case_based":       "case_based",
}


def _empty_rubric() -> dict:
    return {
        "keywords": [], "key_points": [], "formula": None,
        "expected_answer": "", "diagram_required": False,
        "diagram_checklist": [], "partial_marks": {}
    }


def _difficulty_int(raw) -> int:
    return DIFFICULTY_MAP.get(str(raw), 1)


def _type_str(raw: str) -> str:
    return TYPE_MAP.get(raw, raw)


def transform_new_schema(q: dict, chapter_id: str, use_for: str):
    """TDD-schema questions (Ch01-Ch08, Ch10-Ch12)."""
    rubric = q.get("rubric") or _empty_rubric()
    content = {
        "id":              q["id"],
        "use_for":         q.get("use_for", use_for),
        "text":            q.get("text", ""),
        "options":         q.get("options"),
        "rubric":          rubric,
        "template_params": q.get("template_params"),
        "diagram_path":    q.get("question_image"),
    }
    index_row = {
        "id":              q["id"],
        "chapter":         chapter_id,
        "topic":           q.get("topic", ""),
        "type":            _type_str(q.get("type", "short")),
        "difficulty":      _difficulty_int(q.get("difficulty", "L1")),
        "marks":           q.get("marks", 1),
        "board_weightage": 0.0,
        "source":          q.get("source", ""),
        "board_years":     ",".join(str(y) for y in q.get("board_years", [])),
        "has_diagram":     1 if q.get("question_image") else 0,
        "has_template":    1 if q.get("template_params") else 0,
        "times_served":    0,
        "last_served_at":  None,
        "approved":        1,   # imported questions are approved by default
        "tags":            ",".join(q.get("tags", [])) if isinstance(q.get("tags"), list) else str(q.get("tags", "")),
    }
    return content, index_row


def transform_old_schema(q: dict, chapter_id: str, use_for: str):
    """Old-schema questions (Ch09 only — uses 'question'/'answer'/'explanation' fields)."""
    rubric = _empty_rubric()
    answer = q.get("answer", "")
    explanation = q.get("explanation", "")
    rubric["expected_answer"] = f"{answer}\n{explanation}".strip()
    if answer:
        rubric["key_points"] = [answer]

    content = {
        "id":              q["id"],
        "use_for":         use_for,
        "text":            q.get("question", ""),
        "options":         q.get("options"),
        "rubric":          rubric,
        "template_params": None,
        "diagram_path":    None,
    }
    index_row = {
        "id":              q["id"],
        "chapter":         chapter_id,
        "topic":           q.get("topic", ""),
        "type":            _type_str(q.get("type", "short")),
        "difficulty":      _difficulty_int(q.get("difficulty", "L1")),
        "marks":           q.get("marks", 1),
        "board_weightage": 0.0,
        "source":          "ncert",
        "board_years":     "",
        "has_diagram":     0,
        "has_template":    0,
        "times_served":    0,
        "last_served_at":  None,
        "approved":        1,
        "tags":            "",
    }
    return content, index_row


def is_old_schema(q: dict) -> bool:
    return "question" in q and "text" not in q


def load_raw_questions(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    for key in ("test_questions", "understanding_questions", "questions"):
        if key in data:
            return data[key]
    return []


def load_metadata(chapter_dir: str, fallback_title: str) -> dict:
    meta_path = os.path.join(chapter_dir, "Questions", "metadata.json")
    if not os.path.exists(meta_path):
        return {"chapter_title": fallback_title}
    with open(meta_path, encoding="utf-8") as f:
        m = json.load(f)
    # metadata uses either chapter_title or chapter_name
    title = m.get("chapter_title") or m.get("chapter_name") or fallback_title
    return {**m, "chapter_title": title}


def find_json_files(folder: str) -> list[str]:
    """Return all .json files in a folder, sorted."""
    return sorted(glob.glob(os.path.join(folder, "*.json")))


def run_import():
    # Ensure DB and tables exist
    sys.path.insert(0, ROOT)
    from backend.database import init_db
    init_db()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()

    total_questions = 0
    summary_rows = []

    for ch in CHAPTER_REGISTRY:
        chapter_id  = ch["chapter_id"]
        folder_name = ch["folder"]
        chapter_dir = os.path.join(UPLOADS_DIR, folder_name)

        if not os.path.exists(chapter_dir):
            print(f"[SKIP] {chapter_id} — folder not found: {folder_name}")
            continue

        meta = load_metadata(chapter_dir, ch["title"])
        chapter_title = meta["chapter_title"]

        content_list = []
        ids_seen     = set()
        test_count   = 0
        und_count    = 0

        for use_for, sub in [("test", "Test"), ("understanding", "Understanding")]:
            sub_dir = os.path.join(chapter_dir, "Questions", sub)
            if not os.path.exists(sub_dir):
                continue

            json_files = find_json_files(sub_dir)
            for path in json_files:
                raw = load_raw_questions(path)
                for q in raw:
                    if not q.get("id"):
                        continue
                    if q["id"] in ids_seen:
                        continue
                    ids_seen.add(q["id"])

                    if is_old_schema(q):
                        content, index_row = transform_old_schema(q, chapter_id, use_for)
                    else:
                        content, index_row = transform_new_schema(q, chapter_id, use_for)

                    content_list.append(content)

                    cur.execute("""
                        INSERT OR REPLACE INTO question_index
                        (id, chapter, topic, type, difficulty, marks, board_weightage,
                         source, board_years, has_diagram, has_template,
                         times_served, last_served_at, approved, tags)
                        VALUES
                        (:id, :chapter, :topic, :type, :difficulty, :marks, :board_weightage,
                         :source, :board_years, :has_diagram, :has_template,
                         :times_served, :last_served_at, :approved, :tags)
                    """, index_row)

                    if use_for == "test":
                        test_count += 1
                    else:
                        und_count += 1

        # Write chapter content JSON
        out_path = os.path.join(QUESTIONS_DIR, f"{chapter_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {"chapter_id": chapter_id, "chapter_title": chapter_title, "questions": content_list},
                f, indent=2, ensure_ascii=False
            )

        total_questions += len(content_list)
        summary_rows.append((chapter_id, chapter_title, test_count, und_count, len(content_list)))

    conn.commit()
    conn.close()

    # Print summary table
    print()
    print(f"{'Chapter ID':<35} {'Title':<45} {'Test':>5} {'Und':>5} {'Total':>7}")
    print("-" * 100)
    for chapter_id, title, t, u, total in summary_rows:
        print(f"{chapter_id:<35} {title[:44]:<45} {t:>5} {u:>5} {total:>7}")
    print("-" * 100)
    print(f"{'TOTAL':<35} {'':<45} {sum(r[2] for r in summary_rows):>5} {sum(r[3] for r in summary_rows):>5} {total_questions:>7}")
    print()
    print(f"Import complete. {total_questions} questions indexed into SQLite and written to data/questions/")


if __name__ == "__main__":
    run_import()
