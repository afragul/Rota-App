from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import Session, UserId
from app.core.rate_limit import limiter
from app.schemas.place_record import FavoritePlaceOut, PlaceIn
from app.services import favorites as service

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoritePlaceOut])
async def list_favorites(
    request: Request, user_id: UserId, session: Session
) -> list[FavoritePlaceOut]:
    """Kullanıcının favori mekanları (en yeni önce)."""
    favorites = await service.list_favorites(session, user_id)
    return [FavoritePlaceOut.model_validate(f, from_attributes=True) for f in favorites]


@router.post("", response_model=FavoritePlaceOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def add_favorite(
    request: Request, response: Response, payload: PlaceIn, user_id: UserId, session: Session
) -> FavoritePlaceOut:
    """Mekanı favoriye ekler. Zaten favoriyse hata vermez, mevcut kaydı 200 ile döndürür."""
    try:
        favorite, created = await service.add_favorite(session, user_id, payload)
    except service.FavoriteLimitError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Favori sınırına ulaştınız; yenisini eklemek için birini kaldırın",
        ) from None
    if not created:
        response.status_code = status.HTTP_200_OK
    return FavoritePlaceOut.model_validate(favorite, from_attributes=True)


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def remove_favorite(
    request: Request, place_id: str, user_id: UserId, session: Session
) -> Response:
    """Mekanı favorilerden çıkarır."""
    if not await service.remove_favorite(session, user_id, place_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favori bulunamadı")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
