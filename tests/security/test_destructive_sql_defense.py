"""Security tests verifying that no data modification or DDL query can bypass the gateway."""

import pytest

from app.core.errors import DatabaseSecurityError
from app.tools.sql_validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator(max_limit=100)


@pytest.mark.parametrize(
    "destructive_query",
    [
        "DROP TABLE users;",
        "DROP DATABASE mcp_gateway;",
        "ALTER TABLE users DROP COLUMN email;",
        "CREATE TABLE backdoor (id int);",
        "INSERT INTO users (id, username) VALUES ('x', 'admin2');",
        "UPDATE users SET is_active = true WHERE username = 'bad';",
        "DELETE FROM audit_logs;",
        "TRUNCATE TABLE audit_logs;",
        "GRANT ALL PRIVILEGES ON DATABASE mcp_gateway TO evil;",
        "REVOKE ALL ON users FROM admin;",
        "COPY users TO '/tmp/leak.txt';",
        "REPLACE INTO customers (id) VALUES (1);",
    ],
)
def test_all_destructive_operations_blocked(
    validator: SQLValidator, destructive_query: str
) -> None:
    """Security test: Every DDL, DML, and privilege escalation command is rejected with DatabaseSecurityError."""
    with pytest.raises(DatabaseSecurityError):
        validator.validate_and_sanitize(destructive_query)
