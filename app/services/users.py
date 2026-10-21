import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models import (
    DailyUsage,
    FavoritePlace,
    RefreshToken,
    SavedPlan,
    User,
    VisitedPlace,
)


class AuthServiceError(Exception):
    """Kimlik doğrulama/kayıt hatalarının tabanı."""


class EmailAlreadyRegisteredError(AuthServiceError):
    pass


class UsernameTakenError(AuthServiceError):
    pass


class InvalidCredentialsError(AuthServiceError):
    pass


class UserNotFoundError(AuthServiceError):
    pass


def normalize_email(email: str) -> str:
    # Büyük/küçük harf farkıyla aynı e-postayla çift hesap açılmasın.
    return email.strip().lower()


async def _username_taken(
    session: AsyncSession, username: str, except_user_id: uuid.UUID | None = None
) -> bool:
    query = select(User.id).where(func.lower(User.username) == username.lower())
    if except_user_id is not None:
        query = query.where(User.id != except_user_id)
    return await session.scalar(query) is not None


async def register_user(session: AsyncSession, email: str, username: str, password: str) -> User:
    email = normalize_email(email)
    if await session.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailAlreadyRegisteredError
    if await _username_taken(session, username):
        raise UsernameTakenError
    user = User(email=email, username=username, password_hash=await hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Kontrol ile commit arasında gelen eşzamanlı kayıt: hangisi çakıştı?
        await session.rollback()
        if await session.scalar(select(User.id).where(User.email == email)) is not None:
            raise EmailAlreadyRegisteredError from None
        raise UsernameTakenError from None
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    """E-posta/şifre doğruysa kullanıcıyı döndürür. Kullanıcı yok ya da şifre
    yanlış: aynı hata (hangisinin olduğu sızmasın)."""
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if not await verify_password(user.password_hash if user else None, password) or user is None:
        raise InvalidCredentialsError
    return user


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    return user


async def update_username(session: AsyncSession, user_id: uuid.UUID, username: str) -> User:
    user = await get_user(session, user_id)
    if await _username_taken(session, username, except_user_id=user_id):
        raise UsernameTakenError
    user.username = username
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise UsernameTakenError from None
    return user


async def change_password(
    session: AsyncSession, user_id: uuid.UUID, current_password: str, new_password: str
) -> None:
    user = await get_user(session, user_id)
    if not await verify_password(user.password_hash, current_password):
        raise InvalidCredentialsError
    user.password_hash = await hash_password(new_password)
    await session.commit()


async def delete_account(session: AsyncSession, user_id: uuid.UUID, password: str) -> None:
    """Hesabı ve ona bağlı TÜM veriyi kalıcı siler (KVKK: silme hakkı). Şifre doğrulanır:
    çalınmış bir erişim token'ı tek başına hesabı yok edemesin.

    Bağlı tablolar veritabanında da `ON DELETE CASCADE` ile korunuyor, ama burada
    açıkça silinir: davranış veritabanı ayarına bağlı kalmasın ve tek işlemde
    (hepsi ya da hiçbiri) olsun. Soft delete yok; e-posta/kullanıcı adı da tutulmaz."""
    user = await get_user(session, user_id)
    if not await verify_password(user.password_hash, password):
        raise InvalidCredentialsError
    for table in (RefreshToken, SavedPlan, FavoritePlace, VisitedPlace, DailyUsage):
        await session.execute(
            delete(table)
            .where(table.user_id == user_id)
            .execution_options(synchronize_session=False)
        )
    await session.execute(
        delete(User).where(User.id == user_id).execution_options(synchronize_session=False)
    )
    await session.commit()
