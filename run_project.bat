@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Baseera Marketplace Analytics and Sentiment Intelligence
echo   Local launcher - backend (FastAPI) + frontend (React/Vite)
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 1) Locate a working Python interpreter (3.10 or 3.11)
REM ------------------------------------------------------------
set "PYTHON_EXE="
where python >nul 2>nul
if %errorlevel%==0 (
    for /f "delims=" %%P in ('where python') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
    )
)
if not defined PYTHON_EXE (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    ) do (
        if exist %%~P set "PYTHON_EXE=%%~P"
    )
)
if not defined PYTHON_EXE (
    echo [ERROR] No Python interpreter found on PATH or in the usual install
    echo         locations. Install Python 3.10 or 3.11 and re-run this script.
    pause
    exit /b 1
)
echo Using Python: %PYTHON_EXE%

REM ------------------------------------------------------------
REM 2) Locate npm (Node.js)
REM ------------------------------------------------------------
where npm >nul 2>nul
if not %errorlevel%==0 (
    echo [ERROR] npm was not found on PATH. Install Node.js (LTS) and re-run.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 3) Make sure local config files exist (copied from the
REM    committed .example files - never overwrites an existing one)
REM ------------------------------------------------------------
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env from .env.example
)
if not exist "frontend\.env" (
    copy "frontend\.env.example" "frontend\.env" >nul
    echo Created frontend\.env from frontend\.env.example
)

REM ------------------------------------------------------------
REM 4) Sanity checks: model weights and frontend dependencies
REM    must already be present locally (offline requirement -
REM    nothing here is downloaded at run time).
REM ------------------------------------------------------------
if not exist "models\bert_review_sentiment\model.safetensors" (
    echo [WARNING] models\bert_review_sentiment\model.safetensors not found.
    echo           BERT will be unavailable; CNN2D will still work if present.
)
if not exist "models\cnn2d_review_sentiment.pt" (
    echo [WARNING] models\cnn2d_review_sentiment.pt not found.
)
if not exist "frontend\node_modules" (
    echo [ERROR] frontend\node_modules is missing. Run "npm install" inside
    echo         frontend\ once ^(requires internet^) before using this script.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 5) Start backend and frontend, each in its own window
REM ------------------------------------------------------------
echo.
echo Starting backend  (FastAPI) on http://localhost:8000 ...
start "Baseera Backend"  cmd /k "cd /d "%~dp0backend" && "%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo Starting frontend (Vite)    on http://localhost:5173 ...
start "Baseera Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

REM Give the backend a few seconds to finish loading models before
REM opening the browser, so the first request doesn't race startup.
timeout /t 10 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo ------------------------------------------------------------
echo Backend health check:  http://localhost:8000/api/v1/health
echo Frontend app:          http://localhost:5173
echo.
echo Two new windows were opened (Backend, Frontend). Close both
echo of them to stop the servers. This window can be closed safely.
echo ------------------------------------------------------------
pause
