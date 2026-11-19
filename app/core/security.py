import asyncio
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()
_JWT_ALGORITHM = "HS256"
_JWT_ISSUER = "bugunluk"

# Kullanıcı bulunamadığında da gerçek bir doğrulama süresi harcayabilmek için
# (zamanlama farkından "bu e-posta kayıtlı mı" sızmasın) sahte bir hash.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


async def hash_password(password: str) -> str:
    # argon2 CPU-bound ve yavaş (kasıtlı); event loop'u bloklamasın diye thread'de.
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password_hash: str | None, password: str) -> bool:
    """Şifreyi hash'e karşı doğrular. password_hash None ise (kullanıcı yok)
    sahte hash'e karşı doğrulama yapıp her zaman False döner."""

    def _check() -> bool:
        try:
            return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
        except (VerificationError, InvalidHashError):
            return False

    return await asyncio.to_thread(_check)


def create_access_token(user_id: str) -> tuple[str, int]:
    """(token, saniye cinsinden geçerlilik süresi) döndürür."""
    settings = get_settings()
    now = datetime.now(UTC)
    expires_in = settings.jwt_expire_minutes * 60
    claims = {
        "sub": user_id,
        "iss": _JWT_ISSUER,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=_JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> str | None:
    """Token geçerliyse kullanıcı id'sini (sub), değilse None döndürür."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[_JWT_ALGORITHM],
            issuer=_JWT_ISSUER,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
