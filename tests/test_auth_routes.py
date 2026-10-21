import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.auth import get_optional_user_id
from app.db.base import Base
from app.db.models import User
from app.db.session import get_session
from app.main import app

REGISTER = {"email": "Ada@Example.com", "username": "ada", "password": "uzun-bir-sifre-1"}


@pytest.fixture
async def client():
    """Bellekte SQLite ile çalışan istemci; gerçek Postgres gerekmez."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        c.session_factory = factory
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


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
