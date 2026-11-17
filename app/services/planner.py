import json
import logging

from groq import AsyncGroq
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.themes import DEFAULT_THEMES, THEME_TYPES
from app.schemas.places import Place
from app.schemas.plan import DayPlan, PlanRequest

logger = logging.getLogger(__name__)


class _ThemeSelection(BaseModel):
    themes: list[str]


class _AmbiguityCheck(BaseModel):
    needs_clarification: bool
    question: str | None = None


class PlannerServiceError(Exception):
    """LLM'den geçerli bir plan alınamadığında fırlatılır."""


SYSTEM_INSTRUCTION = """Sen bir yerel gezi planlayıcısısın.

Sana verilen mekan listesinden gerçekçi bir günlük plan kurgularsın.

KESİN KURALLAR:
- Sadece verilen listedeki mekanları kullan. Yeni mekan UYDURMA.
- Her durak için listedeki place_id'yi birebir kopyala.
- Duraklar arası yürüme/ulaşım süresini hesaba kat.
- Verilen toplam süreyi aşma.
- Mekan sayısı yetiyorsa TAM OLARAK 3 alternatif üret (en az 2); her biri farklı bir tema
  ve mümkün olduğunca farklı duraklar içersin. Tek alternatif döndürme.
- Öneriler somut olsun. "Güzel vakit geçirirsiniz" gibi boş cümleler yazma.
- Her durağın name/latitude/longitude alanlarını null bırak, bunları sen değil sistem dolduracak.
- Tüm metin alanlarını (theme, title, summary, activity, recommendation) TÜRKÇE yaz. Mekan adları hariç İngilizce kelime kullanma.
"""

AMBIGUITY_SYSTEM_INSTRUCTION = """Kullanıcının serbest metni bir gün planı kurmak için
yeterince açık mı değerlendir.

Metin hiçbir somut sinyal vermiyorsa (ör. "bir şeyler yapalım") ya da açıkça
çelişkiliyse (ör. metin "kısa bir mola" derken toplam süre saatlerce)
needs_clarification alanını true yap ve kısa, tek cümlelik bir netleştirme sorusu
üret. Metin zaten yeterince açıksa needs_clarification false döndür.

Gereksiz yere soru sorma; şüpheye düştüğünde false'a yatkın ol, kullanıcıyı
gereksiz turlarla yorma."""


# Sistemin doldurduğu, LLM'in üretmediği alanlar: şemada göstermek hem gereksiz hem de
# prompt token'ını şişiriyor (Groq'ta dakikalık token kotası dar).
_SYSTEM_FILLED = {
    "DayPlan": ["weather_available", "weather"],
    "PlanAlternative": ["legs", "routes_available"],
}


def _llm_schema(model: type[BaseModel]) -> dict:
    """JSON şemasından sistemin doldurduğu alanları (ve artık kullanılmayan tanımları) çıkarır."""
    schema = model.model_json_schema()
    defs = schema.get("$defs", {})
    for name, fields in _SYSTEM_FILLED.items():
        target = schema if schema.get("title") == name else defs.get(name)
        if target:
            for field in fields:
                target.get("properties", {}).pop(field, None)
    # Hiçbir yerden referanslanmayan tanımları at (RouteLeg, RouteStep, WeatherSummary...)
    changed = True
    while changed:
        changed = False
        text = json.dumps({k: v for k, v in schema.items() if k != "$defs"})
        for name in list(defs):
            referenced = f'"#/$defs/{name}"' in text or any(
                f'"#/$defs/{name}"' in json.dumps(d) for n, d in defs.items() if n != name
            )
            if not referenced:
                del defs[name]
                changed = True
                break
    if not defs:
        schema.pop("$defs", None)
    return schema


def _schema_instruction(model: type[BaseModel]) -> str:
    """Modelin uyması gereken JSON şemasını prompt'a gömer.

    Gemini'nin response_schema'sı çıktıyı şemaya zorluyordu. Groq'un json_object
    modu ise sadece geçerli JSON döndürmeyi garanti ediyor, şemayı zorlamıyor.
    Bu yüzden şemayı prompt içinde açıkça veriyoruz; dönen JSON yine de
    Pydantic ile doğrulanıyor (ValidationError -> PlannerServiceError).
    """
    schema = json.dumps(_llm_schema(model), ensure_ascii=False)
    return (
        "\n\nYanıtını SADECE şu JSON şemasına uyan bir JSON nesnesi olarak ver, "
        f"başka hiçbir açıklama/metin ekleme:\n{schema}"
    )


def _format_places(places: list[Place]) -> str:
    """Mekan havuzunu modelin okuyabileceği metne çevirir."""
    lines = []
    for p in places:
        rating = f"{p.rating} ({p.user_rating_count} yorum)" if p.rating else "puan yok"
        lines.append(
            f"- id: {p.place_id} | {p.name} | {rating} "
            f"| türler: {', '.join(p.types[:3])} | {p.address or 'adres yok'}"
        )
    return "\n".join(lines)


def _build_prompt(
    request: PlanRequest,
    places: list[Place],
    weather_summary: str,
) -> str:
    clarification_block = ""
    if request.previous_question and request.clarification_answer:
        clarification_block = (
            f"Netleştirme sorusu: {request.previous_question}\n"
            f"Kullanıcının cevabı: {request.clarification_answer}\n"
        )

    start_time_line = ""
    if request.start_time:
        start_time_line = (
            f"Başlangıç saati: {request.start_time} (ilk durağın varış saati tam bu "
            "saatte ya da hemen sonrasında olsun, daha erken olmasın)\n"
        )

    return f"""BAĞLAM
Grup: {request.group_type.value}
Bütçe: {request.budget.value}
Toplam süre: {request.duration_hours} saat
{start_time_line}Hava durumu: {weather_summary}
Kullanıcının isteği: {request.free_text or "belirtilmedi"}
{clarification_block}
MEKAN LİSTESİ
{_format_places(places)}

Bu mekanlardan {request.duration_hours} saatlik 3 birbirinden farklı alternatif plan kur.
Tüm metin alanlarını (theme, title, summary, activity, recommendation) TÜRKÇE yaz. Mekan adları hariç İngilizce kelime kullanma.
"""


def _validate_and_enrich_stops(plan: DayPlan, places: list[Place]) -> DayPlan:
    """Model uydurma place_id döndürdüyse o durakları eler.

    Geçerli duraklar mekan havuzundan gelen gerçek ad/koordinatla
    zenginleştirilir (LLM bunları üretmiyor, null bırakıyor -- haritada pin
    basabilmek için gerekli, ama LLM'e ürettirmek halüsinasyon riski taşır).
    """
    by_id = {p.place_id: p for p in places}

    for alternative in plan.alternatives:
        before = len(alternative.stops)
        valid_stops = []
        for stop in alternative.stops:
            place = by_id.get(stop.place_id)
            if place is None:
                continue
            stop.name = place.name
            stop.latitude = place.latitude
            stop.longitude = place.longitude
            valid_stops.append(stop)
        alternative.stops = valid_stops

        dropped = before - len(alternative.stops)
        if dropped:
            logger.warning("'%s' planında %d uydurma mekan elendi", alternative.theme, dropped)

    # Tamamen boşalan alternatifleri at
    plan.alternatives = [a for a in plan.alternatives if a.stops]

    if not plan.alternatives:
        raise PlannerServiceError("Geçerli bir plan oluşturulamadı")

    return plan


MIN_ALTERNATIVES = 2
MAX_ATTEMPTS = 2


async def create_plan(
    request: PlanRequest,
    places: list[Place],
    weather_summary: str,
) -> DayPlan:
    """Mekan havuzundan LLM ile günlük plan üretir.

    Model bazen prompt'a rağmen tek alternatif döndürüyor; MIN_ALTERNATIVES'ın
    altında kalırsa bir kez daha denenir. Yine de azsa eldeki plan döner
    (hiç plan dönmemesinden iyidir).
    """
    best: DayPlan | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        plan = await _generate_plan(request, places, weather_summary)
        if best is None or len(plan.alternatives) > len(best.alternatives):
            best = plan
        if len(best.alternatives) >= MIN_ALTERNATIVES:
            break
        logger.warning("Yalnızca %d alternatif geldi (deneme %d)", len(best.alternatives), attempt)
    assert best is not None
    return best


async def _generate_plan(
    request: PlanRequest,
    places: list[Place],
    weather_summary: str,
) -> DayPlan:
    if not places:
        raise PlannerServiceError("Plan kurmak için mekan bulunamadı")

    settings = get_settings()
    client = AsyncGroq(api_key=settings.groq_api_key.get_secret_value())

    try:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION + _schema_instruction(DayPlan)},
                {"role": "user", "content": _build_prompt(request, places, weather_summary)},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
        )
    except Exception as exc:
        logger.warning("Groq çağrısı başarısız: %s", exc)
        raise PlannerServiceError("Plan servisi yanıt vermedi") from exc

    content = response.choices[0].message.content
    if not content:
        raise PlannerServiceError("Plan servisi boş yanıt döndürdü")

    try:
        plan = DayPlan.model_validate_json(content)
    except ValidationError:
        # Yanıt kullanıcı notundan alıntı içerebilir: içerik değil yalnızca uzunluğu yazılır.
        logger.warning("Groq yanıtı şemaya uymadı (%d karakter)", len(content))
        raise PlannerServiceError("Plan yanıtı çözümlenemedi") from None

    return _validate_and_enrich_stops(plan, places)


async def resolve_themes(free_text: str) -> list[str]:
    """Kullanıcının serbest metnini tema listesine çevirir."""
    settings = get_settings()
    client = AsyncGroq(api_key=settings.groq_api_key.get_secret_value())

    valid = ", ".join(THEME_TYPES.keys())
    prompt = (
        f"Kullanıcı isteği: {free_text}\n\n"
        f"Bu isteğe uygun temaları seç. SADECE şunlardan seç: {valid}\n"
        f"En fazla 3 tema seç." + _schema_instruction(_ThemeSelection)
    )

    try:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("Tema çözümleme başarısız: %s", exc)
        return DEFAULT_THEMES

    content = response.choices[0].message.content
    if not content:
        return DEFAULT_THEMES

    try:
        selection = _ThemeSelection.model_validate_json(content)
    except ValidationError:
        return DEFAULT_THEMES

    # Model uydurma tema döndürebilir, süz
    themes = [t for t in selection.themes if t in THEME_TYPES]
    return themes or DEFAULT_THEMES


async def check_ambiguity(request: PlanRequest) -> str | None:
    """free_text belirsizse netleştirme sorusu döner, değilse None.

    Kritik değil: Groq çöker/bozuk JSON dönerse None'a düşülür, orchestrator
    doğrudan plana devam eder (resolve_themes'teki DEFAULT_THEMES deseniyle aynı).
    """
    settings = get_settings()
    client = AsyncGroq(api_key=settings.groq_api_key.get_secret_value())

    prompt = f"Kullanıcı isteği: {request.free_text}" + _schema_instruction(_AmbiguityCheck)

    try:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": AMBIGUITY_SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("Belirsizlik kontrolü başarısız: %s", exc)
        return None

    content = response.choices[0].message.content
    if not content:
        return None

    try:
        result = _AmbiguityCheck.model_validate_json(content)
    except ValidationError:
        return None

    if result.needs_clarification and result.question:
        return result.question
    return None
