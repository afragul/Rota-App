import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

import certifi

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = 15


def _ssl_context() -> ssl.SSLContext:
    """TLS bağlamı: kök sertifikalar certifi paketinden (httpx'in de kullandığı yer).
    ssl.create_default_context()'in varsayılanı sisteme bağlı: python.org'dan kurulmuş
    macOS Python'larında kök sertifika deposu YOKTUR (`Install Certificates.command`
    çalıştırılmadıkça) ve her SMTP bağlantısı "unable to get local issuer certificate"
    ile düşerdi, oysa aynı makinedeki httpx çağrıları sorunsuz çalışıyordu."""
    return ssl.create_default_context(cafile=certifi.where())


class EmailNotConfiguredError(Exception):
    """SMTP ayarları (smtp_host, smtp_from) yok."""


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def _send_sync(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    context = _ssl_context()
    if settings.smtp_security == "ssl":
        server: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=_TIMEOUT, context=context
        )
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=_TIMEOUT)
    with server:
        if settings.smtp_security == "starttls":
            server.starttls(context=context)
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        server.send_message(message)


async def send_email(to: str, subject: str, body: str) -> None:
    """E-posta gönderir (smtplib bloklayıcı: thread'de). Başarısızlıkta fırlatır."""
    if not is_configured():
        raise EmailNotConfiguredError
    await asyncio.to_thread(_send_sync, to, subject, body)


async def send_email_quietly(to: str, subject: str, body: str) -> None:
    """Arka plan görevi için: hata yutulur ve YALNIZCA türü loglanır. Adres ve ileti
    loglanmaz (kişisel veri; ileti içinde sıfırlama bağlantısı da var), ve hatanın
    kullanıcıya yansıması "bu e-posta kayıtlı mı" bilgisini sızdırırdı."""
    try:
        await send_email(to, subject, body)
    except Exception as exc:
        logger.warning("E-posta gönderilemedi: %s", type(exc).__name__)
