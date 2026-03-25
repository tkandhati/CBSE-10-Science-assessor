"""
Deterministic chapter test paper generator (TDD Section 4.1).
Zero AI — weighted random selection from question_index.

Eight balancing constraints applied in order:
  1. Slot type and marks match exactly
  2. Difficulty distribution within ±1 question tolerance (Section 4.4)
  3. Every major topic in chapter has ≥1 question
  4. Questions weighted by board_weightage
  5. Exclude questions served in last 3 sessions of same type+chapter
  6. ×2.0 for topics where topic_scores < 60%
  7. ×0.5 for above-median times_served (rotation coverage)
  8. No duplicate question IDs across slots
"""
import json
import random
from backend.database import get_db


# ── helpers ───────────────────────────────────────────────────────────────────

def _recently_served(chapter: str, session_type: str, limit: int = 3) -> set[str]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id FROM assessments WHERE chapter=? AND type=? ORDER BY started_at DESC LIMIT ?",
        [chapter, session_type, limit],
    ).fetchall()
    if not rows:
        conn.close()
        return set()
    ids = [r[0] for r in rows]
    ph = ",".join("?" * len(ids))
    q_rows = conn.execute(
        f"SELECT DISTINCT question_id FROM answers WHERE assessment_id IN ({ph})", ids
    ).fetchall()
    conn.close()
    return {r[0] for r in q_rows}


def _all_topics(chapter: str) -> list[str]:
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT topic FROM question_index WHERE chapter=? AND approved=1", [chapter]
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def _slot_candidates(chapter: str, q_type: str, marks: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM question_index WHERE chapter=? AND type=? AND marks=? AND approved=1",
        [chapter, q_type, marks],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _topic_score(q: dict, topic_scores: dict, chapter: str) -> float:
    key = f"{chapter}.{q.get('topic', '')}"
    val = topic_scores.get(key, topic_scores.get(q.get("topic", ""), 100.0))
    if isinstance(val, list):
        val = val[-1].get("pct", 100.0) if val else 100.0
    return float(val)


def _weight(q: dict, topic_scores: dict, chapter: str, median_served: float) -> float:
    w = float(q.get("board_weightage") or 1.0)       # constraint 4
    if _topic_score(q, topic_scores, chapter) < 60.0:
        w *= 2.0                                       # constraint 6
    if (q.get("times_served") or 0) > median_served:
        w *= 0.5                                       # constraint 7
    return max(w, 0.01)


def _weighted_sample(pool: list[dict], count: int, weights: list[float],
                     exclude: set[str]) -> list[dict]:
    """Weighted random sample without replacement, skipping excluded IDs."""
    avail_q = [q for q, _ in zip(pool, weights) if q["id"] not in exclude]
    avail_w = [w for q, w in zip(pool, weights) if q["id"] not in exclude]
    chosen: list[dict] = []
    for _ in range(min(count, len(avail_q))):
        total = sum(avail_w)
        if total <= 0:
            break
        r = random.uniform(0, total)
        cum = 0.0
        pick = 0
        for i, w in enumerate(avail_w):
            cum += w
            if cum >= r:
                pick = i
                break
        chosen.append(avail_q[pick])
        avail_q.pop(pick)
        avail_w.pop(pick)
    return chosen


# ── public API ────────────────────────────────────────────────────────────────

def check_feasibility(chapter: str, template: dict) -> list[str]:
    """Return list of gap descriptions. Empty list means paper can be generated."""
    gaps = []
    for slot in template.get("slots", []):
        q_type = slot["type"]
        marks = slot["marks"]
        need = slot.get("count", slot.get("count_min", 1))
        pool = _slot_candidates(chapter, q_type, marks)
        if len(pool) < need:
            gaps.append(
                f"Slot {slot.get('slot', q_type)}: need {need}× {q_type} "
                f"({marks}m) but only {len(pool)} approved questions available"
            )
    return gaps


def generate_test_paper(
    chapter: str,
    session_type: str,
    template: dict,
    topic_scores: dict,
) -> dict:
    """
    Returns {"selected_ids": [...], "generated_params": {}}.
    Raises ValueError with "FEASIBILITY_FAIL:<json_gaps>" on infeasibility.
    """
    gaps = check_feasibility(chapter, template)
    if gaps:
        raise ValueError("FEASIBILITY_FAIL:" + json.dumps(gaps))

    served = _recently_served(chapter, session_type)   # constraint 5
    all_topics = set(_all_topics(chapter))
    diff_key_map = {f"L{i}": i for i in range(1, 6)}
    difficulty_mix: dict = template.get("difficulty_mix", {})

    selected: list[dict] = []

    # ── Per-slot selection ─────────────────────────────────────────────────
    for slot in template.get("slots", []):
        q_type = slot["type"]
        marks = slot["marks"]
        count = slot.get("count", slot.get("count_min", 1))

        pool = _slot_candidates(chapter, q_type, marks)
        usable = [q for q in pool if q["id"] not in served]
        if len(usable) < count:
            usable = pool  # relax anti-repetition if pool too small

        vals = sorted((q.get("times_served") or 0) for q in usable)
        median = vals[len(vals) // 2] if vals else 0

        already = {q["id"] for q in selected}
        wts = [_weight(q, topic_scores, chapter, median) for q in usable]
        chosen = _weighted_sample(usable, count, wts, already)  # constraints 4,6,7,8
        selected.extend(chosen)

    # ── Repair pass — max 3 iterations ────────────────────────────────────
    for _ in range(3):
        fixed = False

        # Constraint 2: difficulty distribution (±1 tolerance)
        total_q = len(selected)
        exp: dict[int, int] = {
            diff_key_map[k]: round(v * total_q)
            for k, v in difficulty_mix.items()
            if k in diff_key_map
        }
        actual: dict[int, int] = {}
        for q in selected:
            d = int(q.get("difficulty") or 1)
            actual[d] = actual.get(d, 0) + 1

        for lvl, want in exp.items():
            have = actual.get(lvl, 0)
            if abs(have - want) <= 1:
                continue
            # Need more of this level — find a victim from an over-represented level
            over = [lv for lv, cnt in actual.items() if cnt > exp.get(lv, 0) + 1]
            victims = [q for q in selected if (q.get("difficulty") or 1) in (over or [lvl + 1])]
            if not victims:
                continue
            victim = random.choice(victims)
            pool = _slot_candidates(chapter, victim["type"], victim["marks"])
            candidates = [
                q for q in pool
                if (q.get("difficulty") or 1) == lvl
                and q["id"] not in {s["id"] for s in selected if s["id"] != victim["id"]}
            ]
            if candidates:
                selected[selected.index(victim)] = random.choice(candidates)
                fixed = True

        # Constraint 3: every major topic covered
        covered = {q.get("topic") for q in selected}
        for miss in all_topics - covered:
            for slot in template.get("slots", []):
                conn = get_db()
                rows = conn.execute(
                    "SELECT * FROM question_index "
                    "WHERE chapter=? AND topic=? AND type=? AND marks=? AND approved=1 LIMIT 10",
                    [chapter, miss, slot["type"], slot["marks"]],
                ).fetchall()
                conn.close()
                candidates = [
                    dict(r) for r in rows
                    if r["id"] not in {q["id"] for q in selected}
                ]
                if not candidates:
                    continue
                # Replace highest-served question in same slot
                slot_qs = [
                    q for q in selected
                    if q["type"] == slot["type"] and q["marks"] == slot["marks"]
                ]
                if slot_qs:
                    victim = max(slot_qs, key=lambda q: q.get("times_served") or 0)
                    selected[selected.index(victim)] = random.choice(candidates)
                    fixed = True
                    break

        if not fixed:
            break

    return {"selected_ids": [q["id"] for q in selected], "generated_params": {}}


# ── Mock paper constants — all 13 Science chapters ────────────────────────────

_MOCK_CHAPTERS = [
    "ch01_chemical_reactions", "ch02_acids_bases_salts",
    "ch03_metals_non_metals",  "ch04_carbon_compounds",
    "ch05_life_processes",     "ch06_control_coordination",
    "ch07_reproduction",       "ch08_heredity",
    "ch10_light",              "ch11_human_eye",
    "ch12_electricity",        "ch13_magnetic_effects",
    "ch15_our_environment",
]
_MOCK_CHAPTER_WEIGHTS = {
    "ch01_chemical_reactions":   7,
    "ch02_acids_bases_salts":    6,
    "ch03_metals_non_metals":    7,
    "ch04_carbon_compounds":     7,
    "ch05_life_processes":       7,
    "ch06_control_coordination": 6,
    "ch07_reproduction":         5,
    "ch08_heredity":             9,
    "ch10_light":                7,
    "ch11_human_eye":            5,
    "ch12_electricity":          8,
    "ch13_magnetic_effects":     7,
    "ch15_our_environment":      3,
}
_MOCK_TOTAL_WEIGHT = sum(_MOCK_CHAPTER_WEIGHTS.values())  # 84


def _allocate_by_weight(chapters: list, weights: dict, total_count: int) -> dict:
    """
    Distribute total_count questions across chapters proportionally by weight.
    Uses largest-remainder method to ensure allocations sum to total_count.
    """
    total_w = sum(weights.get(c, 0) for c in chapters)
    if total_w == 0:
        n = len(chapters)
        base = total_count // n
        alloc = {c: base for c in chapters}
        for i in range(total_count - base * n):
            alloc[chapters[i]] += 1
        return alloc

    raw = {c: weights.get(c, 0) / total_w * total_count for c in chapters}
    alloc = {c: int(raw[c]) for c in chapters}
    remainder = total_count - sum(alloc.values())
    fracs = sorted(chapters, key=lambda c: raw[c] - int(raw[c]), reverse=True)
    for c in fracs[:remainder]:
        alloc[c] += 1
    return alloc


def check_mock_feasibility(template: dict) -> list:
    """
    Check if question bank has enough approved questions for a full mock across all 5 chapters.
    Returns list of gap descriptions (empty = feasible).
    Flags missing assertion_reason and case_based per chapter as admin alerts.
    """
    gaps = []
    for section_def in template.get("sections", []):
        section = section_def["section"]
        for slot in section_def["slots"]:
            q_type = slot["type"]
            marks = slot["marks"]
            total_needed = slot["count"]

            total_available = 0
            for chapter in _MOCK_CHAPTERS:
                pool = _slot_candidates(chapter, q_type, marks)
                total_available += len(pool)

            if total_available < total_needed:
                chapter_counts = {
                    ch: len(_slot_candidates(ch, q_type, marks)) for ch in _MOCK_CHAPTERS
                }
                zero_chs = [ch for ch, cnt in chapter_counts.items() if cnt == 0]
                gaps.append(
                    f"Section {section} {q_type}({marks}m): need {total_needed}, "
                    f"only {total_available} available. "
                    + (f"Chapters with none: {', '.join(zero_chs)}." if zero_chs else "")
                )

            # Warn admin about chapters missing special question types
            if q_type in ("assertion_reason", "case_based"):
                for chapter in _MOCK_CHAPTERS:
                    pool = _slot_candidates(chapter, q_type, marks)
                    if len(pool) == 0:
                        gaps.append(
                            f"ADMIN ALERT — Section {section}: chapter '{chapter}' has 0 approved "
                            f"{q_type} questions. Add questions or this chapter will be skipped."
                        )
    return gaps


def generate_mock_paper(session_type: str, template: dict, topic_scores: dict) -> dict:
    """
    Generate a full mock paper across all 5 physics chapters.
    Returns {"selected_ids": [...], "generated_params": {}, "section_map": {qid: section_letter}}.
    """
    served = _recently_served("all", session_type)  # anti-repetition across mock sessions
    diff_key_map = {f"L{i}": i for i in range(1, 6)}
    difficulty_mix: dict = template.get("difficulty_mix", {})

    selected: list = []          # list of question_index dicts, each gets a "section" key added
    section_map: dict = {}       # qid → section letter

    for section_def in template.get("sections", []):
        section = section_def["section"]

        for slot in section_def["slots"]:
            q_type = slot["type"]
            marks = slot["marks"]
            total_count = slot["count"]

            # Pool per chapter (fetched once)
            chapter_pools = {ch: _slot_candidates(ch, q_type, marks) for ch in _MOCK_CHAPTERS}
            chapters_with_qs = [ch for ch in _MOCK_CHAPTERS if chapter_pools[ch]]

            # Proportional allocation across chapters that actually have questions
            allocations = _allocate_by_weight(
                chapters_with_qs, _MOCK_CHAPTER_WEIGHTS, total_count
            )

            already_ids = {q["id"] for q in selected}
            section_selected: list = []

            for chapter in _MOCK_CHAPTERS:
                count = allocations.get(chapter, 0)
                if count == 0:
                    continue
                pool = chapter_pools[chapter]
                usable = [q for q in pool if q["id"] not in served]
                if len(usable) < count:
                    usable = pool  # relax anti-repetition if pool too small

                if not usable:
                    continue

                vals = sorted((q.get("times_served") or 0) for q in usable)
                median = vals[len(vals) // 2] if vals else 0
                exclude = already_ids | {q["id"] for q in section_selected}
                wts = [_weight(q, topic_scores, chapter, median) for q in usable]
                chosen = _weighted_sample(usable, count, wts, exclude)
                for q in chosen:
                    q_entry = dict(q)
                    q_entry["_section"] = section
                    section_selected.append(q_entry)
                    already_ids.add(q["id"])

            # Fill any gap caused by chapters with no questions for this slot
            gap = total_count - len(section_selected)
            if gap > 0:
                for chapter in sorted(_MOCK_CHAPTERS, key=lambda c: -_MOCK_CHAPTER_WEIGHTS.get(c, 0)):
                    if gap <= 0:
                        break
                    pool = chapter_pools[chapter]
                    usable = [q for q in pool if q["id"] not in {e["id"] for e in section_selected} | already_ids]
                    if not usable:
                        continue
                    vals = sorted((q.get("times_served") or 0) for q in usable)
                    median = vals[len(vals) // 2] if vals else 0
                    wts = [_weight(q, topic_scores, chapter, median) for q in usable]
                    chosen = _weighted_sample(usable, min(gap, len(usable)), wts, set())
                    for q in chosen:
                        q_entry = dict(q)
                        q_entry["_section"] = section
                        section_selected.append(q_entry)
                        gap -= 1

            selected.extend(section_selected)

    # ── Repair pass — max 3 iterations ────────────────────────────────────
    # Note: section assignment (q["_section"]) is carried through the repair pass
    # and section_map is rebuilt from the final selected list at the end.

    total_q = len(selected)
    exp: dict = {
        diff_key_map[k]: round(v * total_q)
        for k, v in difficulty_mix.items()
        if k in diff_key_map
    }

    for _ in range(3):
        fixed = False

        # Constraint 2: difficulty distribution (±1 tolerance)
        actual: dict = {}
        for q in selected:
            d = int(q.get("difficulty") or 1)
            actual[d] = actual.get(d, 0) + 1

        for lvl, want in exp.items():
            have = actual.get(lvl, 0)
            if abs(have - want) <= 1:
                continue
            over = [lv for lv, cnt in actual.items() if cnt > exp.get(lv, 0) + 1]
            victims = [q for q in selected if (q.get("difficulty") or 1) in (over or [lvl + 1])]
            if not victims:
                continue
            victim = random.choice(victims)
            victim_ch = victim.get("chapter", _MOCK_CHAPTERS[0])
            pool = _slot_candidates(victim_ch, victim["type"], victim["marks"])
            candidates = [
                q for q in pool
                if (q.get("difficulty") or 1) == lvl
                and q["id"] not in {s["id"] for s in selected if s["id"] != victim["id"]}
            ]
            if candidates:
                replacement = dict(random.choice(candidates))
                replacement["_section"] = victim.get("_section", "A")  # preserve section
                selected[selected.index(victim)] = replacement
                fixed = True

        # Constraint 3: every chapter covered at least once in the full paper
        covered_chapters = {q.get("chapter") for q in selected}
        for missing_ch in set(_MOCK_CHAPTERS) - covered_chapters:
            for section_def in template.get("sections", []):
                replaced = False
                for slot in section_def["slots"]:
                    pool = _slot_candidates(missing_ch, slot["type"], slot["marks"])
                    if not pool:
                        continue
                    slot_qs = [
                        q for q in selected
                        if q["type"] == slot["type"] and q["marks"] == slot["marks"]
                    ]
                    if not slot_qs:
                        continue
                    victim = max(slot_qs, key=lambda q: q.get("times_served") or 0)
                    candidates = [
                        q for q in pool
                        if q["id"] not in {s["id"] for s in selected if s["id"] != victim["id"]}
                    ]
                    if not candidates:
                        continue
                    replacement = dict(random.choice(candidates))
                    replacement["_section"] = victim.get("_section", section_def["section"])
                    selected[selected.index(victim)] = replacement
                    fixed = True
                    replaced = True
                    break
                if replaced:
                    break

        if not fixed:
            break

    # Build section_map from final selected list (after all repairs)
    section_map = {q["id"]: q.get("_section", "A") for q in selected}

    return {
        "selected_ids": [q["id"] for q in selected],
        "generated_params": {},
        "section_map": section_map,
    }
