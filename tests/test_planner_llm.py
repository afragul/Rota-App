import json

import pytest

from app.core.themes import DEFAULT_THEMES
from app.schemas.places import Place
from app.schemas.plan import PlanRequest
from app.services.planner import (
    PlannerServiceError,
    check_ambiguity,
    create_plan,
    resolve_themes,
)

PLACES = [
    Place(
        place_id="p1",
        name="Kitap Kahve",
        address="Osmangazi, Bursa",
        latitude=40.1885,
        longitude=29.0610,
        rating=4.6,
        user_rating_count=312,
        types=["cafe"],
    ),
    Place(
        place_id="p2",
        name="Iskender Lokantası",
        address="Yıldırım, Bursa",
        latitude=40.1830,
        longitude=29.0660,
        rating=4.4,
        user_rating_count=900,
        types=["restaurant"],
    ),
]

REQUEST = PlanRequest(city="Bursa", duration_hours=4, free_text="sakin bir gün")


def _stop(place_id: str, order: int) -> dict:
    # LLM name/latitude/longitude'u null bırakır (bkz. SYSTEM_INSTRUCTION)
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


def _plan_json(*stops: dict, alternatives: int = 2) -> str:
    return json.dumps(
        {
            "alternatives": [
                {
                    "theme": f"tema{i}",
                    "title": f"Tur {i}",
                    "summary": "Sakin.",
                    "stops": list(stops),
                }
                for i in range(alternatives)
            ]
        }
    )


# --- create_plan ---


async def test_create_plan_gecerli_yanit_zenginlestirilir(fake_groq):
    """Geçerli yanıtta duraklar havuzdan gelen ad/koordinatla dolmalı."""
    fake = fake_groq(_plan_json(_stop("p1", 1), _stop("p2", 2)))

    plan = await create_plan(REQUEST, PLACES, "20°C, açık")

    stops = plan.alternatives[0].stops
    assert [s.name for s in stops] == ["Kitap Kahve", "Iskender Lokantası"]
    assert stops[0].latitude == 40.1885
    assert len(fake.calls) == 1


async def test_create_plan_tek_alternatifte_bir_kez_daha_dener(fake_groq):
    """Model tek alternatif döndürürse yeniden denenir, daha iyi sonuç kullanılır."""
    fake = fake_groq(_plan_json(_stop("p1", 1), alternatives=1), _plan_json(_stop("p1", 1)))

    plan = await create_plan(REQUEST, PLACES, "20°C, açık")

    assert len(fake.calls) == 2
    assert len(plan.alternatives) == 2


async def test_create_plan_hep_tek_alternatifse_ikinci_denemeden_sonra_birakir(fake_groq):
    """Deneme sayısı sınırlı; yine tek gelirse plan hata vermeden döner."""
    fake = fake_groq(_plan_json(_stop("p1", 1), alternatives=1))

    plan = await create_plan(REQUEST, PLACES, "20°C, açık")

    assert len(fake.calls) == 2
    assert len(plan.alternatives) == 1


async def test_create_plan_istek_dogru_kuruluyor(fake_groq):
    """JSON modu, şema talimatı; prompt'ta mekan id'leri, hava ve süre olmalı."""
    fake = fake_groq(_plan_json(_stop("p1", 1)))

    await create_plan(REQUEST, PLACES, "20°C, açık")

    call = fake.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    system, user = call["messages"]
    assert system["role"] == "system" and "JSON şemasına" in system["content"]
    assert "id: p1" in user["content"] and "id: p2" in user["content"]
    assert "20°C, açık" in user["content"]
    assert "4 saat" in user["content"]
    assert "sakin bir gün" in user["content"]


async def test_create_plan_uydurma_place_id_elenir(fake_groq):
    """Havuzda olmayan place_id'li durak atılmalı, geçerli olan kalmalı."""
    fake_groq(_plan_json(_stop("p1", 1), _stop("uydurma", 2)))

    plan = await create_plan(REQUEST, PLACES, "açık")

    assert [s.place_id for s in plan.alternatives[0].stops] == ["p1"]


async def test_create_plan_bos_havuzda_groq_cagrilmaz(fake_groq):
    fake = fake_groq(_plan_json(_stop("p1", 1)))

    with pytest.raises(PlannerServiceError):
        await create_plan(REQUEST, [], "açık")

    assert fake.calls == []


async def test_create_plan_groq_hata_verirse(fake_groq):
    fake_groq(RuntimeError("groq çöktü"))

    with pytest.raises(PlannerServiceError, match="yanıt vermedi"):
        await create_plan(REQUEST, PLACES, "açık")


async def test_create_plan_bos_yanit(fake_groq):
    fake_groq(None)

    with pytest.raises(PlannerServiceError, match="boş"):
        await create_plan(REQUEST, PLACES, "açık")


@pytest.mark.parametrize("content", ["json değil", '{"alternatives": "yanlış tip"}', "{}"])
async def test_create_plan_sema_disi_yanit(fake_groq, content):
    """Geçerli JSON olmayan ya da şemaya uymayan yanıt PlannerServiceError olmalı."""
    fake_groq(content)

    with pytest.raises(PlannerServiceError, match="çözümlenemedi"):
        await create_plan(REQUEST, PLACES, "açık")


async def test_create_plan_tum_duraklar_uydurmaysa_hata(fake_groq):
    fake_groq(_plan_json(_stop("uydurma1", 1), _stop("uydurma2", 2)))

    with pytest.raises(PlannerServiceError, match="Geçerli bir plan"):
        await create_plan(REQUEST, PLACES, "açık")


# --- resolve_themes ---


async def test_resolve_themes_gecerli_temalar(fake_groq):
    fake = fake_groq(json.dumps({"themes": ["kafe", "tarihi"]}))

    assert await resolve_themes("kahve içip müze gezmek istiyorum") == ["kafe", "tarihi"]
    assert "kahve içip müze" in fake.calls[0]["messages"][0]["content"]


async def test_resolve_themes_uydurma_tema_suzulur(fake_groq):
    fake_groq(json.dumps({"themes": ["kafe", "uzay_yolculugu"]}))

    assert await resolve_themes("kahve") == ["kafe"]


async def test_resolve_themes_hepsi_gecersizse_varsayilan(fake_groq):
    fake_groq(json.dumps({"themes": ["uzay_yolculugu"]}))

    assert await resolve_themes("bir şey") == DEFAULT_THEMES


@pytest.mark.parametrize(
    "response",
    [RuntimeError("groq çöktü"), None, "json değil", '{"themes": "liste değil"}'],
    ids=["groq-hatasi", "bos-yanit", "bozuk-json", "sema-disi"],
)
async def test_resolve_themes_hatada_varsayilana_duser(fake_groq, response):
    """Tema çözümleme kritik değil: her hatada varsayılan temalar dönmeli."""
    fake_groq(response)

    assert await resolve_themes("bir şey") == DEFAULT_THEMES


# --- check_ambiguity ---


async def test_check_ambiguity_belirsizse_soru_doner(fake_groq):
    fake = fake_groq(json.dumps({"needs_clarification": True, "question": "Kaç kişisiniz?"}))

    question = await check_ambiguity(PlanRequest(city="Bursa", free_text="bir şeyler yapalım"))

    assert question == "Kaç kişisiniz?"
    assert len(fake.calls) == 1


async def test_check_ambiguity_netse_none_doner(fake_groq):
    fake_groq(json.dumps({"needs_clarification": False}))

    question = await check_ambiguity(
        PlanRequest(city="Bursa", free_text="kahve içip müze gezmek istiyorum")
    )

    assert question is None


async def test_check_ambiguity_needs_clarification_true_ama_soru_yoksa_none_doner(fake_groq):
    fake_groq(json.dumps({"needs_clarification": True, "question": None}))

    question = await check_ambiguity(PlanRequest(city="Bursa", free_text="bir şeyler yapalım"))

    assert question is None


@pytest.mark.parametrize(
    "response",
    [RuntimeError("groq çöktü"), None, "json değil", '{"needs_clarification": "evet"}'],
    ids=["groq-hatasi", "bos-yanit", "bozuk-json", "sema-disi"],
)
async def test_check_ambiguity_hatada_none_doner_plana_devam_edilir(fake_groq, response):
    """Belirsizlik kontrolü kritik değil: her hatada None dönüp plana devam edilmeli."""
    fake_groq(response)

    question = await check_ambiguity(PlanRequest(city="Bursa", free_text="bir şeyler yapalım"))

    assert question is None
