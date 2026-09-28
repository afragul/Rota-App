import httpx
import pytest
import respx

from app.core.config import get_settings
from app.services.geocoding import GeocodingServiceError, geocode_address

FAKE_RESPONSE = {
    "results": [
        {
            "formatted_address": "Bursa, Türkiye",
            "geometry": {"location": {"lat": 40.1828931, "lng": 29.0663306}},
        }
    ],
    "status": "OK",
}


def _url() -> str:
    return get_settings().google_geocoding_base_url


@respx.mock
async def test_basarili_cozumleme():
    """Normal cevapta koordinat ve adres dönmeli."""
    route = respx.get(_url()).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))

    result = await geocode_address("Bursa")

    assert route.called
    assert result.latitude == 40.1828931
    assert result.longitude == 29.0663306
    assert result.formatted_address == "Bursa, Türkiye"


@respx.mock
async def test_sonuc_bulunamayinca():
    """Google ZERO_RESULTS dönerse GeocodingServiceError fırlatılmalı."""
    respx.get(_url()).mock(
        return_value=httpx.Response(200, json={"results": [], "status": "ZERO_RESULTS"})
    )

    with pytest.raises(GeocodingServiceError):
        await geocode_address("asdkfjaskldfj")


@respx.mock
async def test_google_hata_dondurunce():
    """500 gelirse GeocodingServiceError'a çevrilmeli."""
    respx.get(_url()).mock(return_value=httpx.Response(500, text="sunucu hatası"))

    with pytest.raises(GeocodingServiceError):
        await geocode_address("Bursa")


@respx.mock
async def test_baglanti_kurulamayinca():
    """Ağ yoksa da GeocodingServiceError'a çevrilmeli."""
    respx.get(_url()).mock(side_effect=httpx.ConnectError("baglanti yok"))

    with pytest.raises(GeocodingServiceError):
        await geocode_address("Bursa")


@respx.mock
async def test_istek_dogru_kuruluyor():
    """address, key ve language parametreleri doğru gönderiliyor mu."""
    route = respx.get(_url()).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))

    await geocode_address("Bursa")

    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))

    assert params["address"] == "Bursa"
    assert params["language"] == "tr"
    assert params["key"]
