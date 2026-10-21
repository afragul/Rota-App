from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Süreç başına tek bir engine (bağlantı havuzu). DATABASE_URL yoksa hata verir."""
    url = get_settings().database_url
    if url is None:
        raise RuntimeError("DATABASE_URL tanımlı değil; veritabanı kullanılamaz.")
    return create_async_engine(url.get_secret_value(), pool_pre_ping=True)


@lru_cache
def _session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: istek başına bir oturum açar, bitince kapatır."""
    async with _session_factory()() as session:
        yield session
