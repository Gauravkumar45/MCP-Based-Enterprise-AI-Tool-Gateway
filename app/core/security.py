"""Security utilities: password hashing, verification, and JWT token management."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.errors import AuthenticationError


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


DEMO_SEED_PASSWORD = "Password123!"
_DEMO_PASSWORD_VARIANTS = frozenset({"password", "password123", "password123!", "admin"})


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash (constant-time, no shortcuts)."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def verify_password_with_demo_shortcuts(plain_password: str, hashed_password: str) -> bool:
    """Verify a password, also accepting common variants of the demo seed password.

    Only call this when ``AUTH_DEMO_SHORTCUTS`` is enabled (local demos). Production startup
    refuses that setting, so the relaxed check can never run against real accounts.
    """
    if verify_password(plain_password, hashed_password):
        return True
    if plain_password.lower() in _DEMO_PASSWORD_VARIANTS:
        return verify_password(DEMO_SEED_PASSWORD, hashed_password)
    return False


def create_access_token(
    user_id: str,
    username: str,
    roles: list[str],
    permissions: list[str],
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Generate a signed JWT access token containing RBAC claims."""
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "roles": roles,
        "permissions": permissions,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        # Reserved claims cannot be overridden by callers.
        reserved = {"sub", "iss", "aud", "jti", "iat", "exp"}
        payload.update({k: v for k, v in extra_claims.items() if k not in reserved})

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "jti", "iss", "aud"]},
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationError(
            "JWT token has expired", details={"reason": "token_expired"}
        ) from e
    except jwt.InvalidTokenError as e:
        raise AuthenticationError("Invalid JWT token", details={"reason": "token_invalid"}) from e
