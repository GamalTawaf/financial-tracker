"""Auth refresh, upload hardening, image/reparse, and config security."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from helpers import SIMPLE_OCR, auth_header, png_bytes, register, upload_receipt
from jose import jwt
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from financial_tracker_api.auth import create_token_pair, hash_password
from financial_tracker_api.config import Settings, get_settings
from financial_tracker_api.db import get_session
from financial_tracker_api.main import create_app
from financial_tracker_api.models import RefreshSession, User
from financial_tracker_api.rate_limit import limiter
from financial_tracker_api.seed import seed_categories
from financial_tracker_api.services.uploads import (
    delete_receipt_image,
    resolve_receipt_path,
    sniff_image_extension,
)


def _register_full(client, email: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!ab", "display_name": email},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_rejects_weak_password(client) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_refresh_rotates_and_old_token_fails(client) -> None:
    tokens = _register_full(client, "refresh@example.com")
    first = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["access_token"]
    assert body["refresh_token"] != tokens["refresh_token"]
    assert body["expires_in"] > 0

    reused = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reused.status_code == 401

    me = client.get("/api/auth/me", headers=auth_header(body["access_token"]))
    assert me.status_code == 200


def test_refresh_rejects_access_token_and_garbage(client) -> None:
    tokens = _register_full(client, "badrefresh@example.com")
    assert (
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["access_token"]},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": "not-a-jwt"},
        ).status_code
        == 401
    )


def test_logout_revokes_refresh_token(client) -> None:
    tokens = _register_full(client, "logout@example.com")
    assert (
        client.post(
            "/api/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/auth/logout",
            json={"refresh_token": "garbage"},
        ).status_code
        == 204
    )


def test_expired_refresh_session_rejected() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_categories(session)
        user = User(
            email="exp2@example.com",
            password_hash=hash_password("Password123!ab"),
            display_name="exp",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None
        access, refresh, _ = create_token_pair(session, user.id)
        row = session.exec(select(RefreshSession).where(RefreshSession.user_id == user.id)).first()
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(hours=1)
        session.add(row)
        session.commit()

    def _override():
        with Session(engine) as session:
            yield session

    was = limiter.enabled
    limiter.enabled = False
    app = create_app()
    app.dependency_overrides[get_session] = _override
    with TestClient(app) as tc:
        assert tc.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 401
        assert tc.get("/api/auth/me", headers=auth_header(access)).status_code == 200
    app.dependency_overrides.clear()
    limiter.enabled = was


def test_upload_response_hides_image_path_exposes_has_image(client) -> None:
    token = register(client, "hasimg@example.com")
    body = upload_receipt(client, token).json()
    assert "image_path" not in body
    assert body["has_image"] is True


def test_receipt_image_endpoint_requires_owner(client) -> None:
    token_a = register(client, "img-owner@example.com")
    token_b = register(client, "img-other@example.com")
    receipt_id = upload_receipt(client, token_a).json()["id"]

    ok = client.get(f"/api/receipts/{receipt_id}/image", headers=auth_header(token_a))
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("image/")

    assert (
        client.get(f"/api/receipts/{receipt_id}/image", headers=auth_header(token_b)).status_code
        == 404
    )
    assert client.get(f"/api/receipts/{receipt_id}/image").status_code == 401
    assert client.get("/api/receipts/9999/image", headers=auth_header(token_a)).status_code == 404


def test_reparse_replaces_line_items(client) -> None:
    token = register(client, "reparse@example.com")
    headers = auth_header(token)
    created = upload_receipt(client, token, ocr_text=SIMPLE_OCR).json()
    receipt_id = created["id"]

    new_ocr = """\
Corner Mart
100 Queen St
Candy 1.00
TOTAL 1.00
"""
    with patch(
        "financial_tracker_api.routers.receipts.run_ocr",
        return_value=(new_ocr, 0.95),
    ):
        response = client.post(f"/api/receipts/{receipt_id}/reparse", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["line_items"]) == 1
    assert body["line_items"][0]["line_total_cents"] == 100


def test_reparse_missing_receipt_404(client) -> None:
    token = register(client, "reparse-miss@example.com")
    assert (
        client.post("/api/receipts/9999/reparse", headers=auth_header(token)).status_code == 404
    )


def test_delete_removes_image_file(client) -> None:
    token = register(client, "delfile@example.com")
    settings = get_settings()
    created = upload_receipt(client, token).json()
    receipt_id = created["id"]
    files_before = [p for p in Path(settings.receipts_dir).rglob("*") if p.is_file()]
    assert files_before
    assert (
        client.delete(f"/api/receipts/{receipt_id}", headers=auth_header(token)).status_code == 204
    )
    files_after = [p for p in Path(settings.receipts_dir).rglob("*") if p.is_file()]
    assert len(files_after) < len(files_before)


def test_sniff_rejects_empty_and_non_image() -> None:
    try:
        sniff_image_extension(b"")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        sniff_image_extension(b"not-an-image")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert sniff_image_extension(png_bytes()) == ".png"


def test_resolve_path_blocks_traversal(tmp_path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "ok.png").write_bytes(b"x")
    assert resolve_receipt_path(data, "ok.png").name == "ok.png"
    try:
        resolve_receipt_path(data, "../secret")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        resolve_receipt_path(data, "/etc/passwd")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    delete_receipt_image(data, "../secret")
    delete_receipt_image(data, "missing.png")


def test_production_rejects_weak_secret(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-only-change-me")
    try:
        Settings().assert_secure()
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "SECRET_KEY" in str(exc)
    monkeypatch.setenv("SECRET_KEY", "short")
    try:
        Settings().assert_secure()
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    Settings().assert_secure()


def test_docs_disabled_in_production(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-at-least-32-chars!!")
    monkeypatch.delenv("ENABLE_DOCS", raising=False)
    get_settings.cache_clear()
    assert get_settings().docs_enabled() is False
    app = create_app()
    assert app.docs_url is None
    assert app.openapi_url is None
    get_settings.cache_clear()


def test_docs_can_be_forced_on(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-at-least-32-chars!!")
    monkeypatch.setenv("ENABLE_DOCS", "true")
    get_settings.cache_clear()
    assert get_settings().docs_enabled() is True
    get_settings.cache_clear()


def test_value_error_handler_returns_400(client) -> None:
    app = client.app

    @app.get("/__test_value_error")
    def _boom():
        raise ValueError("boom-detail")

    response = client.get("/__test_value_error")
    assert response.status_code == 400
    assert response.json()["detail"] == "boom-detail"


def test_refresh_rejects_non_numeric_subject(client) -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "abc",
            "exp": datetime.now(UTC) + timedelta(days=1),
            "typ": "refresh",
            "jti": "deadbeef",
        },
        settings.secret_key,
        algorithm="HS256",
    )
    assert client.post("/api/auth/refresh", json={"refresh_token": token}).status_code == 401


def test_refresh_rejects_missing_jti(client) -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(UTC) + timedelta(days=1),
            "typ": "refresh",
        },
        settings.secret_key,
        algorithm="HS256",
    )
    assert client.post("/api/auth/refresh", json={"refresh_token": token}).status_code == 401


def test_access_token_rejects_refresh_typ(client) -> None:
    tokens = _register_full(client, "typmix@example.com")
    assert (
        client.get("/api/auth/me", headers=auth_header(tokens["refresh_token"])).status_code == 401
    )


def test_webp_upload_accepted(client) -> None:
    token = register(client, "webp@example.com")
    buf = BytesIO()
    Image.new("RGB", (32, 32), (10, 20, 30)).save(buf, format="WEBP")
    with patch(
        "financial_tracker_api.routers.receipts.run_ocr",
        return_value=("Shop\nItem 1.00\nTOTAL 1.00\n", 0.9),
    ):
        response = client.post(
            "/api/receipts/upload",
            headers=auth_header(token),
            files={"file": ("shot.webp", buf.getvalue(), "image/webp")},
        )
    assert response.status_code == 201, response.text
    assert response.json()["has_image"] is True


def test_unsupported_image_format_message() -> None:
    buf = BytesIO()
    # BMP is a real image but not in allow-list
    Image.new("RGB", (8, 8)).save(buf, format="BMP")
    try:
        sniff_image_extension(buf.getvalue())
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Unsupported" in str(exc)


def test_validate_password_strength_raises() -> None:
    from financial_tracker_api.auth import validate_password_strength

    try:
        validate_password_strength("noupperordigit")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Password must include" in str(exc)


def test_rotate_handles_naive_expires_at() -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from financial_tracker_api.auth import rotate_refresh_token

    settings = get_settings()
    jti = "naivejti0001"
    token = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(UTC) + timedelta(days=1),
            "typ": "refresh",
            "jti": jti,
        },
        settings.secret_key,
        algorithm="HS256",
    )
    row = SimpleNamespace(
        revoked=False,
        expires_at=datetime(2099, 6, 1, 12, 0, 0),  # naive
        user_id=1,
    )
    session = MagicMock()
    session.exec.return_value.first.return_value = row
    with patch(
        "financial_tracker_api.auth.create_token_pair",
        return_value=("access", "refresh", 3600),
    ):
        pair = rotate_refresh_token(session, token)
    assert pair == ("access", "refresh", 3600)
    assert row.revoked is True


def test_revoke_missing_jti_and_unknown_session(client) -> None:
    settings = get_settings()
    no_jti = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(UTC) + timedelta(days=1),
            "typ": "refresh",
        },
        settings.secret_key,
        algorithm="HS256",
    )
    assert client.post("/api/auth/logout", json={"refresh_token": no_jti}).status_code == 204

    unknown = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(UTC) + timedelta(days=1),
            "typ": "refresh",
            "jti": "never-stored-jti",
        },
        settings.secret_key,
        algorithm="HS256",
    )
    assert client.post("/api/auth/logout", json={"refresh_token": unknown}).status_code == 204


def test_image_and_reparse_missing_file_paths(client) -> None:
    token = register(client, "missfile@example.com")
    headers = auth_header(token)
    created = upload_receipt(client, token).json()
    receipt_id = created["id"]
    settings = get_settings()

    # Delete underlying file → image/reparse 404
    for path in Path(settings.receipts_dir).rglob("*"):
        if path.is_file():
            path.unlink()

    assert client.get(f"/api/receipts/{receipt_id}/image", headers=headers).status_code == 404
    assert client.post(f"/api/receipts/{receipt_id}/reparse", headers=headers).status_code == 404


def test_image_and_reparse_reject_traversal_path(client) -> None:
    token = register(client, "trav@example.com")
    headers = auth_header(token)
    created = upload_receipt(client, token).json()
    receipt_id = created["id"]

    with patch(
        "financial_tracker_api.routers.receipts.resolve_receipt_path",
        side_effect=ValueError("Invalid image path"),
    ):
        assert client.get(f"/api/receipts/{receipt_id}/image", headers=headers).status_code == 404
        assert (
            client.post(f"/api/receipts/{receipt_id}/reparse", headers=headers).status_code == 404
        )


def test_reparse_ocr_failure(client) -> None:
    token = register(client, "reparse-ocr@example.com")
    headers = auth_header(token)
    receipt_id = upload_receipt(client, token).json()["id"]
    with patch(
        "financial_tracker_api.routers.receipts.run_ocr",
        side_effect=OSError("disk read fail"),
    ):
        response = client.post(f"/api/receipts/{receipt_id}/reparse", headers=headers)
    assert response.status_code == 422
    assert "Could not read" in response.json()["detail"]


def test_resolve_symlink_escape(tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.png").write_bytes(b"x")
    link = data_dir / "link"
    try:
        link.symlink_to(outside)
    except OSError:
        return  # platform without symlink support
    try:
        resolve_receipt_path(data_dir, "link/secret.png")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
