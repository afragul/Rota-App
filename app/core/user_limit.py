import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import usage


async def _enforce(session: AsyncSession, user_id: str | None, kind: usage.UsageKind) -> None:
    """Giriş yapmış kullanıcı için günlük kotayı tüketir; doluysa 429. Misafirler
    (user_id yok) burada atlanır: onların kotası guest_limit.py'de (IP bazlı)."""
    if user_id is None:
        return
    settings = get_settings()
    limit = settings.user_daily_plan_limit if kind == "plans" else settings.user_daily_legs_limit
    try:
        allowed = await usage.consume(session, uuid.UUID(user_id), kind, limit)
    except usage.UserNotFoundError:
        # Token geçerli ama hesap silinmiş.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Hesap bulunamadı"
        ) from None
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            # Bilerek X-Guest-Limit-Reached YOK: frontend o başlığı "giriş yap" ekranına
            # yönlendirir; giriş yapmış kullanıcıya bu anlamsız olurdu.
            detail="Günlük kullanım hakkınız doldu. Yarın tekrar deneyebilirsiniz.",
            headers={"X-User-Limit-Reached": "1"},
        )


async def enforce_user_plan_limit(session: AsyncSession, user_id: str | None) -> None:
    await _enforce(session, user_id, "plans")


async def enforce_user_legs_limit(session: AsyncSession, user_id: str | None) -> None:
    await _enforce(session, user_id, "legs")
