from fastapi import APIRouter, Depends, Request

from app.api.deps import Session
from app.core.auth import get_optional_user_id
from app.core.guest_limit import enforce_guest_legs_limit
from app.core.rate_limit import limiter
from app.core.user_limit import enforce_user_legs_limit
from app.schemas.plan import ApproachRequest, ApproachRoute, LegsRequest, LegsResponse, PlanStop
from app.services.routes import get_approach_route, get_route_legs

router = APIRouter(
    prefix="/route",
    tags=["route"],
)


@router.post("/approach", response_model=ApproachRoute)
@limiter.limit("20/minute")
async def approach(request: Request, payload: ApproachRequest) -> ApproachRoute:
    """Kullanıcının konumundan verilen noktaya (ilk durak) rota döndürür."""
    return await get_approach_route(
        origin=(payload.origin_latitude, payload.origin_longitude),
        destination=(payload.destination_latitude, payload.destination_longitude),
        mode=payload.travel_mode,
    )


@router.post("/legs", response_model=LegsResponse)
@limiter.limit("30/minute")
async def recompute_legs(
    request: Request,
    payload: LegsRequest,
    session: Session,
    user_id: str | None = Depends(get_optional_user_id),
) -> LegsResponse:
    """Durak silindiğinde/sırası değiştiğinde ayakları (mesafe/süre/çizgi) yeniden hesaplar."""
    enforce_guest_legs_limit(request, user_id)
    await enforce_user_legs_limit(session, user_id)
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
    legs = await get_route_legs(stops, payload.travel_mode)
    return LegsResponse(legs=legs)
