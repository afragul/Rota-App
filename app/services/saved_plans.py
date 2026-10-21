import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import SavedPlan
from app.schemas.saved_plan import SavePlanRequest


class SavedPlanLimitError(Exception):
    """Kullanıcı kaydedebileceği plan sayısı sınırına ulaştı."""


async def save_plan(
    session: AsyncSession, user_id: uuid.UUID, payload: SavePlanRequest
) -> SavedPlan:
    count = await session.scalar(
        select(func.count()).select_from(SavedPlan).where(SavedPlan.user_id == user_id)
    )
    if (count or 0) >= get_settings().max_saved_plans_per_user:
        raise SavedPlanLimitError
    plan = SavedPlan(
        user_id=user_id,
        theme=payload.theme,
        title=payload.title,
        summary=payload.summary,
        # JSONB'ye düz Python yapıları gider (enum/Pydantic nesneleri değil).
        stops=[s.model_dump(mode="json") for s in payload.stops],
        legs=[leg.model_dump(mode="json") for leg in payload.legs],
        routes_available=payload.routes_available,
    )
    session.add(plan)
    await session.commit()
    return plan


async def list_plans(session: AsyncSession, user_id: uuid.UUID) -> list[SavedPlan]:
    result = await session.scalars(
        select(SavedPlan).where(SavedPlan.user_id == user_id).order_by(SavedPlan.created_at.desc())
    )
    return list(result)


async def delete_plan(session: AsyncSession, user_id: uuid.UUID, plan_id: uuid.UUID) -> bool:
    """Plan kullanıcıya aitse siler. Yoksa ya da başkasınınsa False (ikisi ayırt edilmez)."""
    result = await session.execute(
        delete(SavedPlan).where(SavedPlan.id == plan_id, SavedPlan.user_id == user_id)
    )
    await session.commit()
    return result.rowcount > 0


async def get_shared_plan(session: AsyncSession, plan_id: uuid.UUID) -> SavedPlan | None:
    """Paylaşım linki: yalnızca tek bir id ile okunur, toplu listeleme yok."""
    return await session.get(SavedPlan, plan_id)
