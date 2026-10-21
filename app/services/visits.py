import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import VisitedPlace
from app.schemas.place_record import PlaceIn


class VisitedLimitError(Exception):
    """Kullanıcı, takip edilen farklı mekan sayısı sınırına ulaştı."""


async def _bump(session: AsyncSession, user_id: uuid.UUID, place: PlaceIn) -> bool:
    """Mekan zaten kayıtlıysa sayacı ATOMİK artırır (visit_count + 1, okuyup yazmak
    değil: eşzamanlı iki istek birbirini ezmesin) ve mekan bilgisini tazeler."""
    result = await session.execute(
        update(VisitedPlace)
        .where(VisitedPlace.user_id == user_id, VisitedPlace.place_id == place.place_id)
        .values(
            visit_count=VisitedPlace.visit_count + 1,
            last_visited_at=func.now(),
            **place.model_dump(exclude={"place_id"}),
        )
    )
    return result.rowcount > 0


async def record_visit(session: AsyncSession, user_id: uuid.UUID, place: PlaceIn) -> None:
    """"Ulaşıldı" işaretini kaydeder: yeni mekansa satır açar, varsa sayacı artırır."""
    if await _bump(session, user_id, place):
        await session.commit()
        return
    count = await session.scalar(
        select(func.count()).select_from(VisitedPlace).where(VisitedPlace.user_id == user_id)
    )
    if (count or 0) >= get_settings().max_visited_places_per_user:
        raise VisitedLimitError
    session.add(VisitedPlace(user_id=user_id, **place.model_dump()))
    try:
        await session.commit()
    except IntegrityError:
        # Eşzamanlı başka bir istek aynı mekanı az önce ekledi: sayacı artır.
        await session.rollback()
        await _bump(session, user_id, place)
        await session.commit()


async def list_frequent(
    session: AsyncSession, user_id: uuid.UUID, limit: int
) -> list[VisitedPlace]:
    """En çok ziyaret edilenler önce; eşitlikte en son ziyaret edilen önce."""
    result = await session.scalars(
        select(VisitedPlace)
        .where(VisitedPlace.user_id == user_id)
        .order_by(VisitedPlace.visit_count.desc(), VisitedPlace.last_visited_at.desc())
        .limit(limit)
    )
    return list(result)


async def remove_visit(session: AsyncSession, user_id: uuid.UUID, place_id: str) -> bool:
    result = await session.execute(
        delete(VisitedPlace).where(
            VisitedPlace.user_id == user_id, VisitedPlace.place_id == place_id
        )
    )
    await session.commit()
    return result.rowcount > 0


async def clear_visits(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Kullanıcının tüm ziyaret geçmişini siler (KVKK: geçmişi temizleme hakkı)."""
    await session.execute(delete(VisitedPlace).where(VisitedPlace.user_id == user_id))
    await session.commit()
