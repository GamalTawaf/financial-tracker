# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm AS runtime
RUN apt-get update \
	&& apt-get install -y --no-install-recommends tesseract-ocr \
	&& rm -rf /var/lib/apt/lists/* \
	&& useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY pyproject.toml README.md ./
ENV PATH="/app/.venv/bin:$PATH" \
	PYTHONUNBUFFERED=1 \
	DATABASE_URL=sqlite:////data/app.db \
	DATA_DIR=/data \
	RECEIPTS_DIR=/data/receipts
RUN mkdir -p /data/receipts && chown -R appuser:appuser /data /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "financial_tracker_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
