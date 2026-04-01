"""
generate_hints.py — One-time script to generate LLM-crafted hints for all questions.

Usage:
    python -m backend.scripts.generate_hints [--force] [--chapter ch10_light]

Options:
    --force      Overwrite existing hints (default: skip questions that already have one)
    --chapter    Process only this chapter file (default: all chapters)

Requires at least one API key in environment:
    ANTHROPIC_API_KEY  (preferred)
    GOOGLE_API_KEY
    OPENAI_API_KEY

What it does:
    For each question with key_points, calls LLM in batches of 20 to generate
    a nudge-style hint (1 sentence, ≤15 words, does NOT give the answer away).
    Saves the hint into rubric.hint in the question JSON file.

Run once after setup. Re-run with --force to refresh all hints.
Safe to interrupt — saves after each chapter.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT          = Path(__file__).parent.parent.parent
QUESTIONS_DIR = ROOT / "data" / "questions"

BATCH_SIZE = 20   # questions per LLM call

# ── Provider setup ─────────────────────────────────────────────────────────────

def _init_provider():
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    google_key    = os.environ.get("GOOGLE_API_KEY",    "").strip()
    openai_key    = os.environ.get("OPENAI_API_KEY",    "").strip()

    if anthropic_key:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=anthropic_key)
            print("[hints] Provider: Anthropic (claude-haiku-4-5-20251001)")
            return "anthropic", client
        except Exception as e:
            print(f"[hints] Anthropic init failed: {e}")

    if google_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=google_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            print("[hints] Provider: Google (gemini-2.0-flash)")
            return "google", model
        except Exception as e:
            print(f"[hints] Google init failed: {e}")

    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            print("[hints] Provider: OpenAI (gpt-4o-mini)")
            return "openai", client
        except Exception as e:
            print(f"[hints] OpenAI init failed: {e}")

    return None, None


def _call_llm(provider, client, prompt: str) -> str:
    if provider == "anthropic":
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    if provider == "google":
        resp = client.generate_content(prompt)
        return resp.text

    if provider == "openai":
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

    raise RuntimeError("No provider")


# ── Prompt builder ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are helping a CBSE Class 10 Science student (age 15-16) who is stuck on a question.
Write a SHORT hint for each question — exactly 1 sentence, maximum 15 words.

Rules:
- Start with "Think about:", "Remember:", or "Recall:"
- Nudge the student toward the concept WITHOUT giving the answer away
- Use simple, encouraging language
- Do not mention the answer or correct option directly

Return ONLY a valid JSON array. No markdown, no explanation. Format:
[{"id": "q_id", "hint": "Think about: ..."}]
"""

def _build_prompt(batch: list[dict]) -> str:
    questions_json = json.dumps(
        [
            {
                "id":         q["id"],
                "topic":      q.get("topic", ""),
                "text":       q["text"][:200],
                "key_points": (q.get("rubric") or {}).get("key_points", [])[:3],
            }
            for q in batch
        ],
        indent=2,
        ensure_ascii=False,
    )
    return f"{_SYSTEM_PROMPT}\n\nQuestions:\n{questions_json}"


# ── JSON extraction ─────────────────────────────────────────────────────────────

def _extract_json(text: str) -> list[dict]:
    """Extract JSON array from LLM response, tolerating markdown fences."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    return json.loads(text)


# ── Core processing ─────────────────────────────────────────────────────────────

def process_chapter(chapter_file: Path, provider, client, force: bool) -> tuple[int, int]:
    """
    Process one chapter file. Returns (hints_added, hints_skipped).
    """
    data = json.load(open(chapter_file, encoding="utf-8"))
    questions = data["questions"]

    # Decide which questions need hints
    to_process = []
    for q in questions:
        rubric = q.get("rubric") or {}
        already_has_hint = bool(rubric.get("hint", "").strip())
        has_key_points   = bool(rubric.get("key_points"))
        has_text         = bool(q.get("text", "").strip())

        if already_has_hint and not force:
            continue
        if not has_key_points and not has_text:
            continue  # nothing to work with

        to_process.append(q)

    skipped = len(questions) - len(to_process)
    added   = 0

    if not to_process:
        print(f"  {chapter_file.name}: all {len(questions)} questions already have hints — skipped")
        return 0, skipped

    print(f"  {chapter_file.name}: generating hints for {len(to_process)}/{len(questions)} questions...")

    # Build a lookup for quick update
    q_by_id = {q["id"]: q for q in questions}

    # Process in batches
    for batch_start in range(0, len(to_process), BATCH_SIZE):
        batch = to_process[batch_start: batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(to_process) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"    Batch {batch_num}/{total_batches} ({len(batch)} questions)...", end=" ", flush=True)

        try:
            prompt   = _build_prompt(batch)
            response = _call_llm(provider, client, prompt)
            results  = _extract_json(response)

            for item in results:
                qid  = item.get("id")
                hint = (item.get("hint") or "").strip()
                if qid and hint and qid in q_by_id:
                    q = q_by_id[qid]
                    if q.get("rubric") is None:
                        q["rubric"] = {}
                    q["rubric"]["hint"] = hint
                    added += 1

            print(f"OK ({len(results)} hints)")

        except Exception as e:
            print(f"ERROR — {e}")
            print("      Skipping batch and continuing...")

        # Polite rate-limit pause between batches
        if batch_start + BATCH_SIZE < len(to_process):
            time.sleep(0.5)

    # Save the updated file
    json.dump(data, open(chapter_file, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"  Saved {chapter_file.name}  ({added} hints written)")

    return added, skipped


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate LLM hints for all questions")
    parser.add_argument("--force",   action="store_true", help="Overwrite existing hints")
    parser.add_argument("--chapter", type=str,            help="Process only this chapter (e.g. ch10_light)")
    args = parser.parse_args()

    provider, client = _init_provider()
    if provider is None:
        print("[hints] ERROR: No API key found. Set ANTHROPIC_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY.")
        sys.exit(1)

    # Collect files to process
    if args.chapter:
        pattern = f"{args.chapter}.json"
        files = list(QUESTIONS_DIR.glob(pattern))
        if not files:
            print(f"[hints] ERROR: No file matching {pattern} in {QUESTIONS_DIR}")
            sys.exit(1)
    else:
        files = sorted(QUESTIONS_DIR.glob("*.json"))

    print(f"\n[hints] Processing {len(files)} chapter file(s)  force={args.force}\n")

    total_added   = 0
    total_skipped = 0

    for f in files:
        added, skipped = process_chapter(f, provider, client, args.force)
        total_added   += added
        total_skipped += skipped

    print(f"\n[hints] Done.  Hints written: {total_added}  Already had hints: {total_skipped}")
    print("[hints] Re-run index_questions to refresh SQLite if needed.")


if __name__ == "__main__":
    main()
