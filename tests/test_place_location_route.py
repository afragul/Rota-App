from unittest.mock import AsyncMock

import pytest

from app.core import guest_limit
from app.core.config import get_settings
from app.schemas.places import PlaceLocation

KONUM = PlaceLocation(latitude=40.18, longitude=29.06)


@pytest.fixture(autouse=True)
def _google_sahte(monkeypatch):
    sahte = AsyncMock(return_value=KONUM)
    monkeypatch.setattr("app.api.routes.places.get_place_location", sahte)
    guest_limit._search_counts.clear()
    yield sahte
    guest_limit._search_counts.clear()


async def _giris(client, email: str = "ada@example.com") -> dict:
    kayit = {"email": email, "username": email.split("@")[0], "password": "uzun-bir-sifre-1"}
    r = await client.post("/auth/register", json=kayit)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_konum_doner(client, _google_sahte):
    r = await client.get("/places/ChIJabc/location")

    assert r.status_code == 200
    assert r.json() == {"latitude": 40.18, "longitude": 29.06}
    _google_sahte.assert_awaited_once_with("ChIJabc")


async def test_bos_place_id_422(client, _google_sahte):
    r = await client.get("/places//location")

    assert r.status_code in (404, 422)  # boş path segmenti FastAPI'de route'a hiç düşmez
    _google_sahte.assert_not_awaited()


async def test_misafir_kotasi_arama_ile_paylasilir(client, monkeypatch, _google_sahte):
    """Ayrı bir sayaç yok: /places/search ile aynı günlük arama kotasını paylaşır."""
    monkeypatch.setattr(get_settings(), "guest_daily_search_limit", 2)
    for _ in range(2):
        assert (await client.get("/places/ChIJabc/location")).status_code == 200

    r = await client.get("/places/ChIJabc/location")

    assert r.status_code == 429
    assert r.headers["X-Guest-Limit-Reached"] == "1"
    assert _google_sahte.await_count == 2


async def test_hesap_kotasi_dolunca_429_ve_kullanici_basligi(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "user_daily_search_limit", 1)
    h = await _giris(client)
    assert (await client.get("/places/ChIJabc/location", headers=h)).status_code == 200

    r = await client.get("/places/ChIJabc/location", headers=h)

    assert r.status_code == 429
    assert r.headers["X-User-Limit-Reached"] == "1"


async def test_google_hatasi_502(client, monkeypatch):
    from app.services.places import PlacesServiceError

    hata = AsyncMock(side_effect=PlacesServiceError("Mekân konumu alınamadı"))
    monkeypatch.setattr("app.api.routes.places.get_place_location", hata)

    r = await client.get("/places/ChIJabc/location")

    assert r.status_code == 502
