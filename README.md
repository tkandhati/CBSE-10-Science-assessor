# Science Assessor

A local web application for CBSE Class 10 Science exam preparation. Covers all 13 chapters across
Chemistry, Biology, Physics, and Environmental Science. Supports three session types —
Understanding Sessions (AI-selected questions, auto-graded), Chapter Tests (PDF upload, OCR scoring),
and Full Mock Tests (complete CBSE paper pattern). Includes a student dashboard with XP and streaks,
an admin analytics view, and a question bank manager. Supports Anthropic, Google, and OpenAI as
interchangeable AI providers.

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | React + TypeScript + Tailwind CSS | React 18 / TS 5.4 / Tailwind 3.4 |
| Build tool | Vite | 5.2 |
| Backend | Python FastAPI | 0.111.0 |
| Server | Uvicorn (ASGI) | 0.29.0 |
| Database | SQLite 3 (WAL mode) | Python stdlib |
| AI | Anthropic / Google / OpenAI | claude-sonnet-4-6 / gemini-2.0-flash / gpt-4o |

## Folder Structure

```
science/
├── backend/
│   ├── main.py                  # App entry point
│   ├── database.py              # SQLite init and migrations
│   ├── analytics.py             # Analytics engine
│   ├── gamification.py          # XP, levels, badges
│   ├── requirements.txt
│   ├── routers/
│   │   ├── session.py           # Assessment sessions
│   │   ├── admin.py             # Admin dashboard
│   │   ├── qbank.py             # Question bank
│   │   └── student.py          # Student profile
│   ├── services/
│   │   ├── ai_client.py         # Multi-provider AI (Anthropic/Google/OpenAI)
│   │   ├── ai_stub.py           # Offline fallbacks
│   │   ├── paper_generator.py   # Deterministic paper generation
│   │   ├── evaluator.py         # 3-layer answer evaluation
│   │   ├── profile_updater.py   # XP and streak updates
│   │   └── question_loader.py  # In-memory question store
│   ├── scripts/
│   │   ├── import_questions.py # Legacy import (requires data/uploads/)
│   │   └── index_questions.py  # Index pre-built question JSON into SQLite
│   └── tests/                  # 99 pytest tests
├── frontend/
│   ├── src/
│   │   ├── pages/              # React page components
│   │   ├── api/client.ts       # All API calls
│   │   ├── types/              # TypeScript interfaces
│   │   └── tests/              # 30 Vitest tests
│   ├── vite.config.ts          # /api proxy → localhost:8000
│   └── package.json
├── data/
│   ├── science_assessor.db     # SQLite database (gitignored)
│   ├── config/
│   │   ├── syllabus.json       # 13-chapter curriculum
│   │   └── test_templates.json # Paper slot templates
│   ├── questions/              # Question bank JSON files (one per chapter)
│   │   ├── ch01_chemical_reactions.json    (63 questions)
│   │   ├── ch02_acids_bases_salts.json     (65 questions)
│   │   ├── ch03_metals_non_metals.json     (64 questions)
│   │   ├── ch04_carbon_compounds.json      (85 questions)
│   │   ├── ch05_life_processes.json        (85 questions)
│   │   ├── ch06_control_coordination.json  (64 questions)
│   │   ├── ch07_reproduction.json          (64 questions)
│   │   ├── ch08_heredity.json              (64 questions)
│   │   ├── ch10_light.json                 (65 questions)
│   │   ├── ch11_human_eye.json             (65 questions)
│   │   ├── ch12_electricity.json           (65 questions)
│   │   ├── ch13_magnetic_effects.json      (63 questions)
│   │   └── ch15_our_environment.json       (38 questions)
│   └── uploads/                # Runtime uploads (gitignored)
├── .gitignore
├── pytest.ini
├── run_tests.sh
└── CLAUDE.md
```

## Prerequisites

- Python 3.11+
- Node.js 18+ (LTS)
- npm 9+

## Setup

### 1. Clone

```bash
git clone <repository-url> science
cd science
```

### 2. Environment variable

Create a `.env` file in the project root with **one** AI provider key.
The app checks keys in order and uses the first non-blank one found:

```
# Option 1 — Anthropic (recommended, best PDF OCR)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx

# Option 2 — Google
# GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxx

# Option 3 — OpenAI
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The app runs without any key — AI features return deterministic fallbacks instead.

### 3. Backend

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r backend/requirements.txt
```

Index the question bank into SQLite (run once on a fresh database):

```bash
python -m backend.scripts.index_questions
```

Start the backend:

```bash
uvicorn backend.main:app --reload --app-dir .
```

Runs at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.
The startup log prints which AI provider is active, e.g. `[ai_client] Provider: Anthropic (claude-sonnet-4-6)`.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at `http://localhost:5173`. All `/api/*` requests proxy to the backend automatically.

## Environment Variables

Set **one** API key. The app uses the first non-blank key in this order: Anthropic → Google → OpenAI.

| Variable | Priority | Model | Notes |
|----------|----------|-------|-------|
| `ANTHROPIC_API_KEY` | 1st | claude-sonnet-4-6 | Recommended. Native PDF support for OCR. |
| `GOOGLE_API_KEY` | 2nd | gemini-2.0-flash | Native PDF support. Get key at aistudio.google.com. |
| `OPENAI_API_KEY` | 3rd | gpt-4o | PDF text extracted via pdfplumber before sending. Get key at platform.openai.com. |

Setting multiple keys is fine — only the highest-priority non-blank key is used. If no key is set, all AI calls (question selection, answer evaluation, PDF OCR, study guidance) return deterministic stub responses.

## Running Tests

```bash
bash run_tests.sh
```

Runs all 99 backend (pytest) and 30 frontend (Vitest) tests and reports combined pass/fail.

Run separately:

```bash
# Backend only
python -m pytest backend/tests/ -v

# Frontend only
cd frontend && npm run test
```

## Question Bank

850 approved questions across 13 chapters. Questions are stored in two places:

- **Content** (question text, options, rubric, model answer): `data/questions/{chapter}.json`
- **Metadata** (chapter, topic, type, difficulty, board weightage): `data/science_assessor.db` — `question_index` table

The question ID is the join key between the two stores.

### Adding questions via the admin UI

1. Go to `/admin/questions` → **Upload PDF** tab
2. Upload a PDF containing questions (past board papers, textbook exercises)
3. The active AI provider extracts questions and adds them to the **Review Queue**
4. Open the **Review Queue** tab — approve or reject each question
5. Approved questions are immediately available for new sessions

### Question types

`mcq`, `short` (2m), `short` (3m), `long` (5m), `numerical`, `assertion_reason`, `case_based`

## Known Gaps

- **Chapter 14 (Sources of Energy)** — no questions in the bank. This chapter is not in the CBSE 2026 Science paper syllabus and has not been prioritised.
- **Diagrams** — `data/diagrams/` is empty. Questions with `has_diagram=1` are served without their associated images.
- **OpenAI PDF OCR** — gpt-4o does not natively accept PDFs. Text is extracted via pdfplumber before sending, so handwritten answers may not OCR as accurately as with Anthropic or Google.
