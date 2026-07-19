import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.places import Place

logger = logging.getLogger(__name__)

# Sadece şemamızdaki alanlar. Fazlası hem gereksiz hem daha pahalı.
_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.types",
    ]
)


class PlacesServiceError(Exception):
    """Places API'den veri alınamadığında fırlatılır (weather'daki desenin aynısı)."""


def _to_place(raw: dict[str, Any]) -> Place:
    """Google'ın ham mekân JSON'unu kendi Place modelimize çevirir."""
    location = raw.get("location", {})
    return Place(
        place_id=raw["id"],
        # displayName düz metin değil: {"text": "...", "languageCode": "tr"}
        name=raw.get("displayName", {}).get("text", "İsimsiz"),
        address=raw.get("formattedAddress"),
        latitude=location["latitude"],
        longitude=location["longitude"],
        rating=raw.get("rating"),
        user_rating_count=raw.get("userRatingCount"),
        types=raw.get("types", []),
    )


async def search_nearby(
    latitude: float,
    longitude: float,
    included_types: list[str],
    radius: float = 1500.0,
    max_results: int = 10,
) -> list[Place]:
    """Verilen koordinatın çevresinde, istenen türlerdeki mekânları döndürür."""
    settings = get_settings()
    url = f"{settings.google_places_base_url}/places:searchNearby"

    headers = {
        "Content-Type": "application/json",
        # SecretStr'ı düz metne çevirdiğimiz TEK yer burası
        "X-Goog-Api-Key": settings.places_api_key.get_secret_value(),
        "X-Goog-FieldMask": _FIELD_MASK,
    }

    payload = {
        "includedTypes": included_types,
        "maxResultCount": max_results,
        "languageCode": "tr",  # mekân adları ve adresler Türkçe gelsin
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius,
            }
        },
    }

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Places API çağrısı başarısız: %s", exc)
        raise PlacesServiceError("Mekân verisi alınamadı") from exc

    # Hiç sonuç yoksa Google boş bir gövde döner: {}
    return [_to_place(item) for item in data.get("places", [])]