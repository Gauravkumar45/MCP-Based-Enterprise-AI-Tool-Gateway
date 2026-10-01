"""SQL safety validation engine using SQLGlot AST analysis."""

import re

import sqlglot
from sqlglot import exp

from app.core.errors import DatabaseSecurityError

FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "UPSERT",
    "MERGE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "EXEC",
    "CALL",
    "VACUUM",
    "COPY",
    "PRAGMA",
    "ATTACH",
    "DETACH",
    "KILL",
}

FORBIDDEN_TABLES = {
    "pg_shadow",
    "pg_authid",
    "pg_user",
    "pg_database",
    "pg_stat_activity",
    "pg_settings",
}

FORBIDDEN_EXPRESSION_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,
    exp.Grant,
    exp.Revoke,
    exp.Pragma,
    exp.Merge,
)


class SQLValidator:
    """Enterprise SQL safety validator preventing injection, mutations, and denial-of-service."""

    def __init__(self, max_limit: int = 1000, default_limit: int = 100) -> None:
        self.max_limit = max_limit
        self.default_limit = default_limit

    def validate_and_sanitize(
        self, raw_query: str, requested_limit: int | None = None
    ) -> tuple[str, int]:
        """Validate that query is strictly read-only SELECT and enforce safe row limit.

        Returns:
            (sanitized_sql, effective_limit)
        Raises:
            DatabaseSecurityError on any validation violation.
        """
        if not raw_query or not raw_query.strip():
            raise DatabaseSecurityError("Query string cannot be empty")

        clean_query = raw_query.strip().rstrip(";")

        # 1. Quick regex keyword check for obvious destructive attempts
        upper_query = clean_query.upper()
        for kw in FORBIDDEN_KEYWORDS:
            pattern = rf"\b{kw}\b"
            if re.search(pattern, upper_query):
                raise DatabaseSecurityError(
                    f"Destructive SQL operation detected: '{kw}' keyword is forbidden",
                    details={"forbidden_keyword": kw},
                )

        # 2. Parse AST using SQLGlot
        try:
            expressions = sqlglot.parse(clean_query, read="postgres")
        except Exception as e:
            raise DatabaseSecurityError(
                f"SQL Syntax Error or unparseable query: {e!s}",
                details={"raw_query": clean_query},
            ) from e

        if not expressions:
            raise DatabaseSecurityError("Query contains no executable statements")

        # 3. Block multi-statement queries (e.g. SELECT 1; DROP TABLE users)
        if len(expressions) > 1:
            raise DatabaseSecurityError(
                "Multi-statement queries are strictly prohibited",
                details={"statement_count": len(expressions)},
            )

        root_expr = expressions[0]

        # 4. AST Type check: Must be a Select expression (or CTE Union/Select)
        if not isinstance(root_expr, (exp.Select, exp.Union)):
            raise DatabaseSecurityError(
                f"Disallowed statement type: expected SELECT, got {type(root_expr).__name__}",
                details={"statement_type": type(root_expr).__name__},
            )

        # 5. AST traversal to ensure no nested mutation expressions
        for node in root_expr.walk():
            if isinstance(node, FORBIDDEN_EXPRESSION_TYPES):
                raise DatabaseSecurityError(
                    f"Forbidden SQL operation found in AST: {type(node).__name__}",
                    details={"node_type": type(node).__name__},
                )
            if isinstance(node, exp.Table):
                table_name = node.name.lower()
                if table_name in FORBIDDEN_TABLES:
                    raise DatabaseSecurityError(
                        f"Access to sensitive internal catalog table '{table_name}' is forbidden",
                        details={"table_name": table_name},
                    )

        # 6. Row Limit Enforcement
        limit_to_apply = requested_limit if requested_limit is not None else self.default_limit
        if limit_to_apply > self.max_limit:
            limit_to_apply = self.max_limit

        existing_limit = root_expr.args.get("limit")
        if existing_limit is not None:
            # Query already has a LIMIT clause; check that it does not exceed max_limit
            try:
                # expression attribute holds the limit literal/value
                val_node = existing_limit.expression
                curr_limit_val = int(val_node.this)
                if curr_limit_val > self.max_limit:
                    limit_to_apply = self.max_limit
                else:
                    limit_to_apply = curr_limit_val
            except Exception:
                limit_to_apply = self.max_limit

        # Clear existing limit and re-apply bounded limit
        root_expr.set("limit", None)
        root_expr = root_expr.limit(limit_to_apply)

        sanitized_sql = root_expr.sql(dialect="postgres")
        return sanitized_sql, limit_to_apply
