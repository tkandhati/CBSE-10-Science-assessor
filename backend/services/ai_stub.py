"""
Stub for all Claude API calls.
Phase 1: returns placeholder responses.
Phase 2+ will replace these with real Anthropic API calls.
"""
from typing import Any

def stub_select_questions(chapter: str, topic: str | None, student_profile: dict) -> dict:
    """Phase 2: Call Claude to select questions and generate fresh numerical params."""
    return {
        "question_ids": [],
        "generated_params": {}
    }

def stub_evaluate_subjective(answers: list[dict]) -> list[dict]:
    """Phase 2: Batch-evaluate all subjective answers via Claude."""
    return [
        {
            "question_id": a["question_id"],
            "score": 0,
            "evaluation_layer": "ai",
            "feedback": {"keywords_found": [], "points_covered": [], "points_missed": [], "comment": "Stub — not evaluated"},
            "suggestions": None
        }
        for a in answers
    ]

def stub_pdf_ocr(pdf_path: str, question_ids: list[str]) -> list[dict]:
    """Phase 3: Send PDF to Claude Vision for intelligent split + OCR."""
    return [
        {"question_id": qid, "ocr_text": "", "ocr_confidence": 0.0}
        for qid in question_ids
    ]

def stub_study_guidance(student_profile: dict) -> dict:
    """Phase 2: Generate AI study guidance (cached 24h)."""
    return {
        "priority_topics": [],
        "recommended_sequence": [],
        "ncert_references": [],
        "exam_readiness": "Stub — not yet generated"
    }
