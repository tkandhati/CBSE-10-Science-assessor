"""
Student profile endpoints (Phase 6).
GET /api/student/profile   — XP, level, streak, badges
GET /api/student/badges    — all badges with earned status
GET /api/student/countdown — board exam countdown + weekly targets
"""
import json
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException
from backend.database import get_db
from backend.gamification import BADGES, calculate_level, xp_in_current_level, xp_to_next_level
from backend import analytics

router = APIRouter(prefix="/api/student", tags=["student"])


def _get_profile() -> dict:
    conn = get_db()
    row = conn.execute("SELECT * FROM student_profile WHERE id=1").fetchone()
    conn.close()
    if not row:
        raise HTTPException(500, "Student profile not initialised")
    return dict(row)


@router.get("/profile")
def get_student_profile():
    """Return name, XP, level, streak, badges, exam readiness."""
    p = _get_profile()
    total_xp = p.get("total_xp", 0)
    return {
        "name":               p.get("name", "Student"),
        "total_xp":           total_xp,
        "current_level":      calculate_level(total_xp),
        "xp_in_level":        xp_in_current_level(total_xp),
        "xp_to_next_level":   xp_to_next_level(total_xp),
        "xp_per_level":       500,
        "current_streak":     p.get("current_streak", 0),
        "best_streak":        p.get("best_streak", 0),
        "badges":             json.loads(p.get("badges") or "[]"),
        "exam_readiness_score": p.get("exam_readiness_score", 0.0),
    }


@router.get("/countdown")
def get_countdown():
    """
    Board exam countdown widget data.
    Exam date: 2026-12-31. Weekly targets: 2 understanding + 1 chapter test.
    Projected score reuses get_exam_readiness() — no separate ask to student.
    """
    EXAM_DATE = date(2026, 12, 31)
    today = date.today()
    days_remaining = (EXAM_DATE - today).days

    # Projected score from existing analytics
    readiness = analytics.get_exam_readiness()
    projected_score = readiness["score"]
    projected_max   = readiness["max_marks"]

    # Weekly session count (Mon–today)
    monday = today - timedelta(days=today.weekday())
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT type FROM assessments
               WHERE status='completed'
                 AND date(completed_at) >= ?
                 AND type != 'spark'""",
            (monday.isoformat(),),
        ).fetchall()
    finally:
        conn.close()

    week_understanding = sum(1 for r in rows if r["type"] == "understanding")
    week_chapter_test  = sum(1 for r in rows if r["type"] in ("chapter_short", "chapter_regular"))

    # Pace: sessions per week over last 28 days
    conn2 = get_db()
    try:
        recent = conn2.execute(
            """SELECT COUNT(*) as cnt FROM assessments
               WHERE status='completed'
                 AND date(completed_at) >= ?
                 AND type != 'spark'""",
            ((today - timedelta(days=28)).isoformat(),),
        ).fetchone()
    finally:
        conn2.close()

    sessions_last_4w = (recent["cnt"] or 0)
    per_week = sessions_last_4w / 4.0

    if sessions_last_4w == 0:
        pace_label = "Getting Started"
    elif per_week < 1.5:
        pace_label = "Behind"
    elif per_week <= 4:
        pace_label = "On Track"
    else:
        pace_label = "Ahead"

    # Advice line
    u_needed = max(0, 2 - week_understanding)
    t_needed = max(0, 1 - week_chapter_test)
    if u_needed == 0 and t_needed == 0:
        advice = "Weekly target done! Great work this week."
    elif u_needed > 0 and t_needed > 0:
        advice = f"{u_needed} Understanding + {t_needed} Chapter Test left this week."
    elif u_needed > 0:
        advice = f"{u_needed} more Understanding Session{'s' if u_needed > 1 else ''} this week."
    else:
        advice = "1 Chapter Test left to hit your weekly target."

    return {
        "days_remaining":   max(0, days_remaining),
        "exam_date":        EXAM_DATE.isoformat(),
        "projected_score":  projected_score,
        "projected_max":    projected_max,
        "pace_label":       pace_label,
        "weekly_target":    {"understanding": 2, "chapter_test": 1},
        "weekly_done":      {"understanding": week_understanding, "chapter_test": week_chapter_test},
        "advice":           advice,
    }


@router.get("/badges")
def get_student_badges():
    """Return all 12 badge definitions with earned status."""
    p = _get_profile()
    earned_ids: set = set(json.loads(p.get("badges") or "[]"))
    badges_out = []
    for bid, bdata in BADGES.items():
        badges_out.append({
            **bdata,
            "earned":    bid in earned_ids,
            "earned_at": None,   # timestamp tracking is a future enhancement
        })
    return {"badges": badges_out}
