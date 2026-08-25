#!/usr/bin/env bash
# Baseera Marketplace Analytics and Sentiment Intelligence
# Local launcher - backend (FastAPI) + frontend (React/Vite)
# macOS / Linux equivalent of run_project.bat.
set -euo pipefail

# Resolve repository root relative to this script, regardless of the caller's cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "  Baseera Marketplace Analytics and Sentiment Intelligence"
echo "  Local launcher - backend (FastAPI) + frontend (React/Vite)"
echo "============================================================"
echo

# ------------------------------------------------------------
# 1) Locate a working Python interpreter (3.10 or 3.11)
# ------------------------------------------------------------
PYTHON_EXE=""
for candidate in python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_EXE="$(command -v "$candidate")"
        break
    fi
done
if [ -z "$PYTHON_EXE" ]; then
    echo "[ERROR] No Python interpreter found on PATH."
    echo "        Install Python 3.10 or 3.11 and re-run this script."
    exit 1
fi
echo "Using Python: $PYTHON_EXE"

# ------------------------------------------------------------
# 2) Locate npm (Node.js)
# ------------------------------------------------------------
if ! command -v npm >/dev/null 2>&1; then
    echo "[ERROR] npm was not found on PATH. Install Node.js (LTS) and re-run."
    exit 1
fi

# ------------------------------------------------------------
# 3) Make sure local config files exist (copied from the
#    committed .example files - never overwrites an existing one)
# ------------------------------------------------------------
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp ".env.example" ".env"
    echo "Created .env from .env.example"
fi
if [ ! -f "frontend/.env" ] && [ -f "frontend/.env.example" ]; then
    cp "frontend/.env.example" "frontend/.env"
    echo "Created frontend/.env from frontend/.env.example"
fi

# ------------------------------------------------------------
# 4) Sanity checks: model weights and frontend dependencies
#    must already be present locally (offline requirement -
#    nothing here is downloaded at run time).
# ------------------------------------------------------------
if [ ! -f "models/bert_review_sentiment/model.safetensors" ]; then
    echo "[WARNING] models/bert_review_sentiment/model.safetensors not found."
    echo "          BERT will be unavailable; CNN2D will still work if present."
fi
if [ ! -f "models/cnn2d_review_sentiment.pt" ]; then
    echo "[WARNING] models/cnn2d_review_sentiment.pt not found."
fi
if [ ! -d "frontend/node_modules" ]; then
    echo "[ERROR] frontend/node_modules is missing. Run 'npm install' inside"
    echo "        frontend/ once (requires internet) before using this script."
    exit 1
fi

# ------------------------------------------------------------
# 5) Start backend and frontend as background processes
# ------------------------------------------------------------
echo
echo "Starting backend  (FastAPI) on http://localhost:8000 ..."
(cd "$SCRIPT_DIR/backend" && "$PYTHON_EXE" -m uvicorn app.main:app --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

echo "Starting frontend (Vite)    on http://localhost:5173 ..."
(cd "$SCRIPT_DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

cleanup() {
    echo
    echo "Stopping backend (pid $BACKEND_PID) and frontend (pid $FRONTEND_PID) ..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo
echo "------------------------------------------------------------"
echo "Backend health check:  http://localhost:8000/api/v1/health"
echo "Frontend app:          http://localhost:5173"
echo
echo "Press Ctrl+C to stop both servers."
echo "------------------------------------------------------------"
wait
