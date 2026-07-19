import httpx
import pytest
import respx

from app.core.config import get_settings
from app.services.places import PlacesServiceError, search_nearby

# Google'ın gerçek cevabına benzeyen sahte veri
FAKE_RESPONSE = {
    "places": [
        {
            "id": "ChIJ123",
            "displayName": {"text": "Kitap Kahve", "languageCode": "tr"},
            "formattedAddress": "Osmangazi, Bursa",
            "location": {"latitude": 40.1885, "longitude": 29.0610},
            "rating": 4.6,
            "userRatingCount": 312,
            "types": ["cafe"],
        }
    ]
}


def _url() -> str:
    return f"{get_settings().google_places_base_url}/places:searchNearby"


@respx.mock
async def test_basarili_arama():
    """Normal cevapta Place listesi dönmeli."""
    route = respx.post(_url()).mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )

    places = await search_nearby(40.1885, 29.0610, ["cafe"])

    assert route.called
    assert len(places) == 1
    assert places[0].name == "Kitap Kahve"


@respx.mock
async def test_bos_sonuc():
    """Hiç mekân yoksa Google boş gövde döner; biz boş liste döndürmeliyiz."""
    respx.post(_url()).mock(return_value=httpx.Response(200, json={}))

    places = await search_nearby(40.1885, 29.0610, ["cafe"])

    assert places == []


@respx.mock
async def test_google_hata_dondurunce():
    """500 gelirse PlacesServiceError'a çevrilmeli."""
    respx.post(_url()).mock(return_value=httpx.Response(500, text="sunucu hatası"))

    with pytest.raises(PlacesServiceError):
        await search_nearby(40.1885, 29.0610, ["cafe"])


@respx.mock
async def test_baglanti_kurulamayinca():
    """Ağ yoksa da PlacesServiceError'a çevrilmeli."""
    respx.post(_url()).mock(side_effect=httpx.ConnectError("baglanti yok"))

    with pytest.raises(PlacesServiceError):
        await search_nearby(40.1885, 29.0610, ["cafe"])


@respx.mock
async def test_istek_dogru_kuruluyor():
    """Field mask ve API key başlıkları gönderiliyor mu, gövde doğru mu."""
    route = respx.post(_url()).mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )

    await search_nearby(40.1885, 29.0610, ["cafe", "bakery"], radius=800)

    request = route.calls.last.request

    assert request.headers["X-Goog-Api-Key"]           # key gidiyor mu
    assert "places.id" in request.headers["X-Goog-FieldMask"]
    assert "places.rating" in request.headers["X-Goog-FieldMask"]

    import json
    body = json.loads(request.content)
    assert body["includedTypes"] == ["cafe", "bakery"]
    assert body["locationRestriction"]["circle"]["radius"] == 800
    assert body["languageCode"] == "tr"