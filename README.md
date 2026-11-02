# Financial Tracker

Personal receipt expense tracker: upload a receipt image, parse line items with **local Tesseract OCR**, apply **Ontario HST** rules, categorize spend, and fix flagged lines later.

## Stack

- **Backend:** FastAPI + SQLModel + uv + Alembic + PEP 8 (Ruff)
- **Frontend:** SvelteKit (sessionStorage auth + refresh tokens)
- **OCR:** Tesseract (local)
- **Harness:** [learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering) templates
- **UI craft:** [unslop](https://github.com/heydamir/unslop) + Attendi impeccable / design-taste skills

## Quick start

```bash
# once
brew install tesseract   # macOS
cp .env.example .env     # set SECRET_KEY for anything beyond local toys
chmod +x init.sh

# verify
./init.sh

# run API
cd backend && uv run uvicorn financial_tracker_api.main:app --reload --port 8000

# run web (other terminal) — Vite proxies /api → :8000
cd frontend && npm run dev
```

Open http://localhost:5173 — register (12+ char password with upper/lower/digit), upload a JPG/PNG receipt, browse receipts and category totals.

## Security notes

- `ENVIRONMENT=production` refuses weak/`SECRET_KEY` shorter than 32 chars
- Access JWT ~60m; refresh JWT ~7d with server-side `RefreshSession` (rotate + revoke)
- Auth/upload rate limits via SlowAPI
- Uploads sniffed with Pillow (format allow-list); paths stay under `DATA_DIR`
- Receipt images served only via authenticated `GET /api/receipts/{id}/image`
- OpenAPI/Swagger disabled when `ENVIRONMENT=production` (override with `ENABLE_DOCS=true`)

## Agent workflow

1. Read `AGENTS.md`, `claude-progress.md`, `feature_list.json`
2. Run `./init.sh`
3. Work one feature at a time; record evidence before marking `passing`
4. UI PRs: run unslop + follow `DESIGN.md` (tokens in `frontend/src/app.css`)

## Docker (one command)

Copy `.env.example` → `.env` and set `SECRET_KEY` / `POSTGRES_PASSWORD`. From repo root or `backend/`:

```bash
docker compose up --build
```

- App: http://localhost:3000
- API: http://localhost:8000
- Postgres: internal only (`db:5432`)

Stop with `Ctrl+C`, or `docker compose down`.

### Migrations

```bash
cd backend
uv run alembic upgrade head
```

## Money

All money fields are **integer cents** in the DB and API (`total_cents`, `line_total_cents`, …).  
The UI shows dollars by dividing by 100 (e.g. `3827` → `$38.27`).

## API

- Swagger (dev): http://localhost:8000/docs
- `POST /api/auth/register|login|refresh|logout` · `GET|PATCH /api/auth/me`
- `POST /api/receipts/upload` · `GET /api/receipts` · `GET|PATCH|DELETE /api/receipts/{id}`
- `GET /api/receipts/{id}/image` · `POST /api/receipts/{id}/reparse`
- `PATCH /api/receipts/line-items/{id}`
- `GET /api/stores`
- `GET /api/stats/by-category`
- `GET /api/health`

## Backend tests

API-level only: each test calls HTTP endpoints like a client. The DB is a real in-memory SQLite database. **Tesseract is the only mocked external dependency.**

```bash
cd backend
uv run pytest
```

Coverage is enforced at **100%** (`--cov-fail-under=100`).
