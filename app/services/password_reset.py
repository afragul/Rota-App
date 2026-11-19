import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import PasswordResetToken, User
from app.services import refresh_tokens
from app.services.users import normalize_email


class InvalidResetTokenError(Exception):
    """Token yok, süresi dolmuş ya da zaten kullanılmış."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    # SQLite zaman damgasını saat dilimsiz döndürür (testler); hepsi UTC kabul edilir.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def build_email(raw_token: str) -> tuple[str, str]:
    """(konu, metin). Token URL'nin FRAGMENT'inde (#): fragment sunucuya ve Referer
    başlığına gitmez, yani erişim log'larına ve üçüncü taraflara sızmaz."""
    settings = get_settings()
    link = f"{settings.frontend_base_url.rstrip('/')}/#reset={quote(raw_token)}"
    minutes = settings.password_reset_expire_minutes
    body = (
        "Merhaba,\n\n"
        "Bugünlük hesabın için şifre sıfırlama isteği aldık. Yeni şifre belirlemek için "
        f"aşağıdaki bağlantıya tıkla (en fazla {minutes} dakika geçerli, yalnızca bir kez "
        "kullanılabilir):\n\n"
        f"{link}\n\n"
        "Bu isteği sen yapmadıysan bu e-postayı görmezden gelebilirsin; şifren değişmez.\n"
    )
    return "Bugünlük - Şifre sıfırlama", body


async def create_token(session: AsyncSession, email: str) -> tuple[str, str] | None:
    """Hesap varsa ve yakın zamanda e-posta gönderilmediyse yeni token açar ve
    (adres, ham_token) döndürür; aksi halde None. Çağıran, hangisi olduğunu istemciye
    ASLA yansıtmamalı (hesap var mı bilgisi sızmasın)."""
    settings = get_settings()
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        return None
    now = datetime.now(UTC)

    latest = await session.scalar(
        select(PasswordResetToken.created_at)
        .where(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )
    if latest is not None and now - _aware(latest) < timedelta(
        seconds=settings.password_reset_cooldown_seconds
    ):
        return None  # e-posta bombardımanı: sessizce yok say

    # Yeni istek eskilerini geçersiz kılar (aynı anda tek geçerli bağlantı).
    await session.execute(
        delete(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id)
        .execution_options(synchronize_session=False)
    )
    raw = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash(raw),
            expires_at=now + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    await session.commit()
    return user.email, raw


async def reset_password(session: AsyncSession, raw_token: str, new_password: str) -> None:
    """Token geçerliyse şifreyi değiştirir, token'ı tüketir ve TÜM oturumları kapatır
    (hesap ele geçirilmiş olabilir: açık kalan eski oturumlar düşmeli)."""
    row = await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(raw_token))
    )
    if row is None or _aware(row.expires_at) <= datetime.now(UTC):
        raise InvalidResetTokenError
    user_id: uuid.UUID = row.user_id
    new_hash = await hash_password(new_password)

    # Atomik tüketim: aynı token'la aynı anda gelen iki istekten yalnızca biri satırı silebilir.
    consumed = await session.execute(
        delete(PasswordResetToken)
        .where(PasswordResetToken.id == row.id)
        .execution_options(synchronize_session=False)
    )
    if consumed.rowcount != 1:
        await session.rollback()
        raise InvalidResetTokenError
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(password_hash=new_hash)
        .execution_options(synchronize_session=False)
    )
    await session.execute(
        delete(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    await refresh_tokens.revoke_all_for_user(session, user_id)
