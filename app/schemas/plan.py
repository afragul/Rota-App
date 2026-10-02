from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.schemas.places import Place


class BudgetLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GroupType(StrEnum):
    SOLO = "solo"
    COUPLE = "couple"
    FRIENDS = "friends"
    FAMILY = "family"


class TravelMode(StrEnum):
    """Duraklar arası ulaşım şekli; değerler Google Routes API'nin travelMode adlarıdır."""

    WALK = "WALK"
    TRANSIT = "TRANSIT"
    DRIVE = "DRIVE"


class PlanRequest(BaseModel):
    """Kullanıcıdan gelen istek."""

    # Konum: latitude+longitude İKİLİSİ VEYA city verilmeli
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = Field(
        default=None,
        description="latitude/longitude verilmezse şehir/adres metninden koordinat çözümlenir",
    )

    duration_hours: int = 4
    budget: BudgetLevel = BudgetLevel.MEDIUM
    group_type: GroupType = GroupType.FRIENDS
    travel_mode: TravelMode = TravelMode.WALK

    # Kategori seçimi VEYA serbest metin
    categories: list[str] | None = None
    free_text: str | None = None

    # Netleştirme turu: bir önceki /plan cevabı ClarificationNeeded ise, istemci
    # soruyu ve kullanıcının cevabını bu iki alanla geri gönderir. Sunucu
    # tarafında oturum/state tutulmuyor (bkz. ROADMAP.md Milestone 2).
    previous_question: str | None = Field(
        default=None,
        description="Bir önceki /plan çağrısında dönen netleştirme sorusu (varsa)",
    )
    clarification_answer: str | None = Field(
        default=None,
        description="Kullanıcının previous_question'a cevabı; varsa belirsizlik "
        "kontrolü atlanır, doğrudan plana geçilir",
    )

    @model_validator(mode="after")
    def _konum_verildi_mi(self) -> "PlanRequest":
        has_coords = self.latitude is not None and self.longitude is not None
        if not has_coords and not self.city:
            raise ValueError("latitude/longitude ikilisi veya city alanlarından biri verilmeli")
        return self


class PlanStop(BaseModel):
    """Plandaki tek bir durak."""

    place_id: str = Field(description="Verilen mekan listesinden seçilen id")
    order: int = Field(description="Kaçıncı durak, 1'den başlar")
    arrival_time: str = Field(description="Varış saati, ÖRN: 14:30")
    duration_minutes: int = Field(description="Burada geçirilecek süre")
    activity: str = Field(description="Burada ne yapılır, tek cümle")
    recommendation: str = Field(description="Somut öneri: ne yenir, ne görülür")
    estimated_cost: int = Field(description="Kişi başı tahmini harcama, TL")

    # LLM bu alanları üretmez, null bırakır; mekan havuzundan sistem doldurur
    # (bkz. app/services/planner.py::_validate_and_enrich_stops). Haritada pin
    # basmak için gerekli.
    name: str | None = Field(default=None, description="Mekanın adı (sistem doldurur)")
    latitude: float | None = Field(default=None, description="Mekanın enlemi (sistem doldurur)")
    longitude: float | None = Field(default=None, description="Mekanın boylamı (sistem doldurur)")


class TransitDetail(BaseModel):
    """Toplu taşıma adımının hat/durak bilgisi (Routes API transitDetails)."""

    line_name: str | None = Field(default=None, description='Hat adı/kısa adı, örn: "M4"')
    line_color: str | None = Field(default=None, description='Hat rengi, örn: "#e91e76"')
    line_text_color: str | None = Field(default=None, description="Hat rengi üstündeki yazı rengi")
    vehicle: str | None = Field(default=None, description='Araç türü, örn: "Metro", "Otobüs"')
    headsign: str | None = Field(default=None, description="Aracın gittiği yön/son durak")
    departure_stop: str | None = Field(default=None, description="Biniş durağı")
    arrival_stop: str | None = Field(default=None, description="İniş durağı")
    departure_time: str | None = Field(default=None, description='Yerel kalkış saati, örn: "14:58"')
    stop_count: int | None = Field(default=None, description="Kaç durak gidilir")


class RouteStep(BaseModel):
    """Bir ayağın (iki durak arası) adım adım tarif satırı."""

    travel_mode: TravelMode = Field(description="Bu adımın ulaşımı (TRANSIT ayağında WALK da olur)")
    instruction: str | None = Field(default=None, description="Türkçe talimat")
    maneuver: str | None = Field(
        default=None, description='Google manevra kodu, örn: "TURN_LEFT"; UI ikonu için'
    )
    distance_meters: int = 0
    duration_minutes: int = Field(default=1, description="Tahmini süre, dakika (en az 1)")
    transit: TransitDetail | None = Field(default=None, description="Yalnızca TRANSIT adımlarında")


class RouteLeg(BaseModel):
    """İki ardışık durak arasındaki ulaşım ayağı (harita çizgisi için)."""

    travel_mode: TravelMode = Field(description="Bu ayağın ulaşım şekli")

    from_order: int = Field(description="Başlangıç durağının order değeri")
    to_order: int = Field(description="Varış durağının order değeri")
    distance_meters: int = Field(description="Mesafe, metre")
    duration_minutes: int = Field(description='Tahmini süre, dakika (UI: "15 dk yürüyüş")')
    polyline: str = Field(description="Google encoded polyline; frontend decode edip çizer")
    steps: list[RouteStep] = Field(
        default_factory=list, description="Adım adım tarif (alınamazsa boş)"
    )


class ApproachRequest(BaseModel):
    """Kullanıcının bulunduğu yerden bir noktaya (ilk durak) rota isteği."""

    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    travel_mode: TravelMode = TravelMode.WALK


class ApproachRoute(BaseModel):
    """Kullanıcının konumundan ilk durağa tek ayaklık rota (order'sız RouteLeg)."""

    travel_mode: TravelMode
    distance_meters: int
    duration_minutes: int
    polyline: str = Field(description="Google encoded polyline; frontend decode edip çizer")
    steps: list[RouteStep] = Field(
        default_factory=list, description="Adım adım tarif (alınamazsa boş)"
    )


class LegStop(BaseModel):
    """Ayakları yeniden hesaplamak için gereken minimum durak bilgisi."""

    order: int
    latitude: float
    longitude: float


class LegsRequest(BaseModel):
    """Kullanıcı bir durağı silip/sırasını değiştirip ayakları yeniden istediğinde."""

    stops: list[LegStop]
    travel_mode: TravelMode = TravelMode.WALK


class LegsResponse(BaseModel):
    legs: list[RouteLeg]


class PlanAlternative(BaseModel):
    """Tek bir temalı gün planı."""

    theme: str = Field(description="Tema adı, örn: Tarihi Bursa")
    title: str = Field(description="Çekici bir başlık")
    summary: str = Field(description="Günün özeti, 1-2 cümle")
    stops: list[PlanStop]

    # LLM üretmez; orchestrator, rota servisinden doldurur. Rota alınamazsa boş kalır.
    legs: list[RouteLeg] = Field(
        default_factory=list, description="Ardışık duraklar arası rota (sistem doldurur)"
    )
    routes_available: bool = Field(
        default=True,
        description=(
            "Rota bilgisi alınabildi mi. False ise legs boştur ve UI yalnızca pin "
            "gösterebilir. Tek duraklı planda rota gerekmediği için True kalır."
        ),
    )


class ClarificationNeeded(BaseModel):
    """Planlayıcı devam etmeden önce kullanıcıya netleştirme sorusu sormalı.

    DayPlan'a ortak bir "status" alanı eklenmedi: DayPlan'ın şeması Groq'a
    _schema_instruction ile gösteriliyor, ekstra bir alan LLM'in kendi status
    değerini uydurup şema dışı yanıt vermesine yol açabilir. build_day_plan zaten
    tipli bir instance döndürdüğü için FastAPI response_model'de union'ı
    discriminator olmadan da doğru serialize eder.
    """

    question: str = Field(description="Kullanıcıya sorulacak netleştirici soru")


class WeatherSummary(BaseModel):
    """UI'daki hava rozeti için özet (sistem doldurur)."""

    temperature: float = Field(description="Sıcaklık, °C")
    condition: str = Field(description='Türkçe durum, örn: "yağmurlu"')
    is_bad: bool = Field(description="Yağış/fırtına: indoor ağırlıklı öneri yapıldı")


class DayPlan(BaseModel):
    """LLM'in döndüreceği nihai yapı."""

    weather_available: bool = Field(
        default=True,
        description=(
            "Hava durumu bilgisi alınabildi mi. "
            "False ise plan, hava açık varsayılarak üretilmiştir."
        ),
    )

    # weather_available=False iken None
    weather: WeatherSummary | None = Field(
        default=None, description="Hava özeti (sistem doldurur); alınamadıysa null"
    )

    alternatives: list[PlanAlternative] = Field(
        description="Birbirinden farklı 2-3 alternatif plan"
    )

    # LLM üretmez; orchestrator doldurur (bkz. legs/weather). Plan kurulurken
    # çekilen tüm mekan havuzu (seçilenler dahil) — frontend durak
    # değiştirirken buradan seçer, yeni bir Places çağrısı yapmaz.
    place_pool: list[Place] = Field(default_factory=list)
