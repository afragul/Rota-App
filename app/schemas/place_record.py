from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field


class PlaceIn(BaseModel):
    """Favoriye eklenen / ziyaret kaydedilen mekan (frontend'deki Place ile aynı alanlar,
    enlem/boylam hariç — bkz. app/db/models.py::_PlaceMixin)."""

    place_id: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    rating: float | None = Field(default=None, ge=0, le=5)
    user_rating_count: int | None = Field(default=None, ge=0)
    types: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(
        default_factory=list, max_length=10
    )


class FavoritePlaceOut(PlaceIn):
    id: UUID


class VisitedPlaceOut(PlaceIn):
    visit_count: int
    last_visited_at: datetime
