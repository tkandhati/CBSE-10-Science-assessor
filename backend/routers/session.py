"""
Session lifecycle endpoints (TDD Section 7.3.1).

Phase 2: POST /create (understanding), GET /{id}/questions, POST /{id}/submit, GET /{id}/results
Phase 3: POST /create (chapter_short, chapter_regular), POST /{id}/upload-pdf,
         POST /{id}/confirm-ocr, PUT /{id}/mark-done-writing
"""
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.database import get_db
from backend.models import CreateSessionRequest, SubmitSessionRequest, ConfirmOCRRequest
from backend.services.question_loader import get_all, get_question
from backend.services.question_selector import select_candidates
from backend.services.paper_generator import (
    generate_test_paper, check_feasibility,
    check_mock_feasibility, generate_mock_paper,
)
from backend.services.numerical import generate_params
from backend.services.evaluator import evaluate_answer
from backend.services.profile_updater import update_profile, compute_exam_readiness
from backend.services.ai_client import (
    call_1_select_questions,
    call_1_ocr_pdf,
    call_2_score_and_guide,
)
from backend.gamification import check_and_award_badges, check_level_up, calculate_level

router = APIRouter(prefix="/api/session", tags=["session"])

_TEMPLATES_PATH = Path(__file__).parent.parent.parent / "data" / "config" / "test_templates.json"
_UPLOADS_DIR    = Path(__file__).parent.parent.parent / "data" / "uploads" / "answers"

CHAPTER_TEST_TYPES = {"chapter_short", "chapter_regular"}
PAPER_TEST_TYPES   = {"chapter_short", "chapter_regular", "mock"}

_MOCK_SECTION_INSTRUCTIONS = {
    "A": "Section A — Answer all questions. Each question carries 1 mark. (MCQ / Assertion-Reason)",
    "B": "Section B — Short Answer I. Each question carries 2 marks.",
    "C": "Section C — Short Answer II. Each question carries 3 marks.",
    "D": "Section D — Long Answer. Each question carries 5 marks.",
    "E": "Section E — Case-Based Questions. Each question carries 4 marks.",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_templates() -> dict:
    return json.loads(_TEMPLATES_PATH.read_text(encoding="utf-8"))["templates"]


def _get_profile() -> dict:
    conn = get_db()
    row = conn.execute("SELECT * FROM student_profile WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}


def _new_session_id() -> str:
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:4]
    return f"asmt_{ts}_{short}"


def _normalize_options(raw_options, rubric: dict) -> tuple[list, Optional[int]]:
    """
    Normalize options to list format and return (options_list, correct_index).

    Handles two formats:
      - List:  [{"text": "...", "is_correct": true}, ...]   — standard format
      - Dict:  {"A": "...", "B": "...", "C": "...", "D": "..."}  — legacy format
    """
    if not raw_options:
        return [], None

    if isinstance(raw_options, list):
        correct_index = next(
            (i for i, o in enumerate(raw_options) if isinstance(o, dict) and o.get("is_correct")),
            None,
        )
        return raw_options, correct_index

    if isinstance(raw_options, dict):
        # Legacy dict format — correct answer is the first key_point (e.g. "B")
        correct_key = ""
        kp = (rubric or {}).get("key_points") or []
        if kp:
            correct_key = str(kp[0]).strip().upper()
        keys = list(raw_options.keys())
        options_list = [
            {"text": raw_options[k], "is_correct": k.upper() == correct_key}
            for k in keys
        ]
        correct_index = next(
            (i for i, k in enumerate(keys) if k.upper() == correct_key),
            None,
        )
        return options_list, correct_index

    return [], None


def _build_question_out(qid: str, seq: int, question_store: dict,
                         meta: dict, gen_params: dict) -> Optional[dict]:
    q = question_store.get(qid)
    if not q:
        return None
    q_type = meta.get("type", "short")
    rubric = q.get("rubric") or {}

    options_list, correct_index = _normalize_options(q.get("options"), rubric)

    q_out: dict = {
        "id":               qid,
        "sequence":         seq,
        "text":             q.get("text", ""),
        "type":             q_type,
        "difficulty":       meta.get("difficulty", 1),
        "marks":            meta.get("marks", 1),
        "options":          options_list if options_list else None,
        "diagram_path":     q.get("diagram_path"),
        "generated_params": gen_params.get(qid),
        "rubric":           rubric,
        "correct_option_index": correct_index if q_type in ("mcq", "assertion_reason") else None,
        "expected_answer":  None,
        "expected_answer_str": None,
    }
    if q_type == "numerical":
        gp = gen_params.get(qid)
        if gp:
            q_out["expected_answer"]     = gp.get("expected_answer")
            q_out["expected_answer_str"] = gp.get("expected_answer_str")
    return q_out


def _check_one_active_test(exclude_id: Optional[str] = None) -> Optional[str]:
    """Return existing active chapter/mock test ID if any, else None."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM assessments WHERE is_active=1 "
        "AND type IN ('chapter_short','chapter_regular','mock') "
        "AND status IN ('in_progress','awaiting_upload') LIMIT 1"
    ).fetchone()
    conn.close()
    if row and row[0] != exclude_id:
        return row[0]
    return None


# ── POST /api/session/create ──────────────────────────────────────────────────

@router.post("/create")
def create_session(req: CreateSessionRequest):
    profile           = _get_profile()
    topic_scores      = json.loads(profile.get("topic_scores")      or "{}")
    numerical_mastery = json.loads(profile.get("numerical_mastery") or "{}")
    question_store    = get_all()

    # ── Understanding Session (Phase 2) ───────────────────────────────────
    if req.type == "understanding":
        candidates = select_candidates(
            chapter=req.chapter,
            topic=req.topic,
            topic_scores=topic_scores,
            session_type="understanding",
        )
        if not candidates:
            raise HTTPException(404, f"No approved questions for chapter '{req.chapter}'.")

        ai_result       = call_1_select_questions(req.chapter, req.topic, candidates,
                                                  topic_scores, numerical_mastery, question_store)
        selected_ids    = ai_result.get("selected_question_ids", [])
        gen_params: dict = ai_result.get("generated_params", {})

        if not selected_ids:
            raise HTTPException(500, "AI selection returned no questions.")

        meta_lut = {c["id"]: c for c in candidates}

    # ── Chapter Test (Phase 3) ─────────────────────────────────────────────
    elif req.type in CHAPTER_TEST_TYPES:
        existing = _check_one_active_test()
        if existing:
            raise HTTPException(
                409,
                f"Another chapter test ({existing}) is already in progress. "
                "Complete or expire it before starting a new one.",
            )

        templates = _load_templates()
        template  = templates.get(req.type)
        if not template:
            raise HTTPException(400, f"Unknown session type '{req.type}'.")

        # Feasibility check
        gaps = check_feasibility(req.chapter, template)
        if gaps:
            raise HTTPException(
                422,
                {
                    "error": "FEASIBILITY_FAIL",
                    "gaps": gaps,
                    "message": "Question bank does not have enough approved questions for this paper.",
                },
            )

        try:
            paper    = generate_test_paper(req.chapter, req.type, template, topic_scores)
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("FEASIBILITY_FAIL:"):
                gaps = json.loads(msg[len("FEASIBILITY_FAIL:"):])
                raise HTTPException(422, {"error": "FEASIBILITY_FAIL", "gaps": gaps})
            raise HTTPException(500, msg)

        selected_ids = paper["selected_ids"]
        gen_params   = paper["generated_params"]

        # Build meta lookup from question_index
        conn_m = get_db()
        meta_lut: dict = {}
        for qid in selected_ids:
            row = conn_m.execute("SELECT * FROM question_index WHERE id=?", [qid]).fetchone()
            if row:
                meta_lut[qid] = dict(row)
        conn_m.close()

    # ── Full Mock Test (Phase 4) ───────────────────────────────────────────
    elif req.type == "mock":
        existing = _check_one_active_test()
        if existing:
            raise HTTPException(
                409,
                f"Another test ({existing}) is already in progress. "
                "Complete or expire it before starting the mock.",
            )

        templates = _load_templates()
        template  = templates.get("mock")
        if not template:
            raise HTTPException(400, "Mock template not found in test_templates.json.")

        # Feasibility check across all 5 chapters
        gaps = check_mock_feasibility(template)
        # Abort only on hard gaps (total questions insufficient); admin alerts are warnings
        hard_gaps = [g for g in gaps if not g.startswith("ADMIN ALERT")]
        if hard_gaps:
            raise HTTPException(
                422,
                {
                    "error": "FEASIBILITY_FAIL",
                    "gaps": gaps,
                    "message": "Question bank does not have enough approved questions for the mock paper.",
                },
            )
        if gaps:  # admin-only warnings — log but do not abort
            print(f"[mock] Feasibility warnings: {gaps}")

        try:
            paper = generate_mock_paper("mock", template, topic_scores)
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("FEASIBILITY_FAIL:"):
                gaps = json.loads(msg[len("FEASIBILITY_FAIL:"):])
                raise HTTPException(422, {"error": "FEASIBILITY_FAIL", "gaps": gaps})
            raise HTTPException(500, msg)

        selected_ids = paper["selected_ids"]
        gen_params   = paper["generated_params"]
        section_map: dict = paper["section_map"]

        # Build meta lookup
        conn_m = get_db()
        meta_lut = {}
        for qid in selected_ids:
            row = conn_m.execute("SELECT * FROM question_index WHERE id=?", [qid]).fetchone()
            if row:
                meta_lut[qid] = dict(row)
        conn_m.close()

    else:
        raise HTTPException(400, f"Session type '{req.type}' not supported in this phase.")

    # ── Build question list for response ──────────────────────────────────
    # section_map only exists for mock; default to empty for other types
    if "section_map" not in dir():
        section_map = {}

    questions_out = []
    total_marks   = 0
    for seq, qid in enumerate(selected_ids, start=1):
        meta = meta_lut.get(qid, {})

        # Generate numerical params if not already done (Understanding sessions)
        if meta.get("type") == "numerical" and not gen_params.get(qid):
            q = question_store.get(qid, {})
            tp = q.get("template_params")
            if tp:
                gp = generate_params(tp, numerical_mastery, qid)
                gen_params[qid] = gp

        q_out = _build_question_out(qid, seq, question_store, meta, gen_params)
        if q_out:
            total_marks += meta.get("marks", 1)
            # Attach section for mock questions
            if req.type == "mock":
                q_out["section"] = section_map.get(qid, "A")
            questions_out.append(q_out)

    # ── Persist assessment ────────────────────────────────────────────────
    session_id = _new_session_id()
    now        = datetime.now().isoformat()
    expires_at = (datetime.now() + timedelta(hours=48)).isoformat()
    chapter_val = "all" if req.type == "mock" else (req.chapter or "")

    conn = get_db()
    conn.execute(
        """INSERT INTO assessments
           (id, type, chapter, topic, question_ids, generated_params,
            total_marks, status, started_at, expires_at, is_active, section_map)
           VALUES (?,?,?,?,?,?,?,'in_progress',?,?,1,?)""",
        [session_id, req.type, chapter_val, req.topic,
         json.dumps(selected_ids), json.dumps(gen_params),
         total_marks, now, expires_at, json.dumps(section_map)],
    )
    for qid in selected_ids:
        conn.execute(
            "UPDATE question_index SET times_served=times_served+1, last_served_at=? WHERE id=?",
            [now, qid],
        )
    conn.commit()
    conn.close()

    resp = {
        "session_id":      session_id,
        "status":          "in_progress",
        "type":            req.type,
        "chapter":         chapter_val,
        "topic":           req.topic,
        "total_questions": len(questions_out),
        "total_marks":     total_marks,
        "questions":       questions_out,
    }
    if req.type == "mock":
        resp["section_map"] = section_map
        resp["duration_minutes"] = 180
    return resp


# ── GET /api/session/active ───────────────────────────────────────────────────

@router.get("/active")
def get_active_session():
    conn = get_db()
    row = conn.execute(
        "SELECT id, type, chapter, status FROM assessments "
        "WHERE is_active=1 AND status IN ('in_progress','awaiting_upload') "
        "ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return {"active_session_id": None}
    return {
        "active_session_id": row["id"],
        "type":    row["type"],
        "chapter": row["chapter"],
        "status":  row["status"],
    }


# ── GET /api/session/{id}/questions ──────────────────────────────────────────

@router.get("/{session_id}/questions")
def get_questions(session_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM assessments WHERE id=?", [session_id]).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Session not found.")
    assessment = dict(row)
    if assessment["status"] == "expired":
        raise HTTPException(410, "Session has expired.")

    question_store = get_all()
    selected_ids   = json.loads(assessment["question_ids"] or "[]")
    gen_params     = json.loads(assessment["generated_params"] or "{}")
    section_map_q  = json.loads(assessment.get("section_map") or "{}")
    is_mock        = assessment["type"] == "mock"

    questions_out = []
    for seq, qid in enumerate(selected_ids, start=1):
        conn2 = get_db()
        meta_row = conn2.execute("SELECT * FROM question_index WHERE id=?", [qid]).fetchone()
        conn2.close()
        meta  = dict(meta_row) if meta_row else {}
        q_out = _build_question_out(qid, seq, question_store, meta, gen_params)
        if q_out:
            if is_mock:
                q_out["section"] = section_map_q.get(qid, "A")
            questions_out.append(q_out)

    resp = {
        "session_id":      session_id,
        "status":          assessment["status"],
        "type":            assessment["type"],
        "chapter":         assessment["chapter"],
        "topic":           assessment["topic"],
        "total_marks":     assessment["total_marks"],
        "total_questions": len(questions_out),
        "questions":       questions_out,
    }
    if is_mock:
        resp["section_map"] = section_map_q
        resp["duration_minutes"] = 180
    return resp


# ── PUT /api/session/{id}/mark-done-writing ───────────────────────────────────

@router.put("/{session_id}/mark-done-writing")
def mark_done_writing(session_id: str):
    conn = get_db()
    row = conn.execute("SELECT status, type FROM assessments WHERE id=?", [session_id]).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Session not found.")
    if row["status"] not in ("in_progress",):
        conn.close()
        raise HTTPException(400, f"Cannot mark done — status is '{row['status']}'.")
    conn.execute("UPDATE assessments SET status='awaiting_upload' WHERE id=?", [session_id])
    conn.commit()
    conn.close()
    return {"session_id": session_id, "status": "awaiting_upload"}


# ── POST /api/session/{id}/upload-pdf ─────────────────────────────────────────

@router.post("/{session_id}/upload-pdf")
async def upload_pdf(session_id: str, file: UploadFile = File(...)):
    """
    Phase 3 — AI Call 1: OCR the answer sheet.
    Stores ocr_text + ocr_confidence per question in answers table.
    Returns low_confidence items (confidence < 0.75) for student confirmation.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM assessments WHERE id=?", [session_id]).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Session not found.")
    assessment = dict(row)
    conn.close()

    if assessment["status"] == "expired":
        raise HTTPException(410, "Session has expired.")
    if assessment["status"] not in ("in_progress", "awaiting_upload"):
        raise HTTPException(400, f"Cannot upload — status is '{assessment['status']}'.")

    # Check OCR not already completed (idempotency guard)
    conn2 = get_db()
    existing_ocr = conn2.execute(
        "SELECT COUNT(*) as cnt FROM answers WHERE assessment_id=? AND ocr_text IS NOT NULL",
        [session_id],
    ).fetchone()
    conn2.close()
    if existing_ocr and existing_ocr["cnt"] > 0:
        raise HTTPException(400, "OCR already completed for this session. Use confirm-ocr to correct answers.")

    # Save PDF
    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = _UPLOADS_DIR / f"{session_id}.pdf"
    content  = await file.read()
    pdf_path.write_bytes(content)

    # Build ordered question list for OCR prompt
    question_store = get_all()
    selected_ids   = json.loads(assessment["question_ids"] or "[]")
    gen_params     = json.loads(assessment["generated_params"] or "{}")

    questions_list = []
    for seq, qid in enumerate(selected_ids, start=1):
        conn3 = get_db()
        meta_row = conn3.execute("SELECT * FROM question_index WHERE id=?", [qid]).fetchone()
        conn3.close()
        meta = dict(meta_row) if meta_row else {}
        q    = question_store.get(qid, {})
        questions_list.append({
            "id":       qid,
            "sequence": seq,
            "text":     q.get("text", ""),
            "type":     meta.get("type", "short"),
            "marks":    meta.get("marks", 1),
        })

    # ── AI Call 1: OCR ────────────────────────────────────────────────────
    ocr_results = call_1_ocr_pdf(content, questions_list)

    # Index OCR results by question_id
    ocr_map = {item["question_id"]: item for item in ocr_results}

    # Persist OCR results into answers table
    conn4  = get_db()
    low_confidence = []

    for qid in selected_ids:
        conn_m = get_db()
        meta_row = conn_m.execute("SELECT * FROM question_index WHERE id=?", [qid]).fetchone()
        conn_m.close()
        meta = dict(meta_row) if meta_row else {}

        ocr_item   = ocr_map.get(qid, {})
        ocr_text   = ocr_item.get("answer_text", "") or ""
        confidence = float(ocr_item.get("confidence", 0.0))
        ans_id     = f"ans_{uuid.uuid4().hex[:12]}"

        conn4.execute(
            """INSERT OR REPLACE INTO answers
               (id, assessment_id, question_id, ocr_text, ocr_confidence, max_marks)
               VALUES (?,?,?,?,?,?)""",
            [ans_id, session_id, qid, ocr_text, confidence, meta.get("marks", 1)],
        )

        if confidence < 0.75:
            low_confidence.append({
                "question_id": qid,
                "sequence":    next((q["sequence"] for q in questions_list if q["id"] == qid), 0),
                "question_text": next((q["text"][:120] for q in questions_list if q["id"] == qid), ""),
                "ocr_text":    ocr_text,
                "confidence":  confidence,
            })

    conn4.execute(
        "UPDATE assessments SET status='submitted', answer_pdf_path=? WHERE id=?",
        [str(pdf_path), session_id],
    )
    conn4.commit()
    conn4.close()

    return {
        "session_id":     session_id,
        "status":         "submitted",
        "questions_ocrd": len(selected_ids),
        "low_confidence": low_confidence,
    }


# ── POST /api/session/{id}/confirm-ocr ───────────────────────────────────────

@router.post("/{session_id}/confirm-ocr")
def confirm_ocr(session_id: str, req: ConfirmOCRRequest):
    """
    Student confirms or corrects low-confidence OCR extractions.
    Saves corrected text to answers.answer_text; original ocr_text is preserved.
    """
    conn = get_db()
    row = conn.execute("SELECT status FROM assessments WHERE id=?", [session_id]).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Session not found.")

    for item in req.confirmations:
        conn.execute(
            "UPDATE answers SET answer_text=? WHERE assessment_id=? AND question_id=?",
            [item.answer_text, session_id, item.question_id],
        )
    conn.commit()
    conn.close()
    return {"status": "confirmed", "updated": len(req.confirmations)}


# ── POST /api/session/{id}/submit ─────────────────────────────────────────────

@router.post("/{session_id}/submit")
def submit_session(session_id: str, req: Optional[SubmitSessionRequest] = None):
    """
    Understanding:   answers come from req body (typed answers)
    Chapter Tests:   answers already in DB from OCR + confirmation
    Both paths:      Layer 1 → Layer 2 → Layer 3 (single AI Call 2)
    """
    conn = get_db()
    row  = conn.execute("SELECT * FROM assessments WHERE id=?", [session_id]).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Session not found.")

    assessment  = dict(row)
    sess_type   = assessment.get("type", "understanding")
    gen_params  = json.loads(assessment.get("generated_params") or "{}")
    question_store = get_all()

    # ── Gather answers ─────────────────────────────────────────────────────
    if sess_type in PAPER_TEST_TYPES:
        # Chapter Test: read from answers table (OCR + confirmed)
        if assessment["status"] not in ("submitted",):
            raise HTTPException(
                400,
                f"Cannot score — status is '{assessment['status']}'. Upload PDF first.",
            )
        conn2 = get_db()
        ans_rows = conn2.execute(
            "SELECT * FROM answers WHERE assessment_id=? ORDER BY rowid", [session_id]
        ).fetchall()
        conn2.close()
        # Build answer map
        answers_in = [
            {
                "question_id":     r["question_id"],
                "answer_text":     r["answer_text"] or r["ocr_text"] or "",
                "selected_option": r["selected_option"],
                "time_seconds":    r["time_seconds"] or 0,
            }
            for r in ans_rows
        ]
    else:
        # Understanding: answers from request body
        if not req or not req.answers:
            raise HTTPException(400, "Answer payload required for understanding sessions.")
        answers_in = [
            {
                "question_id":     a.question_id,
                "answer_text":     a.answer_text,
                "selected_option": a.selected_option,
                "time_seconds":    a.time_seconds or 0,
            }
            for a in req.answers
        ]

    # ── Metadata lookup ────────────────────────────────────────────────────
    question_meta: dict = {}
    conn3 = get_db()
    for ans in answers_in:
        r = conn3.execute("SELECT * FROM question_index WHERE id=?", [ans["question_id"]]).fetchone()
        if r:
            question_meta[ans["question_id"]] = dict(r)
    conn3.close()

    # ── Layers 1 & 2 ──────────────────────────────────────────────────────
    results:   dict       = {}
    ai_needed: list[dict] = []

    for ans in answers_in:
        qid    = ans["question_id"]
        q      = question_store.get(qid, {})
        meta   = question_meta.get(qid, {})
        q_type = meta.get("type", "short")

        scored, needs_ai = evaluate_answer(
            question={**q, "marks": meta.get("marks", 1)},
            q_type=q_type,
            answer_text=ans["answer_text"],
            selected_option=ans["selected_option"],
            generated_params=gen_params.get(qid),
        )

        # Understanding sessions: always use AI for subjective — keyword match is too rigid
        if sess_type == "understanding" and q_type in ("short", "long", "assertion_reason"):
            needs_ai = True

        if needs_ai:
            ai_needed.append({
                "question_id":   qid,
                "question_text": q.get("text", ""),
                "type":          q_type,
                "max_marks":     meta.get("marks", 1),
                "rubric":        q.get("rubric") or {},
                "answer_text":   ans["answer_text"] or "",
            })
        else:
            results[qid] = {**(scored or {}), "max_marks": meta.get("marks", 1)}

    # ── Layer 3 — single AI Call 2 ─────────────────────────────────────────
    overall_guidance = ""
    if ai_needed:
        # Use call_2_score_and_guide for all session types — it scores + returns overall guidance
        call2 = call_2_score_and_guide(ai_needed, assessment["chapter"], sess_type)
        ai_evals     = call2["evaluations"]
        overall_guidance = call2.get("overall_guidance", "")

        for ev in ai_evals:
            qid   = ev["question_id"]
            meta  = question_meta.get(qid, {})
            max_m = meta.get("marks", 1)
            results[qid] = {
                "score":            ev.get("score", 0),
                "max_marks":        max_m,
                "is_correct":       ev.get("score", 0) >= max_m * 0.8,
                "evaluation_layer": "ai",
                "feedback": {
                    "keywords_found": ev.get("keywords_found", []),
                    "points_covered": ev.get("points_covered", []),
                    "points_missed":  ev.get("points_missed", []),
                    "comment":        ev.get("comment", ""),
                },
                "suggestions": ev.get("suggestions"),
            }

    # ── Persist scored answers ─────────────────────────────────────────────
    conn4       = get_db()
    score_total = 0.0
    answers_data: list[dict] = []

    for ans in answers_in:
        qid  = ans["question_id"]
        meta = question_meta.get(qid, {})
        r = results.get(qid, {
            "score": 0, "max_marks": meta.get("marks", 1),
            "is_correct": False, "evaluation_layer": "deterministic", "feedback": {},
        })
        ans_id = f"ans_{uuid.uuid4().hex[:12]}"

        if sess_type in PAPER_TEST_TYPES:
            # Update existing row (created during OCR upload)
            conn4.execute(
                """UPDATE answers SET
                   score=?, max_marks=?, is_correct=?,
                   evaluation_layer=?, feedback=?, suggestions=?,
                   time_seconds=?
                   WHERE assessment_id=? AND question_id=?""",
                [
                    r.get("score", 0), r.get("max_marks", 1),
                    1 if r.get("is_correct") else 0,
                    r.get("evaluation_layer", "deterministic"),
                    json.dumps(r.get("feedback", {})),
                    json.dumps(r.get("suggestions")),
                    ans.get("time_seconds", 0),
                    session_id, qid,
                ],
            )
        else:
            conn4.execute(
                """INSERT OR REPLACE INTO answers
                   (id, assessment_id, question_id, answer_text, selected_option,
                    score, max_marks, evaluation_layer, feedback, suggestions,
                    time_seconds, is_correct)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    ans_id, session_id, qid,
                    ans["answer_text"], ans["selected_option"],
                    r.get("score", 0), r.get("max_marks", 1),
                    r.get("evaluation_layer", "deterministic"),
                    json.dumps(r.get("feedback", {})),
                    json.dumps(r.get("suggestions")),
                    ans.get("time_seconds", 0),
                    1 if r.get("is_correct") else 0,
                ],
            )

        score_total += r.get("score", 0)
        answers_data.append({
            "question_id": qid,
            "score":       r.get("score", 0),
            "max_marks":   r.get("max_marks", 1),
            "is_correct":  bool(r.get("is_correct", False)),
        })

    total_marks = max(assessment.get("total_marks", 1), 1)
    percentage  = round(score_total / total_marks * 100, 1)

    # Compute session duration (needed for assessments UPDATE and badge check)
    _duration_secs = 0
    if assessment.get("started_at"):
        try:
            from datetime import datetime as _dt
            _start = _dt.fromisoformat(assessment["started_at"])
            _duration_secs = int((_dt.now() - _start).total_seconds())
        except Exception:
            pass

    # ── Capture pre-session state for badge/level checks ──────────────────
    _old_profile      = _get_profile()
    _old_xp           = _old_profile.get("total_xp", 0)
    _old_topic_scores = json.loads(_old_profile.get("topic_scores") or "{}")

    conn4.execute(
        """UPDATE assessments SET
           status='scored', score_obtained=?, percentage=?, completed_at=?, is_active=0,
           overall_guidance=?, duration_seconds=?
           WHERE id=?""",
        [score_total, percentage, datetime.now().isoformat(), overall_guidance, _duration_secs, session_id],
    )
    conn4.commit()
    conn4.close()

    # ── Purge: keep only last 6 completed sessions ─────────────────────────
    conn_purge = get_db()
    old_ids = conn_purge.execute(
        """SELECT id FROM assessments WHERE status IN ('scored','completed')
           ORDER BY completed_at DESC LIMIT -1 OFFSET 6"""
    ).fetchall()
    for (old_id,) in old_ids:
        conn_purge.execute("DELETE FROM answers WHERE assessment_id=?", [old_id])
        conn_purge.execute("DELETE FROM assessments WHERE id=?", [old_id])
    conn_purge.commit()
    conn_purge.close()

    # ── Update student_profile ─────────────────────────────────────────────
    profile_update = update_profile(
        answers_data=answers_data,
        question_meta=question_meta,
        session_type=sess_type,
        generated_params=gen_params,
    )

    # ── Gamification: badges + level-up ───────────────────────────────────
    _new_badges = check_and_award_badges(
        session_id      = session_id,
        sess_type       = sess_type,
        chapter         = assessment["chapter"],
        answers_data    = answers_data,
        profile         = _old_profile,
        topic_scores_before = _old_topic_scores,
        topic_scores_after  = profile_update.get("topic_scores", {}),
        current_streak  = profile_update["current_streak"],
        total_xp_new    = profile_update["total_xp"],
        percentage      = percentage,
        duration_seconds = _duration_secs,
    )
    _leveled_up, _new_level = check_level_up(_old_xp, profile_update["total_xp"])

    result: dict = {
        "session_id":       session_id,
        "status":           "scored",
        "type":             sess_type,
        "chapter":          assessment["chapter"],
        "topic":            assessment.get("topic"),
        "total_marks":      total_marks,
        "score_obtained":   score_total,
        "percentage":       percentage,
        "overall_guidance": overall_guidance,
        "new_badges":       _new_badges,
        "leveled_up":       _leveled_up,
        "current_level":    _new_level,
        **profile_update,
    }

    # ── Mock-specific: exam readiness + section/chapter breakdowns ─────────
    if sess_type == "mock":
        exam_readiness = compute_exam_readiness(profile_update.get("topic_scores", {}))
        conn_er = get_db()
        conn_er.execute("UPDATE student_profile SET exam_readiness_score=? WHERE id=1", [exam_readiness])
        conn_er.commit()
        conn_er.close()
        result["exam_readiness_score"] = exam_readiness

        # Section breakdown
        section_map_s = json.loads(assessment.get("section_map") or "{}")
        section_breakdown: dict = {}
        chapter_breakdown: dict = {}
        for a in answers_data:
            qid   = a["question_id"]
            score = a["score"]
            max_m = a["max_marks"]
            sec   = section_map_s.get(qid, "?")
            ch    = question_meta.get(qid, {}).get("chapter", "unknown")
            if sec not in section_breakdown:
                section_breakdown[sec] = {"score": 0.0, "max_marks": 0}
            section_breakdown[sec]["score"]     += score
            section_breakdown[sec]["max_marks"] += max_m
            if ch not in chapter_breakdown:
                chapter_breakdown[ch] = {"score": 0.0, "max_marks": 0}
            chapter_breakdown[ch]["score"]     += score
            chapter_breakdown[ch]["max_marks"] += max_m
        result["section_breakdown"] = section_breakdown
        result["chapter_breakdown"] = chapter_breakdown

    return result


# ── GET /api/session/{id}/results ─────────────────────────────────────────────

@router.get("/{session_id}/results")
def get_results(session_id: str):
    conn = get_db()
    assessment_row = conn.execute("SELECT * FROM assessments WHERE id=?", [session_id]).fetchone()
    if not assessment_row:
        conn.close()
        raise HTTPException(404, "Session not found.")
    assessment  = dict(assessment_row)
    answer_rows = conn.execute(
        "SELECT * FROM answers WHERE assessment_id=? ORDER BY rowid", [session_id]
    ).fetchall()
    conn.close()

    question_store  = get_all()
    is_mock         = assessment.get("type") == "mock"
    section_map_r   = json.loads(assessment.get("section_map") or "{}")

    results = []
    for ar in answer_rows:
        a   = dict(ar)
        qid = a["question_id"]
        q   = question_store.get(qid, {})
        rubric = q.get("rubric") or {}

        conn2 = get_db()
        meta_row = conn2.execute(
            "SELECT type, difficulty, chapter FROM question_index WHERE id=?", [qid]
        ).fetchone()
        conn2.close()
        q_type     = meta_row["type"]     if meta_row else "short"
        difficulty = meta_row["difficulty"] if meta_row else 1
        q_chapter  = meta_row["chapter"]   if meta_row else ""

        entry = {
            "question_id":      qid,
            "question_text":    q.get("text", ""),
            "question_type":    q_type,
            "difficulty":       difficulty,
            "student_answer":   a.get("answer_text") or a.get("ocr_text"),
            "selected_option":  a.get("selected_option"),
            "score":            a.get("score", 0),
            "max_marks":        a.get("max_marks", 1),
            "is_correct":       bool(a.get("is_correct")),
            "evaluation_layer": a.get("evaluation_layer", "deterministic"),
            "feedback":         json.loads(a.get("feedback") or "{}"),
            "suggestions":      json.loads(a.get("suggestions") or "null"),
            "model_answer":     rubric.get("expected_answer", ""),
            "key_points":       rubric.get("key_points", []),
        }
        if is_mock:
            entry["section"]  = section_map_r.get(qid, "?")
            entry["chapter"]  = q_chapter
        results.append(entry)

    profile = _get_profile()
    topic_scores_raw = json.loads(profile.get("topic_scores") or "{}")

    resp = {
        "session_id":       session_id,
        "type":             assessment.get("type"),
        "chapter":          assessment.get("chapter"),
        "topic":            assessment.get("topic"),
        "total_marks":      assessment.get("total_marks", 0),
        "score_obtained":   assessment.get("score_obtained", 0),
        "percentage":       assessment.get("percentage", 0),
        "status":           assessment.get("status"),
        "overall_guidance": assessment.get("overall_guidance") or "",
        "results":          results,
        "total_xp":         profile.get("total_xp", 0),
        "current_streak":   profile.get("current_streak", 0),
        "topic_scores":     topic_scores_raw,
    }

    if is_mock:
        # Section breakdown
        section_breakdown: dict = {}
        chapter_breakdown: dict = {}
        for r in results:
            sec = r.get("section", "?")
            ch  = r.get("chapter", "unknown")
            s, m = r["score"], r["max_marks"]
            if sec not in section_breakdown:
                section_breakdown[sec] = {"score": 0.0, "max_marks": 0}
            section_breakdown[sec]["score"]     += s
            section_breakdown[sec]["max_marks"] += m
            if ch not in chapter_breakdown:
                chapter_breakdown[ch] = {"score": 0.0, "max_marks": 0}
            chapter_breakdown[ch]["score"]     += s
            chapter_breakdown[ch]["max_marks"] += m

        resp["section_breakdown"]    = section_breakdown
        resp["chapter_breakdown"]    = chapter_breakdown
        resp["exam_readiness_score"] = profile.get("exam_readiness_score", 0.0)
        resp["duration_minutes"]     = 180

    return resp
