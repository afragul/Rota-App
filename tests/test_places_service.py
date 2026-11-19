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

def _text_url() -> str:
    return f"{get_settings().google_places_base_url}/places:searchText"


@respx.mock
async def test_metin_aramasi_sonuclari_doner_ve_konuma_oncelik_verir():
    import json

    from app.services.places import search_text

    route = respx.post(_text_url()).mock(return_value=httpx.Response(200, json=FAKE_RESPONSE))

    places = await search_text("Kitap Kahve", 40.18, 29.06)

    assert [p.name for p in places] == ["Kitap Kahve"]
    sent = json.loads(route.calls.last.request.content)
    assert sent["textQuery"] == "Kitap Kahve"
    assert sent["languageCode"] == "tr"
    # Bölgeyle sınırlama değil, öncelik (locationBias): başka şehirdeki yer de bulunabilsin.
    assert "locationBias" in sent and "locationRestriction" not in sent
    assert route.calls.last.request.headers["X-Goog-Api-Key"]


@respx.mock
async def test_metin_aramasi_sonuc_yoksa_bos_liste():
    from app.services.places import search_text

    respx.post(_text_url()).mock(return_value=httpx.Response(200, json={}))

    assert await search_text("yokboyleyer", 40.18, 29.06) == []


@respx.mock
async def test_metin_aramasi_hatada_places_service_error():
    from app.services.places import search_text

    respx.post(_text_url()).mock(return_value=httpx.Response(500))

    with pytest.raises(PlacesServiceError):
        await search_text("kahve", 40.18, 29.06)


# --- get_place_location ---
# favorite_places/visited_places artık koordinat saklamıyor (Google ToS 14.3/19.3,
# bkz. ROADMAP.md); bir mekan gerçekten kullanılacağı an koordinat buradan anlık çekilir.


def _location_url(place_id: str) -> str:
    return f"{get_settings().google_places_base_url}/places/{place_id}"


@respx.mock
async def test_konum_basariyla_cekilir():
    from app.services.places import get_place_location

    route = respx.get(_location_url("ChIJ123")).mock(
        return_value=httpx.Response(
            200, json={"location": {"latitude": 40.1885, "longitude": 29.0610}}
        )
    )

    konum = await get_place_location("ChIJ123")

    assert (konum.latitude, konum.longitude) == (40.1885, 29.0610)
    # Yalnızca konum alanı istenmeli: en ucuz fiyat katmanında kalınır.
    assert route.calls.last.request.headers["X-Goog-FieldMask"] == "location"


@respx.mock
async def test_konum_google_hata_dondurunce():
    from app.services.places import get_place_location

    respx.get(_location_url("ChIJ123")).mock(return_value=httpx.Response(404))

    with pytest.raises(PlacesServiceError):
        await get_place_location("ChIJ123")


@respx.mock
async def test_konum_beklenmeyen_govdede_places_service_error():
    from app.services.places import get_place_location

    respx.get(_location_url("ChIJ123")).mock(return_value=httpx.Response(200, json={}))

    with pytest.raises(PlacesServiceError):
        await get_place_location("ChIJ123")
