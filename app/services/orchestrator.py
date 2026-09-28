import asyncio
import logging

from app.core.themes import DEFAULT_THEMES, types_for
from app.schemas.places import Place
from app.schemas.plan import DayPlan, PlanRequest
from app.services.geocoding import geocode_address
from app.services.places import PlacesServiceError, search_nearby
from app.services.planner import create_plan, resolve_themes
from app.services.weather import WeatherServiceError, get_current_weather

logger = logging.getLogger(__name__)

MAX_POOL_SIZE = 40


async def _resolve_coordinates(request: PlanRequest) -> tuple[float, float]:
    """İstekte koordinat varsa onu kullanır, yoksa city'yi koordinata çevirir."""
    if request.latitude is not None and request.longitude is not None:
        return request.latitude, request.longitude

    assert request.city is not None  # PlanRequest validator'ı garanti ediyor
    result = await geocode_address(request.city)
    logger.info(
        "'%s' -> (%s, %s) olarak çözümlendi", request.city, result.latitude, result.longitude
    )
    return result.latitude, result.longitude


async def _gather_places(latitude: float, longitude: float, themes: list[str]) -> list[Place]:
    """Her tema için ayrı arama yapıp havuzu birleştirir."""
    tasks = [
        search_nearby(
            latitude=latitude,
            longitude=longitude,
            included_types=types_for([theme]),
            max_results=10,
        )
        for theme in themes
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    pool: list[Place] = []
    seen: set[str] = set()
    for theme, result in zip(themes, results, strict=True):
        if isinstance(result, Exception):
            logger.warning("'%s' teması için arama başarısız: %s", theme, result)
            continue
        for place in result:
            if place.place_id not in seen:
                seen.add(place.place_id)
                pool.append(place)

    return pool[:MAX_POOL_SIZE]


async def _weather_summary(latitude: float, longitude: float) -> str:
    """Hava durumunu metne çevirir; alınamazsa plan yine de kurulur."""
    try:
        weather = await get_current_weather(latitude, longitude)
        return f"{weather.temperature}°C, {weather.description}"
    except WeatherServiceError as exc:
        logger.warning("Hava durumu alınamadı: %s", exc)
        return "bilinmiyor"


async def build_day_plan(request: PlanRequest) -> DayPlan:
    """Uçtan uca: konum çözümleme → temalar → mekan havuzu + hava → plan."""
    # 1. Konumu netleştir (city verildiyse koordinata çevir)
    latitude, longitude = await _resolve_coordinates(request)

    # 2. Temaları belirle
    if request.categories:
        themes = request.categories
    elif request.free_text:
        themes = await resolve_themes(request.free_text)
    else:
        themes = DEFAULT_THEMES

    logger.info("Seçilen temalar: %s", themes)

    # 3. Hava ve mekanları paralel çek
    weather_task = _weather_summary(latitude, longitude)
    places_task = _gather_places(latitude, longitude, themes)
    weather, pool = await asyncio.gather(weather_task, places_task)

    if not pool:
        raise PlacesServiceError("Bu bölgede uygun mekan bulunamadı")

    logger.info("Havuzda %d mekan var", len(pool))

    # 4. Planı kur
    return await create_plan(request, pool, weather)
