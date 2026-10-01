"""Security tests for SQL injection prevention via AST analysis."""

import pytest

from app.core.errors import DatabaseSecurityError
from app.tools.sql_validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator(max_limit=1000)


@pytest.mark.parametrize(
    "injection_payload",
    [
        "SELECT * FROM customers WHERE name = '' OR '1'='1'",  # Valid syntax, but safe read-only
        "SELECT * FROM customers; EXEC xp_cmdshell('dir')",
        "SELECT * FROM customers; SHUTDOWN;",
        "SELECT * FROM pg_shadow",
        "SELECT * FROM pg_authid",
        "SELECT pg_sleep(10)",
        "SELECT 1; ATTACH DATABASE '/tmp/pwned.db' AS pwned",
        "SELECT * FROM customers UNION SELECT * FROM pg_shadow",
    ],
)
def test_sql_injection_attempts(validator: SQLValidator, injection_payload: str) -> None:
    """Security test: Reject or safely constrain malicious SQL patterns."""
    if any(
        forbidden in injection_payload.upper()
        for forbidden in ["EXEC", "SHUTDOWN", "PG_SHADOW", "PG_AUTHID", "ATTACH"]
    ):
        with pytest.raises(DatabaseSecurityError):
            validator.validate_and_sanitize(injection_payload)
    else:
        # Queries without forbidden keywords/tables must be parsed and have safe LIMIT enforced
        sanitized, limit = validator.validate_and_sanitize(injection_payload)
        assert "LIMIT" in sanitized
        assert limit <= 1000
