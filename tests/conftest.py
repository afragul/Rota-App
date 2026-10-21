import os

# Testler gerçek .env'e ve gerçek key'lere bağımlı olmasın: ortam değişkenleri
# .env'den önceliklidir, bu yüzden Settings ilk kez oluşturulmadan önce sahte
# değerler tanımlanır (setdefault: gerçek ortam değişkeni varsa ona dokunmaz).
for _name in ("PLACES_API_KEY", "GEOCODING_API_KEY", "ROUTES_API_KEY", "GROQ_API_KEY"):
    os.environ.setdefault(_name, f"test-{_name.lower()}")

os.environ.setdefault("JWT_SECRET", "test-jwt-secret-en-az-32-karakter-uzunlugunda")

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
