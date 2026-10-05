from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

# Tanımlı bir limiti olmayan route için güvenlik ağı; korunan endpoint'ler
# kendi (daha sıkı) limitlerini route dekoratöründe belirtir.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    enabled=get_settings().rate_limit_enabled,
)
