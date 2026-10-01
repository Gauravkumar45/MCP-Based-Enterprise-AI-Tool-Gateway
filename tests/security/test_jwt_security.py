"""Security tests for JWT verification, forged claims, algorithm confusion, and expiration."""

from datetime import timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.core.security import create_access_token, decode_access_token


def test_reject_forged_signature() -> None:
    """Security test: Reject token signed with forged secret key."""
    settings = get_settings()
    forged_token = jwt.encode(
        {"sub": "attacker", "roles": ["admin"], "permissions": ["database.read"]},
        "fake-secret-key-attacker-controlled-12345",
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(forged_token)


def test_reject_none_algorithm_attack() -> None:
    """Security test: Reject 'none' algorithm token bypass."""
    none_alg_token = (
        "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhZG1pbiIsInJvbGVzIjpbImFkbWluIl19."
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(none_alg_token)


def test_reject_expired_token() -> None:
    """Security test: Reject expired credentials."""
    expired_token = create_access_token(
        user_id="user-expired",
        username="expired_user",
        roles=["analyst"],
        permissions=["database.read"],
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(AuthenticationError) as exc_info:
        decode_access_token(expired_token)
    assert "expired" in exc_info.value.message.lower()
