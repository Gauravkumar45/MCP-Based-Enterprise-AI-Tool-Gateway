"""Security tests for authentication hardening.

Covers: removal of the demo-password backdoor, opt-in demo shortcuts, failed-login lockout,
token revocation on logout (REST and MCP), issuer/audience enforcement, production config
validation, CORS and security headers.
"""

from collections.abc import AsyncGenerator
from typing import Any

import httpx
import jwt
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import authenticate_token
from app.core.config import DEFAULT_JWT_SECRET, Settings, get_settings
from app.core.errors import AuthenticationError
from app.core.security import (
    DEMO_SEED_PASSWORD,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    verify_password_with_demo_shortcuts,
)
from app.database.session import get_db
from app.main import create_app
from app.services import auth_guard

TEST_PASSWORD = "Pass123!"  # matches tests/conftest.py seed users


@pytest.fixture(autouse=True)
def _isolated_auth_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the in-memory backend and start every test with clean guard state."""
    monkeypatch.setattr(auth_guard, "get_redis_client", lambda: None)
    auth_guard._memory_revoked.clear()
    auth_guard._memory_login_failures.clear()


@pytest_asyncio.fixture
async def api(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    app: FastAPI = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _login(client: httpx.AsyncClient, username: str, password: str) -> httpx.Response:
    return await client.post("/auth/login", json={"username": username, "password": password})


# ---------------------------------------------------------------------------
# Password verification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", ["password", "Password123", "password123!", "admin"])
def test_demo_password_variants_are_not_a_backdoor(variant: str) -> None:
    """Strict verification must not accept demo variants for the seed password."""
    hashed = hash_password(DEMO_SEED_PASSWORD)
    assert verify_password(variant, hashed) is False
    assert verify_password(DEMO_SEED_PASSWORD, hashed) is True


def test_demo_shortcut_verifier_only_applies_to_seed_password() -> None:
    seed_hash = hash_password(DEMO_SEED_PASSWORD)
    other_hash = hash_password("SomeRealUserPassword!9")
    assert verify_password_with_demo_shortcuts("admin", seed_hash) is True
    assert verify_password_with_demo_shortcuts("admin", other_hash) is False


# ---------------------------------------------------------------------------
# Login endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_rejects_demo_variant_when_shortcuts_disabled(
    api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "AUTH_DEMO_SHORTCUTS", False)
    assert (await _login(api, "analyst", TEST_PASSWORD)).status_code == 200
    assert (await _login(api, "analyst", "password")).status_code == 401
    # Demo aliases are ignored too
    assert (await _login(api, "bob", TEST_PASSWORD)).status_code == 401


@pytest.mark.asyncio
async def test_login_demo_aliases_work_when_shortcuts_enabled(
    api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "AUTH_DEMO_SHORTCUTS", True)
    resp = await _login(api, "Bob", TEST_PASSWORD)
    assert resp.status_code == 200
    assert resp.json()["username"] == "analyst"


@pytest.mark.asyncio
async def test_unknown_user_gets_generic_401(api: httpx.AsyncClient) -> None:
    resp = await _login(api, "nobody-here", TEST_PASSWORD)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect username or password"


@pytest.mark.asyncio
async def test_repeated_failures_lock_out_username(
    api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "LOGIN_MAX_FAILED_ATTEMPTS", 3)
    for _ in range(3):
        assert (await _login(api, "viewer", "wrong-password")).status_code == 401

    # Even the correct password is refused while locked out
    locked = await _login(api, "viewer", TEST_PASSWORD)
    assert locked.status_code == 429
    assert "Retry-After" in locked.headers

    # Other accounts are unaffected
    assert (await _login(api, "analyst", TEST_PASSWORD)).status_code == 200


@pytest.mark.asyncio
async def test_successful_login_resets_failure_counter(
    api: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "LOGIN_MAX_FAILED_ATTEMPTS", 3)
    for _ in range(2):
        await _login(api, "viewer", "wrong-password")
    assert (await _login(api, "viewer", TEST_PASSWORD)).status_code == 200
    for _ in range(2):
        await _login(api, "viewer", "wrong-password")
    assert (await _login(api, "viewer", TEST_PASSWORD)).status_code == 200


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_revokes_token(api: httpx.AsyncClient) -> None:
    token = (await _login(api, "analyst", TEST_PASSWORD)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await api.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert "token" not in me.json(), "/auth/me must not echo the bearer token"

    assert (await api.post("/auth/logout", headers=headers)).status_code == 204

    after = await api.get("/auth/me", headers=headers)
    assert after.status_code == 401
    assert "revoked" in after.json()["detail"].lower()

    # A fresh login still works
    assert (await _login(api, "analyst", TEST_PASSWORD)).status_code == 200


@pytest.mark.asyncio
async def test_revoked_token_rejected_on_mcp_path() -> None:
    token = create_access_token("u-1", "analyst", ["analyst"], ["database.read"])
    ctx = await authenticate_token(token)
    assert ctx.token_id and ctx.token_expires_at
    await auth_guard.get_revocation_list().revoke(ctx.token_id, float(ctx.token_expires_at))
    with pytest.raises(AuthenticationError) as exc_info:
        await authenticate_token(token)
    assert exc_info.value.details["reason"] == "token_revoked"


# ---------------------------------------------------------------------------
# Claim validation
# ---------------------------------------------------------------------------


def _raw_token(**overrides: Any) -> str:
    settings = get_settings()
    claims: dict[str, Any] = {
        "sub": "u-1",
        "jti": "abc",
        "iat": 1,
        "exp": 9_999_999_999,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def test_valid_raw_token_accepted() -> None:
    assert decode_access_token(_raw_token())["sub"] == "u-1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "some-other-service"},
        {"iss": "https://evil.example"},
        {"aud": None},
        {"iss": None},
        {"jti": None},
        {"exp": None},
    ],
)
def test_tokens_with_wrong_or_missing_claims_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(_raw_token(**overrides))


def test_extra_claims_cannot_override_reserved_claims() -> None:
    token = create_access_token(
        "u-1", "analyst", ["analyst"], [], extra_claims={"sub": "admin", "aud": "x"}
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "u-1"


# ---------------------------------------------------------------------------
# Production configuration and HTTP hardening
# ---------------------------------------------------------------------------


def test_production_rejects_insecure_defaults() -> None:
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET=DEFAULT_JWT_SECRET,
        AUTH_DEMO_SHORTCUTS=True,
        CORS_ALLOWED_ORIGINS=["*"],
    )
    errors = settings.production_config_errors()
    assert len(errors) == 3
    with pytest.raises(RuntimeError, match="Insecure production configuration"):
        settings.validate_for_environment()


def test_production_accepts_hardened_config() -> None:
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET="x" * 48,
        AUTH_DEMO_SHORTCUTS=False,
        CORS_ALLOWED_ORIGINS=["https://copilot.example.com"],
        DEBUG=False,
    )
    assert settings.production_config_errors() == []
    settings.validate_for_environment()


def test_development_allows_demo_settings() -> None:
    settings = Settings(APP_ENV="development", AUTH_DEMO_SHORTCUTS=True)
    settings.validate_for_environment()


def test_create_app_fails_fast_in_insecure_production(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "JWT_SECRET", DEFAULT_JWT_SECRET)
    with pytest.raises(RuntimeError):
        create_app()


@pytest.mark.asyncio
async def test_security_headers_present(api: httpx.AsyncClient) -> None:
    resp = await api.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_cors_does_not_allow_unknown_origins(api: httpx.AsyncClient) -> None:
    resp = await api.options(
        "/auth/login",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example"
    assert resp.headers.get("access-control-allow-origin") != "*"

    allowed = get_settings().CORS_ALLOWED_ORIGINS[0]
    ok = await api.options(
        "/auth/login",
        headers={"Origin": allowed, "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers.get("access-control-allow-origin") == allowed
