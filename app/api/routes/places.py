from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import Field

from app.core.rate_limit import limiter
from app.schemas.places import Place
from app.services.places import search_nearby

router = APIRouter(
    prefix="/places",
    tags=["places"],
)


@router.get("/nearby")
@limiter.limit("20/minute")
async def get_nearby_places(
    request: Request,
    latitude: Annotated[float, Query(ge=-90, le=90, description="Enlem")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Boylam")],
    types: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=50, pattern=r"^[a-z_]+$")]],
        Query(max_length=5, description="Mekân türleri, örn: cafe, restaurant, museum"),
    ],
    radius: Annotated[float, Query(gt=0, le=50_000, description="Arama yarıçapı (metre)")] = 1500.0,
    max_results: Annotated[int, Query(ge=1, le=20, description="Maksimum sonuç sayısı")] = 10,
) -> list[Place]:
    """Verilen koordinatın çevresindeki mekânları döndürür."""
    return await search_nearby(
        latitude=latitude,
        longitude=longitude,
        included_types=types,
        radius=radius,
        max_results=max_results,
    )
