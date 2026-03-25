"""
Core analytics engine for admin endpoints (Phase 5).
All aggregation computed at query time — no pre-aggregated tables.
"""
import json
from pathlib import Path
from backend.database import get_db
from backend.services.question_loader import get_all as get_question_store

_SYLLABUS_PATH = Path(__file__).parent.parent / "data" / "config" / "syllabus.json"

_CHAPTER_BOARD_WEIGHTS = {
    # Chemistry — 27 marks
    "ch01_chemical_reactions":   7,
    "ch02_acids_bases_salts":    6,
    "ch03_metals_non_metals":    7,
    "ch04_carbon_compounds":     7,
    # Biology — 27 marks
    "ch05_life_processes":       7,
    "ch06_control_coordination": 6,
    "ch07_reproduction":         5,
    "ch08_heredity":             9,
    # Physics — 27 marks
    "ch10_light":                7,
    "ch11_human_eye":            5,
    "ch12_electricity":          8,
    "ch13_magnetic_effects":     7,
    # Environmental Science — 3 marks
    "ch15_our_environment":      3,
}

_SUBJECT_MARKS = {
    "Chemistry":             27,
    "Biology":               27,
    "Physics":               27,
    "Environmental Science":  3,
}

_CHAPTER_SUBJECTS = {
    "ch01_chemical_reactions":   "Chemistry",
    "ch02_acids_bases_salts":    "Chemistry",
    "ch03_metals_non_metals":    "Chemistry",
    "ch04_carbon_compounds":     "Chemistry",
    "ch05_life_processes":       "Biology",
    "ch06_control_coordination": "Biology",
    "ch07_reproduction":         "Biology",
    "ch08_heredity":             "Biology",
    "ch10_light":                "Physics",
    "ch11_human_eye":            "Physics",
    "ch12_electricity":          "Physics",
    "ch13_magnetic_effects":     "Physics",
    "ch15_our_environment":      "Environmental Science",
}

BOARD_TOTAL_MARKS = sum(_CHAPTER_BOARD_WEIGHTS.values())  # 84


def _load_syllabus() -> dict:
    return json.loads(_SYLLABUS_PATH.read_text(encoding="utf-8"))


def _get_profile() -> dict:
    conn = get_db()
    row = conn.execute("SELECT * FROM student_profile WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}


def get_topic_scores(min_attempts: int = 3) -> dict:
    """
    Returns dict of topic_key -> weighted average score %.
    topic_key format: "chapter_id.topic_id"
    Only topics with >= min_attempts are included.
    """
    profile = _get_profile()
    topic_scores   = json.loads(profile.get("topic_scores")   or "{}")
    topic_attempts = json.loads(profile.get("topic_attempts") or "{}")

    return {
        k: round(float(v), 1)
        for k, v in topic_scores.items()
        if topic_attempts.get(k, 0) >= min_attempts
    }


def get_topic_trend(topic_id: str, n: int = 10) -> str:
    """
    Fetch last n answers for the topic from the answers table.
    Returns "up" / "down" / "flat".
    """
    parts = topic_id.split(".", 1)
    if len(parts) != 2:
        return "flat"
    chapter, topic = parts

    conn = get_db()
    rows = conn.execute(
        """
        SELECT a.score, a.max_marks
        FROM   answers a
        JOIN   question_index qi  ON a.question_id    = qi.id
        JOIN   assessments    ass ON a.assessment_id  = ass.id
        WHERE  qi.chapter = ? AND qi.topic = ? AND a.max_marks > 0
        ORDER  BY ass.started_at DESC
        LIMIT  ?
        """,
        (chapter, topic, n),
    ).fetchall()
    conn.close()

    if len(rows) < 4:
        return "flat"

    # rows[0] = most recent; convert to pct
    pcts = [r["score"] / r["max_marks"] * 100 for r in rows]
    recent_avg = sum(pcts[:3]) / 3
    prev_avg   = sum(pcts[3:6]) / len(pcts[3:6])

    diff = recent_avg - prev_avg
    if diff > 5:
        return "up"
    if diff < -5:
        return "down"
    return "flat"


def get_topic_classification(topic_scores: dict) -> dict:
    """
    Classify each syllabus topic into a band.
    Returns dict of topic_key -> {band, score, attempts, last_tested, trend, recommended_action}
    """
    profile            = _get_profile()
    topic_attempts     = json.loads(profile.get("topic_attempts")     or "{}")
    topic_last_tested  = json.loads(profile.get("topic_last_tested")  or "{}")

    syllabus = _load_syllabus()
    result: dict = {}

    for chapter in syllabus.get("chapters", []):
        for topic in chapter.get("topics", []):
            key      = f"{chapter['id']}.{topic['id']}"
            attempts = topic_attempts.get(key, 0)
            score    = topic_scores.get(key)

            if attempts < 3 or score is None:
                band = "Untested"
                score_val = float(score) if score is not None else 0.0
            else:
                score_val = float(score)
                if score_val >= 80:
                    band = "Strong"
                elif score_val >= 60:
                    band = "Developing"
                elif score_val >= 40:
                    band = "Weak"
                else:
                    band = "Critical"

            trend = get_topic_trend(key)

            if band == "Critical":
                action = "Revise Now"
            elif band == "Weak":
                action = "Practice More"
            elif band == "Developing" and trend == "flat":
                action = "Consolidate"
            elif band == "Strong" and trend == "up":
                action = "Keep Going"
            elif band == "Strong":
                action = "Maintain"
            elif band == "Untested":
                action = "Start Practising"
            else:
                action = "Practice More"

            result[key] = {
                "topic_title":         topic["title"],
                "chapter_id":          chapter["id"],
                "chapter_title":       chapter["title"],
                "band":                band,
                "score":               score_val,
                "attempts":            attempts,
                "last_tested":         topic_last_tested.get(key),
                "trend":               trend,
                "recommended_action":  action,
            }

    return result


def get_chapter_performance() -> dict:
    """
    Returns dict of chapter_id -> {average, attempts, band, title}
    Computed from answers JOIN question_index.
    """
    conn = get_db()
    rows = conn.execute(
        """
        SELECT qi.chapter,
               SUM(a.score)      AS total_score,
               SUM(a.max_marks)  AS total_max,
               COUNT(a.id)       AS attempts
        FROM   answers a
        JOIN   question_index qi ON a.question_id = qi.id
        WHERE  a.max_marks > 0
        GROUP  BY qi.chapter
        """
    ).fetchall()
    conn.close()

    syllabus = _load_syllabus()
    ch_titles = {c["id"]: c["title"] for c in syllabus.get("chapters", [])}

    result: dict = {}
    for row in rows:
        chapter = row["chapter"]
        avg = round(row["total_score"] / row["total_max"] * 100, 1) if row["total_max"] else 0.0
        if avg >= 80:
            band = "Strong"
        elif avg >= 60:
            band = "Developing"
        elif avg >= 40:
            band = "Weak"
        elif avg > 0:
            band = "Critical"
        else:
            band = "Untested"
        result[chapter] = {
            "title":    ch_titles.get(chapter, chapter),
            "average":  avg,
            "attempts": row["attempts"],
            "band":     band,
        }

    # Fill missing chapters — all 13 chapters always appear
    for chapter, weight in _CHAPTER_BOARD_WEIGHTS.items():
        if chapter not in result:
            result[chapter] = {
                "title":    ch_titles.get(chapter, chapter),
                "average":  0.0,
                "attempts": 0,
                "band":     "Untested",
                "subject":  _CHAPTER_SUBJECTS.get(chapter, ""),
            }
        else:
            result[chapter]["subject"] = _CHAPTER_SUBJECTS.get(chapter, "")

    return result


def get_marks_lost_by_type() -> dict:
    """Returns dict of question_type -> marks_lost."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT qi.type,
               SUM(a.max_marks - a.score) AS marks_lost
        FROM   answers a
        JOIN   question_index qi ON a.question_id = qi.id
        GROUP  BY qi.type
        """
    ).fetchall()
    conn.close()
    return {row["type"]: round(row["marks_lost"], 1) for row in rows}


def get_exam_readiness() -> dict:
    """
    Returns {score, range_low, range_high, band_label, subject_breakdown}.
    Scaled to BOARD_TOTAL_MARKS (84). Subject breakdown shows Physics/Chemistry/Biology/EnvSci sub-scores.
    """
    profile      = _get_profile()
    topic_scores = json.loads(profile.get("topic_scores") or "{}")

    chapter_scores: dict = {}
    for key, pct in topic_scores.items():
        chapter = key.split(".", 1)[0] if "." in key else key
        if chapter in _CHAPTER_BOARD_WEIGHTS:
            chapter_scores.setdefault(chapter, []).append(float(pct))

    readiness = 0.0
    subject_scores: dict = {s: 0.0 for s in _SUBJECT_MARKS}

    for chapter, weight in _CHAPTER_BOARD_WEIGHTS.items():
        scores = chapter_scores.get(chapter, [])
        avg = sum(scores) / len(scores) if scores else 50.0
        contrib = avg / 100.0 * weight
        readiness += contrib
        subj = _CHAPTER_SUBJECTS.get(chapter, "Physics")
        subject_scores[subj] = subject_scores.get(subj, 0.0) + contrib

    score      = round(readiness, 1)
    max_marks  = BOARD_TOTAL_MARKS
    range_low  = round(max(0.0, score - 2.0), 1)
    range_high = round(min(float(max_marks), score + 2.0), 1)

    # Band thresholds scaled proportionally from 84
    pct = score / max_marks * 100
    if pct >= 75:
        band = "Excellent"
    elif pct >= 60:
        band = "Good"
    elif pct >= 45:
        band = "Satisfactory"
    elif pct >= 33:
        band = "Needs Improvement"
    else:
        band = "Critical"

    return {
        "score":      score,
        "range_low":  range_low,
        "range_high": range_high,
        "band_label": band,
        "max_marks":  max_marks,
        "subject_breakdown": {
            subj: {"score": round(subject_scores.get(subj, 0.0), 1), "max": _SUBJECT_MARKS[subj]}
            for subj in _SUBJECT_MARKS
        },
    }


def get_weak_topics(n: int = 5) -> list:
    """Top n weakest topics with >= 3 attempts, sorted ascending by score."""
    scores = get_topic_scores(min_attempts=3)
    profile = _get_profile()
    topic_last_tested = json.loads(profile.get("topic_last_tested") or "{}")
    topic_attempts    = json.loads(profile.get("topic_attempts")    or "{}")

    syllabus = _load_syllabus()
    ch_titles = {c["id"]: c["title"] for c in syllabus.get("chapters", [])}
    topic_titles: dict = {}
    for c in syllabus.get("chapters", []):
        for t in c.get("topics", []):
            topic_titles[f"{c['id']}.{t['id']}"] = t["title"]

    sorted_topics = sorted(scores.items(), key=lambda x: x[1])
    result = []
    for k, v in sorted_topics[:n]:
        parts = k.split(".", 1)
        result.append({
            "topic_key":    k,
            "topic_title":  topic_titles.get(k, k),
            "chapter_id":   parts[0] if parts else k,
            "chapter_title": ch_titles.get(parts[0], parts[0]) if parts else k,
            "score":        v,
            "attempts":     topic_attempts.get(k, 0),
            "last_tested":  topic_last_tested.get(k),
        })
    return result


def get_untested_topics() -> list:
    """Topics from syllabus with < 3 attempts."""
    profile        = _get_profile()
    topic_attempts = json.loads(profile.get("topic_attempts") or "{}")

    syllabus   = _load_syllabus()
    untested   = []
    for chapter in syllabus.get("chapters", []):
        for topic in chapter.get("topics", []):
            key      = f"{chapter['id']}.{topic['id']}"
            attempts = topic_attempts.get(key, 0)
            if attempts < 3:
                untested.append({
                    "topic_key":     key,
                    "topic_title":   topic["title"],
                    "chapter_id":    chapter["id"],
                    "chapter_title": chapter["title"],
                    "attempts":      attempts,
                })
    return untested
