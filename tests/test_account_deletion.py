from sqlalchemy import func, select

from app.db.models import FavoritePlace, RefreshToken, SavedPlan, User, VisitedPlace

SIFRE = "uzun-bir-sifre-1"
COOKIE = "rota_refresh"
PLACE = {
    "place_id": "yer-1",
    "name": "Kapalı Çarşı",
    "latitude": 40.19,
    "longitude": 29.06,
    "types": [],
}
PLAN = {
    "theme": "Tarihi",
    "title": "Tur",
    "summary": "s",
    "stops": [
        {
            "place_id": "yer-1",
            "order": 1,
            "arrival_time": "10:00",
            "duration_minutes": 60,
            "activity": "a",
            "recommendation": "r",
            "estimated_cost": 10,
        }
    ],
}


async def _hesap(client, email: str) -> dict:
    """Kayıt olur, her tablodan bir satır oluşturur. Authorization başlığını döndürür."""
    kayit = {"email": email, "username": email.split("@")[0], "password": SIFRE}
    r = await client.post("/auth/register", json=kayit)
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.post("/plans", json=PLAN, headers=h)).status_code == 201
    assert (await client.post("/favorites", json=PLACE, headers=h)).status_code == 201
    assert (await client.post("/visits", json=PLACE, headers=h)).status_code == 204
    return h


async def _sayilar(client) -> dict[str, int]:
    async with client.session_factory() as session:
        return {
            model.__tablename__: await session.scalar(select(func.count()).select_from(model))
            for model in (User, RefreshToken, SavedPlan, FavoritePlace, VisitedPlace)
        }


async def test_hesap_silinince_tum_verisi_gider(client):
    h = await _hesap(client, "ada@example.com")
    assert all(n == 1 for n in (await _sayilar(client)).values())

    r = await client.request("DELETE", "/me", json={"password": SIFRE}, headers=h)
    assert r.status_code == 204
    assert (await _sayilar(client)) == {
        "users": 0,
        "refresh_tokens": 0,
        "saved_plans": 0,
        "favorite_places": 0,
        "visited_places": 0,
    }


async def test_baskasinin_verisi_silinmez(client):
    ada = await _hesap(client, "ada@example.com")
    await _hesap(client, "can@example.com")

    await client.request("DELETE", "/me", json={"password": SIFRE}, headers=ada)
    assert all(n == 1 for n in (await _sayilar(client)).values())  # Can'ın her şeyi duruyor


async def test_yanlis_sifreyle_silinmez(client):
    h = await _hesap(client, "ada@example.com")
    r = await client.request("DELETE", "/me", json={"password": "yanlis-sifre"}, headers=h)
    assert r.status_code == 400  # 401 değil: istemci 401'de oturumu düşürür
    assert all(n == 1 for n in (await _sayilar(client)).values())


async def test_giris_yapmadan_ve_sifresiz_silinemez(client):
    h = await _hesap(client, "ada@example.com")
    assert (await client.request("DELETE", "/me", json={"password": SIFRE})).status_code == 401
    assert (await client.request("DELETE", "/me", headers=h)).status_code == 422
    bos = await client.request("DELETE", "/me", json={"password": ""}, headers=h)
    assert bos.status_code == 422
    assert (await _sayilar(client))["users"] == 1


async def test_silinen_hesap_artik_giris_yenileme_ve_erisim_yapamaz(client):
    h = await _hesap(client, "ada@example.com")
    ham = client.cookies.get(COOKIE)
    await client.request("DELETE", "/me", json={"password": SIFRE}, headers=h)

    giris = await client.post("/auth/login", json={"email": "ada@example.com", "password": SIFRE})
    assert giris.status_code == 401
    client.cookies.clear()
    yenile = await client.post("/auth/refresh", headers={"cookie": f"{COOKIE}={ham}"})
    assert yenile.status_code == 401

    # Erişim token'ı süresi dolmadan da kullanılamaz (hesap yok) — 500 değil 401.
    for yol in ("/me", "/plans", "/favorites", "/visits"):
        assert (await client.get(yol, headers=h)).status_code == 401, yol
    assert (await client.post("/plans", json=PLAN, headers=h)).status_code == 401
    assert (await client.post("/favorites", json=PLACE, headers=h)).status_code == 401
    assert (await client.post("/visits", json=PLACE, headers=h)).status_code == 401


async def test_silinen_planin_paylasim_linki_olur(client):
    h = await _hesap(client, "ada@example.com")
    plan_id = (await client.get("/plans", headers=h)).json()[0]["id"]
    assert (await client.get(f"/shared/{plan_id}")).status_code == 200

    await client.request("DELETE", "/me", json={"password": SIFRE}, headers=h)
    assert (await client.get(f"/shared/{plan_id}")).status_code == 404


async def test_silme_refresh_cookie_sini_temizler(client):
    h = await _hesap(client, "ada@example.com")
    r = await client.request("DELETE", "/me", json={"password": SIFRE}, headers=h)
    assert COOKIE in r.headers["set-cookie"]
    assert "max-age=0" in r.headers["set-cookie"].lower()


async def test_ayni_eposta_ve_kullanici_adiyla_yeniden_kayit_olunabilir(client):
    h = await _hesap(client, "ada@example.com")
    await client.request("DELETE", "/me", json={"password": SIFRE}, headers=h)

    r = await client.post(
        "/auth/register", json={"email": "ada@example.com", "username": "ada", "password": SIFRE}
    )
    assert r.status_code == 201
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # Yeni hesap boş başlar: eski verinin hiçbiri geri gelmez.
    assert (await client.get("/plans", headers=h2)).json() == []
    assert (await client.get("/favorites", headers=h2)).json() == []
