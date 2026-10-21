from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.users import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    UsernameTakenError,
    authenticate_user,
    register_user,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


def _token_response(user: User) -> TokenResponse:
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
    request: Request,
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
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
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    """E-posta ve şifreyle giriş yapar."""
    try:
        user = await authenticate_user(session, payload.email, payload.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya şifre hatalı"
        ) from None
    return _token_response(user)
