from fastapi import Response

from app.core.config import get_settings

REFRESH_COOKIE = "bugunluk_refresh"


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Refresh token'ı httpOnly cookie olarak yazar: JavaScript okuyamaz (XSS çalamaz),
    SameSite=Strict ile başka sitelerden tetiklenen isteklerle gönderilmez (CSRF)."""
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=settings.refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=settings.refresh_cookie_path,
    )
