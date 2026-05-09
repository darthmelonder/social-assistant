"""Unit tests for the database module.

These tests verify the lazy-init engine and session factory without
opening a real DB connection (SQLAlchemy defers connection until first query).
"""
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def test_get_engine_returns_async_engine():
    from app.core.database import get_engine

    engine = get_engine()
    assert isinstance(engine, AsyncEngine)


def test_get_engine_is_cached():
    from app.core.database import get_engine

    assert get_engine() is get_engine()


def test_get_session_factory_returns_async_sessionmaker():
    from app.core.database import get_session_factory

    factory = get_session_factory()
    assert isinstance(factory, async_sessionmaker)


def test_get_session_factory_is_cached():
    from app.core.database import get_session_factory

    assert get_session_factory() is get_session_factory()


def test_engine_url_matches_settings():
    from app.core.config import get_settings
    from app.core.database import get_engine

    engine = get_engine()
    settings = get_settings()
    # render_as_string(hide_password=False) gives the full URL for comparison
    assert engine.url.render_as_string(hide_password=False) == settings.DATABASE_URL
