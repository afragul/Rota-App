import asyncio
import logging
from dataclasses import dataclass

from app.core.logging import clean_log
from app.core.themes import DEFAULT_THEMES, filter_for_bad_weather, types_for
from app.schemas.places import Place
from app.schemas.plan import (
    AnchorPlace,
    ClarificationNeeded,
    DayPlan,
    PlanRequest,
    PlanStop,
    WeatherSummary,
)
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
    # Koordinatlar kişisel veri sayılabilir: yalnızca çözümlendiği yazılır.
    logger.info("'%s' koordinata çözümlendi", clean_log(request.city))
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


def _ensure_anchor_stop(plan: DayPlan, anchor: AnchorPlace) -> None:
    """LLM'in seçimine güvenmeden, anchor mekanını her alternatife durak
    olarak garanti eder (zaten varsa dokunmaz). Ana sayfada sık gidilen bir
    mekana basılınca kullanılır — kullanıcı "bu mekan kesin rotada olsun"
    dediği için, LLM'in onu havuzdan seçip seçmediğine bakılmaz."""
    for alternative in plan.alternatives:
        if any(stop.place_id == anchor.place_id for stop in alternative.stops):
            continue
        alternative.stops.append(
            PlanStop(
                place_id=anchor.place_id,
                order=len(alternative.stops) + 1,
                arrival_time="-",
                duration_minutes=60,
                activity=f"{anchor.name} keşfi",
                recommendation="Detaylar için Google Maps linkine bakabilirsin.",
                estimated_cost=0,
                name=anchor.name,
                latitude=anchor.latitude,
                longitude=anchor.longitude,
            )
        )


@dataclass
class _WeatherContext:
    summary: str
    is_bad: bool  # yağış/fırtına -> tema havuzu indoor'a daraltılır
    info: WeatherSummary | None = None  # None: hava alınamadı


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
        info=WeatherSummary(
            temperature=weather.temperature,
            condition=weather.condition,
            is_bad=is_bad_weather(weather.code),
        ),
    )


async def _determine_themes(request: PlanRequest) -> list[str]:
    """Kategori seçimi, serbest metin veya varsayılan temalardan birini kullanır."""
    if request.categories:
        return request.categories
    if request.free_text:
        return await resolve_themes(request.free_text)
    return DEFAULT_THEMES


async def build_day_plan(
    request: PlanRequest, max_alternatives: int | None = None
) -> DayPlan | ClarificationNeeded:
    """Uçtan uca: (belirsizlik kontrolü) → konum çözümleme → hava+temalar → mekan havuzu → plan.

    max_alternatives verilirse (misafirler için 1) fazla alternatifler rota
    hesabından ÖNCE atılır, böylece atılanlar için Routes çağrısı yapılmaz.
    """
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

    # Anchor mekanı havuzda yoksa ekle (ek bir Places çağrısı değil, istemci
    # zaten tam Place verisini gönderiyor) — LLM onu görüp seçebilsin diye.
    if request.anchor_place and not any(p.place_id == request.anchor_place.place_id for p in pool):
        pool.insert(
            0,
            Place(
                place_id=request.anchor_place.place_id,
                name=request.anchor_place.name,
                address=request.anchor_place.address,
                latitude=request.anchor_place.latitude,
                longitude=request.anchor_place.longitude,
                types=request.anchor_place.types,
            ),
        )

    if not pool:
        raise PlacesServiceError("Bu bölgede uygun mekan bulunamadı")

    logger.info("Havuzda %d mekan var", len(pool))

    # 4. Planı kur
    plan = await create_plan(request, pool, weather.summary)
    if max_alternatives is not None:
        plan.alternatives = plan.alternatives[:max_alternatives]

    # LLM anchor mekanını seçmemiş olabilir; seçmediyse zorla ekle (bkz.
    # docstring) — legs hesaplamasından (add_routes) ÖNCE, ki eklenen durağın
    # da rota çizgisi normal akışta hesaplansın.
    if request.anchor_place:
        _ensure_anchor_stop(plan, request.anchor_place)

    # Havuzu da döndür: frontend durak değiştirirken (ücretsiz) buradan seçer.
    plan.place_pool = pool

    # 5. Rota çizgisini seçilen ulaşım moduyla ekle (kritik değil, hata planı düşürmez)
    plan = await add_routes(plan, request.travel_mode)

    plan.weather = weather.info
    plan.weather_available = weather.info is not None
    return plan
