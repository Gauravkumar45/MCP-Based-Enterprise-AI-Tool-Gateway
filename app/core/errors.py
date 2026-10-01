"""Standardized error codes and exception classes for the MCP Tool Gateway."""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Standardized error codes as specified in enterprise gateway requirements."""

    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    INVALID_TOOL_INPUT = "INVALID_TOOL_INPUT"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_RATE_LIMITED = "TOOL_RATE_LIMITED"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class GatewayException(Exception):
    """Base exception for all MCP Gateway errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to structured dictionary format."""
        return {
            "error": self.code.value,
            "message": self.message,
            "details": self.details,
        }


class AuthenticationError(GatewayException):
    """Raised when authentication fails or token is missing/invalid."""

    def __init__(
        self, message: str = "Authentication failed", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code=ErrorCode.AUTHENTICATION_FAILED,
            message=message,
            details=details,
            status_code=401,
        )


class AuthorizationError(GatewayException):
    """Raised when user lacks permission to access or execute a tool."""

    def __init__(
        self,
        message: str = "User is not authorized to execute this tool",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.AUTHORIZATION_FAILED,
            message=message,
            details=details,
            status_code=403,
        )


class ToolNotFoundError(GatewayException):
    """Raised when the requested tool does not exist in registry."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            code=ErrorCode.TOOL_NOT_FOUND,
            message=f"Tool '{tool_name}' not found in registry",
            details={"tool_name": tool_name},
            status_code=404,
        )


class InvalidToolInputError(GatewayException):
    """Raised when tool arguments fail validation schemas."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=ErrorCode.INVALID_TOOL_INPUT,
            message=message,
            details=details,
            status_code=422,
        )


class ToolTimeoutError(GatewayException):
    """Raised when tool execution exceeds its configured timeout."""

    def __init__(self, tool_name: str, timeout_seconds: float) -> None:
        super().__init__(
            code=ErrorCode.TOOL_TIMEOUT,
            message=f"Execution of tool '{tool_name}' exceeded timeout of {timeout_seconds}s",
            details={"tool_name": tool_name, "timeout_seconds": timeout_seconds},
            status_code=504,
        )


class RateLimitExceededError(GatewayException):
    """Raised when rate limit is exceeded."""

    def __init__(self, key: str, retry_after: int) -> None:
        super().__init__(
            code=ErrorCode.TOOL_RATE_LIMITED,
            message=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
            details={"key": key, "retry_after_seconds": retry_after},
            status_code=429,
        )


class ToolExecutionError(GatewayException):
    """Raised when tool execution fails unexpectedly."""

    def __init__(self, tool_name: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=ErrorCode.TOOL_EXECUTION_FAILED,
            message=f"Failed to execute tool '{tool_name}': {message}",
            details=details,
            status_code=500,
        )


class DatabaseSecurityError(GatewayException):
    """Raised when SQL safety check fails (e.g. DDL/DML injection or disallowed syntax)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=ErrorCode.DATABASE_ERROR,
            message=message,
            details=details,
            status_code=400,
        )
