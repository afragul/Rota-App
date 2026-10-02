from fastapi import APIRouter, HTTPException, status

from app.schemas.plan import ApproachRequest, ApproachRoute, LegsRequest, LegsResponse, PlanStop
from app.services.routes import RoutesServiceError, get_approach_route, get_route_legs

router = APIRouter(
    prefix="/route",
    tags=["route"],
)


@router.post("/approach", response_model=ApproachRoute)
async def approach(request: ApproachRequest) -> ApproachRoute:
    """Kullanıcının konumundan verilen noktaya (ilk durak) rota döndürür."""
    try:
        return await get_approach_route(
            origin=(request.origin_latitude, request.origin_longitude),
            destination=(request.destination_latitude, request.destination_longitude),
            mode=request.travel_mode,
        )
    except RoutesServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/legs", response_model=LegsResponse)
async def recompute_legs(request: LegsRequest) -> LegsResponse:
    """Durak silindiğinde/sırası değiştiğinde ayakları (mesafe/süre/çizgi) yeniden hesaplar."""
    ordered = sorted(request.stops, key=lambda s: s.order)
    stops = [
        PlanStop(
            place_id="",
            order=s.order,
            arrival_time="",
            duration_minutes=0,
            activity="",
            recommendation="",
            estimated_cost=0,
            latitude=s.latitude,
            longitude=s.longitude,
        )
        for s in ordered
    ]
    try:
        legs = await get_route_legs(stops, request.travel_mode)
    except RoutesServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return LegsResponse(legs=legs)
