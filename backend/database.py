import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "science_assessor.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS question_index (
        id                TEXT PRIMARY KEY,
        chapter           TEXT NOT NULL,
        topic             TEXT NOT NULL,
        type              TEXT NOT NULL,
        difficulty        INTEGER NOT NULL,
        marks             INTEGER NOT NULL,
        board_weightage   REAL    DEFAULT 0.0,
        source            TEXT    DEFAULT '',
        board_years       TEXT    DEFAULT '',
        has_diagram       BOOLEAN DEFAULT 0,
        has_template      BOOLEAN DEFAULT 0,
        times_served      INTEGER DEFAULT 0,
        last_served_at    DATETIME,
        approved          BOOLEAN DEFAULT 0,
        tags              TEXT    DEFAULT ''
    );

    CREATE INDEX IF NOT EXISTS idx_question_filter
        ON question_index (chapter, topic, type, difficulty, approved);

    CREATE INDEX IF NOT EXISTS idx_question_rotation
        ON question_index (times_served, last_served_at);

    CREATE TABLE IF NOT EXISTS assessments (
        id                TEXT PRIMARY KEY,
        type              TEXT    NOT NULL,
        chapter           TEXT    NOT NULL,
        topic             TEXT,
        question_ids      JSON    NOT NULL DEFAULT '[]',
        generated_params  JSON,
        total_marks       INTEGER NOT NULL DEFAULT 0,
        score_obtained    REAL    DEFAULT 0,
        percentage        REAL    DEFAULT 0,
        duration_seconds  INTEGER DEFAULT 0,
        status            TEXT    NOT NULL DEFAULT 'in_progress',
        answer_pdf_path   TEXT,
        started_at        DATETIME NOT NULL,
        completed_at      DATETIME,
        expires_at        DATETIME,
        is_active         BOOLEAN DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS answers (
        id                TEXT PRIMARY KEY,
        assessment_id     TEXT    NOT NULL REFERENCES assessments(id),
        question_id       TEXT    NOT NULL REFERENCES question_index(id),
        answer_text       TEXT    DEFAULT '',
        selected_option   INTEGER,
        ocr_confidence    REAL,
        ocr_text          TEXT,
        score             REAL    DEFAULT 0,
        max_marks         INTEGER NOT NULL,
        evaluation_layer  TEXT    DEFAULT 'deterministic',
        feedback          JSON,
        suggestions       JSON,
        time_seconds      INTEGER DEFAULT 0,
        is_correct        BOOLEAN DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS student_profile (
        id                  INTEGER PRIMARY KEY DEFAULT 1,
        name                TEXT    NOT NULL DEFAULT 'Student',
        total_xp            INTEGER DEFAULT 0,
        current_streak      INTEGER DEFAULT 0,
        best_streak         INTEGER DEFAULT 0,
        last_active_date    DATE,
        topic_scores        JSON    DEFAULT '{}',
        topic_attempts      JSON    DEFAULT '{}',
        topic_last_tested   JSON    DEFAULT '{}',
        numerical_mastery   JSON    DEFAULT '{}',
        badges              JSON    DEFAULT '[]',
        guidance_cache      JSON,
        guidance_cached_at  DATETIME
    );

    CREATE TABLE IF NOT EXISTS review_queue (
        id          TEXT PRIMARY KEY,
        chapter     TEXT NOT NULL,
        topic       TEXT NOT NULL,
        type        TEXT NOT NULL,
        difficulty  INTEGER NOT NULL DEFAULT 2,
        marks       INTEGER NOT NULL DEFAULT 2,
        text        TEXT NOT NULL DEFAULT '',
        options     JSON,
        rubric      JSON,
        source      TEXT DEFAULT '',
        board_years TEXT DEFAULT '',
        tags        TEXT DEFAULT '',
        added_at    DATETIME NOT NULL,
        status      TEXT NOT NULL DEFAULT 'pending'
    );
    """)

    # Seed student profile row if not exists
    cur.execute("INSERT OR IGNORE INTO student_profile (id, name) VALUES (1, 'Student')")

    # Phase 4 migrations — safe to run repeatedly (ignored if column exists)
    _migrations = [
        "ALTER TABLE student_profile ADD COLUMN exam_readiness_score REAL DEFAULT 0.0",
        "ALTER TABLE assessments ADD COLUMN section_map JSON DEFAULT '{}'",
        "ALTER TABLE assessments ADD COLUMN overall_guidance TEXT DEFAULT ''",
        # Phase 5 — admin score override
        "ALTER TABLE answers ADD COLUMN override_score REAL",
        "ALTER TABLE answers ADD COLUMN override_note  TEXT DEFAULT ''",
        # Phase 6
        "ALTER TABLE student_profile ADD COLUMN badges JSON DEFAULT '[]'",
    ]
    for _m in _migrations:
        try:
            cur.execute(_m)
        except Exception:
            pass  # column already exists

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")
