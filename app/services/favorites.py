import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import FavoritePlace
from app.schemas.place_record import PlaceIn


class FavoriteLimitError(Exception):
    """Kullanıcı favori sayısı sınırına ulaştı."""


async def _get(session: AsyncSession, user_id: uuid.UUID, place_id: str) -> FavoritePlace | None:
    return await session.scalar(
        select(FavoritePlace).where(
            FavoritePlace.user_id == user_id, FavoritePlace.place_id == place_id
        )
    )


async def add_favorite(
    session: AsyncSession, user_id: uuid.UUID, place: PlaceIn
) -> tuple[FavoritePlace, bool]:
    """Mekanı favoriye ekler. (kayıt, yeni_mi) döner; zaten favoriyse mevcut kayıt
    ve False (idempotent: ikinci çağrı hata vermez)."""
    existing = await _get(session, user_id, place.place_id)
    if existing is not None:
        return existing, False
    count = await session.scalar(
        select(func.count()).select_from(FavoritePlace).where(FavoritePlace.user_id == user_id)
    )
    if (count or 0) >= get_settings().max_favorites_per_user:
        raise FavoriteLimitError
    favorite = FavoritePlace(user_id=user_id, **place.model_dump())
    session.add(favorite)
    try:
        await session.commit()
    except IntegrityError:
        # Kontrol ile commit arasında aynı mekan eşzamanlı eklendi.
        await session.rollback()
        existing = await _get(session, user_id, place.place_id)
        if existing is None:
            raise
        return existing, False
    return favorite, True


async def list_favorites(session: AsyncSession, user_id: uuid.UUID) -> list[FavoritePlace]:
    result = await session.scalars(
        select(FavoritePlace)
        .where(FavoritePlace.user_id == user_id)
        .order_by(FavoritePlace.created_at.desc())
    )
    return list(result)


async def remove_favorite(session: AsyncSession, user_id: uuid.UUID, place_id: str) -> bool:
    result = await session.execute(
        delete(FavoritePlace).where(
            FavoritePlace.user_id == user_id, FavoritePlace.place_id == place_id
        )
    )
    await session.commit()
    return result.rowcount > 0
