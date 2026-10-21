from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.plan import PlanStop, RouteLeg

# Saklanan JSON şişmesin: bir planda makul bir üst sınır.
MAX_SAVED_STOPS = 25


class SavePlanRequest(BaseModel):
    """Kullanıcının kaydettiği tek bir alternatif plan (PlanAlternative'in sınırlı hali)."""

    theme: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(max_length=1000)
    stops: list[PlanStop] = Field(min_length=1, max_length=MAX_SAVED_STOPS)
    legs: list[RouteLeg] = Field(default_factory=list, max_length=MAX_SAVED_STOPS)
    routes_available: bool = True


class SavedPlanCreated(BaseModel):
    id: UUID


class SavedPlanSummary(BaseModel):
    """Hesap ekranındaki liste satırı (stops/legs olmadan)."""

    id: UUID
    theme: str
    title: str
    summary: str
    created_at: datetime


class SharedPlan(BaseModel):
    """Paylaşım linkiyle açılan tam plan. Sahibin kimliği (user_id) bilerek yok;
    yerine isteği yapanın sahibi olup olmadığını söyleyen `is_owner` var."""

    id: UUID
    theme: str
    title: str
    summary: str
    stops: list[PlanStop]
    legs: list[RouteLeg]
    routes_available: bool
    created_at: datetime
    is_owner: bool = False
