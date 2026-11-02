"""Database engine and session helpers."""

from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from financial_tracker_api.config import get_settings

_settings = get_settings()
connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, connect_args=connect_args)


def _ensure_column(table: str, column: str, ddl: str) -> None:
    """Add a missing column on an existing table (SQLite/Postgres)."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def init_db() -> None:
    """Create tables if they do not exist."""
    # Import models so metadata is complete before create_all.
    import financial_tracker_api.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _ensure_column("receipt", "store_id", "store_id INTEGER")
    _ensure_column("lineitem", "quantity_unit", "quantity_unit VARCHAR DEFAULT 'ea'")


def get_session() -> Generator[Session]:
    """Yield a SQLModel session for request handlers."""
    with Session(engine) as session:
        yield session
