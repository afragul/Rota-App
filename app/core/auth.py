from fastapi import Header

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
