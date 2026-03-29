"""
Multi-provider AI client for Science Assessor.

Provider selection — first non-blank key wins, in this order:
  1. ANTHROPIC_API_KEY  →  claude-sonnet-4-6
  2. GOOGLE_API_KEY     →  gemini-2.0-flash
  3. OPENAI_API_KEY     →  gpt-4o

If no key is set, all calls fall back to deterministic stubs (ai_stub.py).
The active provider is logged at startup.

Per-session AI budget: strictly 2 calls maximum.
  - Understanding:   Call 1 = question selection + numericals
                     Call 2 = evaluate subjective answers
  - Chapter / Mock:  Call 1 = PDF OCR + answer splitting
                     Call 2 = score + improvement suggestions
  - Admin guidance:  independent call, outside per-session budget
"""
import os
import json
import re
import base64
import io
from typing import Optional

# ── Provider initialisation (priority: Anthropic → Google → OpenAI) ───────────

_PROVIDER: Optional[str] = None   # "anthropic" | "google" | "openai" | None
_anthropic_client = None
_google_model     = None
_openai_client    = None

_ANTHROPIC_MODEL = "claude-sonnet-4-6"
_GOOGLE_MODEL    = "gemini-2.5-flash"
_OPENAI_MODEL    = "gpt-4o"

_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
_GOOGLE_KEY    = os.environ.get("GOOGLE_API_KEY",    "").strip()
_OPENAI_KEY    = os.environ.get("OPENAI_API_KEY",    "").strip()

if _ANTHROPIC_KEY:
    try:
        from anthropic import Anthropic
        _anthropic_client = Anthropic(api_key=_ANTHROPIC_KEY)
        _PROVIDER = "anthropic"
        print(f"[ai_client] Provider: Anthropic ({_ANTHROPIC_MODEL})")
    except Exception as _e:
        print(f"[ai_client] Anthropic init failed: {_e}")

if _PROVIDER is None and _GOOGLE_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=_GOOGLE_KEY)
        _google_model = genai.GenerativeModel(_GOOGLE_MODEL)
        _PROVIDER = "google"
        print(f"[ai_client] Provider: Google ({_GOOGLE_MODEL})")
    except Exception as _e:
        print(f"[ai_client] Google init failed: {_e}")

if _PROVIDER is None and _OPENAI_KEY:
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=_OPENAI_KEY)
        _PROVIDER = "openai"
        print(f"[ai_client] Provider: OpenAI ({_OPENAI_MODEL})")
    except Exception as _e:
        print(f"[ai_client] OpenAI init failed: {_e}")

if _PROVIDER is None:
    print("[ai_client] No API key found — running in stub mode (deterministic fallbacks)")

_AVAILABLE = _PROVIDER is not None


def get_active_provider() -> Optional[str]:
    """Return the active provider name, or None if running in stub mode."""
    return _PROVIDER


# ── Low-level dispatch helpers ─────────────────────────────────────────────────

def _call_text(prompt: str, max_tokens: int) -> str:
    """Send a text-only prompt to the active provider. Returns response text."""
    if _PROVIDER == "anthropic":
        resp = _anthropic_client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    if _PROVIDER == "google":
        resp = _google_model.generate_content(prompt)
        return resp.text

    if _PROVIDER == "openai":
        resp = _openai_client.chat.completions.create(
            model=_OPENAI_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

    raise RuntimeError("No AI provider available")


def _call_with_pdf(prompt: str, pdf_bytes: bytes, max_tokens: int) -> str:
    """
    Send a prompt + PDF to the active provider.

    - Anthropic: native PDF document type (base64)
    - Google:    inline PDF part (base64)
    - OpenAI:    gpt-4o does not natively accept PDFs — text is extracted
                 via pdfplumber and appended to the prompt
    """
    if _PROVIDER == "anthropic":
        resp = _anthropic_client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(pdf_bytes).decode(),
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return resp.content[0].text

    if _PROVIDER == "google":
        import google.generativeai as genai
        pdf_part = {"mime_type": "application/pdf",
                    "data": base64.b64encode(pdf_bytes).decode()}
        resp = _google_model.generate_content([pdf_part, prompt])
        return resp.text

    if _PROVIDER == "openai":
        # Extract text from PDF with pdfplumber, then send as a text prompt
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            pdf_text = "\n\n".join(pages) if pages else "[PDF text extraction failed]"
        except Exception as ex:
            pdf_text = f"[PDF text extraction failed: {ex}]"

        full_prompt = f"{prompt}\n\n--- PDF CONTENT (text extracted) ---\n{pdf_text}"
        resp = _openai_client.chat.completions.create(
            model=_OPENAI_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": full_prompt}],
        )
        return resp.choices[0].message.content

    raise RuntimeError("No AI provider available")


def _parse_json_response(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


# ── Call 1: Question Selection ─────────────────────────────────────────────────

def call_1_select_questions(
    chapter: str,
    topic: Optional[str],
    candidates: list[dict],
    topic_scores: dict[str, float],
    numerical_mastery: dict,
    question_store: dict,
) -> dict:
    """
    Select 10-12 questions and generate fresh numerical params.
    Falls back to deterministic selection if no provider is available.
    """
    if not _AVAILABLE:
        return _fallback_select(candidates, question_store, numerical_mastery)

    cand_info = []
    for c in candidates[:50]:
        qid = c["id"]
        q = question_store.get(qid, {})
        entry = {
            "id":           qid,
            "topic":        c["topic"],
            "type":         c["type"],
            "difficulty":   c["difficulty"],
            "marks":        c["marks"],
            "times_served": c["times_served"],
            "text_preview": (q.get("text") or "")[:120],
        }
        if c.get("has_template") and q.get("template_params"):
            entry["template_params"] = q["template_params"]
        cand_info.append(entry)

    chapter_scores = {k: v for k, v in topic_scores.items() if chapter in k}

    prompt = f"""You are selecting questions for a CBSE Class 10 Science Understanding Session.

Chapter: {chapter}
Topic filter: {topic or "full chapter — cover all topics broadly"}

Student topic scores (0-100, lower = needs more work):
{json.dumps(chapter_scores, indent=2)}

Eligible candidates ({len(cand_info)} questions):
{json.dumps(cand_info, indent=2)}

Task:
1. Select exactly 11 questions (10-12 range acceptable).
2. Cover different sub-topics — do NOT cluster on one topic.
3. Prioritise questions where topic score < 60.
4. Type mix target: ~3 MCQ, ~5 short, ~2 numerical, ~1 long.
5. Difficulty mix: ~25% L1, ~30% L2, ~30% L3, ~15% L4.
6. For every numerical question selected, compute fresh variable values within the template_params ranges and compute expected_answer from formula_expression.

Return ONLY valid JSON — no other text:
{{
  "selected_question_ids": ["id1", "id2"],
  "generated_params": {{
    "<question_id>": {{
      "variables": {{"var": value}},
      "expected_answer": 0.0,
      "expected_answer_str": "0.0 units",
      "formula_used": "expression"
    }}
  }},
  "session_note": "one sentence rationale"
}}"""

    try:
        text = _call_text(prompt, max_tokens=2048)
        return _parse_json_response(text)
    except Exception as exc:
        print(f"[ai_client] call_1_select_questions failed ({_PROVIDER}): {exc} — using fallback")
        return _fallback_select(candidates, question_store, numerical_mastery)


def _fallback_select(candidates: list[dict], question_store: dict, numerical_mastery: dict) -> dict:
    """Deterministic fallback: balanced by type, ordered by weight."""
    from backend.services.numerical import generate_params

    type_budget = {"mcq": 3, "short": 5, "numerical": 2, "long": 1}
    selected: list[dict] = []
    type_counts: dict[str, int] = {}

    for c in candidates:
        t = c["type"]
        if type_counts.get(t, 0) < type_budget.get(t, 1):
            selected.append(c)
            type_counts[t] = type_counts.get(t, 0) + 1
        if len(selected) >= 11:
            break

    if len(selected) < 10:
        for c in candidates:
            if c not in selected:
                selected.append(c)
            if len(selected) >= 10:
                break

    gen_params: dict = {}
    for c in selected:
        if c["type"] == "numerical" and c.get("has_template"):
            q = question_store.get(c["id"], {})
            tp = q.get("template_params")
            if tp:
                gen_params[c["id"]] = generate_params(tp, numerical_mastery, c["id"])

    return {
        "selected_question_ids": [c["id"] for c in selected],
        "generated_params":      gen_params,
        "session_note":          "Fallback deterministic selection (no AI provider configured).",
    }


# ── Call 2: Subjective Evaluation ─────────────────────────────────────────────

def call_2_evaluate_subjective(items: list[dict]) -> list[dict]:
    """
    items: [{question_id, question_text, type, max_marks, rubric, answer_text}]
    Returns: [{question_id, score, keywords_found, points_covered, points_missed, comment, suggestions}]
    """
    if not items:
        return []
    if not _AVAILABLE:
        return _fallback_evaluate(items)

    prompt = f"""You are scoring CBSE Class 10 Science answers for an Understanding Session.
Be encouraging but accurate. Award partial marks proportionally.

Answers to evaluate ({len(items)} items):
{json.dumps(items, indent=2)}

Return ONLY valid JSON:
{{
  "evaluations": [
    {{
      "question_id": "...",
      "score": 1.5,
      "keywords_found": ["keyword"],
      "points_covered": ["point correctly addressed"],
      "points_missed": ["point not addressed"],
      "comment": "One encouraging sentence.",
      "suggestions": "One specific improvement tip."
    }}
  ]
}}"""

    try:
        text = _call_text(prompt, max_tokens=3000)
        result = _parse_json_response(text)
        return result.get("evaluations", [])
    except Exception as exc:
        print(f"[ai_client] call_2_evaluate_subjective failed ({_PROVIDER}): {exc} — using fallback")
        return _fallback_evaluate(items)


# ── Call 1 (Phase 3): PDF OCR ──────────────────────────────────────────────────

def call_1_ocr_pdf(pdf_bytes: bytes, questions: list[dict]) -> list[dict]:
    """
    Send the full PDF with the ordered question list.
    Returns list of {question_id, answer_text, confidence}.
    OpenAI path uses pdfplumber text extraction (no native PDF vision).
    """
    if not _AVAILABLE:
        return _fallback_ocr(questions)

    q_list = "\n".join(
        f"Q{q['sequence']}. [ID:{q['id']}] ({q['type']}, {q['marks']}m): {(q.get('text') or '')[:120]}"
        for q in questions
    )

    prompt = f"""You are extracting a CBSE Class 10 Science student's handwritten answers from their answer sheet PDF.

The test paper had these questions (in order):
{q_list}

For each question, find the student's answer — it may be on any page, written anywhere. The student may have:
- Written answers in order or skipped around
- Left some questions unanswered
- Written across multiple lines or continued on the next page

Return ONLY valid JSON:
{{
  "answers": [
    {{
      "question_id": "<exact id from the list above>",
      "answer_text": "<extracted answer, verbatim as written>",
      "confidence": 0.95
    }}
  ]
}}

Confidence scoring:
- 1.0  = clearly legible, complete answer
- 0.75-0.99 = readable but some words unclear
- 0.50-0.74 = significant parts unclear or answer may be incomplete
- <0.50 = mostly unreadable

Include an entry for every question. Use empty string and confidence 0.0 for blank/unanswered questions."""

    try:
        text = _call_with_pdf(prompt, pdf_bytes, max_tokens=4096)
        result = _parse_json_response(text)
        return result.get("answers", [])
    except Exception as exc:
        print(f"[ai_client] call_1_ocr_pdf failed ({_PROVIDER}): {exc} — using fallback")
        return _fallback_ocr(questions)


def _fallback_ocr(questions: list[dict]) -> list[dict]:
    return [{"question_id": q["id"], "answer_text": "", "confidence": 0.0} for q in questions]


# ── Call 2 (Phase 3): Score + Overall Guidance ────────────────────────────────

def call_2_score_and_guide(items: list[dict], chapter: str, session_type: str) -> dict:
    """
    Score answers and return overall_guidance paragraph.
    Used for Chapter Tests and Mocks.
    Returns {"evaluations": [...], "overall_guidance": "..."}
    """
    if not items:
        return {"evaluations": [], "overall_guidance": ""}
    if not _AVAILABLE:
        evals = _fallback_evaluate(items)
        return {"evaluations": evals, "overall_guidance": "AI evaluation unavailable — review model answers manually."}

    is_mock = session_type == "mock"
    scope_desc = "Full Mock Test (all 13 Science chapters)" if is_mock else f"chapter test for {chapter}"
    guidance_spec = (
        "A comprehensive 3-4 sentence paragraph covering: (1) top 3 weakest areas identified "
        "across the full paper with specific chapter and topic names, (2) estimated marks "
        "recoverable with targeted revision in the next 2 weeks, (3) specific study "
        "recommendation for each weak area."
        if is_mock
        else "A 2-3 sentence paragraph: summarise overall performance, highlight 1-2 strongest areas, give 1-2 specific improvement priorities."
    )

    prompt = f"""You are scoring a CBSE Class 10 Science {scope_desc}.
Be encouraging but accurate. Award partial marks proportionally.

Answers to evaluate ({len(items)} items):
{json.dumps(items, indent=2)}

Return ONLY valid JSON:
{{
  "evaluations": [
    {{
      "question_id": "...",
      "score": 1.5,
      "keywords_found": ["keyword"],
      "points_covered": ["point correctly addressed"],
      "points_missed": ["point not addressed"],
      "comment": "One encouraging sentence.",
      "suggestions": "One specific improvement tip."
    }}
  ],
  "overall_guidance": "{guidance_spec}"
}}"""

    try:
        text = _call_text(prompt, max_tokens=4096)
        result = _parse_json_response(text)
        return {
            "evaluations":     result.get("evaluations", []),
            "overall_guidance": result.get("overall_guidance", ""),
        }
    except Exception as exc:
        print(f"[ai_client] call_2_score_and_guide failed ({_PROVIDER}): {exc} — using fallback")
        evals = _fallback_evaluate(items)
        return {"evaluations": evals, "overall_guidance": "AI evaluation unavailable."}


def _fallback_evaluate(items: list[dict]) -> list[dict]:
    """Fallback: award half marks for any non-empty answer."""
    results = []
    for item in items:
        has_answer = bool((item.get("answer_text") or "").strip())
        max_marks  = item.get("max_marks", 1)
        score      = round(max_marks * 0.5, 1) if has_answer else 0
        results.append({
            "question_id":    item["question_id"],
            "score":          score,
            "keywords_found": [],
            "points_covered": [],
            "points_missed":  ["AI evaluation unavailable — manual review recommended"],
            "comment":        "Answer received. Full evaluation requires an AI provider (no API key configured).",
            "suggestions":    "Review the model answer and compare your response.",
        })
    return results


# ── Admin Guidance Call (outside per-session budget) ──────────────────────────

def call_guidance(
    weak_topics: list,
    recent_sessions: list,
    current_streak: int,
    exam_readiness_score: float,
    days_until_exam: int,
) -> dict:
    """
    Independent admin guidance call — outside the per-session 2-call budget.
    Cached for 24 hours in student_profile.guidance_cache.
    """
    if not _AVAILABLE:
        return _fallback_guidance(weak_topics, exam_readiness_score, days_until_exam)

    prompt = f"""You are a study advisor for a CBSE Class 10 Science student preparing for board exams.

Student status:
- Days until board exam: {days_until_exam}
- Current study streak: {current_streak} days
- Projected board score (out of 84 marks): {exam_readiness_score}

Top weakest topics (score 0-100, lower = weaker):
{json.dumps(weak_topics, indent=2)}

Last 5 sessions:
{json.dumps(recent_sessions, indent=2)}

Return ONLY valid JSON with this exact structure (no other text):
{{
  "priority_topics": [
    {{
      "topic_key": "chapter_id.topic_id",
      "topic_name": "Human-readable topic name",
      "current_score": 45.0,
      "reason": "Why this is a priority for the student",
      "ncert_reference": "NCERT Class 10 Science, Chapter X, Section Y.Z"
    }}
  ],
  "recommended_sequence": [
    {{
      "day": 1,
      "session_type": "understanding",
      "focus": "topic_key or chapter_id",
      "note": "Specific focus instruction"
    }}
  ],
  "exam_readiness_projection": {{
    "current_score": {exam_readiness_score},
    "target_score": 70.0,
    "marks_recoverable": 5.0,
    "what_if": "One sentence: if student improves top 3 weak topics by 20%, projected gain"
  }},
  "cached_at": "{__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}"
}}

Constraints:
- priority_topics: exactly 3 items
- recommended_sequence: exactly 7 items (one per day)
- Be specific — name the actual topics and NCERT sections
- Marks recoverable = realistic estimate based on board weightage (84 total marks)"""

    try:
        text = _call_text(prompt, max_tokens=2048)
        result = _parse_json_response(text)
        if "cached_at" not in result:
            from datetime import datetime, timezone as tz
            result["cached_at"] = datetime.now(tz.utc).isoformat()
        return result
    except Exception as exc:
        print(f"[ai_client] call_guidance failed ({_PROVIDER}): {exc} — using fallback")
        return _fallback_guidance(weak_topics, exam_readiness_score, days_until_exam)


def _fallback_guidance(weak_topics: list, exam_readiness_score: float, days_until_exam: int) -> dict:
    from datetime import datetime, timezone as tz

    priority = []
    for t in weak_topics[:3]:
        parts = t["topic_key"].split(".", 1)
        priority.append({
            "topic_key":       t["topic_key"],
            "topic_name":      t.get("topic_title", parts[1].replace("_", " ").title() if len(parts) > 1 else t["topic_key"]),
            "current_score":   t["score"],
            "reason":          "Lowest performance score in practice sessions",
            "ncert_reference": "See NCERT Class 10 Science textbook",
        })

    session_types = ["understanding", "understanding", "chapter_short", "understanding", "understanding", "chapter_regular", "understanding"]
    sequence = []
    for i in range(7):
        focus = weak_topics[i % len(weak_topics)]["topic_key"] if weak_topics else "revision"
        sequence.append({
            "day":          i + 1,
            "session_type": session_types[i],
            "focus":        focus,
            "note":         f"Focus on weak area: {focus}",
        })

    return {
        "priority_topics":      priority,
        "recommended_sequence": sequence,
        "exam_readiness_projection": {
            "current_score":    exam_readiness_score,
            "target_score":     70.0,
            "marks_recoverable": round(max(0.0, 70.0 - exam_readiness_score), 1),
            "what_if":          "Improving top 3 weak topics by 20% could add approximately 3-5 marks to your board score.",
        },
        "cached_at": datetime.now(tz.utc).isoformat(),
    }


# ── Spark: Daily 10-Question Concept Check ────────────────────────────────────

# Question mix by day of week (0=Mon … 6=Sun)
_SPARK_DAY_MIXES: dict[int, dict[str, int]] = {
    0: {"formula_recall": 4, "conceptual": 3, "trap": 3},
    1: {"formula_recall": 2, "mind_twister": 4, "scenario": 4},
    2: {"conceptual": 3, "true_false": 4, "close_call": 3},
    3: {"formula_recall": 3, "conceptual": 4, "trap": 3},
    4: {"formula_recall": 2, "mind_twister": 3, "scenario": 5},
    5: {"conceptual": 4, "formula_recall": 3, "close_call": 3},
    6: {"formula_recall": 2, "conceptual": 2, "mind_twister": 2, "trap": 2, "scenario": 2},
}

_SPARK_TYPE_GUIDE = {
    "formula_recall":  "Test if the student remembers the right formula, unit, or definition.",
    "conceptual":      "Test understanding of why/how something works — no calculation needed.",
    "trap":            "Two options look very similar (e.g. differ only in units or sign) — test careful reading.",
    "mind_twister":    "A fun, counterintuitive scenario that makes the student genuinely think.",
    "true_false":      "Phrase as MCQ with True/False/Cannot determine style options — add a 'because…' clause.",
    "scenario":        "Apply the concept to a real-world everyday situation.",
    "close_call":      "Near-identical options — only one is exactly right (e.g. formula with a subtle sign error).",
}


def get_spark_day_mix() -> dict[str, int]:
    """Return today's question-type mix (keyed by day of week)."""
    from datetime import date
    return _SPARK_DAY_MIXES[date.today().weekday()]


def call_spark_generate(
    chapter: str,
    topic: str,
    question_mix: dict[str, int],
    history_stems: list[str],
) -> list[dict]:
    """
    Generate 10 fresh MCQs for a Daily Spark session.
    Each question: {type, question, options[4], correct_index, explanation}
    Falls back to existing question_index MCQs when no AI provider is available.
    """
    if not _AVAILABLE:
        return _fallback_spark(chapter, topic)

    mix_desc = ", ".join(
        f"{count} {qtype.replace('_', ' ')}" for qtype, count in question_mix.items()
    )
    type_guide = "\n".join(
        f"- {k}: {v}" for k, v in _SPARK_TYPE_GUIDE.items() if k in question_mix
    )
    history_note = ""
    if history_stems:
        stems_list = "\n".join(f"- {s}" for s in history_stems)
        history_note = (
            f"\n\nIMPORTANT — do NOT repeat or closely paraphrase these "
            f"{len(history_stems)} previously asked questions:\n{stems_list}"
        )

    prompt = f"""You are generating a Daily Spark — a 10-question MCQ concept check for a CBSE Class 10 Science student.

Chapter: {chapter.replace('_', ' ').title()}
Topic: {topic.replace('_', ' ').title()}

Question mix today: {mix_desc}

Question type definitions:
{type_guide}

Rules:
- Exactly 10 questions, exactly 4 options each
- Tone: a favourite teacher running a fun quiz — warm, encouraging, a little playful. Make the student genuinely want to answer the next one. Never clinical or exam-like.
- Difficulty: makes him think but never panics him — no full calculations required
- Do NOT number the questions in the text{history_note}

For each question provide THREE support fields:
1. hint: A warm one-sentence nudge from a favourite teacher — specific to THIS question, activates the exact mental model needed to reason through it. Never generic ("think carefully", "remember the formula"). Must reference the actual concept, relationship, or mechanism in the question. E.g. for a resistance question: "Psst — what does the formula tell you happens to resistance when the wire gets longer?" For a photosynthesis question: "Hint: where exactly in the leaf does the light reaction happen — and why does that matter here?"
2. solution_approach: Shown after answering — the favourite teacher explaining the thinking path in 2-3 sentences. If wrong: "Good try! Here's the cool part…". If right: reinforce WHY it's right and what insight it shows. Build the mental model, not just confirm the answer.
3. explanation: One crisp sentence — why correct is correct, why the top wrong option tricks people.

Return ONLY valid JSON (no markdown, no commentary):
{{
  "questions": [
    {{
      "type": "conceptual",
      "question": "Question text here",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_index": 2,
      "hint": "Think about which variable in the formula stays constant here.",
      "solution_approach": "First identify what is given and what changes. Then apply the formula — notice that if X is fixed, increasing Y must decrease Z proportionally. That rules out two options immediately.",
      "explanation": "Correct because... Option A is tempting but wrong because..."
    }}
  ]
}}"""

    try:
        text = _call_text(prompt, max_tokens=6000)
        result = _parse_json_response(text)
        questions = result.get("questions", [])
        # Backfill hint/solution_approach if AI omitted them (graceful degradation)
        for q in questions:
            if not q.get("hint"):
                q["hint"] = ""          # empty = hide hint button in UI
            if not q.get("solution_approach"):
                q["solution_approach"] = q.get("explanation", "")
        valid = [
            q for q in questions
            if q.get("question") and len(q.get("options", [])) == 4
            and isinstance(q.get("correct_index"), int)
        ]
        hints_present = sum(1 for q in valid if q.get("hint"))
        print(f"[ai_client] call_spark_generate: {len(valid)} questions, {hints_present} with hints")
        if len(valid) >= 8:
            return valid[:10]
        print(f"[ai_client] call_spark_generate returned {len(valid)} valid questions — using fallback")
        return _fallback_spark(chapter, topic)
    except Exception as exc:
        print(f"[ai_client] call_spark_generate failed ({_PROVIDER}): {exc} — using fallback")
        return _fallback_spark(chapter, topic)


def _fallback_spark(chapter: str, topic: str) -> list[dict]:
    """
    Fallback: pull existing approved MCQs from question_index + JSON store.
    Converts them to spark format so the feature works without an AI key.
    """
    from backend.database import get_db
    from backend.services import question_loader

    conn = get_db()
    rows = conn.execute(
        """SELECT id FROM question_index
           WHERE chapter=? AND topic=? AND type='mcq' AND approved=1
           ORDER BY RANDOM() LIMIT 10""",
        (chapter, topic),
    ).fetchall()

    # Widen to full chapter if not enough topic-specific questions
    if len(rows) < 5:
        rows = conn.execute(
            """SELECT id FROM question_index
               WHERE chapter=? AND type='mcq' AND approved=1
               ORDER BY RANDOM() LIMIT 10""",
            (chapter,),
        ).fetchall()
    conn.close()

    questions = []
    for row in rows:
        q = question_loader._question_store.get(row["id"], {})
        opts = q.get("options") or []
        if len(opts) < 2:
            continue
        correct_index = next((i for i, o in enumerate(opts) if o.get("is_correct")), 0)
        explanation = (
            (q.get("rubric") or {}).get("expected_answer")
            or "Review your notes for the correct answer."
        )
        questions.append({
            "type": "conceptual",
            "question": q.get("text", ""),
            "options": [o.get("text", "") for o in opts[:4]],
            "correct_index": correct_index,
            "hint": "",   # fallback questions have no AI-generated hint
            "solution_approach": explanation,
            "explanation": explanation,
        })

    # Pad to 10 if needed
    while len(questions) < 10:
        questions.append({
            "type": "conceptual",
            "question": f"[No AI key configured — add ANTHROPIC_API_KEY / GOOGLE_API_KEY / OPENAI_API_KEY to .env for fresh Spark questions on {topic.replace('_', ' ')}.]",
            "options": ["True", "False", "Cannot determine", "Depends on context"],
            "correct_index": 0,
            "hint": "Set ANTHROPIC_API_KEY to enable AI-generated hints.",
            "solution_approach": "Set ANTHROPIC_API_KEY in your environment to enable AI-generated Spark questions.",
            "explanation": "Set ANTHROPIC_API_KEY in your environment to enable AI-generated Spark questions.",
        })

    return questions[:10]


# ── PDF Question Extraction (qbank) ───────────────────────────────────────────

def call_extract_questions_from_pdf(pdf_bytes: bytes) -> list:
    """
    Extract questions from a CBSE paper PDF for the review queue.
    Returns list of question dicts: {chapter, topic, type, difficulty, marks, text, options, rubric}
    """
    if not _AVAILABLE:
        return []

    prompt = """You are extracting questions from a CBSE Class 10 Science paper PDF.

For each question found, return a structured JSON entry.

Return ONLY valid JSON:
{
  "questions": [
    {
      "text": "Full question text",
      "type": "mcq|short|numerical|long|assertion_reason|case_based",
      "marks": 1,
      "difficulty": 2,
      "chapter": "ch01_chemical_reactions|ch02_acids_bases_salts|ch03_metals_non_metals|ch04_carbon_compounds|ch05_life_processes|ch06_control_coordination|ch07_reproduction|ch08_heredity|ch10_light|ch11_human_eye|ch12_electricity|ch13_magnetic_effects|ch15_our_environment",
      "topic": "topic_id_snake_case",
      "board_years": "2023",
      "options": [{"text": "option text", "is_correct": false}],
      "rubric": {
        "keywords": [],
        "key_points": [],
        "formula": null,
        "expected_answer": "",
        "diagram_required": false,
        "diagram_checklist": [],
        "partial_marks": {}
      }
    }
  ]
}

Rules:
- type: use mcq for multiple-choice, assertion_reason for assertion-reason, case_based for passage-based
- difficulty: 1=remember, 2=understand, 3=apply, 4=analyse, 5=evaluate
- chapter: use the exact IDs listed above; if unsure, use the closest match
- options: only populate for mcq and assertion_reason types; null otherwise
- Include ALL questions found in the PDF"""

    try:
        text = _call_with_pdf(prompt, pdf_bytes, max_tokens=4096)
        result = _parse_json_response(text)
        return result.get("questions", [])
    except Exception as exc:
        print(f"[ai_client] call_extract_questions_from_pdf failed ({_PROVIDER}): {exc}")
        return []
