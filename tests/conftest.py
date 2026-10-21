import os

# Testler gerçek .env'e ve gerçek key'lere bağımlı olmasın: ortam değişkenleri
# .env'den önceliklidir, bu yüzden Settings ilk kez oluşturulmadan önce sahte
# değerler tanımlanır (setdefault: gerçek ortam değişkeni varsa ona dokunmaz).
for _name in ("PLACES_API_KEY", "GEOCODING_API_KEY", "ROUTES_API_KEY", "GROQ_API_KEY"):
    os.environ.setdefault(_name, f"test-{_name.lower()}")

os.environ.setdefault("JWT_SECRET", "test-jwt-secret-en-az-32-karakter-uzunlugunda")

# Testlerde cookie http://test üzerinden ve "/" yoluyla gider (prod: Secure, /api/auth).
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("REFRESH_COOKIE_PATH", "/")

# Testler, aynı app singleton'ını (TestClient) tekrar tekrar çağırabilir;
# IP bazlı rate limiting testlerde kapalı olmalı, aksi halde test sayısı
# arttıkça flaky 429'lar görülebilir (bkz. app/core/rate_limit.py).
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402


class FakeGroq:
    """AsyncGroq yerine geçer; çağrı argümanlarını kaydeder.

    `responses` sırayla tüketilir (son eleman tekrarlanır). Eleman Exception ise
    fırlatılır, str ise mesaj içeriği olarak döner (None -> boş yanıt).
    """

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        if isinstance(item, Exception):
            raise item
        message = SimpleNamespace(content=item)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def fake_groq(monkeypatch):
    """`fake_groq("yanıt1", "yanıt2")` planner'daki Groq istemcisini sahteyle değiştirir."""

    def install(*responses) -> FakeGroq:
        fake = FakeGroq(list(responses))
        monkeypatch.setattr("app.services.planner.AsyncGroq", lambda **_: fake)
        return fake

    return install


@pytest.fixture
async def client():
    """Bellekte SQLite ile çalışan HTTP istemcisi; gerçek Postgres gerekmez."""
    import httpx
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base
    from app.db.session import get_session
    from app.main import app

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
