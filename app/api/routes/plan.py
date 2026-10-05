from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.auth import get_optional_user_id
from app.core.guest_limit import enforce_guest_plan_limit
from app.core.rate_limit import limiter
from app.schemas.plan import ClarificationNeeded, DayPlan, PlanRequest
from app.services.geocoding import GeocodingServiceError
from app.services.orchestrator import build_day_plan
from app.services.places import PlacesServiceError
from app.services.planner import PlannerServiceError

router = APIRouter(
    prefix="/plan",
    tags=["plan"],
)


@router.post("", response_model=DayPlan | ClarificationNeeded)
@limiter.limit("10/minute")
async def create_day_plan(
    request: Request,
    payload: PlanRequest,
    user_id: str | None = Depends(get_optional_user_id),
) -> DayPlan | ClarificationNeeded:
    """Kullanıcı girdilerinden günlük alternatif planlar üretir."""
    enforce_guest_plan_limit(request, user_id)
    try:
        return await build_day_plan(payload)
    except GeocodingServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except PlacesServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except PlannerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
