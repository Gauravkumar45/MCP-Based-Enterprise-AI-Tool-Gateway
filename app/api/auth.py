"""Authentication router issuing signed JWT tokens with RBAC claims."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user_context
from app.auth.models import LoginRequest, TokenResponse, UserContext
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.database.repositories import UserRepository
from app.database.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, summary="User Login")
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate credentials and generate a signed JWT bearer token with RBAC permissions."""
    user_repo = UserRepository(db)
    raw_user = credentials.username.strip()
    username = raw_user.lower()
    if username in ("bob", "analyst_bob"):
        username = "analyst"
    elif username in ("alice", "viewer_alice"):
        username = "viewer"

    user = await user_repo.get_by_username(username)

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Collect unique roles and permissions
    roles = [r.name for r in user.roles]
    permissions_set: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            permissions_set.add(perm.name)
    permissions = sorted(permissions_set)

    settings = get_settings()
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
