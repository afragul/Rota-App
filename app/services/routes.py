import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.plan import DayPlan, PlanAlternative, PlanStop, RouteLeg, TravelMode

logger = logging.getLogger(__name__)

# Sadece şemamızdaki alanlar; fazlası gereksiz ve daha pahalı.
_FIELD_MASK = "routes.legs.distanceMeters,routes.legs.duration,routes.legs.polyline.encodedPolyline"


class RoutesServiceError(Exception):
    """Rota alınamadığında fırlatılır (weather/places'daki desenin aynısı)."""


def _waypoint(stop: PlanStop) -> dict[str, Any]:
    return {"location": {"latLng": {"latitude": stop.latitude, "longitude": stop.longitude}}}


def _parse_minutes(value: str) -> int:
    """Google süreyi "312s" biçiminde döndürür; UI dakika gösterir (en az 1 dk)."""
    return max(1, round(float(value.rstrip("s")) / 60))


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
        )
        for raw, start, end in zip(raw_legs, stops[:-1], stops[1:], strict=True)
    ]


async def _compute_legs(stops: list[PlanStop], mode: TravelMode) -> list[RouteLeg]:
    """Tek computeRoutes isteğiyle sıralı durakların ardışık ayaklarını döndürür.

    İlk durak origin, son durak destination, ortadakiler intermediates olur;
    Google her ayak için ayrı mesafe/süre/polyline döndürür.
    """
    settings = get_settings()
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.routes_api_key.get_secret_value(),
        "X-Goog-FieldMask": _FIELD_MASK,
    }
    payload: dict[str, Any] = {
        "origin": _waypoint(stops[0]),
        "destination": _waypoint(stops[-1]),
        "travelMode": mode.value,
        "languageCode": "tr",
    }
    if len(stops) > 2:
        payload["intermediates"] = [_waypoint(s) for s in stops[1:-1]]

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
    if not raw_legs or len(raw_legs) != len(stops) - 1:
        logger.warning(
            "Routes API beklenen ayakları döndürmedi (%s, %d durak)", mode.value, len(stops)
        )
        raise RoutesServiceError("Bu duraklar için rota bulunamadı")

    try:
        return _to_legs(raw_legs, stops, mode)
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
