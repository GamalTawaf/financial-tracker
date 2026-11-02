"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from financial_tracker_api.auth import (
    create_token_pair,
    hash_password,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from financial_tracker_api.db import get_session
from financial_tracker_api.deps import get_current_user
from financial_tracker_api.models import User, utcnow
from financial_tracker_api.rate_limit import limiter
from financial_tracker_api.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(session: Session, user_id: int) -> TokenResponse:
    access, refresh, expires_in = create_token_pair(session, user_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    body: RegisterRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Create a user and return access + refresh tokens."""
    existing = session.exec(select(User).where(User.email == body.email.lower())).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None
    return _token_response(session, user.id)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: LoginRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Authenticate and return access + refresh tokens."""
    user = session.exec(select(User).where(User.email == body.email.lower())).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    assert user.id is not None
    return _token_response(session, user.id)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh(
    request: Request,
    body: RefreshRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Rotate a refresh token into a new token pair."""
    pair = rotate_refresh_token(session, body.refresh_token)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    access, refresh_token, expires_in = pair
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, session: Session = Depends(get_session)) -> None:
    """Revoke the provided refresh token."""
    revoke_refresh_token(session, body.refresh_token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    """Return the current user profile."""
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UserUpdateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    """Update display name and/or province."""
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.province is not None:
        user.province = body.province
    user.updated_at = utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
