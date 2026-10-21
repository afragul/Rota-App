import uuid

from fastapi import Depends, Header, HTTPException, status

from app.core.security import decode_access_token


async def get_optional_user_id(authorization: str | None = Header(default=None)) -> str | None:
    """Geçerli bir erişim token'ı (JWT) varsa kullanıcı id'sini (sub) döndürür;
    yoksa/geçersizse/süresi dolmuşsa None (misafir sayılır).

    Backend için kimlik doğrulama hiçbir endpoint'te zorunlu değil — bu
    sadece misafir kotalarını (bkz. guest_limit.py) atlamak için "giriş
    yapmış mı" sorusuna cevap verir. Asla hata fırlatmaz.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return decode_access_token(authorization.removeprefix("Bearer "))


async def require_user_id(user_id: str | None = Depends(get_optional_user_id)) -> uuid.UUID:
    """Giriş zorunlu endpoint'ler için: geçerli token yoksa 401."""
    if user_id is not None:
        try:
            return uuid.UUID(user_id)
        except ValueError:
            pass
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bu işlem için giriş yapmalısınız",
        headers={"WWW-Authenticate": "Bearer"},
    )
