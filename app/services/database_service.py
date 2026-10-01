"""Database query service with read-only execution, timeout enforcement, and AST safety validation."""

import asyncio
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import DatabaseSecurityError, ToolExecutionError, ToolTimeoutError
from app.tools.sql_validator import SQLValidator


class DatabaseService:
    """Service executing safe read-only SQL queries against enterprise database."""

    def __init__(
        self,
        session: AsyncSession,
        sql_validator: SQLValidator | None = None,
    ) -> None:
        self.session = session
        settings = get_settings()
        self.validator = sql_validator or SQLValidator(
            max_limit=settings.MAX_QUERY_LIMIT,
            default_limit=100,
        )

    async def execute_query(
        self,
        query: str,
        limit: int = 100,
        timeout_seconds: float = 10.0,
    ) -> dict[str, Any]:
        """Validate, sanitize, and execute read-only SQL query with hard timeout."""
        settings = get_settings()
        effective_timeout = min(timeout_seconds, float(settings.MAX_TOOL_TIMEOUT_SECONDS))

        # 1. SQL Safety and AST Validation
        sanitized_query, enforced_limit = self.validator.validate_and_sanitize(
            raw_query=query,
            requested_limit=limit,
        )

        t0 = time.perf_counter()
        try:
            # 2. Async execution guarded by timeout
            async def _run() -> Any:
                # Set transaction read-only if supported by dialect
                try:
                    await self.session.execute(text("SET TRANSACTION READ ONLY"))
                except Exception:
                    # SQLite dialect does not have SET TRANSACTION READ ONLY
                    pass

                result = await self.session.execute(text(sanitized_query))
                rows = [dict(row._mapping) for row in result]
                columns = list(result.keys()) if rows else []
                return rows, columns

            rows, columns = await asyncio.wait_for(_run(), timeout=effective_timeout)
            execution_time_ms = round((time.perf_counter() - t0) * 1000, 2)

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "limit_applied": enforced_limit,
                "execution_time_ms": execution_time_ms,
                "sanitized_query": sanitized_query,
            }

        except TimeoutError as e:
            raise ToolTimeoutError(
                tool_name="query_database", timeout_seconds=effective_timeout
            ) from e
        except DatabaseSecurityError:
            raise
        except Exception as e:
            raise ToolExecutionError(
                tool_name="query_database",
                message=f"Database execution failed: {e!s}",
                details={"query": sanitized_query},
            ) from e
