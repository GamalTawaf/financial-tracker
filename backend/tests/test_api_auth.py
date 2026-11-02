"""Auth endpoints exercised as HTTP requests."""

from helpers import auth_header, register


def test_health(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body


def test_register_login_me_and_update(client) -> None:
    token = register(client, "ada@example.com", display_name="Ada")
    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    assert me.json()["display_name"] == "Ada"

    login = client.post(
        "/api/auth/login",
        json={"email": "ada@example.com", "password": "Password123!ab"},
    )
    assert login.status_code == 200
    login_token = login.json()["access_token"]

    patched = client.patch(
        "/api/auth/me",
        headers=auth_header(login_token),
        json={"display_name": "Ada Lovelace", "province": "ON"},
    )
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Ada Lovelace"
    assert patched.json()["province"] == "ON"


def test_register_duplicate_email_conflict(client) -> None:
    register(client, "dup@example.com")
    again = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "Password123!ab"},
    )
    assert again.status_code == 409
    assert "already" in again.json()["detail"].lower()


def test_login_invalid_credentials(client) -> None:
    register(client, "user@example.com")
    bad = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401


def test_me_requires_auth(client) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    )


def test_me_rejects_unknown_user_token(client) -> None:
    from financial_tracker_api.auth import create_access_token

    token = create_access_token("999999")
    response = client.get("/api/auth/me", headers=auth_header(token))
    assert response.status_code == 401
    assert response.json()["detail"] == "User not found"


def test_me_rejects_non_numeric_subject(client) -> None:
    from financial_tracker_api.auth import create_access_token

    token = create_access_token("not-an-id")
    response = client.get("/api/auth/me", headers=auth_header(token))
    assert response.status_code == 401
