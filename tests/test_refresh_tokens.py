from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.auth import get_optional_user_id
from app.core.config import get_settings
from app.db.models import RefreshToken

COOKIE = "bugunluk_refresh"
KAYIT = {"email": "ada@example.com", "username": "ada", "password": "uzun-bir-sifre-1"}


async def _yenile(client, ham: str):
    """Verilen ham token'la /auth/refresh çağırır. Cookie başlık olarak AÇIKÇA gönderilir:
    httpx'in cookie kavanozu "test" gibi noktasız host'a cookie göndermez, bu da
    "token reddedildi" testlerini cookie hiç gitmediği için yanlışlıkla geçirirdi."""
    client.cookies.clear()
    return await client.post("/auth/refresh", headers={"cookie": f"{COOKIE}={ham}"})


async def _giris(client) -> dict:
    r = await client.post("/auth/register", json=KAYIT)
    assert r.status_code == 201
    return r.json()


async def test_giriste_refresh_cookie_guvenli_ozelliklerle_verilir(client):
    r = await client.post("/auth/register", json=KAYIT)
    cookie = r.headers["set-cookie"].lower()
    assert f"{COOKIE}=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/" in cookie
    assert "max-age=" in cookie
    # Ham token yanıt gövdesinde dönmez, yalnızca cookie'de.
    assert client.cookies.get(COOKIE) not in r.text


async def test_refresh_yeni_erisim_tokeni_verir_ve_cookie_doner(client):
    ilk = await _giris(client)
    eski_cookie = client.cookies.get(COOKIE)

    r = await client.post("/auth/refresh")
    assert r.status_code == 200
    assert r.json()["user"]["id"] == ilk["user"]["id"]
    assert await get_optional_user_id(f"Bearer {r.json()['access_token']}") == ilk["user"]["id"]
    assert client.cookies.get(COOKIE) != eski_cookie  # her yenilemede dönüşür


async def test_cookie_yoksa_refresh_reddedilir(client):
    r = await client.post("/auth/refresh")
    assert r.status_code == 401


async def test_bilinmeyen_token_reddedilir(client):
    assert (await _yenile(client, "uydurma-token")).status_code == 401


async def test_token_veritabaninda_ozet_olarak_saklanir(client):
    await _giris(client)
    ham = client.cookies.get(COOKIE)
    async with client.session_factory() as session:
        satir = await session.scalar(select(RefreshToken))
    assert satir.token_hash != ham
    assert len(satir.token_hash) == 64  # SHA-256 hex


async def test_eski_token_hemen_tekrar_gelirse_aile_kapanmaz(client):
    # İki sekmenin aynı anda yenilemesi: ikinci istek reddedilir ama oturum yaşamaya devam eder.
    await _giris(client)
    eski = client.cookies.get(COOKIE)
    assert (await client.post("/auth/refresh")).status_code == 200
    yeni = client.cookies.get(COOKIE)

    assert (await _yenile(client, eski)).status_code == 401

    assert (await _yenile(client, yeni)).status_code == 200


async def test_calinti_token_sure_disi_tekrar_gelirse_tum_aile_kapanir(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", 0)
    await _giris(client)
    eski = client.cookies.get(COOKIE)
    assert (await client.post("/auth/refresh")).status_code == 200
    yeni = client.cookies.get(COOKIE)

    # Saldırgan eski token'ı kullanır: reddedilir ve zincir kapanır...
    assert (await _yenile(client, eski)).status_code == 401
    # ...meşru kullanıcının yeni token'ı da artık geçersiz.
    assert (await _yenile(client, yeni)).status_code == 401


async def test_suresi_dolmus_token_reddedilir(client):
    await _giris(client)
    async with client.session_factory() as session:
        await session.execute(
            update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    assert (await client.post("/auth/refresh")).status_code == 401


async def test_basarisiz_refresh_cookie_yi_siler(client):
    r = await _yenile(client, "uydurma")
    assert COOKIE in r.headers["set-cookie"]
    assert "max-age=0" in r.headers["set-cookie"].lower()


async def test_cikis_refresh_tokeni_iptal_eder(client):
    await _giris(client)
    ham = client.cookies.get(COOKIE)
    assert (await client.post("/auth/logout")).status_code == 204

    assert (await _yenile(client, ham)).status_code == 401  # çalınmış kopya


async def test_cookie_olmadan_cikis_hata_vermez(client):
    assert (await client.post("/auth/logout")).status_code == 204


async def test_sifre_degisince_diger_oturumlar_kapanir_bu_oturum_surer(client):
    ilk = await _giris(client)
    diger_cihaz = client.cookies.get(COOKIE)

    # Bu cihaz: ayrı bir oturum açıp şifreyi değiştirir.
    client.cookies.clear()
    giris = await client.post(
        "/auth/login", json={"email": KAYIT["email"], "password": KAYIT["password"]}
    )
    h = {"Authorization": f"Bearer {giris.json()['access_token']}"}
    r = await client.post(
        "/me/password",
        json={"current_password": KAYIT["password"], "new_password": "yepyeni-sifre-9"},
        headers=h,
    )
    assert r.status_code == 204
    assert COOKIE in r.headers["set-cookie"]

    assert (await client.post("/auth/refresh")).status_code == 200  # bu cihaz devam eder
    assert (await _yenile(client, diger_cihaz)).status_code == 401  # eski oturum kapandı
    assert ilk["user"]["id"]  # (kayıt başarılıydı)
