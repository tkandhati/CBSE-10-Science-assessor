"""
Student profile endpoints (Phase 6).
GET /api/student/profile   — XP, level, streak, badges
GET /api/student/badges    — all badges with earned status
"""
import json
from fastapi import APIRouter, HTTPException
from backend.database import get_db
from backend.gamification import BADGES, calculate_level, xp_in_current_level, xp_to_next_level

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
