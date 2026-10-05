from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.geocoding import GeocodeResult
from app.services.geocoding import GeocodingServiceError, geocode_address

router = APIRouter(prefix="/geocode", tags=["geocode"])


@router.get("")
async def get_geocode(
    address: Annotated[
        str, Query(min_length=1, max_length=200, description="Şehir veya adres metni")
    ],
) -> GeocodeResult:
    """Verilen şehir/adres metnini koordinata çevirir."""
    try:
        return await geocode_address(address)
    except GeocodingServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
