import json

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.schemas.plan import DayPlan, PlanAlternative, PlanStop, TravelMode
from app.services.routes import RoutesServiceError, add_routes, get_approach_route, get_route_legs


def _stop(order: int, lat: float | None = 40.0, lng: float | None = 29.0) -> PlanStop:
    return PlanStop(
        place_id=f"p{order}",
        order=order,
        arrival_time="14:00",
        duration_minutes=60,
        activity="Gezmek",
        recommendation="Yürü",
        estimated_cost=0,
        name=f"Mekan {order}",
        latitude=lat,
        longitude=lng,
    )


def _leg(meters: int = 500, seconds: str = "400s", poly: str = "abc") -> dict:
    return {
        "distanceMeters": meters,
        "duration": seconds,
        "polyline": {"encodedPolyline": poly},
    }


def _url() -> str:
    return get_settings().google_routes_base_url


def _plan(*stops: PlanStop) -> DayPlan:
    return DayPlan(
        alternatives=[PlanAlternative(theme="t", title="T", summary="s", stops=list(stops))]
    )


@respx.mock
async def test_ayaklar_duraklara_baglaniyor():
    """2 ayak dönünce from/to order'lar ardışık duraklarla eşleşmeli."""
    respx.post(_url()).mock(
        return_value=httpx.Response(
            200, json={"routes": [{"legs": [_leg(500, "400s", "a"), _leg(900, "700.5s", "b")]}]}
        )
    )

    legs = await get_route_legs([_stop(1), _stop(2), _stop(3)], TravelMode.WALK)

    assert [(leg.from_order, leg.to_order) for leg in legs] == [(1, 2), (2, 3)]
    assert legs[1].distance_meters == 900
    assert legs[1].duration_minutes == 12  # "700.5s" ~ 11.7 dk -> 12
    assert legs[0].polyline == "a"
    assert legs[0].duration_minutes == 7  # "400s" ~ 6.7 dk -> 7


@respx.mock
async def test_istek_dogru_kuruluyor():
    """WALK modu, intermediates, key ve field mask gönderilmeli."""
    route = respx.post(_url()).mock(
        return_value=httpx.Response(200, json={"routes": [{"legs": [_leg(), _leg()]}]})
    )

    await get_route_legs([_stop(1), _stop(2), _stop(3)], TravelMode.WALK)

    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["travelMode"] == "WALK"
    assert len(body["intermediates"]) == 1
    assert request.headers["X-Goog-Api-Key"]
    assert "routes.legs.polyline" in request.headers["X-Goog-FieldMask"]


async def test_tek_durakta_istek_atilmaz():
    """1 durakta rota anlamsız; ağ çağrısı olmadan boş dönmeli."""
    assert await get_route_legs([_stop(1)], TravelMode.WALK) == []


@respx.mock
async def test_google_hata_dondurunce():
    respx.post(_url()).mock(return_value=httpx.Response(500, text="hata"))

    with pytest.raises(RoutesServiceError):
        await get_route_legs([_stop(1), _stop(2)], TravelMode.WALK)


@respx.mock
async def test_rota_bulunamayinca():
    """Google boş routes dönerse RoutesServiceError."""
    respx.post(_url()).mock(return_value=httpx.Response(200, json={}))

    with pytest.raises(RoutesServiceError):
        await get_route_legs([_stop(1), _stop(2)], TravelMode.WALK)


@respx.mock
async def test_add_routes_hata_plani_dusurmez():
    """Rota servisi çökse bile plan döner, legs boş kalır."""
    respx.post(_url()).mock(side_effect=httpx.ConnectError("baglanti yok"))

    plan = await add_routes(_plan(_stop(1), _stop(2)))

    assert plan.alternatives[0].legs == []
    assert plan.alternatives[0].routes_available is False
    assert len(plan.alternatives[0].stops) == 2


@respx.mock
async def test_koordinatsiz_durak_atlanir():
    """Koordinatı olmayan durak rotaya girmez; kalan iki durak bağlanır."""
    route = respx.post(_url()).mock(
        return_value=httpx.Response(200, json={"routes": [{"legs": [_leg()]}]})
    )

    plan = await add_routes(_plan(_stop(1), _stop(2, lat=None, lng=None), _stop(3)))

    assert not json.loads(route.calls.last.request.content).get("intermediates")
    legs = plan.alternatives[0].legs
    assert [(leg.from_order, leg.to_order) for leg in legs] == [(1, 3)]


@respx.mock
async def test_arac_modu_istege_ve_ayaga_yansiyor():
    """DRIVE seçilince istekte DRIVE gitmeli, ayak da bu modu taşımalı."""
    route = respx.post(_url()).mock(
        return_value=httpx.Response(200, json={"routes": [{"legs": [_leg()]}]})
    )

    legs = await get_route_legs([_stop(1), _stop(2)], TravelMode.DRIVE)

    assert json.loads(route.calls.last.request.content)["travelMode"] == "DRIVE"
    assert legs[0].travel_mode is TravelMode.DRIVE


@respx.mock
async def test_toplu_tasima_cift_basina_istek_atar():
    """TRANSIT intermediates desteklemez: 3 durak -> 2 ayrı istek, intermediates yok."""
    route = respx.post(_url()).mock(
        return_value=httpx.Response(200, json={"routes": [{"legs": [_leg()]}]})
    )

    legs = await get_route_legs([_stop(1), _stop(2), _stop(3)], TravelMode.TRANSIT)

    assert route.call_count == 2
    for call in route.calls:
        body = json.loads(call.request.content)
        assert body["travelMode"] == "TRANSIT"
        assert "intermediates" not in body
    assert [(leg.from_order, leg.to_order) for leg in legs] == [(1, 2), (2, 3)]


@respx.mock
async def test_basarili_rotada_routes_available_true(caplog):
    respx.post(_url()).mock(return_value=httpx.Response(200, json={"routes": [{"legs": [_leg()]}]}))

    plan = await add_routes(_plan(_stop(1), _stop(2)))

    assert plan.alternatives[0].routes_available is True


@respx.mock
async def test_tek_duraklik_plan_routes_available_kalir():
    """Tek durakta rota gerekmez; bu bir hata sayılmamalı."""
    plan = await add_routes(_plan(_stop(1)))

    assert plan.alternatives[0].legs == []
    assert plan.alternatives[0].routes_available is True


@respx.mock
async def test_log_google_hata_govdesini_ve_modu_icerir(caplog):
    """403 gelince log'da durum kodu, mod ve Google'ın mesajı görünmeli."""
    respx.post(_url()).mock(
        return_value=httpx.Response(403, text="Routes API has not been used in project 123")
    )

    with caplog.at_level("WARNING"):
        await add_routes(_plan(_stop(1), _stop(2)), TravelMode.TRANSIT)

    assert "403" in caplog.text
    assert "TRANSIT" in caplog.text
    assert "Routes API has not been used" in caplog.text


# --- get_approach_route (kullanıcı konumu -> ilk durak) ---


@respx.mock
async def test_approach_route_tek_ayak_doner():
    route = respx.post(_url()).mock(
        return_value=httpx.Response(200, json={"routes": [{"legs": [_leg(1200, "600s", "xyz")]}]})
    )

    result = await get_approach_route((40.0, 29.0), (40.1, 29.1), TravelMode.WALK)

    assert (result.distance_meters, result.duration_minutes, result.polyline) == (1200, 10, "xyz")
    assert result.travel_mode is TravelMode.WALK
    body = json.loads(route.calls[0].request.content)
    assert body["origin"]["location"]["latLng"] == {"latitude": 40.0, "longitude": 29.0}
    assert body["destination"]["location"]["latLng"] == {"latitude": 40.1, "longitude": 29.1}
    assert body["travelMode"] == "WALK"


@respx.mock
async def test_approach_route_google_hata_verirse():
    respx.post(_url()).mock(return_value=httpx.Response(403, text="kapalı"))

    with pytest.raises(RoutesServiceError):
        await get_approach_route((40.0, 29.0), (40.1, 29.1), TravelMode.DRIVE)


@respx.mock
async def test_approach_route_bos_sonuc():
    respx.post(_url()).mock(return_value=httpx.Response(200, json={"routes": []}))

    with pytest.raises(RoutesServiceError):
        await get_approach_route((40.0, 29.0), (40.1, 29.1), TravelMode.TRANSIT)


# --- adım adım tarif (steps) ---

_WALK_STEP = {
    "distanceMeters": 70,
    "staticDuration": "77s",
    "travelMode": "WALK",
    "navigationInstruction": {
        "maneuver": "TURN_RIGHT",
        "instructions": "Mühürdar Cd. yönünde sağa dönün",
    },
}
_TRANSIT_STEP = {
    "distanceMeters": 1348,
    "staticDuration": "138s",
    "travelMode": "TRANSIT",
    "navigationInstruction": {"instructions": "Metro Sabiha Gökçen üzerinden"},
    "transitDetails": {
        "stopDetails": {
            "departureStop": {"name": "Kadıköy"},
            "arrivalStop": {"name": "Ayrılık Çeşmesi"},
        },
        "localizedValues": {"departureTime": {"time": {"text": "14:58"}}},
        "headsign": "Sabiha Gökçen",
        "stopCount": 1,
        "transitLine": {
            "name": "Kadıköy - Tavşantepe",
            "nameShort": "M4",
            "color": "#e91e76",
            "textColor": "#ffffff",
            "vehicle": {"name": {"text": "Metro"}, "type": "SUBWAY"},
        },
    },
}


@respx.mock
async def test_approach_route_adimlari_cozer():
    leg = {**_leg(900, "800s", "xyz"), "steps": [_WALK_STEP, _TRANSIT_STEP]}
    route = respx.post(_url()).mock(
        return_value=httpx.Response(200, json={"routes": [{"legs": [leg]}]})
    )

    result = await get_approach_route((40.0, 29.0), (40.1, 29.1), TravelMode.TRANSIT)

    walk, transit = result.steps
    assert (walk.travel_mode, walk.maneuver, walk.distance_meters) == (
        TravelMode.WALK,
        "TURN_RIGHT",
        70,
    )
    assert walk.instruction == "Mühürdar Cd. yönünde sağa dönün"
    assert walk.transit is None
    assert transit.travel_mode is TravelMode.TRANSIT
    assert transit.transit.line_name == "M4"
    assert (transit.transit.vehicle, transit.transit.departure_stop) == ("Metro", "Kadıköy")
    assert (transit.transit.arrival_stop, transit.transit.stop_count) == ("Ayrılık Çeşmesi", 1)
    assert transit.transit.departure_time == "14:58"
    # Adımlar için field mask'e steps alanları istenmeli
    assert (
        "routes.legs.steps.navigationInstruction"
        in route.calls[0].request.headers["X-Goog-FieldMask"]
    )


@respx.mock
async def test_duraklar_arasi_ayaklar_da_adim_tasir():
    respx.post(_url()).mock(
        return_value=httpx.Response(
            200, json={"routes": [{"legs": [{**_leg(500, "400s", "a"), "steps": [_WALK_STEP]}]}]}
        )
    )

    legs = await get_route_legs([_stop(1), _stop(2)], TravelMode.WALK)

    assert [s.maneuver for s in legs[0].steps] == ["TURN_RIGHT"]


@respx.mock
async def test_bozuk_adim_atlanir_ayak_etkilenmez():
    """Adımlar kritik değil: biri bozuksa o atlanır, mesafe/süre/çizgi yine döner."""
    bad = {"distanceMeters": "sayı değil", "travelMode": "WALK"}
    leg = {**_leg(500, "400s", "a"), "steps": [bad, _WALK_STEP]}
    respx.post(_url()).mock(return_value=httpx.Response(200, json={"routes": [{"legs": [leg]}]}))

    result = await get_approach_route((40.0, 29.0), (40.1, 29.1), TravelMode.WALK)

    assert result.polyline == "a"
    assert len(result.steps) == 1


@respx.mock
async def test_adim_yoksa_bos_liste():
    respx.post(_url()).mock(return_value=httpx.Response(200, json={"routes": [{"legs": [_leg()]}]}))

    result = await get_approach_route((40.0, 29.0), (40.1, 29.1), TravelMode.WALK)

    assert result.steps == []
