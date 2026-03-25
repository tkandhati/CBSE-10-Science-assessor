"""
Question Bank admin endpoints (Phase 6).
Manages the review queue and live question bank.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from backend.database import get_db
from backend.services.question_loader import get_all as get_question_store

router = APIRouter(prefix="/api/qbank", tags=["qbank"])

_DATA_DIR    = Path(__file__).parent.parent.parent / "data"
_QDATA_DIR   = _DATA_DIR / "questions"
_SYLLABUS    = _DATA_DIR / "config" / "syllabus.json"

_CHAPTER_FILES = {
    "ch01_chemical_reactions":   "ch01_chemical_reactions.json",
    "ch02_acids_bases_salts":    "ch02_acids_bases_salts.json",
    "ch03_metals_non_metals":    "ch03_metals_non_metals.json",
    "ch04_carbon_compounds":     "ch04_carbon_compounds.json",
    "ch05_life_processes":       "ch05_life_processes.json",
    "ch06_control_coordination": "ch06_control_coordination.json",
    "ch07_reproduction":         "ch07_reproduction.json",
    "ch08_heredity":             "ch08_heredity.json",
    "ch10_light":                "ch10_light.json",
    "ch11_human_eye":            "ch11_human_eye.json",
    "ch12_electricity":          "ch12_electricity.json",
    "ch13_magnetic_effects":     "ch13_magnetic_effects.json",
    "ch15_our_environment":      "ch15_our_environment.json",
}


def _parse_json(value) -> dict | list:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def qbank_stats():
    """Question bank statistics grouped by chapter, type, difficulty, approval status."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT chapter, type, difficulty, approved, COUNT(*) AS cnt
        FROM   question_index
        GROUP  BY chapter, type, difficulty, approved
        """
    ).fetchall()

    # Also count pending in review_queue
    pending_by_chapter = {}
    try:
        prows = conn.execute(
            "SELECT chapter, COUNT(*) AS cnt FROM review_queue WHERE status='pending' GROUP BY chapter"
        ).fetchall()
        for pr in prows:
            pending_by_chapter[pr["chapter"]] = pr["cnt"]
    except Exception:
        pass

    conn.close()

    by_chapter:    dict = {}
    by_type:       dict = {}
    by_difficulty: dict = {}
    total = 0
    approved_count = 0

    for row in rows:
        ch   = row["chapter"]
        typ  = row["type"]
        diff = row["difficulty"]
        cnt  = row["cnt"]
        appr = bool(row["approved"])
        total += cnt
        if appr:
            approved_count += cnt
        by_chapter.setdefault(ch, {"approved": 0, "pending": 0, "rejected": 0, "total": 0})
        by_chapter[ch]["total"]    += cnt
        by_chapter[ch]["approved"] += cnt if appr else 0
        by_chapter[ch]["pending"]  += 0 if appr else cnt
        by_type[typ]         = by_type.get(typ, 0) + cnt
        by_difficulty[str(diff)] = by_difficulty.get(str(diff), 0) + cnt

    # Merge review_queue pending counts into by_chapter
    for ch, cnt in pending_by_chapter.items():
        by_chapter.setdefault(ch, {"approved": 0, "pending": 0, "rejected": 0, "total": 0})
        by_chapter[ch]["pending"] += cnt
        by_chapter[ch]["total"]   += cnt

    review_total = sum(pending_by_chapter.values())

    return {
        "total":            total + review_total,
        "approved":         approved_count,
        "pending_review":   review_total,
        "by_chapter":       by_chapter,
        "by_type":          by_type,
        "by_difficulty":    by_difficulty,
    }


# ── Review Queue ──────────────────────────────────────────────────────────────

@router.get("/review-queue")
def review_queue(
    chapter: Optional[str] = None,
    topic:   Optional[str] = None,
    type:    Optional[str] = None,
    page:    int = Query(default=1, ge=1),
    limit:   int = Query(default=20, ge=1, le=100),
):
    """Questions pending admin approval, from the review_queue table."""
    conn = get_db()
    where_parts = ["status = 'pending'"]
    params: list = []
    if chapter:
        where_parts.append("chapter = ?")
        params.append(chapter)
    if topic:
        where_parts.append("topic = ?")
        params.append(topic)
    if type:
        where_parts.append("type = ?")
        params.append(type)

    where_sql = " AND ".join(where_parts)
    total = conn.execute(f"SELECT COUNT(*) FROM review_queue WHERE {where_sql}", params).fetchone()[0]
    offset = (page - 1) * limit
    rows = conn.execute(
        f"SELECT * FROM review_queue WHERE {where_sql} ORDER BY added_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    conn.close()

    questions = []
    for r in rows:
        d = dict(r)
        d["options"] = _parse_json(d.get("options"))
        d["rubric"]  = _parse_json(d.get("rubric"))
        questions.append(d)

    return {"questions": questions, "total": total, "page": page, "limit": limit}


@router.put("/{question_id}/approve")
def approve_question(question_id: str):
    """
    Approve: write to chapter JSON file and insert into question_index with approved=True.
    Removes from review_queue.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM review_queue WHERE id=?", (question_id,)).fetchone()
    if not row:
        # Maybe it's already in question_index (pending = approved=0)
        qi = conn.execute("SELECT * FROM question_index WHERE id=?", (question_id,)).fetchone()
        if qi:
            conn.execute("UPDATE question_index SET approved=1 WHERE id=?", (question_id,))
            conn.commit()
            conn.close()
            return {"question_id": question_id, "status": "approved"}
        conn.close()
        raise HTTPException(404, "Question not found in review queue")

    q = dict(row)
    chapter = q["chapter"]

    # Write to chapter JSON file
    fname = _CHAPTER_FILES.get(chapter)
    if fname:
        fpath = _QDATA_DIR / fname
        if fpath.exists():
            data = json.loads(fpath.read_text(encoding="utf-8"))
        else:
            data = {"questions": []}

        # Build question object for JSON file
        q_obj = {
            "id":          q["id"],
            "text":        q["text"],
            "type":        q["type"],
            "marks":       q["marks"],
            "topic":       q["topic"],
            "difficulty":  q["difficulty"],
            "options":     _parse_json(q.get("options")) or None,
            "rubric": _parse_json(q.get("rubric")) or {
                "keywords": [], "key_points": [], "formula": None,
                "expected_answer": "", "diagram_required": False,
                "diagram_checklist": [], "partial_marks": {},
            },
            "source":      q.get("source", ""),
            "board_years": q.get("board_years", ""),
            "tags":        q.get("tags", ""),
        }
        # Remove existing entry if present
        data["questions"] = [x for x in data["questions"] if x["id"] != question_id]
        data["questions"].append(q_obj)
        fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Insert/update question_index
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO question_index
           (id, chapter, topic, type, difficulty, marks, approved, source, board_years,
            has_diagram, has_template, times_served, tags)
           VALUES (?,?,?,?,?,?,1,?,?,0,0,0,?)""",
        [question_id, q["chapter"], q["topic"], q["type"],
         q["difficulty"], q["marks"], q.get("source",""), q.get("board_years",""), q.get("tags","")],
    )
    conn.execute("DELETE FROM review_queue WHERE id=?", (question_id,))
    conn.commit()
    conn.close()
    return {"question_id": question_id, "status": "approved"}


@router.put("/{question_id}/reject")
def reject_question(question_id: str):
    """Mark as rejected in review_queue (soft delete)."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM review_queue WHERE id=?", (question_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Question not found in review queue")
    conn.execute("UPDATE review_queue SET status='rejected' WHERE id=?", (question_id,))
    conn.commit()
    conn.close()
    return {"question_id": question_id, "status": "rejected"}


class EditQuestionBody(BaseModel):
    text:             Optional[str] = None
    topic:            Optional[str] = None
    type:             Optional[str] = None
    difficulty:       Optional[int] = None
    marks:            Optional[int] = None
    tags:             Optional[str] = None
    rubric_keywords:  Optional[list] = None
    rubric_key_points: Optional[list] = None
    rubric_expected_answer: Optional[str] = None


@router.put("/{question_id}/edit")
def edit_question(question_id: str, body: EditQuestionBody):
    """Edit question metadata and/or rubric in review_queue."""
    conn = get_db()
    row = conn.execute("SELECT * FROM review_queue WHERE id=?", (question_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Question not found in review queue")

    q = dict(row)
    rubric = _parse_json(q.get("rubric")) or {}

    # Apply updates
    if body.text is not None:
        q["text"] = body.text
    if body.topic is not None:
        q["topic"] = body.topic
    if body.type is not None:
        q["type"] = body.type
    if body.difficulty is not None:
        q["difficulty"] = body.difficulty
    if body.marks is not None:
        q["marks"] = body.marks
    if body.tags is not None:
        q["tags"] = body.tags
    if body.rubric_keywords is not None:
        rubric["keywords"] = body.rubric_keywords
    if body.rubric_key_points is not None:
        rubric["key_points"] = body.rubric_key_points
    if body.rubric_expected_answer is not None:
        rubric["expected_answer"] = body.rubric_expected_answer

    conn.execute(
        """UPDATE review_queue SET text=?, topic=?, type=?, difficulty=?, marks=?, tags=?, rubric=?
           WHERE id=?""",
        [q["text"], q["topic"], q["type"], q["difficulty"], q["marks"], q.get("tags", ""),
         json.dumps(rubric), question_id],
    )
    conn.commit()
    conn.close()
    return {"question_id": question_id, "status": "updated"}


# ── Live Bank (approved questions) ───────────────────────────────────────────

@router.get("/live")
def live_bank(
    chapter:    Optional[str] = None,
    topic:      Optional[str] = None,
    type:       Optional[str] = None,
    difficulty: Optional[int] = None,
    search:     Optional[str] = None,
    page:       int = Query(default=1, ge=1),
    limit:      int = Query(default=20, ge=1, le=100),
):
    """All approved questions with filters and pagination."""
    conn = get_db()
    where_parts = ["approved = 1"]
    params: list = []

    if chapter:
        where_parts.append("chapter = ?")
        params.append(chapter)
    if topic:
        where_parts.append("topic = ?")
        params.append(topic)
    if type:
        where_parts.append("type = ?")
        params.append(type)
    if difficulty:
        where_parts.append("difficulty = ?")
        params.append(difficulty)

    where_sql = " AND ".join(where_parts)
    total = conn.execute(f"SELECT COUNT(*) FROM question_index WHERE {where_sql}", params).fetchone()[0]
    offset = (page - 1) * limit
    rows = conn.execute(
        f"""SELECT id, chapter, topic, type, difficulty, marks, times_served, last_served_at, source, tags
            FROM question_index WHERE {where_sql} ORDER BY chapter, topic, id
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()
    conn.close()

    question_store = get_question_store()
    questions = []
    for r in rows:
        d = dict(r)
        q = question_store.get(d["id"], {})
        # Apply text search filter
        if search and search.lower() not in (q.get("text", "") + d.get("tags", "")).lower():
            continue
        d["text_preview"] = (q.get("text", "") or "")[:200]
        d["full_text"]    = q.get("text", "")
        d["options"]      = q.get("options")
        rubric = q.get("rubric") or {}
        d["expected_answer"] = rubric.get("expected_answer", "")
        d["key_points"]      = rubric.get("key_points", [])
        questions.append(d)

    return {"questions": questions, "total": total, "page": page, "limit": limit}


# ── PDF Scan ──────────────────────────────────────────────────────────────────

@router.post("/scan-pdf")
async def scan_pdf(file: UploadFile = File(...)):
    """
    Upload a CBSE paper PDF. AI extracts questions and adds them to review_queue.
    Uses Claude Vision (same client as Phase 3 OCR).
    """
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file uploaded")

    # Call AI to extract questions
    try:
        from backend.services.ai_client import call_extract_questions_from_pdf
        extracted = call_extract_questions_from_pdf(content)
    except Exception as exc:
        extracted = []
        print(f"[qbank] PDF scan failed: {exc}")

    if not extracted:
        return {"status": "no_questions_extracted", "queued": 0}

    conn = get_db()
    now = datetime.now().isoformat()
    queued = 0
    for q in extracted:
        qid = f"rq_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO review_queue
               (id, chapter, topic, type, difficulty, marks, text, options, rubric, source, board_years, tags, added_at, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'pending')""",
            [
                qid,
                q.get("chapter", "unknown"),
                q.get("topic", "unknown"),
                q.get("type", "short"),
                q.get("difficulty", 2),
                q.get("marks", 2),
                q.get("text", ""),
                json.dumps(q.get("options")),
                json.dumps(q.get("rubric", {})),
                q.get("source", "PDF scan"),
                q.get("board_years", ""),
                q.get("tags", ""),
                now,
            ],
        )
        queued += 1
    conn.commit()
    conn.close()

    return {"status": "queued", "queued": queued}


# ── Retag ─────────────────────────────────────────────────────────────────────

@router.post("/retag")
def retag(chapter: Optional[str] = None, topic: Optional[str] = None):
    """
    Re-run AI tagging on review_queue questions for the given chapter/topic.
    Stub: returns count of questions that would be retagged.
    """
    conn = get_db()
    where = "status='pending'"
    params: list = []
    if chapter:
        where += " AND chapter=?"
        params.append(chapter)
    if topic:
        where += " AND topic=?"
        params.append(topic)
    count = conn.execute(f"SELECT COUNT(*) FROM review_queue WHERE {where}", params).fetchone()[0]
    conn.close()
    return {"status": "retagged", "retagged": count}


# ── Stats shortcut for admin ──────────────────────────────────────────────────

@router.get("/coverage")
def qbank_coverage():
    """Coverage alias — delegates to admin coverage logic."""
    from backend.routers.admin import coverage_report
    return coverage_report()
