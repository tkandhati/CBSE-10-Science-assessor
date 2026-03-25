"""
test_gamification.py — Tests 46-65.
Tests XP, level, and badge functions from gamification.py.
Badge tests that need DB use tmp_db fixture.
"""
import json
import sqlite3
import uuid
import pytest
from datetime import datetime, timedelta

from backend.gamification import (
    calculate_xp,
    calculate_level,
    xp_in_current_level,
    xp_to_next_level,
    check_level_up,
    check_and_award_badges,
    BADGES,
)


# ── XP calculation ────────────────────────────────────────────────────────────

def test_46_xp_l1_full_marks():
    """calculate_xp(1, 1.0, 1.0) = 10 (L1 full marks)."""
    assert calculate_xp(1, 1.0, 1.0) == 10


def test_47_xp_l5_full_marks():
    """calculate_xp(5, 1.0, 1.0) = 75 (L5 full marks)."""
    assert calculate_xp(5, 1.0, 1.0) == 75


def test_48_xp_l2_half_marks():
    """calculate_xp(2, 1.0, 2.0) = 10 (50% of L2=20)."""
    result = calculate_xp(2, 1.0, 2.0)
    assert result == 10, f"Expected 10, got {result}"


def test_xp_proportional_partial():
    """XP is proportional for partial marks."""
    # L3=30, 1/3 correct
    result = calculate_xp(3, 1.0, 3.0)
    assert result == 10, f"Expected 10 (1/3 of 30), got {result}"


def test_xp_zero_max_marks():
    """calculate_xp with max_marks=0 returns 0."""
    assert calculate_xp(1, 0, 0) == 0


# ── Level calculation ─────────────────────────────────────────────────────────

def test_49_level_at_zero_xp():
    """calculate_level(0) = 1."""
    assert calculate_level(0) == 1


def test_50_level_at_499_xp():
    """calculate_level(499) = 1."""
    assert calculate_level(499) == 1


def test_51_level_at_500_xp():
    """calculate_level(500) = 2."""
    assert calculate_level(500) == 2


def test_52_level_at_1000_xp():
    """calculate_level(1000) = 3."""
    assert calculate_level(1000) == 3


def test_level_negative_xp_is_1():
    """Negative XP → level 1."""
    assert calculate_level(-100) == 1


# ── XP within level ───────────────────────────────────────────────────────────

def test_53_xp_in_current_level():
    """xp_in_current_level values."""
    assert xp_in_current_level(0) == 0
    assert xp_in_current_level(499) == 499
    assert xp_in_current_level(500) == 0


def test_54_xp_to_next_level():
    """xp_to_next_level values."""
    assert xp_to_next_level(0) == 500
    assert xp_to_next_level(499) == 1
    assert xp_to_next_level(500) == 500


# ── Level up check ────────────────────────────────────────────────────────────

def test_55_check_level_up_crossing_threshold():
    """check_level_up(499, 500) = (True, 2)."""
    leveled_up, new_level = check_level_up(499, 500)
    assert leveled_up is True
    assert new_level == 2


def test_56_check_level_up_no_crossing():
    """check_level_up(0, 499) = (False, 1)."""
    leveled_up, new_level = check_level_up(0, 499)
    assert leveled_up is False
    assert new_level == 1


def test_check_level_up_same_xp():
    """check_level_up with same XP → no level up."""
    leveled_up, new_level = check_level_up(250, 250)
    assert leveled_up is False


# ── Badge helpers ─────────────────────────────────────────────────────────────

def _seed_profile(db_path: str, **kwargs):
    """Update student_profile in test DB with given field values."""
    conn = sqlite3.connect(db_path)
    defaults = {
        "total_xp": 0, "current_streak": 0, "best_streak": 0,
        "badges": "[]", "topic_scores": "{}",
    }
    defaults.update(kwargs)
    conn.execute(
        """UPDATE student_profile SET
           total_xp=?, current_streak=?, best_streak=?, badges=?
           WHERE id=1""",
        [defaults["total_xp"], defaults["current_streak"],
         defaults["best_streak"], defaults["badges"]],
    )
    conn.commit()
    conn.close()


def _get_badges(db_path: str) -> set:
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT badges FROM student_profile WHERE id=1").fetchone()
    conn.close()
    return set(json.loads(row[0] or "[]")) if row else set()


def _make_session(db_path: str, sess_type: str = "understanding",
                  chapter: str = "ch10_light", percentage: float = 100.0,
                  status: str = "scored", n_answers: int = 0) -> str:
    """Insert a session and optional answers into test DB."""
    conn = sqlite3.connect(db_path)
    sess_id = f"asmt_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO assessments
           (id, type, chapter, topic, question_ids, total_marks, score_obtained, percentage,
            status, started_at, is_active)
           VALUES (?,?,?,?,?,?,?,?,?,?,0)""",
        [sess_id, sess_type, chapter, None, "[]",
         100, percentage, percentage, status, now],
    )
    # Insert dummy answers
    for i in range(n_answers):
        qid = f"dummy_q_{i}"
        ans_id = f"ans_{uuid.uuid4().hex[:8]}"
        # Ensure question_index row exists
        conn.execute(
            """INSERT OR IGNORE INTO question_index
               (id, chapter, topic, type, difficulty, marks, approved)
               VALUES (?,?,?,?,?,?,1)""",
            [qid, chapter, "general", "mcq", 1, 1],
        )
        conn.execute(
            """INSERT INTO answers
               (id, assessment_id, question_id, score, max_marks, is_correct)
               VALUES (?,?,?,?,?,1)""",
            [ans_id, sess_id, qid, 1, 1],
        )
    conn.commit()
    conn.close()
    return sess_id


def _profile_dict(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM student_profile WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}


# ── Test 57 ──────────────────────────────────────────────────────────────────

def test_57_first_perfect_badge_awarded_on_first_100_percent(tmp_db):
    """first_perfect badge awarded on first 100% session."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, percentage=100.0, status="scored")

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=50, percentage=100.0,
    )
    assert "first_perfect" in new_badges, f"Expected first_perfect in {new_badges}"


# ── Test 58 ──────────────────────────────────────────────────────────────────

def test_58_first_perfect_not_awarded_if_already_earned(tmp_db):
    """first_perfect badge NOT awarded if already earned."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges='["first_perfect"]')
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, percentage=100.0, status="scored")

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=100, percentage=100.0,
    )
    assert "first_perfect" not in new_badges, "Should not re-award first_perfect"


# ── Test 59 ──────────────────────────────────────────────────────────────────

def test_59_streak_7_badge_awarded(tmp_db):
    """streak_7 badge awarded when current_streak >= 7."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, percentage=70.0, status="scored")

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=7, total_xp_new=100, percentage=70.0,
    )
    assert "streak_7" in new_badges, f"Expected streak_7 in {new_badges}"


# ── Test 60 ──────────────────────────────────────────────────────────────────

def test_60_century_badge_awarded_at_100_answers(tmp_db):
    """century badge awarded when answers table count >= 100."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")

    # Insert 100 dummy answers
    sess_id = _make_session(tmp_db, percentage=80.0, status="scored", n_answers=100)
    profile = _profile_dict(tmp_db)

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=200, percentage=80.0,
    )
    assert "century" in new_badges, f"Expected century in {new_badges}"


# ── Test 61 ──────────────────────────────────────────────────────────────────

def test_61_chapter_master_badge_for_chapter_regular_80_percent(tmp_db):
    """chapter_master_ch12_electricity badge awarded for chapter_regular with >=80%."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, sess_type="chapter_regular",
                            chapter="ch12_electricity", percentage=82.0, status="scored")

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="chapter_regular",
        chapter="ch12_electricity", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=100, percentage=82.0,
    )
    assert "chapter_master_ch12_electricity" in new_badges, (
        f"Expected chapter_master_ch12_electricity in {new_badges}."
    )


# ── Test 62 ──────────────────────────────────────────────────────────────────

def test_62_board_ready_badge_for_mock_70_percent(tmp_db):
    """board_ready badge awarded for mock session with >= 70%."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, sess_type="mock", chapter="all",
                            percentage=75.0, status="scored")

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="mock",
        chapter="all", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=500, percentage=75.0,
    )
    assert "board_ready" in new_badges, f"Expected board_ready in {new_badges}"


# ── Test 63 ──────────────────────────────────────────────────────────────────

def test_63_speed_demon_badge_under_480s_80_percent(tmp_db):
    """speed_demon badge awarded for understanding < 480s with >= 80%."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, sess_type="understanding",
                            chapter="ch10_light", percentage=85.0, status="scored")

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=100, percentage=85.0,
        duration_seconds=300,  # 5 minutes — well under 8 min
    )
    assert "speed_demon" in new_badges, f"Expected speed_demon in {new_badges}"


# ── Test 64 ──────────────────────────────────────────────────────────────────

def test_64_comeback_kid_badge_topic_crosses_threshold(tmp_db):
    """comeback_kid badge awarded when a topic moves from <50% to >70%."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, percentage=80.0, status="scored")

    before = {"ch10_light.reflection_laws": 40.0}
    after  = {"ch10_light.reflection_laws": 75.0}

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile, topic_scores_before=before, topic_scores_after=after,
        current_streak=1, total_xp_new=100, percentage=80.0,
    )
    assert "comeback_kid" in new_badges, f"Expected comeback_kid in {new_badges}"


# ── Test 65 ──────────────────────────────────────────────────────────────────

def test_65_badge_check_idempotent(tmp_db):
    """Running check_and_award_badges twice for same session doesn't double-award."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, percentage=100.0, status="scored")

    # First call
    new_badges_1 = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=50, percentage=100.0,
    )
    assert "first_perfect" in new_badges_1

    # Second call — same session, updated profile
    profile2 = _profile_dict(tmp_db)
    new_badges_2 = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile2, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=50, percentage=100.0,
    )
    # Should not award first_perfect again
    assert "first_perfect" not in new_badges_2, "Badge awarded twice — not idempotent"


# ── Badge catalog checks ──────────────────────────────────────────────────────

def test_badges_dict_has_expected_entries():
    """BADGES dict contains expected badge IDs for all 13 chapters."""
    expected = {
        "first_perfect", "streak_7", "streak_30", "century",
        "chapter_master_ch01_chemical_reactions",
        "chapter_master_ch02_acids_bases_salts",
        "chapter_master_ch03_metals_non_metals",
        "chapter_master_ch04_carbon_compounds",
        "chapter_master_ch05_life_processes",
        "chapter_master_ch06_control_coordination",
        "chapter_master_ch07_reproduction",
        "chapter_master_ch08_heredity",
        "chapter_master_ch10_light",
        "chapter_master_ch11_human_eye",
        "chapter_master_ch12_electricity",
        "chapter_master_ch13_magnetic_effects",
        "chapter_master_ch15_our_environment",
        "board_ready", "speed_demon", "comeback_kid",
    }
    assert set(BADGES.keys()) == expected, f"BADGES mismatch: {set(BADGES.keys()) ^ expected}"


def test_speed_demon_not_awarded_when_too_slow(tmp_db):
    """speed_demon badge NOT awarded when duration > 480s."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, percentage=90.0, status="scored")

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="understanding",
        chapter="ch10_light", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=100, percentage=90.0,
        duration_seconds=600,  # 10 minutes — over limit
    )
    assert "speed_demon" not in new_badges


def test_board_ready_not_awarded_below_70_percent(tmp_db):
    """board_ready badge NOT awarded for mock with < 70%."""
    import backend.database as dbmod
    dbmod.DB_PATH = tmp_db

    _seed_profile(tmp_db, badges="[]")
    profile = _profile_dict(tmp_db)
    sess_id = _make_session(tmp_db, sess_type="mock", chapter="all",
                            percentage=65.0, status="scored")

    new_badges = check_and_award_badges(
        session_id=sess_id, sess_type="mock",
        chapter="all", answers_data=[],
        profile=profile, topic_scores_before={}, topic_scores_after={},
        current_streak=1, total_xp_new=200, percentage=65.0,
    )
    assert "board_ready" not in new_badges
