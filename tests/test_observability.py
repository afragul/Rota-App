from app.core.audit import audit
from app.core.auth import get_optional_user_id


async def test_yanitta_istek_numarasi_var(client):
    r = await client.get("/health")

    assert r.status_code == 200
    assert len(r.headers["x-request-id"]) == 32


async def test_gecerli_gelen_istek_numarasi_aynen_doner(client):
    r = await client.get("/health", headers={"X-Request-ID": "istemci-123456"})

    assert r.headers["x-request-id"] == "istemci-123456"


async def test_gecersiz_gelen_istek_numarasi_yenisiyle_degisir(client):
    # Log'a yazılacağı için satır sonu/boşluk içeren değer kabul edilmemeli
    r = await client.get("/health", headers={"X-Request-ID": "kisa"})

    assert r.headers["x-request-id"] != "kisa"
    assert len(r.headers["x-request-id"]) == 32


async def test_istek_numarasi_istek_icindeki_log_satirlarina_gecer():
    import httpx
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route

    from app.core.logging import request_id_var
    from app.core.request_id import RequestIdMiddleware

    gorulen = []

    async def endpoint(request):
        gorulen.append(request_id_var.get())
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(RequestIdMiddleware)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/", headers={"X-Request-ID": "istemci-123456"})

    assert gorulen == ["istemci-123456"]
    assert r.headers["x-request-id"] == "istemci-123456"


async def test_hazirlik_ucu_veritabani_varken_ok(client):
    r = await client.get("/health/ready")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_hazirlik_ucu_veritabani_yokken_503_ve_ayrinti_sizmaz(client, monkeypatch, caplog):
    class KirikEngine:
        def connect(self):
            raise ConnectionError("postgresql://rota:GIZLI-SIFRE@db/rota")

    monkeypatch.setattr("app.api.routes.health.get_engine", lambda: KirikEngine())
    with caplog.at_level("ERROR"):
        r = await client.get("/health/ready")

    assert r.status_code == 503
    assert r.json() == {"status": "unavailable"}
    assert "ConnectionError" in caplog.text
    assert "GIZLI-SIFRE" not in caplog.text


async def test_gecersiz_token_audit_loguna_yazilir_token_yazilmaz(client, caplog):
    with caplog.at_level("INFO", logger="audit"):
        r = await client.get("/me", headers={"Authorization": "Bearer GIZLI.TOKEN.DEGERI"})

    assert r.status_code == 401
    assert "geçersiz ya da süresi dolmuş" in caplog.text
    assert "/me" in caplog.text
    assert "GIZLI.TOKEN.DEGERI" not in caplog.text


async def test_token_yoksa_audit_logu_yazilmaz(caplog):
    with caplog.at_level("INFO", logger="audit"):
        assert await get_optional_user_id(None) is None

    assert caplog.text == ""


def test_audit_ip_ve_yol_yazar_satir_sonunu_temizler(caplog):
    from types import SimpleNamespace

    request = SimpleNamespace(
        client=SimpleNamespace(host="1.2.3.4"), url=SimpleNamespace(path="/plan\nERROR sahte")
    )
    with caplog.at_level("WARNING", logger="audit"):
        audit(request, "deneme olayı")

    assert "deneme olayı | ip=1.2.3.4 yol=/plan ERROR sahte" in caplog.text
    assert "\nERROR sahte" not in caplog.text


async def test_misafir_kotasi_dolunca_audit_logu_yazilir(caplog):
    from types import SimpleNamespace

    import pytest
    from fastapi import HTTPException

    from app.core import guest_limit

    guest_limit._counts.clear()
    request = SimpleNamespace(
        client=SimpleNamespace(host="9.9.9.9"), url=SimpleNamespace(path="/plan")
    )
    with caplog.at_level("WARNING", logger="audit"):
        with pytest.raises(HTTPException):
            for _ in range(1000):
                guest_limit.enforce_guest_plan_limit(request, None)
    guest_limit._counts.clear()

    assert "misafir günlük plan kotası doldu | ip=9.9.9.9 yol=/plan" in caplog.text


async def test_hiz_siniri_asilinca_audit_logu_yazilir_ve_slowapi_yaniti_doner(caplog, monkeypatch):
    from types import SimpleNamespace

    from app.core import rate_limit

    monkeypatch.setattr(rate_limit, "_rate_limit_exceeded_handler", lambda request, exc: "yanıt")
    request = SimpleNamespace(
        client=SimpleNamespace(host="5.5.5.5"), url=SimpleNamespace(path="/auth/login")
    )
    with caplog.at_level("WARNING", logger="audit"):
        sonuc = rate_limit.rate_limit_exceeded_handler(request, None)

    assert sonuc == "yanıt"
    assert "hız sınırı aşıldı | ip=5.5.5.5 yol=/auth/login" in caplog.text
