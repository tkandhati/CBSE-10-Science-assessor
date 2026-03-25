from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

# ── Session / Assessment ─────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    type: str                           # understanding | chapter_short | chapter_regular | mock
    chapter: Optional[str] = None       # chapter_id; None or "all" for mock
    topic: Optional[str] = None

class SubmitAnswerItem(BaseModel):
    question_id: str
    answer_text: Optional[str] = None
    selected_option: Optional[int] = None
    time_seconds: Optional[int] = 0

class SubmitSessionRequest(BaseModel):
    answers: List[SubmitAnswerItem] = []

class ConfirmOCRItem(BaseModel):
    question_id: str
    answer_text: str  # confirmed or corrected text

class ConfirmOCRRequest(BaseModel):
    confirmations: List[ConfirmOCRItem]

# ── Question Bank ─────────────────────────────────────────────────────────────

class ApproveQuestionRequest(BaseModel):
    pass

class EditQuestionRequest(BaseModel):
    text: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[int] = None
    marks: Optional[int] = None
    tags: Optional[str] = None
    approved: Optional[bool] = None
