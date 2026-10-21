import pytest
from sqlalchemy import select

from app.core.auth import get_optional_user_id
from app.db.models import User

REGISTER = {"email": "Ada@Example.com", "username": "ada", "password": "uzun-bir-sifre-1"}


async def test_kayit_token_ve_kullanici_doner(client):
    r = await client.post("/auth/register", json=REGISTER)
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "ada@example.com"  # küçük harfe çevrildi
    assert "password" not in str(body)
    assert await get_optional_user_id(f"Bearer {body['access_token']}") == body["user"]["id"]


async def test_sifre_duz_metin_saklanmaz(client):
    await client.post("/auth/register", json=REGISTER)
    async with client.session_factory() as session:
        user = await session.scalar(select(User))
    assert user.password_hash.startswith("$argon2")
    assert REGISTER["password"] not in user.password_hash


async def test_ayni_eposta_buyuk_kucuk_harf_farkiyla_tekrar_kayit_olmaz(client):
    await client.post("/auth/register", json=REGISTER)
    r = await client.post("/auth/register", json={**REGISTER, "email": "ADA@example.COM"})
    assert r.status_code == 409


@pytest.mark.parametrize(
    "override",
    [
        {"email": "gecersiz"},
        {"password": "kisa"},
        {"password": "x" * 129},
        {"username": " a "},
        {"username": "x" * 51},
    ],
)
async def test_gecersiz_kayit_girdisi_reddedilir(client, override):
    r = await client.post("/auth/register", json={**REGISTER, **override})
    assert r.status_code == 422


async def test_dogru_bilgilerle_giris_yapilir(client):
    await client.post("/auth/register", json=REGISTER)
    r = await client.post(
        "/auth/login", json={"email": "ADA@example.com", "password": REGISTER["password"]}
    )
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "ada"


async def test_yanlis_sifre_ve_olmayan_kullanici_ayni_hatayi_verir(client):
    await client.post("/auth/register", json=REGISTER)
    yanlis = await client.post(
        "/auth/login", json={"email": REGISTER["email"], "password": "yanlis-sifre"}
    )
    yok = await client.post(
        "/auth/login", json={"email": "yok@example.com", "password": "yanlis-sifre"}
    )
    assert yanlis.status_code == yok.status_code == 401
    assert yanlis.json() == yok.json()


# --- Kullanıcı adı benzersizliği, /me ---


async def _giris(client, email="ada@example.com", username="ada") -> dict:
    body = {"email": email, "username": username, "password": REGISTER["password"]}
    r = await client.post("/auth/register", json=body)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_kullanici_adi_buyuk_kucuk_harf_duyarsiz_benzersiz(client):
    await _giris(client, "ada@example.com", "Ada")
    r = await client.post(
        "/auth/register",
        json={"email": "baska@example.com", "username": "ADA", "password": REGISTER["password"]},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "Bu kullanıcı adı alınmış"


async def test_me_profili_doner_giris_gerekir(client):
    assert (await client.get("/me")).status_code == 401
    h = await _giris(client)
    r = await client.get("/me", headers=h)
    assert r.status_code == 200
    assert r.json()["username"] == "ada"
    assert "password" not in str(r.json())


async def test_kullanici_adi_degistirilir(client):
    h = await _giris(client)
    r = await client.patch("/me", json={"username": "  yeni_ad  "}, headers=h)
    assert r.status_code == 200
    assert r.json()["username"] == "yeni_ad"  # boşluklar kırpıldı
    assert (await client.get("/me", headers=h)).json()["username"] == "yeni_ad"


async def test_kullanici_adi_baskasinda_ise_degistirilemez_kendi_adi_olur(client):
    h = await _giris(client, "ada@example.com", "ada")
    await _giris(client, "can@example.com", "can")
    assert (await client.patch("/me", json={"username": "CAN"}, headers=h)).status_code == 409
    # Kendi adının büyük/küçük harfini değiştirmek çakışma sayılmaz.
    assert (await client.patch("/me", json={"username": "ADA"}, headers=h)).status_code == 200


async def test_sifre_degistirilir_eskisiyle_giris_artik_olmaz(client):
    h = await _giris(client)
    r = await client.post(
        "/me/password",
        json={"current_password": REGISTER["password"], "new_password": "yepyeni-sifre-9"},
        headers=h,
    )
    assert r.status_code == 204
    eski = await client.post(
        "/auth/login", json={"email": "ada@example.com", "password": REGISTER["password"]}
    )
    yeni = await client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "yepyeni-sifre-9"}
    )
    assert (eski.status_code, yeni.status_code) == (401, 200)


async def test_sifre_degistirirken_mevcut_sifre_yanlissa_reddedilir(client):
    h = await _giris(client)
    r = await client.post(
        "/me/password",
        json={"current_password": "yanlis-sifre", "new_password": "yepyeni-sifre-9"},
        headers=h,
    )
    assert r.status_code == 400
    ok = await client.post(
        "/auth/login", json={"email": "ada@example.com", "password": REGISTER["password"]}
    )
    assert ok.status_code == 200  # şifre değişmedi


async def test_yeni_sifre_cok_kisaysa_reddedilir(client):
    h = await _giris(client)
    r = await client.post(
        "/me/password",
        json={"current_password": REGISTER["password"], "new_password": "kisa"},
        headers=h,
    )
    assert r.status_code == 422
