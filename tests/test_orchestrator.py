"""build_day_plan uçtan uca: gerçek orchestrator/servis kodu, sahte HTTP + sahte Groq."""

import json

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.schemas.plan import AnchorPlace, ClarificationNeeded, PlanRequest
from app.services.geocoding import GeocodingServiceError
from app.services.orchestrator import build_day_plan
from app.services.places import PlacesServiceError
from app.services.planner import PlannerServiceError
from app.services.weather import OPEN_METEO_URL

GEOCODE_OK = {
    "results": [
        {
            "formatted_address": "Bursa, Türkiye",
            "geometry": {"location": {"lat": 40.18, "lng": 29.06}},
        }
    ],
    "status": "OK",
}

PLACES_OK = {
    "places": [
        {
            "id": "p1",
            "displayName": {"text": "Kitap Kahve", "languageCode": "tr"},
            "formattedAddress": "Osmangazi, Bursa",
            "location": {"latitude": 40.1885, "longitude": 29.0610},
            "rating": 4.6,
            "userRatingCount": 312,
            "types": ["cafe"],
        },
        {
            "id": "p2",
            "displayName": {"text": "Iskender Lokantası", "languageCode": "tr"},
            "formattedAddress": "Yıldırım, Bursa",
            "location": {"latitude": 40.1830, "longitude": 29.0660},
            "rating": 4.4,
            "userRatingCount": 900,
            "types": ["restaurant"],
        },
    ]
}


def _weather(code: int, temp: float = 20.0) -> dict:
    return {
        "latitude": 40.18,
        "longitude": 29.06,
        "current": {"time": "2026-09-29T14:00", "temperature_2m": temp, "weather_code": code},
    }


def _stop(place_id: str, order: int) -> dict:
    return {
        "place_id": place_id,
        "order": order,
        "arrival_time": "14:00",
        "duration_minutes": 60,
        "activity": "Gezmek",
        "recommendation": "Bir şeyler dene",
        "estimated_cost": 100,
        "name": None,
        "latitude": None,
        "longitude": None,
    }


# Model normalde 2-3 alternatif döndürür; planner tek alternatifte yeniden dener.
PLAN_JSON = json.dumps(
    {
        "alternatives": [
            {
                "theme": "kafe",
                "title": "Kafe Turu",
                "summary": "Sakin.",
                "stops": [_stop("p1", 1), _stop("p2", 2)],
            },
            {
                "theme": "yemek",
                "title": "Yemek Turu",
                "summary": "Doyurucu.",
                "stops": [_stop("p2", 1), _stop("p1", 2)],
            },
        ]
    }
)

_LEG = {"distanceMeters": 600, "duration": "480s", "polyline": {"encodedPolyline": "xyz"}}
ROUTES_OK = {"routes": [{"legs": [_LEG]}]}


def _geocode_url() -> str:
    return get_settings().google_geocoding_base_url


def _places_url() -> str:
    return f"{get_settings().google_places_base_url}/places:searchNearby"


def _routes_url() -> str:
    return get_settings().google_routes_base_url


def _mock_all(weather=None, places=None, routes=None, geocode=None) -> dict:
    """Tüm dış servisleri mutlu yol cevaplarıyla mock'lar; her rota döndürülür."""
    return {
        "geocode": respx.get(_geocode_url()).mock(
            return_value=geocode or httpx.Response(200, json=GEOCODE_OK)
        ),
        "weather": respx.get(OPEN_METEO_URL).mock(
            return_value=weather or httpx.Response(200, json=_weather(0))
        ),
        "places": respx.post(_places_url()).mock(
            return_value=places or httpx.Response(200, json=PLACES_OK)
        ),
        "routes": respx.post(_routes_url()).mock(
            return_value=routes or httpx.Response(200, json=ROUTES_OK)
        ),
    }


def _requested_types(route) -> list[set[str]]:
    """Places'e giden her isteğin includedTypes kümesi."""
    return [set(json.loads(c.request.content)["includedTypes"]) for c in route.calls]


@respx.mock
async def test_mutlu_yol_sehirden_plana(fake_groq):
    """city -> geocode -> hava+mekan -> plan -> rota; her aşama sonuca yansımalı."""
    fake = fake_groq(PLAN_JSON)
    routes = _mock_all()

    plan = await build_day_plan(PlanRequest(city="Bursa", categories=["kafe"]))

    assert routes["geocode"].called
    assert plan.weather_available is True
    assert plan.weather is not None and plan.weather.condition == "açık"
    alt = plan.alternatives[0]
    assert [s.name for s in alt.stops] == ["Kitap Kahve", "Iskender Lokantası"]
    assert alt.routes_available is True
    assert [(leg.from_order, leg.to_order) for leg in alt.legs] == [(1, 2)]
    # Hava özeti ve mekan havuzu LLM prompt'una ulaşmış olmalı
    user_prompt = fake.calls[0]["messages"][1]["content"]
    assert "20.0°C, açık" in user_prompt
    assert "id: p1" in user_prompt


@respx.mock
async def test_koordinat_verilirse_geocoding_cagrilmaz(fake_groq):
    fake_groq(PLAN_JSON)
    routes = _mock_all()

    await build_day_plan(PlanRequest(latitude=40.18, longitude=29.06, categories=["kafe"]))

    assert not routes["geocode"].called


@respx.mock
async def test_geocoding_hatasi_yukari_iletilir(fake_groq):
    fake_groq(PLAN_JSON)
    _mock_all(geocode=httpx.Response(200, json={"results": [], "status": "ZERO_RESULTS"}))

    with pytest.raises(GeocodingServiceError):
        await build_day_plan(PlanRequest(city="asdkfjaskl", categories=["kafe"]))


@respx.mock
async def test_kotu_havada_acik_hava_temasi_elenir(fake_groq):
    """Yağmurlu havada 'acik_hava' türleri Places'e hiç gönderilmemeli."""
    fake_groq(PLAN_JSON)
    routes = _mock_all(weather=httpx.Response(200, json=_weather(63)))

    await build_day_plan(PlanRequest(city="Bursa", categories=["acik_hava", "kafe"]))

    sent = _requested_types(routes["places"])
    assert len(sent) == 1  # sadece "kafe" teması aranmış
    assert "park" not in sent[0] and "cafe" in sent[0]


@respx.mock
async def test_iyi_havada_acik_hava_temasi_korunur(fake_groq):
    fake_groq(PLAN_JSON)
    routes = _mock_all(weather=httpx.Response(200, json=_weather(0)))

    await build_day_plan(PlanRequest(city="Bursa", categories=["acik_hava", "kafe"]))

    assert len(_requested_types(routes["places"])) == 2


@respx.mock
async def test_hava_servisi_coker_plan_yine_kurulur(fake_groq):
    """Hava kritik değil: 'bilinmiyor' özetiyle plan kurulmalı, daraltma yapılmamalı."""
    fake = fake_groq(PLAN_JSON)
    routes = _mock_all(weather=httpx.Response(500, text="hata"))

    plan = await build_day_plan(PlanRequest(city="Bursa", categories=["acik_hava", "kafe"]))

    assert "bilinmiyor" in fake.calls[0]["messages"][1]["content"]
    assert plan.weather_available is False
    assert plan.weather is None
    assert len(_requested_types(routes["places"])) == 2
    assert plan.alternatives


@respx.mock
async def test_serbest_metin_temalari_mekan_aramasina_yansir(fake_groq):
    """free_text -> belirsizlik kontrolü (1) -> resolve_themes (2) -> Places türleri -> plan (3)."""
    fake = fake_groq(
        json.dumps({"needs_clarification": False}),
        json.dumps({"themes": ["kafe"]}),
        PLAN_JSON,
    )
    routes = _mock_all()

    await build_day_plan(PlanRequest(city="Bursa", free_text="kahve içmek istiyorum"))

    assert len(fake.calls) == 3
    sent = _requested_types(routes["places"])
    assert len(sent) == 1 and "cafe" in sent[0]


@respx.mock
async def test_hicbir_kategori_yoksa_varsayilan_temalar_aranir(fake_groq):
    fake_groq(PLAN_JSON)
    routes = _mock_all()

    await build_day_plan(PlanRequest(city="Bursa"))

    assert len(_requested_types(routes["places"])) == 3  # yemek, kafe, tarihi


@respx.mock
async def test_bir_tema_aramasi_basarisiz_olsa_da_havuz_kurulur(fake_groq):
    """Temalardan biri 500 dönerse diğerinin sonuçlarıyla devam edilmeli."""
    fake_groq(PLAN_JSON)
    _mock_all()

    def _places(request: httpx.Request) -> httpx.Response:
        if "cafe" in json.loads(request.content)["includedTypes"]:
            return httpx.Response(500, text="hata")
        return httpx.Response(200, json=PLACES_OK)

    respx.post(_places_url()).mock(side_effect=_places)

    plan = await build_day_plan(PlanRequest(city="Bursa", categories=["kafe", "yemek"]))

    assert plan.alternatives


@respx.mock
async def test_mekan_bulunamazsa_hata(fake_groq):
    fake = fake_groq(PLAN_JSON)
    _mock_all(places=httpx.Response(200, json={}))

    with pytest.raises(PlacesServiceError, match="uygun mekan"):
        await build_day_plan(PlanRequest(city="Bursa", categories=["kafe"]))

    assert fake.calls == []  # mekan yokken LLM'e gidilmemeli


@respx.mock
async def test_llm_gecersiz_yanit_verirse_hata(fake_groq):
    fake_groq("json değil")
    _mock_all()

    with pytest.raises(PlannerServiceError):
        await build_day_plan(PlanRequest(city="Bursa", categories=["kafe"]))


@respx.mock
async def test_rota_servisi_coker_plan_yine_doner(fake_groq):
    """Rota kritik değil: plan döner, legs boş, routes_available=False."""
    fake_groq(PLAN_JSON)
    _mock_all(routes=httpx.Response(403, text="Routes API has not been used"))

    plan = await build_day_plan(PlanRequest(city="Bursa", categories=["kafe"]))

    alt = plan.alternatives[0]
    assert len(alt.stops) == 2
    assert alt.legs == []
    assert alt.routes_available is False


@respx.mock
async def test_secilen_ulasim_modu_rotaya_iletilir(fake_groq):
    fake_groq(PLAN_JSON)
    routes = _mock_all()

    plan = await build_day_plan(
        PlanRequest(city="Bursa", categories=["kafe"], travel_mode="DRIVE")
    )

    assert json.loads(routes["routes"].calls.last.request.content)["travelMode"] == "DRIVE"
    assert plan.alternatives[0].legs[0].travel_mode == "DRIVE"


@respx.mock
async def test_belirsiz_serbest_metinde_plan_yerine_soru_doner_api_cagrilmaz(fake_groq):
    """Belirsizse hiçbir dış API çağrılmamalı: geocoding/hava/mekan israf edilmemeli."""
    fake = fake_groq(json.dumps({"needs_clarification": True, "question": "Kaç kişisiniz?"}))
    routes = _mock_all()

    result = await build_day_plan(PlanRequest(city="Bursa", free_text="bir şeyler yapalım"))

    assert isinstance(result, ClarificationNeeded)
    assert result.question == "Kaç kişisiniz?"
    assert not routes["geocode"].called
    assert not routes["weather"].called
    assert not routes["places"].called
    assert len(fake.calls) == 1  # sadece belirsizlik kontrolü, create_plan çağrılmadı


@respx.mock
async def test_kategori_verilmisse_belirsizlik_kontrolu_atlanir(fake_groq):
    """categories verilmişse free_text'in belirsizliği önemsiz: tema zaten categories'ten gelir."""
    fake = fake_groq(PLAN_JSON)
    _mock_all()

    plan = await build_day_plan(
        PlanRequest(city="Bursa", categories=["kafe"], free_text="bir şeyler yapalım")
    )

    assert plan.alternatives
    assert len(fake.calls) == 1  # sadece create_plan, belirsizlik kontrolü hiç çağrılmadı


@respx.mock
async def test_clarification_cevabi_verilince_kontrol_atlanir_plan_kurulur(fake_groq):
    """previous_question/clarification_answer doluysa belirsizlik kontrolü atlanır.

    free_text tek başına (categories yok) yine de resolve_themes'i tetikler; bu
    yüzden akış resolve_themes + create_plan olmak üzere 2 Groq çağrısı yapar.
    """
    fake = fake_groq(json.dumps({"themes": ["kafe"]}), PLAN_JSON)
    routes = _mock_all()

    plan = await build_day_plan(
        PlanRequest(
            city="Bursa",
            free_text="bir şeyler yapalım",
            previous_question="Kaç kişisiniz?",
            clarification_answer="4 kişiyiz",
        )
    )

    assert routes["geocode"].called
    assert plan.alternatives
    assert len(fake.calls) == 2  # belirsizlik kontrolü atlandı: resolve_themes + create_plan
    user_prompt = fake.calls[1]["messages"][1]["content"]
    assert "4 kişiyiz" in user_prompt


@respx.mock
async def test_anchor_place_llm_secmese_de_her_alternatife_eklenir(fake_groq):
    """LLM'in sahte yanıtı (PLAN_JSON) anchor place_id'yi hiç içermiyor; yine de
    orchestrator her alternatife garanti etmeli (kullanıcı "bu mekan kesin
    rotada olsun" diyor, LLM'in seçimine güvenilmiyor)."""
    fake_groq(PLAN_JSON)
    _mock_all()

    anchor = AnchorPlace(place_id="anchor1", name="Favori Kafe", latitude=40.19, longitude=29.07)
    plan = await build_day_plan(
        PlanRequest(city="Bursa", categories=["kafe"], anchor_place=anchor)
    )

    for alt in plan.alternatives:
        anchor_stops = [s for s in alt.stops if s.place_id == "anchor1"]
        assert len(anchor_stops) == 1
        assert anchor_stops[0].name == "Favori Kafe"
        assert anchor_stops[0].order == len(alt.stops)  # sona eklendi


@respx.mock
async def test_anchor_place_llm_zaten_secmisse_tekrar_eklenmez(fake_groq):
    """LLM'in yanıtı anchor place_id'yi zaten içeriyorsa ikinci bir kopya eklenmemeli."""
    fake_groq(PLAN_JSON)  # "p1"/"p2" zaten PLACES_OK havuzunda
    _mock_all()

    anchor = AnchorPlace(place_id="p1", name="Kitap Kahve", latitude=40.1885, longitude=29.0610)
    plan = await build_day_plan(
        PlanRequest(city="Bursa", categories=["kafe"], anchor_place=anchor)
    )

    for alt in plan.alternatives:
        assert sum(1 for s in alt.stops if s.place_id == "p1") == 1


@respx.mock
async def test_belirsizlik_kontrolu_cokerse_plana_devam_edilir(fake_groq):
    """Belirsizlik kontrolü kritik değil: Groq çökerse plan yine kurulmalı.

    Ambiguity check hatada None'a düşer, ardından resolve_themes + create_plan
    normal akışıyla devam eder (toplam 3 Groq çağrısı).
    """
    fake = fake_groq(RuntimeError("groq çöktü"), json.dumps({"themes": ["kafe"]}), PLAN_JSON)
    _mock_all()

    plan = await build_day_plan(PlanRequest(city="Bursa", free_text="bir şeyler yapalım"))

    assert plan.alternatives
    assert len(fake.calls) == 3


@respx.mock
async def test_max_alternatives_fazla_alternatifi_atar(fake_groq):
    """Misafir için max_alternatives=1: LLM birden çok alternatif dönse de yalnızca biri kalır."""
    fake_groq(PLAN_JSON)
    _mock_all()

    plan = await build_day_plan(
        PlanRequest(city="Bursa", categories=["kafe"]), max_alternatives=1
    )

    assert len(plan.alternatives) == 1
