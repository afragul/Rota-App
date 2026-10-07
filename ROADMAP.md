# Yol Haritası

Backend önce tamamlanıp sonra frontend'e geçilecek şekilde sıralandı. README.md "Şu anki durum" ve DESIGN.md "Sonraki adımlar" bölümleriyle tutarlıdır; oradaki eksikler burada somut görevlere bölündü.

## Milestone 1 — Backend'i tamamla

- [x] **Şehir/adres → koordinat çözümleme**: `/plan` artık `latitude`/`longitude` ikilisi yerine `city` de kabul ediyor (`app/services/geocoding.py`, Google Geocoding API). `GEOCODING_API_KEY` bunun için kullanılıyor. Bağımsız test için `GET /geocode` eklendi.
- [x] **Hava durumuna göre kural bazlı indoor/outdoor ağırlıklandırma**: `app/services/weather.py::is_bad_weather` yağış/fırtına kodlarını işaretliyor, `app/core/themes.py::filter_for_bad_weather` kötü havada `acik_hava` temasını mekan aramasından önce eliyor (`orchestrator.py::build_day_plan`). Not: bu artık hava sonucunun mekan aramasından önce beklenmesini gerektiriyor — hava/mekan paralel çekimi kayboldu, tema çözümleme (LLM) ile hava paralel kaldı. Ayrıca `_weather_summary`'deki `weather.description` (var olmayan alan) hatası `weather.condition` olarak düzeltildi.
- [x] **Rota/harita verisi — pin'ler**: Stitch UI tasarımı incelenirken fark edildi: haritada pin basmak için bile `PlanStop`'ta koordinat yoktu. `PlanStop`'a `name`/`latitude`/`longitude` eklendi; LLM bunları üretmiyor (null bırakıyor), `planner.py::_validate_and_enrich_stops` doğrulanmış mekan havuzundan dolduruyor.
- [x] **Rota/harita verisi — çizgi**: `PlanAlternative.legs` ardışık duraklar arası ayakları (`travel_mode`, `distance_meters`, `duration_minutes`, encoded `polyline`) taşıyor. Ulaşım şeklini kullanıcı seçiyor: `PlanRequest.travel_mode` (`WALK` varsayılan, `TRANSIT`, `DRIVE`). `app/services/routes.py` Google Routes API'yi (`computeRoutes`) çağırıyor: `WALK`/`DRIVE` için alternatif başına tek istek, `TRANSIT` intermediates desteklemediği için ardışık çift başına ayrı istek. `orchestrator.py::build_day_plan` planı kurduktan sonra ekliyor. Rota kritik değil: servis çökerse `legs` boş kalır, plan yine döner.
  - Log sorunu çözüldü: hata log'u artık HTTP durum kodu, ulaşım modu ve Google'ın hata gövdesini (ör. "Routes API has not been used in project...") içeriyor; istemci için `PlanAlternative.routes_available` (`weather_available` ile aynı desen) rota alınamadığını bildiriyor.
  - Kapsam dışı: bisiklet/motosiklet modları.
- [x] **Adım adım yol tarifi**: `RouteLeg.steps` (ve `ApproachRoute.steps`) Routes API'nin `navigationInstruction`/`transitDetails` alanlarından dolduruluyor: Türkçe talimat, manevra kodu (ikon için), mesafe/süre; toplu taşıma adımlarında hat, araç türü, yön, biniş/iniş durağı, durak sayısı (`app/services/routes.py::_parse_steps`). Adımlar kritik değil: bozuk adım atlanır, hiç yoksa liste boş kalır.
- [x] **Canlı navigasyon modu** (`frontend/src/screens/NavigationScreen.tsx`, `nav.ts`): plan detayında "Rotayı Başlat" tam ekran harita açar; `watchPosition` ile canlı konum, konumun rota çizgisi üzerindeki ilerlemesinden hesaplanan geçerli adım, bir sonraki manevraya/varışa kalan mesafe, kalan süre/varış saati. Rotadan 50 m (veya GPS doğruluğunun 1,5 katı) uzaklaşınca ardışık iki ölçümde yeniden hesaplama (`/route/approach`), durağa 30 m kala varış kartı ve sıradaki ayağa geçiş. Backend'e ek veri gerekmedi.
- [x] **Kullanıcının konumundan ilk durağa rota**: `POST /route/approach` (`app/api/routes/route.py`) konum + ilk durak + ulaşım şekli alıp tek ayaklık rota (çizgi + adımlar) döner. Konum plan çıktıktan sonra, plan detayında istenir; başlangıç ekranında yalnızca şehir/semt yazılır.
- [x] **LLM şemasından sistemin doldurduğu alanlar çıkarıldı** (`planner.py::_llm_schema`): `legs`, `weather` vb. prompt'ta gösterilmiyor, şema ~3 kat küçüldü (Groq dakikalık token kotası dar).
- [x] **Eksik test kapsamı**: `planner.py`'de `create_plan` ve `resolve_themes` (Groq `conftest.py::fake_groq` ile sahtelenir: geçerli/bozuk/boş yanıt, Groq hatası, uydurma id/tema) ve `orchestrator.py::build_day_plan` uçtan uca (geocoding, hava, mekan, rota HTTP'si `respx` ile; kötü hava daraltması, hava/rota servisi çökmesi, kısmi tema hatası, mekan yokluğu, ulaşım modu) test ediliyor. Testler sahte key'lerle çalışır, `.env` gerekmez.
- [x] **`.env.example` doldurulması**: `PLACES_API_KEY`, `GEOCODING_API_KEY`, `ROUTES_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL` için placeholder değerlerle dolduruldu, hangi Google API'lerinin etkin olması gerektiği yorum olarak yazıldı. Kurulum: `cp .env.example .env`.

## Milestone 2 — AI'nin soru sorabilmesi

- [x] Serbest metin belirsiz/çelişkiliyse (ör. "bir şeyler yapalım" gibi hiçbir sinyal vermiyorsa) `build_day_plan`, `create_plan`'a gitmeden önce `app/services/planner.py::check_ambiguity` ile bir netleştirme sorusu döndürebiliyor (`ClarificationNeeded`). Kontrol kritik değil: Groq çöker/bozuk yanıt dönerse `None`'a düşülür, plana normal devam edilir (`resolve_themes`'teki `DEFAULT_THEMES` deseniyle aynı).
- [x] Karar: ek bir state deposu/tablo YOK. Backend diğer her endpoint gibi stateless kaldı. İstemci, önceki soruyu ve kullanıcının cevabını `PlanRequest.previous_question` / `.clarification_answer` ile bir sonraki istekte geri gönderir; bu ikisi doluysa belirsizlik kontrolü koşulsuz atlanır (tek netleştirme turu, döngü yok).
- [x] `/plan` aynı endpoint'te çok turlu hale getirildi (ayrı bir `/plan/clarify` eklenmedi). `response_model` artık `DayPlan | ClarificationNeeded`; hangi tip döndüğü istemci tarafında ayırt edilir (`ClarificationNeeded` sadece `question` alanı taşır).

## Milestone 3 — Frontend

DESIGN.md'deki ekranlara birebir karşılık gelir.

- [ ] Teknoloji seçimi (framework, state yönetimi, harita kütüphanesi).
- [ ] Konum/şehir seçimi ekranı (Milestone 1'deki geocoding'e bağlı).
- [ ] Tercihler ekranı (bütçe, grup tipi, süre, aktivite türü chip'leri, serbest metin).
- [ ] Sonuç ekranı — alternatif plan kartları + hava rozeti.
- [ ] Plan detay ekranı — durak zaman çizelgesi + harita (Milestone 1'deki rota verisine bağlı).
- [ ] Hata/boş durum ekranları (mekân bulunamadı, plan üretilemedi, hava alınamadı).

## İnovasyon — Hesap, favoriler ve rota düzenleme

Backend'e dokunmadan (auth tamamen frontend+Supabase'de) başlayıp, durak
düzenlemeyle backend'e geri dönen bir seri. Hepsi ücretsiz kalacak şekilde
tasarlandı: yeni Google Places/LLM çağrısı yok, zaten çekilen veriyi yeniden
kullanıyor.

- [x] **Supabase Auth**: giriş opsiyonel (misafir modu kalıyor) — kayıt,
  giriş, şifremi unuttum/sıfırlama (`frontend/src/auth.ts`,
  `screens/AccountScreen.tsx`). Backend bundan habersiz, kullanıcı kimliği
  hiçbir endpoint'te doğrulanmıyor.
- [x] **Kullanıcı adı**: `profiles` tablosu, `auth.users` insert'inde
  `SECURITY DEFINER` trigger ile otomatik satır (signUp'ın `options.data`
  metadata'sından); sonradan Hesabım'dan değiştirilebilir. Kısıtlama yok,
  sadece emoji yasak.
- [x] **Misafir rota limiti**: hesapsız kullanıcı 3 rota oluşturabiliyor;
  4. denemede istek atılmadan "Ücretsiz hakkın doldu" ekranı (giriş/kayıt
  yönlendirmesi) açılıyor (`frontend/src/guestLimit.ts`,
  `screens/LimitScreen.tsx`, `App.tsx::submit`). Sayaç yalnızca başarıyla
  üretilen planlarda artıyor (hata ve netleştirme sorusu sayılmıyor), giriş
  yapmış kullanıcıya uygulanmıyor. Sayaç `localStorage`'da: tarayıcı verisi
  silinince ya da API doğrudan çağrılınca aşılır; kayda yönlendirme amaçlı
  yumuşak bir sınır. Gerçek zorlama için aşağıdaki JWT maddesine bak.
- [x] **Açık/koyu tema anahtarı**: `data-theme` + `localStorage`, sistem
  ayarını ezebiliyor (`frontend/src/theme.ts`).
- [x] **Rota kaydetme/favorileme + link ile paylaşım**: `saved_plans`
  tablosu (RLS: herkes okuyabilir — gizlilik modeli linkteki uuid, sahibi
  silebilir). Yıldız butonu toggle (bas→kaydet, tekrar bas→sil).
  `SharedPlanScreen.tsx` linki açanı (giriş yapmamış olsa da) salt-okunur
  gösterir; mobilde `navigator.share` ile WhatsApp vb.'ye doğrudan paylaşım.
- [x] **Durak sil/sırala**: `POST /route/legs` (`app/api/routes/route.py`,
  mevcut `get_route_legs` servisini yeniden kullanır) — herhangi bir durak
  sırası için ayakları (mesafe/süre/çizgi) yeniden hesaplar.
- [x] **Durak değiştir/taşı/ekle**: `DayPlan.place_pool` plan kurulurken
  çekilen ama kullanılmayan mekan havuzunu döndürür (`orchestrator.py`) —
  yeni bir Places çağrısı yok. Frontend'de kategoriye göre filtreleyip
  (`THEME_TYPES` mirror'ı) durak değiştirme, planlar arası durak taşıma/alma,
  havuzdan/başka plandan yeni durak ekleme (`DetailScreen.tsx::StopEditSheet`).
- [x] **Google Maps linki**: her durağın yanında gerçek fotoğraf/yorumlar
  için Maps'e açılan bir link (`meta.ts::mapsUrl`, sadece `place_id`'den
  kurulur, ekstra çağrı yok).
- [x] **"Ulaşıldı" işaretleme**: kart ve haritadaki pin soluklaşır, durak
  silinmez.

- [x] **Mekan bazlı favorileme**: rota değil, tekil bir mekanı favorileme
  (`favorite_places` tablosu, RLS tamamen özel — `saved_plans`'ın aksine
  select bile herkese açık değil). Plan detayındaki her durakta kalp ikonu
  (`DetailScreen.tsx`), Hesabım'da "Favori Mekanlarım" listesi
  (`AccountScreen.tsx`). Favorilenen bir mekan, "+ Durak ekle" sayfasının
  yeni "Favorilerimden ekle" sekmesinden (`StopEditSheet`) herhangi bir
  rotaya eklenebiliyor — zaten var olan `onPickPlace`/`stopFromPlace`
  akışını aynen kullanıyor, yeni kablolama gerekmedi.
- [x] **Sık gidilen yerler**: "Ulaşıldı" işaretlemesi artık kalıcı — önceden
  tamamen client-side, sekme değişince/durak düzenlenince sıfırlanan geçici
  bir state'ti (`arrived`), şimdi (oturum açıkken) her "Ulaşıldı"ya
  basışta `visited_places` tablosuna ziyaret sayacı işliyor
  (`visitedPlaces.ts::recordVisit`, await'siz/kritik değil). Ana sayfada
  (`LocationScreen.tsx`) en sık gidilen 5 mekan tıklanabilir kartlar olarak
  çıkıyor. Tıklanınca o mekan **garanti** rotada oluyor ama süre/bütçe/grup
  gibi tercihler yine normal akıştan (`PreferencesScreen`) soruluyor —
  kullanıcı "anında 1 duraklı rota" değil, "bu mekanı çapa alan ama
  tercihleri yine soran" bir akış istedi. Garanti backend'de:
  `PlanRequest.anchor_place` verilirse `orchestrator.py::_ensure_anchor_stop`
  LLM'in seçimine güvenmeden mekanı her alternatife durak olarak ekliyor
  (LLM zaten seçtiyse dokunmuyor). Anchor'ın koordinatları zaten bilindiği
  için `city`/geocoding hiç kullanılmıyor — hem ücretsiz hem mekan havuzu
  anchor'ın etrafında aranıyor (daha isabetli).
- [x] **Başlangıç saati seçimi**: Tercihler ekranındaki "13:00 - 16:00" ipucu
  aslında tamamen kozmetikti — tarayıcı saatinden hesaplanıp gösteriliyordu
  ama backend'e hiç gönderilmiyordu, LLM'in "şu an saat kaç" bilgisi yoktu.
  Artık gerçek bir `<input type="time">` ile değiştirilebiliyor
  (`PreferencesScreen.tsx`), `PlanRequest.start_time` ("HH:MM") olarak
  gönderiliyor ve `planner.py::_build_prompt`'a "ilk durak bu saatte ya da
  hemen sonrasında başlasın" talimatıyla ekleniyor. Tamamen ücretsiz (yeni
  API çağrısı yok, sadece prompt'a bir satır).
- [x] **"Kendi rotanı oluştur" linki düzeltildi**: `SharedPlanScreen.tsx`'teki
  bu buton `onClose`'u çağırıyordu, yani App.tsx'in altındaki mevcut view'a
  dönüyordu (çoğu zaman görünürde hiçbir şey değişmiyordu). Artık ayrı bir
  `onCreateOwn` prop'u var, `App.tsx` bunu açıkça `location` view'ına
  yönlendiriyor.
- [ ] **Mekan arama (serbest metinle herhangi bir yeri aratıp rotaya ekleme)**:
  değerlendirildi, kullanıcı şimdilik istemedi — Google Places Text
  Search/Autocomplete gerektirir, favoriler/havuzdan ekle/sık gidilenlerin
  aksine her kullanımda gerçek bir API maliyeti olur.
- [ ] **Mekan fotoğrafı/yorumları**: Google Places'te ek maliyetli
  (fotoğraf: mekan+fotoğraf başına ayrı çağrı; yorumlar: daha pahalı bir
  fiyat katmanı + ayrı Place Details çağrısı gerektiriyor). Ücretsiz bir
  yol bulunursa değerlendirilecek, şu an öncelik değil.
- [ ] **Mekan değiştirirken AI'ya sorma**: şu an sadece kategori chip
  filtresi var (ücretsiz); kullanıcının serbest metinle ("bunu beğenmedim,
  daha sakin bir yer olsun" gibi) tarif etmesi ve LLM'in havuzdan/yeni
  aramadan seçmesi — maliyet/karmaşıklık nedeniyle kapsam dışı tutuldu.
- [ ] **Profil fotoğrafı**: Supabase Storage'da yeni bir bucket + RLS
  policy'leri gerekiyor, henüz kurulmadı.

<<<<<<< feat/toggle_db
 Updated upstream
- [ ] **Backend'in Supabase JWT doğrulaması**: şu an hiçbir endpoint
  kullanıcı kimliği istemiyor; kullanıcıya özel backend mantığı gerekirse
  (ör. plan geçmişini backend'in de görmesi) eklenecek.

=======
>>>>>>> local
## Milestone 4 — Public'e açılış hazırlığı

Uygulama şu an tek kullanıcılı/demo kullanımına göre kuruldu. Herkese açık
yayınlamadan önce yapılacaklar; öncelik sırasıyla (güvenlik/maliyet önce).

### Yayın öncesi zorunlu

- [x] **`/plan` ve `/route/*` için istek sınırı (rate limit)**: `slowapi` ile
  IP bazlı limit — `/plan` `10/dakika`, `/route/approach` `20/dakika`,
  `/route/legs` `30/dakika`, `/geocode`/`/places/nearby`/`/weather`
  `20/dakika`, tanımsız her route için `60/dakika` güvenlik ağı
  (`app/core/rate_limit.py`). `/health` muaf. Testlerde kapalı
  (`RATE_LIMIT_ENABLED=false`, bkz. `tests/conftest.py`) — aksi halde aynı
  `TestClient`'ı tekrar tekrar çağıran testler flaky 429 alabilirdi.
- [x] **Backend'de Supabase JWT doğrulaması**: `app/core/auth.py::get_optional_user_id`
  — geçerli bir Supabase JWT'si (HS256, `SUPABASE_JWT_SECRET`, `aud=authenticated`)
  varsa kullanıcı id'si (`sub`), yoksa/geçersizse `None` (misafir). Tamamen
  opsiyonel: secret ayarlanmazsa her istek misafir sayılır, backend'in
  auth'tan habersiz tasarımı bozulmaz. Şu an sadece `/plan`'da, misafir
  kotasını atlamak için kullanılıyor.
- [x] **Misafir limitini sunucuda zorlama**: `app/core/guest_limit.py` —
  giriş yapmamış istekler için IP+gün bazlı bellek-içi sayaç
  (`guest_daily_plan_limit=3`, frontend'deki `GUEST_PLAN_LIMIT` ile aynı).
  Aşılınca `429` + `X-Guest-Limit-Reached: 1` header'ı; frontend bunu
  localStorage'dan bağımsız olarak "limit" ekranına çevirir
  (`api.ts::ApiError.guestLimit`, `App.tsx::submit`), slowapi'nin genel
  429'uyla karıştırmaz. Bellekte tutuluyor — process yeniden başlayınca/çoklu
  worker'da sıfırlanır; kalıcı/paylaşımlı sayaç gerekirse Redis'e taşınabilir.
- [x] **Girdi sınırları**: `PlanRequest` (koordinat aralıkları, `duration_hours`
  1-12, `free_text`/`city`/`previous_question`/`clarification_answer`
  `max_length`, `categories` en fazla 6 ve yalnızca `THEME_TYPES`
  anahtarları), `ApproachRequest`/`LegStop` koordinat aralıkları,
  `LegsRequest.stops` en fazla 25, `/geocode` `address` en fazla 200,
  `/places/nearby` `types` en fazla 5 eleman + `[a-z_]+` deseni.
- [x] **CORS ve yayın yapılandırması**: `CORSMiddleware` eklendi
  (`Settings.cors_origins`, virgülle ayrılmış, varsayılan dev origin'i);
  `/docs`, `/redoc`, `/openapi.json` artık `DEBUG=false` iken (yayın
  varsayılanı) tamamen kapalı. README'de `uvicorn --proxy-headers` +
  reverse proxy/HTTPS notu eklendi.
- [x] **Supabase RLS denetimi**: panelden `pg_policies`/`pg_class`/`pg_proc`
  üzerinden canlı kurulum çıkarılıp doğrulandı (2026-10-05). `profiles`:
  select herkese açık, insert/update sahibi (`auth.uid() = id`).
  `saved_plans`: select herkese açık (gizlilik modeli uuid'nin tahmin
  edilememesi), insert/delete sahibi, **update policy'si yok** (frontend hiç
  güncelleme yapmıyor). Her iki tabloda da `relrowsecurity=true` — RLS
  gerçekten uygulanıyor (sadece tanımlı olmak yetmez, bu da kontrol edildi).
  `handle_new_user()` trigger fonksiyonu `SECURITY DEFINER` + sabit
  `search_path` (hijack'e karşı) ve parametrik insert (injection riski yok).
  Tam şema artık [`supabase/schema.sql`](supabase/schema.sql)'de — panelde
  değil, repoda. Bilinen kırılgan nokta (düzeltilmedi, bilerek not edildi):
  `profiles.username` NOT NULL ama `handle_new_user()` onu
  `raw_user_meta_data ->> 'username'`'den okuyor — frontend'in `signUp`
  çağrısı metadata'da `username` göndermeyi unutursa/OAuth gibi başka bir
  kayıt yolu eklenirse trigger NOT NULL ihlaliyle patlar ve kayıt tamamen
  başarısız olur.
- [x] **API anahtarı kısıtları ve bütçe uyarısı**: Google Cloud konsolunda
  anahtar kısıtları ve Google/Groq'ta kota + bütçe alarmı kuruldu (manuel,
  kod değişikliği değil).
- [ ] **Sırların yönetimi**: `.env` git'te değil (`.gitignore`), ama yayın
  ortamında ortam değişkeni/secret manager kullanılacak; sızmış olabilecek
  anahtarlar yenilensin.

### Yayın için gerekli altyapı

- [ ] **Deploy**: backend için `Dockerfile` (şu an yok) ve bir barındırma
  seçimi; frontend `vite build` çıktısının statik barındırılması; ortam
  başına (`dev`/`prod`) ayrı Supabase projesi ve API anahtarları.
- [ ] **CI**: GitHub Actions ile `ruff check`, `pytest`, frontend `tsc -b` ve
  `oxlint` (şu an hiçbiri otomatik koşmuyor, `.github/` yok).
- [ ] **Hata izleme ve log**: backend log'larının toplanması, frontend için
  hata raporlama (ör. Sentry); LLM/Google hata oranlarının izlenmesi.
- [ ] **`/health` kapsamı**: şu an yalnızca "ayakta" döner; yayın ortamında
  bağımlılık durumunu (en azından anahtarların tanımlı olması) da yansıtsın.

### Kullanıcıya dönük

- [ ] **Gizlilik politikası ve konum izni metni**: konum yalnızca tarayıcıda
  kullanılıp Routes API'ye gönderiliyor; ne toplandığı/saklandığı açıkça
  yazılsın. Hesap silme (Supabase kullanıcısı ve `saved_plans` kayıtları)
  için bir yol düşünülmeli.
- [ ] **Frontend testleri**: giriş, misafir limiti ve plan akışının testi yok;
  en azından `guestLimit.ts` ve `authErrorText` için birim testleri.
- [ ] **LLM çıktı kalitesi**: planların Türkçe dönmesi prompt'ta zorlandı
  ama rastgele kayma tamamen ölçülmedi; birkaç gerçek çıktıyla kontrol, gerekirse
  `temperature` düşürme.

## Öncelik dışı / fikir aşamasında

- PDF/export olarak plan paylaşımı
