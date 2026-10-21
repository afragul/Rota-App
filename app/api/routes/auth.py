from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import REFRESH_COOKIE, clear_refresh_cookie, set_refresh_cookie
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import refresh_tokens
from app.services.users import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    UsernameTakenError,
    UserNotFoundError,
    authenticate_user,
    get_user,
    register_user,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

Session = Annotated[AsyncSession, Depends(get_session)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


async def _start_session(response: Response, session: AsyncSession, user: User) -> TokenResponse:
    """Kısa ömürlü erişim token'ı döndürür, uzun ömürlü refresh token'ı cookie'ye yazar."""
    set_refresh_cookie(response, await refresh_tokens.issue_token(session, user.id))
    token, expires_in = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut(id=str(user.id), email=user.email, username=user.username),
    )


# Kaba kuvvet ve toplu hesap açma denemelerine karşı sıkı dakikalık limitler.
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request, response: Response, payload: RegisterRequest, session: Session
) -> TokenResponse:
    """Yeni hesap açar ve doğrudan oturum (token) döndürür."""
    try:
        user = await register_user(session, payload.email, payload.username, payload.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta ile zaten bir hesap var"
        ) from None
    except UsernameTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu kullanıcı adı alınmış"
        ) from None
    return await _start_session(response, session, user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request, response: Response, payload: LoginRequest, session: Session
) -> TokenResponse:
    """E-posta ve şifreyle giriş yapar."""
    try:
        user = await authenticate_user(session, payload.email, payload.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya şifre hatalı"
        ) from None
    return await _start_session(response, session, user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request, response: Response, session: Session, refresh_token: RefreshCookie = None
) -> TokenResponse | JSONResponse:
    """Cookie'deki refresh token'la yeni erişim token'ı alır; refresh token da yenilenir."""
    try:
        if refresh_token is None:
            raise refresh_tokens.InvalidRefreshTokenError
        user_id, new_raw = await refresh_tokens.rotate_token(session, refresh_token)
        user = await get_user(session, user_id)
    except (refresh_tokens.InvalidRefreshTokenError, UserNotFoundError):
        # HTTPException fırlatılsa response üzerindeki cookie silme başlığı kaybolurdu.
        failure = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Oturum süresi doldu"}
        )
        clear_refresh_cookie(failure)
        return failure
    set_refresh_cookie(response, new_raw)
    token, expires_in = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut(id=str(user.id), email=user.email, username=user.username),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def logout(
    request: Request, response: Response, session: Session, refresh_token: RefreshCookie = None
) -> Response:
    """Oturumu kapatır: refresh token ailesi iptal edilir, cookie silinir."""
    if refresh_token is not None:
        await refresh_tokens.revoke_token(session, refresh_token)
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(out)
    return out
