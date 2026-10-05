from fastapi import APIRouter, HTTPException, Request, status

from app.core.rate_limit import limiter
from app.schemas.plan import ApproachRequest, ApproachRoute, LegsRequest, LegsResponse, PlanStop
from app.services.routes import RoutesServiceError, get_approach_route, get_route_legs

router = APIRouter(
    prefix="/route",
    tags=["route"],
)


@router.post("/approach", response_model=ApproachRoute)
@limiter.limit("20/minute")
async def approach(request: Request, payload: ApproachRequest) -> ApproachRoute:
    """Kullanıcının konumundan verilen noktaya (ilk durak) rota döndürür."""
    try:
        return await get_approach_route(
            origin=(payload.origin_latitude, payload.origin_longitude),
            destination=(payload.destination_latitude, payload.destination_longitude),
            mode=payload.travel_mode,
        )
    except RoutesServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/legs", response_model=LegsResponse)
@limiter.limit("30/minute")
async def recompute_legs(request: Request, payload: LegsRequest) -> LegsResponse:
    """Durak silindiğinde/sırası değiştiğinde ayakları (mesafe/süre/çizgi) yeniden hesaplar."""
    ordered = sorted(payload.stops, key=lambda s: s.order)
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
        legs = await get_route_legs(stops, payload.travel_mode)
    except RoutesServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return LegsResponse(legs=legs)
