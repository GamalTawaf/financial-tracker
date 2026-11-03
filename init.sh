#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> Working directory: $PWD"

if [[ ! -f backend/pyproject.toml ]]; then
  echo "==> Backend not scaffolded yet; skipping verification."
  exit 0
fi

echo "==> Syncing backend dependencies (uv)"
(
  cd backend
  uv sync --all-extras
)

echo "==> Syncing frontend dependencies"
(
  cd frontend
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
)

echo "==> Running baseline verification"
(
  cd backend
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest -q
)
(
  cd frontend
  npm run check
  npm test --if-present
)

echo "==> Startup commands"
echo "    Preferred: docker compose up --build   # app http://localhost:3000"
echo "    Local API:  (cd backend && uv run uvicorn financial_tracker_api.main:app --reload --port 8000)"
echo "    Local web:  (cd frontend && npm run dev)  # http://localhost:5173"

if [[ "${RUN_START_COMMAND:-0}" = "1" ]]; then
  echo "==> Starting API (background) and frontend"
  (cd backend && uv run uvicorn financial_tracker_api.main:app --reload --port 8000) &
  (cd frontend && npm run dev)
fi

echo "Set RUN_START_COMMAND=1 if you want init.sh to launch local (non-Docker) servers."