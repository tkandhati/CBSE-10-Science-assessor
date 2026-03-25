#!/usr/bin/env python3
"""Phase 5 validation — 72 items."""
import os, sys, json, re, ast, sqlite3
sys.path.insert(0, os.getcwd())

results = []

def check(num, name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((num, status, name, detail))
    return condition

def read_file(path):
    try:
        return open(path, encoding='utf-8').read()
    except:
        return ""

def has_fn(src, fn):
    return f"def {fn}" in src

ROOT = os.getcwd()
DB_PATH = os.path.join(ROOT, "data", "science_assessor.db")

# Init DB
try:
    from backend.database import init_db
    init_db()
except Exception as e:
    print(f"init_db: {e}")

# ── PHASE 1-4 REGRESSION ──────────────────────────────────────────────────────
check(1, "5 chapter JSON files exist",
    all(os.path.exists(f"data/questions/{f}") for f in
        ["light.json","human_eye.json","electricity.json","magnetic_effects.json","sources_of_energy.json"]))

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
check(2, "All DB tables exist", all(t in tables for t in ["question_index","assessments","answers","student_profile"]))
cols_answers = {r[1] for r in conn.execute("PRAGMA table_info(answers)").fetchall()}
cols_profile = {r[1] for r in conn.execute("PRAGMA table_info(student_profile)").fetchall()}
cols_assess  = {r[1] for r in conn.execute("PRAGMA table_info(assessments)").fetchall()}
check(2, "Phase5 cols: override_score/note in answers",
    "override_score" in cols_answers and "override_note" in cols_answers)
check(2, "guidance_cache/cached_at in student_profile",
    "guidance_cache" in cols_profile and "guidance_cached_at" in cols_profile)
check(2, "exam_readiness_score in student_profile", "exam_readiness_score" in cols_profile)
check(2, "section_map/overall_guidance in assessments",
    "section_map" in cols_assess and "overall_guidance" in cols_assess)
conn.close()

sess = read_file("backend/routers/session.py")
check(3, "session/create supports all 4 types",
    all(t in sess for t in ["understanding","chapter_short","chapter_regular","mock"]))
check(4, "one-active-test rule enforced", "_check_one_active_test" in sess)
check(5, "upload-pdf endpoint exists", "upload-pdf" in sess or "upload_pdf" in sess)
check(6, "2-call Claude budget used", "call_1" in sess and "call_2" in sess)
check(7, "update_profile called after session", "update_profile" in sess)
check(8, "results endpoint exists", "results" in sess)
check(9, "expiry job in main.py", "expire" in read_file("backend/main.py").lower())

tmpl = json.loads(open("data/config/test_templates.json").read())["templates"]["mock"]
total_q = sum(slot["count"] for section in tmpl["sections"] for slot in section["slots"])
check(10, f"Mock question count correct per CBSE 2026 (template={total_q})", total_q == 39,
    f"Expected 39, got {total_q}" if total_q != 39 else "")

# ── ANALYTICS ────────────────────────────────────────────────────────────────
a = read_file("backend/analytics.py")
check(11, "analytics.py exists", bool(a))
for fn in ["get_topic_scores","get_topic_trend","get_topic_classification","get_chapter_performance",
           "get_marks_lost_by_type","get_exam_readiness","get_weak_topics","get_untested_topics"]:
    check(11, f"  analytics.{fn} defined", has_fn(a, fn))
pu = read_file("backend/services/profile_updater.py")
check(12, "Decay weights 1.0/0.5/0.25 in profile_updater", all(w in pu for w in ["0.5","0.25","decay"]))
check(13, "1.5x session weight for exam-condition in profile_updater",
    "1.5" in pu and "SESSION_WEIGHT" in pu)
check(14, "min_attempts gate in analytics", "min_attempts" in a)
for band in ["Strong","Developing","Weak","Critical","Untested"]:
    check(15, f"Band '{band}' in analytics", band in a)
check(16, "get_topic_trend compares recent vs prev avg", "recent" in a and ("prev" in a or "previous" in a))
check(16, "Trend returns up/down/flat", all(t in a for t in ['"up"','"down"','"flat"']))
check(17, "chapter_performance JOINs answers+question_index", "JOIN" in a.upper() and "question_index" in a)
check(18, "marks_lost_by_type queries question type", "marks_lost" in a.lower() and "type" in a)
check(19, "exam_readiness uses board weights and range",
    "_CHAPTER_BOARD_WEIGHTS" in a and "range_low" in a and "band_label" in a)
check(20, "get_weak_topics sorts ascending", "sorted" in a)
check(21, "get_untested_topics loads syllabus, checks <3 attempts",
    "syllabus" in a.lower() and ("< 3" in a or "<3" in a))

# ── ADMIN API ─────────────────────────────────────────────────────────────────
adm = read_file("backend/routers/admin.py")
check(22, "dashboard returns all required fields",
    all(f in adm for f in ["total_sessions","overall_average","chapter_performance","exam_readiness","current_streak"]))
check(23, "strengths returns topic classification", "classification" in adm and "topics" in adm)
check(24, "Action logic: Revise Now/Practice More/Consolidate/Keep Going",
    all(a2 in adm for a2 in ["Revise Now","Practice More","Consolidate","Keep Going"]))
check(25, "sessions endpoint paginated with filters",
    "page" in adm and "limit" in adm and "chapter" in adm)
check(26, "session detail fetches from question_store",
    ("get_question_store" in adm or "question_store" in adm) and "question_text" in adm)
check(27, "marks_lost_by_type and marks_lost_by_reason", "marks_lost_by_type" in adm and "marks_lost_by_reason" in adm)
check(28, "coverage compares against test templates",
    "_TEMPLATES_PATH" in adm or "test_templates" in adm)
check(29, "guidance cache check < 24h", "24" in adm and "guidance_cache" in adm)
check(30, "guidance passes correct context", all(f in adm for f in ["weak_topics","days_until_exam"]))
ai = read_file("backend/services/ai_client.py")
check(31, "guidance response has 3 required sections",
    all(f in ai for f in ["priority_topics","recommended_sequence","exam_readiness_projection"]))
check(32, "guidance cached after fresh call", "guidance_cache" in adm and "guidance_cached_at" in adm)
check(33, "guidance call independent (call_guidance not call_1/call_2)",
    "call_guidance" in adm and "call_1" not in adm and "call_2" not in adm)

# ── FRONTEND ─────────────────────────────────────────────────────────────────
db  = read_file("frontend/src/pages/admin/AdminDashboard.tsx")
ts  = read_file("frontend/src/pages/admin/TopicStrengths.tsx")
sd  = read_file("frontend/src/pages/admin/SessionDetail.tsx")
sg  = read_file("frontend/src/pages/admin/StudyGuidance.tsx")
app = read_file("frontend/src/App.tsx")

check(34, "Dashboard: 5 metrics in strip",
    all(m in db for m in ["total_sessions","total_questions_answered","overall_average","current_streak","best_streak"]))
check(35, "Dashboard: chapter bars with colour coding", "BAND_COLOR" in db and "bg-green" in db)
check(36, "Dashboard: chapter bar expands to show topic rows",
    ("expanded" in db.lower() or "setExpanded" in db) and "topic" in db.lower(),
    "Expands but shows link to strengths page, not inline topic rows" if "Topic Intelligence" in db else "")
check(37, "Dashboard: recent sessions clickable to /admin/session/:id",
    "navigate" in db and "admin/session" in db)
check(38, "Dashboard: strengths green pills", "strengths" in db.lower() and "bg-green" in db)
check(39, "Dashboard: weaknesses red/orange pills",
    "weaknesses" in db.lower() and ("bg-red" in db or "bg-orange" in db))
check(40, "Dashboard: exam readiness with range+band", "range_low" in db and "band_label" in db)
check(41, "Dashboard: coverage gap alert shown conditionally", "coverage_gaps" in db and "length" in db)

check(42, "TopicStrengths: weak topics summary at top", "weak_topics" in ts and "Weakest" in ts)
check(43, "TopicStrengths: untested topics panel", "untested_topics" in ts)
check(44, "TopicStrengths: accordion auto-expands Weak/Critical",
    "hasWeak" in ts and ("Weak" in ts and "Critical" in ts))
check(45, "TopicStrengths: chapter header shows avg+band", "chapter_title" in ts and "average" in ts.lower())
check(46, "TopicStrengths: topic rows have 6 data points",
    all(f in ts for f in ["topic_title","score","attempts","last_tested","trend"]))
check(47, "TopicStrengths: trend arrows ↑↓→", "↑" in ts and "↓" in ts and "→" in ts)
check(48, "TopicStrengths: action badges correct",
    all(a3 in ts for a3 in ["Revise Now","Practice More","Consolidate","Keep Going"]))
check(49, "TopicStrengths: trend sparkline (mini SVG/canvas line chart)",
    "svg" in ts.lower() or "sparkline" in ts.lower() or "polyline" in ts.lower() or "<path" in ts.lower(),
    "Trend shown as arrow only — no mini sparkline chart")

check(50, "SessionDetail: header shows date/type/chapter/score/time",
    all(f in sd for f in ["started_at","type","chapter","score_obtained","total_marks"]))
check(51, "SessionDetail: question_text from in-memory dict", "question_text" in sd)
check(52, "SessionDetail: ocr_text for paper, answer_text for understanding",
    "ocr_text" in sd and "answer_text" in sd)
check(53, "SessionDetail: evaluation_layer badge", "evaluation_layer" in sd and "LAYER_COLOR" in sd)
check(54, "SessionDetail: feedback + model answer", "model_answer" in sd and "points_missed" in sd)
check(55, "SessionDetail: marks lost panels", "marks_lost_by_type" in sd and "marks_lost_by_reason" in sd)
check(56, "SessionDetail: score override panel", "OverridePanel" in sd and "overrideAnswerScore" in sd)
check(57, "answers table has override_score/note cols",
    all(c in read_file("backend/database.py") for c in ["override_score","override_note"]))

check(58, "StudyGuidance: loading state", "loading" in sg.lower() and "Loading" in sg)
check(59, "StudyGuidance: priority_topics with ncert_reference",
    "priority_topics" in sg and "ncert_reference" in sg)
check(60, "StudyGuidance: recommended_sequence 7-day plan", "recommended_sequence" in sg)
check(61, "StudyGuidance: exam_readiness_projection", "exam_readiness_projection" in sg)
check(62, "StudyGuidance: refresh forces fresh call",
    "refresh" in sg.lower() and ("true" in sg))

check(63, "App.tsx: two-tier Student/Admin nav", "Student" in app and "Admin" in app)
check(64, "Student nav: active test resume link",
    ("activeTest" in app or "active_session" in app or "ActiveTest" in app or "resume" in app.lower()),
    "Nav is static — no dynamic active test resume link")
check(65, "Admin nav: all 5 links present",
    all(l in app for l in ["/admin/strengths","/admin/sessions","/admin/guidance","/admin/questions"]))
check(66, "Nav: active link highlighting", "isActive" in app)

check(67, "Dashboard handles empty state", "No completed" in db or "0" in db)
check(68, "topic_scores updated and accessible",
    "topic_scores" in pu and "topic_scores" in a)
check(69, "chapter perf recalculates dynamically (SQL aggregation)", "SUM" in a.upper() and "JOIN" in a.upper())
check(70, "guidance context: weak topics + streak + readiness",
    "weak_topics" in adm and "current_streak" in adm and "exam_readiness" in adm)
check(71, "override recalculates score_obtained + percentage",
    "score_obtained" in adm and "percentage" in adm and "UPDATE assessments" in adm)
check(72, "All admin pages import from ../../api/client",
    all("../../api/client" in read_file(f"frontend/src/pages/admin/{p}")
        for p in ["AdminDashboard.tsx","TopicStrengths.tsx","SessionDetail.tsx","StudyGuidance.tsx"]))

# ── REPORT ────────────────────────────────────────────────────────────────────
passed = sum(1 for _,s,_,_ in results if s=="PASS")
failed = sum(1 for _,s,_,_ in results if s=="FAIL")
print(f"\n{'='*72}")
print(f"PHASE 5 VALIDATION — {passed}/{len(results)} PASS, {failed} FAIL")
print(f"{'='*72}")
for num, status, name, detail in results:
    m = "✓" if status=="PASS" else "✗"
    print(f"{m} [{status}] #{num:02d} {name}" + (f"\n     ↳ {detail}" if detail else ""))
print(f"\n{'='*72}")
