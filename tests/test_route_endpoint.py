import httpx
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

BODY = {
    "origin_latitude": 40.0,
    "origin_longitude": 29.0,
    "destination_latitude": 40.1,
    "destination_longitude": 29.1,
    "travel_mode": "WALK",
}


@respx.mock
def test_approach_endpoint_basarili():
    respx.post(get_settings().google_routes_base_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "legs": [
                            {
                                "distanceMeters": 800,
                                "duration": "600s",
                                "polyline": {"encodedPolyline": "abc"},
                            }
                        ]
                    }
                ]
            },
        )
    )

    response = TestClient(app).post("/route/approach", json=BODY)

    assert response.status_code == 200
    assert response.json() == {
        "travel_mode": "WALK",
        "distance_meters": 800,
        "duration_minutes": 10,
        "polyline": "abc",
        "steps": [],
    }


@respx.mock
def test_approach_endpoint_rota_yoksa_502():
    respx.post(get_settings().google_routes_base_url).mock(
        return_value=httpx.Response(200, json={"routes": []})
    )

    response = TestClient(app).post("/route/approach", json=BODY)

    assert response.status_code == 502


def test_approach_endpoint_eksik_alan_422():
    assert TestClient(app).post("/route/approach", json={"origin_latitude": 1}).status_code == 422
