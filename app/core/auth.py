import jwt
from fastapi import Header

from app.core.config import get_settings


async def get_optional_user_id(authorization: str | None = Header(default=None)) -> str | None:
    """Supabase JWT'si geçerliyse kullanıcı id'sini (sub) döndürür; yoksa/
    geçersizse None (misafir sayılır).

    Backend için kimlik doğrulama hiçbir endpoint'te zorunlu değil — bu
    sadece misafir plan kotasını (bkz. guest_limit.py) atlamak için "giriş
    yapmış mı" sorusuna cevap verir.

    SUPABASE_JWT_SECRET iki farklı şey olabilir (Supabase projesi hangisini
    kullanıyorsa): eski/legacy simetrik "JWT Secret" (düz metin, HS256) ya
    da yeni asimetrik "Signing Keys" özelliğinin PEM formatlı genel anahtarı
    ("-----BEGIN PUBLIC KEY-----" ile başlar, ES256/RS256). Hangisi olduğu
    bu önekten otomatik anlaşılır; kullanıcı ikisinden hangisini kopyaladığını
    bilmek zorunda kalmaz.
    """
    settings = get_settings()
    secret = settings.supabase_jwt_secret
    if not secret or not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    key = secret.get_secret_value()
    algorithms = ["ES256", "RS256"] if key.strip().startswith("-----BEGIN") else ["HS256"]
    try:
        payload = jwt.decode(token, key, algorithms=algorithms, audience="authenticated")
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
