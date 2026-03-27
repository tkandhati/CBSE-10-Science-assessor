import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from backend.database import init_db, get_db
from backend.services.question_loader import load_all_questions
from backend.routers import session, admin, qbank, student, spark


def _expire_stale_sessions() -> int:
    """Mark expired sessions synchronously. Returns count expired."""
    conn = get_db()
    cur = conn.execute(
        """UPDATE assessments
           SET status='expired', is_active=0
           WHERE expires_at < datetime('now')
             AND status IN ('in_progress', 'awaiting_upload')"""
    )
    n = cur.rowcount
    conn.commit()
    conn.close()
    if n:
        print(f"[expiry] Marked {n} session(s) as expired.")
    return n


async def _expiry_loop():
    """Background task: run expiry check every hour."""
    while True:
        await asyncio.sleep(3600)
        try:
            _expire_stale_sessions()
        except Exception as exc:
            print(f"[expiry] Error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_all_questions()
    _expire_stale_sessions()           # run once on startup
    task = asyncio.create_task(_expiry_loop())
    yield
    task.cancel()


app = FastAPI(title="Physics Assessor API", version="1.0.0", lifespan=lifespan)

DIAGRAMS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "diagrams")
app.mount("/diagrams", StaticFiles(directory=DIAGRAMS_DIR), name="diagrams")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(admin.router)
app.include_router(qbank.router)
app.include_router(student.router)
app.include_router(spark.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/syllabus")
def get_syllabus():
    path = Path(__file__).parent.parent / "data" / "config" / "syllabus.json"
    return json.loads(path.read_text(encoding="utf-8"))
