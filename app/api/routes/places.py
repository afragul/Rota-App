from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from app.api.deps import Session
from app.core.auth import get_optional_user_id
from app.core.guest_limit import enforce_guest_search_limit
from app.core.rate_limit import limiter
from app.core.user_limit import enforce_user_search_limit
from app.schemas.places import Place
from app.services.places import search_nearby, search_text

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


@router.get("/search", response_model=list[Place])
@limiter.limit("20/minute")
async def search_places(
    request: Request,
    session: Session,
    q: Annotated[
        str, Query(min_length=2, max_length=100, description="Aranacak mekân adı ya da tarifi")
    ],
    latitude: Annotated[float, Query(ge=-90, le=90, description="Önceliklendirilecek enlem")],
    longitude: Annotated[float, Query(ge=-180, le=180, description="Önceliklendirilecek boylam")],
    user_id: str | None = Depends(get_optional_user_id),
) -> list[Place]:
    """Serbest metinle mekân arar; verilen koordinata yakın sonuçlar öne çıkar. Her çağrı
    ücretli bir Google Text Search olduğundan misafir ve hesap başına günlük kotası vardır."""
    enforce_guest_search_limit(request, user_id)
    await enforce_user_search_limit(session, user_id)
    return await search_text(q.strip(), latitude, longitude)
