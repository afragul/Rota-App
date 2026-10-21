import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_user_id
from app.db.models import User
from app.db.session import get_session

Session = Annotated[AsyncSession, Depends(get_session)]


async def _existing_user_id(
    user_id: Annotated[uuid.UUID, Depends(require_user_id)], session: Session
) -> uuid.UUID:
    """Token geçerli olsa bile hesap silinmişse 401: erişim token'ı hesap silindikten
    sonra süresi dolana kadar (dakikalarca) geçerli kalırdı; bu kontrol silinen hesabın
    erişimini anında keser ve yabancı anahtar hatasıyla 500 dönmesini de önler."""
    if await session.scalar(select(User.id).where(User.id == user_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hesap bulunamadı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


# Giriş zorunlu route'larda: geçerli token'dan kullanıcı id'si (hesap hâlâ var), DB oturumu.
UserId = Annotated[uuid.UUID, Depends(_existing_user_id)]
