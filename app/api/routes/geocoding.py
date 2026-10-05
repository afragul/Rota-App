from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.rate_limit import limiter
from app.schemas.geocoding import GeocodeResult
from app.services.geocoding import GeocodingServiceError, geocode_address

router = APIRouter(prefix="/geocode", tags=["geocode"])


@router.get("")
@limiter.limit("20/minute")
async def get_geocode(
    request: Request,
    address: Annotated[
        str, Query(min_length=1, max_length=200, description="Şehir veya adres metni")
    ],
) -> GeocodeResult:
    """Verilen şehir/adres metnini koordinata çevirir."""
    try:
        return await geocode_address(address)
    except GeocodingServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
