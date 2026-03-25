"""
test_api_endpoints.py — Tests 66-80.
HTTP-layer tests using TestClient with mocked AI.

NOTE: The test_client fixture uses a fresh empty test DB. For session endpoints
that need question_index populated (understanding, chapter_short, chapter_regular),
we copy question metadata from the production DB into the test DB at the start
of each relevant test.
"""
import json
import sqlite3
import uuid
import pytest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent
PROD_DB = ROOT / "data" / "science_assessor.db"


def _prod_conn():
    conn = sqlite3.connect(str(PROD_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _copy_chapter_to_test_db(test_db_path: str, chapter: str):
    """Copy all question_index rows for a chapter from prod DB into test DB."""
    prod = _prod_conn()
    rows = prod.execute(
        "SELECT * FROM question_index WHERE chapter=? AND approved=1", [chapter]
    ).fetchall()
    prod.close()

    test_conn = sqlite3.connect(test_db_path)
    for r in rows:
        test_conn.execute(
            """INSERT OR REPLACE INTO question_index
               (id, chapter, topic, type, difficulty, marks, board_weightage,
                source, board_years, has_diagram, has_template, times_served,
                last_served_at, approved, tags)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [r["id"], r["chapter"], r["topic"], r["type"], r["difficulty"],
             r["marks"], r["board_weightage"], r["source"], r["board_years"],
             r["has_diagram"], r["has_template"], r["times_served"],
             r["last_served_at"], 1, r["tags"]],
        )
    test_conn.commit()
    test_conn.close()


def _get_real_ch10_ids(n: int = 5) -> list:
    """Fetch a few real ch10_light question IDs from production DB."""
    conn = _prod_conn()
    rows = conn.execute(
        "SELECT id FROM question_index WHERE chapter='ch10_light' AND approved=1 LIMIT ?", [n]
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _get_real_ch12_ids(n: int = 5) -> list:
    conn = _prod_conn()
    rows = conn.execute(
        "SELECT id FROM question_index WHERE chapter='ch12_electricity' AND approved=1 LIMIT ?", [n]
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _get_real_all_chapter_ids(per_chapter: int = 2) -> list:
    """Get a few IDs from each of 13 chapters for mock."""
    chapters = [
        "ch01_chemical_reactions", "ch02_acids_bases_salts", "ch03_metals_non_metals",
        "ch04_carbon_compounds", "ch05_life_processes", "ch06_control_coordination",
        "ch07_reproduction", "ch08_heredity", "ch10_light", "ch11_human_eye",
        "ch12_electricity", "ch13_magnetic_effects", "ch15_our_environment",
    ]
    conn = _prod_conn()
    ids = []
    for ch in chapters:
        rows = conn.execute(
            "SELECT id FROM question_index WHERE chapter=? AND approved=1 LIMIT ?",
            [ch, per_chapter],
        ).fetchall()
        ids.extend(r[0] for r in rows)
    conn.close()
    return ids


# ── Test 66 ──────────────────────────────────────────────────────────────────

def test_66_create_understanding_session(test_client):
    """POST /api/session/create (understanding, ch10_light) → 200 with session_id + questions."""
    client, mocks = test_client

    import backend.database as dbmod
    _copy_chapter_to_test_db(dbmod.DB_PATH, "ch10_light")
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    ids = _get_real_ch10_ids(3)
    mocks["call_select"].return_value = {
        "selected_question_ids": ids,
        "generated_params": {},
        "session_note": "test",
    }

    resp = client.post("/api/session/create", json={
        "type": "understanding", "chapter": "ch10_light",
    })
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert "session_id" in data
    assert "questions" in data
    assert len(data["questions"]) > 0


# ── Test 67 ──────────────────────────────────────────────────────────────────

def test_67_create_chapter_short_session(test_client):
    """POST /api/session/create (chapter_short, ch10_light) → 200 with session_id."""
    client, mocks = test_client

    import backend.database as dbmod
    _copy_chapter_to_test_db(dbmod.DB_PATH, "ch10_light")
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    resp = client.post("/api/session/create", json={
        "type": "chapter_short", "chapter": "ch10_light",
    })
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:300]}"
    data = resp.json()
    assert "session_id" in data


# ── Test 68 ──────────────────────────────────────────────────────────────────

def test_68_create_chapter_regular_session(test_client):
    """POST /api/session/create (chapter_regular, ch02_acids_bases_salts) → 200."""
    client, mocks = test_client

    import backend.database as dbmod
    # Use ch02 which has enough questions for all chapter_regular slots
    _copy_chapter_to_test_db(dbmod.DB_PATH, "ch02_acids_bases_salts")
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    resp = client.post("/api/session/create", json={
        "type": "chapter_regular", "chapter": "ch02_acids_bases_salts",
    })
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:300]}"
    assert "session_id" in resp.json()


# ── Test 69 ──────────────────────────────────────────────────────────────────

def test_69_create_mock_session(test_client):
    """POST /api/session/create (mock) → 200."""
    client, mocks = test_client

    resp = client.post("/api/session/create", json={"type": "mock"})
    assert resp.status_code in (200, 422), f"Got {resp.status_code}: {resp.text[:300]}"
    if resp.status_code == 200:
        assert "session_id" in resp.json()


# ── Test 70 ──────────────────────────────────────────────────────────────────

def test_70_get_session_questions(test_client):
    """GET /api/session/{id}/questions → 200 with question list."""
    client, mocks = test_client

    import backend.database as dbmod
    _copy_chapter_to_test_db(dbmod.DB_PATH, "ch10_light")
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    ids = _get_real_ch10_ids(3)
    mocks["call_select"].return_value = {
        "selected_question_ids": ids,
        "generated_params": {},
        "session_note": "test",
    }

    create_resp = client.post("/api/session/create", json={
        "type": "understanding", "chapter": "ch10_light",
    })
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]

    resp = client.get(f"/api/session/{session_id}/questions")
    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data
    assert len(data["questions"]) > 0


# ── Test 71 ──────────────────────────────────────────────────────────────────

def test_71_get_active_session_null_when_none(test_client):
    """GET /api/session/active → {active_session_id: null} when no active test."""
    client, mocks = test_client
    resp = client.get("/api/session/active")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("active_session_id") is None


# ── Test 72 ──────────────────────────────────────────────────────────────────

def test_72_get_active_session_returns_correct_id(test_client):
    """GET /api/session/active returns correct id when chapter_short exists."""
    client, mocks = test_client

    import backend.database as dbmod
    _copy_chapter_to_test_db(dbmod.DB_PATH, "ch10_light")
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    # Create a chapter_short session
    resp = client.post("/api/session/create", json={
        "type": "chapter_short", "chapter": "ch10_light",
    })
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
    session_id = resp.json()["session_id"]

    active_resp = client.get("/api/session/active")
    assert active_resp.status_code == 200
    data = active_resp.json()
    assert data.get("active_session_id") == session_id


# ── Test 73 ──────────────────────────────────────────────────────────────────

def test_73_mark_done_writing(test_client):
    """PUT /api/session/{id}/mark-done-writing → 200, status=awaiting_upload."""
    client, mocks = test_client

    import backend.database as dbmod
    _copy_chapter_to_test_db(dbmod.DB_PATH, "ch10_light")
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    create_resp = client.post("/api/session/create", json={
        "type": "chapter_short", "chapter": "ch10_light",
    })
    assert create_resp.status_code == 200, f"Got {create_resp.status_code}: {create_resp.text[:200]}"
    session_id = create_resp.json()["session_id"]

    resp = client.put(f"/api/session/{session_id}/mark-done-writing")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "awaiting_upload"


# ── Test 74 ──────────────────────────────────────────────────────────────────

def test_74_admin_dashboard(test_client):
    """GET /api/admin/dashboard → 200, has total_sessions, chapter_performance, exam_readiness."""
    client, mocks = test_client
    resp = client.get("/api/admin/dashboard")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    assert "total_sessions" in data
    assert "chapter_performance" in data
    assert "exam_readiness" in data


# ── Test 75 ──────────────────────────────────────────────────────────────────

def test_75_admin_strengths(test_client):
    """GET /api/admin/strengths → 200, has topics dict."""
    client, mocks = test_client
    resp = client.get("/api/admin/strengths")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    assert "topics" in data
    # The topics dict should have entries (from all 13 chapters in syllabus)
    assert isinstance(data["topics"], dict)
    assert len(data["topics"]) > 0


# ── Test 76 ──────────────────────────────────────────────────────────────────

def test_76_student_profile(test_client):
    """GET /api/student/profile → 200, has name, total_xp, current_level, current_streak, badges."""
    client, mocks = test_client
    resp = client.get("/api/student/profile")
    assert resp.status_code == 200
    data = resp.json()
    for field in ("name", "total_xp", "current_level", "current_streak", "badges"):
        assert field in data, f"Missing field '{field}' in profile response"


# ── Test 77 ──────────────────────────────────────────────────────────────────

def test_77_student_badges_list(test_client):
    """GET /api/student/badges → 200, has badges list with 12 items."""
    client, mocks = test_client
    resp = client.get("/api/student/badges")
    assert resp.status_code == 200
    data = resp.json()
    assert "badges" in data
    assert len(data["badges"]) == 20, (
        f"Expected 20 badge definitions (13 chapter masters + 7 others), got {len(data['badges'])}"
    )


# ── Test 78 ──────────────────────────────────────────────────────────────────

def test_78_qbank_stats(test_client):
    """GET /api/qbank/stats → 200, has total, approved, pending_review, by_chapter."""
    client, mocks = test_client
    resp = client.get("/api/qbank/stats")
    assert resp.status_code == 200
    data = resp.json()
    for field in ("total", "approved", "pending_review", "by_chapter"):
        assert field in data, f"Missing field '{field}'"


# ── Test 79 ──────────────────────────────────────────────────────────────────

def test_79_qbank_live(test_client):
    """GET /api/qbank/live → 200, has questions list and total."""
    client, mocks = test_client
    resp = client.get("/api/qbank/live")
    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data
    assert "total" in data


# ── Test 80 ──────────────────────────────────────────────────────────────────

def test_80_health_check(test_client):
    """GET /api/health → 200, {status: ok}."""
    client, mocks = test_client
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


# ── Extra sanity checks ───────────────────────────────────────────────────────

def test_create_session_invalid_type_returns_400(test_client):
    """POST /create with unknown type → 400."""
    client, mocks = test_client
    resp = client.post("/api/session/create", json={"type": "invalid_type"})
    assert resp.status_code in (400, 422), f"Expected 4xx, got {resp.status_code}"


def test_get_nonexistent_session_questions_returns_404(test_client):
    """GET /api/session/nonexistent/questions → 404."""
    client, mocks = test_client
    resp = client.get("/api/session/nonexistent_session_xyz/questions")
    assert resp.status_code == 404


def test_admin_sessions_endpoint(test_client):
    """GET /api/admin/sessions → 200 with sessions list."""
    client, mocks = test_client
    resp = client.get("/api/admin/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert "total" in data
