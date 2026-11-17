import logging

from fastapi import Request
from slowapi.util import get_remote_address

from app.core.logging import clean_log

# Güvenlik olayları ayrı bir logger'da: canlıda süzülüp uyarıya bağlanabilir.
logger = logging.getLogger("audit")


def audit(request: Request, event: str) -> None:
    """Güvenlik olayını IP + yol ile kaydeder. Token, şifre ya da kullanıcı kimliği YAZILMAZ
    (kimlikle loglama KVKK değerlendirmesine bağlı, bkz. ROADMAP)."""
    ip = clean_log(get_remote_address(request))
    logger.warning("%s | ip=%s yol=%s", event, ip, clean_log(request.url.path))
