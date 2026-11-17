from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import guest_limit
from app.core.config import get_settings


def _fake_request(ip: str = "1.2.3.4"):
    return SimpleNamespace(client=SimpleNamespace(host=ip), url=SimpleNamespace(path="/plan"))


@pytest.fixture(autouse=True)
def _temiz_sayac():
    """Modül seviyesindeki global sayaçlar testler arasında sızmasın."""
    guest_limit._counts.clear()
    guest_limit._legs_counts.clear()
    yield
    guest_limit._counts.clear()
    guest_limit._legs_counts.clear()


def test_misafir_limitin_altindayken_gecer():
    request = _fake_request()
    limit = get_settings().guest_daily_plan_limit
    for _ in range(limit):
        guest_limit.enforce_guest_plan_limit(request, user_id=None)


def test_misafir_limit_asilinca_429():
    request = _fake_request()
    limit = get_settings().guest_daily_plan_limit
    for _ in range(limit):
        guest_limit.enforce_guest_plan_limit(request, user_id=None)

    with pytest.raises(HTTPException) as exc_info:
        guest_limit.enforce_guest_plan_limit(request, user_id=None)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers.get("X-Guest-Limit-Reached") == "1"


def test_giris_yapmis_kullanici_limitlenmez():
    request = _fake_request()
    limit = get_settings().guest_daily_plan_limit
    for _ in range(limit + 5):
        guest_limit.enforce_guest_plan_limit(request, user_id="user-1")


def test_farkli_ip_birbirini_etkilemez():
    limit = get_settings().guest_daily_plan_limit
    for _ in range(limit):
        guest_limit.enforce_guest_plan_limit(_fake_request("1.1.1.1"), user_id=None)

    # İkinci IP hâlâ kendi kotasını kullanabilmeli.
    guest_limit.enforce_guest_plan_limit(_fake_request("2.2.2.2"), user_id=None)


def test_legs_limitin_altindayken_gecer():
    request = _fake_request()
    limit = get_settings().guest_daily_legs_limit
    for _ in range(limit):
        guest_limit.enforce_guest_legs_limit(request, user_id=None)


def test_legs_limit_asilinca_429():
    request = _fake_request()
    limit = get_settings().guest_daily_legs_limit
    for _ in range(limit):
        guest_limit.enforce_guest_legs_limit(request, user_id=None)

    with pytest.raises(HTTPException) as exc_info:
        guest_limit.enforce_guest_legs_limit(request, user_id=None)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers.get("X-Guest-Limit-Reached") == "1"


def test_legs_limit_giris_yapmis_kullaniciya_uygulanmaz():
    request = _fake_request()
    limit = get_settings().guest_daily_legs_limit
    for _ in range(limit + 5):
        guest_limit.enforce_guest_legs_limit(request, user_id="user-1")


def test_legs_ve_plan_sayaclari_birbirinden_ayri():
    """Her iki kota da ayrı sayaçlar: biri dolunca diğeri etkilenmemeli."""
    request = _fake_request()
    plan_limit = get_settings().guest_daily_plan_limit
    for _ in range(plan_limit):
        guest_limit.enforce_guest_plan_limit(request, user_id=None)

    with pytest.raises(HTTPException):
        guest_limit.enforce_guest_plan_limit(request, user_id=None)

    # /route/legs kotası plan kotasından bağımsız, hâlâ kullanılabilir.
    guest_limit.enforce_guest_legs_limit(request, user_id=None)
