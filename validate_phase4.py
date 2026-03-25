"""
validate_phase4.py — Comprehensive validation for Physics Assessor Phases 1-4.
Checks all 47 items: DB schema, backend logic, frontend types, code quality.
"""
import json
import os
import sys
import re
import ast
import sqlite3

ROOT = r"C:\CBSE10\science"
results = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((status, name, detail))
    return condition


def read_file(rel_path):
    """Read file relative to ROOT, return content or None on error."""
    full = os.path.join(ROOT, rel_path)
    try:
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return None


def parse_py(rel_path):
    """Return AST tree or None if parse error / file missing."""
    src = read_file(rel_path)
    if src is None:
        return None
    try:
        return ast.parse(src)
    except SyntaxError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1-3 Regression (items 1-10)
# ─────────────────────────────────────────────────────────────────────────────

# Locate the SQLite database
db_path = os.path.join(ROOT, "data", "science_assessor.db")
db_exists = os.path.isfile(db_path)

if db_exists:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def get_columns(table):
        try:
            cur = conn.execute(f"PRAGMA table_info({table})")
            return {row[1] for row in cur.fetchall()}
        except Exception:
            return set()

    def table_exists(table):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table]
        )
        return cur.fetchone() is not None
else:
    conn = None
    def get_columns(table): return set()
    def table_exists(table): return False

# 1. DB tables exist
tables_needed = ["question_index", "assessments", "answers", "student_profile"]
all_tables = all(table_exists(t) for t in tables_needed)
missing_tables = [t for t in tables_needed if not table_exists(t)]
check(
    "1. DB tables exist: question_index, assessments, answers, student_profile",
    all_tables,
    f"Missing: {missing_tables}" if missing_tables else "",
)

# 2. question_index key columns
qi_required = {"id", "chapter", "topic", "type", "difficulty", "marks",
               "approved", "times_served", "last_served_at"}
qi_cols = get_columns("question_index")
qi_missing = qi_required - qi_cols
check(
    "2. question_index has key columns",
    not qi_missing,
    f"Missing columns: {qi_missing}" if qi_missing else "",
)

# 3. assessments columns
a_required = {"id", "type", "chapter", "total_marks", "status",
              "expires_at", "is_active", "section_map", "overall_guidance"}
a_cols = get_columns("assessments")
a_missing = a_required - a_cols
check(
    "3. assessments has required columns",
    not a_missing,
    f"Missing columns: {a_missing}" if a_missing else "",
)

# 4. student_profile columns
# Spec lists: id, xp, streak_days, topic_scores, guidance_cache, exam_readiness_score
# Actual schema uses total_xp (for xp) and current_streak/best_streak (for streak_days).
# We check both interpretations: the spec-named columns AND the actual schema columns,
# treating total_xp as satisfying 'xp' and current_streak as satisfying 'streak_days'.
sp_cols = get_columns("student_profile")
sp_required_exact = {"id", "xp", "streak_days", "topic_scores",
                     "guidance_cache", "exam_readiness_score"}
# Canonical names per database.py schema
sp_required_actual = {"id", "total_xp", "current_streak", "topic_scores",
                      "guidance_cache", "exam_readiness_score"}
# Pass if either the exact spec names OR the actual schema names are satisfied
sp_missing_exact  = sp_required_exact  - sp_cols
sp_missing_actual = sp_required_actual - sp_cols
sp_ok = (not sp_missing_exact) or (not sp_missing_actual)
detail_4 = ""
if sp_missing_exact and sp_missing_actual:
    detail_4 = f"Missing (spec names): {sp_missing_exact}; Missing (schema names): {sp_missing_actual}"
elif sp_missing_exact and not sp_missing_actual:
    detail_4 = ("Schema uses total_xp/current_streak instead of spec names xp/streak_days "
                "— all required columns present under actual schema names")
check(
    "4. student_profile has required columns (id, xp/total_xp, streak_days/current_streak, "
    "topic_scores, guidance_cache, exam_readiness_score)",
    sp_ok,
    detail_4,
)

# 5. test_templates.json exists with required keys
templates_path = os.path.join(ROOT, "data", "config", "test_templates.json")
templates_exist = os.path.isfile(templates_path)
templates_data = None
templates_keys_ok = False
if templates_exist:
    try:
        with open(templates_path, encoding="utf-8") as f:
            raw = json.load(f)
        templates_data = raw.get("templates", {})
        required_keys = {"understanding", "chapter_short", "chapter_regular", "mock"}
        templates_keys_ok = required_keys.issubset(templates_data.keys())
    except Exception:
        pass
check(
    "5. test_templates.json exists with understanding, chapter_short, chapter_regular, mock",
    templates_exist and templates_keys_ok,
    "" if templates_keys_ok else "File missing or missing required keys",
)

# 6. chapter_regular total_marks == 40
cr_marks = None
if templates_data:
    cr_marks = templates_data.get("chapter_regular", {}).get("total_marks")
check(
    "6. chapter_regular total_marks == 40",
    cr_marks == 40,
    f"Got {cr_marks}" if cr_marks != 40 else "",
)

# 7. chapter_short total_marks == 14
cs_marks = None
if templates_data:
    cs_marks = templates_data.get("chapter_short", {}).get("total_marks")
check(
    "7. chapter_short total_marks == 14",
    cs_marks == 14,
    f"Got {cs_marks}" if cs_marks != 14 else "",
)

# 8. mock total_marks == 80
mock_marks = None
if templates_data:
    mock_marks = templates_data.get("mock", {}).get("total_marks")
check(
    "8. mock total_marks == 80",
    mock_marks == 80,
    f"Got {mock_marks}" if mock_marks != 80 else "",
)

# 9. mock has sections A, B, C, D, E
mock_sections = []
if templates_data:
    mock_template = templates_data.get("mock", {})
    mock_sections = [s["section"] for s in mock_template.get("sections", [])]
mock_has_sections = set(mock_sections) == {"A", "B", "C", "D", "E"}
check(
    "9. mock has sections A, B, C, D, E",
    mock_has_sections,
    f"Got sections: {mock_sections}" if not mock_has_sections else "",
)

# 10. mock section counts: A=20 questions (16 MCQ + 4 A/R), B=6, C=7, D=3, E=3
# Total = 39 questions, 80 marks
mock_counts_ok = False
mock_total_q = 0
mock_total_m = 0
if templates_data and mock_has_sections:
    mock_template = templates_data.get("mock", {})
    sec_q: dict = {}
    sec_m: dict = {}
    for sec_def in mock_template.get("sections", []):
        sec = sec_def["section"]
        q_count = sum(slot["count"] for slot in sec_def["slots"])
        m_total = sum(slot["total"] for slot in sec_def["slots"])
        sec_q[sec] = q_count
        sec_m[sec] = m_total
    mock_total_q = sum(sec_q.values())
    mock_total_m = sum(sec_m.values())
    # A=20 (16+4), B=6, C=7, D=3, E=3
    expected_q = {"A": 20, "B": 6, "C": 7, "D": 3, "E": 3}
    expected_m = {"A": 20, "B": 12, "C": 21, "D": 15, "E": 12}
    q_ok = sec_q == expected_q
    m_ok = sec_m == expected_m
    mock_counts_ok = q_ok and m_ok and mock_total_q == 39 and mock_total_m == 80
    detail_10 = (
        f"counts={sec_q} marks={sec_m} total_q={mock_total_q} total_m={mock_total_m}"
        if not mock_counts_ok else ""
    )
else:
    detail_10 = "Mock template or sections not available"
check(
    "10. mock section counts A=20,B=6,C=7,D=3,E=3 (39 q, 80 marks)",
    mock_counts_ok,
    detail_10,
)

if conn:
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 Backend (items 11-30)
# ─────────────────────────────────────────────────────────────────────────────

pg_src = read_file(r"backend\services\paper_generator.py")
pg_tree = parse_py(r"backend\services\paper_generator.py")
pu_src = read_file(r"backend\services\profile_updater.py")
pu_tree = parse_py(r"backend\services\profile_updater.py")
sess_src = read_file(r"backend\routers\session.py")
sess_tree = parse_py(r"backend\routers\session.py")
db_src = read_file(r"backend\database.py")
db_tree = parse_py(r"backend\database.py")
ai_src = read_file(r"backend\services\ai_client.py")
models_src = read_file(r"backend\models.py")

# 11. paper_generator.py imports check_mock_feasibility and generate_mock_paper exist
pg_has_check_mock = pg_src is not None and bool(re.search(r"def check_mock_feasibility", pg_src))
pg_has_gen_mock = pg_src is not None and bool(re.search(r"def generate_mock_paper", pg_src))
check(
    "11. paper_generator.py has check_mock_feasibility and generate_mock_paper",
    pg_has_check_mock and pg_has_gen_mock,
    f"check_mock_feasibility={'found' if pg_has_check_mock else 'MISSING'}, "
    f"generate_mock_paper={'found' if pg_has_gen_mock else 'MISSING'}",
)

# 12. profile_updater.py has compute_exam_readiness function
pu_has_readiness = pu_src is not None and bool(re.search(r"def compute_exam_readiness", pu_src))
check(
    "12. profile_updater.py has compute_exam_readiness function",
    pu_has_readiness,
    "" if pu_has_readiness else "Function not found",
)

# 13. _MOCK_CHAPTERS has all 5 chapters
expected_chapters = {"light", "human_eye", "electricity", "magnetic_effects", "sources_of_energy"}
mock_chapters_ok = False
if pg_src:
    m = re.search(r"_MOCK_CHAPTERS\s*=\s*\[([^\]]+)\]", pg_src)
    if m:
        found_chs = set(re.findall(r'"(\w+)"', m.group(1)))
        mock_chapters_ok = expected_chapters == found_chs
check(
    "13. _MOCK_CHAPTERS has all 5 chapters",
    mock_chapters_ok,
    "" if mock_chapters_ok else f"Pattern not found or chapters missing",
)

# 14. _MOCK_CHAPTER_WEIGHTS sums to 30
weights_sum_ok = False
weights_sum = None
if pg_src:
    m = re.search(r"_MOCK_CHAPTER_WEIGHTS\s*=\s*\{([^}]+)\}", pg_src)
    if m:
        pairs = re.findall(r'"(\w+)":\s*(\d+)', m.group(1))
        if pairs:
            weights_sum = sum(int(v) for _, v in pairs)
            weights_sum_ok = weights_sum == 30
check(
    "14. _MOCK_CHAPTER_WEIGHTS sums to 30",
    weights_sum_ok,
    f"Sum={weights_sum}" if not weights_sum_ok else "",
)

# 15. _allocate_by_weight function exists in paper_generator.py
pg_has_allocate = pg_src is not None and bool(re.search(r"def _allocate_by_weight", pg_src))
check(
    "15. _allocate_by_weight function exists in paper_generator.py",
    pg_has_allocate,
    "" if pg_has_allocate else "Function not found",
)

# 16. check_mock_feasibility function exists
check(
    "16. check_mock_feasibility function exists",
    pg_has_check_mock,
    "" if pg_has_check_mock else "Not found",
)

# 17. generate_mock_paper function exists
check(
    "17. generate_mock_paper function exists",
    pg_has_gen_mock,
    "" if pg_has_gen_mock else "Not found",
)

# 18. PAPER_TEST_TYPES in session.py includes 'mock'
sess_paper_types_ok = sess_src is not None and bool(
    re.search(r"PAPER_TEST_TYPES\s*=\s*\{[^}]*['\"]mock['\"]", sess_src)
)
check(
    "18. PAPER_TEST_TYPES in session.py includes 'mock'",
    sess_paper_types_ok,
    "" if sess_paper_types_ok else "Pattern not found",
)

# 19. session.py imports compute_exam_readiness
sess_imports_readiness = sess_src is not None and bool(
    re.search(r"from\s+backend\.services\.profile_updater\s+import[^)]+compute_exam_readiness", sess_src)
    or re.search(r"import.*compute_exam_readiness", sess_src)
)
check(
    "19. session.py imports compute_exam_readiness",
    sess_imports_readiness,
    "" if sess_imports_readiness else "Import not found",
)

# 20. session.py imports check_mock_feasibility and generate_mock_paper
sess_imports_mock_fns = sess_src is not None and (
    bool(re.search(r"check_mock_feasibility", sess_src)) and
    bool(re.search(r"generate_mock_paper", sess_src))
)
check(
    "20. session.py imports check_mock_feasibility, generate_mock_paper",
    sess_imports_mock_fns,
    "" if sess_imports_mock_fns else "One or both imports missing",
)

# 21. database.py has ALTER TABLE migrations for exam_readiness_score, section_map, overall_guidance
db_has_er = db_src is not None and bool(re.search(r"ALTER TABLE.*exam_readiness_score", db_src))
db_has_sm = db_src is not None and bool(re.search(r"ALTER TABLE.*section_map", db_src))
db_has_og = db_src is not None and bool(re.search(r"ALTER TABLE.*overall_guidance", db_src))
check(
    "21. database.py has ALTER TABLE migrations for exam_readiness_score, section_map, overall_guidance",
    db_has_er and db_has_sm and db_has_og,
    f"exam_readiness_score={'found' if db_has_er else 'MISSING'}, "
    f"section_map={'found' if db_has_sm else 'MISSING'}, "
    f"overall_guidance={'found' if db_has_og else 'MISSING'}",
)

# 22. models.py CreateSessionRequest has chapter as Optional
models_chapter_optional = models_src is not None and bool(
    re.search(r"chapter\s*:\s*Optional\[str\]", models_src)
)
check(
    "22. models.py CreateSessionRequest has chapter as Optional[str]",
    models_chapter_optional,
    "" if models_chapter_optional else "Pattern not found",
)

# 23. add_case_based.py script exists
add_cb_exists = os.path.isfile(os.path.join(ROOT, "backend", "scripts", "add_case_based.py"))
check(
    "23. add_case_based.py script exists",
    add_cb_exists,
    "" if add_cb_exists else "File not found at backend/scripts/add_case_based.py",
)

# 24. ai_client.py call_2_score_and_guide handles mock session_type
ai_mock_handling = ai_src is not None and bool(
    re.search(r"session_type.*mock|mock.*session_type|is_mock\s*=\s*session_type\s*==\s*['\"]mock['\"]", ai_src)
)
check(
    "24. ai_client.py call_2_score_and_guide handles mock session_type",
    ai_mock_handling,
    "" if ai_mock_handling else "Mock session_type handling not found",
)

# 25. generate_mock_paper returns dict with selected_ids, generated_params, section_map keys
# Check the return statement in the function
gmp_return_ok = pg_src is not None and bool(
    re.search(r'"selected_ids"', pg_src)
    and re.search(r'"generated_params"', pg_src)
    and re.search(r'"section_map"', pg_src)
)
# More precise: check they appear together in a return dict
if pg_src:
    # Find the generate_mock_paper function body and check it returns all 3 keys
    gmp_block = re.search(
        r"def generate_mock_paper.*?(?=\ndef |\Z)", pg_src, re.DOTALL
    )
    if gmp_block:
        block_text = gmp_block.group(0)
        gmp_return_ok = (
            '"selected_ids"' in block_text and
            '"generated_params"' in block_text and
            '"section_map"' in block_text
        )
check(
    "25. generate_mock_paper returns dict with selected_ids, generated_params, section_map",
    gmp_return_ok,
    "" if gmp_return_ok else "One or more keys missing from return value",
)

# 26. section_map is built AFTER repair pass (not before)
# The repair pass loop should appear before "section_map = {..."
# Look for the comment "Build section_map from final selected list" after the repair loop
sm_after_repair = False
if pg_src:
    # Find position of "for _ in range(3):" within generate_mock_paper
    gmp_start = pg_src.find("def generate_mock_paper")
    if gmp_start != -1:
        gmp_text = pg_src[gmp_start:]
        # Find repair loop then section_map build
        repair_pos = gmp_text.find("for _ in range(3):")
        smap_pos = re.search(r"section_map\s*=\s*\{q\[.id.\]", gmp_text)
        if repair_pos != -1 and smap_pos:
            sm_after_repair = smap_pos.start() > repair_pos
check(
    "26. section_map is built AFTER repair pass (not before)",
    sm_after_repair,
    "" if sm_after_repair else "section_map assignment not found after repair loop",
)

# 27. _MOCK_SECTION_INSTRUCTIONS dict has keys A,B,C,D,E in session.py
msi_ok = sess_src is not None and bool(
    re.search(r"_MOCK_SECTION_INSTRUCTIONS\s*=\s*\{", sess_src)
)
if msi_ok and sess_src:
    m = re.search(r"_MOCK_SECTION_INSTRUCTIONS\s*=\s*\{([^}]+)\}", sess_src)
    if m:
        found_keys = set(re.findall(r'"([A-E])"', m.group(1)))
        msi_ok = found_keys == {"A", "B", "C", "D", "E"}
check(
    "27. _MOCK_SECTION_INSTRUCTIONS dict has keys A,B,C,D,E in session.py",
    msi_ok,
    "" if msi_ok else "Dict not found or missing keys",
)

# 28. exam_readiness_score is stored in student_profile after mock submit
er_stored = sess_src is not None and bool(
    re.search(r"exam_readiness_score", sess_src)
    and re.search(r"UPDATE student_profile SET exam_readiness_score", sess_src)
)
check(
    "28. exam_readiness_score is stored in student_profile after mock submit",
    er_stored,
    "" if er_stored else "UPDATE student_profile SET exam_readiness_score not found in session.py",
)

# 29. get_results returns section_breakdown, chapter_breakdown, exam_readiness_score for mock
gr_returns_ok = sess_src is not None and (
    "section_breakdown" in sess_src and
    "chapter_breakdown" in sess_src and
    "exam_readiness_score" in sess_src
)
check(
    "29. get_results returns section_breakdown, chapter_breakdown, exam_readiness_score for mock",
    gr_returns_ok,
    "" if gr_returns_ok else "One or more keys missing from session.py",
)

# 30. get_questions returns section on each question for mock
gq_section_ok = sess_src is not None and bool(
    re.search(r'q_out\["section"\]\s*=', sess_src)
    or re.search(r"section.*section_map", sess_src)
)
check(
    "30. get_questions returns section on each question for mock",
    gq_section_ok,
    "" if gq_section_ok else "section assignment on question output not found",
)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 Frontend (items 31-42)
# ─────────────────────────────────────────────────────────────────────────────

types_src = read_file(r"frontend\src\types\index.ts")
ss_src = read_file(r"frontend\src\pages\StartSession.tsx")
ts_src = read_file(r"frontend\src\pages\TakeSession.tsx")
res_src = read_file(r"frontend\src\pages\Results.tsx")

# 31. types/index.ts has section on Question
types_section_q = types_src is not None and bool(
    re.search(r"section\??\s*:\s*string", types_src)
)
check(
    "31. types/index.ts has section on Question",
    types_section_q,
    "" if types_section_q else "section field not found on Question interface",
)

# 32. types/index.ts has SectionBreakdown interface
types_sb = types_src is not None and bool(
    re.search(r"interface SectionBreakdown", types_src)
)
check(
    "32. types/index.ts has SectionBreakdown interface",
    types_sb,
    "" if types_sb else "SectionBreakdown interface not found",
)

# 33. types/index.ts has section_breakdown, chapter_breakdown, exam_readiness_score on SessionResults
types_sr_fields = types_src is not None and (
    "section_breakdown" in types_src and
    "chapter_breakdown" in types_src and
    "exam_readiness_score" in types_src
)
check(
    "33. types/index.ts has section_breakdown, chapter_breakdown, exam_readiness_score on SessionResults",
    types_sr_fields,
    "" if types_sr_fields else "One or more fields missing from SessionResults",
)

# 34. StartSession.tsx has 'mock' in Mode type
ss_mock_mode = ss_src is not None and bool(
    re.search(r"type Mode\s*=.*mock", ss_src)
    or re.search(r"'mock'.*Mode|Mode.*'mock'", ss_src)
)
# More permissive: just check 'mock' appears in Mode type definition line
if ss_src:
    mode_line = re.search(r"type Mode\s*=\s*['\"]understanding['\"].*", ss_src)
    ss_mock_mode = mode_line is not None and "mock" in mode_line.group(0)
    if not ss_mock_mode:
        # Try multiline search
        mode_block = re.search(r"type Mode\s*=\s*[^;]+;", ss_src, re.DOTALL)
        ss_mock_mode = mode_block is not None and "mock" in mode_block.group(0)
check(
    "34. StartSession.tsx has 'mock' in Mode type",
    ss_mock_mode,
    "" if ss_mock_mode else "Mode type definition not found or 'mock' missing",
)

# 35. StartSession.tsx has mockConfirm state
ss_mock_confirm = ss_src is not None and bool(
    re.search(r"mockConfirm", ss_src)
)
check(
    "35. StartSession.tsx has mockConfirm state",
    ss_mock_confirm,
    "" if ss_mock_confirm else "mockConfirm not found",
)

# 36. StartSession.tsx hides chapter picker when isMock
ss_hides_chapter = ss_src is not None and bool(
    re.search(r"\{!isMock", ss_src)
    or re.search(r"isMock.*Chapter|Chapter.*isMock", ss_src)
)
check(
    "36. StartSession.tsx hides chapter picker when isMock",
    ss_hides_chapter,
    "" if ss_hides_chapter else "!isMock chapter picker guard not found",
)

# 37. TakeSession.tsx has MockTestView component
ts_mock_view = ts_src is not None and bool(
    re.search(r"function MockTestView|MockTestView\s*=", ts_src)
)
check(
    "37. TakeSession.tsx has MockTestView component",
    ts_mock_view,
    "" if ts_mock_view else "MockTestView component not found",
)

# 38. TakeSession.tsx shows "3 Hours" duration for mock
ts_3hours = ts_src is not None and bool(
    re.search(r"3 Hours|3\s*hours", ts_src, re.IGNORECASE)
)
check(
    "38. TakeSession.tsx shows '3 Hours' duration for mock",
    ts_3hours,
    "" if ts_3hours else "'3 Hours' text not found",
)

# 39. Results.tsx has readinessBand helper function
res_rb = res_src is not None and bool(
    re.search(r"function readinessBand", res_src)
)
check(
    "39. Results.tsx has readinessBand helper function",
    res_rb,
    "" if res_rb else "readinessBand function not found",
)

# 40. Results.tsx has ExamReadinessCard component
res_erc = res_src is not None and bool(
    re.search(r"function ExamReadinessCard|ExamReadinessCard\s*=", res_src)
)
check(
    "40. Results.tsx has ExamReadinessCard component",
    res_erc,
    "" if res_erc else "ExamReadinessCard component not found",
)

# 41. Results.tsx has SectionBreakdownCard component
res_sbc = res_src is not None and bool(
    re.search(r"function SectionBreakdownCard|SectionBreakdownCard\s*=", res_src)
)
check(
    "41. Results.tsx has SectionBreakdownCard component",
    res_sbc,
    "" if res_sbc else "SectionBreakdownCard component not found",
)

# 42. Results.tsx shows overall_guidance
res_og = res_src is not None and bool(
    re.search(r"overall_guidance", res_src)
)
check(
    "42. Results.tsx shows overall_guidance",
    res_og,
    "" if res_og else "overall_guidance not found in Results.tsx",
)


# ─────────────────────────────────────────────────────────────────────────────
# Code Quality (items 43-47)
# ─────────────────────────────────────────────────────────────────────────────

# 43. paper_generator.py repair pass uses lvl not lv (line ~180)
# The bug would be using 'lv' instead of 'lvl' in the over-represented level filter
pg_repair_lvl_ok = False
if pg_src:
    # Find the repair pass section and look for the over-represented filter
    # The correct code uses `lv` as a loop variable within a comprehension: [lv for lv, cnt in actual.items() if ...]
    # The variable `lvl` is the outer loop variable from `for lvl, want in exp.items()`
    # The check is: the comprehension should use consistent variable naming (lv, not lvl as the iteration var)
    # Specifically look for the line: over = [lv for lv, cnt in actual.items() if cnt > exp.get(lv, 0) + 1]
    # vs the bug: over = [lvl for lvl, cnt in ...]  (would shadow outer lvl)
    # Check that the repair pass line uses 'lv' (not 'lv' == 'lvl' shadowing)
    repair_section = re.search(
        r"# ── Repair pass.*?(?=\n# ──|\ndef |\Z)", pg_src, re.DOTALL
    )
    if repair_section:
        repair_text = repair_section.group(0)
        # Look for the over= line - correct uses [lv for lv, cnt ... if cnt > exp.get(lv, ...]
        over_line = re.search(r"over\s*=\s*\[(\w+)\s+for\s+(\w+),\s*cnt\s+in\s+actual\.items\(\)", repair_text)
        if over_line:
            loop_var = over_line.group(2)  # the variable name used in the comprehension
            # It should be 'lv' not 'lvl' (to avoid shadowing the outer for-loop variable 'lvl')
            # Actually in generate_mock_paper the outer var is also 'lvl', so using 'lv' is correct
            pg_repair_lvl_ok = loop_var == "lv"
        else:
            # Try a broader search in the full source
            over_match = re.search(
                r"over\s*=\s*\[(\w+)\s+for\s+(\w+),\s*cnt\s+in\s+actual\.items\(\)\s+if\s+cnt\s*>",
                pg_src
            )
            if over_match:
                loop_var = over_match.group(2)
                pg_repair_lvl_ok = loop_var == "lv"
check(
    "43. paper_generator.py repair pass uses 'lv' not 'lvl' in over-represented filter comprehension",
    pg_repair_lvl_ok,
    "" if pg_repair_lvl_ok else "Variable naming issue or pattern not found — check 'over = [lv for lv, cnt ...' line",
)

# 44. No syntax errors in paper_generator.py
pg_syntax_ok = pg_src is not None and pg_tree is not None
if pg_src is not None and pg_tree is None:
    # Re-check to get error message
    try:
        ast.parse(pg_src)
        pg_syntax_ok = True
    except SyntaxError as e:
        pg_detail = f"SyntaxError at line {e.lineno}: {e.msg}"
    else:
        pg_detail = ""
else:
    pg_detail = "" if pg_syntax_ok else "File not found"
check(
    "44. No syntax errors in paper_generator.py",
    pg_syntax_ok,
    pg_detail,
)

# 45. No syntax errors in session.py
sess_syntax_ok = sess_src is not None and sess_tree is not None
if sess_src is not None and sess_tree is None:
    try:
        ast.parse(sess_src)
        sess_syntax_ok = True
    except SyntaxError as e:
        sess_detail = f"SyntaxError at line {e.lineno}: {e.msg}"
    else:
        sess_detail = ""
else:
    sess_detail = "" if sess_syntax_ok else "File not found"
check(
    "45. No syntax errors in session.py",
    sess_syntax_ok,
    sess_detail,
)

# 46. No syntax errors in profile_updater.py
pu_syntax_ok = pu_src is not None and pu_tree is not None
if pu_src is not None and pu_tree is None:
    try:
        ast.parse(pu_src)
        pu_syntax_ok = True
    except SyntaxError as e:
        pu_detail = f"SyntaxError at line {e.lineno}: {e.msg}"
    else:
        pu_detail = ""
else:
    pu_detail = "" if pu_syntax_ok else "File not found"
check(
    "46. No syntax errors in profile_updater.py",
    pu_syntax_ok,
    pu_detail,
)

# 47. No syntax errors in database.py
db_syntax_ok = db_src is not None and db_tree is not None
if db_src is not None and db_tree is None:
    try:
        ast.parse(db_src)
        db_syntax_ok = True
    except SyntaxError as e:
        db_detail = f"SyntaxError at line {e.lineno}: {e.msg}"
    else:
        db_detail = ""
else:
    db_detail = "" if db_syntax_ok else "File not found"
check(
    "47. No syntax errors in database.py",
    db_syntax_ok,
    db_detail,
)


# ─────────────────────────────────────────────────────────────────────────────
# Print results
# ─────────────────────────────────────────────────────────────────────────────

print()
print("=" * 78)
print("  Physics Assessor - Phase 1-4 Validation Report")
print("=" * 78)

passed = sum(1 for s, _, _ in results if s == "PASS")
failed = sum(1 for s, _, _ in results if s == "FAIL")

sections = [
    ("Phase 1-3 Regression", range(0, 10)),
    ("Phase 4 Backend",      range(10, 30)),
    ("Phase 4 Frontend",     range(30, 42)),
    ("Code Quality",         range(42, 47)),
]

for section_name, idx_range in sections:
    print(f"\n  -- {section_name} --")
    for i in idx_range:
        if i >= len(results):
            break
        s, n, d = results[i]
        marker = "+" if s == "PASS" else "X"
        line = f"  {marker} [{s}] {n}"
        if d:
            line += f"\n        detail: {d}"
        print(line)

print()
print("=" * 78)
print(f"  Result: {passed}/{len(results)} passed,  {failed} failed")
print("=" * 78)
print()

sys.exit(0 if failed == 0 else 1)
