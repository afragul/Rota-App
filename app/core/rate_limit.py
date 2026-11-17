from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.audit import audit
from app.core.config import get_settings

# Tanımlı bir limiti olmayan route için güvenlik ağı; korunan endpoint'ler
# kendi (daha sıkı) limitlerini route dekoratöründe belirtir.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    enabled=get_settings().rate_limit_enabled,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """slowapi'nin 429 yanıtı aynen döner; ek olarak olay audit log'a yazılır."""
    audit(request, "hız sınırı aşıldı")
    return _rate_limit_exceeded_handler(request, exc)
