import uuid

import pytest

from app.core.config import get_settings

STOP = {
    "place_id": "p1",
    "order": 1,
    "arrival_time": "10:00",
    "duration_minutes": 60,
    "activity": "Gez",
    "recommendation": "Çay iç",
    "estimated_cost": 100,
    "name": "Kapalı Çarşı",
    "latitude": 40.19,
    "longitude": 29.06,
}
LEG = {
    "travel_mode": "WALK",
    "from_order": 1,
    "to_order": 2,
    "distance_meters": 500,
    "duration_minutes": 7,
    "polyline": "abc",
}
PLAN = {
    "theme": "Tarihi Bursa",
    "title": "Osmanlı izinde",
    "summary": "Bir günlük tarih turu.",
    "stops": [STOP],
    "legs": [LEG],
    "routes_available": True,
}


async def _giris(client, email: str = "ada@example.com") -> dict:
    kayit = {"email": email, "username": email.split("@")[0], "password": "uzun-bir-sifre-1"}
    r = await client.post("/auth/register", json=kayit)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_giris_yapmadan_plan_islemleri_reddedilir(client):
    assert (await client.post("/plans", json=PLAN)).status_code == 401
    assert (await client.get("/plans")).status_code == 401
    assert (await client.delete(f"/plans/{uuid.uuid4()}")).status_code == 401


async def test_plan_kaydedilir_ve_listelenir(client):
    h = await _giris(client)
    r = await client.post("/plans", json=PLAN, headers=h)
    assert r.status_code == 201
    plan_id = r.json()["id"]

    liste = (await client.get("/plans", headers=h)).json()
    assert [p["id"] for p in liste] == [plan_id]
    assert liste[0]["title"] == "Osmanlı izinde"
    assert "stops" not in liste[0]  # liste satırında ağır alanlar yok


async def test_kullanici_sadece_kendi_planlarini_gorur(client):
    ada = await _giris(client, "ada@example.com")
    can = await _giris(client, "can@example.com")
    await client.post("/plans", json=PLAN, headers=ada)
    assert (await client.get("/plans", headers=can)).json() == []


async def test_baskasinin_plani_silinemez(client):
    ada = await _giris(client, "ada@example.com")
    can = await _giris(client, "can@example.com")
    plan_id = (await client.post("/plans", json=PLAN, headers=ada)).json()["id"]

    assert (await client.delete(f"/plans/{plan_id}", headers=can)).status_code == 404
    assert len((await client.get("/plans", headers=ada)).json()) == 1  # hâlâ duruyor


async def test_kendi_plani_silinir(client):
    h = await _giris(client)
    plan_id = (await client.post("/plans", json=PLAN, headers=h)).json()["id"]
    assert (await client.delete(f"/plans/{plan_id}", headers=h)).status_code == 204
    assert (await client.get("/plans", headers=h)).json() == []
    assert (await client.delete(f"/plans/{plan_id}", headers=h)).status_code == 404


async def test_paylasim_linki_girissiz_acilir_ve_sahibi_gizler(client):
    h = await _giris(client)
    plan_id = (await client.post("/plans", json=PLAN, headers=h)).json()["id"]

    r = await client.get(f"/shared/{plan_id}")  # Authorization yok
    assert r.status_code == 200
    body = r.json()
    assert body["stops"][0]["name"] == "Kapalı Çarşı"
    assert "user_id" not in body


async def test_olmayan_paylasim_404_ve_bozuk_id_422(client):
    assert (await client.get(f"/shared/{uuid.uuid4()}")).status_code == 404
    assert (await client.get("/shared/liste-degil")).status_code == 422


async def test_plan_sayisi_siniri(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_saved_plans_per_user", 2)
    h = await _giris(client)
    for _ in range(2):
        assert (await client.post("/plans", json=PLAN, headers=h)).status_code == 201
    assert (await client.post("/plans", json=PLAN, headers=h)).status_code == 409


@pytest.mark.parametrize(
    "override",
    [
        {"stops": []},
        {"stops": [STOP] * 26},
        {"title": ""},
        {"title": "x" * 201},
        {"summary": "x" * 1001},
        {"stops": [{"place_id": "p1"}]},  # eksik alanlar
    ],
)
async def test_gecersiz_plan_reddedilir(client, override):
    h = await _giris(client)
    r = await client.post("/plans", json={**PLAN, **override}, headers=h)
    assert r.status_code == 422


async def test_paylasimda_is_owner_yalniz_sahibine_true(client):
    ada = await _giris(client, "ada@example.com")
    can = await _giris(client, "can@example.com")
    plan_id = (await client.post("/plans", json=PLAN, headers=ada)).json()["id"]

    assert (await client.get(f"/shared/{plan_id}", headers=ada)).json()["is_owner"] is True
    assert (await client.get(f"/shared/{plan_id}", headers=can)).json()["is_owner"] is False
    assert (await client.get(f"/shared/{plan_id}")).json()["is_owner"] is False
