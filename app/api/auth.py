"""Authentication router issuing signed JWT tokens with RBAC claims."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user_context
from app.auth.models import LoginRequest, TokenResponse, UserContext
from app.core.config import get_settings
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    verify_password_with_demo_shortcuts,
)
from app.database.repositories import UserRepository
from app.database.session import get_db
from app.services.auth_guard import LoginThrottle, get_revocation_list

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Demo-only username aliases, honoured only when AUTH_DEMO_SHORTCUTS is enabled.
DEMO_USERNAME_ALIASES = {
    "bob": "analyst",
    "analyst_bob": "analyst",
    "alice": "viewer",
    "viewer_alice": "viewer",
}

# Used to spend the same bcrypt time when the username does not exist, so response timing
# does not reveal which usernames are valid.
_DUMMY_PASSWORD_HASH = hash_password("timing-equalisation-dummy-password")


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenResponse, summary="User Login")
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate credentials and generate a signed JWT bearer token with RBAC permissions."""
    settings = get_settings()
    user_repo = UserRepository(db)
    username = credentials.username.strip().lower()
    if settings.AUTH_DEMO_SHORTCUTS:
        username = DEMO_USERNAME_ALIASES.get(username, username)

    throttle = LoginThrottle()
    if await throttle.is_locked(username):
        logger.warning("Login blocked for locked-out username '%s'", username)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(throttle.window_seconds)},
        )

    check_password = (
        verify_password_with_demo_shortcuts if settings.AUTH_DEMO_SHORTCUTS else verify_password
    )
    user = await user_repo.get_by_username(username)
    if user is None:
        verify_password(credentials.password, _DUMMY_PASSWORD_HASH)
        await throttle.record_failure(username)
        raise _invalid_credentials()
    if not check_password(credentials.password, user.hashed_password):
        await throttle.record_failure(username)
        raise _invalid_credentials()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    await throttle.reset(username)

    # Collect unique roles and permissions
    roles = [r.name for r in user.roles]
    permissions_set: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions_set.add(perm.name)
    permissions = sorted(permissions_set)

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        roles=roles,
        permissions=permissions,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        username=user.username,
        roles=roles,
        permissions=permissions,
    )


@router.get("/me", response_model=UserContext, summary="Current User Context")
async def get_me(user: UserContext = Depends(get_current_user_context)) -> UserContext:
    """Retrieve authenticated user's session claims, active roles, and granted permissions."""
    return user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke Current Token",
)
async def logout(user: UserContext = Depends(get_current_user_context)) -> Response:
    """Revoke the caller's bearer token so it is rejected by REST and MCP endpoints."""
    if user.token_id and user.token_expires_at:
        await get_revocation_list().revoke(user.token_id, float(user.token_expires_at))
        logger.info("Revoked token %s for user %s", user.token_id, user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
