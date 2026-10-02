import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.plan import (
    ApproachRoute,
    DayPlan,
    PlanAlternative,
    PlanStop,
    RouteLeg,
    RouteStep,
    TransitDetail,
    TravelMode,
)

logger = logging.getLogger(__name__)

# Sadece şemamızdaki alanlar; fazlası gereksiz ve daha pahalı.
_FIELD_MASK = ",".join(
    [
        "routes.legs.distanceMeters",
        "routes.legs.duration",
        "routes.legs.polyline.encodedPolyline",
        # Adım adım tarif
        "routes.legs.steps.distanceMeters",
        "routes.legs.steps.staticDuration",
        "routes.legs.steps.travelMode",
        "routes.legs.steps.navigationInstruction",
        "routes.legs.steps.transitDetails",
    ]
)


class RoutesServiceError(Exception):
    """Rota alınamadığında fırlatılır (weather/places'daki desenin aynısı)."""


def _waypoint(stop: PlanStop) -> dict[str, Any]:
    return {"location": {"latLng": {"latitude": stop.latitude, "longitude": stop.longitude}}}


def _parse_minutes(value: str) -> int:
    """Google süreyi "312s" biçiminde döndürür; UI dakika gösterir (en az 1 dk)."""
    return max(1, round(float(value.rstrip("s")) / 60))


def _parse_transit(raw: dict[str, Any]) -> TransitDetail:
    line = raw.get("transitLine") or {}
    stops = raw.get("stopDetails") or {}
    times = (raw.get("localizedValues") or {}).get("departureTime") or {}
    return TransitDetail(
        line_name=line.get("nameShort") or line.get("name"),
        line_color=line.get("color"),
        line_text_color=line.get("textColor"),
        vehicle=((line.get("vehicle") or {}).get("name") or {}).get("text"),
        headsign=raw.get("headsign"),
        departure_stop=(stops.get("departureStop") or {}).get("name"),
        arrival_stop=(stops.get("arrivalStop") or {}).get("name"),
        departure_time=((times.get("time") or {}).get("text")),
        stop_count=raw.get("stopCount"),
    )


def _parse_steps(raw_leg: dict[str, Any], fallback_mode: TravelMode) -> list[RouteStep]:
    """Ayağın adımlarını çözer. Adımlar kritik değil: bozuk bir adım atlanır,
    hiçbiri çözülemezse boş liste döner; ayağın kendisi (mesafe/süre/çizgi) etkilenmez."""
    steps: list[RouteStep] = []
    for raw in raw_leg.get("steps") or []:
        try:
            nav = raw.get("navigationInstruction") or {}
            mode = raw.get("travelMode")
            step_mode = TravelMode(mode) if mode in TravelMode.__members__ else fallback_mode
            transit = raw.get("transitDetails")
            steps.append(
                RouteStep(
                    travel_mode=step_mode,
                    instruction=nav.get("instructions"),
                    maneuver=nav.get("maneuver"),
                    distance_meters=raw.get("distanceMeters", 0),
                    duration_minutes=_parse_minutes(raw.get("staticDuration", "0s")),
                    transit=_parse_transit(transit) if transit else None,
                )
            )
        except (ValueError, TypeError, AttributeError) as exc:
            logger.warning("Rota adımı çözümlenemedi, atlandı: %s", exc)
    return steps


def _to_legs(
    raw_legs: list[dict[str, Any]], stops: list[PlanStop], mode: TravelMode
) -> list[RouteLeg]:
    return [
        RouteLeg(
            from_order=start.order,
            to_order=end.order,
            travel_mode=mode,
            # Aynı noktaya iki durak varsa Google distanceMeters'ı hiç göndermez
            distance_meters=raw.get("distanceMeters", 0),
            duration_minutes=_parse_minutes(raw.get("duration", "0s")),
            polyline=raw["polyline"]["encodedPolyline"],
            steps=_parse_steps(raw, mode),
        )
        for raw, start, end in zip(raw_legs, stops[:-1], stops[1:], strict=True)
    ]


async def _request_legs(payload: dict[str, Any], mode: TravelMode) -> list[dict[str, Any]]:
    """computeRoutes'a tek istek atar, ham ayakları (legs) döndürür."""
    settings = get_settings()
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.routes_api_key.get_secret_value(),
        "X-Goog-FieldMask": _FIELD_MASK,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            response = await client.post(
                settings.google_routes_base_url, headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        # Asıl neden Google'ın gövdesinde (ör. 403: Routes API etkin değil, 400: geçersiz istek)
        logger.warning(
            "Routes API %s (%s) hatası döndürdü: %s",
            exc.response.status_code,
            mode.value,
            exc.response.text[:300],
        )
        raise RoutesServiceError("Rota bilgisine ulaşılamadı") from exc
    except httpx.HTTPError as exc:
        logger.warning("Routes API'ye ulaşılamadı (%s): %s", mode.value, exc)
        raise RoutesServiceError("Rota bilgisine ulaşılamadı") from exc

    routes = data.get("routes") or []
    raw_legs = routes[0].get("legs") if routes else None
    if not raw_legs:
        logger.warning("Routes API ayak döndürmedi (%s)", mode.value)
        raise RoutesServiceError("Bu noktalar için rota bulunamadı")
    return raw_legs


async def _compute_legs(stops: list[PlanStop], mode: TravelMode) -> list[RouteLeg]:
    """Tek computeRoutes isteğiyle sıralı durakların ardışık ayaklarını döndürür.

    İlk durak origin, son durak destination, ortadakiler intermediates olur;
    Google her ayak için ayrı mesafe/süre/polyline döndürür.
    """
    payload: dict[str, Any] = {
        "origin": _waypoint(stops[0]),
        "destination": _waypoint(stops[-1]),
        "travelMode": mode.value,
        "languageCode": "tr",
    }
    if len(stops) > 2:
        payload["intermediates"] = [_waypoint(s) for s in stops[1:-1]]

    raw_legs = await _request_legs(payload, mode)
    if len(raw_legs) != len(stops) - 1:
        logger.warning(
            "Routes API beklenen ayakları döndürmedi (%s, %d durak)", mode.value, len(stops)
        )
        raise RoutesServiceError("Bu duraklar için rota bulunamadı")

    try:
        return _to_legs(raw_legs, stops, mode)
    except (KeyError, ValueError) as exc:
        logger.warning("Routes API yanıtı çözümlenemedi: %s", exc)
        raise RoutesServiceError("Rota yanıtı çözümlenemedi") from exc


async def get_approach_route(
    origin: tuple[float, float], destination: tuple[float, float], mode: TravelMode
) -> ApproachRoute:
    """Kullanıcının konumundan (origin) verilen noktaya (genelde ilk durak) tek ayak rota."""

    def point(lat_lng: tuple[float, float]) -> dict[str, Any]:
        return {"location": {"latLng": {"latitude": lat_lng[0], "longitude": lat_lng[1]}}}

    payload = {
        "origin": point(origin),
        "destination": point(destination),
        "travelMode": mode.value,
        "languageCode": "tr",
    }
    raw = (await _request_legs(payload, mode))[0]
    try:
        return ApproachRoute(
            travel_mode=mode,
            distance_meters=raw.get("distanceMeters", 0),
            duration_minutes=_parse_minutes(raw.get("duration", "0s")),
            polyline=raw["polyline"]["encodedPolyline"],
            steps=_parse_steps(raw, mode),
        )
    except (KeyError, ValueError) as exc:
        logger.warning("Routes API yanıtı çözümlenemedi: %s", exc)
        raise RoutesServiceError("Rota yanıtı çözümlenemedi") from exc


async def get_route_legs(stops: list[PlanStop], mode: TravelMode) -> list[RouteLeg]:
    """Sıralı durakların ardışık çiftleri arasındaki ayakları seçilen ulaşım moduyla döndürür."""
    if len(stops) < 2:
        return []

    if mode is TravelMode.TRANSIT:
        # Routes API TRANSIT modunda intermediates kabul etmiyor: her çift ayrı istek
        pairs = zip(stops[:-1], stops[1:], strict=True)
        per_pair = await asyncio.gather(*(_compute_legs([a, b], mode) for a, b in pairs))
        return [leg for legs in per_pair for leg in legs]

    return await _compute_legs(stops, mode)


async def _fill_legs(alternative: PlanAlternative, mode: TravelMode) -> None:
    # Koordinatı olmayan durak rotaya giremez; kalanlar order sırasına göre bağlanır
    stops = sorted(
        (s for s in alternative.stops if s.latitude is not None and s.longitude is not None),
        key=lambda s: s.order,
    )
    try:
        alternative.legs = await get_route_legs(stops, mode)
    except RoutesServiceError as exc:
        # Rota kritik değil: plan yine döner, sadece harita çizgisi olmaz. Nedeni
        # (hangi plan, hangi mod) log'da; istemci routes_available=False ile haberdar olur.
        logger.warning("'%s' planı için rota eklenemedi: %s", alternative.theme, exc)
        alternative.legs = []
        alternative.routes_available = False


async def add_routes(plan: DayPlan, mode: TravelMode = TravelMode.WALK) -> DayPlan:
    """Her alternatifin `legs` alanını doldurur; alternatifler paralel sorgulanır."""
    await asyncio.gather(*(_fill_legs(a, mode) for a in plan.alternatives))
    return plan
