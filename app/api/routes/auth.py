from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import REFRESH_COOKIE, clear_refresh_cookie, set_refresh_cookie
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import (
    AuthCapabilities,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.services import email as email_service
from app.services import password_reset, refresh_tokens
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


@router.get("/capabilities", response_model=AuthCapabilities)
async def capabilities() -> AuthCapabilities:
    """Sunucuda hangi hesap özellikleri açık (SMTP yoksa şifre sıfırlama kapalı)."""
    return AuthCapabilities(password_reset=email_service.is_configured())


@router.post("/forgot", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    background: BackgroundTasks,
    session: Session,
) -> dict[str, str]:
    """Şifre sıfırlama bağlantısı gönderir. Hesap var olsun olmasın AYNI cevabı döner
    (hesap var mı bilgisi sızmasın); e-posta arka planda gönderilir, böylece gönderme
    süresi de yanıt süresinden anlaşılamaz."""
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Şifre sıfırlama bu sunucuda henüz yapılandırılmamış",
        )
    created = await password_reset.create_token(session, payload.email)
    if created is not None:
        address, raw_token = created
        subject, body = password_reset.build_email(raw_token)
        background.add_task(email_service.send_email_quietly, address, subject, body)
    return {"detail": "Bu e-posta kayıtlıysa şifre sıfırlama bağlantısı gönderildi"}


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def reset_password(
    request: Request, payload: ResetPasswordRequest, session: Session
) -> Response:
    """E-postadaki bağlantıdaki token'la yeni şifre belirler; tüm oturumlar kapanır."""
    try:
        await password_reset.reset_password(session, payload.token, payload.new_password)
    except password_reset.InvalidResetTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bağlantı geçersiz ya da süresi dolmuş. Yeni bir bağlantı iste.",
        ) from None
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(out)
    return out
