# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Science Assessor — a web-based CBSE Class 10 Science Assessment Platform covering all 13 chapters across Physics, Chemistry, and Biology for a single student.
Stack: React + TypeScript + Tailwind (frontend), Python FastAPI (backend), SQLite (database), Claude API (AI).

## Running the project

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --app-dir ..

# Index questions into SQLite (run once after setup)
python -m backend.scripts.index_questions

# Frontend
cd frontend
npm install
npm run dev
```

## Architecture

### Hybrid storage (critical — do not change)
- **Question content** (text, options, rubric, template_params, diagram_path) lives in `data/questions/{chapter_id}.json`
- **Question metadata** (chapter, topic, type, difficulty, marks, usage stats) is indexed in SQLite `question_index`
- **The question ID is the join key** between JSON and SQLite — never put content in SQLite, never put metadata in JSON

### SQLite tables
| Table | Purpose |
|---|---|
| `question_index` | Metadata + usage stats for every question |
| `assessments` | One row per session (Understanding / Chapter Test / Mock / Spark) |
| `answers` | One row per question answer within a session |
| `student_profile` | Single row (id=1) — XP, streaks, topic scores, guidance cache |
| `spark_history` | Question stems asked in past Spark sessions — used to prevent repetition |

#### `assessments.spark_questions` (Spark only)
Spark sessions store their AI-generated questions directly on the assessments row as JSON (`spark_questions` column). Spark does **not** use `question_index` or `answers` — questions are fully AI-generated and ephemeral.

### Key indexes on `question_index`
- `(chapter, topic, type, difficulty, approved)` — fast paper generation queries
- `(times_served, last_served_at)` — anti-repetition rotation

### AI calls — strict 2-call budget per session (+ 1 for Spark)
- **Understanding**: Call 1 = question selection + fresh numericals; Call 2 = evaluate subjective answers
- **Chapter Test / Mock**: Call 1 = PDF OCR + intelligent split; Call 2 = score + improvement suggestions
- **Daily Spark**: 1 AI call per session — generates all 10 MCQs + explanations upfront; outside the 2-call session budget
- Paper generation (Chapter Test / Mock) is **deterministic — no AI**
- All AI calls are stubbed in `backend/services/ai_stub.py` — replace stubs in Phase 2

### 13 chapters
| ID | Title | Subject | NCERT Ch | Board Marks |
|---|---|---|---|---|
| `ch01_chemical_reactions` | Chemical Reactions and Equations | Chemistry | 1 | 7 |
| `ch02_acids_bases_salts` | Acids, Bases and Salts | Chemistry | 2 | 6 |
| `ch03_metals_non_metals` | Metals and Non-Metals | Chemistry | 3 | 7 |
| `ch04_carbon_compounds` | Carbon and its Compounds | Chemistry | 4 | 7 |
| `ch05_life_processes` | Life Processes | Biology | 6 | 7 |
| `ch06_control_coordination` | Control and Coordination | Biology | 7 | 6 |
| `ch07_reproduction` | How do Organisms Reproduce? | Biology | 8 | 5 |
| `ch08_heredity` | Heredity and Evolution | Biology | 9 | 9 |
| `ch10_light` | Light — Reflection and Refraction | Physics | 10 | 7 |
| `ch11_human_eye` | The Human Eye and the Colourful World | Physics | 11 | 5 |
| `ch12_electricity` | Electricity | Physics | 12 | 8 |
| `ch13_magnetic_effects` | Magnetic Effects of Current | Physics | 13 | 7 |
| `ch15_our_environment` | Our Environment | Environmental Science | 15 | 3 |

Total board marks: 84 (Chemistry 27 + Biology 27 + Physics 27 + Env Science 3)

## Existing question data
- Ch01–Ch08 and Ch10–Ch13 questions are in TDD schema under `data/questions/`
- Ch15 (Our Environment) questions are in `data/questions/ch15_our_environment.json` — 38 questions
- Note: the file previously named `sources_of_energy.json` contained Our Environment questions and has been corrected

## Build phases
- **Phase 1** (complete): folder structure, DB schema, JSON stubs, FastAPI skeleton, React skeleton, import script
- **Phase 2** (complete): Understanding Sessions — real AI question selection, session flow, auto-grading, feedback
- **Phase 3** (complete): Chapter Tests — balanced paper generation, PDF upload, Claude Vision OCR, evaluation
- **Phase 4** (complete): Full Mock Test — CBSE 2026 paper pattern, 3-hour session, comprehensive results
- **Spark** (complete): Daily Spark micro-mode — 10 AI-generated MCQs, topic rotation by attempts, anti-repetition via stem history, day-based question mix

## Daily Spark feature
- Route: `GET /api/spark/today`, `POST /api/spark/start`, `POST /api/spark/{id}/complete`
- Topic rotation: picks topic with fewest `topic_attempts`; tie-break by oldest `topic_last_tested`
- Anti-repetition: last 30 question stems per topic stored in `spark_history` and passed to AI prompt
- Question mix varies by day of week (7 different mixes — formula recall / conceptual / traps / mind-twisters / scenarios)
- Fallback (no AI key): pulls real MCQs from `question_index` and converts them to Spark format
- Completion credits streak + 10 XP per correct answer
- Dashboard shows a Spark banner (green = done today, amber = not yet done)

## Board Exam Countdown Widget
- Route: `GET /api/student/countdown`
- Exam date hardcoded: 2026-12-31
- Projected score auto-calculated from `analytics.get_exam_readiness()` — out of 84 board marks, no student input
- Pace label derived from session frequency over last 28 days: Getting Started / Behind / On Track / Ahead
- Weekly targets: 2 Understanding Sessions + 1 Chapter Test (Mon–Sun window)
- Weekly done count queries `assessments` table filtered by this week and type
- Advice line tells exactly what's left to hit the weekly target
- Shown as a slim card on the dashboard between the Spark banner and Quick Start

## Understanding Session — diagram question exclusion
- `question_selector.py`: `select_candidates()` passes `exclude_diagram=True` when `session_type="understanding"`
- `get_eligible_questions()` adds `AND has_diagram=0` to the SQL query when `exclude_diagram=True`
- `index_questions.py`: `requires_diagram()` detects both `diagram_path` presence AND draw/sketch keywords in question text
- Re-run `python -m backend.scripts.index_questions` after any question data change to refresh flags
- Chapter Tests and Mock Tests are unaffected — diagram questions remain eligible there
