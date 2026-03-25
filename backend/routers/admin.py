"""
Admin API endpoints — Phase 5.
All analytics computed at query time via analytics.py.
"""
import json
from datetime import datetime, timedelta, timezone, date as date_type
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend import analytics
from backend.services.question_loader import get_all as get_question_store
from backend.services.ai_client import call_guidance

router = APIRouter(prefix="/api/admin", tags=["admin"])

_TEMPLATES_PATH = Path(__file__).parent.parent.parent / "data" / "config" / "test_templates.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_json_field(value) -> dict | list:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def _classify_reason(point: str) -> str:
    p = point.lower()
    if "formula" in p or "equation" in p:
        return "formula not used"
    if "diagram" in p or "draw" in p:
        return "diagram incomplete"
    return "key point missed"


def _check_coverage_gaps() -> list:
    """Return coverage gaps against test templates."""
    conn = get_db()
    rows = conn.execute(
        "SELECT chapter, type, COUNT(*) as cnt FROM question_index WHERE approved=1 GROUP BY chapter, type"
    ).fetchall()
    conn.close()

    # Build lookup: (chapter, type) -> count
    avail: dict = {}
    for row in rows:
        avail[(row["chapter"], row["type"])] = avail.get((row["chapter"], row["type"]), 0) + row["cnt"]

    templates = json.loads(_TEMPLATES_PATH.read_text(encoding="utf-8"))["templates"]
    chapters = [
        "ch01_chemical_reactions", "ch02_acids_bases_salts",
        "ch03_metals_non_metals",  "ch04_carbon_compounds",
        "ch05_life_processes",     "ch06_control_coordination",
        "ch07_reproduction",       "ch08_heredity",
        "ch10_light",              "ch11_human_eye",
        "ch12_electricity",        "ch13_magnetic_effects",
        "ch15_our_environment",
    ]
    gaps = []

    for chapter_id in chapters:
        for tmpl_id in ["chapter_short", "chapter_regular"]:
            tmpl = templates[tmpl_id]
            for slot in tmpl["slots"]:
                needed    = slot["count"]
                q_type    = slot["type"]
                available = avail.get((chapter_id, q_type), 0)
                if available < needed:
                    gaps.append({
                        "chapter":   chapter_id,
                        "template":  tmpl_id,
                        "type":      q_type,
                        "needed":    needed,
                        "available": available,
                        "gap":       needed - available,
                    })
    return gaps


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def admin_dashboard():
    """Aggregated stats, chapter performance, strengths/weaknesses, exam readiness."""
    chapter_perf  = analytics.get_chapter_performance()
    weak_topics   = analytics.get_weak_topics(5)
    exam_readiness = analytics.get_exam_readiness()

    conn = get_db()
    total_sessions = conn.execute(
        "SELECT COUNT(*) FROM assessments WHERE status='completed'"
    ).fetchone()[0]
    total_answered = conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    avg_row = conn.execute(
        "SELECT AVG(percentage) FROM assessments WHERE status='completed' AND percentage > 0"
    ).fetchone()
    overall_avg = round(avg_row[0] or 0.0, 1)

    profile = conn.execute(
        "SELECT current_streak, best_streak FROM student_profile WHERE id=1"
    ).fetchone()

    recent_rows = conn.execute(
        """
        SELECT id, type, chapter, topic, score_obtained, total_marks,
               percentage, started_at, completed_at, duration_seconds, status
        FROM   assessments
        WHERE  status = 'completed'
        ORDER  BY started_at DESC
        LIMIT  10
        """
    ).fetchall()
    conn.close()

    # Strengths: topics with highest scores (min 3 attempts)
    all_scores    = analytics.get_topic_scores(min_attempts=3)
    sorted_scores = sorted(all_scores.items(), key=lambda x: -x[1])

    profile_data = _parse_json_field(None)
    if profile:
        profile_data = {"current_streak": profile["current_streak"], "best_streak": profile["best_streak"]}

    return {
        "total_sessions":          total_sessions,
        "total_questions_answered": total_answered,
        "overall_average":         overall_avg,
        "current_streak":          profile["current_streak"] if profile else 0,
        "best_streak":             profile["best_streak"] if profile else 0,
        "chapter_performance":     chapter_perf,
        "recent_sessions":         [dict(r) for r in recent_rows],
        "strengths":               [{"topic_key": k, "score": v} for k, v in sorted_scores[:4]],
        "weaknesses":              weak_topics,
        "exam_readiness":          exam_readiness,
        "coverage_gaps":           _check_coverage_gaps(),
    }


@router.get("/strengths")
def topic_strengths():
    """
    Full topic intelligence payload with bands, trends, recommended actions.
    Action labels: 'Revise Now' (Critical), 'Practice More' (Weak),
    'Consolidate' (Developing/flat), 'Keep Going' (Strong/up).
    """
    topic_scores_qualified = analytics.get_topic_scores(min_attempts=3)
    classification = analytics.get_topic_classification(topic_scores_qualified)
    weak_topics    = analytics.get_weak_topics(5)
    untested       = analytics.get_untested_topics()

    return {
        "topics":          classification,
        "weak_topics":     weak_topics,
        "untested_topics": untested,
    }


@router.get("/sessions")
def list_sessions(
    page:    int = Query(default=1,  ge=1),
    limit:   int = Query(default=10, ge=1, le=100),
    chapter: Optional[str] = None,
    type:    Optional[str] = None,
):
    """Paginated session history with optional filters."""
    conn = get_db()

    where_clauses: list[str] = []
    params: list = []
    if chapter:
        where_clauses.append("chapter = ?")
        params.append(chapter)
    if type:
        where_clauses.append("type = ?")
        params.append(type)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    total  = conn.execute(f"SELECT COUNT(*) FROM assessments {where_sql}", params).fetchone()[0]
    offset = (page - 1) * limit

    rows = conn.execute(
        f"""
        SELECT id, type, chapter, topic, total_marks, score_obtained, percentage,
               status, started_at, completed_at, duration_seconds
        FROM   assessments
        {where_sql}
        ORDER  BY started_at DESC
        LIMIT  ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()
    conn.close()

    return {"sessions": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}


@router.get("/session/{session_id}")
def session_detail(session_id: str):
    """Full session detail: every question, answer, OCR, score, marks lost analysis."""
    conn = get_db()
    assessment = conn.execute(
        "SELECT * FROM assessments WHERE id=?", (session_id,)
    ).fetchone()
    if not assessment:
        conn.close()
        raise HTTPException(404, "Session not found")

    assessment_dict = dict(assessment)
    # Parse JSON columns
    for col in ("question_ids", "generated_params", "section_map"):
        assessment_dict[col] = _parse_json_field(assessment_dict.get(col))

    answer_rows = conn.execute(
        "SELECT * FROM answers WHERE assessment_id=? ORDER BY rowid",
        (session_id,),
    ).fetchall()
    conn.close()

    question_store = get_question_store()

    answers_out:        list  = []
    marks_lost_by_type: dict  = {}
    marks_lost_by_reason: dict = {}

    for ans in answer_rows:
        a = dict(ans)
        qid = a["question_id"]
        q   = question_store.get(qid, {})

        a["question_text"]  = q.get("text", "")
        a["question_type"]  = q.get("type", "")
        a["model_answer"]   = (q.get("rubric") or {}).get("expected_answer", "")
        a["key_points"]     = (q.get("rubric") or {}).get("key_points", [])

        a["feedback"]    = _parse_json_field(a.get("feedback"))
        a["suggestions"] = _parse_json_field(a.get("suggestions")) if a.get("suggestions") else []

        marks_lost = (a.get("max_marks") or 0) - (a.get("score") or 0)
        if marks_lost > 0:
            q_type = q.get("type", "unknown")
            marks_lost_by_type[q_type] = round(
                marks_lost_by_type.get(q_type, 0.0) + marks_lost, 1
            )
            for point in (a["feedback"].get("points_missed") or []):
                reason = _classify_reason(str(point))
                marks_lost_by_reason[reason] = marks_lost_by_reason.get(reason, 0) + 1

        answers_out.append(a)

    return {
        "session":             assessment_dict,
        "answers":             answers_out,
        "marks_lost_by_type":  marks_lost_by_type,
        "marks_lost_by_reason": marks_lost_by_reason,
    }


class OverrideRequest(BaseModel):
    score: float
    note:  str = ""


@router.put("/session/{session_id}/answer/{answer_id}/override")
def override_answer_score(session_id: str, answer_id: str, body: OverrideRequest):
    """Override AI-scored answer. Recalculates assessment totals immediately."""
    conn = get_db()
    ans = conn.execute(
        "SELECT * FROM answers WHERE id=? AND assessment_id=?", (answer_id, session_id)
    ).fetchone()
    if not ans:
        conn.close()
        raise HTTPException(404, "Answer not found")

    max_marks = ans["max_marks"]
    if body.score < 0 or body.score > max_marks:
        conn.close()
        raise HTTPException(400, f"Score must be 0–{max_marks}")

    conn.execute(
        "UPDATE answers SET score=?, override_score=?, override_note=? WHERE id=?",
        (body.score, body.score, body.note, answer_id),
    )

    agg = conn.execute(
        "SELECT SUM(score) AS total FROM answers WHERE assessment_id=?", (session_id,)
    ).fetchone()
    total_max_row = conn.execute(
        "SELECT total_marks FROM assessments WHERE id=?", (session_id,)
    ).fetchone()

    new_score = round(agg["total"] or 0.0, 1)
    total_max = total_max_row["total_marks"] if total_max_row else 1
    new_pct   = round(new_score / total_max * 100, 1) if total_max else 0.0

    conn.execute(
        "UPDATE assessments SET score_obtained=?, percentage=? WHERE id=?",
        (new_score, new_pct, session_id),
    )
    conn.commit()
    conn.close()

    return {"score": body.score, "new_total": new_score, "new_percentage": new_pct}


@router.get("/coverage")
def coverage_report():
    """Question bank coverage gaps vs test template requirements."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT chapter, topic, type, difficulty, COUNT(*) AS cnt
        FROM   question_index
        WHERE  approved = 1
        GROUP  BY chapter, topic, type, difficulty
        """
    ).fetchall()
    conn.close()

    chapter_counts: dict = {}
    for row in rows:
        chapter_counts[row["chapter"]] = chapter_counts.get(row["chapter"], 0) + row["cnt"]

    return {
        "gaps":           _check_coverage_gaps(),
        "chapter_counts": chapter_counts,
    }


@router.get("/guidance")
def study_guidance(refresh: bool = False):
    """
    AI-generated study guidance, cached 24 hours.
    Outside the per-session 2-call budget.
    Pass ?refresh=true to force a fresh call.
    """
    conn = get_db()
    profile_row = conn.execute("SELECT * FROM student_profile WHERE id=1").fetchone()
    conn.close()

    if not profile_row:
        raise HTTPException(500, "Student profile not found")

    profile   = dict(profile_row)
    cached_at = profile.get("guidance_cached_at")
    cache_raw = profile.get("guidance_cache")

    # Return cached if fresh (< 24 h) and not forced refresh
    if cached_at and cache_raw and not refresh:
        try:
            dt = datetime.fromisoformat(cached_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if age_h < 24:
                return _parse_json_field(cache_raw)
        except Exception:
            pass

    # Build context for AI call
    weak_topics   = analytics.get_weak_topics(5)
    exam_readiness = analytics.get_exam_readiness()

    conn = get_db()
    recent_rows = conn.execute(
        """
        SELECT type, chapter, percentage, started_at
        FROM   assessments WHERE status='completed'
        ORDER  BY started_at DESC LIMIT 5
        """
    ).fetchall()
    conn.close()

    board_exam_date  = date_type(2026, 4, 15)
    days_until_exam  = (board_exam_date - date_type.today()).days

    guidance_data = call_guidance(
        weak_topics         = weak_topics,
        recent_sessions     = [dict(r) for r in recent_rows],
        current_streak      = profile.get("current_streak", 0),
        exam_readiness_score = exam_readiness["score"],
        days_until_exam     = days_until_exam,
    )

    # Cache result
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "UPDATE student_profile SET guidance_cache=?, guidance_cached_at=? WHERE id=1",
        (json.dumps(guidance_data), now_iso),
    )
    conn.commit()
    conn.close()

    return guidance_data
