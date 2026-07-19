from fastapi import APIRouter, HTTPException, status

from app.schemas.plan import DayPlan, PlanRequest
from app.services.orchestrator import build_day_plan
from app.services.places import PlacesServiceError
from app.services.planner import PlannerServiceError

router = APIRouter(
    prefix="/plan",
    tags=["plan"],
)


@router.post("", response_model=DayPlan)
async def create_day_plan(request: PlanRequest) -> DayPlan:
    """Kullanıcı girdilerinden günlük alternatif planlar üretir."""
    try:
        return await build_day_plan(request)
    except PlacesServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except PlannerServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
