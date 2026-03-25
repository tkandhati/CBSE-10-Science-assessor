"""
conftest.py — shared fixtures for all backend tests.

Key design decisions:
- tmp_db patches backend.database.DB_PATH BEFORE importing the app (module reload).
- All Claude API calls are mocked so no network calls occur.
- test_client loads questions from the real JSON files (read-only).
"""
import sys
import json
import importlib
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Fake Claude response templates
# ---------------------------------------------------------------------------

MOCK_SELECT_RESPONSE = {
    "selected_question_ids": [],   # filled dynamically per-test
    "generated_params": {},
    "session_note": "test selection",
}

MOCK_OCR_RESPONSE = []   # filled per test

MOCK_EVAL_RESPONSE = {
    "evaluations": [],
    "overall_guidance": "Good work",
}

MOCK_GUIDANCE_RESPONSE = {
    "priority_topics": [],
    "recommended_sequence": [],
    "exam_readiness_projection": {
        "current_score": 50.0,
        "target_score": 70.0,
        "marks_recoverable": 10.0,
        "what_if": "Practice more",
    },
}


# ---------------------------------------------------------------------------
# tmp_db fixture — isolated SQLite database for each test
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """
    Create a fresh SQLite database at a temp path.
    Patches backend.database.DB_PATH so every get_db() call uses the test DB.
    Returns the string path to the test DB file.
    """
    db_path = str(tmp_path / "test.db")

    # Must patch BEFORE importing any module that calls get_db() at import time.
    import backend.database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", db_path)
    dbmod.init_db()

    yield db_path

    # Restore is handled by monkeypatch automatically.


# ---------------------------------------------------------------------------
# test_client fixture — FastAPI test client with mocked AI + test DB
# ---------------------------------------------------------------------------

@pytest.fixture
def test_client(tmp_db):
    """
    FastAPI TestClient with:
    - Test (temporary) database
    - All Claude API calls mocked
    - Questions loaded from real JSON files
    """
    # Import AFTER DB_PATH is patched.
    from starlette.testclient import TestClient
    from backend.services.question_loader import load_all_questions

    with patch("backend.services.ai_client.call_1_select_questions") as m1, \
         patch("backend.services.ai_client.call_1_ocr_pdf") as m2, \
         patch("backend.services.ai_client.call_2_evaluate_subjective") as m3, \
         patch("backend.services.ai_client.call_2_score_and_guide") as m4, \
         patch("backend.services.ai_client.call_guidance") as m5:

        m1.return_value = MOCK_SELECT_RESPONSE.copy()
        m2.return_value = []
        m3.return_value = []
        m4.return_value = MOCK_EVAL_RESPONSE.copy()
        m5.return_value = MOCK_GUIDANCE_RESPONSE.copy()

        from backend.main import app

        # Load questions into in-memory store
        load_all_questions()

        client = TestClient(app, raise_server_exceptions=True)

        yield client, {
            "call_select": m1,
            "call_ocr":    m2,
            "call_eval":   m3,
            "call_score":  m4,
            "call_guidance": m5,
        }


# ---------------------------------------------------------------------------
# Helper: insert minimal question_index rows into test DB
# ---------------------------------------------------------------------------

def insert_test_questions(db_path: str, chapter: str, questions: list[dict]):
    """
    Insert rows into question_index for paper-generation tests that need
    a populated test DB.
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    for q in questions:
        conn.execute(
            """INSERT OR REPLACE INTO question_index
               (id, chapter, topic, type, difficulty, marks, board_weightage,
                approved, times_served, has_template)
               VALUES (?,?,?,?,?,?,?,1,0,0)""",
            [
                q["id"], chapter, q.get("topic", "general"),
                q["type"], q.get("difficulty", 2), q["marks"],
                q.get("board_weightage", 1.0),
            ],
        )
    conn.commit()
    conn.close()
