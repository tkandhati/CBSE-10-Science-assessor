@echo off
title Science Assessor — Stopper
color 0C

echo.
echo  =========================================
echo   Science Assessor — Stopping services
echo  =========================================
echo.

REM ── Kill process on port 8000 (backend) ─────────────────────────────────────
echo  [1/2] Stopping backend  (port 8000)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo         Killing PID %%p
    taskkill /PID %%p /F > nul 2>&1
)

REM ── Kill process on port 5173 (frontend) ────────────────────────────────────
echo  [2/2] Stopping frontend (port 5173)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
    echo         Killing PID %%p
    taskkill /PID %%p /F > nul 2>&1
)

echo.
echo  Done. Both services stopped.
echo  (The terminal windows may still be open — you can close them manually.)
echo.
pause
