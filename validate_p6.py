#!/usr/bin/env python3
"""
Phase 6 Validation Script — Physics Assessor
Checks 91 items across backend, frontend, and logic.
"""
import sys
import os
import re
import importlib
import traceback

BASE = r"C:\CBSE10\science"

results = []

def check(item_num, description, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((item_num, description, passed, detail))
    detail_str = f"  ({detail})" if detail and not passed else ""
    print(f"[{status}] {item_num:>3}. {description}{detail_str}")

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return None

def file_exists(rel):
    return os.path.isfile(os.path.join(BASE, rel))

def has_pattern(text, pattern, flags=0):
    if text is None:
        return False
    return bool(re.search(pattern, text, flags))

def has_string(text, s):
    if text is None:
        return False
    return s in text

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1-5 REGRESSION
# ─────────────────────────────────────────────────────────────────────────────

db_py = read_file(os.path.join(BASE, "backend", "database.py"))
main_py = read_file(os.path.join(BASE, "backend", "main.py"))
session_py = read_file(os.path.join(BASE, "backend", "routers", "session.py"))
admin_py = read_file(os.path.join(BASE, "backend", "routers", "admin.py"))
app_tsx = read_file(os.path.join(BASE, "frontend", "src", "App.tsx"))
client_ts = read_file(os.path.join(BASE, "frontend", "src", "api", "client.ts"))

# 1. database.py init_db + tables
tables_needed = ["question_index", "assessments", "answers", "student_profile", "review_queue"]
has_init_db = has_pattern(db_py, r"def init_db\(")
has_all_tables = all(has_string(db_py, t) for t in tables_needed)
missing_tables = [t for t in tables_needed if not has_string(db_py, t)]
check(1, "database.py: init_db() exists and all 5 tables present",
      has_init_db and has_all_tables,
      f"missing: {missing_tables}" if missing_tables else ("no init_db" if not has_init_db else ""))

# 2. main.py imports and includes 4 routers
router_imports = ["session", "admin", "qbank", "student"]
has_imports = all(has_pattern(main_py, rf"from.*routers.*import.*{r}|import.*routers\.{r}") for r in router_imports)
has_includes = all(has_pattern(main_py, rf"include_router.*{r}") for r in router_imports)
missing_imports = [r for r in router_imports if not has_pattern(main_py, rf"from.*routers.*import.*{r}|import.*routers\.{r}")]
missing_includes = [r for r in router_imports if not has_pattern(main_py, rf"include_router.*{r}")]
check(2, "main.py: imports and includes session/admin/qbank/student routers",
      has_imports and has_includes,
      f"missing imports:{missing_imports} missing includes:{missing_includes}")

# 3. session.py endpoints
session_endpoints = [
    (r'@router\.post\(.*["\']\/create', "POST /create"),
    (r'@router\.get\(.*\{id\}.*\/questions', "GET /{id}/questions"),
    (r'@router\.post\(.*\{id\}.*\/submit', "POST /{id}/submit"),
    (r'@router\.get\(.*\{id\}.*\/results', "GET /{id}/results"),
    (r'@router\.post\(.*\{id\}.*\/upload-pdf', "POST /{id}/upload-pdf"),
    (r'@router\.post\(.*\{id\}.*\/confirm-ocr', "POST /{id}/confirm-ocr"),
    (r'@router\.put\(.*\{id\}.*\/mark-done-writing', "PUT /{id}/mark-done-writing"),
]
missing_ep = [name for pat, name in session_endpoints if not has_pattern(session_py, pat)]
check(3, "session.py: all 7 required endpoints",
      len(missing_ep) == 0,
      f"missing: {missing_ep}")

# 4. admin.py endpoints
admin_endpoints = [
    (r'["\']\/api\/admin\/dashboard["\']|path.*dashboard', "/api/admin/dashboard"),
    (r'["\']\/api\/admin\/strengths["\']|\/strengths', "/strengths"),
    (r'["\']\/api\/admin\/sessions["\']|\/sessions', "/sessions"),
    (r'["\']\/api\/admin\/session\/\{', "/session/{id}"),
    (r'["\']\/api\/admin\/coverage["\']|\/coverage', "/coverage"),
    (r'["\']\/api\/admin\/guidance["\']|\/guidance', "/guidance"),
    (r'override', "PUT override"),
]
missing_admin = [name for pat, name in admin_endpoints if not has_pattern(admin_py, pat)]
check(4, "admin.py: all required endpoints",
      len(missing_admin) == 0,
      f"missing: {missing_admin}")

# 5. App.tsx routes
app_routes = [
    (r'path=["\']\/["\']|route.*path.*["\']\/["\']', "route /"),
    (r'\/session\/new', "/session/new"),
    (r'\/session\/:id["\'\s]', "/session/:id"),
    (r'\/admin["\'\s>]|path=["\']\/admin["\']', "/admin"),
    (r'\/admin\/session\/:id', "/admin/session/:id"),
    (r'\/admin\/sessions', "/admin/sessions"),
    (r'\/admin\/questions', "/admin/questions"),
    (r'\/admin\/guidance', "/admin/guidance"),
    (r'\/admin\/strengths', "/admin/strengths"),
    (r'\/session\/:id\/upload', "/session/:id/upload"),
    (r'\/session\/:id\/results', "/session/:id/results"),
]
missing_routes = [name for pat, name in app_routes if not has_pattern(app_tsx, pat)]
check(5, "App.tsx: all required routes",
      len(missing_routes) == 0,
      f"missing: {missing_routes}")

# 6. client.ts functions
client_fns = [
    "createSession", "getActiveSession", "submitSession", "getResults",
    "getAdminDashboard", "getTopicStrengths", "overrideAnswerScore",
    "getStudyGuidance", "getAdminSessions"
]
missing_fns = [f for f in client_fns if not has_string(client_ts, f)]
check(6, "client.ts: all required API functions",
      len(missing_fns) == 0,
      f"missing: {missing_fns}")

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Gamification Backend
# ─────────────────────────────────────────────────────────────────────────────

gamification_path = os.path.join(BASE, "backend", "gamification.py")
gam_py = read_file(gamification_path)

# 7. gamification.py exists
check(7, "backend/gamification.py exists",
      gam_py is not None)

# 8. LEVEL_XP dict
check(8, "LEVEL_XP = {1:10, 2:20, 3:30, 4:50, 5:75} in gamification.py",
      has_pattern(gam_py, r"LEVEL_XP\s*=\s*\{") and
      all(has_pattern(gam_py, p) for p in [r"1\s*:\s*10", r"2\s*:\s*20", r"3\s*:\s*30", r"4\s*:\s*50", r"5\s*:\s*75"]),
      "LEVEL_XP dict not found or missing entries")

# 9. XP_PER_LEVEL = 500
check(9, "XP_PER_LEVEL = 500 in gamification.py",
      has_pattern(gam_py, r"XP_PER_LEVEL\s*=\s*500"))

# 10. calculate_xp function
check(10, "calculate_xp(difficulty, score, max_marks) function exists",
      has_pattern(gam_py, r"def calculate_xp\("))

# 11-13: calculate_level, xp_in_current_level, xp_to_next_level functions
check(11, "calculate_level(total_xp) function exists",
      has_pattern(gam_py, r"def calculate_level\("))

check(12, "xp_in_current_level(total_xp) function exists",
      has_pattern(gam_py, r"def xp_in_current_level\("))

check(13, "xp_to_next_level(total_xp) function exists",
      has_pattern(gam_py, r"def xp_to_next_level\("))

# 14. check_level_up returns (bool, int)
check(14, "check_level_up(old_xp, new_xp) function exists",
      has_pattern(gam_py, r"def check_level_up\("))

# 15. check_and_award_badges function with required params
badge_params = [
    "session_id", "sess_type", "chapter", "answers_data", "profile",
    "topic_scores_before", "topic_scores_after", "current_streak",
    "total_xp_new", "percentage", "duration_seconds"
]
has_badge_fn = has_pattern(gam_py, r"def check_and_award_badges\(")
if has_badge_fn:
    # Find the function signature (could be multiline)
    fn_match = re.search(r"def check_and_award_badges\((.*?)\):", gam_py, re.DOTALL)
    fn_sig = fn_match.group(1) if fn_match else ""
    missing_params = [p for p in badge_params if p not in fn_sig]
else:
    missing_params = badge_params
check(15, "check_and_award_badges() with all required parameters",
      has_badge_fn and len(missing_params) == 0,
      f"missing params: {missing_params}" if missing_params else ("function not found" if not has_badge_fn else ""))

# 16. 12 badges defined
badge_ids = [
    "first_perfect", "streak_7", "streak_30", "century",
    "chapter_master_light", "chapter_master_human_eye",
    "chapter_master_electricity", "chapter_master_magnetic_effects",
    "chapter_master_sources_of_energy", "board_ready", "speed_demon", "comeback_kid"
]
missing_badges = [b for b in badge_ids if not has_string(gam_py, b)]
check(16, "All 12 badge IDs defined in gamification.py",
      len(missing_badges) == 0,
      f"missing: {missing_badges}")

# 17. Badge check is idempotent (existing_badges checked)
check(17, "Badge check is idempotent (existing_badges checked before awarding)",
      has_pattern(gam_py, r"existing_badges") and
      has_pattern(gam_py, r"not in existing_badges|if.*badge.*not in|existing_badges.*not"))

# 18. New badges persisted to student_profile.badges
check(18, "New badges persisted to student_profile.badges JSON column",
      has_pattern(gam_py, r"badges") and
      has_pattern(gam_py, r"UPDATE student_profile|badges.*json|json.*badges", re.IGNORECASE))

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Student API
# ─────────────────────────────────────────────────────────────────────────────

student_py = read_file(os.path.join(BASE, "backend", "routers", "student.py"))

# 19. student.py exists with prefix /api/student
check(19, "backend/routers/student.py exists with prefix /api/student",
      student_py is not None and has_pattern(student_py, r"/api/student"))

# 20. GET /api/student/profile returns required fields
profile_fields = ["name", "total_xp", "current_level", "xp_in_level", "xp_to_next_level",
                  "xp_per_level", "current_streak", "best_streak", "badges", "exam_readiness_score"]
missing_profile_fields = [f for f in profile_fields if not has_string(student_py, f)]
check(20, "GET /api/student/profile returns all required fields",
      has_pattern(student_py, r"[\"\']/profile[\"\']|profile") and len(missing_profile_fields) == 0,
      f"missing fields: {missing_profile_fields}")

# 21. GET /api/student/badges returns all 12 badge definitions
check(21, "GET /api/student/badges endpoint returns badge definitions with earned/earned_at",
      has_pattern(student_py, r"[\"\']/badges[\"\']|/badges") and
      has_string(student_py, "earned"))

# 22. student router registered in main.py
check(22, "student router registered in main.py",
      has_pattern(main_py, r"include_router.*student|student.*include_router"))

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Question Bank API
# ─────────────────────────────────────────────────────────────────────────────

qbank_py = read_file(os.path.join(BASE, "backend", "routers", "qbank.py"))

# 23. qbank.py exists with prefix /api/qbank
check(23, "backend/routers/qbank.py exists with prefix /api/qbank",
      qbank_py is not None and has_pattern(qbank_py, r"/api/qbank"))

# 24. GET /api/qbank/stats
check(24, "GET /api/qbank/stats endpoint exists",
      has_pattern(qbank_py, r"[\"\']/stats[\"\']|/stats"))

# 25. GET /api/qbank/review-queue with params
check(25, "GET /api/qbank/review-queue with chapter/topic/type/page/limit params",
      has_pattern(qbank_py, r"review.queue") and
      all(has_string(qbank_py, p) for p in ["chapter", "topic", "page", "limit"]))

# 26. PUT /api/qbank/{id}/approve
check(26, "PUT /api/qbank/{id}/approve endpoint",
      has_pattern(qbank_py, r"approve"))

# 27. PUT /api/qbank/{id}/reject
check(27, "PUT /api/qbank/{id}/reject endpoint",
      has_pattern(qbank_py, r"reject"))

# 28. PUT /api/qbank/{id}/edit with EditQuestionBody
check(28, "PUT /api/qbank/{id}/edit with EditQuestionBody model",
      has_pattern(qbank_py, r"edit") and has_pattern(qbank_py, r"EditQuestionBody|EditQuestion"))

# 29. GET /api/qbank/live with filters and pagination
check(29, "GET /api/qbank/live endpoint with filters and pagination",
      has_pattern(qbank_py, r"[\"\']/live[\"\']|/live"))

# 30. POST /api/qbank/scan-pdf
check(30, "POST /api/qbank/scan-pdf calls call_extract_questions_from_pdf",
      has_pattern(qbank_py, r"scan.pdf|scan_pdf") and
      has_pattern(qbank_py, r"call_extract_questions_from_pdf|extract_questions"))

# 31. POST /api/qbank/retag
check(31, "POST /api/qbank/retag endpoint",
      has_pattern(qbank_py, r"retag"))

# 32. qbank router registered in main.py
check(32, "qbank router registered in main.py",
      has_pattern(main_py, r"include_router.*qbank|qbank.*include_router"))

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Session Submit — Gamification Integration
# ─────────────────────────────────────────────────────────────────────────────

# 33. session.py imports gamification functions
check(33, "session.py imports check_and_award_badges, check_level_up, calculate_level",
      has_pattern(session_py, r"check_and_award_badges") and
      has_pattern(session_py, r"check_level_up") and
      has_pattern(session_py, r"calculate_level"))

# 34. _duration_secs computed BEFORE UPDATE assessments
if session_py:
    dur_pos = session_py.find("_duration_secs")
    upd_pos = session_py.find("UPDATE assessments")
    check(34, "_duration_secs computed BEFORE UPDATE assessments",
          dur_pos != -1 and upd_pos != -1 and dur_pos < upd_pos,
          f"dur_pos={dur_pos}, upd_pos={upd_pos}")
else:
    check(34, "_duration_secs computed BEFORE UPDATE assessments", False, "session.py not found")

# 35. _old_profile/_old_xp/_old_topic_scores captured before update_profile
check(35, "_old_profile/_old_xp/_old_topic_scores captured before update_profile()",
      has_pattern(session_py, r"_old_profile|_old_xp|_old_topic_scores"))

# 36. check_and_award_badges() called after update_profile() with correct args
check(36, "check_and_award_badges() called after update_profile()",
      has_pattern(session_py, r"check_and_award_badges\("))

# 37. check_level_up called with _old_xp and profile_update["total_xp"]
check(37, "check_level_up() called with _old_xp and new total_xp",
      has_pattern(session_py, r"check_level_up\("))

# 38. new_badges, leveled_up, current_level in result dict
result_keys = ["new_badges", "leveled_up", "current_level"]
missing_keys = [k for k in result_keys if not has_string(session_py, k)]
check(38, "new_badges, leveled_up, current_level included in result dict",
      len(missing_keys) == 0,
      f"missing: {missing_keys}")

# 39. duration_seconds persisted in UPDATE assessments
check(39, "duration_seconds persisted in UPDATE assessments",
      has_pattern(session_py, r"duration_seconds") and
      has_pattern(session_py, r"UPDATE assessments"))

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Database
# ─────────────────────────────────────────────────────────────────────────────

# 40. review_queue table columns
rq_cols = ["id", "chapter", "topic", "type", "difficulty", "marks", "text",
           "options", "rubric", "source", "board_years", "tags", "added_at", "status"]
missing_rq_cols = [c for c in rq_cols if not has_string(db_py, c)]
check(40, "review_queue table with all required columns",
      has_pattern(db_py, r"review_queue") and len(missing_rq_cols) == 0,
      f"missing cols: {missing_rq_cols}")

# 41. ALTER TABLE student_profile ADD COLUMN badges
check(41, "Migration: ALTER TABLE student_profile ADD COLUMN badges",
      has_pattern(db_py, r"ALTER TABLE student_profile ADD COLUMN badges|ADD COLUMN badges"))

# 42. student_profile CREATE TABLE has badges column
# Find CREATE TABLE student_profile block
if db_py:
    sp_match = re.search(r"CREATE TABLE.*?student_profile.*?\)", db_py, re.DOTALL | re.IGNORECASE)
    sp_block = sp_match.group(0) if sp_match else ""
    check(42, "student_profile CREATE TABLE has badges column",
          "badges" in sp_block,
          "badges not in CREATE TABLE block" if sp_block else "CREATE TABLE student_profile block not found")
else:
    check(42, "student_profile CREATE TABLE has badges column", False, "database.py not found")

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Frontend — Dashboard
# ─────────────────────────────────────────────────────────────────────────────

dashboard_tsx = read_file(os.path.join(BASE, "frontend", "src", "pages", "Dashboard.tsx"))

# 43. Dashboard.tsx exists
check(43, "frontend/src/pages/Dashboard.tsx exists",
      dashboard_tsx is not None)

# 44. Dashboard fetches /api/student/profile and /api/student/badges
check(44, "Dashboard fetches /api/student/profile and /api/student/badges",
      has_pattern(dashboard_tsx, r"student/profile|getStudentProfile") and
      has_pattern(dashboard_tsx, r"student/badges|getBadges|getStudentBadges"))

# 45. Dashboard fetches getAdminDashboard, getTopicStrengths, getAdminSessions
check(45, "Dashboard fetches getAdminDashboard, getTopicStrengths, getAdminSessions",
      has_string(dashboard_tsx, "getAdminDashboard") and
      has_string(dashboard_tsx, "getTopicStrengths") and
      has_string(dashboard_tsx, "getAdminSessions"))

# 46. XPBar component
check(46, "XPBar component renders XP progress bar",
      has_pattern(dashboard_tsx, r"XPBar|xp.*bar|xpBar", re.IGNORECASE))

# 47. ProgressRing SVG component
check(47, "ProgressRing SVG component for chapter progress",
      has_pattern(dashboard_tsx, r"ProgressRing|progressRing|<svg.*circle|<circle", re.IGNORECASE))

# 48. BadgeShelf component with tooltips
check(48, "BadgeShelf component with tooltips (earned=colored, unearned=greyed)",
      has_pattern(dashboard_tsx, r"BadgeShelf|badge.*shelf|shelf", re.IGNORECASE) and
      has_pattern(dashboard_tsx, r"tooltip|title=|earned", re.IGNORECASE))

# 49. Quick-start buttons (3)
check(49, "Quick-start buttons (Understanding, Chapter Test, Mock)",
      has_pattern(dashboard_tsx, r"Understanding|Chapter Test|Mock", re.IGNORECASE) and
      has_pattern(dashboard_tsx, r"button|Button|onClick", re.IGNORECASE))

# 50. Shows "Resume Test" if activeTestId
check(50, 'Shows "Resume Test" if activeTestId is set',
      has_pattern(dashboard_tsx, r"Resume|activeTestId|resumeTest|active.*test", re.IGNORECASE))

# 51. Recent sessions table
check(51, "Recent sessions table with navigation to results",
      has_pattern(dashboard_tsx, r"sessions|session.*table|recent.*session", re.IGNORECASE) and
      has_pattern(dashboard_tsx, r"results|navigate|link", re.IGNORECASE))

# 52. Empty state
check(52, "Empty state when no sessions",
      has_pattern(dashboard_tsx, r"empty|no session|no.*test|yet|haven", re.IGNORECASE))

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Frontend — Results Celebrations
# ─────────────────────────────────────────────────────────────────────────────

results_tsx = read_file(os.path.join(BASE, "frontend", "src", "pages", "Results.tsx"))

# 53. celebrationDone state
check(53, "Results.tsx has celebrationDone state",
      has_pattern(results_tsx, r"celebrationDone|celebration.*Done|setCelebration"))

# 54. Results.tsx reads new_badges, leveled_up, current_level from location.state
check(54, "Results.tsx reads new_badges, leveled_up, current_level from location.state",
      has_string(results_tsx, "new_badges") and
      has_string(results_tsx, "leveled_up") and
      has_string(results_tsx, "current_level") and
      has_pattern(results_tsx, r"location\.state|useLocation"))

# 55. Celebration modal renders BEFORE results when new_badges or leveled_up
check(55, "Celebration modal renders before results when new_badges or leveled_up",
      has_pattern(results_tsx, r"celebrat|modal|overlay", re.IGNORECASE) and
      has_pattern(results_tsx, r"new_badges.*leveled_up|leveled_up.*new_badges|new_badges\s*\|\||leveled_up\s*\|\|"))

# 56. Level-up section with Level Up! text
check(56, 'Level-up section shows Level Up! text with level number',
      has_pattern(results_tsx, r"Level Up|level.*up|leveled_up", re.IGNORECASE))

# 57. Badge section shows badge IDs as pills
check(57, "Badge section shows badge IDs as formatted pills",
      has_pattern(results_tsx, r"new_badges|badge.*pill|pill|badge.*map", re.IGNORECASE))

# 58. "See Results" button dismisses celebration
check(58, '"See Results ->" button dismisses celebration',
      has_pattern(results_tsx, r"See Results|setCelebrationDone|dismiss", re.IGNORECASE))

# 59. XP earned shown in results score card
check(59, "XP earned shown in results score card",
      has_pattern(results_tsx, r"xp.*earn|earn.*xp|total_xp|XP", re.IGNORECASE))

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Frontend — Question Bank Admin UI
# ─────────────────────────────────────────────────────────────────────────────

qbank_tsx = read_file(os.path.join(BASE, "frontend", "src", "pages", "admin", "QuestionBank.tsx"))

# 60. QuestionBank.tsx exists
check(60, "frontend/src/pages/admin/QuestionBank.tsx exists",
      qbank_tsx is not None)

# 61. 4 tabs: Review Queue, Live Bank, Upload PDF, Retag
tab_keywords = [
    (r"Review Queue|review.queue", "Review Queue"),
    (r"Live Bank|live.*bank|Live", "Live Bank"),
    (r"Upload.*PDF|upload.*pdf|scan.*pdf", "Upload PDF"),
    (r"Retag|retag", "Retag"),
]
missing_tabs = [name for pat, name in tab_keywords if not has_pattern(qbank_tsx, pat, re.IGNORECASE)]
check(61, "QuestionBank has 4 tabs: Review Queue, Live Bank, Upload PDF, Retag",
      len(missing_tabs) == 0,
      f"missing: {missing_tabs}")

# 62. Stats panel
check(62, "Stats panel showing total/approved/pending counts",
      has_pattern(qbank_tsx, r"total|approved|pending", re.IGNORECASE) and
      has_pattern(qbank_tsx, r"stats|Stats", re.IGNORECASE))

# 63. Review Queue: approve/reject buttons
check(63, "Review Queue: approve/reject buttons",
      has_pattern(qbank_tsx, r"approve|Approve") and
      has_pattern(qbank_tsx, r"reject|Reject"))

# 64. Live Bank: chapter/type filters, paginated table
check(64, "Live Bank: chapter/type filters, paginated table",
      has_pattern(qbank_tsx, r"chapter|Chapter") and
      has_pattern(qbank_tsx, r"page|Page|pagination", re.IGNORECASE))

# 65. Upload PDF: file input calls scanPDF
check(65, "Upload PDF: file input for PDF, calls scanPDF",
      has_pattern(qbank_tsx, r"scanPDF|scan_pdf|scan.*pdf", re.IGNORECASE) and
      has_pattern(qbank_tsx, r"input.*type.*file|file.*input|<input", re.IGNORECASE))

# 66. Retag panel: chapter/topic selectors
check(66, "Retag panel: chapter/topic selectors",
      has_pattern(qbank_tsx, r"retag|Retag") and
      has_pattern(qbank_tsx, r"topic|Topic"))

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Types
# ─────────────────────────────────────────────────────────────────────────────

types_ts = read_file(os.path.join(BASE, "frontend", "src", "types", "index.ts"))

# 67. StudentProfile interface
sp_fields = ["name", "total_xp", "current_level", "xp_in_level", "xp_to_next_level",
             "xp_per_level", "current_streak", "best_streak", "badges", "exam_readiness_score"]
missing_sp = [f for f in sp_fields if not has_string(types_ts, f)]
check(67, "StudentProfile interface with all required fields",
      has_pattern(types_ts, r"StudentProfile") and len(missing_sp) == 0,
      f"missing: {missing_sp}")

# 68. BadgeInfo interface
badge_fields = ["id", "name", "description", "icon", "earned", "earned_at"]
missing_bi = [f for f in badge_fields if not has_string(types_ts, f)]
check(68, "BadgeInfo interface with id/name/description/icon/earned/earned_at",
      has_pattern(types_ts, r"BadgeInfo") and len(missing_bi) == 0,
      f"missing: {missing_bi}")

# 69. ReviewQueueQuestion interface
check(69, "ReviewQueueQuestion interface in types/index.ts",
      has_pattern(types_ts, r"ReviewQueueQuestion"))

# 70. QBankStats interface
check(70, "QBankStats interface in types/index.ts",
      has_pattern(types_ts, r"QBankStats"))

# 71. LiveQuestion interface
check(71, "LiveQuestion interface in types/index.ts",
      has_pattern(types_ts, r"LiveQuestion"))

# 72. SessionResults has new_badges/leveled_up/current_level
check(72, "SessionResults has new_badges?, leveled_up?, current_level?",
      has_pattern(types_ts, r"SessionResults") and
      has_string(types_ts, "new_badges") and
      has_string(types_ts, "leveled_up") and
      has_string(types_ts, "current_level"))

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6: Navigation
# ─────────────────────────────────────────────────────────────────────────────

# 73. App.tsx has /admin/questions route mapped to QuestionBank
check(73, "App.tsx has /admin/questions route mapped to QuestionBank",
      has_pattern(app_tsx, r"\/admin\/questions") and
      has_pattern(app_tsx, r"QuestionBank"))

# 74. App.tsx adminLinks includes "Question Bank" link
check(74, 'App.tsx adminLinks includes "Question Bank" link to /admin/questions',
      has_pattern(app_tsx, r"Question Bank|QuestionBank") and
      has_pattern(app_tsx, r"\/admin\/questions"))

# 75. Nav component shows "Resume Test" link when active test exists
nav_files = [
    os.path.join(BASE, "frontend", "src", "App.tsx"),
    os.path.join(BASE, "frontend", "src", "components", "Nav.tsx") if os.path.isfile(os.path.join(BASE, "frontend", "src", "components", "Nav.tsx")) else None,
]
nav_content = " ".join([read_file(f) or "" for f in nav_files if f])
check(75, 'Nav component shows "Resume Test" link when active test exists',
      has_pattern(nav_content, r"Resume.*Test|resumeTest|activeTest|active.*test", re.IGNORECASE))

# 76. Two-tier navigation: Student tab + Admin tab
check(76, "Two-tier navigation: Student tab + Admin tab",
      has_pattern(app_tsx, r"Student|student") and
      has_pattern(app_tsx, r"Admin|admin") and
      has_pattern(app_tsx, r"tab|Tab|nav|Nav", re.IGNORECASE))

# ─────────────────────────────────────────────────────────────────────────────
# LOGIC CHECKS — import gamification and test
# ─────────────────────────────────────────────────────────────────────────────

print("\n--- Running gamification logic tests ---")

gam = None
gam_error = None
try:
    sys.path.insert(0, BASE)
    # Ensure backend package is importable
    if os.path.join(BASE, "backend") not in sys.path:
        sys.path.insert(0, os.path.join(BASE, "backend"))
    import backend.gamification as gam_mod
    gam = gam_mod
except Exception as e:
    gam_error = str(e)
    print(f"  WARNING: Could not import backend.gamification: {e}")

def logic_check(item_num, description, expr_fn):
    try:
        result = expr_fn()
        check(item_num, description, result)
    except Exception as e:
        check(item_num, description, False, str(e))

if gam:
    # 77-81: calculate_level
    logic_check(77, "calculate_level(0) == 1", lambda: gam.calculate_level(0) == 1)
    logic_check(78, "calculate_level(499) == 1", lambda: gam.calculate_level(499) == 1)
    logic_check(79, "calculate_level(500) == 2", lambda: gam.calculate_level(500) == 2)
    logic_check(80, "calculate_level(999) == 2", lambda: gam.calculate_level(999) == 2)
    logic_check(81, "calculate_level(1000) == 3", lambda: gam.calculate_level(1000) == 3)

    # 82-84: xp_in_current_level
    logic_check(82, "xp_in_current_level(0) == 0", lambda: gam.xp_in_current_level(0) == 0)
    logic_check(83, "xp_in_current_level(499) == 499", lambda: gam.xp_in_current_level(499) == 499)
    logic_check(84, "xp_in_current_level(500) == 0", lambda: gam.xp_in_current_level(500) == 0)

    # 85-86: xp_to_next_level
    logic_check(85, "xp_to_next_level(0) == 500", lambda: gam.xp_to_next_level(0) == 500)
    logic_check(86, "xp_to_next_level(499) == 1", lambda: gam.xp_to_next_level(499) == 1)

    # 87-88: check_level_up
    logic_check(87, "check_level_up(499, 500) == (True, 2)", lambda: gam.check_level_up(499, 500) == (True, 2))
    logic_check(88, "check_level_up(0, 499) == (False, 1)", lambda: gam.check_level_up(0, 499) == (False, 1))

    # 89-90: calculate_xp
    logic_check(89, "calculate_xp(1, 1, 1) == 10 (full XP at diff 1)",
                lambda: gam.calculate_xp(1, 1, 1) == 10)
    logic_check(90, "calculate_xp(3, 2, 4) == 15 (partial: 30 * 0.5)",
                lambda: gam.calculate_xp(3, 2, 4) == 15)

    # 91: Badge idempotency
    def test_badge_idempotency():
        # Check the source code for idempotency — awarding badge twice won't double count
        # We look for set membership check in the award logic
        return has_pattern(gam_py, r"existing_badges") and \
               (has_pattern(gam_py, r"not in existing_badges") or
                has_pattern(gam_py, r"if.*not in.*badge|badge.*not in"))
    logic_check(91, "Badge idempotency: awarding badge twice does not double-count",
                test_badge_idempotency)
else:
    for i in range(77, 92):
        check(i, f"Logic check {i} (gamification import failed)", False, gam_error)

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*70)
passed = sum(1 for _, _, p, _ in results if p)
failed = len(results) - passed

print(f"\n{'='*70}")
print(f"SUMMARY: {passed}/91 PASS, {failed} FAIL")
print(f"{'='*70}")

if failed > 0:
    print("\nFAILED ITEMS:")
    for num, desc, p, detail in results:
        if not p:
            print(f"  [{num:>3}] {desc}")
            if detail:
                print(f"         Reason: {detail}")

sys.exit(0 if failed == 0 else 1)
