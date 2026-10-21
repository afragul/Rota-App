from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models import User


class AuthServiceError(Exception):
    """Kimlik doğrulama/kayıt hatalarının tabanı."""


class EmailAlreadyRegisteredError(AuthServiceError):
    pass


class InvalidCredentialsError(AuthServiceError):
    pass


def normalize_email(email: str) -> str:
    # Büyük/küçük harf farkıyla aynı e-postayla çift hesap açılmasın.
    return email.strip().lower()


async def register_user(session: AsyncSession, email: str, username: str, password: str) -> User:
    email = normalize_email(email)
    exists = await session.scalar(select(User.id).where(User.email == email))
    if exists is not None:
        raise EmailAlreadyRegisteredError
    user = User(email=email, username=username, password_hash=await hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Yukarıdaki kontrol ile commit arasında aynı e-postayla gelen eşzamanlı kayıt.
        await session.rollback()
        raise EmailAlreadyRegisteredError from None
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    """E-posta/şifre doğruysa kullanıcıyı döndürür. Kullanıcı yok ya da şifre
    yanlış: aynı hata (hangisinin olduğu sızmasın)."""
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if not await verify_password(user.password_hash if user else None, password) or user is None:
        raise InvalidCredentialsError
    return user
