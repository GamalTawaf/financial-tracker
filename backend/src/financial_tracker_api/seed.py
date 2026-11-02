"""Database seed helpers."""

from sqlmodel import Session, select

from financial_tracker_api.models import Category
from financial_tracker_api.services.categories import SEED_CATEGORIES


def seed_categories(session: Session) -> None:
    """Insert default categories if missing."""
    for slug, name in SEED_CATEGORIES:
        existing = session.exec(select(Category).where(Category.slug == slug)).first()
        if existing is None:
            session.add(Category(slug=slug, name=name))
    session.commit()
