"""Structured logging with contextual tracking (request_id, trace_id, user_id, tool_name)."""

import contextvars
import json
import logging
import sys
from typing import Any

# Context variables for distributed request tracing
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
trace_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
user_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")
tool_name_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("tool_name", default="")


class StructuredJsonFormatter(logging.Formatter):
    """JSON log formatter adhering to enterprise observability standards."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get() or getattr(record, "request_id", None),
            "trace_id": trace_id_ctx.get() or getattr(record, "trace_id", None),
            "user_id": user_id_ctx.get() or getattr(record, "user_id", None),
            "tool_name": tool_name_ctx.get() or getattr(record, "tool_name", None),
        }

        # Include custom metric fields if provided in extra
        for field in ("execution_time_ms", "status", "latency_ms", "status_code", "error_code"):
            if hasattr(record, field):
                log_payload[field] = getattr(record, field)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps({k: v for k, v in log_payload.items() if v is not None})


def setup_logging(log_level: str = "INFO", json_format: bool = True) -> logging.Logger:
    """Configure root logger with structured JSON formatting."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )

    root_logger.addHandler(handler)
    return logging.getLogger("gateway")


logger = logging.getLogger("gateway")
