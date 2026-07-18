from fastapi import APIRouter, Query
from typing import Annotated
from app.services.weather import get_current_weather
from app.schemas.weather import CurrentWeather

router = APIRouter(
    prefix="/weather",
    tags=["weather"]
)

@router.get("")
async def get_weather(
        latitude: Annotated[float, Query(ge=-90, le=90)],  # enlem sinirlari
        longitude: Annotated[float, Query(ge=-180, le=180)],  # boylam sinirlari
) -> CurrentWeather:
    return await get_current_weather(latitude=latitude, longitude=longitude)



