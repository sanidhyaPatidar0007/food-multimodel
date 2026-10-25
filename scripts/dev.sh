#!/usr/bin/env bash
# Run backend and frontend together (macOS/Linux). Ctrl+C stops both.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
( cd "$ROOT/backend" && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000 ) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT
cd "$ROOT/frontend" && npm run dev
