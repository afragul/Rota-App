from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.api.deps import Session, UserId
from app.core.rate_limit import limiter
from app.schemas.place_record import PlaceIn, VisitedPlaceOut
from app.services import visits as service

router = APIRouter(prefix="/visits", tags=["visits"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def record_visit(
    request: Request, payload: PlaceIn, user_id: UserId, session: Session
) -> Response:
    """Bir durak "Ulaşıldı" işaretlenince çağrılır: ziyaret sayacını artırır."""
    try:
        await service.record_visit(session, user_id, payload)
    except service.VisitedLimitError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ziyaret geçmişi sınırına ulaşıldı"
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=list[VisitedPlaceOut])
async def list_frequent_places(
    request: Request,
    user_id: UserId,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> list[VisitedPlaceOut]:
    """"Sık gidilen yerler": en çok ziyaret edilenler önce."""
    places = await service.list_frequent(session, user_id, limit)
    return [VisitedPlaceOut.model_validate(p, from_attributes=True) for p in places]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def clear_visits(request: Request, user_id: UserId, session: Session) -> Response:
    """Tüm ziyaret geçmişini siler."""
    await service.clear_visits(session, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def remove_visit(
    request: Request, place_id: str, user_id: UserId, session: Session
) -> Response:
    """Tek bir mekanı ziyaret geçmişinden siler."""
    if not await service.remove_visit(session, user_id, place_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kayıt bulunamadı")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
