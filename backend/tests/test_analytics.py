"""
test_analytics.py — Tests 34-45.
Tests analytics.py functions using tmp_db fixture.
"""
import json
import sqlite3
import pytest
from pathlib import Path


def _set_profile(db_path: str, topic_scores: dict = None, topic_attempts: dict = None,
                 topic_last_tested: dict = None):
    """Helper to write profile fields into the test DB."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """UPDATE student_profile SET topic_scores=?, topic_attempts=?, topic_last_tested=? WHERE id=1""",
        [
            json.dumps(topic_scores or {}),
            json.dumps(topic_attempts or {}),
            json.dumps(topic_last_tested or {}),
        ],
    )
    conn.commit()
    conn.close()


# ── Test 34 ──────────────────────────────────────────────────────────────────

def test_get_topic_scores_empty_when_no_attempts(tmp_db):
    """get_topic_scores() returns empty dict when profile has no attempts."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    from backend.analytics import get_topic_scores
    result = get_topic_scores(min_attempts=3)
    assert result == {}, f"Expected empty dict, got {result}"


# ── Test 35 ──────────────────────────────────────────────────────────────────

def test_get_topic_scores_excludes_below_min_attempts(tmp_db):
    """get_topic_scores() excludes topics with < 3 attempts."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _set_profile(
        tmp_db,
        topic_scores={"ch10_light.reflection": 75.0, "ch10_light.refraction": 60.0},
        topic_attempts={"ch10_light.reflection": 2, "ch10_light.refraction": 5},
    )

    from backend.analytics import get_topic_scores
    result = get_topic_scores(min_attempts=3)
    assert "ch10_light.reflection" not in result, "Should exclude topic with only 2 attempts"
    assert "ch10_light.refraction" in result, "Should include topic with 5 attempts"


# ── Test 36 ──────────────────────────────────────────────────────────────────

def test_get_topic_classification_untested_for_low_attempts(tmp_db):
    """get_topic_classification returns 'Untested' band for topics with < 3 attempts."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _set_profile(
        tmp_db,
        topic_scores={},
        topic_attempts={"ch10_light.reflection_laws": 1},
    )

    from backend.analytics import get_topic_classification
    result = get_topic_classification({})

    # Every topic should be Untested (no topic has >= 3 attempts)
    for key, info in result.items():
        assert info["band"] == "Untested", f"{key} should be Untested, got {info['band']}"


# ── Test 37 ──────────────────────────────────────────────────────────────────

def test_get_topic_classification_bands(tmp_db):
    """Test band assignments: Strong>=80, Developing 60-79, Weak 40-59, Critical <40."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    # Set up 4 topics with different scores and >=3 attempts
    scores = {
        "ch10_light.reflection_laws": 85.0,
        "ch10_light.refraction": 65.0,
        "ch10_light.lens_formula": 45.0,
        "ch10_light.human_eye_defects": 35.0,
    }
    attempts = {k: 5 for k in scores}

    _set_profile(tmp_db, topic_scores=scores, topic_attempts=attempts)

    from backend.analytics import get_topic_classification
    result = get_topic_classification(scores)

    # Check only the topics we set
    for key, expected_band in [
        ("ch10_light.reflection_laws", "Strong"),
        ("ch10_light.refraction", "Developing"),
        ("ch10_light.lens_formula", "Weak"),
        ("ch10_light.human_eye_defects", "Critical"),
    ]:
        if key in result:
            assert result[key]["band"] == expected_band, (
                f"{key}: expected {expected_band}, got {result[key]['band']}"
            )


# ── Test 38 ──────────────────────────────────────────────────────────────────

def test_get_topic_trend_flat_when_insufficient_data(tmp_db):
    """get_topic_trend returns 'flat' when < 4 data points."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    from backend.analytics import get_topic_trend
    # No answers in DB → < 4 points → flat
    result = get_topic_trend("ch10_light.reflection_laws")
    assert result == "flat"


# ── Test 39 ──────────────────────────────────────────────────────────────────

def test_get_topic_trend_up_when_improving(tmp_db):
    """get_topic_trend returns 'up' when recent avg > prev avg + 5%."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    # Insert question_index row and assessment rows
    conn = sqlite3.connect(tmp_db)

    # Create a question in ch10_light with topic=reflection_laws
    conn.execute(
        """INSERT OR REPLACE INTO question_index
           (id, chapter, topic, type, difficulty, marks, approved)
           VALUES ('test_q_trend', 'ch10_light', 'reflection_laws', 'short', 2, 2, 1)"""
    )

    # Create 2 assessments (older = low score, recent = high score)
    import uuid
    from datetime import datetime, timedelta

    old_sess = f"asmt_old_{uuid.uuid4().hex[:6]}"
    new_sess = f"asmt_new_{uuid.uuid4().hex[:6]}"
    base_time = datetime.now() - timedelta(days=10)

    for i, (sess_id, days_ago, score_pct) in enumerate([
        (old_sess + "_1", 8, 0.3),
        (old_sess + "_2", 7, 0.3),
        (old_sess + "_3", 6, 0.3),
        (new_sess + "_1", 2, 1.0),
        (new_sess + "_2", 1, 0.9),
        (new_sess + "_3", 0, 0.95),
    ]):
        sess_time = (datetime.now() - timedelta(days=days_ago)).isoformat()
        conn.execute(
            """INSERT INTO assessments
               (id, type, chapter, topic, question_ids, total_marks, status, started_at, is_active)
               VALUES (?,?,?,?,?,?,?,?,0)""",
            [sess_id, "understanding", "ch10_light", None, "[]", 2, "scored", sess_time],
        )
        max_m = 2
        score = round(score_pct * max_m, 1)
        ans_id = f"ans_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO answers
               (id, assessment_id, question_id, score, max_marks)
               VALUES (?,?,?,?,?)""",
            [ans_id, sess_id, "test_q_trend", score, max_m],
        )

    conn.commit()
    conn.close()

    from backend.analytics import get_topic_trend
    result = get_topic_trend("ch10_light.reflection_laws")
    assert result == "up", f"Expected 'up' trend, got '{result}'"


# ── Test 40 ──────────────────────────────────────────────────────────────────

def test_get_topic_trend_down_when_declining(tmp_db):
    """get_topic_trend returns 'down' when recent avg < prev avg - 5%."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    conn = sqlite3.connect(tmp_db)
    conn.execute(
        """INSERT OR REPLACE INTO question_index
           (id, chapter, topic, type, difficulty, marks, approved)
           VALUES ('test_q_down', 'ch10_light', 'refraction', 'short', 2, 2, 1)"""
    )

    import uuid
    from datetime import datetime, timedelta

    # High scores long ago, low scores recently
    for days_ago, score_pct in [(8, 1.0), (7, 0.9), (6, 0.95), (2, 0.2), (1, 0.3), (0, 0.25)]:
        sess_id = f"asmt_{uuid.uuid4().hex[:8]}"
        sess_time = (datetime.now() - timedelta(days=days_ago)).isoformat()
        conn.execute(
            """INSERT INTO assessments
               (id, type, chapter, topic, question_ids, total_marks, status, started_at, is_active)
               VALUES (?,?,?,?,?,?,?,?,0)""",
            [sess_id, "understanding", "ch10_light", None, "[]", 2, "scored", sess_time],
        )
        ans_id = f"ans_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO answers (id, assessment_id, question_id, score, max_marks) VALUES (?,?,?,?,?)",
            [ans_id, sess_id, "test_q_down", round(score_pct * 2, 1), 2],
        )

    conn.commit()
    conn.close()

    from backend.analytics import get_topic_trend
    result = get_topic_trend("ch10_light.refraction")
    assert result == "down", f"Expected 'down' trend, got '{result}'"


# ── Test 41 ──────────────────────────────────────────────────────────────────

def test_get_exam_readiness_max_marks_is_84(tmp_db):
    """get_exam_readiness() max_marks = 84."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    from backend.analytics import get_exam_readiness
    result = get_exam_readiness()
    assert result["max_marks"] == 84, f"Expected max_marks=84, got {result['max_marks']}"


# ── Test 42 ──────────────────────────────────────────────────────────────────

def test_get_exam_readiness_subject_breakdown_has_4_subjects(tmp_db):
    """get_exam_readiness() returns subject_breakdown with 4 subjects."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    from backend.analytics import get_exam_readiness
    result = get_exam_readiness()
    breakdown = result.get("subject_breakdown", {})
    expected_subjects = {"Chemistry", "Biology", "Physics", "Environmental Science"}
    assert set(breakdown.keys()) == expected_subjects, (
        f"Expected {expected_subjects}, got {set(breakdown.keys())}"
    )


# ── Test 43 ──────────────────────────────────────────────────────────────────

def test_get_weak_topics_sorted_ascending(tmp_db):
    """get_weak_topics() returns topics sorted ascending by score."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    # Set up a few topics with >=3 attempts and various scores
    scores = {
        "ch10_light.reflection_laws":   45.0,
        "ch10_light.refraction":        30.0,
        "ch12_electricity.ohms_law":    55.0,
        "ch12_electricity.resistance":  25.0,
        "ch13_magnetic_effects.field":  60.0,
    }
    attempts = {k: 4 for k in scores}
    _set_profile(tmp_db, topic_scores=scores, topic_attempts=attempts)

    from backend.analytics import get_weak_topics
    result = get_weak_topics(n=5)

    assert len(result) > 0, "Expected some weak topics"
    # Verify ascending sort
    for i in range(len(result) - 1):
        assert result[i]["score"] <= result[i + 1]["score"], (
            f"Topics not sorted ascending: {result[i]['score']} > {result[i+1]['score']}"
        )


# ── Test 44 ──────────────────────────────────────────────────────────────────

def test_get_untested_topics_returns_all_when_no_attempts(tmp_db):
    """get_untested_topics() returns all syllabus topics when profile has no attempts."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    # No topic attempts in profile
    _set_profile(tmp_db, topic_scores={}, topic_attempts={})

    from backend.analytics import get_untested_topics
    result = get_untested_topics()

    assert len(result) > 0, "Expected untested topics when no attempts"

    # Load actual syllabus topic count
    syllabus_path = Path(__file__).parent.parent.parent / "data" / "config" / "syllabus.json"
    syllabus = json.loads(syllabus_path.read_text(encoding="utf-8"))
    total_topics = sum(len(c.get("topics", [])) for c in syllabus.get("chapters", []))

    assert len(result) == total_topics, (
        f"Expected {total_topics} untested topics, got {len(result)}"
    )


# ── Test 45 ──────────────────────────────────────────────────────────────────

def test_get_chapter_performance_has_all_13_chapters(tmp_db):
    """get_chapter_performance() returns dict with all 13 chapter IDs."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    from backend.analytics import get_chapter_performance

    result = get_chapter_performance()

    expected_chapters = {
        "ch01_chemical_reactions", "ch02_acids_bases_salts",
        "ch03_metals_non_metals", "ch04_carbon_compounds",
        "ch05_life_processes", "ch06_control_coordination",
        "ch07_reproduction", "ch08_heredity",
        "ch10_light", "ch11_human_eye",
        "ch12_electricity", "ch13_magnetic_effects",
        "ch15_our_environment",
    }
    missing = expected_chapters - set(result.keys())
    assert missing == set(), f"Chapter performance missing chapters: {missing}"


# ── Bonus ─────────────────────────────────────────────────────────────────────

def test_exam_readiness_score_range(tmp_db):
    """Exam readiness score is in range [0, 84]."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    from backend.analytics import get_exam_readiness
    r = get_exam_readiness()
    assert 0 <= r["score"] <= 84, f"Score {r['score']} out of range [0, 84]"


def test_get_weak_topics_empty_when_no_qualified_data(tmp_db):
    """get_weak_topics() returns empty list when no topic has >= 3 attempts."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _set_profile(tmp_db, topic_scores={"ch10_light.reflection": 50.0},
                 topic_attempts={"ch10_light.reflection": 2})

    from backend.analytics import get_weak_topics
    result = get_weak_topics()
    assert result == [], f"Expected empty list, got {result}"
