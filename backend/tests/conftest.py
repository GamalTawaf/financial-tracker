"""Shared pytest fixtures for API-level tests.

Tests exercise HTTP endpoints like a client. The in-memory SQLite DB is real.
Only external I/O (Tesseract OCR) is mocked.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from financial_tracker_api.db import get_session
from financial_tracker_api.main import create_app
from financial_tracker_api.rate_limit import limiter
from financial_tracker_api.seed import seed_categories


@pytest.fixture()
def client() -> Generator[TestClient]:
    """In-memory SQLite app client with seeded categories."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _override_session() -> Generator[Session]:
        with Session(engine) as session:
            yield session

    with Session(engine) as session:
        seed_categories(session)

    # Shared TestClient IP would trip SlowAPI across the suite.
    was_enabled = limiter.enabled
    limiter.enabled = False
    app = create_app()
    app.state.test_engine = engine
    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    limiter.enabled = was_enabled
