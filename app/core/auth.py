import jwt
from fastapi import Header

from app.core.config import get_settings


async def get_optional_user_id(authorization: str | None = Header(default=None)) -> str | None:
    """Supabase JWT'si geçerliyse kullanıcı id'sini (sub) döndürür; yoksa/
    geçersizse None (misafir sayılır).

    Backend için kimlik doğrulama hiçbir endpoint'te zorunlu değil — bu
    sadece misafir plan kotasını (bkz. guest_limit.py) atlamak için "giriş
    yapmış mı" sorusuna cevap verir.
    """
    settings = get_settings()
    secret = settings.supabase_jwt_secret
    if not secret or not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token, secret.get_secret_value(), algorithms=["HS256"], audience="authenticated"
        )
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
