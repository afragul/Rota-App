import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from app.core.config import get_settings
from app.schemas.plan import ClarificationNeeded
from app.services import usage

PLAN_BODY = {
    "latitude": 40.19,
    "longitude": 29.06,
    "duration_hours": 4,
    "budget": "medium",
    "group_type": "friends",
}
LEGS_BODY = {
    "stops": [
        {"order": 1, "latitude": 40.0, "longitude": 29.0},
        {"order": 2, "latitude": 40.1, "longitude": 29.1},
    ],
    "travel_mode": "WALK",
}


@pytest.fixture(autouse=True)
def _dis_servisler_sahte(monkeypatch):
    """Google/Groq'a gitmeyelim: yalnızca kota davranışı sınanıyor."""
    monkeypatch.setattr(
        "app.api.routes.plan.build_day_plan",
        AsyncMock(return_value=ClarificationNeeded(question="Kaç kişisiniz?")),
    )
    monkeypatch.setattr("app.api.routes.route.get_route_legs", AsyncMock(return_value=[]))


async def _giris(client, email: str = "ada@example.com") -> dict:
    kayit = {"email": email, "username": email.split("@")[0], "password": "uzun-bir-sifre-1"}
    r = await client.post("/auth/register", json=kayit)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_plan_limiti_dolunca_429_verir(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "user_daily_plan_limit", 2)
    h = await _giris(client)
    for _ in range(2):
        assert (await client.post("/plan", json=PLAN_BODY, headers=h)).status_code == 200

    r = await client.post("/plan", json=PLAN_BODY, headers=h)
    assert r.status_code == 429
    assert "Günlük" in r.json()["detail"]
    assert r.headers["X-User-Limit-Reached"] == "1"
    # Misafir başlığı OLMAMALI: frontend onu "giriş yap" ekranına yönlendirir.
    assert "X-Guest-Limit-Reached" not in r.headers


async def test_limit_kullanici_basina_ayridir(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "user_daily_plan_limit", 1)
    ada = await _giris(client, "ada@example.com")
    can = await _giris(client, "can@example.com")
    assert (await client.post("/plan", json=PLAN_BODY, headers=ada)).status_code == 200
    assert (await client.post("/plan", json=PLAN_BODY, headers=ada)).status_code == 429
    assert (await client.post("/plan", json=PLAN_BODY, headers=can)).status_code == 200


async def test_plan_ve_legs_sayaclari_birbirinden_bagimsiz(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "user_daily_plan_limit", 1)
    monkeypatch.setattr(get_settings(), "user_daily_legs_limit", 2)
    h = await _giris(client)
    assert (await client.post("/plan", json=PLAN_BODY, headers=h)).status_code == 200
    assert (await client.post("/plan", json=PLAN_BODY, headers=h)).status_code == 429
    # Plan kotası dolsa da durak düzenleme (legs) kendi kotasından devam eder.
    assert (await client.post("/route/legs", json=LEGS_BODY, headers=h)).status_code == 200
    assert (await client.post("/route/legs", json=LEGS_BODY, headers=h)).status_code == 200
    assert (await client.post("/route/legs", json=LEGS_BODY, headers=h)).status_code == 429


async def test_ertesi_gun_kota_sifirlanir(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "user_daily_plan_limit", 1)
    h = await _giris(client)
    assert (await client.post("/plan", json=PLAN_BODY, headers=h)).status_code == 200
    assert (await client.post("/plan", json=PLAN_BODY, headers=h)).status_code == 429

    yarin = usage.today() + timedelta(days=1)
    monkeypatch.setattr(usage, "today", lambda: yarin)
    assert (await client.post("/plan", json=PLAN_BODY, headers=h)).status_code == 200


async def test_misafir_bu_kotadan_etkilenmez(client, monkeypatch):
    # Kullanıcı kotası 0 olsa bile misafir kendi (IP bazlı) kotasıyla çalışır.
    monkeypatch.setattr(get_settings(), "user_daily_plan_limit", 0)
    assert (await client.post("/plan", json=PLAN_BODY)).status_code == 200


async def test_limit_sifir_ise_giris_yapmis_kullanici_reddedilir(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "user_daily_plan_limit", 0)
    h = await _giris(client)
    assert (await client.post("/plan", json=PLAN_BODY, headers=h)).status_code == 429


async def test_eszamanli_istekler_limiti_asamaz(tmp_path):
    """Her eşzamanlı istek kendi bağlantısını kullanmalı; `client` fixture'ındaki tek
    paylaşımlı bağlantı (StaticPool) oturumların birbirinin rollback'ini bozardı. Bu yüzden
    dosya tabanlı SQLite ve servis seviyesinde. Gerçek Postgres'te de 25 eşzamanlı oturumla
    denendi (tam 5 izin, 0 hata) — bkz. ROADMAP."""
    import uuid

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.db.base import Base
    from app.db.models import User

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db", poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    async with factory() as session:
        session.add(User(id=user_id, email="a@b.com", username="ada", password_hash="x"))
        await session.commit()

    async def tek_istek() -> bool:
        async with factory() as session:
            return await usage.consume(session, user_id, "plans", 5)

    # İlk tur günün İLK çağrılarını da içerir (satır yok -> eşzamanlı ekleme yarışı).
    sonuc = await asyncio.gather(*(tek_istek() for _ in range(15)))
    await engine.dispose()
    assert sonuc.count(True) == 5
    assert sonuc.count(False) == 10


async def test_silinmis_hesabin_tokeni_401_verir(client):
    h = await _giris(client)
    await client.request("DELETE", "/me", json={"password": "uzun-bir-sifre-1"}, headers=h)
    assert (await client.post("/plan", json=PLAN_BODY, headers=h)).status_code == 401
    assert (await client.post("/route/legs", json=LEGS_BODY, headers=h)).status_code == 401


async def test_hesap_silinince_sayac_satirlari_da_gider(client):
    from sqlalchemy import func, select

    from app.db.models import DailyUsage

    h = await _giris(client)
    await client.post("/plan", json=PLAN_BODY, headers=h)
    async with client.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(DailyUsage)) == 1
    await client.request("DELETE", "/me", json={"password": "uzun-bir-sifre-1"}, headers=h)
    async with client.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(DailyUsage)) == 0
