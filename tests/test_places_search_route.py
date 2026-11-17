from unittest.mock import AsyncMock

import pytest

from app.core import guest_limit
from app.core.config import get_settings
from app.schemas.places import Place

YER = Place(
    place_id="ChIJabc",
    name="Kozahan",
    address="Bursa",
    latitude=40.18,
    longitude=29.06,
    types=["shopping_mall"],
)
PARAMS = {"q": "Kozahan", "latitude": 40.18, "longitude": 29.06}


@pytest.fixture(autouse=True)
def _google_sahte(monkeypatch):
    sahte = AsyncMock(return_value=[YER])
    monkeypatch.setattr("app.api.routes.places.search_text", sahte)
    guest_limit._search_counts.clear()
    yield sahte
    guest_limit._search_counts.clear()


async def _giris(client, email: str = "ada@example.com") -> dict:
    kayit = {"email": email, "username": email.split("@")[0], "password": "uzun-bir-sifre-1"}
    r = await client.post("/auth/register", json=kayit)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_arama_sonuc_doner(client, _google_sahte):
    r = await client.get("/places/search", params=PARAMS)

    assert r.status_code == 200
    assert r.json()[0]["name"] == "Kozahan"
    _google_sahte.assert_awaited_once_with("Kozahan", 40.18, 29.06)


async def test_arama_metni_kirpilir(client, _google_sahte):
    await client.get("/places/search", params={**PARAMS, "q": "  Kozahan  "})

    assert _google_sahte.await_args.args[0] == "Kozahan"


@pytest.mark.parametrize(
    "degisiklik",
    [{"q": "a"}, {"q": "x" * 101}, {"latitude": 95}, {"longitude": -181}],
)
async def test_gecersiz_girdi_422_ve_google_cagrilmaz(client, _google_sahte, degisiklik):
    r = await client.get("/places/search", params={**PARAMS, **degisiklik})

    assert r.status_code == 422
    _google_sahte.assert_not_awaited()


async def test_q_zorunlu(client):
    r = await client.get("/places/search", params={"latitude": 40.0, "longitude": 29.0})

    assert r.status_code == 422


async def test_misafir_kotasi_dolunca_429_ve_misafir_basligi(client, monkeypatch, _google_sahte):
    monkeypatch.setattr(get_settings(), "guest_daily_search_limit", 2)
    for _ in range(2):
        assert (await client.get("/places/search", params=PARAMS)).status_code == 200

    r = await client.get("/places/search", params=PARAMS)

    assert r.status_code == 429
    assert r.headers["X-Guest-Limit-Reached"] == "1"
    assert _google_sahte.await_count == 2  # kota dolunca Google'a gidilmez


async def test_giris_yapmis_kullanici_misafir_kotasina_takilmaz(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "guest_daily_search_limit", 1)
    h = await _giris(client)
    for _ in range(3):
        assert (await client.get("/places/search", params=PARAMS, headers=h)).status_code == 200


async def test_hesap_kotasi_dolunca_429_ve_kullanici_basligi(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "user_daily_search_limit", 2)
    h = await _giris(client)
    for _ in range(2):
        assert (await client.get("/places/search", params=PARAMS, headers=h)).status_code == 200

    r = await client.get("/places/search", params=PARAMS, headers=h)

    assert r.status_code == 429
    assert r.headers["X-User-Limit-Reached"] == "1"
    assert "X-Guest-Limit-Reached" not in r.headers


async def test_arama_sayaci_plan_ve_legs_sayaclarindan_bagimsiz(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "user_daily_search_limit", 1)
    h = await _giris(client)
    assert (await client.get("/places/search", params=PARAMS, headers=h)).status_code == 200
    assert (await client.get("/places/search", params=PARAMS, headers=h)).status_code == 429

    # Arama kotası dolsa da /route/legs kendi kotasından devam eder.
    monkeypatch.setattr("app.api.routes.route.get_route_legs", AsyncMock(return_value=[]))
    legs = {
        "stops": [
            {"order": 1, "latitude": 40.0, "longitude": 29.0},
            {"order": 2, "latitude": 40.1, "longitude": 29.1},
        ],
        "travel_mode": "WALK",
    }
    assert (await client.post("/route/legs", json=legs, headers=h)).status_code == 200


async def test_google_hatasi_502(client, monkeypatch):
    from app.services.places import PlacesServiceError

    hata = AsyncMock(side_effect=PlacesServiceError("Mekân verisi alınamadı"))
    monkeypatch.setattr("app.api.routes.places.search_text", hata)
    r = await client.get("/places/search", params=PARAMS)

    assert r.status_code == 502
