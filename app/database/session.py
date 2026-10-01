"""Database connection management and async session lifecycle."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_readonly_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_readonly_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or initialize primary async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict[str, Any] = {}
        # SQLite specific configuration for testing compatibility
        if settings.DATABASE_URL.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DB_ECHO,
                connect_args=connect_args,
            )
        else:
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DB_ECHO,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_pre_ping=True,
            )
    return _engine


def get_readonly_engine() -> AsyncEngine:
    """Get or initialize dedicated read-only database engine."""
    global _readonly_engine
    if _readonly_engine is None:
        settings = get_settings()
        url = settings.DATABASE_READONLY_URL or settings.DATABASE_URL
        connect_args: dict[str, Any] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            _readonly_engine = create_async_engine(
                url,
                echo=settings.DB_ECHO,
                connect_args=connect_args,
            )
        else:
            _readonly_engine = create_async_engine(
                url,
                echo=settings.DB_ECHO,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_pre_ping=True,
            )
    return _readonly_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create primary async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


def get_readonly_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create read-only async session factory."""
    global _readonly_session_factory
    if _readonly_session_factory is None:
        engine = get_readonly_engine()
        _readonly_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _readonly_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session with automatic transaction management."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_readonly_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a dedicated read-only database session."""
    factory = get_readonly_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()  # Ensure read-only sessions never commit mutations


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for standalone async sessions outside FastAPI request scope."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def readonly_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for standalone read-only sessions."""
    factory = get_readonly_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
