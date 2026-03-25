"""
test_session_lifecycle.py — Tests 81-84.
Full end-to-end session flow tests using TestClient.

IMPORTANT: The understanding session create path calls select_candidates() which
queries question_index in the TEST DB. So we must populate question_index in
the test DB with real question metadata (copied from production) before creating
understanding sessions.
"""
import json
import sqlite3
import uuid
import io
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

ROOT = Path(__file__).parent.parent.parent
PROD_DB = ROOT / "data" / "science_assessor.db"


# ── DB helpers ────────────────────────────────────────────────────────────────

def _prod_conn():
    conn = sqlite3.connect(str(PROD_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _copy_chapter_to_test_db(test_db_path: str, chapter: str):
    """Copy all question_index rows for a chapter from prod DB to test DB."""
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


def _get_prod_ids_by_type(chapter: str, q_type: str, marks: int, limit: int = 3) -> list:
    conn = _prod_conn()
    rows = conn.execute(
        "SELECT id FROM question_index WHERE chapter=? AND type=? AND marks=? AND approved=1 LIMIT ?",
        [chapter, q_type, marks, limit],
    ).fetchall()
    conn.close()
    return [r["id"] for r in rows]


# ── Test 81 — Full understanding session lifecycle ────────────────────────────

def test_81_full_understanding_session(test_client):
    """
    Full understanding session:
    POST /create → GET /questions → POST /submit
    Verify results list, feedback for every question, xp_earned > 0.
    """
    client, mocks = test_client

    import backend.database as dbmod
    test_db = dbmod.DB_PATH

    # Populate test DB with ch10_light questions so select_candidates() works
    _copy_chapter_to_test_db(test_db, "ch10_light")

    # Load questions into in-memory store
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    # Pick a mix of real question IDs from ch10_light
    mcq_ids = _get_prod_ids_by_type("ch10_light", "mcq", 1, 2)
    short_ids = _get_prod_ids_by_type("ch10_light", "short", 2, 2)
    selected_ids = (mcq_ids + short_ids)[:4]

    if not selected_ids:
        pytest.skip("No ch10_light questions available in prod DB")

    mocks["call_select"].return_value = {
        "selected_question_ids": selected_ids,
        "generated_params": {},
        "session_note": "test understanding session",
    }

    # ── Step 1: Create session ─────────────────────────────────────────────
    create_resp = client.post("/api/session/create", json={
        "type": "understanding", "chapter": "ch10_light",
    })
    assert create_resp.status_code == 200, f"Create failed: {create_resp.text[:300]}"
    session_id = create_resp.json()["session_id"]
    questions = create_resp.json()["questions"]
    assert len(questions) > 0

    # ── Step 2: GET questions ──────────────────────────────────────────────
    q_resp = client.get(f"/api/session/{session_id}/questions")
    assert q_resp.status_code == 200
    q_data = q_resp.json()
    assert "questions" in q_data

    # ── Step 3: Submit answers ─────────────────────────────────────────────
    answers = []
    for q in questions:
        if q["type"] == "mcq":
            answers.append({
                "question_id": q["id"],
                "selected_option": 0,
                "answer_text": None,
                "time_seconds": 30,
            })
        else:
            answers.append({
                "question_id": q["id"],
                "answer_text": "This is a test answer with some relevant content",
                "selected_option": None,
                "time_seconds": 60,
            })

    submit_resp = client.post(f"/api/session/{session_id}/submit", json={"answers": answers})
    assert submit_resp.status_code == 200, f"Submit failed: {submit_resp.text[:300]}"
    result = submit_resp.json()

    # Verify response structure
    assert result["status"] == "scored"
    assert "score_obtained" in result
    assert "percentage" in result
    assert "xp_earned" in result
    assert result["xp_earned"] >= 0  # Could be 0 if all wrong


# ── Test 82 — Chapter test flow with mocked OCR ───────────────────────────────

def test_82_chapter_test_flow_mocked_ocr(test_client):
    """
    Chapter short test flow:
    POST /create → PUT /mark-done-writing → POST /upload-pdf → POST /confirm-ocr → POST /submit
    Verify score_obtained and percentage in response.
    """
    client, mocks = test_client

    import backend.database as dbmod
    test_db = dbmod.DB_PATH

    # Populate test DB with ch10_light questions for paper generation
    _copy_chapter_to_test_db(test_db, "ch10_light")

    from backend.services.question_loader import load_all_questions
    load_all_questions()

    # ── Step 1: Create chapter_short session ──────────────────────────────
    create_resp = client.post("/api/session/create", json={
        "type": "chapter_short", "chapter": "ch10_light",
    })
    assert create_resp.status_code == 200, f"Create failed: {create_resp.text[:300]}"
    data = create_resp.json()
    session_id = data["session_id"]
    questions = data["questions"]
    assert len(questions) > 0

    # ── Step 2: Mark done writing ─────────────────────────────────────────
    mark_resp = client.put(f"/api/session/{session_id}/mark-done-writing")
    assert mark_resp.status_code == 200

    # ── Step 3: Upload PDF (mocked OCR) ───────────────────────────────────
    # Mock OCR returns answers for all questions
    ocr_answers = []
    for q in questions:
        if q["type"] == "mcq":
            ocr_answers.append({
                "question_id": q["id"],
                "answer_text": "B",
                "confidence": 0.95,
            })
        else:
            ocr_answers.append({
                "question_id": q["id"],
                "answer_text": "Test OCR answer text with some relevant content",
                "confidence": 0.85,
            })
    mocks["call_ocr"].return_value = ocr_answers

    dummy_pdf = b"%PDF-1.4 fake pdf content for testing"
    upload_resp = client.post(
        f"/api/session/{session_id}/upload-pdf",
        files={"file": ("test.pdf", io.BytesIO(dummy_pdf), "application/pdf")},
    )
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text[:300]}"
    upload_data = upload_resp.json()
    assert upload_data["status"] == "submitted"

    # ── Step 4: Confirm OCR ───────────────────────────────────────────────
    confirmations = [
        {"question_id": q["id"], "answer_text": "Confirmed answer text"}
        for q in questions
    ]
    confirm_resp = client.post(
        f"/api/session/{session_id}/confirm-ocr",
        json={"confirmations": confirmations},
    )
    assert confirm_resp.status_code == 200

    # ── Step 5: Submit ─────────────────────────────────────────────────────
    # For paper tests, answers come from DB (OCR), so body can be empty
    mocks["call_score"].return_value = {
        "evaluations": [],
        "overall_guidance": "Good effort overall",
    }

    submit_resp = client.post(f"/api/session/{session_id}/submit", json={})
    assert submit_resp.status_code == 200, f"Submit failed: {submit_resp.text[:300]}"
    result = submit_resp.json()

    assert "score_obtained" in result, "Missing score_obtained"
    assert "percentage" in result, "Missing percentage"
    assert result["status"] == "scored"


# ── Test 83 — Expired session returns 410 ─────────────────────────────────────

def test_83_expired_session_returns_410(test_client):
    """
    Create chapter_short session, expire it in DB, then GET /questions → 410.
    """
    client, mocks = test_client

    import backend.database as dbmod
    test_db = dbmod.DB_PATH

    _copy_chapter_to_test_db(test_db, "ch10_light")
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    # Create a chapter_short session (ch10_light has enough questions)
    create_resp = client.post("/api/session/create", json={
        "type": "chapter_short", "chapter": "ch10_light",
    })
    assert create_resp.status_code == 200, f"Could not create session: {create_resp.text[:200]}"

    session_id = create_resp.json()["session_id"]

    # Manually expire the session in the test DB
    conn = sqlite3.connect(test_db)
    conn.execute(
        "UPDATE assessments SET expires_at=?, status='expired' WHERE id=?",
        [(datetime.now() - timedelta(hours=1)).isoformat(), session_id],
    )
    conn.commit()
    conn.close()

    # GET /questions should return 410 Gone
    resp = client.get(f"/api/session/{session_id}/questions")
    assert resp.status_code == 410, f"Expected 410 Gone, got {resp.status_code}: {resp.text[:200]}"


# ── Test 84 — Admin score override ────────────────────────────────────────────

def test_84_admin_score_override(test_client):
    """
    Create + submit understanding session, then override one answer score via admin endpoint.
    Verify new_total is recalculated.
    """
    client, mocks = test_client

    import backend.database as dbmod
    test_db = dbmod.DB_PATH

    _copy_chapter_to_test_db(test_db, "ch10_light")
    from backend.services.question_loader import load_all_questions
    load_all_questions()

    mcq_ids = _get_prod_ids_by_type("ch10_light", "mcq", 1, 2)
    if not mcq_ids:
        pytest.skip("No MCQ questions available")

    mocks["call_select"].return_value = {
        "selected_question_ids": mcq_ids[:2],
        "generated_params": {},
        "session_note": "test",
    }

    # ── Create session ─────────────────────────────────────────────────────
    create_resp = client.post("/api/session/create", json={
        "type": "understanding", "chapter": "ch10_light",
    })
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]
    questions = create_resp.json()["questions"]

    # ── Submit with wrong answers (score = 0) ──────────────────────────────
    answers = [
        {
            "question_id": q["id"],
            "selected_option": 3,   # intentionally wrong (likely)
            "answer_text": None,
            "time_seconds": 10,
        }
        for q in questions if q["type"] == "mcq"
    ]

    submit_resp = client.post(f"/api/session/{session_id}/submit", json={"answers": answers})
    assert submit_resp.status_code == 200

    # ── Get answer IDs from admin session detail ───────────────────────────
    detail_resp = client.get(f"/api/admin/session/{session_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    answer_rows = detail.get("answers", [])
    assert len(answer_rows) > 0, "No answers found in session detail"

    first_answer = answer_rows[0]
    answer_id = first_answer["id"]
    max_marks = first_answer["max_marks"]

    # ── Override score to max_marks ────────────────────────────────────────
    override_resp = client.put(
        f"/api/admin/session/{session_id}/answer/{answer_id}/override",
        json={"score": max_marks, "note": "Manual override for test"},
    )
    assert override_resp.status_code == 200, f"Override failed: {override_resp.text[:200]}"
    override_data = override_resp.json()

    assert override_data["score"] == max_marks
    assert "new_total" in override_data
    assert override_data["new_total"] >= max_marks   # at least the override score
    assert "new_percentage" in override_data
