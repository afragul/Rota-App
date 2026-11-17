import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import clean_log
from app.schemas.geocoding import GeocodeResult

logger = logging.getLogger(__name__)


class GeocodingServiceError(Exception):
    """Şehir/adres koordinata çevrilemediğinde fırlatılır (weather/places'daki desenin aynısı)."""


def _to_result(raw: dict[str, Any]) -> GeocodeResult:
    location = raw["geometry"]["location"]
    return GeocodeResult(
        formatted_address=raw.get("formatted_address", ""),
        latitude=location["lat"],
        longitude=location["lng"],
    )


async def geocode_address(address: str) -> GeocodeResult:
    """Verilen şehir/adres metnini koordinata çevirir."""
    settings = get_settings()

    params = {
        "address": address,
        "language": "tr",
        # Türkiye içindeki aynı isimli yerler (örn. "Alsancak" hem İzmir'de hem
        # Kıbrıs'ta) region biası olmadan yanlış sonuca gidebiliyor; bu sadece
        # bir öncelik ipucu (ccTLD), gerçek dışı bir kısıtlama değil.
        "region": "tr",
        "key": settings.geocoding_api_key.get_secret_value(),
    }

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            response = await client.get(settings.google_geocoding_base_url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        # str(exc) HTTPStatusError'da tam URL'yi taşır; key query string'de olduğu için
        # log'a sızar. Yalnızca hata türü ve (varsa) durum kodu yazılır.
        status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.warning(
            "Geocoding API çağrısı başarısız: %s (durum=%s)", type(exc).__name__, status_code
        )
        raise GeocodingServiceError("Adres/şehir bilgisine ulaşılamadı") from exc

    # Google, hatalı istekte de 200 dönüp durumu body'deki "status" alanına yazar
    api_status = data.get("status")
    results = data.get("results") or []
    if api_status != "OK" or not results:
        logger.warning(
            "Geocoding '%s' için sonuç döndürmedi (status=%s)", clean_log(address), api_status
        )
        raise GeocodingServiceError(f"'{address}' için konum bulunamadı")

    return _to_result(results[0])
