import asyncio
import logging
from dataclasses import dataclass

from app.core.themes import DEFAULT_THEMES, filter_for_bad_weather, types_for
from app.schemas.places import Place
from app.schemas.plan import ClarificationNeeded, DayPlan, PlanRequest
from app.services.geocoding import geocode_address
from app.services.places import PlacesServiceError, search_nearby
from app.services.planner import check_ambiguity, create_plan, resolve_themes
from app.services.routes import add_routes
from app.services.weather import WeatherServiceError, get_current_weather, is_bad_weather

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


@dataclass
class _WeatherContext:
    summary: str
    is_bad: bool  # yağış/fırtına -> tema havuzu indoor'a daraltılır


async def _fetch_weather_context(latitude: float, longitude: float) -> _WeatherContext:
    """Hava durumunu özet metne ve indoor/outdoor kararına çevirir.

    Hava servisi kritik değil: alınamazsa plan yine de kurulur, sadece
    indoor/outdoor daraltması uygulanmaz (is_bad=False, karma önerilir).
    """
    try:
        weather = await get_current_weather(latitude, longitude)
    except WeatherServiceError as exc:
        logger.warning("Hava durumu alınamadı: %s", exc)
        return _WeatherContext(summary="bilinmiyor", is_bad=False)

    return _WeatherContext(
        summary=f"{weather.temperature}°C, {weather.condition}",
        is_bad=is_bad_weather(weather.code),
    )


async def _determine_themes(request: PlanRequest) -> list[str]:
    """Kategori seçimi, serbest metin veya varsayılan temalardan birini kullanır."""
    if request.categories:
        return request.categories
    if request.free_text:
        return await resolve_themes(request.free_text)
    return DEFAULT_THEMES


async def build_day_plan(request: PlanRequest) -> DayPlan | ClarificationNeeded:
    """Uçtan uca: (belirsizlik kontrolü) → konum çözümleme → hava+temalar → mekan havuzu → plan."""
    # 0. free_text tek başına tema kaynağıysa ve bu ilk turdaysa (henüz bir
    # cevap gelmemişse) belirsizlik kontrolü yap. Geocoding/hava/mekan
    # aramasından ÖNCE çalışır ki belirsizse o çağrılar hiç yapılmasın.
    if request.free_text and not request.categories and not request.clarification_answer:
        question = await check_ambiguity(request)
        if question:
            return ClarificationNeeded(question=question)

    # 1. Konumu netleştir (city verildiyse koordinata çevir)
    latitude, longitude = await _resolve_coordinates(request)

    # 2. Hava durumu ve tema çözümleme birbirinden bağımsız, paralel çekilebilir
    weather_task = _fetch_weather_context(latitude, longitude)
    themes_task = _determine_themes(request)
    weather, themes = await asyncio.gather(weather_task, themes_task)

    # 3. Hava kötüyse mekan araması başlamadan temaları indoor'a daralt.
    # Bu yüzden mekan araması artık hava sonucunu bekliyor, eskisi gibi
    # hava ile paralel çekilemiyor.
    if weather.is_bad:
        before = themes
        themes = filter_for_bad_weather(themes)
        if themes != before:
            logger.info("Hava kötü, temalar daraltıldı: %s -> %s", before, themes)

    pool = await _gather_places(latitude, longitude, themes)

    if not pool:
        raise PlacesServiceError("Bu bölgede uygun mekan bulunamadı")

    logger.info("Havuzda %d mekan var", len(pool))

    # 4. Planı kur
    plan = await create_plan(request, pool, weather.summary)

    # 5. Rota çizgisini seçilen ulaşım moduyla ekle (kritik değil, hata planı düşürmez)
    return await add_routes(plan, request.travel_mode)
