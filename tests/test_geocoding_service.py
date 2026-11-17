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
    """address, key, language ve region parametreleri doğru gönderiliyor mu."""
    route = respx.get(_url()).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))

    await geocode_address("Bursa")

    request = route.calls.last.request
    params = dict(httpx.QueryParams(request.url.query))

    assert params["address"] == "Bursa"
    assert params["language"] == "tr"
    assert params["region"] == "tr"
    assert params["key"]


@respx.mock
async def test_hata_logunda_api_key_gecmez(caplog):
    """Google 4xx dönünce httpx hata mesajı URL'yi (key dahil) taşır; log'a sızmamalı."""
    respx.get(_url()).mock(return_value=httpx.Response(403))
    key = get_settings().geocoding_api_key.get_secret_value()

    with caplog.at_level("WARNING"), pytest.raises(GeocodingServiceError):
        await geocode_address("Bursa")

    assert caplog.text  # log gerçekten yazılmış olmalı, yoksa test anlamsız
    assert key not in caplog.text
