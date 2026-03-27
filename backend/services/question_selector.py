"""
Question selection for Understanding Sessions.
Queries question_index, applies TDD Section 4.3 weighting,
and returns a ranked candidate list for AI Call 1.
"""
import json
from typing import Optional
from backend.database import get_db


def get_recent_session_ids(chapter: str, session_type: str, limit: int = 3) -> list[str]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id FROM assessments WHERE type=? AND chapter=? ORDER BY started_at DESC LIMIT ?",
        [session_type, chapter, limit],
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_recently_served_ids(session_ids: list[str]) -> set[str]:
    if not session_ids:
        return set()
    conn = get_db()
    ph = ",".join("?" * len(session_ids))
    rows = conn.execute(
        f"SELECT DISTINCT question_id FROM answers WHERE assessment_id IN ({ph})",
        session_ids,
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def get_last_session_topics(session_ids: list[str]) -> set[str]:
    """Topics that appeared in the most recent session."""
    if not session_ids:
        return set()
    last_id = session_ids[0]
    conn = get_db()
    rows = conn.execute(
        """SELECT DISTINCT qi.topic FROM answers a
           JOIN question_index qi ON a.question_id = qi.id
           WHERE a.assessment_id = ?""",
        [last_id],
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def get_eligible_questions(
    chapter: str,
    topic: Optional[str],
    recently_served: set[str],
    exclude_diagram: bool = False,
) -> list[dict]:
    conn = get_db()
    params: list = [chapter]
    query = "SELECT * FROM question_index WHERE chapter=? AND approved=1"
    if topic:
        query += " AND topic=?"
        params.append(topic)
    if exclude_diagram:
        query += " AND has_diagram=0"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    eligible = []
    for r in rows:
        d = dict(r)
        if d["id"] not in recently_served:
            eligible.append(d)
    return eligible


def compute_weights(
    questions: list[dict],
    topic_scores: dict[str, float],
    last_session_topics: set[str],
) -> list[tuple[dict, float]]:
    """Apply Section 4.3 selection weights."""
    served_counts = [q["times_served"] for q in questions]
    median_served = sorted(served_counts)[len(served_counts) // 2] if served_counts else 0

    weighted = []
    for q in questions:
        weight = 1.0
        chapter = q["chapter"]
        topic = q["topic"]

        # Check topic score (try chapter.topic key first, then bare topic)
        score = topic_scores.get(f"{chapter}.{topic}", topic_scores.get(topic, 100.0))
        if isinstance(score, list):          # handle history list format
            score = score[-1]["pct"] if score else 100.0

        if score < 60:
            weight *= 2.0
        if topic not in last_session_topics:
            weight *= 1.5
        if q["times_served"] > median_served:
            weight *= 0.5

        weighted.append((q, weight))

    return weighted


def select_candidates(
    chapter: str,
    topic: Optional[str],
    topic_scores: dict,
    session_type: str = "understanding",
    max_candidates: int = 50,
) -> list[dict]:
    """
    Full pipeline: eligible → weighted → sorted → top N.
    Returns list of question_index rows sorted by weight descending.
    """
    recent_ids = get_recent_session_ids(chapter, session_type)
    recently_served = get_recently_served_ids(recent_ids)
    last_topics = get_last_session_topics(recent_ids)

    no_diagram = (session_type == "understanding")
    eligible = get_eligible_questions(chapter, topic, recently_served, exclude_diagram=no_diagram)
    if not eligible:
        # Fallback: ignore anti-repetition if pool is too small
        eligible = get_eligible_questions(chapter, topic, set(), exclude_diagram=no_diagram)

    weighted = compute_weights(eligible, topic_scores, last_topics)
    weighted.sort(key=lambda x: x[1], reverse=True)

    return [q for q, _ in weighted[:max_candidates]]
