import httpx
import respx
from fastapi.testclient import TestClient

from app.core import guest_limit
from app.core.config import get_settings
from app.main import app

BODY = {
    "origin_latitude": 40.0,
    "origin_longitude": 29.0,
    "destination_latitude": 40.1,
    "destination_longitude": 29.1,
    "travel_mode": "WALK",
}

LEGS_BODY = {
    "stops": [
        {"order": 1, "latitude": 40.0, "longitude": 29.0},
        {"order": 2, "latitude": 40.1, "longitude": 29.1},
    ],
    "travel_mode": "WALK",
}

_LEGS_ROUTES_RESPONSE = httpx.Response(
    200,
    json={
        "routes": [
            {
                "legs": [
                    {
                        "distanceMeters": 500,
                        "duration": "300s",
                        "polyline": {"encodedPolyline": "xyz"},
                    }
                ]
            }
        ]
    },
)


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


def test_legs_endpoint_fazla_durak_422():
    """MAX_LEG_STOPS (12) üzerindeki durak sayısı Routes çağrısına gitmeden reddedilmeli."""
    too_many = {
        "stops": [{"order": i, "latitude": 40.0, "longitude": 29.0} for i in range(1, 14)],
        "travel_mode": "WALK",
    }
    response = TestClient(app).post("/route/legs", json=too_many)
    assert response.status_code == 422


@respx.mock
def test_legs_endpoint_misafir_kota_asilinca_429():
    """Günlük misafir /route/legs kotası dolunca 429 + X-Guest-Limit-Reached döner."""
    guest_limit._legs_counts.clear()
    respx.post(get_settings().google_routes_base_url).mock(return_value=_LEGS_ROUTES_RESPONSE)
    client = TestClient(app)
    limit = get_settings().guest_daily_legs_limit

    for _ in range(limit):
        assert client.post("/route/legs", json=LEGS_BODY).status_code == 200

    response = client.post("/route/legs", json=LEGS_BODY)

    assert response.status_code == 429
    assert response.headers.get("X-Guest-Limit-Reached") == "1"
    guest_limit._legs_counts.clear()
