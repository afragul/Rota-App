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
- Rate limiting (`slowapi`), kendi kayıt/giriş sistemimiz (argon2 şifre, kısa ömürlü JWT + `httpOnly` refresh çerezi), kullanıcı verisi için PostgreSQL, sunucu taraflı misafir plan kotası (`/plan`) ve ayrı bir misafir kotası (`/route/legs`), CORS, Content-Security-Policy (frontend build'inde) ve girdi sınırları — bkz. `CLAUDE.md`'deki "Security" bölümü.

### Frontend

`frontend/` içinde Vite + React + TypeScript + Tailwind, Leaflet ile harita. **Hazır**:

- Konum/tercih seçimi, sonuç ve plan detayı ekranları; açık/koyu tema anahtarı
- Canlı navigasyon modu, plan detayında durakları sil/sırala/değiştir/taşı/ekle
- **Hesap** (backend'in kendi auth'u, PostgreSQL): giriş opsiyonel (misafir modu var), kayıt/giriş, kullanıcı adı ve şifre değiştirme, sessiz oturum yenileme, hesabı silme, "şifremi unuttum" (kod hazır ama bilerek kapalı: KVKK nedeniyle `SMTP_*` tanımlanmıyor, bkz. ROADMAP)
- Rota kaydetme/favorileme ve link ile paylaşım (`saved_plans` tablosu, `/plans` ve `/shared/{id}`)
- Mekan bazlı favorileme (`favorite_places` tablosu, rotadan bağımsız) — plan detayındaki her durakta kalp ikonu, Hesabım'da liste, "+ Durak ekle" sayfasında "Favorilerimden ekle" sekmesiyle herhangi bir rotaya eklenebilir
- Sık gidilen yerler: "Ulaşıldı" işaretlemeleri `visited_places` tablosuna kalıcı ziyaret sayacı olarak işlenir; ana sayfada en sık gidilen 5 mekan tıklanabilir kart olarak çıkar, tıklanınca o mekan garanti rotaya girer (tercihler yine sorulur)
- Production build'inde (`npm run build`) bir Content-Security-Policy meta tag'i — `npm run dev`'de yok (HMR'ı kırar), bkz. `frontend/vite.config.ts` ve `CLAUDE.md`'deki "Security" bölümü

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
| `GUEST_DAILY_LEGS_LIMIT` | hayır | Varsayılan: `20`. Giriş yapmamış kullanıcıların günlük `/route/legs` (durak sil/sırala/ekle) kotası — `/plan`'dan ayrı bir sayaç, daha sık tetiklenen bir aksiyon olduğu için daha yüksek |
| `GUEST_DAILY_SEARCH_LIMIT` | hayır | Varsayılan: `20`. Giriş yapmamış kullanıcıların günlük mekan arama (`/places/search`, ücretli Google Text Search) kotası; ayrı sayaç |
| `JWT_SECRET` | evet | Erişim token'larını imzalamak için gizli anahtar, en az 32 karakter (`openssl rand -hex 32`). Sızarsa herkes istediği kullanıcı adına token üretebilir; yayında ayrı bir değer kullan |
| `JWT_EXPIRE_MINUTES` | hayır | Varsayılan: `15`. Erişim token'ının ömrü; oturumu refresh token sürdürür |
| `REFRESH_TOKEN_EXPIRE_DAYS` | hayır | Varsayılan: `30`. Refresh token (çerez) ömrü |
| `COOKIE_SECURE` | hayır | Varsayılan: `true`. Refresh çerezi yalnızca HTTPS'te gider. Yerel `http` geliştirmede `false` yap; yayında dokunma |
| `REFRESH_COOKIE_PATH` | hayır | Varsayılan: `/api/auth`. Tarayıcının gördüğü API adresiyle eşleşmeli; yanlışsa çerez gönderilmez ve oturum yenilenemez |
| `DATABASE_URL` | evet\* | PostgreSQL bağlantısı, ör. `postgresql+asyncpg://rota:<şifre>@localhost:5433/rota`. Docker'da `api` servisi için compose bunu kendisi kurar. Kullanıcı verisi (hesap, planlar, favoriler) için gerekli; yoksa bu endpoint'ler çalışmaz |
| `POSTGRES_PASSWORD` | evet\* | `docker-compose.yml`'deki Postgres için (`POSTGRES_USER`/`POSTGRES_DB` opsiyonel, varsayılan `rota`) |
| `MAX_SAVED_PLANS_PER_USER`, `MAX_FAVORITES_PER_USER`, `MAX_VISITED_PLACES_PER_USER` | hayır | Varsayılan: `100`, `200`, `500`. Kullanıcı başına depolama üst sınırları |
| `USER_DAILY_PLAN_LIMIT` | hayır | Varsayılan: `30`. Giriş yapmış bir kullanıcının günlük `/plan` kotası (hesap açmak ücretsiz olduğundan ücretli Google/Groq çağrılarına hesap başına da üst sınır). Gün Türkiye saatine (UTC+3) göre; sayaç veritabanında tutulur |
| `USER_DAILY_LEGS_LIMIT` | hayır | Varsayılan: `300`. Giriş yapmış bir kullanıcının günlük `/route/legs` kotası (`/plan`'dan ayrı sayaç) |
| `USER_DAILY_SEARCH_LIMIT` | hayır | Varsayılan: `100`. Giriş yapmış bir kullanıcının günlük `/places/search` kotası (ayrı sayaç) |
| `SMTP_HOST`, `SMTP_FROM` | hayır | Şifre sıfırlama e-postaları için SMTP sunucusu ve gönderen (`Rota <no-reply@alanadi.com>`). **Yoksa özellik kapalıdır:** `/auth/forgot` 503 verir, arayüz "şifremi unuttum" bağlantısını göstermez |
| `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SECURITY` | hayır | Varsayılan port `587`, güvenlik `starttls` (`ssl` = 465, `none` = yalnızca yerel test). Hangi sağlayıcı olursa (Gmail uygulama şifresi, Resend, SendGrid, Mailgun) SMTP bilgilerini buraya yaz |
| `FRONTEND_BASE_URL` | hayır | Varsayılan: `http://localhost:5173`. E-postadaki sıfırlama bağlantısı bununla başlar; yayında frontend'in gerçek adresi olmalı |
| `PASSWORD_RESET_EXPIRE_MINUTES`, `PASSWORD_RESET_COOLDOWN_SECONDS` | hayır | Varsayılan `60` ve `60`: bağlantının ömrü ve aynı hesaba iki e-posta arasındaki en kısa süre |
| `CORS_ORIGINS` | hayır | Varsayılan: `http://localhost:5173`. Virgülle ayrılmış izinli origin listesi; prod'da frontend'in gerçek adresiyle değiştirilmeli |

`PLACES_API_KEY`, `GEOCODING_API_KEY`, `ROUTES_API_KEY`, `GROQ_API_KEY` ve `JWT_SECRET` olmadan uygulama açılışta hata verir (bilinçli tercih, bkz. `app/core/config.py`). \* `DATABASE_URL`/`POSTGRES_PASSWORD` açılışta zorunlu değil, ama hesap/plan/favori/ziyaret endpoint'leri onsuz çalışmaz.

### Veritabanı (PostgreSQL)

```bash
docker compose up -d db        # Postgres'i başlatır (yalnızca 127.0.0.1:5433'e açık)
alembic upgrade head           # tabloları oluşturur / günceller
```

Şema `migrations/` altındaki Alembic migration'larıdır (kaynak: `app/db/models.py`).
Model değiştirince `alembic revision --autogenerate -m "açıklama"` ile yeni migration
üret, içine bak, sonra `alembic upgrade head`. Backend'i de konteynerde çalıştırmak için
`docker compose up --build`: `api` konteyneri açılışta `alembic upgrade head`'i kendisi
çalıştırır (`docker-entrypoint.sh`); migration başarısız olursa konteyner hatayla çıkar.
Birden çok `api` kopyası çalıştıracaksan migration'ı ayrı bir adım olarak çalıştırıp
kopyalarda `RUN_MIGRATIONS=false` ver (iki kopya aynı anda migration çalıştırmamalı).
Testler bellekte SQLite kullanır, Postgres gerekmez.

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
ve yayına özel bir `JWT_SECRET`, `DATABASE_URL`, güçlü bir `POSTGRES_PASSWORD`
ayarlanmalı. Refresh çerezi `Secure` olduğu için yayın HTTPS olmalı; frontend ve API
aynı adreste, API `/api` önekiyle sunulmalı (aksi halde `REFRESH_COOKIE_PATH`
ayarlanmalı). Sunucuda `db` servisinin `ports:` satırını kaldır: veritabanı internete açık olmamalı.

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
| `GET` | `/places/search` | Serbest metinle mekan arama (`q`, `latitude`, `longitude`: konum yalnızca öncelik verir). Ücretli; misafir ve hesap başına günlük kota |
| `GET` | `/geocode` | Şehir/adres metnini koordinata çevirir |
| `POST` | `/plan` | Konum, süre, bütçe, grup tipi ve tema/serbest metin tercihlerinden alternatif gün planları üretir (serbest metin belirsizse önce netleştirme sorusu döner) |
| `POST` | `/route/approach` | Kullanıcının konumundan verilen noktaya (genelde ilk durak) tek ayaklık rota |
| `POST` | `/route/legs` | Verilen durak listesi (sıra + koordinat) için ardışık ayakları yeniden hesaplar — durak silindiğinde/sırası değiştiğinde kullanılır |
| `POST` | `/auth/register`, `/auth/login` | Hesap açar / giriş yapar; erişim token'ı döner, refresh token `httpOnly` çereze yazılır |
| `POST` | `/auth/forgot`, `/auth/reset` | Şifre sıfırlama bağlantısı iste (hesap var olsun olmasın aynı cevap) / e-postadaki token'la yeni şifre belirle (tek kullanımlık, 1 saat; tüm oturumlar kapanır). SMTP gerektirir |
| `GET` | `/auth/capabilities` | Sunucuda hangi hesap özellikleri açık (`password_reset`: SMTP var mı) |
| `POST` | `/auth/refresh`, `/auth/logout` | Çerezdeki refresh token'la yeni erişim token'ı alır (token döner) / oturumu kapatır ve token'ı iptal eder |
| `GET`, `PATCH`, `DELETE` | `/me` | Profil / kullanıcı adını değiştir / hesabı ve tüm veriyi kalıcı sil (giriş gerekir; silmede gövdede `{"password": ...}` istenir) |
| `POST` | `/me/password` | Mevcut şifreyi doğrulayıp yenisini belirler; diğer cihazlardaki oturumlar kapanır |
| `POST`, `GET`, `DELETE` | `/plans`, `/plans/{id}` | Planı kaydet / kayıtlı planları listele / sil (giriş gerekir, yalnızca kendi planların) |
| `GET` | `/shared/{id}` | Paylaşım linkiyle planı aç (girişsiz; sahibin kimliği dönmez, yalnızca `is_owner`) |
| `GET`, `POST`, `DELETE` | `/favorites`, `/favorites/{place_id}` | Favori mekanlar (giriş gerekir; ekleme idempotent) |
| `POST`, `GET`, `DELETE` | `/visits`, `/visits/{place_id}` | "Ulaşıldı" ziyaret kaydı, sık gidilenler, tek kaydı / tüm geçmişi silme (giriş gerekir) |

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
```

Node **≥ 20.19** (ya da ≥ 22.12) gerekir (Vite 8 ve oxlint). Daha eski Node'da `npm install`/`npm ci` yerel paketleri sessizce atlar ve lint/build `Cannot find native binding` ile patlar; `node -v` ile kontrol et.

Frontend için ortam değişkeni gerekmez; hesap/plan/favori istekleri backend'e `/api` üzerinden
gider. Bunların çalışması için backend'in PostgreSQL'e bağlı olması gerekir (yukarıdaki
"Veritabanı" bölümü). Oturum: kısa ömürlü erişim token'ı `localStorage`'da, uzun ömürlü
refresh token `httpOnly` çerezde durur ve `frontend/src/auth.ts` süresi dolmadan sessizce yeniler.

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