from fastapi import APIRouter, Depends, Request

from app.api.deps import Session
from app.core.auth import get_optional_user_id
from app.core.guest_limit import enforce_guest_plan_limit
from app.core.rate_limit import limiter
from app.core.user_limit import enforce_user_plan_limit
from app.schemas.plan import ClarificationNeeded, DayPlan, PlanRequest
from app.services.orchestrator import build_day_plan

router = APIRouter(
    prefix="/plan",
    tags=["plan"],
)


@router.post("", response_model=DayPlan | ClarificationNeeded)
@limiter.limit("10/minute")
async def create_day_plan(
    request: Request,
    payload: PlanRequest,
    session: Session,
    user_id: str | None = Depends(get_optional_user_id),
) -> DayPlan | ClarificationNeeded:
    """Kullanıcı girdilerinden günlük alternatif planlar üretir."""
    enforce_guest_plan_limit(request, user_id)
    await enforce_user_plan_limit(session, user_id)
    # Misafirler (giriş yapmamış) istek başına tek alternatif alır.
    # Servis hataları app/api/errors.py'deki merkezi işleyicide 502'ye çevrilir.
    return await build_day_plan(payload, max_alternatives=1 if user_id is None else None)
