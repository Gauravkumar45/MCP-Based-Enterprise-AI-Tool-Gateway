"""Authentication and authorization schemas."""

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """Authenticated user context propagated throughout tool execution and audit trails."""

    user_id: str
    username: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    token: str | None = None

    def has_permission(self, permission: str) -> bool:
        """Check if user holds the specified permission."""
        return permission in self.permissions or "admin" in self.roles


class LoginRequest(BaseModel):
    """User login credential payload."""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    """JWT access token response model."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    username: str
    roles: list[str]
    permissions: list[str]
