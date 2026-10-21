import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import RefreshToken


class InvalidRefreshTokenError(Exception):
    """Refresh token yok, süresi dolmuş, iptal edilmiş ya da çalıntı."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    # SQLite zaman damgasını saat dilimsiz döndürür (testler); hepsi UTC kabul edilir.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def issue_token(
    session: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID | None = None
) -> str:
    """Yeni refresh token üretir, özetini kaydeder, ham değeri döndürür (cookie'ye yazılır)."""
    raw = secrets.token_urlsafe(48)
    now = datetime.now(UTC)
    session.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id or uuid.uuid4(),
            token_hash=_hash(raw),
            expires_at=now + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    # Bu kullanıcının süresi dolmuş eski kayıtları birikmesin.
    await session.execute(
        delete(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.expires_at < now)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    return raw


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    await session.commit()


async def rotate_token(session: AsyncSession, raw: str) -> tuple[uuid.UUID, str]:
    """Geçerli token'ı iptal edip aynı ailede yenisini açar. (user_id, yeni_ham_token) döner."""
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if row is None:
        raise InvalidRefreshTokenError
    now = datetime.now(UTC)

    if row.revoked_at is not None:
        grace = timedelta(seconds=get_settings().refresh_reuse_grace_seconds)
        if now - _aware(row.revoked_at) > grace:
            # İptal edilmiş token süre dışı tekrar geldi: çalınmış olabilir, aileyi kapat.
            await _revoke_family(session, row.family_id)
        raise InvalidRefreshTokenError
    if _aware(row.expires_at) <= now:
        raise InvalidRefreshTokenError

    # Atomik iptal: aynı anda gelen iki istekten yalnızca biri satırı iptal edebilir.
    result = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await session.rollback()
        raise InvalidRefreshTokenError
    await session.commit()
    return row.user_id, await issue_token(session, row.user_id, row.family_id)


async def revoke_token(session: AsyncSession, raw: str) -> None:
    """Çıkış: token'ın ailesini iptal eder (token bilinmiyorsa sessizce geçer)."""
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    if row is not None:
        await _revoke_family(session, row.family_id)


async def revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Kullanıcının tüm oturumlarını kapatır (şifre değişince)."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    await session.commit()
