import pytest

from app.core.config import get_settings

PLACE = {
    "place_id": "ChIJ-abc_1",
    "name": "Kapalı Çarşı",
    "address": "Bursa",
    "latitude": 40.19,
    "longitude": 29.06,
    "rating": 4.5,
    "user_rating_count": 120,
    "types": ["tourist_attraction"],
}


def _yer(n: int) -> dict:
    return {**PLACE, "place_id": f"yer-{n}", "name": f"Yer {n}"}


async def _giris(client, email: str = "ada@example.com") -> dict:
    kayit = {"email": email, "username": email.split("@")[0], "password": "uzun-bir-sifre-1"}
    r = await client.post("/auth/register", json=kayit)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Giriş zorunluluğu ---


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/favorites"),
        ("POST", "/favorites"),
        ("DELETE", "/favorites/x"),
        ("GET", "/visits"),
        ("POST", "/visits"),
        ("DELETE", "/visits"),
        ("DELETE", "/visits/x"),
    ],
)
async def test_giris_yapmadan_reddedilir(client, method, path):
    r = await client.request(method, path, json=PLACE if method == "POST" else None)
    assert r.status_code == 401


# --- Favoriler ---


async def test_favori_eklenir_listelenir_ve_cikarilir(client):
    h = await _giris(client)
    r = await client.post("/favorites", json=PLACE, headers=h)
    assert r.status_code == 201
    assert r.json()["name"] == "Kapalı Çarşı"

    liste = (await client.get("/favorites", headers=h)).json()
    assert [f["place_id"] for f in liste] == ["ChIJ-abc_1"]

    assert (await client.delete("/favorites/ChIJ-abc_1", headers=h)).status_code == 204
    assert (await client.get("/favorites", headers=h)).json() == []
    assert (await client.delete("/favorites/ChIJ-abc_1", headers=h)).status_code == 404


async def test_ayni_mekani_tekrar_favorilemek_hata_vermez(client):
    h = await _giris(client)
    ilk = await client.post("/favorites", json=PLACE, headers=h)
    ikinci = await client.post("/favorites", json=PLACE, headers=h)
    assert (ilk.status_code, ikinci.status_code) == (201, 200)
    assert ilk.json()["id"] == ikinci.json()["id"]
    assert len((await client.get("/favorites", headers=h)).json()) == 1


async def test_favoriler_kullaniciya_ozeldir(client):
    ada = await _giris(client, "ada@example.com")
    can = await _giris(client, "can@example.com")
    await client.post("/favorites", json=PLACE, headers=ada)
    assert (await client.get("/favorites", headers=can)).json() == []
    # Can'ın aynı mekanı favorilemesi Ada'nın kaydıyla çakışmaz.
    assert (await client.post("/favorites", json=PLACE, headers=can)).status_code == 201
    # Can kendi favorisini silince Ada'nınki durur.
    await client.delete("/favorites/ChIJ-abc_1", headers=can)
    assert len((await client.get("/favorites", headers=ada)).json()) == 1


async def test_favori_sayisi_siniri(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_favorites_per_user", 2)
    h = await _giris(client)
    for n in range(2):
        assert (await client.post("/favorites", json=_yer(n), headers=h)).status_code == 201
    assert (await client.post("/favorites", json=_yer(9), headers=h)).status_code == 409
    # Zaten favori olan mekanı yeniden eklemek sınıra takılmaz.
    assert (await client.post("/favorites", json=_yer(0), headers=h)).status_code == 200


@pytest.mark.parametrize(
    "override",
    [
        {"place_id": ""},
        {"name": "x" * 201},
        {"latitude": 91},
        {"longitude": -181},
        {"rating": 6},
        {"user_rating_count": -1},
        {"types": ["a"] * 11},
    ],
)
async def test_gecersiz_mekan_reddedilir(client, override):
    h = await _giris(client)
    govde = {**PLACE, **override}
    assert (await client.post("/favorites", json=govde, headers=h)).status_code == 422
    assert (await client.post("/visits", json=govde, headers=h)).status_code == 422


# --- Ziyaretler ---


async def test_ziyaret_sayaci_artar_ve_sik_gidilenler_siralanir(client):
    h = await _giris(client)
    for n in (1, 2, 2, 3, 3, 3):
        assert (await client.post("/visits", json=_yer(n), headers=h)).status_code == 204

    liste = (await client.get("/visits", headers=h)).json()
    assert [(p["place_id"], p["visit_count"]) for p in liste] == [
        ("yer-3", 3),
        ("yer-2", 2),
        ("yer-1", 1),
    ]
    assert (await client.get("/visits?limit=2", headers=h)).json()[0]["place_id"] == "yer-3"
    assert len((await client.get("/visits?limit=2", headers=h)).json()) == 2


async def test_ziyarette_mekan_bilgisi_tazelenir(client):
    h = await _giris(client)
    await client.post("/visits", json=PLACE, headers=h)
    await client.post("/visits", json={**PLACE, "name": "Yeni Ad"}, headers=h)
    (kayit,) = (await client.get("/visits", headers=h)).json()
    assert (kayit["name"], kayit["visit_count"]) == ("Yeni Ad", 2)


async def test_ziyaretler_kullaniciya_ozeldir(client):
    ada = await _giris(client, "ada@example.com")
    can = await _giris(client, "can@example.com")
    await client.post("/visits", json=PLACE, headers=ada)
    assert (await client.get("/visits", headers=can)).json() == []


async def test_limit_sinirlari(client):
    h = await _giris(client)
    assert (await client.get("/visits?limit=0", headers=h)).status_code == 422
    assert (await client.get("/visits?limit=51", headers=h)).status_code == 422


async def test_tek_ziyaret_silinir(client):
    h = await _giris(client)
    await client.post("/visits", json=_yer(1), headers=h)
    await client.post("/visits", json=_yer(2), headers=h)
    assert (await client.delete("/visits/yer-1", headers=h)).status_code == 204
    assert (await client.delete("/visits/yer-1", headers=h)).status_code == 404
    assert [p["place_id"] for p in (await client.get("/visits", headers=h)).json()] == ["yer-2"]


async def test_gecmis_temizlenir_ve_sadece_kendi_gecmisi(client):
    ada = await _giris(client, "ada@example.com")
    can = await _giris(client, "can@example.com")
    await client.post("/visits", json=_yer(1), headers=ada)
    await client.post("/visits", json=_yer(1), headers=can)

    assert (await client.delete("/visits", headers=ada)).status_code == 204
    assert (await client.get("/visits", headers=ada)).json() == []
    assert len((await client.get("/visits", headers=can)).json()) == 1  # Can'ınki durur


async def test_ziyaret_mekan_sayisi_siniri(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_visited_places_per_user", 2)
    h = await _giris(client)
    for n in range(2):
        assert (await client.post("/visits", json=_yer(n), headers=h)).status_code == 204
    assert (await client.post("/visits", json=_yer(9), headers=h)).status_code == 409
    # Mevcut mekanın sayacını artırmak sınıra takılmaz.
    assert (await client.post("/visits", json=_yer(0), headers=h)).status_code == 204
