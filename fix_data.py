"""
Migration script — runs all data + DB fixes for Science Assessor expansion.
Safe to re-run (idempotent).
"""
import json, os, shutil, sqlite3, re
from pathlib import Path

ROOT = Path("C:/CBSE10/science")
QUESTIONS_DIR = ROOT / "data" / "questions"
DB_PATH = ROOT / "data" / "science_assessor.db"

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys=OFF")
conn.execute("PRAGMA journal_mode=WAL")

# ── 1. Rename Physics JSON files + fix chapter_id inside ─────────────────────
RENAMES = [
    ("light.json",            "ch10_light.json",            "ch10_light",            "Light — Reflection and Refraction"),
    ("human_eye.json",        "ch11_human_eye.json",        "ch11_human_eye",        "The Human Eye and the Colourful World"),
    ("electricity.json",      "ch12_electricity.json",      "ch12_electricity",      "Electricity"),
    ("magnetic_effects.json", "ch13_magnetic_effects.json", "ch13_magnetic_effects", "Magnetic Effects of Electric Current"),
]

for old_name, new_name, new_id, new_title in RENAMES:
    old_path = QUESTIONS_DIR / old_name
    new_path = QUESTIONS_DIR / new_name
    if old_path.exists():
        data = json.loads(old_path.read_text(encoding="utf-8"))
        old_id = data.get("chapter_id", "")
        data["chapter_id"] = new_id
        data["chapter_title"] = new_title
        new_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        old_path.unlink()
        print(f"  RENAMED {old_name} → {new_name}")
        # Update SQLite
        conn.execute("UPDATE question_index SET chapter=? WHERE chapter=?", (new_id, old_id))
        conn.execute("UPDATE assessments SET chapter=? WHERE chapter=?", (new_id, old_id))
        print(f"  SQL: updated chapter '{old_id}' → '{new_id}'")
    elif new_path.exists():
        print(f"  SKIP {new_name} (already renamed)")
    else:
        print(f"  WARN: {old_name} not found")

# ── 2. Fix sources_of_energy.json → ch15_our_environment.json ────────────────
src_old = QUESTIONS_DIR / "sources_of_energy.json"
src_new = QUESTIONS_DIR / "ch15_our_environment.json"

if src_old.exists() or src_new.exists():
    src = src_old if src_old.exists() else src_new
    data = json.loads(src.read_text(encoding="utf-8"))
    old_ch_id = data.get("chapter_id", "sources_of_energy")

    # Rename question IDs: chap13_eco_* → ch15_*
    id_map = {}
    for q in data["questions"]:
        old_qid = q["id"]
        # replace any prefix like "chap13_eco_" or "sources_" etc with "ch15_"
        new_qid = re.sub(r'^(chap13_eco_|sources_of_energy_|se_)', 'ch15_', old_qid)
        if new_qid == old_qid:
            # fallback: just replace chap13 prefix
            new_qid = old_qid.replace("chap13_eco_", "ch15_").replace("chap13_", "ch15_")
        id_map[old_qid] = new_qid
        q["id"] = new_qid

    data["chapter_id"] = "ch15_our_environment"
    data["chapter_title"] = "Our Environment"

    src_new.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if src_old.exists():
        src_old.unlink()
    print(f"  FIXED sources_of_energy.json → ch15_our_environment.json ({len(id_map)} question IDs updated)")

    # Update SQLite: chapter + question IDs
    conn.execute("UPDATE question_index SET chapter='ch15_our_environment' WHERE chapter=?", (old_ch_id,))
    conn.execute("UPDATE assessments SET chapter='ch15_our_environment' WHERE chapter=?", (old_ch_id,))
    for old_qid, new_qid in id_map.items():
        if old_qid != new_qid:
            # Check if answer rows reference old_qid (update if so)
            conn.execute("UPDATE answers SET question_id=? WHERE question_id=?", (new_qid, old_qid))
            conn.execute("UPDATE question_index SET id=? WHERE id=?", (new_qid, old_qid))
    print(f"  SQL: question IDs updated in question_index + answers")
else:
    print("  SKIP ch15 (neither file found)")

# ── 3. Update board_weightage in question_index ───────────────────────────────
BOARD_WEIGHTS = {
    "ch01_chemical_reactions":  7,
    "ch02_acids_bases_salts":   6,
    "ch03_metals_non_metals":   7,
    "ch04_carbon_compounds":    7,
    "ch05_life_processes":      7,
    "ch06_control_coordination":6,
    "ch07_reproduction":        5,
    "ch08_heredity":            9,
    "ch10_light":               7,
    "ch11_human_eye":           5,
    "ch12_electricity":         8,
    "ch13_magnetic_effects":    7,
    "ch15_our_environment":     3,
}

for chapter_id, board_marks in BOARD_WEIGHTS.items():
    count_row = conn.execute(
        "SELECT COUNT(*) FROM question_index WHERE chapter=?", (chapter_id,)
    ).fetchone()
    count = count_row[0] if count_row else 0
    if count > 0:
        per_q = round(board_marks / count, 6)
        conn.execute(
            "UPDATE question_index SET board_weightage=? WHERE chapter=?",
            (per_q, chapter_id)
        )
        print(f"  board_weightage: {chapter_id} → {per_q:.4f} ({board_marks}m / {count}q)")
    else:
        print(f"  WARN: no questions found for {chapter_id}")

conn.commit()
conn.close()
print("\nMigration complete.")
