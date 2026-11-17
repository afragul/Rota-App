import logging
import uuid

from fastapi import Depends, Header, HTTPException, Request, status
from slowapi.util import get_remote_address

from app.core.logging import clean_log
from app.core.security import decode_access_token

logger = logging.getLogger("audit")


async def get_optional_user_id(
    authorization: str | None = Header(default=None),
    request: Request = None,  # type: ignore[assignment]  # doğrudan çağrılarda (testler) verilmeyebilir
) -> str | None:
    """Geçerli bir erişim token'ı (JWT) varsa kullanıcı id'sini (sub) döndürür;
    yoksa/geçersizse/süresi dolmuşsa None (misafir sayılır).

    Backend için kimlik doğrulama hiçbir endpoint'te zorunlu değil — bu
    sadece misafir kotalarını (bkz. guest_limit.py) atlamak için "giriş
    yapmış mı" sorusuna cevap verir. Asla hata fırlatmaz.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    user_id = decode_access_token(authorization.removeprefix("Bearer "))
    if user_id is None and request is not None:
        # INFO: süresi dolan 15 dk'lık token'lar normal akışta sık görülür (arkasından sessiz
        # yenileme gelir); WARNING olsaydı gerçek saldırı izi gürültüde kaybolurdu.
        # Token'ın kendisi ASLA yazılmaz.
        logger.info(
            "geçersiz ya da süresi dolmuş erişim token'ı | ip=%s yol=%s",
            clean_log(get_remote_address(request)),
            clean_log(request.url.path),
        )
    return user_id


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
