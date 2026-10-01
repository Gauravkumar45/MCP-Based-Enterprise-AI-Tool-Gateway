"""Unit tests for AST-based SQL safety validation."""

import pytest

from app.core.errors import DatabaseSecurityError
from app.tools.sql_validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator(max_limit=500, default_limit=100)


def test_valid_select_query(validator: SQLValidator) -> None:
    """Test standard SELECT query validation and default limit injection."""
    query = "SELECT id, name, email FROM customers WHERE status = 'active'"
    sanitized, limit = validator.validate_and_sanitize(query)
    assert "SELECT" in sanitized
    assert "LIMIT 100" in sanitized
    assert limit == 100


def test_select_with_custom_safe_limit(validator: SQLValidator) -> None:
    """Test custom limit within allowed bounds."""
    query = "SELECT * FROM orders"
    sanitized, limit = validator.validate_and_sanitize(query, requested_limit=50)
    assert "LIMIT 50" in sanitized
    assert limit == 50


def test_excessive_limit_clamping(validator: SQLValidator) -> None:
    """Test that limits exceeding max_limit are clamped down to max_limit."""
    query = "SELECT * FROM orders LIMIT 9999"
    sanitized, limit = validator.validate_and_sanitize(query)
    assert "LIMIT 500" in sanitized
    assert limit == 500


@pytest.mark.parametrize(
    "destructive_sql",
    [
        "DROP TABLE users",
        "TRUNCATE TABLE customers",
        "DELETE FROM invoices WHERE id = 1",
        "INSERT INTO customers (id, name) VALUES ('1', 'hacker')",
        "UPDATE users SET is_active = false",
        "ALTER TABLE users ADD COLUMN compromised text",
        "GRANT ALL PRIVILEGES ON ALL TABLES TO PUBLIC",
        "VACUUM FULL",
    ],
)
def test_destructive_sql_rejection(validator: SQLValidator, destructive_sql: str) -> None:
    """Ensure all mutation operations are blocked with DatabaseSecurityError."""
    with pytest.raises(DatabaseSecurityError):
        validator.validate_and_sanitize(destructive_sql)


def test_multi_statement_blocking(validator: SQLValidator) -> None:
    """Test that multi-statement chained queries are blocked."""
    chained_query = "SELECT 1; DROP TABLE customers;"
    with pytest.raises(DatabaseSecurityError) as exc_info:
        validator.validate_and_sanitize(chained_query)
    assert (
        "forbidden" in exc_info.value.message.lower()
        or "multi-statement" in exc_info.value.message.lower()
    )


def test_sensitive_system_catalog_blocking(validator: SQLValidator) -> None:
    """Test blocking access to sensitive internal catalog tables."""
    queries = [
        "SELECT * FROM pg_shadow",
        "SELECT * FROM pg_authid",
        "SELECT * FROM pg_user",
    ]
    for q in queries:
        with pytest.raises(DatabaseSecurityError) as exc_info:
            validator.validate_and_sanitize(q)
        assert (
            "forbidden" in exc_info.value.message.lower()
            or "catalog" in exc_info.value.message.lower()
        )


def test_empty_query_rejection(validator: SQLValidator) -> None:
    """Test that empty or whitespace-only queries are rejected."""
    with pytest.raises(DatabaseSecurityError):
        validator.validate_and_sanitize("   ")
