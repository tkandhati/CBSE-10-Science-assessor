"""
Gamification engine — XP, levels, streaks, achievement badges (Phase 6).
Shared by all session submit endpoints. All badge logic is here — never duplicated.
"""
import json
from backend.database import get_db

# ── XP ────────────────────────────────────────────────────────────────────────

LEVEL_XP   = {1: 10, 2: 20, 3: 30, 4: 50, 5: 75}
XP_PER_LEVEL = 500


def calculate_xp(difficulty: int, score: float, max_marks: float) -> int:
    """XP for one question: full XP if correct, proportional if partial."""
    base = LEVEL_XP.get(difficulty, 10)
    if max_marks <= 0:
        return 0
    ratio = score / max_marks
    if ratio >= 0.99:
        return base
    return int(base * ratio)


def calculate_level(total_xp: int) -> int:
    """Level = floor(total_xp / 500) + 1 (Level 1 at 0 XP)."""
    return max(1, (max(0, total_xp) // XP_PER_LEVEL) + 1)


def xp_in_current_level(total_xp: int) -> int:
    """XP accumulated within the current level (0–499)."""
    return max(0, total_xp) % XP_PER_LEVEL


def xp_to_next_level(total_xp: int) -> int:
    """XP still needed to reach the next level."""
    return XP_PER_LEVEL - xp_in_current_level(total_xp)


def check_level_up(old_xp: int, new_xp: int) -> tuple:
    """Returns (leveled_up: bool, new_level: int)."""
    old_level = calculate_level(old_xp)
    new_level = calculate_level(new_xp)
    return new_level > old_level, new_level


# ── Badges ────────────────────────────────────────────────────────────────────

BADGES: dict = {
    "first_perfect": {
        "id": "first_perfect", "name": "First Perfect",
        "description": "Scored 100% on a session for the first time",
        "icon": "⭐",
    },
    "streak_7": {
        "id": "streak_7", "name": "Week Warrior",
        "description": "Maintained a 7-day study streak",
        "icon": "🔥",
    },
    "streak_30": {
        "id": "streak_30", "name": "Monthly Master",
        "description": "Maintained a 30-day study streak",
        "icon": "🏆",
    },
    "century": {
        "id": "century", "name": "Century",
        "description": "Answered 100 questions in total",
        "icon": "💯",
    },
    "chapter_master_ch01_chemical_reactions": {
        "id": "chapter_master_ch01_chemical_reactions", "name": "Reaction Master",
        "description": "Scored ≥80% on a Regular Chapter Test for Chemical Reactions",
        "icon": "⚗️",
    },
    "chapter_master_ch02_acids_bases_salts": {
        "id": "chapter_master_ch02_acids_bases_salts", "name": "pH Champion",
        "description": "Scored ≥80% on a Regular Chapter Test for Acids, Bases and Salts",
        "icon": "🧪",
    },
    "chapter_master_ch03_metals_non_metals": {
        "id": "chapter_master_ch03_metals_non_metals", "name": "Metals Expert",
        "description": "Scored ≥80% on a Regular Chapter Test for Metals and Non-Metals",
        "icon": "⚙️",
    },
    "chapter_master_ch04_carbon_compounds": {
        "id": "chapter_master_ch04_carbon_compounds", "name": "Carbon Master",
        "description": "Scored ≥80% on a Regular Chapter Test for Carbon Compounds",
        "icon": "🔗",
    },
    "chapter_master_ch05_life_processes": {
        "id": "chapter_master_ch05_life_processes", "name": "Life Sciences Pro",
        "description": "Scored ≥80% on a Regular Chapter Test for Life Processes",
        "icon": "🌱",
    },
    "chapter_master_ch06_control_coordination": {
        "id": "chapter_master_ch06_control_coordination", "name": "Neuro Champion",
        "description": "Scored ≥80% on a Regular Chapter Test for Control and Coordination",
        "icon": "🧠",
    },
    "chapter_master_ch07_reproduction": {
        "id": "chapter_master_ch07_reproduction", "name": "Biology Expert",
        "description": "Scored ≥80% on a Regular Chapter Test for Reproduction",
        "icon": "🧬",
    },
    "chapter_master_ch08_heredity": {
        "id": "chapter_master_ch08_heredity", "name": "Genetics Guru",
        "description": "Scored ≥80% on a Regular Chapter Test for Heredity and Evolution",
        "icon": "🔬",
    },
    "chapter_master_ch10_light": {
        "id": "chapter_master_ch10_light", "name": "Light Master",
        "description": "Scored ≥80% on a Regular Chapter Test for Light",
        "icon": "💡",
    },
    "chapter_master_ch11_human_eye": {
        "id": "chapter_master_ch11_human_eye", "name": "Optics Expert",
        "description": "Scored ≥80% on a Regular Chapter Test for Human Eye",
        "icon": "👁",
    },
    "chapter_master_ch12_electricity": {
        "id": "chapter_master_ch12_electricity", "name": "Circuit Champion",
        "description": "Scored ≥80% on a Regular Chapter Test for Electricity",
        "icon": "⚡",
    },
    "chapter_master_ch13_magnetic_effects": {
        "id": "chapter_master_ch13_magnetic_effects", "name": "Magnetic Marvel",
        "description": "Scored ≥80% on a Regular Chapter Test for Magnetic Effects",
        "icon": "🧲",
    },
    "chapter_master_ch15_our_environment": {
        "id": "chapter_master_ch15_our_environment", "name": "Eco Champion",
        "description": "Scored ≥80% on a Regular Chapter Test for Our Environment",
        "icon": "🌍",
    },
    "board_ready": {
        "id": "board_ready", "name": "Board Ready",
        "description": "Scored ≥70% on a Full Mock Test",
        "icon": "🎓",
    },
    "speed_demon": {
        "id": "speed_demon", "name": "Speed Demon",
        "description": "Finished an Understanding Session under 8 min with ≥80% score",
        "icon": "⚡",
    },
    "comeback_kid": {
        "id": "comeback_kid", "name": "Comeback Kid",
        "description": "Improved any topic from below 50% to above 70%",
        "icon": "📈",
    },
}


def check_and_award_badges(
    session_id: str,
    sess_type: str,
    chapter: str,
    answers_data: list,
    profile: dict,
    topic_scores_before: dict,
    topic_scores_after: dict,
    current_streak: int,
    total_xp_new: int,
    percentage: float,
    duration_seconds: int = 0,
) -> list:
    """
    Check all 8 badge categories. Award any not yet earned.
    Idempotent — checking twice never double-awards.
    Returns list of newly awarded badge IDs.
    """
    conn = get_db()
    existing_badges: set = set(json.loads(profile.get("badges") or "[]"))
    new_badges: list = []

    def _award(badge_id: str):
        if badge_id not in existing_badges and badge_id in BADGES:
            existing_badges.add(badge_id)
            new_badges.append(badge_id)

    # 1. First Perfect — 100% on THIS session AND no prior 100% session
    if percentage >= 100.0:
        prior = conn.execute(
            "SELECT COUNT(*) FROM assessments "
            "WHERE percentage >= 100.0 AND id != ? AND status='scored'",
            (session_id,),
        ).fetchone()[0]
        if prior == 0:
            _award("first_perfect")

    # 2 & 3. Streak milestones
    if current_streak >= 7:
        _award("streak_7")
    if current_streak >= 30:
        _award("streak_30")

    # 4. Century — total answers across ALL sessions
    total_answered = conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    if total_answered >= 100:
        _award("century")

    # 5. Chapter Master (chapter_regular only, ≥80%)
    if sess_type == "chapter_regular" and percentage >= 80.0:
        badge_id = f"chapter_master_{chapter}"
        _award(badge_id)

    # 6. Board Ready — mock ≥70%
    if sess_type == "mock" and percentage >= 70.0:
        _award("board_ready")

    # 7. Speed Demon — understanding session < 8 min (480 s) and ≥80%
    if sess_type == "understanding" and percentage >= 80.0 and 0 < duration_seconds <= 480:
        _award("speed_demon")

    # 8. Comeback Kid — any topic moves from <50% to >70%
    for topic_key, after_score in topic_scores_after.items():
        before_score = topic_scores_before.get(topic_key)
        if before_score is not None and before_score < 50.0 and after_score > 70.0:
            _award("comeback_kid")
            break

    # Persist if any new badges were awarded
    if new_badges:
        conn.execute(
            "UPDATE student_profile SET badges=? WHERE id=1",
            (json.dumps(list(existing_badges)),),
        )
        conn.commit()
    conn.close()
    return new_badges
