# Rota App

Gruplar (arkadaş, aile, çift, tek kişi) için yapay zekâ destekli günlük rota planlayıcı. Kullanıcı birkaç tercih seçer, sistem konumun hava durumunu ve yakındaki mekânları toplar, Groq üzerinden çalışan bir LLM bu verilerden birbirinden farklı alternatif planlar kurar.

## Fikir

Kullanıcı uygulamaya girdiğinde:

1. **Konum/şehir** seçer.
2. **Bütçe** seçer *(opsiyonel — düşük / orta / yüksek)*.
3. **Aktivite türü** seçer *(opsiyonel — tarihi, yemek, kafe, açık hava, eğlence, alışveriş...)*.
4. İsterse hazır seçenekler yerine **serbest metinle** ne istediğini yazar: *"Ailecek 4 saatimiz var, çocuklarla açık havada bir şeyler yapmak istiyoruz"* gibi. Gerekirse yapay zekâ netleştirmek için ek soru sorar.

Sistem bu tercihlere göre:

- Seçilen konumun **anlık hava durumunu** çeker.
- Hava **yağışlı/kötü** ise kapalı alan (indoor) ağırlıklı, **açık/iyi** ise karma (indoor + outdoor) aktiviteler önerir.
- Yakındaki mekânları **Google Places** üzerinden tema bazlı arar.
- Toplanan mekân havuzunu, hava durumunu ve kullanıcı tercihlerini **Groq** üzerinden çalışan LLM'e vererek 2-3 alternatif, duraklı bir gün planı ürettirir.
- Sonucu haritada rotaya dönüştürüp kullanıcıya sunar.

## Şu anki durum

Backend'in çekirdeği çalışır durumda. Aşağıdakiler **hazır**:

- Konum bazlı mekân arama (Google Places "New" API)
- Anlık hava durumu (Open-Meteo)
- Şehir/adres adından koordinat çözümleme (Google Geocoding API) — `/plan` isteğinde `latitude`/`longitude` yerine `city` de verilebilir
- Hava durumuna göre kural bazlı indoor/outdoor daraltma: yağış/fırtına kodlarında sadece açık havada anlamlı temalar (`acik_hava`) mekan aramasından önce elenir, iyi havada karma kalır (`app/core/themes.py::filter_for_bad_weather`, `app/services/weather.py::is_bad_weather`)
- Duraklar arası mesafe/süre/harita çizgisi, ulaşım şekli kullanıcı seçimli: yürüyüş, toplu taşıma, araba (Google Routes API, `PlanAlternative.legs`)
- Hava durumu + mekân havuzundan Groq ile alternatifli gün planı üretimi
- Serbest metinden tema çözümleme (kullanıcı "ne istediğini" yazınca uygun temalara eşleme)
- Serbest metin belirsiz/çelişkiliyse (ör. "bir şeyler yapalım") LLM doğrudan plan yerine bir netleştirme sorusu döndürür (`app/services/planner.py::check_ambiguity`); aynı `POST /plan`, istemci `previous_question`/`clarification_answer` alanlarıyla cevabı geri gönderince bir tur sonra plana devam edilir. Backend stateless kalır — sunucu tarafında konuşma geçmişi tutulmaz.

Henüz **yapılmadı** (yol haritasında, bkz. `ROADMAP.md`):

- Adım adım yol tarifi (rota çizgisi hazır, talimat metinleri yok)
- Frontend / mobil arayüz

## Teknoloji yığını

- **FastAPI** — HTTP API
- **Pydantic / pydantic-settings** — şema ve ortam değişkeni yönetimi
- **httpx** — dış servis çağrıları
- **Google Places API (New)** — mekân arama
- **Google Geocoding API** — şehir/adres → koordinat
- **Open-Meteo** — hava durumu
- **Groq** (`groq`) — plan üretimi ve serbest metin → tema çözümleme
- **pytest / pytest-asyncio / respx** — test

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

`.env` dosyası oluştur (`.env.example` referans alınabilir):

```bash
cp .env.example .env
```

| Değişken | Zorunlu | Açıklama |
| --- | --- | --- |
| `PLACES_API_KEY` | evet | Google Places API anahtarı |
| `GEOCODING_API_KEY` | evet | Google Geocoding API anahtarı (şehir/adres çözümleme) |
| `ROUTES_API_KEY` | evet | Google Routes API anahtarı (duraklar arası rota çizgisi) |
| `GROQ_API_KEY` | evet | Groq API anahtarı ([console.groq.com](https://console.groq.com)) |
| `GOOGLE_PLACES_BASE_URL` | hayır | Varsayılan: `https://places.googleapis.com/v1` |
| `GOOGLE_GEOCODING_BASE_URL` | hayır | Varsayılan: `https://maps.googleapis.com/maps/api/geocode/json` |
| `GROQ_MODEL` | hayır | Varsayılan: `openai/gpt-oss-120b`. Hangi modellerin erişilebilir olduğu hesap/tier'a göre değişir (bkz. `console.groq.com/docs/models`). |
| `HTTP_TIMEOUT` | hayır | Dış servis çağrıları için saniye cinsinden zaman aşımı (varsayılan `10.0`) |
| `APP_NAME` | hayır | Varsayılan: `Rota App` |
| `DEBUG` | hayır | Varsayılan: `false` |

`PLACES_API_KEY`, `GEOCODING_API_KEY`, `ROUTES_API_KEY` ve `GROQ_API_KEY` olmadan uygulama açılışta hata verir (bilinçli tercih, bkz. `app/core/config.py`).

## Çalıştırma

```bash
fastapi dev app/main.py
```

API `http://127.0.0.1:8000` üzerinde ayağa kalkar, dokümantasyon `/docs`'ta.

## Test

```bash
pytest
```

## API uç noktaları

| Metot | Yol | Açıklama |
| --- | --- | --- |
| `GET` | `/health` | Sağlık kontrolü |
| `GET` | `/weather` | Verilen koordinat için anlık hava durumu |
| `GET` | `/places/nearby` | Verilen koordinat ve türlere göre yakındaki mekânlar |
| `GET` | `/geocode` | Şehir/adres metnini koordinata çevirir |
| `POST` | `/plan` | Konum, süre, bütçe, grup tipi ve tema/serbest metin tercihlerinden alternatif gün planları üretir (serbest metin belirsizse önce netleştirme sorusu döner) |

### `POST /plan` örnek istek

Koordinatla:

```json
{
  "latitude": 40.1826,
  "longitude": 29.0665,
  "duration_hours": 4,
  "budget": "medium",
  "group_type": "family",
  "free_text": "Çocuklarla açık havada bir şeyler yapmak istiyoruz"
}
```

Şehir adıyla (`latitude`/`longitude` yerine, backend geocoding ile koordinata çevirir):

```json
{
  "city": "Bursa",
  "duration_hours": 4,
  "budget": "medium",
  "group_type": "family",
  "free_text": "Çocuklarla açık havada bir şeyler yapmak istiyoruz"
}
```

`latitude`+`longitude` ikilisi veya `city` alanlarından biri zorunlu; hiçbiri verilmezse istek 422 ile reddedilir. `categories` (örn. `["yemek", "kafe", "tarihi"]`) ile `free_text` birlikte de kullanılabilir; `categories` verilmişse öncelik onda, hiçbiri verilmezse varsayılan temalar (`yemek`, `kafe`, `tarihi`) kullanılır.

### Netleştirme turu (belirsiz `free_text`)

`categories` verilmemişse ve `free_text` yeterince açık değilse `POST /plan`, `DayPlan` yerine bir soru döner:

```json
{
  "question": "Kaç kişi olacaksınız?"
}
```

İstemci soruyu gösterir, kullanıcının cevabını alır ve aynı isteği `previous_question`/`clarification_answer` ekleyerek tekrar gönderir:

```json
{
  "city": "Bursa",
  "free_text": "bir şeyler yapalım",
  "previous_question": "Kaç kişi olacaksınız?",
  "clarification_answer": "4 kişiyiz"
}
```

Bu ikinci istek her zaman normal `DayPlan` döner — belirsizlik kontrolü bir kez yapılır, tekrar sorulmaz. Sunucu tarafında bir konuşma geçmişi tutulmaz; bu iki alanı geri göndermek istemcinin sorumluluğundadır.