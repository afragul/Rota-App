import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import Session, UserId
from app.core.auth import get_optional_user_id
from app.core.rate_limit import limiter
from app.schemas.saved_plan import (
    SavedPlanCreated,
    SavedPlanSummary,
    SavePlanRequest,
    SharedPlan,
)
from app.services import saved_plans as service

# Giriş gerektiren, kullanıcıya ait plan işlemleri.
router = APIRouter(prefix="/plans", tags=["plans"])

# Girişsiz, link ile açılan paylaşım (id tahmin edilemez bir UUID; toplu listeleme yok).
shared_router = APIRouter(prefix="/shared", tags=["plans"])


@router.post("", response_model=SavedPlanCreated, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_saved_plan(
    request: Request, payload: SavePlanRequest, user_id: UserId, session: Session
) -> SavedPlanCreated:
    """Planı kullanıcının hesabına kaydeder."""
    try:
        plan = await service.save_plan(session, user_id, payload)
    except service.SavedPlanLimitError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıtlı plan sınırına ulaştınız; yenisini eklemek için birini silin",
        ) from None
    return SavedPlanCreated(id=plan.id)


@router.get("", response_model=list[SavedPlanSummary])
async def list_saved_plans(
    request: Request, user_id: UserId, session: Session
) -> list[SavedPlanSummary]:
    """Kullanıcının kayıtlı planları (en yeni önce)."""
    plans = await service.list_plans(session, user_id)
    return [SavedPlanSummary.model_validate(p, from_attributes=True) for p in plans]


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_saved_plan(
    request: Request, plan_id: uuid.UUID, user_id: UserId, session: Session
) -> Response:
    """Planı siler. Başkasının planı ile olmayan plan aynı 404'ü verir."""
    if not await service.delete_plan(session, user_id, plan_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan bulunamadı")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@shared_router.get("/{plan_id}", response_model=SharedPlan)
@limiter.limit("30/minute")
async def get_shared_plan(
    request: Request,
    plan_id: uuid.UUID,
    session: Session,
    viewer_id: str | None = Depends(get_optional_user_id),
) -> SharedPlan:
    """Paylaşım linkiyle planı açar (giriş gerekmez). Geçerli token varsa ve plan
    o kullanıcınınsa `is_owner` true döner (UI'ın "kaydedilenlerden çıkar" düğmesi için)."""
    plan = await service.get_shared_plan(session, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan bulunamadı")
    shared = SharedPlan.model_validate(plan, from_attributes=True)
    shared.is_owner = viewer_id is not None and viewer_id == str(plan.user_id)
    return shared
