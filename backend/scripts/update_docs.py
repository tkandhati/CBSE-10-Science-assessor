"""
Pre-push documentation updater + gitignore validator.

Called by .githooks/pre-push on every git push.
Only touches doc sections relevant to what actually changed.
Never blocks the push — always exits 0.

Sections auto-updated:
  README.md  — question counts per chapter  (data/questions/*.json changed)
  README.md  — total question count         (any question file changed)
  .gitignore — missing patterns             (new file matches a should-ignore rule)

Warnings only (needs human judgment):
  CLAUDE.md  — SQLite tables section        (backend/database.py changed)
  README.md  — router file list             (backend/routers/*.py changed)
  CLAUDE.md  — AI calls section             (backend/services/ai_client.py changed)
  tracked files that should be ignored      (already committed, needs git rm --cached)
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # .../science/
CLAUDE_MD = ROOT / "CLAUDE.md"
README_MD = ROOT / "README.md"
QUESTIONS_DIR = ROOT / "data" / "questions"


GITIGNORE = ROOT / ".gitignore"

# Patterns: (regex to match file path, gitignore pattern to add, reason)
_SHOULD_IGNORE: list[tuple[str, str, str]] = [
    (r"\.log$",                  "*.log",              "log file"),
    (r"\.tmp$",                  "*.tmp",              "temp file"),
    (r"\.bak$",                  "*.bak",              "backup file"),
    (r"(^|/)__pycache__/",       "__pycache__/",       "Python cache"),
    (r"\.py[cod]$",              "*.py[cod]",          "compiled Python"),
    (r"(^|/)\.pytest_cache/",    ".pytest_cache/",     "pytest cache"),
    (r"(^|/)node_modules/",      "node_modules/",      "Node dependencies"),
    (r"(^|/)dist/",              "dist/",              "build output"),
    (r"(^|/)build/",             "build/",             "build output"),
    (r"(^|/)htmlcov/",           "htmlcov/",           "coverage report"),
    (r"\.coverage$",             ".coverage",          "coverage data"),
    (r"coverage\.xml$",          "coverage.xml",       "coverage report"),
    (r"\.db$",                   "*.db",               "SQLite database"),
    (r"\.db-shm$",               "*.db-shm",           "SQLite WAL file"),
    (r"\.db-wal$",               "*.db-wal",           "SQLite WAL file"),
    (r"(^|/)data/uploads/",      "data/uploads/",      "runtime uploads"),
    (r"\.env$",                  ".env",               "secrets file"),
    (r"\.env\.local$",           ".env.local",         "secrets file"),
    (r"\.DS_Store$",             ".DS_Store",          "macOS metadata"),
    (r"Thumbs\.db$",             "Thumbs.db",          "Windows thumbnail cache"),
    (r"\.swp$",                  "*.swp",              "Vim swap file"),
    (r"(^|/)\.(vscode|idea)/",   ".vscode/\n.idea/",   "IDE config"),
    (r"(^|/)\.venv/",            ".venv/",             "Python virtual env"),
]


# ── Changed files ─────────────────────────────────────────────────────────────

def get_changed_files() -> list[str]:
    """Return files changed in commits about to be pushed."""
    for cmd in (
        ["git", "diff", "--name-only", "@{u}..HEAD"],
        ["git", "diff", "--name-only", "HEAD~1..HEAD"],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()
        except Exception:
            pass
    return []


def get_added_files() -> list[str]:
    """Return only newly added files (A = Added) in commits about to be pushed."""
    for cmd in (
        ["git", "diff", "--name-only", "--diff-filter=A", "@{u}..HEAD"],
        ["git", "diff", "--name-only", "--diff-filter=A", "HEAD~1..HEAD"],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()
        except Exception:
            pass
    return []


# ── Auto-update: question counts (README.md) ──────────────────────────────────

def update_question_counts(changed: list[str]) -> bool:
    changed_q = [f for f in changed if f.startswith("data/questions/") and f.endswith(".json")]
    if not changed_q:
        return False

    readme = README_MD.read_text(encoding="utf-8")
    updated = False

    for rel in changed_q:
        path = ROOT / rel
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            count = len(data) if isinstance(data, list) else len(data.get("questions", []))
        except Exception:
            continue

        pattern = rf"({re.escape(path.name)}\s+)\(\d+ questions\)"
        new_readme, n = re.subn(pattern, rf"\g<1>({count} questions)", readme)
        if n and new_readme != readme:
            readme = new_readme
            updated = True
            print(f"  [docs] {path.name}: question count → {count}")

    if not updated:
        return False

    # Also refresh total question count
    total = 0
    for qf in QUESTIONS_DIR.glob("*.json"):
        try:
            data = json.loads(qf.read_text(encoding="utf-8"))
            total += len(data) if isinstance(data, list) else len(data.get("questions", []))
        except Exception:
            pass
    readme, _ = re.subn(r"\d+ approved questions", f"{total} approved questions", readme)

    README_MD.write_text(readme, encoding="utf-8")
    subprocess.run(["git", "add", str(README_MD)], cwd=ROOT, capture_output=True)
    print(f"  [docs] README.md staged (total questions: {total})")
    return True


# ── Warn: SQLite tables (CLAUDE.md) ───────────────────────────────────────────

def warn_sqlite_tables(changed: list[str]) -> None:
    if "backend/database.py" not in changed:
        return
    db_text = (ROOT / "backend" / "database.py").read_text(encoding="utf-8")
    claude_text = CLAUDE_MD.read_text(encoding="utf-8")
    tables = re.findall(
        r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+[`'\"]?(\w+)[`'\"]?",
        db_text, re.IGNORECASE,
    )
    missing = [t for t in tables if t not in ("sqlite_sequence",) and f"`{t}`" not in claude_text]
    if missing:
        print(f"  [docs] WARN database.py changed — tables not in CLAUDE.md: {', '.join(missing)}")


# ── Warn: new router files (README.md) ────────────────────────────────────────

def warn_routers(changed: list[str]) -> None:
    new_routers = [
        f for f in changed
        if re.match(r"backend/routers/\w+\.py$", f) and "__init__" not in f
    ]
    if not new_routers:
        return
    readme = README_MD.read_text(encoding="utf-8")
    for f in new_routers:
        name = Path(f).name
        if name not in readme:
            print(f"  [docs] WARN new router {name} not listed in README.md folder structure")


# ── Warn: AI client changes (CLAUDE.md) ───────────────────────────────────────

def warn_ai_client(changed: list[str]) -> None:
    if "backend/services/ai_client.py" in changed:
        print("  [docs] WARN ai_client.py changed — review CLAUDE.md 'AI calls' section")


# ── Validate: gitignore for newly added files ─────────────────────────────────

def validate_gitignore() -> bool:
    """
    Check every newly added file against _SHOULD_IGNORE rules.
    - If the pattern is missing from .gitignore → add it automatically.
    - If the file is already tracked but matches a rule → warn to un-track it.
    Returns True if .gitignore was modified.
    """
    added = get_added_files()
    if not added:
        return False

    gitignore_text = GITIGNORE.read_text(encoding="utf-8") if GITIGNORE.exists() else ""
    new_patterns: list[tuple[str, str]] = []   # (pattern, reason)
    already_tracked: list[tuple[str, str]] = [] # (file, reason)

    for f in added:
        for regex, pattern, reason in _SHOULD_IGNORE:
            if not re.search(regex, f):
                continue
            # Pattern already in .gitignore?
            base_pattern = pattern.split("\n")[0]
            if base_pattern in gitignore_text:
                # Pattern exists but file was committed anyway — already tracked
                already_tracked.append((f, reason))
            else:
                new_patterns.append((pattern, reason))
            break  # first matching rule wins

    # Auto-add missing patterns to .gitignore
    gitignore_updated = False
    for pattern, reason in new_patterns:
        if pattern.split("\n")[0] not in gitignore_text:
            gitignore_text += f"\n# Auto-added: {reason}\n{pattern}\n"
            gitignore_updated = True
            print(f"  [gitignore] Added pattern: {pattern.split(chr(10))[0]}  ({reason})")

    if gitignore_updated:
        GITIGNORE.write_text(gitignore_text, encoding="utf-8")
        subprocess.run(["git", "add", str(GITIGNORE)], cwd=ROOT, capture_output=True)
        print("  [gitignore] .gitignore updated and staged.")

    for f, reason in already_tracked:
        print(f"  [gitignore] WARN '{f}' is a {reason} — should not be committed.")
        print(f"              Remove it: git rm --cached {f}")

    return gitignore_updated


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    changed = get_changed_files()
    if not changed:
        sys.exit(0)

    print(f"[update_docs] {len(changed)} file(s) changed — checking docs...")

    gitignore_updated = validate_gitignore()
    docs_updated      = update_question_counts(changed)
    warn_sqlite_tables(changed)
    warn_routers(changed)
    warn_ai_client(changed)

    if gitignore_updated or docs_updated:
        print("[update_docs] Files auto-updated and staged. Amend before pushing:")
        print("  git commit --amend --no-edit && git push")

    sys.exit(0)


if __name__ == "__main__":
    main()
