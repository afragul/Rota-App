import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_user_id
from app.db.session import get_session

# Giriş zorunlu route'larda: geçerli token'dan kullanıcı id'si, istek başına DB oturumu.
UserId = Annotated[uuid.UUID, Depends(require_user_id)]
Session = Annotated[AsyncSession, Depends(get_session)]
