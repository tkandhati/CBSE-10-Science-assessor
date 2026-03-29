"""
Daily Spark router — /api/spark

POST /api/spark/start          Pick next topic (rotation by attempts), generate 10 MCQs via AI
POST /api/spark/{id}/complete  Mark done, credit streak + XP
GET  /api/spark/today          Check if a spark was already completed today
"""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_db
from backend.services import ai_client

router = APIRouter(prefix="/api/spark", tags=["spark"])


# ── Topic rotation ─────────────────────────────────────────────────────────────

# Subject grouping — rotation order: Chemistry → Biology → Physics → Env Science
_SUBJECT_ORDER = ["chemistry", "biology", "physics", "env_sci"]
_SUBJECT_CHAPTERS: dict[str, list[str]] = {
    "chemistry": ["ch01_chemical_reactions", "ch02_acids_bases_salts", "ch03_metals_non_metals", "ch04_carbon_compounds"],
    "biology":   ["ch05_life_processes", "ch06_control_coordination", "ch07_reproduction", "ch08_heredity"],
    "physics":   ["ch10_light", "ch11_human_eye", "ch12_electricity", "ch13_magnetic_effects"],
    "env_sci":   ["ch15_our_environment"],
}
# Reverse map: chapter → subject
_CHAPTER_SUBJECT: dict[str, str] = {
    ch: subj
    for subj, chapters in _SUBJECT_CHAPTERS.items()
    for ch in chapters
}


def _all_topics(conn) -> list[tuple[str, str]]:
    """Return all distinct (chapter, topic) pairs that have approved MCQs."""
    rows = conn.execute(
        """SELECT DISTINCT chapter, topic FROM question_index
           WHERE approved=1 ORDER BY chapter, topic"""
    ).fetchall()
    return [(r["chapter"], r["topic"]) for r in rows]


def _pick_topic(profile: dict, conn) -> tuple[str, str]:
    """
    Pick next topic using subject-first rotation:
    1. Pick subject with fewest total spark attempts (tie-break: predefined order).
    2. Within subject, pick chapter with fewest total attempts.
    3. Within chapter, pick topic with fewest attempts (tie-break: oldest last_tested).
    """
    all_topics = _all_topics(conn)
    if not all_topics:
        return ("ch12_electricity", "ohms_law")

    topic_attempts = profile.get("topic_attempts", {}) or {}
    topic_last     = profile.get("topic_last_tested", {}) or {}

    # Build per-chapter attempt totals from available topics
    chapter_totals: dict[str, int] = {}
    for ch, tp in all_topics:
        key = f"{ch}.{tp}"
        chapter_totals[ch] = chapter_totals.get(ch, 0) + topic_attempts.get(key, 0)

    # Step 1 — pick subject with fewest total attempts
    subject_totals: dict[str, int] = {}
    for subj in _SUBJECT_ORDER:
        subject_totals[subj] = sum(
            chapter_totals.get(ch, 0)
            for ch in _SUBJECT_CHAPTERS[subj]
        )
    best_subject = min(_SUBJECT_ORDER, key=lambda s: subject_totals[s])

    # Step 2 — within subject, pick chapter with fewest total attempts
    subject_chapters_available = [
        ch for ch in _SUBJECT_CHAPTERS[best_subject]
        if any(ch == t[0] for t in all_topics)
    ]
    if not subject_chapters_available:
        # Fallback: ignore subject constraint
        subject_chapters_available = list({ch for ch, _ in all_topics})

    best_chapter = min(subject_chapters_available, key=lambda ch: chapter_totals.get(ch, 0))

    # Step 3 — within chapter, pick topic with fewest attempts (tie-break: oldest last_tested)
    chapter_topics = [(ch, tp) for ch, tp in all_topics if ch == best_chapter]
    best_ch, best_tp = chapter_topics[0]
    best_att  = float("inf")
    best_last = "9999-12-31"

    for ch, tp in chapter_topics:
        key      = f"{ch}.{tp}"
        attempts = topic_attempts.get(key, 0)
        last     = topic_last.get(key, "0000-01-01")
        if attempts < best_att or (attempts == best_att and last < best_last):
            best_ch, best_tp = ch, tp
            best_att  = attempts
            best_last = last

    return best_ch, best_tp


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/today")
def spark_today_status():
    """Return whether a Spark was already completed today."""
    conn = get_db()
    try:
        today = date.today().isoformat()
        row = conn.execute(
            """SELECT id FROM assessments
               WHERE type='spark' AND status='completed'
                 AND date(completed_at)=?""",
            (today,),
        ).fetchone()
        return {"completed_today": row is not None, "session_id": row["id"] if row else None}
    finally:
        conn.close()


@router.post("/start")
def start_spark():
    """
    Pick the next topic by rotation, generate 10 fresh MCQs via AI,
    store the session and question stems in spark_history.
    """
    conn = get_db()
    try:
        # Load profile
        profile_row = conn.execute("SELECT * FROM student_profile WHERE id=1").fetchone()
        profile: dict = dict(profile_row) if profile_row else {}
        for field in ("topic_attempts", "topic_last_tested"):
            v = profile.get(field)
            profile[field] = json.loads(v) if isinstance(v, str) and v else {}

        # Pick topic
        chapter_id, topic_id = _pick_topic(profile, conn)

        # Load history stems for this topic (last 30)
        hist_rows = conn.execute(
            """SELECT question_stem FROM spark_history
               WHERE chapter=? AND topic=?
               ORDER BY asked_on DESC LIMIT 30""",
            (chapter_id, topic_id),
        ).fetchall()
        history_stems = [r["question_stem"] for r in hist_rows]

        # Day-based question mix
        question_mix = ai_client.get_spark_day_mix()

        # Generate via AI (or fallback)
        questions = ai_client.call_spark_generate(
            chapter=chapter_id,
            topic=topic_id,
            question_mix=question_mix,
            history_stems=history_stems,
        )

        # Create assessment record
        session_id = f"spark_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now_iso    = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """INSERT INTO assessments
               (id, type, chapter, topic, question_ids, total_marks, status, started_at, spark_questions)
               VALUES (?, 'spark', ?, ?, '[]', 0, 'in_progress', ?, ?)""",
            (session_id, chapter_id, topic_id, now_iso, json.dumps(questions)),
        )

        # Save question stems to history (for anti-repetition)
        today = date.today().isoformat()
        for q in questions:
            stem = (q.get("question") or "")[:200]
            if stem:
                conn.execute(
                    """INSERT OR IGNORE INTO spark_history
                       (id, chapter, topic, question_stem, asked_on)
                       VALUES (?, ?, ?, ?, ?)""",
                    (uuid.uuid4().hex, chapter_id, topic_id, stem, today),
                )

        conn.commit()

        return {
            "session_id": session_id,
            "chapter":    chapter_id,
            "topic":      topic_id,
            "questions":  questions,
        }
    finally:
        conn.close()


class CompleteBody(BaseModel):
    correct_count: int = 0


@router.post("/{session_id}/complete")
def complete_spark(session_id: str, body: CompleteBody):
    """
    Mark spark session complete.
    Credits streak, awards 10 XP per correct answer,
    and increments topic_attempts for the rotation.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM assessments WHERE id=? AND type='spark'",
            (session_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Spark session not found")

        session = dict(row)
        if session["status"] == "completed":
            # Idempotent — return current profile state
            prof = conn.execute("SELECT current_streak, total_xp FROM student_profile WHERE id=1").fetchone()
            return {
                "status":         "already_completed",
                "xp_gained":      0,
                "current_streak": prof["current_streak"] if prof else 0,
                "total_xp":       prof["total_xp"] if prof else 0,
            }

        now_iso    = datetime.now(timezone.utc).isoformat()
        chapter_id = session["chapter"]
        topic_id   = session["topic"]
        topic_key  = f"{chapter_id}.{topic_id}"

        # Mark assessment complete
        conn.execute(
            "UPDATE assessments SET status='completed', completed_at=?, is_active=0 WHERE id=?",
            (now_iso, session_id),
        )

        # Load profile
        profile_row = conn.execute("SELECT * FROM student_profile WHERE id=1").fetchone()
        profile: dict = dict(profile_row) if profile_row else {}
        for field in ("topic_attempts", "topic_last_tested", "badges"):
            v = profile.get(field)
            default = [] if field == "badges" else {}
            profile[field] = json.loads(v) if isinstance(v, str) and v else default

        # Increment topic_attempts + last_tested
        attempts = profile["topic_attempts"]
        attempts[topic_key] = attempts.get(topic_key, 0) + 1
        last_tested = profile["topic_last_tested"]
        last_tested[topic_key] = date.today().isoformat()

        # Streak logic
        today     = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        last_active     = profile.get("last_active_date")
        current_streak  = profile.get("current_streak", 0)
        best_streak     = profile.get("best_streak", 0)

        if last_active == today:
            pass  # already counted today
        elif last_active == yesterday:
            current_streak += 1
        else:
            current_streak = 1

        best_streak = max(best_streak, current_streak)

        # XP: 10 per correct answer
        xp_gained = max(0, body.correct_count) * 10
        total_xp  = profile.get("total_xp", 0) + xp_gained

        conn.execute(
            """UPDATE student_profile SET
               topic_attempts=?, topic_last_tested=?,
               current_streak=?, best_streak=?, last_active_date=?,
               total_xp=?
               WHERE id=1""",
            (
                json.dumps(attempts),
                json.dumps(last_tested),
                current_streak,
                best_streak,
                today,
                total_xp,
            ),
        )
        conn.commit()

        return {
            "status":         "completed",
            "xp_gained":      xp_gained,
            "current_streak": current_streak,
            "total_xp":       total_xp,
        }
    finally:
        conn.close()
