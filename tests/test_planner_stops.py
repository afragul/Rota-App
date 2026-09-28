import pytest

from app.schemas.places import Place
from app.schemas.plan import DayPlan, PlanAlternative, PlanStop
from app.services.planner import PlannerServiceError, _validate_and_enrich_stops

PLACE = Place(
    place_id="p1",
    name="Kitap Kahve",
    address="Osmangazi, Bursa",
    latitude=40.1885,
    longitude=29.0610,
    rating=4.6,
    user_rating_count=312,
    types=["cafe"],
)


def _stop(place_id: str) -> PlanStop:
    return PlanStop(
        place_id=place_id,
        order=1,
        arrival_time="14:00",
        duration_minutes=60,
        activity="Kahve içmek",
        recommendation="Filtre kahve dene",
        estimated_cost=100,
    )


def _plan(*stops: PlanStop) -> DayPlan:
    return DayPlan(
        alternatives=[
            PlanAlternative(
                theme="kafe", title="Kafe Turu", summary="Sakin bir mola", stops=list(stops)
            )
        ]
    )


def test_gecerli_durak_mekan_bilgisiyle_zenginlestirilir():
    plan = _plan(_stop("p1"))

    result = _validate_and_enrich_stops(plan, [PLACE])

    stop = result.alternatives[0].stops[0]
    assert stop.name == "Kitap Kahve"
    assert stop.latitude == 40.1885
    assert stop.longitude == 29.0610


def test_uydurma_place_id_elenir():
    plan = _plan(_stop("p1"), _stop("uydurma-id"))

    result = _validate_and_enrich_stops(plan, [PLACE])

    stops = result.alternatives[0].stops
    assert len(stops) == 1
    assert stops[0].place_id == "p1"


def test_tum_duraklar_uydurmaysa_hata_firlatilir():
    plan = _plan(_stop("uydurma-id"))

    with pytest.raises(PlannerServiceError):
        _validate_and_enrich_stops(plan, [PLACE])
