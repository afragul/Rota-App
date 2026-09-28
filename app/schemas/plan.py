
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class BudgetLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GroupType(StrEnum):
    SOLO = "solo"
    COUPLE = "couple"
    FRIENDS = "friends"
    FAMILY = "family"


class PlanRequest(BaseModel):
    """Kullanıcıdan gelen istek."""

    # Konum: latitude+longitude İKİLİSİ VEYA city verilmeli
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = Field(
        default=None,
        description="latitude/longitude verilmezse şehir/adres metninden koordinat çözümlenir",
    )

    duration_hours: int = 4
    budget: BudgetLevel = BudgetLevel.MEDIUM
    group_type: GroupType = GroupType.FRIENDS

    # Kategori seçimi VEYA serbest metin
    categories: list[str] | None = None
    free_text: str | None = None

    @model_validator(mode="after")
    def _konum_verildi_mi(self) -> "PlanRequest":
        has_coords = self.latitude is not None and self.longitude is not None
        if not has_coords and not self.city:
            raise ValueError("latitude/longitude ikilisi veya city alanlarından biri verilmeli")
        return self


class PlanStop(BaseModel):
    """Plandaki tek bir durak."""

    place_id: str = Field(description="Verilen mekan listesinden seçilen id")
    order: int = Field(description="Kaçıncı durak, 1'den başlar")
    arrival_time: str = Field(description="Varış saati, ÖRN: 14:30")
    duration_minutes: int = Field(description="Burada geçirilecek süre")
    activity: str = Field(description="Burada ne yapılır, tek cümle")
    recommendation: str = Field(description="Somut öneri: ne yenir, ne görülür")
    estimated_cost: int = Field(description="Kişi başı tahmini harcama, TL")

    # LLM bu alanları üretmez, null bırakır; mekan havuzundan sistem doldurur
    # (bkz. app/services/planner.py::_validate_and_enrich_stops). Haritada pin
    # basmak için gerekli.
    name: str | None = Field(default=None, description="Mekanın adı (sistem doldurur)")
    latitude: float | None = Field(default=None, description="Mekanın enlemi (sistem doldurur)")
    longitude: float | None = Field(default=None, description="Mekanın boylamı (sistem doldurur)")


class PlanAlternative(BaseModel):
    """Tek bir temalı gün planı."""

    theme: str = Field(description="Tema adı, örn: Tarihi Bursa")
    title: str = Field(description="Çekici bir başlık")
    summary: str = Field(description="Günün özeti, 1-2 cümle")
    stops: list[PlanStop]


class DayPlan(BaseModel):
    """LLM'in döndüreceği nihai yapı."""
    weather_available: bool = Field(
        default=True,
        description=(
            "Hava durumu bilgisi alınabildi mi. "
            "False ise plan, hava açık varsayılarak üretilmiştir."
        ),
    )

    alternatives: list[PlanAlternative] = Field(
        description="Birbirinden farklı 2-3 alternatif plan"
    )
