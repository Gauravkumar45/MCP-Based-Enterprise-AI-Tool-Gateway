"""Unit tests for authentication, password hashing, and JWT token management."""

from datetime import timedelta

import pytest

from app.core.errors import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing() -> None:
    """Test bcrypt password hashing and verification."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_creation_and_decoding() -> None:
    """Test generating signed JWT access token and decoding RBAC claims."""
    token = create_access_token(
        user_id="user-123",
        username="alice",
        roles=["analyst"],
        permissions=["database.read", "documents.search"],
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["username"] == "alice"
    assert payload["roles"] == ["analyst"]
    assert "database.read" in payload["permissions"]
    assert "documents.search" in payload["permissions"]
    assert "jti" in payload
    assert "exp" in payload


def test_jwt_expiration() -> None:
    """Test that expired tokens raise AuthenticationError."""
    expired_token = create_access_token(
        user_id="user-expired",
        username="bob",
        roles=["viewer"],
        permissions=[],
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    with pytest.raises(AuthenticationError) as exc_info:
        decode_access_token(expired_token)
    assert "expired" in exc_info.value.message.lower()


def test_jwt_invalid_signature() -> None:
    """Test that tampering with JWT token signature raises AuthenticationError."""
    valid_token = create_access_token(
        user_id="user-test",
        username="charlie",
        roles=["admin"],
        permissions=["database.read"],
    )
    # Tamper with the signature portion
    parts = valid_token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.tampered_signature_bytes"
    with pytest.raises(AuthenticationError):
        decode_access_token(tampered_token)
