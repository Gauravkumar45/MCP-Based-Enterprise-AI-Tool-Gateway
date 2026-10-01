"""JWT authentication dependencies and permission validation."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import UserContext
from app.core.errors import AuthenticationError
from app.core.logging import user_id_ctx
from app.core.security import decode_access_token

security = HTTPBearer(auto_error=False)


async def get_current_user_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    authorization: Annotated[str | None, Header()] = None,
    token_query: Annotated[str | None, Query(alias="token")] = None,
) -> UserContext:
    """Extract, decode, and validate JWT credentials from header or query param."""
    token: str | None = None

    if credentials and credentials.credentials:
        token = credentials.credentials
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif token_query:
        token = token_query

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user_context = UserContext(
        user_id=str(payload.get("sub", "")),
        username=str(payload.get("username", "")),
        roles=list(payload.get("roles", [])),
        permissions=list(payload.get("permissions", [])),
        token=token,
    )

    # Propagate user_id to structured logging context
    user_id_ctx.set(user_context.user_id)
    return user_context


def require_permission(required_perm: str) -> Callable[[UserContext], UserContext]:
    """Dependency factory checking that the authenticated user possesses the required permission."""

    def _dependency(user: Annotated[UserContext, Depends(get_current_user_context)]) -> UserContext:
        if not user.has_permission(required_perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User lacks required permission: {required_perm}",
            )
        return user

    return _dependency
