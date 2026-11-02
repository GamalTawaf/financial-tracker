"""Schema bootstrap helpers used by app lifespan (not HTTP, but required for startup)."""

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlmodel import SQLModel

import financial_tracker_api.db as db_module
import financial_tracker_api.models  # noqa: F401
from financial_tracker_api.db import _ensure_column, init_db


def test_init_db_adds_missing_columns(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE receipt ("
                "id INTEGER PRIMARY KEY, user_id INTEGER, image_path VARCHAR, store_name VARCHAR)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE lineitem ("
                "id INTEGER PRIMARY KEY, receipt_id INTEGER, name VARCHAR, quantity FLOAT)"
            )
        )
    monkeypatch.setattr(db_module, "engine", engine)
    init_db()
    with engine.connect() as conn:
        receipt_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(receipt)"))}
        item_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(lineitem)"))}
    assert "store_id" in receipt_cols
    assert "quantity_unit" in item_cols
    # Second call is a no-op once the columns exist.
    _ensure_column("receipt", "store_id", "store_id INTEGER")
    _ensure_column("lineitem", "quantity_unit", "quantity_unit VARCHAR DEFAULT 'ea'")


def test_ensure_column_noop_without_table(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    monkeypatch.setattr(db_module, "engine", engine)
    _ensure_column("receipt", "store_id", "store_id INTEGER")


def test_get_session_yields_session(monkeypatch, tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'sess.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    gen = db_module.get_session()
    session = next(gen)
    assert session is not None
    try:
        next(gen)
    except StopIteration:
        pass
