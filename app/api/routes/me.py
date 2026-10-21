from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.cookies import set_refresh_cookie
from app.api.deps import Session, UserId
from app.core.rate_limit import limiter
from app.schemas.auth import ChangePasswordRequest, UpdateProfileRequest, UserOut
from app.services import refresh_tokens
from app.services.users import (
    InvalidCredentialsError,
    UsernameTakenError,
    UserNotFoundError,
    change_password,
    get_user,
    update_username,
)

router = APIRouter(prefix="/me", tags=["me"])


def _out(user) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, username=user.username)


@router.get("", response_model=UserOut)
async def get_me(request: Request, user_id: UserId, session: Session) -> UserOut:
    """Giriş yapmış kullanıcının profili."""
    try:
        return _out(await get_user(session, user_id))
    except UserNotFoundError:
        # Token geçerli ama hesap silinmiş.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Hesap bulunamadı"
        ) from None


@router.patch("", response_model=UserOut)
@limiter.limit("20/minute")
async def update_me(
    request: Request, payload: UpdateProfileRequest, user_id: UserId, session: Session
) -> UserOut:
    """Kullanıcı adını değiştirir."""
    try:
        return _out(await update_username(session, user_id, payload.username))
    except UsernameTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu kullanıcı adı alınmış"
        ) from None
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Hesap bulunamadı"
        ) from None


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def change_my_password(
    request: Request, payload: ChangePasswordRequest, user_id: UserId, session: Session
) -> Response:
    """Mevcut şifreyi doğrulayıp yenisini belirler. Başka cihazlardaki oturumlar
    kapanır; bu cihaz için yeni bir refresh token verilir (oturumu sürer)."""
    try:
        await change_password(session, user_id, payload.current_password, payload.new_password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Mevcut şifre hatalı"
        ) from None
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Hesap bulunamadı"
        ) from None
    await refresh_tokens.revoke_all_for_user(session, user_id)
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_refresh_cookie(out, await refresh_tokens.issue_token(session, user_id))
    return out
