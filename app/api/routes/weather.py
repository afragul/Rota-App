import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.weather import CurrentWeather
from app.services.weather import WeatherServiceError, get_current_weather

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("")
async def get_weather(
    latitude: Annotated[float, Query(ge=-90, le=90)],  # enlem sinirlari
    longitude: Annotated[float, Query(ge=-180, le=180)],  # boylam sinirlari
) -> CurrentWeather:
    try:
        return await get_current_weather(latitude=latitude, longitude=longitude)
    except WeatherServiceError as exc:
        logger.exception("Hava durumu alinamadi (lat=%s, lon=%s)", latitude, longitude)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
