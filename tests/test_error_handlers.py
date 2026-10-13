"""Merkezi hata işleyicileri (app/api/errors.py): servis hatası -> 502, beklenmeyen hata -> 500."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.services.geocoding import GeocodingServiceError
from app.services.weather import WeatherServiceError


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/geo")
    async def geo():
        raise GeocodingServiceError("konum bulunamadı")

    @app.get("/weather")
    async def weather():
        raise WeatherServiceError("hava alınamadı")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("https://x.test/?key=GIZLI-ANAHTAR")

    # raise_server_exceptions=False: işleyicinin ürettiği 500 cevabını görebilelim
    return TestClient(app, raise_server_exceptions=False)


def test_servis_hatasi_502_ve_mesaj_doner(client):
    response = client.get("/geo")

    assert response.status_code == 502
    assert response.json() == {"detail": "konum bulunamadı"}


def test_her_servis_hatasi_502_olur(client):
    assert client.get("/weather").status_code == 502


def test_beklenmeyen_hata_500_ve_ayrinti_sizmaz(client, caplog):
    with caplog.at_level("ERROR"):
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Beklenmeyen bir hata oluştu"}
    assert "GIZLI-ANAHTAR" not in response.text
    # Log'da yalnızca hata türü ve yol var, mesaj (URL/key taşıyabilir) yok
    assert "RuntimeError" in caplog.text
    assert "/boom" in caplog.text
    assert "GIZLI-ANAHTAR" not in caplog.text
