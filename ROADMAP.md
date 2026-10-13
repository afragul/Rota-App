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
- [x] **Misafire istek başına tek alternatif**: `/plan`, giriş yapmamış
  isteklerde `build_day_plan(..., max_alternatives=1)` çağırır; fazla
  alternatifler rota hesabından ÖNCE atılır (atılanlar için Routes çağrısı
  yapılmaz). Giriş yapanlar 2-3 alternatif almaya devam eder. LLM yine birden
  çok alternatif üretir (Groq maliyeti değişmez; prompt'u misafir için "1
  alternatif" yapmak ileride düşünülebilir). `LimitScreen.tsx`'teki "3 rota
  oluşturabilirsin" metni buna göre güncellenmedi.
- [x] **`city` boşluk kontrolü**: `PlanRequest` baş/son boşlukları atar
  (`str_strip_whitespace`); yalnızca boşluktan oluşan `city` koordinat yokken
  reddedilir. Anchor (sık gidilen yer) akışı koordinatla geldiği için etkilenmez.
- [x] **XSS (harita pin'leri)**: `RouteMap.tsx`/`NavMap.tsx` `divIcon` HTML'ine
  `stop.order`/`seg.stopOrder` ham basıyordu; `saved_plans.stops` herkesin
  yazabildiği jsonb olduğundan paylaşım linki üzerinden depolanmış XSS
  mümkündü. Artık `Number(...)` ile basılıyor; `mapsUrl` içinde `place_id`
  `encodeURIComponent` ile kodlanıyor.
- [ ] **`/route/legs` maliyet sınırı**: TRANSIT modunda 25 durak = 24 ayrı
  Routes çağrısı (30 istek/dk ile IP başına ~720 çağrı/dk); durak üst sınırı
  düşürülmeli (10-12) ve bu endpoint'e de misafir kotası düşünülmeli.
- [ ] **Küçük girdi sıkılaştırmaları**: `AnchorPlace` `place_id`/`name`
  `min_length`, `types` öğelerine `max_length`; `LegStop.order` `ge=1, le=25`
  ve benzersizlik; `PlanRequest`'e `extra="forbid"`.
- [ ] **Content-Security-Policy**: `index.html`/web sunucusuna CSP (Leaflet
  karoları ve Supabase adresleri listelenerek); yanlış ayar haritayı/girişi
  bozabileceği için test edilerek eklenmeli.
- [ ] **Rate limit — canlıda doğrulama**: limitler IP'ye göre sayıldığı için
  proxy gerçek istemci IP'sini (`X-Forwarded-For`) iletmeli; uvicorn'a
  dışarıdan doğrudan erişilememeli (`--forwarded-allow-ips='*'` yalnızca
  proxy arkasında güvenli, yoksa istemci başlığı uydurup limiti atlatır).
  Canlıda iki farklı ağdan `/plan` deneyip sayaçların ayrı işlediği elle
  doğrulanmalı.
- [ ] **Rate limit — bellek içi sayaçlar**: slowapi ve `guest_limit.py` sayaçları
  bellekte; yeniden başlatmada sıfırlanır, çoklu worker'da limit worker sayısı
  kadar gevşer. Tek worker ile başla; büyürse Redis.
- [ ] **Rate limit — giriş yapanlar için günlük üst sınır**: giriş yapan
  kullanıcı `/plan`'da yalnızca dakikada 10 ile sınırlı, günlük sınır yok;
  hesap açmak ücretsiz olduğundan maliyet riski var. Kullanıcı bazlı günlük
  sınır düşünülebilir.
- [ ] **Rate limit — Supabase giriş/kayıt/şifre sıfırlama**: bu istekler
  backend'e uğramaz, backend limiti uygulanmaz; Supabase panelindeki
  Auth rate limit ayarları kontrol edilmeli. (Misafir kotası IP'ye bağlı:
  paylaşılan ağlarda kota paylaşılır, VPN ile aşılabilir — kabul edilen sınır;
  asıl koruma Google/Groq harcama limitleri.)
- [ ] **IDOR / sahiplik — `saved_plans` listelenebiliyor**: `saved_plans_select_all`
  (`using (true)`) yüzünden anon anahtarı olan herkes tablonun tamamını
  (`/rest/v1/saved_plans?select=*`) çekebilir; "uuid tahmin edilemez" gizlilik
  modeli yalnızca satır tek tek aranıyorsa geçerli, tablo listelenebiliyorsa
  boşa düşer. Tüm kullanıcıların planları ve `user_id`'leri okunabilir.
  Düzeltme: select'i sahibine kapat (`auth.uid() = user_id`) ve paylaşım
  linkini `security definer` bir fonksiyonla (`get_shared_plan(id uuid)` →
  tek satır, `search_path` sabit) sun; `fetchSharedPlan` buna geçer.
  Canlıdan önce yapılmalı.
- [x] **IDOR / sahiplik — diğer tablolar**: `favorite_places`/`visited_places`
  select-insert-update-delete yalnızca sahibine (`auth.uid() = user_id`),
  `profiles` ve `saved_plans` yazma işlemleri de sahibine kısıtlı; frontend'in
  `userId`'yi kendisinin göndermesi güvenlik sağlamıyor, asıl zorlama RLS'te.
  Backend'de kullanıcıya ait kaynak olmadığı için IDOR yüzeyi yok. (Not:
  `profiles` select herkese açık, kullanıcı adları kamuya açık kabul edildi.)
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
- [x] **Merkezi hata yönetimi**: `app/api/errors.py::register_exception_handlers`
  (`main.py`'de kayıtlı). Tüm `*ServiceError`'lar (geocoding, places, planner,
  routes, weather) tek işleyicide `502 {"detail": ...}` olur; route'lardaki
  tekrarlayan `try/except` kaldırıldı (`plan`, `route`, `geocoding`, `places`;
  `weather` kendi bağlamlı log'u için olduğu gibi bırakıldı). Yakalanmayan
  her hata `500 {"detail": "Beklenmeyen bir hata oluştu"}` döner; ayrıntı
  istemciye gitmez ve log'a yalnızca hata türü + yol yazılır (`str(exc)` bilerek
  yok: httpx hataları URL/key taşıyabilir). Testler: `tests/test_error_handlers.py`.
  Bilinen sınır: Starlette 500'leri CORS katmanının dışından döndürür, yani
  farklı origin'den gelen tarayıcı 500'ü CORS hatası gibi görebilir (aynı
  adres mimarisinde sorun değil). Uvicorn yine de yakalanmayan hatanın tam
  traceback'ini kendi log'una yazar; bu çıktı log toplama hizmetine gidiyorsa
  hassas veri taraması düşünülmeli.
- [x] **Geocoding anahtarı log'a sızıyordu**: Geocoding key'i query string'de
  gittiği için Google 4xx/5xx dönünce `geocoding.py` `str(exc)`'i log'luyordu ve
  `HTTPStatusError` mesajı tam URL'yi (key dahil) taşıdığından anahtar log'a
  yazılıyordu. Artık yalnızca hata türü ve durum kodu loglanıyor; regresyon
  testi `tests/test_geocoding_service.py::test_hata_logunda_api_key_gecmez`.
  Places/Routes key'i header'da, Groq SDK ile gittiği için etkilenmiyordu.
- [ ] **Sırların yönetimi**: `.env` git'te değil (`.gitignore`; git geçmişinde
  de yok, kodda sabit anahtar yok, anahtarlar `SecretStr`), ama yayın
  ortamında ortam değişkeni/secret manager kullanılacak (Dockerfile yazılırken
  `.dockerignore` ile `.env` imaja girmemeli); sızmış olabilecek anahtarlar
  yenilensin; CI kurulunca commit'lerde sır taraması (ör. `gitleaks`).

### Yayın için gerekli altyapı

- [ ] **Yayın mimarisi kararı — frontend ve API aynı adreste**: web sunucusu
  (Nginx/Caddy) `/` için `frontend/dist`'i verir, `/api/*`'i `/api` önekini
  silerek backend'e (`:8000`) iletir (Vite dev proxy'sinin canlı karşılığı;
  frontend zaten göreli `/api/...` kullanıyor). Aynı origin olduğu için CORS
  devreye girmez; yine de `CORS_ORIGINS` canlı adrese ayarlanır, `localhost`
  çıkarılır. Proxy gerçek istemci IP'sini `X-Forwarded-For` ile iletmeli,
  yoksa rate limit ve misafir kotası tüm kullanıcılar için tek IP sayar.
  Birden çok worker çalıştırılırsa misafir sayacı worker başına ayrı tutulur
  (bellek içi) — tek worker ya da Redis.
- [ ] **Barındırma, alan adı ve bütçe kararı (açık)**: henüz seçilmedi.
  HTTPS sertifikası ücretsiz (Let's Encrypt; Caddy otomatik alır/yeniler,
  Nginx'te Certbot, Render/Railway/Vercel gibi hizmetlerde kendiliğinden
  gelir). Ücretli olabilecekler: alan adı (IP adresine sertifika alınamaz;
  yıllık küçük bir ücret) ve barındırma (ücretsiz katmanlar sınırlı/uyuyabilir,
  VPS aylık ücretli). Test için barındırma hizmetinin ücretsiz alt adresi
  yeterli; gerçek kullanıcıya açarken kendi alan adı alınmalı (alt adres
  güven vermez, sonradan adres değişirse paylaşım linkleri bozulur). Karar
  verilince Dockerfile/web sunucusu ayarı buna göre yazılacak (aşağıdaki
  "Deploy" maddesi).
- [ ] **HTTPS kontrolleri (canlıya alınca)**: sertifika geçerliliği ve
  otomatik yenileme, `http://` → `https://` yönlendirmesi, `Strict-Transport-Security`
  başlığı (önce kısa süreyle), tarayıcı Console'da mixed content olmaması
  (`http://` taraması), `uvicorn --proxy-headers` ile `X-Forwarded-Proto`/`-For`
  iletimi. Konum izni (`navigator.geolocation`) yalnızca HTTPS'te çalıştığı
  için navigasyon modu telefonda canlı adreste ayrıca denenmeli; Supabase
  e-posta bağlantıları (`https` canlı adres) de kontrol edilmeli.
- [ ] **Supabase canlı ayarları**: ücretli pakete geçiş ve yedekleme, Site
  URL/Redirect URLs'e canlı adres (localhost çıkarılır), e-posta doğrulama,
  canlı için kendi SMTP'si (varsayılan e-posta servisi çok düşük limitli),
  `SUPABASE_JWT_SECRET`'in canlı ortamda doldurulması (boşsa herkes misafir).
  Yedekleme: otomatik yedeklerin açık olduğunu panelden doğrula ve ayrı bir
  test projesinde bir kez geri yüklemeyi dene (yedekleme kapsamı/saklama süresi
  pakete göre değişir, güncel koşullar Supabase sayfasından doğrulanmalı).
  PITR, kendi `pg_dump` kopyası ve yazılı felaket planı kullanıcı sayısı
  artınca değerlendirilecek. `.env` içeriğinin kopyası da güvenli bir yerde
  (şifre yöneticisi/secret yöneticisi) tutulmalı.
- [ ] **Deploy**: backend için `Dockerfile` (şu an yok) ve bir barındırma
  seçimi; frontend `vite build` çıktısının statik barındırılması; ortam
  başına (`dev`/`prod`) ayrı Supabase projesi ve API anahtarları.
- [ ] **CI**: GitHub Actions ile `ruff check`, `pytest`, frontend `tsc -b` ve
  `oxlint` (şu an hiçbiri otomatik koşmuyor, `.github/` yok).
- [ ] **Bağımlılık taraması (dependency scanning)**: bilinen güvenlik
  açıkları için düzenli ve otomatik tarama.
  - Frontend: `npm audit` (canlıya giden paketlerde `--omit=dev` ile 0 açık,
    2026-10-13). Geliştirme araçlarında `braces` (yüksek, yığın taşması DoS)
    raporlanıyor; zincir `braces` → `micromatch`/`chokidar` → `tailwindcss` 3.x.
    Düzeltme Tailwind 4'e geçişi (büyük sürüm, arayüzü etkileyebilir)
    gerektiriyor; yalnızca derleme/geliştirme zamanında çalıştığı için acil
    değil, Tailwind yükseltmesi yapılırken çözülecek.
  - Backend: `pip-audit` henüz kurulu değil/çalıştırılmadı. `pyproject.toml`'daki
    sürümler sabit değil ve kilit dosyası yok (`uv.lock`/`requirements.txt`),
    yani canlıda kurulacak sürüm kuruluma göre değişir; sürümleri sabitleyen
    bir kilit dosyası üretilmeli.
  - Otomasyon: CI kurulunca (yukarıdaki CI maddesi) `npm audit` ve `pip-audit`
    her değişiklikte koşsun; GitHub Dependabot için ayar dosyası eklensin
    (açık bir pakette otomatik güncelleme önerisi açar).
- [ ] **Hata izleme ve log**: backend log'larının toplanması, frontend için
  hata raporlama (ör. Sentry); LLM/Google hata oranlarının izlenmesi.
- [ ] **`/health` kapsamı**: şu an yalnızca "ayakta" döner; yayın ortamında
  bağımlılık durumunu (en azından anahtarların tanımlı olması) da yansıtsın.
- [ ] **Log yapısı**: her isteğe bir istek numarası (request id) verilip log
  satırlarına yazılsın; log biçimi canlıda yapılandırılmış (JSON) olabilir.
  Şu an düz metin, yalnızca konsola, seviye sabit `INFO`.
- [ ] **Güvenlik olayları için audit log**: şu an hiçbiri kaydedilmiyor.
  `warning` olarak (IP + yol + olay; token'ın kendisi ASLA) şunlar yazılmalı:
  misafir kotası aşıldı (`guest_limit.py`), rate limit aşıldı (slowapi'nin
  varsayılan işleyicisi log yazmıyor), geçersiz/süresi dolmuş JWT
  (`auth.py` sessizce `None` döndürüyor). Giriş yapmış kullanıcının `/plan`
  isteği kimlik (`sub`) ile kaydedilmeli mi, KVKK değerlendirmesiyle birlikte
  karar verilecek. Kaydet/sil/favori gibi veri değişiklikleri backend'e
  uğramaz; bunların izi Supabase panelindeki Auth/veritabanı log'larındadır
  (saklama süresi plana bağlı, kontrol edilmeli). Uvicorn erişim log'unun
  proxy arkasında doğru istemci IP'sini yazdığı doğrulanmalı.
- [ ] **Log'a girenlerin temizlenmesi**: kullanıcı metni (`geocoding.py` adres,
  `orchestrator.py` şehir) satır sonu karakterleri temizlenerek yazılmalı (log
  injection); koordinatlar (`weather.py`, `orchestrator.py`) ve LLM yanıtından
  alıntı (`planner.py`, ilk 300 karakter; kullanıcı notu içerebilir) kişisel
  veri sayılabileceğinden mümkünse kaba tutulmalı ya da loglanmamalı; log
  saklama süresi belirlenmeli.

### Kullanıcıya dönük

- [ ] **Gizlilik politikası ve konum izni metni**: konum yalnızca tarayıcıda
  kullanılıp Routes API'ye gönderiliyor; ne toplandığı/saklandığı açıkça
  yazılsın. Hesap silme (Supabase kullanıcısı ve `saved_plans` kayıtları)
  için bir yol düşünülmeli. Ayrıntısı aşağıdaki KVKK maddelerinde.

#### KVKK (6698 sayılı Kanun) hazırlığı

Not: bu bölüm bir veri envanteri ve yapılacaklar listesidir, hukuki görüş
değildir. Metinler ve yükümlülüklerin kapsamı (açık rıza gerekip gerekmediği,
VERBİS kaydı, yurt dışı aktarım şartları) bir hukuk uzmanıyla netleştirilmeli.

**Veri envanteri (koddan çıkarıldı):**

| Veri | Nerede | Kaynak |
|---|---|---|
| E-posta, şifre (Supabase Auth'ta), kullanıcı adı | Supabase `auth.users`, `profiles` | Kayıt |
| Kaydedilen planlar (durak, konum, `user_id`) | Supabase `saved_plans` | Kullanıcı |
| Favori mekanlar (ad, adres, koordinat) | Supabase `favorite_places` | Kullanıcı |
| Ziyaret geçmişi (mekan, koordinat, ziyaret sayısı, son ziyaret zamanı) | Supabase `visited_places` | "Ulaşıldı" işaretlemesi |
| Şehir/adres metni, koordinat, serbest metin, tercihler | Backend isteği; Google/Groq/Open-Meteo'ya iletilir; kısmen log'a düşer | Plan formu |
| IP adresi | Rate limit ve misafir kotası (bellekte), uvicorn erişim log'u | Her istek |
| Anlık cihaz konumu (navigasyon) | `watchPosition` → `/route/approach` → Google Routes; kodda kalıcı saklandığı yer görülmedi | Cihaz |
| Oturum token'ı, tema, misafir plan sayacı | Tarayıcı `localStorage` (çerez yok) | İstemci |

**Üçüncü taraflar / yurt dışı aktarım:** Google (Geocoding, Places, Routes),
Groq (serbest metin, tercihler, mekan listesi LLM'e gider), Open-Meteo
(koordinat), Supabase (hesap ve kayıtlar). Her birinin sunucu bölgesi ve
sözleşme koşulları kontrol edilip aydınlatma metninde yazılmalı; yurt dışına
aktarım şartları hukuken değerlendirilmeli. Supabase projesinin bölgesi
(AB/ABD vb.) seçilmiş mi bakılmalı.

**Yapılacaklar:**
- [ ] **Aydınlatma metni**: veri sorumlusu kimliği ve iletişim, hangi verinin
  hangi amaçla ve hangi hukuki sebeple işlendiği, kimlere aktarıldığı, saklama
  süresi, ilgili kişi hakları ve başvuru yolu. Kayıt/giriş ekranından ve
  alt bilgiden erişilebilir olmalı.
- [ ] **Konum için bilgilendirme/rıza metni**: şehir yazarak plan, cihaz
  konumu (navigasyon) ve ziyaret geçmişi ayrı ayrı anlatılsın; konumun açık
  rıza gerektirip gerektirmediği hukuki olarak netleştirilsin. Tarayıcı konum
  izni isteminden önce kısa bir açıklama gösterilsin.
- [ ] **Silme hakkı**: hesap silme akışı (Supabase kullanıcısı, `profiles`,
  `saved_plans`, `favorite_places`, `visited_places`; tabloların hepsi
  `on delete cascade` ile `auth.users`'a bağlı, yani kullanıcı silinince
  satırlar gider; ama bu akışı kullanıcı kendi başına başlatamıyor). Ayrıca
  `visited_places` için bilerek DELETE policy'si yok (`schema.sql`); kullanıcı
  ziyaret geçmişini temizleyemiyor, bu silme hakkıyla çelişir.
- [ ] **Erişim / taşınabilirlik**: kullanıcının kendi verisini görebilmesi ve
  dışa aktarabilmesi (Hesabım'dan JSON indir gibi).
- [ ] **Paylaşılan planlar**: `saved_plans` şu an herkese listelenebilir (bkz.
  "IDOR / sahiplik" maddesi); bu durum kişisel veri güvenliği yükümlülüğü
  açısından da ele alınmalı, kullanıcı paylaşımı kapatabilmeli.
- [ ] **Saklama süreleri**: log'lar, `visited_places` (ziyaret geçmişi),
  kullanılmayan hesaplar için süre belirlenip uygulanmalı.
- [ ] **Veri ihlali süreci**: sızıntı olursa kim, neyi, kime ne zamana kadar
  bildirir (mevzuattaki süreler hukuki olarak doğrulanmalı); log ve audit
  kayıtları buna dayanak olacak.
- [ ] **VERBİS / kayıt yükümlülüğü**: uygulamanın işletici statüsüne göre
  gerekip gerekmediği hukuken kontrol edilmeli.
- [ ] **Sağlayıcı sözleşmeleri**: Google, Groq, Supabase için veri işleme
  şartları/DPA incelenmeli; Groq'a giden kullanıcı serbest metninin
  eğitimde kullanılmadığı ayarı doğrulanmalı.
- [ ] **Çocuklar**: yaş sınırı ve ebeveyn onayı gerekliliği değerlendirilmeli.
- [ ] **Frontend testleri**: giriş, misafir limiti ve plan akışının testi yok;
  en azından `guestLimit.ts` ve `authErrorText` için birim testleri.
- [ ] **LLM çıktı kalitesi**: planların Türkçe dönmesi prompt'ta zorlandı
  ama rastgele kayma tamamen ölçülmedi; birkaç gerçek çıktıyla kontrol, gerekirse
  `temperature` düşürme.

## Öncelik dışı / fikir aşamasında

- PDF/export olarak plan paylaşımı
