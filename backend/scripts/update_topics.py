"""
update_topics.py — TASK 1-5 combined script

1. Reads source files from data/uploads/ to build {question_id: topic}
2. Updates data/questions/*.json with topic field
3. Updates SQLite question_index with topic and use_for values
4. Identifies topic gaps (chapter, topic, use_for combos with count < 2)
5. Generates missing understanding questions
6. Appends generated questions to data/questions/*.json

Run: python -m backend.scripts.update_topics
"""

import json
import os
import sqlite3
import sys
import re
from pathlib import Path
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUESTIONS_DIR = os.path.join(ROOT, "data", "questions")
UPLOADS_DIR = os.path.join(ROOT, "data", "uploads")
DB_PATH = os.path.join(ROOT, "data", "science_assessor.db")

# Mapping: canonical chapter_id -> list of upload Chapter folders to scan
CHAPTER_UPLOAD_MAP = {
    "ch01_chemical_reactions":   ["Chapter01"],
    "ch02_acids_bases_salts":    ["Chapter02"],
    "ch03_metals_non_metals":    ["Chapter03"],
    "ch04_carbon_compounds":     ["Chapter04"],
    "ch05_life_processes":       ["Chapter05"],
    "ch06_control_coordination": ["Chapter06"],
    "ch07_reproduction":         ["Chapter07"],
    "ch08_heredity":             ["Chapter08"],
    "ch10_light":                ["Chapter09", "Chapter10"],  # spherical_mirrors + human_eye topics
    "ch11_human_eye":            ["Chapter11"],               # electric topics -> ch11 canonical
    "ch12_electricity":          ["Chapter11"],               # same uploads as ch11 canonical
    "ch13_magnetic_effects":     ["Chapter12"],               # magnetic topics
    "ch15_our_environment":      ["Chapter13"],               # ecosystem topics
}

# For ch15, the IDs don't match uploads - infer topic from ID prefix
CH15_ID_TOPIC_MAP = {
    "ch15_mcq_001":     "ecosystem_components",
    "ch15_sht_001":     "ecosystem_components",
    "ch15_sht_002":     "ecosystem_components",
    "ch15_lng_001":     "ecosystem_components",
    "ch15_mcq_und_001": "ecosystem_components",
    "ch15_mcq_und_002": "ecosystem_components",
    "ch15_sht_und_001": "ecosystem_components",
    "ch15_sht_und_002": "ecosystem_components",
    "ch15_cb_001":      "ecosystem_components",
}

CH15_PREFIX_TOPIC = {
    "ch15_fcw": "food_chains_webs",
    "ch15_bio": "biological_magnification",
    "ch15_ozo": "ozone_layer",
    "ch15_wst": "waste_management",
}

# For ch11_human_eye canonical: IDs are humaneye10_* which map to Chapter10 uploads
# Chapter10 upload has topics: defects_of_vision, atmospheric_refraction, etc.
# These are already in Chapter10 uploads and will be matched via ch10_light map
# But ch11_human_eye canonical actually holds the humaneye questions
# Let's add Chapter10 to ch11_human_eye mapping too
CHAPTER_UPLOAD_MAP["ch11_human_eye"] = ["Chapter10", "Chapter11"]
# Note: ch10_light canonical has T_CH09_* IDs (from Chapter09) and humaneye10_* IDs (from Chapter10)
# ch11_human_eye canonical has humaneye10_* IDs — we need Chapter10 uploads for that

# For ch12_electricity canonical (chap11_* IDs): Chapter11 uploads
# For ch13_magnetic_effects canonical (chap12_* IDs): Chapter12 uploads


def infer_ch15_topic(qid: str) -> str:
    """Infer topic for ch15 questions from their ID prefix."""
    if qid in CH15_ID_TOPIC_MAP:
        return CH15_ID_TOPIC_MAP[qid]
    for prefix, topic in CH15_PREFIX_TOPIC.items():
        if qid.startswith(prefix):
            return topic
    return "ecosystem_components"


def load_source_questions(chapter_id: str) -> dict:
    """Load all source questions for a chapter, return {id: topic}."""
    id_topic = {}
    folders = CHAPTER_UPLOAD_MAP.get(chapter_id, [])

    for folder in folders:
        for subdir in ["Test", "Understanding"]:
            dir_path = os.path.join(UPLOADS_DIR, folder, "Questions", subdir)
            if not os.path.isdir(dir_path):
                continue
            for fname in os.listdir(dir_path):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(dir_path, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        questions = data
                    elif isinstance(data, dict) and "questions" in data:
                        questions = data["questions"]
                    else:
                        continue
                    for q in questions:
                        qid = q.get("id")
                        topic = q.get("topic", "")
                        if qid and topic:
                            id_topic[qid] = topic
                except Exception as e:
                    print(f"  [WARN] Could not load {fpath}: {e}")
    return id_topic


def infer_use_for_from_id(qid: str) -> str:
    """Infer use_for from question ID patterns."""
    qid_lower = qid.lower()
    # Patterns for understanding
    if re.search(r'_und_|_und\d+|_understanding_', qid_lower):
        return "understanding"
    # Patterns for test
    if re.search(r'^t_ch|_test_|_test\d+', qid_lower):
        return "test"
    return ""


def task1_update_topics():
    """Task 1: Extract topics from uploads and update JSON files + SQLite."""
    print("\n" + "="*70)
    print("TASK 1: Extracting topics and updating JSON + SQLite")
    print("="*70)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=OFF")
    cur = conn.cursor()

    # Ensure use_for column exists (migration)
    try:
        cur.execute("ALTER TABLE question_index ADD COLUMN use_for TEXT NOT NULL DEFAULT ''")
        conn.commit()
        print("  Added use_for column to question_index")
    except Exception:
        pass  # Column already exists

    global_matched = 0
    global_unmatched = 0
    global_use_for_fixed = 0

    for chapter_id in CHAPTER_UPLOAD_MAP:
        json_path = os.path.join(QUESTIONS_DIR, f"{chapter_id}.json")
        if not os.path.exists(json_path):
            print(f"[SKIP] {chapter_id} — JSON not found")
            continue

        # Load source topics
        src_topics = load_source_questions(chapter_id)

        # Load canonical JSON
        with open(json_path, encoding="utf-8") as f:
            canon = json.load(f)

        questions = canon.get("questions", [])
        matched = 0
        unmatched = []

        for q in questions:
            qid = q.get("id", "")
            topic = src_topics.get(qid, "")

            # Special handling for ch15 (IDs don't match uploads)
            if not topic and chapter_id == "ch15_our_environment":
                topic = infer_ch15_topic(qid)

            # Fix use_for for None/missing entries (case-based *_cb_001 questions)
            if q.get("use_for") is None or q.get("use_for", "") == "":
                inferred_uf = infer_use_for_from_id(qid)
                if not inferred_uf:
                    # Default case-based to "test" if ID ends in _cb_
                    if "_cb_" in qid.lower():
                        inferred_uf = "test"
                    else:
                        inferred_uf = "test"
                q["use_for"] = inferred_uf
                global_use_for_fixed += 1

            if topic:
                q["topic"] = topic
                matched += 1
                # Update SQLite topic and use_for
                cur.execute(
                    "UPDATE question_index SET topic=?, use_for=? WHERE id=?",
                    (topic, q["use_for"], qid)
                )
            else:
                unmatched.append(qid)
                # Still update use_for
                cur.execute(
                    "UPDATE question_index SET use_for=? WHERE id=?",
                    (q["use_for"], qid)
                )

        # Save updated JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(canon, f, indent=2, ensure_ascii=False)

        global_matched += matched
        global_unmatched += len(unmatched)
        status = f"matched={matched}, unmatched={len(unmatched)}"
        if unmatched:
            status += f" [{', '.join(unmatched[:3])}{'...' if len(unmatched) > 3 else ''}]"
        print(f"  {chapter_id:<35} {status}")

    conn.commit()
    conn.close()

    print(f"\nSummary: {global_matched} IDs matched with topics, {global_unmatched} had no match")
    print(f"         {global_use_for_fixed} questions had use_for fixed (was None/empty)")
    return global_matched, global_unmatched


def task2_find_gaps():
    """Task 2: Identify (chapter, topic, use_for) combos with count < 2."""
    print("\n" + "="*70)
    print("TASK 2: Identifying topic gaps")
    print("="*70)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT chapter, topic, use_for, COUNT(*) as cnt
        FROM question_index
        WHERE approved=1
        GROUP BY chapter, topic, use_for
        ORDER BY chapter, topic, use_for
    """)
    rows = cur.fetchall()

    # Print full table
    print(f"\n{'Chapter':<35} {'Topic':<42} {'use_for':<15} {'Count':>5}")
    print("-" * 102)
    for chapter, topic, use_for, cnt in rows:
        flag = " <-- GAP" if cnt < 2 else ""
        print(f"  {chapter:<33} {(topic or 'NULL'):<42} {(use_for or 'NULL'):<15} {cnt:>5}{flag}")

    # Find gaps
    gaps = [(c, t, u, n) for c, t, u, n in rows if n < 2]

    print(f"\n{'='*70}")
    print(f"GAPS (count < 2): {len(gaps)} combinations")

    # Build lookup: for each (chapter, topic), understanding count
    understanding_counts = {(c, t): n for c, t, u, n in rows if u == "understanding"}
    test_topics = set((c, t) for c, t, u, n in rows if u == "test")

    understanding_gaps = []
    for (chapter, topic) in sorted(test_topics):
        count = understanding_counts.get((chapter, topic), 0)
        if count < 2:
            understanding_gaps.append((chapter, topic, count))

    print("\nTopics needing more understanding questions:")
    print(f"{'Chapter':<35} {'Topic':<42} {'Current Count':>13}")
    print("-" * 95)
    for chapter, topic, count in understanding_gaps:
        print(f"  {chapter:<33} {topic:<42} {count:>13}")

    if not understanding_gaps:
        print("  (none — all topics have >= 2 understanding questions)")

    conn.close()
    return gaps, understanding_gaps


def load_all_existing_ids() -> set:
    """Load all existing question IDs from all canonical JSON files."""
    ids = set()
    for fname in os.listdir(QUESTIONS_DIR):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(QUESTIONS_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        for q in data.get("questions", []):
            qid = q.get("id")
            if qid:
                ids.add(qid)
    return ids


def make_unique_id(base_id: str, existing_ids: set) -> str:
    """Ensure generated ID is unique."""
    if base_id not in existing_ids:
        return base_id
    i = 2
    while f"{base_id}_{i:03d}" in existing_ids:
        i += 1
    return f"{base_id}_{i:03d}"


# ===== GENERATED QUESTIONS =====
# Topics use exact names from the upload source files (verified from the analysis above)
# Only generating for actual gaps identified

GENERATED_QUESTIONS = {
    # ch10_light: reflection_laws/understanding has only 1 question — needs 1 more
    "ch10_light": {
        "reflection_laws": [
            {
                "id": "gen_ch10_rfl_und_mcq_001",
                "use_for": "understanding",
                "topic": "reflection_laws",
                "text": "The angle of reflection is measured with respect to:",
                "type": "mcq",
                "difficulty": "L1",
                "marks": 1,
                "options": [
                    {"text": "The reflecting surface", "is_correct": False},
                    {"text": "The normal to the reflecting surface at the point of incidence", "is_correct": True},
                    {"text": "The incident ray", "is_correct": False},
                    {"text": "The horizontal plane", "is_correct": False}
                ],
                "rubric": {
                    "keywords": [],
                    "key_points": ["Both angle of incidence and angle of reflection are always measured from the normal to the surface at the point of incidence"],
                    "formula": None,
                    "expected_answer": "The normal to the reflecting surface at the point of incidence",
                    "diagram_required": False,
                    "diagram_checklist": [],
                    "partial_marks": {}
                },
                "template_params": None,
                "diagram_path": None
            },
            {
                "id": "gen_ch10_rfl_und_mcq_002",
                "use_for": "understanding",
                "topic": "reflection_laws",
                "text": "According to the second law of reflection:",
                "type": "mcq",
                "difficulty": "L1",
                "marks": 1,
                "options": [
                    {"text": "The angle of incidence equals twice the angle of reflection", "is_correct": False},
                    {"text": "The incident ray, normal, and reflected ray all lie in the same plane", "is_correct": True},
                    {"text": "The reflected ray is always perpendicular to the incident ray", "is_correct": False},
                    {"text": "The angle of reflection is always 90 degrees", "is_correct": False}
                ],
                "rubric": {
                    "keywords": [],
                    "key_points": ["Second law: The incident ray, the normal at the point of incidence, and the reflected ray — all lie in the same plane"],
                    "formula": None,
                    "expected_answer": "The incident ray, normal, and reflected ray all lie in the same plane",
                    "diagram_required": False,
                    "diagram_checklist": [],
                    "partial_marks": {}
                },
                "template_params": None,
                "diagram_path": None
            }
        ]
    }
}


def task3_generate_questions(understanding_gaps: list) -> dict:
    """Task 3: Generate missing understanding questions for gaps."""
    print("\n" + "="*70)
    print("TASK 3: Generating missing understanding questions")
    print("="*70)

    existing_ids = load_all_existing_ids()
    new_questions_by_chapter = defaultdict(list)

    gaps_handled = 0
    gaps_skipped = 0

    for chapter, topic, current_count in sorted(understanding_gaps):
        needed = 2 - current_count
        available = GENERATED_QUESTIONS.get(chapter, {}).get(topic, [])

        if not available:
            print(f"  [SKIP] {chapter}/{topic} — no generated questions available (need {needed}), current count = {current_count}")
            gaps_skipped += 1
            continue

        added = 0
        for q in available[:needed]:
            qid = q["id"]
            if qid in existing_ids:
                qid = make_unique_id(qid, existing_ids)
                q = dict(q)
                q["id"] = qid
            existing_ids.add(qid)
            new_questions_by_chapter[chapter].append(q)
            added += 1

        if added > 0:
            print(f"  [GEN] {chapter}/{topic}: added {added} question(s) (was {current_count})")
            gaps_handled += 1
        if added < needed:
            print(f"  [WARN] {chapter}/{topic}: only added {added}/{needed} needed questions")

    print(f"\nGenerated questions for {gaps_handled} topic gap(s), {gaps_skipped} gap(s) had no template")
    return dict(new_questions_by_chapter)


def task4_append_and_index(new_by_chapter: dict):
    """Task 4: Append generated questions to JSON files."""
    print("\n" + "="*70)
    print("TASK 4: Appending new questions to data/questions/*.json")
    print("="*70)

    if not new_by_chapter:
        print("  No new questions to append.")
        return

    for chapter_id, new_qs in new_by_chapter.items():
        if not new_qs:
            continue
        json_path = os.path.join(QUESTIONS_DIR, f"{chapter_id}.json")
        if not os.path.exists(json_path):
            print(f"  [SKIP] {chapter_id} — JSON not found")
            continue

        with open(json_path, encoding="utf-8") as f:
            canon = json.load(f)

        existing_count = len(canon.get("questions", []))
        canon["questions"].extend(new_qs)
        new_count = len(canon["questions"])

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(canon, f, indent=2, ensure_ascii=False)

        print(f"  {chapter_id}: {existing_count} -> {new_count} questions (+{new_count - existing_count})")


def task5_verify():
    """Task 5: Verify the final state."""
    print("\n" + "="*70)
    print("TASK 5: Final verification query")
    print("="*70)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT chapter, topic, use_for, COUNT(*) as cnt
        FROM question_index
        WHERE approved=1
        GROUP BY chapter, topic, use_for
        ORDER BY chapter, topic, use_for
    """)
    rows = cur.fetchall()

    print(f"\n{'Chapter':<35} {'Topic':<42} {'use_for':<15} {'Count':>5}")
    print("-" * 102)

    has_issue = False
    for chapter, topic, use_for, cnt in rows:
        flag = ""
        if use_for == "understanding" and cnt < 2:
            flag = " *** BELOW 2 ***"
            has_issue = True
        print(f"  {chapter:<33} {(topic or 'NULL'):<42} {(use_for or 'NULL'):<15} {cnt:>5}{flag}")

    if has_issue:
        print("\n*** WARNING: Some understanding topics still have fewer than 2 questions! ***")
    else:
        print("\nAll (chapter, topic, use_for=understanding) combinations have >= 2 questions.")

    cur.execute("""
        SELECT COUNT(*),
               COUNT(CASE WHEN topic!='' AND topic IS NOT NULL THEN 1 END),
               COUNT(CASE WHEN use_for!='' AND use_for IS NOT NULL THEN 1 END)
        FROM question_index WHERE approved=1
    """)
    total, with_topic, with_use_for = cur.fetchone()
    print(f"\nTotal approved questions:  {total}")
    print(f"With topic filled:         {with_topic}")
    print(f"Without topic:             {total - with_topic}")
    print(f"With use_for filled:       {with_use_for}")
    print(f"Without use_for:           {total - with_use_for}")

    conn.close()


def main():
    print("Science Assessor -- Topic Update + Gap Fill")
    print("=" * 70)

    sys.path.insert(0, ROOT)

    # Task 1: Update topics in JSON and SQLite
    task1_update_topics()

    # Task 2: Find gaps
    gaps, understanding_gaps = task2_find_gaps()

    # Task 3: Generate missing questions
    new_questions = task3_generate_questions(understanding_gaps)

    # Task 4: Append to JSON files
    task4_append_and_index(new_questions)

    # Re-run index_questions to get new questions into SQLite with topics + use_for
    if new_questions:
        print("\n" + "="*70)
        print("Re-indexing all questions into SQLite...")
        print("="*70)
        from backend.scripts.index_questions import run_index
        run_index()

        # Re-apply topic updates for newly indexed questions
        print("\nRe-applying topic updates to newly indexed questions...")
        task1_update_topics()
    else:
        print("\nNo new questions added — skipping re-index.")

    # Task 5: Verify
    task5_verify()

    print("\n" + "="*70)
    print("All tasks complete!")
    print("="*70)


if __name__ == "__main__":
    main()
