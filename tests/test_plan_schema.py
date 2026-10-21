import pytest
from pydantic import ValidationError

from app.schemas.plan import AnchorPlace, LegsRequest, LegStop, PlanRequest


def test_koordinatla_gecerli():
    """latitude/longitude ikilisi tek başına yeterli olmalı."""
    request = PlanRequest(latitude=40.18, longitude=29.06)

    assert request.city is None


def test_sehirle_gecerli():
    """city tek başına yeterli olmalı, koordinat zorunlu değil."""
    request = PlanRequest(city="Bursa")

    assert request.latitude is None
    assert request.longitude is None


def test_konum_hic_verilmezse_hata():
    """Ne koordinat ne city verilirse istek reddedilmeli."""
    with pytest.raises(ValidationError):
        PlanRequest()


def test_yarim_koordinat_yetersiz():
    """Sadece latitude verilip longitude eksikse ve city de yoksa hata vermeli."""
    with pytest.raises(ValidationError):
        PlanRequest(latitude=40.18)


def test_gecersiz_girdiler_reddedilir():
    for kwargs in (
        {"duration_hours": 0},
        {"duration_hours": 100},
        {"free_text": "a" * 501},
        {"city": "a" * 201},
        {"categories": ["yok_boyle_tema"]},
        {"categories": ["kafe"] * 7},
        {"latitude": 91.0, "longitude": 0.0},
    ):
        with pytest.raises(ValidationError):
            PlanRequest(**{"city": "Bursa", **kwargs})


def test_start_time_gecerli():
    request = PlanRequest(city="Bursa", start_time="14:30")
    assert request.start_time == "14:30"


def test_start_time_verilmezse_none():
    request = PlanRequest(city="Bursa")
    assert request.start_time is None


def test_start_time_gecersiz_format_reddedilir():
    for value in ("9:00", "24:00", "14:60", "öğleden sonra", "14-30"):
        with pytest.raises(ValidationError):
            PlanRequest(city="Bursa", start_time=value)


def test_anchor_place_gecerli():
    request = PlanRequest(
        city="Bursa",
        anchor_place=AnchorPlace(
            place_id="p1", name="Favori Kafe", latitude=40.18, longitude=29.06
        ),
    )
    assert request.anchor_place is not None
    assert request.anchor_place.place_id == "p1"


def test_anchor_place_gecersiz_girdiler_reddedilir():
    base = {"place_id": "p1", "name": "Kafe", "latitude": 40.18, "longitude": 29.06}
    for kwargs in (
        {"latitude": 91.0},
        {"longitude": -181.0},
        {"name": "a" * 201},
        {"place_id": "a" * 301},
        {"address": "a" * 301},
        {"types": ["cafe"] * 11},
        {"place_id": ""},
        {"name": ""},
        {"types": ["a" * 51]},
    ):
        with pytest.raises(ValidationError):
            AnchorPlace(**{**base, **kwargs})


def test_bos_veya_bosluk_city_reddedilir():
    """Koordinat yokken city yalnızca boşluktan oluşuyorsa konum verilmemiş sayılır."""
    with pytest.raises(ValidationError):
        PlanRequest(city="   ")


def test_plan_request_tanimsiz_alan_reddedilir():
    """extra='forbid': tanımsız alan sessizce yok sayılmak yerine hata vermeli."""
    with pytest.raises(ValidationError):
        PlanRequest(city="Bursa", uydurma_alan="deger")


def test_leg_stop_order_siniri():
    for order in (0, -1, 26):
        with pytest.raises(ValidationError):
            LegStop(order=order, latitude=40.18, longitude=29.06)


def test_legs_request_tekrar_eden_order_reddedilir():
    stops = [
        LegStop(order=1, latitude=40.18, longitude=29.06),
        LegStop(order=1, latitude=40.19, longitude=29.07),
    ]
    with pytest.raises(ValidationError):
        LegsRequest(stops=stops)


def test_legs_request_benzersiz_order_gecerli():
    stops = [
        LegStop(order=1, latitude=40.18, longitude=29.06),
        LegStop(order=2, latitude=40.19, longitude=29.07),
    ]
    request = LegsRequest(stops=stops)
    assert len(request.stops) == 2
