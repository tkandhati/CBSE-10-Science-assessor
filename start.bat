@echo off
title Science Assessor — Launcher
color 0A

REM ── Use the folder this .bat file lives in as the project root ───────────────
set "ROOT=%~dp0"
REM Strip trailing backslash
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo.
echo  =========================================
echo   Science Assessor — Starting up
echo  =========================================
echo  Root: %ROOT%
echo.

REM ── Check backend port is free ──────────────────────────────────────────────
netstat -ano | findstr ":8000" | findstr "LISTENING" > nul
if %errorlevel%==0 (
    echo  [WARN] Port 8000 is already in use.
    echo         Backend may already be running, or another app is on that port.
    echo         Run stop.bat first if you want a clean restart.
    echo.
    pause
    exit /b 1
)

REM ── Start backend in a new window ───────────────────────────────────────────
echo  [1/2] Starting backend  ^(http://localhost:8000^)...
start "Science Assessor — Backend" cmd /k "cd /d "%ROOT%" && .venv\Scripts\activate && uvicorn backend.main:app --reload --app-dir . && echo. && echo Backend stopped. Press any key to close. && pause > nul"

REM ── Wait for backend to initialise ──────────────────────────────────────────
echo        Waiting for backend to initialise...
timeout /t 4 /nobreak > nul

REM ── Start frontend in a new window ──────────────────────────────────────────
echo  [2/2] Starting frontend ^(http://localhost:5173^)...
start "Science Assessor — Frontend" cmd /k "cd /d "%ROOT%\frontend" && npm run dev && echo. && echo Frontend stopped. Press any key to close. && pause > nul"

REM ── Open browser ────────────────────────────────────────────────────────────
echo.
echo        Opening browser in 3 seconds...
timeout /t 3 /nobreak > nul
start http://localhost:5173

echo.
echo  Both services are running.
echo  To stop them, run stop.bat or press Ctrl+C in each window.
echo.
echo  This window can be closed.
echo.
