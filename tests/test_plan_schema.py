import pytest
from pydantic import ValidationError

from app.schemas.plan import AnchorPlace, PlanRequest


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
    ):
        with pytest.raises(ValidationError):
            AnchorPlace(**{**base, **kwargs})


def test_bos_veya_bosluk_city_reddedilir():
    """Koordinat yokken city yalnızca boşluktan oluşuyorsa konum verilmemiş sayılır."""
    with pytest.raises(ValidationError):
        PlanRequest(city="   ")
