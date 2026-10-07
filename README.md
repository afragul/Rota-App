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

### Backend

Çekirdek çalışır durumda. Aşağıdakiler **hazır**:

- Konum bazlı mekân arama (Google Places "New" API)
- Anlık hava durumu (Open-Meteo)
- Şehir/adres adından koordinat çözümleme (Google Geocoding API) — `/plan` isteğinde `latitude`/`longitude` yerine `city` de verilebilir
- Hava durumuna göre kural bazlı indoor/outdoor daraltma: yağış/fırtına kodlarında sadece açık havada anlamlı temalar (`acik_hava`) mekan aramasından önce elenir, iyi havada karma kalır (`app/core/themes.py::filter_for_bad_weather`, `app/services/weather.py::is_bad_weather`)
- Duraklar arası mesafe/süre/harita çizgisi ve **adım adım tarif** (Türkçe talimat; toplu taşımada hat/durak bilgisi), ulaşım şekli kullanıcı seçimli: yürüyüş, toplu taşıma, araba (Google Routes API, `PlanAlternative.legs[].steps`)
- Kullanıcının konumundan ilk durağa rota (`POST /route/approach`) ve frontend'de canlı navigasyon modu ("Rotayı Başlat"): konum plan çıktıktan sonra, plan detayında istenir
- Durak sırası/listesi değiştiğinde ayakları yeniden hesaplama (`POST /route/legs`) — frontend'de durak silme/sıralama/değiştirme için kullanılır
- Hava durumu + mekân havuzundan Groq ile alternatifli gün planı üretimi
- Serbest metinden tema çözümleme (kullanıcı "ne istediğini" yazınca uygun temalara eşleme)
- Serbest metin belirsiz/çelişkiliyse (ör. "bir şeyler yapalım") LLM doğrudan plan yerine bir netleştirme sorusu döndürür (`app/services/planner.py::check_ambiguity`); aynı `POST /plan`, istemci `previous_question`/`clarification_answer` alanlarıyla cevabı geri gönderince bir tur sonra plana devam edilir. Backend stateless kalır — sunucu tarafında konuşma geçmişi tutulmaz.
- Plan kurulurken çekilen mekan havuzu (`DayPlan.place_pool`) tamamen yanıta dahil edilir — frontend'in durak değiştirme/ekleme özelliği bu havuzu yeniden kullanır, ek bir Google çağrısı yapmaz.
- `PlanRequest.anchor_place` verilirse (ana sayfada "sık gidilen yer" seçilince) o mekan, LLM'in seçimine bakılmaksızın her alternatife durak olarak garanti edilir (`orchestrator.py::_ensure_anchor_stop`); anchor'ın koordinatları zaten bilindiği için geocoding'e gerek kalmaz.
- Rate limiting (`slowapi`), opsiyonel Supabase JWT doğrulaması, sunucu taraflı misafir plan kotası, CORS ve girdi sınırları — bkz. `CLAUDE.md`'deki "Security" bölümü.

### Frontend

`frontend/` içinde Vite + React + TypeScript + Tailwind, Leaflet ile harita. **Hazır**:

- Konum/tercih seçimi, sonuç ve plan detayı ekranları; açık/koyu tema anahtarı
- Canlı navigasyon modu, plan detayında durakları sil/sırala/değiştir/taşı/ekle
- **Supabase Auth** (tamamen frontend'de, backend'den bağımsız): giriş opsiyonel (misafir modu var), kayıt/giriş/şifremi unuttum, kullanıcı adı
- Rota kaydetme/favorileme ve link ile paylaşım (Supabase `saved_plans` tablosu — bkz. "Frontend kurulumu")
- Mekan bazlı favorileme (`favorite_places` tablosu, rotadan bağımsız) — plan detayındaki her durakta kalp ikonu, Hesabım'da liste, "+ Durak ekle" sayfasında "Favorilerimden ekle" sekmesiyle herhangi bir rotaya eklenebilir
- Sık gidilen yerler: "Ulaşıldı" işaretlemeleri `visited_places` tablosuna kalıcı ziyaret sayacı olarak işlenir; ana sayfada en sık gidilen 5 mekan tıklanabilir kart olarak çıkar, tıklanınca o mekan garanti rotaya girer (tercihler yine sorulur)

Henüz **yapılmadı** (yol haritasında, bkz. `ROADMAP.md`'nin "Sırada / fikir aşamasında" bölümü):

- Mekan fotoğrafı/yorumları, mekan değiştirirken AI'ya serbest metinle sorma, profil fotoğrafı

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
| `DEBUG` | hayır | Varsayılan: `false`. `true` olmadıkça `/docs`, `/redoc`, `/openapi.json` kapalıdır. |
| `RATE_LIMIT_ENABLED` | hayır | Varsayılan: `true`. IP bazlı rate limiting'i (`slowapi`) kapatmak için `false` (testlerde kapalı) |
| `GUEST_DAILY_PLAN_LIMIT` | hayır | Varsayılan: `3`. Giriş yapmamış kullanıcıların günlük `/plan` kotası (sunucu tarafı; `frontend/src/guestLimit.ts`'teki `GUEST_PLAN_LIMIT` ile aynı tutulmalı) |
| `SUPABASE_JWT_SECRET` | hayır | Supabase Dashboard → Project Settings → API → JWT Settings — projende "JWT Secret" (legacy, HS256) varsa onu, yoksa "Signing Keys" altındaki aktif anahtarın PEM formatlı genel anahtarını ("-----BEGIN PUBLIC KEY-----" ile başlar, ES256/RS256) kopyala; hangisi olduğu otomatik anlaşılır. Ayarlanmazsa her istek misafir sayılır (giriş yapmış kullanıcılar da günlük kotaya tabi olur) |
| `CORS_ORIGINS` | hayır | Varsayılan: `http://localhost:5173`. Virgülle ayrılmış izinli origin listesi; prod'da frontend'in gerçek adresiyle değiştirilmeli |

`PLACES_API_KEY`, `GEOCODING_API_KEY`, `ROUTES_API_KEY` ve `GROQ_API_KEY` olmadan uygulama açılışta hata verir (bilinçli tercih, bkz. `app/core/config.py`).

## Çalıştırma

```bash
fastapi dev app/main.py
```

API `http://127.0.0.1:8000` üzerinde ayağa kalkar, dokümantasyon (`DEBUG=true` iken) `/docs`'ta.

### Dağıtım (prod)

`fastapi dev` geliştirme içindir, yayında kullanılmaz. Reverse proxy
(nginx/Caddy) arkasında, HTTPS proxy'de sonlandırılmış şekilde çalıştır:

```bash
uvicorn app.main:app --proxy-headers --forwarded-allow-ips='*'
```

`--forwarded-allow-ips` IP bazlı rate limiting'in (yukarıda) gerçek istemci
IP'sini görmesi için proxy'nin `X-Forwarded-For` header'ına güvenilmesini
sağlar — reverse proxy'nin bunu doğru ayarladığından emin ol. Prod `.env`'de
ayrıca `DEBUG=false` (varsayılan), `CORS_ORIGINS` (gerçek frontend adresi)
ve giriş yapmış kullanıcıları ayırt etmek istiyorsan `SUPABASE_JWT_SECRET`
ayarlanmalı.

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
| `POST` | `/route/approach` | Kullanıcının konumundan verilen noktaya (genelde ilk durak) tek ayaklık rota |
| `POST` | `/route/legs` | Verilen durak listesi (sıra + koordinat) için ardışık ayakları yeniden hesaplar — durak silindiğinde/sırası değiştiğinde kullanılır |

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

## Frontend kurulumu

```bash
cd frontend
npm install
cp .env.example .env
```

`frontend/.env` içine Supabase proje bilgilerini yaz (Supabase Dashboard →
Project Settings → API):

| Değişken | Açıklama |
| --- | --- |
| `VITE_SUPABASE_URL` | Supabase proje URL'i |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/public key (RLS ile korunur) |

Hesap/favoriler özelliği için Supabase projende **SQL Editor**'de
[`supabase/schema.sql`](supabase/schema.sql) dosyasının tamamını çalıştır
(bir kerelik) — `profiles` (kullanıcı adı; `auth.users` insert'inde trigger
otomatik satır açar) ve `saved_plans` (kaydedilen/favorilenen rotalar, link
ile paylaşım) tablolarını, RLS policy'lerini ve trigger'ı kurar.

İkisi de RLS açık; `profiles` herkese okunabilir/sahibi güncelleyebilir,
`saved_plans` herkese okunabilir (gizlilik modeli linkteki tahmin edilemeyen
uuid) ama sadece sahibi silebilir/ekleyebilir (hiç update policy'si yok).
RLS kurulumu 2026-10-05'te `pg_policies`/`pg_class.relrowsecurity` üzerinden
doğrulandı (bkz. ROADMAP.md Milestone 4).

Dev server'ı çalıştır:

```bash
npm run dev
```

Vite `http://localhost:5173`'te açılır, `/api/*` istekleri backend'e
(`http://localhost:8000`) proxy'lenir (bkz. `frontend/vite.config.ts`) —
backend'in de ayrıca `fastapi dev app/main.py` ile ayakta olması gerekir.

Lint ve tip kontrolü:

```bash
npm run lint
npx tsc -b --noEmit
```