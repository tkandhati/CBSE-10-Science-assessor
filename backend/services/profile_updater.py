"""
Updates student_profile after a session is scored (TDD Section 11.2).

Rolling average with decay:
  - Last 3 sessions  → full weight (1.0)
  - Sessions 4–7 ago → 0.5 weight
  - Older            → 0.25 weight

Session type weighting:
  - Chapter Tests / Mock → 1.5×
  - Understanding Session → 1.0×

XP per question:
  L1=10, L2=20, L3=30, L4=50, L5=75
  Correct = full XP; partial = proportional.
"""
import json
from datetime import date, timedelta
from backend.database import get_db

LEVEL_XP = {1: 10, 2: 20, 3: 30, 4: 50, 5: 75}
SESSION_WEIGHT = {"understanding": 1.0, "chapter_short": 1.5, "chapter_regular": 1.5, "mock": 1.5}

_CHAPTER_BOARD_WEIGHTS = {
    "ch01_chemical_reactions":   7,
    "ch02_acids_bases_salts":    6,
    "ch03_metals_non_metals":    7,
    "ch04_carbon_compounds":     7,
    "ch05_life_processes":       7,
    "ch06_control_coordination": 6,
    "ch07_reproduction":         5,
    "ch08_heredity":             9,
    "ch10_light":                7,
    "ch11_human_eye":            5,
    "ch12_electricity":          8,
    "ch13_magnetic_effects":     7,
    "ch15_our_environment":      3,
}
BOARD_TOTAL_MARKS = sum(_CHAPTER_BOARD_WEIGHTS.values())  # 84


def compute_exam_readiness(topic_scores_flat: dict) -> float:
    """
    Estimate projected board score out of 84 (full Science paper).
    Averages topic scores per chapter, weights by board_weightage, sums.
    Untested chapters assumed 50%.
    """
    chapter_topic_scores: dict = {}
    for key, pct in topic_scores_flat.items():
        chapter = key.split(".", 1)[0] if "." in key else key
        if chapter in _CHAPTER_BOARD_WEIGHTS:
            chapter_topic_scores.setdefault(chapter, []).append(float(pct))

    readiness = 0.0
    for chapter, weight in _CHAPTER_BOARD_WEIGHTS.items():
        scores = chapter_topic_scores.get(chapter, [])
        avg = sum(scores) / len(scores) if scores else 50.0
        readiness += avg / 100.0 * weight

    return round(readiness, 1)


def _flat_score(history: list[dict]) -> float:
    """Compute decayed weighted average from a score history list."""
    if not history:
        return 0.0
    total_w = total_wt = 0.0
    for i, entry in enumerate(reversed(history)):
        decay = 1.0 if i < 3 else (0.5 if i < 7 else 0.25)
        w = entry.get("session_weight", 1.0) * decay
        total_wt += entry["pct"] * w
        total_w += w
    return round(total_wt / total_w, 1) if total_w else 0.0


def update_profile(
    answers_data: list[dict],
    question_meta: dict[str, dict],
    session_type: str,
    generated_params: dict,
) -> dict:
    """
    answers_data: [{question_id, score, max_marks, is_correct}]
    question_meta: {question_id: {topic, difficulty, chapter, type}}
    generated_params: {question_id: {variables, expected_answer, ...}}

    Returns {xp_earned, current_streak, best_streak, total_xp, topic_scores_flat}
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM student_profile WHERE id=1").fetchone()
    profile = dict(row)

    # Load JSON columns
    topic_scores      = json.loads(profile.get("topic_scores")      or "{}")
    topic_attempts    = json.loads(profile.get("topic_attempts")     or "{}")
    topic_last_tested = json.loads(profile.get("topic_last_tested")  or "{}")
    numerical_mastery = json.loads(profile.get("numerical_mastery")  or "{}")

    today = date.today().isoformat()
    sess_w = SESSION_WEIGHT.get(session_type, 1.0)
    xp_earned = 0

    for ans in answers_data:
        qid = ans["question_id"]
        meta = question_meta.get(qid, {})
        topic    = meta.get("topic", "unknown")
        chapter  = meta.get("chapter", "unknown")
        diff     = meta.get("difficulty", 1)
        q_type   = meta.get("type", "short")

        topic_key = f"{chapter}.{topic}"
        score_pct = (ans["score"] / ans["max_marks"] * 100) if ans.get("max_marks") else 0.0

        # Append to rolling history
        history = topic_scores.get(topic_key, [])
        if not isinstance(history, list):
            history = [{"pct": float(history), "session_weight": 1.0, "date": today}]
        history.append({"pct": score_pct, "session_weight": sess_w, "date": today})
        if len(history) > 10:
            history = history[-10:]
        topic_scores[topic_key] = history

        topic_attempts[topic_key]    = topic_attempts.get(topic_key, 0) + 1
        topic_last_tested[topic_key] = today

        # Numerical mastery
        if q_type == "numerical":
            m = numerical_mastery.get(qid, {"correct_streak": 0, "last_params": None})
            if ans.get("is_correct"):
                m["correct_streak"] = m.get("correct_streak", 0) + 1
            else:
                m["correct_streak"] = 0
            # Store the params used so we can reuse if wrong
            if generated_params.get(qid):
                m["last_params"] = generated_params[qid]
            numerical_mastery[qid] = m

        # XP
        base_xp = LEVEL_XP.get(diff, 10)
        if ans.get("is_correct"):
            xp_earned += base_xp
        elif ans.get("score", 0) > 0 and ans.get("max_marks", 1):
            xp_earned += int(base_xp * ans["score"] / ans["max_marks"])

    # Streak calculation
    last_active     = profile.get("last_active_date")
    current_streak  = profile.get("current_streak", 0)
    best_streak     = profile.get("best_streak", 0)
    yesterday       = (date.today() - timedelta(days=1)).isoformat()

    if last_active == today:
        pass  # already counted today
    elif last_active == yesterday:
        current_streak += 1
    else:
        current_streak = 1

    best_streak = max(best_streak, current_streak)
    total_xp    = (profile.get("total_xp") or 0) + xp_earned

    # Flatten history → scalar scores for analytics
    flat_scores = {k: _flat_score(v) if isinstance(v, list) else v for k, v in topic_scores.items()}

    conn.execute(
        """UPDATE student_profile SET
               total_xp=?, current_streak=?, best_streak=?, last_active_date=?,
               topic_scores=?, topic_attempts=?, topic_last_tested=?, numerical_mastery=?
           WHERE id=1""",
        (
            total_xp, current_streak, best_streak, today,
            json.dumps(flat_scores),
            json.dumps(topic_attempts),
            json.dumps(topic_last_tested),
            json.dumps(numerical_mastery),
        ),
    )
    conn.commit()
    conn.close()

    return {
        "xp_earned":      xp_earned,
        "current_streak": current_streak,
        "best_streak":    best_streak,
        "total_xp":       total_xp,
        "topic_scores":   flat_scores,
    }
