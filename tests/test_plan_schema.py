import pytest
from pydantic import ValidationError

from app.schemas.plan import PlanRequest


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
    import pytest
    from pydantic import ValidationError

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
