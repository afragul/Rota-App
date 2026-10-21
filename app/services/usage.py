import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyUsage, User

UsageKind = Literal["plans", "legs"]

# Türkiye 2016'dan beri yaz saati uygulamıyor: sabit UTC+3 yeterli (tzdata gerekmez).
_TURKEY = timedelta(hours=3)
# Eski günlerin satırları birikmesin diye bu kadar günden eskisi silinir.
_KEEP_DAYS = 7


class UserNotFoundError(Exception):
    """Sayaç yazılacak hesap yok (silinmiş)."""


def today() -> date:
    return (datetime.now(UTC) + _TURKEY).date()


async def consume(session: AsyncSession, user_id: uuid.UUID, kind: UsageKind, limit: int) -> bool:
    """Bugünkü sayaca bir birim ekler. Limit dolmuşsa eklemez ve False döner.

    Artırma tek bir koşullu UPDATE ile yapılır (`... WHERE sayaç < limit`): oku-sonra-yaz
    değil, atomik; aynı anda gelen istekler limiti aşamaz."""
    if limit <= 0:
        return False
    day = today()
    column = getattr(DailyUsage, kind)

    async def _bump() -> bool:
        result = await session.execute(
            update(DailyUsage)
            .where(DailyUsage.user_id == user_id, DailyUsage.day == day, column < limit)
            .values({kind: column + 1})
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    if await _bump():
        await session.commit()
        return True

    if await session.scalar(
        select(DailyUsage.user_id).where(DailyUsage.user_id == user_id, DailyUsage.day == day)
    ):
        await session.rollback()
        return False  # bugünün satırı var ve limit dolu

    # Bugünün ilk çağrısı: eski günleri temizle, sonra satırı aç. Temizlik, ekleme
    # BEKLEMEDEYKEN çalışsaydı otomatik flush eklemeyi erken tetikler ve eşzamanlı
    # istekte çıkan çakışma aşağıdaki try/except'in DIŞINDA patlardı (500).
    await session.execute(
        delete(DailyUsage)
        .where(DailyUsage.user_id == user_id, DailyUsage.day < day - timedelta(days=_KEEP_DAYS))
        .execution_options(synchronize_session=False)
    )
    try:
        session.add(DailyUsage(user_id=user_id, day=day, **{kind: 1}))
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        # Ya eşzamanlı başka bir istek satırı az önce açtı (tekrar dene) ya da hesap yok.
        if await session.scalar(select(User.id).where(User.id == user_id)) is None:
            raise UserNotFoundError from None
        if await _bump():
            await session.commit()
            return True
        await session.rollback()
        return False
