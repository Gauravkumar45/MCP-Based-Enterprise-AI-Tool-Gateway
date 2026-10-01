"""Pytest global test fixtures and configuration."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.models import UserContext
from app.auth.permissions import DEFAULT_ROLE_PERMISSIONS
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password
from app.database.models import (
    Base,
    Customer,
    Document,
    Invoice,
    Order,
    Permission,
    Role,
    User,
)
from app.mcp.registry import ToolRegistry, create_default_registry


@pytest.fixture
def test_settings() -> Settings:
    """Fixture returning application test settings."""
    settings = get_settings()
    return settings


@pytest_asyncio.fixture
async def async_test_engine() -> AsyncGenerator[Any, None]:
    """In-memory SQLite async engine for isolated and blazingly fast testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Isolated database session fixture populated with seed entities."""
    session_factory = async_sessionmaker(
        bind=async_test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        # Seed test permissions
        perms_map: dict[str, Permission] = {}
        for _role, p_list in DEFAULT_ROLE_PERMISSIONS.items():
            for p in p_list:
                if p not in perms_map:
                    perm = Permission(name=p, description=p)
                    session.add(perm)
                    perms_map[p] = perm
        await session.flush()

        # Seed test roles
        roles_map: dict[str, Role] = {}
        for r_name, p_names in DEFAULT_ROLE_PERMISSIONS.items():
            role = Role(name=r_name, description=f"{r_name} role")
            for p_name in p_names:
                role.permissions.append(perms_map[p_name])
            session.add(role)
            roles_map[r_name] = role
        await session.flush()

        # Seed test users
        admin_user = User(
            username="admin", email="admin@test.com", hashed_password=hash_password("Pass123!")
        )
        admin_user.roles.append(roles_map["admin"])
        session.add(admin_user)

        analyst_user = User(
            username="analyst", email="analyst@test.com", hashed_password=hash_password("Pass123!")
        )
        analyst_user.roles.append(roles_map["analyst"])
        session.add(analyst_user)

        viewer_user = User(
            username="viewer", email="viewer@test.com", hashed_password=hash_password("Pass123!")
        )
        viewer_user.roles.append(roles_map["viewer"])
        session.add(viewer_user)

        # Seed sample customer, invoice, order, document
        cust = Customer(
            customer_id="CUST-1001",
            name="Acme Corp",
            email="acme@test.com",
            tier="enterprise",
            lifetime_value=500000.0,
            status="active",
        )
        session.add(cust)

        now = datetime.now(UTC)
        inv = Invoice(
            invoice_id="INV-2024-001",
            customer_id="CUST-1001",
            amount=50000.0,
            currency="USD",
            status="paid",
            due_date=now + timedelta(days=30),
            issued_date=now,
        )
        session.add(inv)

        ord_item = Order(
            order_id="ORD-9001",
            customer_id="CUST-1001",
            total_amount=50000.0,
            status="delivered",
            items_count=5,
            tracking_number="TRK-12345",
        )
        session.add(ord_item)

        doc = Document(
            document_id="DOC-001",
            title="Enterprise Security Policy",
            content="All access to enterprise tools requires valid RBAC tokens and AST SQL checks.",
            category="security",
            source="wiki/sec.md",
        )
        session.add(doc)

        await session.commit()
        yield session


@pytest.fixture
def admin_context() -> UserContext:
    """UserContext for admin user."""
    return UserContext(
        user_id="user-admin-1",
        username="admin",
        roles=["admin"],
        permissions=DEFAULT_ROLE_PERMISSIONS["admin"],
        token=create_access_token(
            "user-admin-1", "admin", ["admin"], DEFAULT_ROLE_PERMISSIONS["admin"]
        ),
    )


@pytest.fixture
def analyst_context() -> UserContext:
    """UserContext for analyst user."""
    return UserContext(
        user_id="user-analyst-2",
        username="analyst",
        roles=["analyst"],
        permissions=DEFAULT_ROLE_PERMISSIONS["analyst"],
        token=create_access_token(
            "user-analyst-2", "analyst", ["analyst"], DEFAULT_ROLE_PERMISSIONS["analyst"]
        ),
    )


@pytest.fixture
def viewer_context() -> UserContext:
    """UserContext for viewer user (read-only document and system status only)."""
    return UserContext(
        user_id="user-viewer-3",
        username="viewer",
        roles=["viewer"],
        permissions=DEFAULT_ROLE_PERMISSIONS["viewer"],
        token=create_access_token(
            "user-viewer-3", "viewer", ["viewer"], DEFAULT_ROLE_PERMISSIONS["viewer"]
        ),
    )


@pytest.fixture
def tool_registry() -> ToolRegistry:
    """Default tool registry instance."""
    return create_default_registry()
