"""Store listing routes."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from financial_tracker_api.db import get_session
from financial_tracker_api.deps import get_current_user
from financial_tracker_api.models import User
from financial_tracker_api.schemas import StoreResponse
from financial_tracker_api.services.stores import list_stores_for_user

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("", response_model=list[StoreResponse])
def list_stores(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[StoreResponse]:
    """List distinct stores for the current user."""
    assert user.id is not None
    return [
        StoreResponse(
            id=store.id or 0,
            name=store.name,
            address=store.address,
            phone=store.phone,
        )
        for store in list_stores_for_user(session, user.id)
    ]
