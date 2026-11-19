# Yol Haritası

Backend önce tamamlanıp sonra frontend'e geçilecek şekilde sıralandı. README.md "Şu anki durum" ve DESIGN.md "Sonraki adımlar" bölümleriyle tutarlıdır; oradaki eksikler burada somut görevlere bölündü.

## Milestone 1 — Backend'i tamamla

- [x] **Şehir/adres → koordinat çözümleme**: `/plan` artık `latitude`/`longitude` ikilisi yerine `city` de kabul ediyor (`app/services/geocoding.py`, Google Geocoding API). `GEOCODING_API_KEY` bunun için kullanılıyor. Bağımsız test için `GET /geocode` eklendi.
  - **[x] 2026-11-17 düzeltme — aynı isimli yer karışması**: "Alsancak" yazınca İzmir'deki değil Kıbrıs'taki (Girne) Alsancak'a gidiyordu (region biası yoktu, Google ilk sonucu seçiyordu). Ücretsiz çözüm: `geocode_address` isteğine `region=tr` eklendi (yalnızca öncelik ipucu, kısıtlama değil) — gerçek API'yle doğrulandı, artık düz "Alsancak" İzmir/Konak'ı buluyor. **Açık/bilinçli trade-off:** bu, gerçekten yurt dışına plan yapan birinin aynı isimli yabancı bir adresini de Türkiye'ye kaydırabilir; yazarken açılır öneri listesi (Google Places Autocomplete, ücretli) daha doğru bir çözüm ama şimdilik ücretsiz olanla devam edildi.
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

- [x] **Teknoloji seçimi**: Vite + React + TypeScript + Tailwind + Leaflet.
  Router kütüphanesi yok — `App.tsx` elle yazılmış bir state machine
  (`view` union'ı), state yönetimi React'in kendi `useState`/prop drilling'i
  (ayrı bir kütüphane yok). Bkz. `CLAUDE.md`'deki "Frontend" bölümü.
- [x] **Konum/şehir seçimi ekranı**: `screens/LocationScreen.tsx` — şehir
  arama + (giriş yapılmışsa) "Sık Gidilen Yerlerin" hızlı seçim kartları.
- [x] **Tercihler ekranı**: `screens/PreferencesScreen.tsx` — grup tipi,
  süre, bütçe, kategori chip'leri, serbest metin, başlangıç saati seçimi.
- [x] **Sonuç ekranı**: alternatif plan kartları + hava rozeti —
  `screens/ResultsScreen.tsx`.
- [x] **Plan detay ekranı**: `screens/DetailScreen.tsx` — durak zaman
  çizelgesi + harita (`components/RouteMap.tsx`, Leaflet).
- [x] **Hata/boş durum ekranları**: mekân bulunamadı/plan üretilemedi
  (`components/ErrorBanner.tsx`), netleştirme sorusu (`screens/ClarifyScreen.tsx`),
  misafir limiti (`screens/LimitScreen.tsx`).

## İnovasyon — Hesap, favoriler ve rota düzenleme

Backend'e dokunmadan (auth tamamen frontend+Supabase'de) başlayıp, durak
düzenlemeyle backend'e geri dönen bir seri. (Geçmiş notu: hesap ve kayıtlar
artık Supabase'te değil, kendi PostgreSQL'imizde — bkz. "Milestone 5". Bu
bölümdeki Supabase maddeleri tarihsel kayıt olarak bırakıldı.) Hepsi ücretsiz kalacak şekilde
tasarlandı: yeni Google Places/LLM çağrısı yok, zaten çekilen veriyi yeniden
kullanıyor.

- [x] **Supabase Auth**: giriş opsiyonel (misafir modu kalıyor) — kayıt,
  giriş, şifremi unuttum/sıfırlama (`frontend/src/auth.ts`,
  `screens/AccountScreen.tsx`). Backend bundan habersiz, kullanıcı kimliği
  hiçbir endpoint'te doğrulanmıyor. **Güncel durum:** Supabase Auth kaldırıldı,
  yerine backend'in kendi kayıt/giriş sistemi geldi (bkz. Milestone 5).
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
- [x] **Mekan arama (serbest metinle herhangi bir yeri aratıp rotaya ekleme)**:
  yapıldı. `GET /places/search` (Google Places Text Search, `locationBias` ile planın
  bölgesine yakın sonuçlar öne çıkar, bölgeyle sınırlı değil); arayüzde durak
  ekle/değiştir sayfasında "Mekan ara" sekmesi (`components/PlaceSearch.tsx`).
  Her arama ücretli olduğu için: yazdıkça değil yalnızca "Ara"ya basınca istek
  gider, `20/dakika` IP limiti, misafir günlük 20 / hesap günlük 100 arama
  (ayrı `searches` sayacı, migration 0006). **Açık:** gerçek Google anahtarıyla
  uçtan uca denenmedi (testler sahte yanıtla); alan maskesi `searchNearby` ile aynı
  (puan alanı yüzünden daha pahalı fiyat katmanına girebilir: Google faturasında
  kontrol edilmeli); arayüz tarayıcıda elle denenmedi.
- [ ] **Mekan fotoğrafı/yorumları** (karar: şimdilik yok, ileride bir güncellemede): Google Places'te ek maliyetli
  (fotoğraf: mekan+fotoğraf başına ayrı çağrı; yorumlar: daha pahalı bir
  fiyat katmanı + ayrı Place Details çağrısı gerektiriyor). Ücretsiz bir
  yol bulunursa değerlendirilecek, şu an öncelik değil.
- [ ] **Mekan değiştirirken AI'ya sorma**: şu an sadece kategori chip
  filtresi var (ücretsiz); kullanıcının serbest metinle ("bunu beğenmedim,
  daha sakin bir yer olsun" gibi) tarif etmesi ve LLM'in havuzdan/yeni
  aramadan seçmesi — maliyet/karmaşıklık nedeniyle kapsam dışı tutuldu.
- [ ] **Profil fotoğrafı** (karar: yok, dosya yüklemesi yapılmayacak): bunun yerine ileride
  basit bir seçim: renk seçtirme ya da hazır avatarlar (bitmoji tarzı). Dosya
  depolama ve KVKK yükü olmadığı için tercih edildi.

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
  kotasını atlamak için kullanılıyor. **Güncel durum:** artık Supabase JWT'si
  değil, backend'in kendi ürettiği JWT doğrulanıyor (`app/core/security.py`,
  zorunlu `JWT_SECRET`); `get_optional_user_id` aynı sözleşmeyi koruyor.
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
- [x] **`/route/legs` maliyet sınırı**: `MAX_LEG_STOPS` 25 → 12
  (`app/schemas/plan.py`) — TRANSIT modunda artık en fazla 11 ayrı Routes
  çağrısı tetiklenebiliyor (önceden 24). Ayrıca bu endpoint'e `/plan`'daki
  günlük misafir kotasından ayrı, kendi sayacı eklendi: `guest_limit.py`'deki
  `enforce_guest_legs_limit` + yeni `guest_daily_legs_limit` ayarı
  (varsayılan 20 — durak düzenleme, plan üretmekten çok daha sık tetiklenen
  bir aksiyon olduğu için `guest_daily_plan_limit`'ten kasıtlı olarak daha
  yüksek). `recompute_legs` artık `get_optional_user_id`'yi de kullanıyor;
  bunun doğru çalışması için frontend'in `fetchLegs`'i artık `accessToken`
  alıp `Authorization` header'ında gönderiyor (`api.ts`, `DetailScreen.tsx`)
  — aksi halde giriş yapmış kullanıcılar da yanlışlıkla misafir sayılırdı.
  Testler: `tests/test_guest_limit.py`, `tests/test_route_endpoint.py`.
- [x] **Küçük girdi sıkılaştırmaları**: `AnchorPlace.place_id`/`.name`'e
  `min_length=1`, `.types` listesindeki her öğeye `max_length=50`;
  `LegStop.order`'a `ge=1, le=MAX_LEG_STOPS`; `LegsRequest`'e order'ların
  benzersiz olmasını zorlayan bir `field_validator`; `PlanRequest`'e
  `extra="forbid"` (tanımsız bir alan artık sessizce yok sayılmıyor, 422
  dönüyor). Testler: `tests/test_plan_schema.py`.
- [x] **Content-Security-Policy**: `frontend/vite.config.ts`'e yalnızca
  **build** sırasında (`apply: 'build'`) `index.html`'e bir CSP meta tag'i
  enjekte eden bir plugin eklendi — dev sunucusunda eklenmiyor, çünkü
  `@vitejs/plugin-react`'in Fast Refresh preamble'ı satır içi bir `<script>`
  enjekte ediyor ve bu, `script-src`'de `'unsafe-inline'` olmadan HMR'ı
  kırardı; build çıktısında böyle bir inline script olmadığı için orada
  `script-src 'self'` sıkı kalabiliyor (önceki XSS açığının asıl vektörü
  olan satır içi olay işleyicilerine — `onerror=`, `onclick=` vb. — karşı
  ek bir savunma katmanı). `style-src` Tailwind/React'in olası satır içi
  stilleri için `'unsafe-inline'` içeriyor (script-src'de yok — asıl risk
  orada). `img-src` Leaflet karoları için `https://*.tile.openstreetmap.org`,
  `connect-src` yalnızca `'self'` (`/api/*` aynı origin; Supabase kaldırılınca
  `https://*.supabase.co` izni de çıkarıldı). `frame-ancestors` meta tag'de desteklenmediği
  için (yalnızca HTTP header) eklenmedi — gerçek web sunucusu kurulunca not
  edildi. Test: `npm run build` sonrası `frontend/dist`'i backend'e proxy'leyen
  yerel bir sunucu üzerinden Playwright ile gerçek bir plan üretimi (harita
  dahil, `RouteMap.tsx`'teki Leaflet karoları ve özel `divIcon` pin'leri
  sorunsuz yüklendi) ve Supabase'e giden bir `fetch` denendi — hiçbir CSP
  ihlali görülmedi.
- [ ] **Rate limit — canlıda doğrulama**: limitler IP'ye göre sayıldığı için
  proxy gerçek istemci IP'sini (`X-Forwarded-For`) iletmeli; uvicorn'a
  dışarıdan doğrudan erişilememeli (`--forwarded-allow-ips='*'` yalnızca
  proxy arkasında güvenli, yoksa istemci başlığı uydurup limiti atlatır).
  Canlıda iki farklı ağdan `/plan` deneyip sayaçların ayrı işlediği elle
  doğrulanmalı.
- [ ] **Rate limit — bellek içi sayaçlar**: slowapi ve `guest_limit.py` sayaçları
  bellekte; yeniden başlatmada sıfırlanır, çoklu worker'da limit worker sayısı
  kadar gevşer. Tek worker ile başla; büyürse Redis.
- [x] **Rate limit — giriş yapanlar için günlük üst sınır**: hesap başına günlük
  kota, veritabanında (`daily_usage`, migration 0004): `/plan` 30, `/route/legs`
  300 (`USER_DAILY_PLAN_LIMIT`/`USER_DAILY_LEGS_LIMIT`). Artırma tek koşullu
  `UPDATE` ile atomik; gün Türkiye saatine göre; yeniden başlatmada sıfırlanmaz,
  çoklu worker'da paylaşılır. Gerçek Postgres'te 25 eşzamanlı oturumla denendi
  (tam 5 izin / 20 red / 0 hata, limit 5). Açık: limit değerleri tahmini, gerçek
  kullanımla ayarlanmalı; kota dolunca frontend anlaşılır bir ekran gösteriyor
  ("Günlük hakkın doldu", "Tekrar Dene" gizli) ama kalan hak / sıfırlanma saati
  gösterimi yok ve `/route/legs` kotası dolunca durak düzenlemede rota çizgisi
  sessizce güncellenmiyor; misafir sayacı hâlâ bellek içi (aşağıdaki "bellek içi sayaçlar" maddesi).
- [x] **Rate limit — giriş/kayıt**: auth artık backend'de; `/auth/register`
  `5/dakika`, `/auth/login` `10/dakika`, `/auth/refresh` `30/dakika`,
  `/me/password` `5/dakika`, `/auth/forgot` `5/dakika` (+ hesap başına 60 sn
  bekleme), `/auth/reset` `10/dakika` (IP bazlı). Açık kalan: hesap bazlı
  kilitleme (aynı e-postaya dağıtık denemeler IP limitini aşar). (Misafir kotası IP'ye bağlı:
  paylaşılan ağlarda kota paylaşılır, VPN ile aşılabilir — kabul edilen sınır;
  asıl koruma Google/Groq harcama limitleri.)
- [x] **IDOR / sahiplik — `saved_plans` listelenebiliyordu (düzeltildi,
  2026-10-19)**: `saved_plans_select_all` (`using (true)`) yüzünden anon
  anahtarı olan herkes tablonun tamamını (`/rest/v1/saved_plans?select=*`)
  çekebiliyordu; "uuid tahmin edilemez" gizlilik modeli yalnızca satır tek
  tek aranıyorsa geçerliydi, tablo listelenebildiği için boşa düşüyordu.
  Düzeltme: `saved_plans_select_own` policy'siyle select sahibine kapatıldı
  (`auth.uid() = user_id`); paylaşım linki artık `get_shared_plan(plan_id
  uuid)` adlı `SECURITY DEFINER` bir fonksiyonla sunuluyor (RLS'i bilerek
  atlar ama sadece tek bir id için, `search_path` sabit —
  `supabase/schema.sql`). `frontend/src/savedPlans.ts::fetchSharedPlan`
  artık ham `select` yerine `supabase.rpc('get_shared_plan', ...)` çağırıyor.
  **Supabase'de `supabase/schema.sql`'in tamamının tekrar çalıştırılması
  gerekiyor** (yeni policy + fonksiyon panelde henüz yok).
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
- [x] **Supabase RLS denetimi** (tarihsel; Supabase kaldırıldı — sahiplik
  kontrolü artık backend'de, bkz. Milestone 5): panelden `pg_policies`/`pg_class`/`pg_proc`
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
- [x] **Sır taraması (gitleaks)**: `.github/workflows/ci.yml`'e `gitleaks/gitleaks-action@v2`
  job'u eklendi (push/PR'daki yeni commit'leri tarar, tüm geçmişi değil).
  Lokal Docker ile tam geçmiş (`--all`) taranarak doğrulandı: gerçek bir anahtar/sır
  bulunamadı. 3 "sahte test/CI JWT_SECRET'i" yanlış pozitifi `.gitleaksignore`'a
  fingerprint'leriyle eklendi (örn. `ci.yml`'deki `ci-icin-sahte-jwt-anahtari`).
  1 bulgu daha var (`frontend/dist/...js` içinde eski bir Supabase anon JWT) ama bu
  yalnızca lokal bir `git stash`'te (`refs/stash`) — hiç GitHub'a pushlanmadı, CI'ın
  gördüğü geçmişte yok, görmezden gelinebilir (temizlemek istenirse `git stash list`).
  **Resend API anahtarı sızdı mı sorusu bu taramayla da netleşti:** repoda (ne
  committed dosyalarda ne git geçmişinde, stash dahil) gerçek bir Resend anahtarının
  izi yok — gerçek anahtar (varsa) yalnızca onu test eden kişinin kendi `.env`'inde
  durmuş olmalı, bu repoya hiç girmemiş. Yine de emin olmak maliyetsiz olduğu için
  Resend panelinden o anahtarın iptal edilip yenisinin üretilmesi öneriliyor —
  bu adım kod dışı, hesaba erişimi olan kişi tarafından yapılmalı.
- [ ] **Sırların yönetimi (geri kalan)**: `.env` git'te değil (`.gitignore`;
  git geçmişinde de yok, kodda sabit anahtar yok, anahtarlar `SecretStr`), ama
  yayın ortamında ortam değişkeni/secret manager kullanılacak (Dockerfile
  yazılırken `.dockerignore` ile `.env` imaja girmemeli).
- [ ] **Üçüncü taraf ToS uyumluluğu (2026-11-17, mimari kısmı henüz karar verilmedi)**:
  canlıya/gerçek kullanıcıya açmadan önce gözden geçirilmeli, düşük trafikte
  risk düşük ama büyüdükçe artıyor (ihlal = dava değil, erişimin kesilmesi):
  - **Google Maps Platform + Leaflet/OSM birlikteliği — DOĞRULANDI (2026-11-19)**:
    Google Maps Platform Service Specific Terms'ten (kullanıcı tarayıcıdan okuyup
    paylaştı) birebir alıntı: **Places API** "14.2 No use with a non-Google map.
    Customer must not use Google Maps Content from the Places API in conjunction
    with a non-Google map." — **Routes API** "19.2 No use with a non-Google map.
    Customer must not use Google Maps Content from the Routes API in conjunction
    with a non-Google map." Mimarimiz tam bu kalıba giriyor: `RouteMap.tsx`/`NavMap.tsx`
    Leaflet/OSM karosu üzerine Places mekanlarını ve Routes rota çizgisini basıyor —
    yani şu an bu madde teknik olarak ihlal ediliyor. Karar iki seçenek arasında,
    ikisi de mimariyi/bütçeyi değiştirir: (a) Leaflet'i Google Maps JS API ile
    değiştirmek (önerilen — Places/Routes verisi aynen kalır, yalnızca harita
    bileşeni değişir, izole bir değişiklik), (b) Places/Routes'u Google-dışı bir
    kaynakla değiştirmek (örn. Nominatim/Overpass + OSRM — mekan verisi kalitesi
    düşer: puan/yorum sayısı gibi Google'a özgü alanlar kaybolur). Google'ın yeni
    "Places UI Kit" ürünü (15.1) bu kısıtı kendi widget'ları için bilerek geçersiz
    kılıyor ("This clause will prevail over the No Use with Non-Google Maps clause"),
    ama (i) hazır/kendi tasarımımızla uyuşmayan bir UI bileşeni ve (ii) Routes
    içeriği için aynı muafiyet yok — tek başına çözüm değil. Henüz kod değişikliği
    yapılmadı, karar bekliyor.
  - **Google verisi saklama — DÜZELTİLDİ (2026-11-19)**: aynı belgeden doğrulanan
    **14.3/19.3**: "Customer may temporarily cache latitude and longitude values
    from the Places/Routes API for up to 30 consecutive calendar days, after which
    Customer must delete the cached latitude and longitude values." (yalnızca
    enlem/boylam için geçerli — `place_id`/ad/adres bu maddenin kapsamında değil,
    süresiz saklanabilir.) `favorite_places`/`visited_places` koordinatı süresiz
    saklıyordu; artık **hiç saklamıyor** (`ea5e2f5c949e` migration'ı,
    `app/db/models.py::_PlaceMixin`, `app/schemas/place_record.py::PlaceIn`).
    Bunun yerine yeni `GET /places/{place_id}/location` (`app/services/places.py::
    get_place_location`, en ucuz "Location Only" alan maskesiyle, `/places/search`
    ile aynı misafir/hesap arama kotasını paylaşır) bir mekan GERÇEKTEN
    kullanılacağı an (favoriden/sık gidilenden rotaya durak ya da çapa eklenirken)
    konumu anlık çeker, hiçbir yere kaydetmez. Liste ekranları (Favorilerim, Sık
    Gidilenler) zaten yalnızca ad/adres/puan gösterdiği için hiç etkilenmedi.
    Gerçek Google API'siyle uçtan uca doğrulandı (favori eklendi, listede
    koordinat yok, gerçek bir `place_id` ile `/location` doğru koordinatı döndü).
    Testler: `tests/test_places_service.py` (get_place_location), yeni
    `tests/test_place_location_route.py`, `tests/test_places_records_routes.py::
    test_favori_kaydinda_koordinat_saklanmaz`.
  - **OSM tile politikası — doğrulandı**: `operations.osmfoundation.org/policies/tiles`
    canlı sayfası okundu — yoğun/ticari trafikte bildirimsiz erişim kesilebileceği,
    bunun yerine ücretli bir sağlayıcı (MapTiler/Stadia Maps/Mapbox/Jawg) veya
    kendi sunucunun önerildiği doğrulandı. Kodda da doğrulandı: `NavMap.tsx:30`
    ve `RouteMap.tsx:22` hâlâ çıplak `tile.openstreetmap.org`'a istek atıyor.
    Canlıya açmadan önce bir sağlayıcıya geçilmeli (CSP `img-src` de buna göre).
  - **Groq**: groq.com/terms-of-use API'yi kapsamıyor ("These Terms do not apply
    to you in connection with your use of Groq's cloud services") — asıl
    sözleşme console hesabında kabul edilen "Groq Services Agreement" (herkese
    açık değil); ticari kullanım/veri saklama/kota maddeleri oradan kontrol
    edilmeli.

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
  için navigasyon modu telefonda canlı adreste ayrıca denenmeli. Refresh
  cookie'si `Secure` olduğu için (`COOKIE_SECURE=true`) HTTPS olmadan oturum
  yenilenmez; bu da bu maddeyi zorunlu kılar.
- [ ] **PostgreSQL canlı ayarları** (Supabase'in yerine): `db` servisinin
  `ports:` satırı sunucuda tamamen silinmeli (veritabanı internete açık
  olmamalı, yalnızca `api` konteyneri `db` adıyla erişmeli); `POSTGRES_PASSWORD`
  PC'dekinden bağımsız, uzun ve rastgele olmalı; düzenli `pg_dump` yedeği ve en
  az bir kez geri yükleme denemesi (`pgdata` volume'u tek başına yedek değildir);
  `JWT_SECRET` canlıya özel üretilmeli; `COOKIE_SECURE=true` (varsayılan) ve
  `REFRESH_COOKIE_PATH` tarayıcının gördüğü adresle eşleşmeli. `.env` içeriğinin
  kopyası güvenli bir yerde (şifre yöneticisi/secret yöneticisi) tutulmalı.
- [ ] **Deploy**: `Dockerfile` ve `docker-compose.yml` var (yerelde `db` +
  `api`); henüz yok: bir barındırma seçimi, frontend `vite build` çıktısının
  statik barındırılması ve `/api` altında API ile aynı adreste sunulması, ortam
  başına (`dev`/`prod`) ayrı veritabanı ve API anahtarları. Migration'lar `api`
  konteyneri açılırken otomatik uygulanır (`docker-entrypoint.sh`, tek kopya
  varsayımı; çok kopyada `RUN_MIGRATIONS=false`). `api` imajı derlenip denendi: konteynerde `alembic upgrade head`, `/health` ve kayıt (DB'ye yazma) çalıştı.
- [x] **CI**: `.github/workflows/ci.yml` — backend (Python 3.11 ve 3.12: `ruff`,
  `pytest`), migrations (gerçek Postgres servisinde `alembic upgrade head`,
  `alembic check`, `downgrade base` + yeniden `upgrade`), frontend (`npm ci`,
  oxlint, `tsc -b`, build). Sır yok, API anahtarları sahte. Her adım GitHub'a
  göndermeden önce temiz bir klonda (`.env` yok) simüle edildi; bu sırada CI'ı ilk
  koşuda kırabilecek bir sorun bulundu: frontend araçları Node ≥ 20.19 ister, eski
  Node'da `npm ci` yerel bağlamaları sessizce atlıyor (workflow Node 22 kullanıyor,
  `package.json`'a `engines` eklendi). GitHub'daki ilk gerçek koşu geçti (PR #20).
  **Açık:** `main` için "CI geçmeden merge edilemez" dal koruması (branch
  protection) elle açılmalı, açıldığı teyit edilmedi; `pip-audit`/`npm audit` ve
  Dependabot yok (aşağıdaki "Bağımlılık taraması" maddesi).
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
- [x] **`/health` kapsamı**: `/health` canlılık (hep hızlı), yeni `/health/ready`
  veritabanına `SELECT 1` atar, bozuksa `503 {"status":"unavailable"}` (ayrıntı dışarı
  verilmez, sebep log'a). API anahtarları tanımsızsa uygulama zaten açılmıyor.
  **Açık:** yayın ortamında bu uç bir izleme/yük dengeleyiciye bağlanmalı;
  `docker-compose.yml`'a `healthcheck` eklenmedi.
- [x] **Log yapısı**: her isteğe numara (`X-Request-ID`, log satırlarında
  `request_id`); `LOG_FORMAT=json` ve `LOG_LEVEL` ayarları. **Açık:** loglar hâlâ yalnızca
  konsola gidiyor (toplama/saklama canlı ortama bağlı).
- [ ] **Güvenlik olayları için audit log** — **kısmen yapıldı** (logger `audit`, yalnızca IP + yol): rate limit aşıldı, misafir kotası doldu, geçersiz/süresi dolmuş token (INFO). **Açık:** giriş yapmış kullanıcının kota dolumu (`user_limit.py`) loglanmıyor; başarısız girişler (`/auth/login` 401) ayrıca loglanmıyor; kimlikle loglama kararı. Eski not: şu an hiçbiri kaydedilmiyordu.
  `warning` olarak (IP + yol + olay; token'ın kendisi ASLA) şunlar yazılmalı:
  misafir kotası aşıldı (`guest_limit.py`), rate limit aşıldı (slowapi'nin
  varsayılan işleyicisi log yazmıyor), geçersiz/süresi dolmuş JWT
  (`auth.py` sessizce `None` döndürüyor). Giriş yapmış kullanıcının `/plan`
  isteği kimlik (`sub`) ile kaydedilmeli mi, KVKK değerlendirmesiyle birlikte
  karar verilecek. Kaydet/sil/favori gibi veri değişiklikleri backend'e
  uğramaz; bunların izi Supabase panelindeki Auth/veritabanı log'larındadır
  (saklama süresi plana bağlı, kontrol edilmeli). **Güncel durum:** artık
  bu istekler backend'e uğruyor, yani kimlik (`sub`) ile loglanabilirler; ama
  kimlik/audit log'u henüz yazılmıyor. Uvicorn erişim log'unun
  proxy arkasında doğru istemci IP'sini yazdığı doğrulanmalı.
- [ ] **Log saklama süresi ve Docker log döndürme (sunucuya geçerken)**: karar: barındırıcı
  seçilince birlikte ele alınacak. Şu an loglar yalnızca stdout'a gidiyor; Docker
  varsayılanında konteyner ömrü boyunca ve sınırsız tutulur (`docker-compose.yml`'da
  `logging` ayarı yok, disk dolabilir). Yapılacak: üst süre belirle (ör. 30 gün, hukuki
  danışmanla), `max-size`/`max-file` ile döndürme, süreyi aydınlatma metnindeki
  "Ne kadar saklıyoruz?" bölümüne yaz. Loglarda IP, istek yolu ve (temizlenmiş) şehir/adres
  metni var; koordinat, token, şifre, LLM yanıtı yok.
- [x] **Log'a girenlerin temizlenmesi** (yapıldı: `clean_log`, koordinat ve LLM yanıt alıntısı artık loglanmıyor; **açık:** log saklama süresi). Eski not: kullanıcı metni (`geocoding.py` adres,
  `orchestrator.py` şehir) satır sonu karakterleri temizlenerek yazılmalı (log
  injection); koordinatlar (`weather.py`, `orchestrator.py`) ve LLM yanıtından
  alıntı (`planner.py`, ilk 300 karakter; kullanıcı notu içerebilir) kişisel
  veri sayılabileceğinden mümkünse kaba tutulmalı ya da loglanmamalı; log
  saklama süresi belirlenmeli.

### Kullanıcıya dönük

- [ ] **Gizlilik politikası ve konum izni metni**: konum yalnızca tarayıcıda
  kullanılıp Routes API'ye gönderiliyor; ne toplandığı/saklandığı açıkça
  yazılsın. Hesap silme (`users` kaydı ve ona bağlı tüm veriler) için bir yol
  düşünülmeli. Ayrıntısı aşağıdaki KVKK maddelerinde.

#### KVKK (6698 sayılı Kanun) hazırlığı

Not: bu bölüm bir veri envanteri ve yapılacaklar listesidir, hukuki görüş
değildir. Metinler ve yükümlülüklerin kapsamı (açık rıza gerekip gerekmediği,
VERBİS kaydı, yurt dışı aktarım şartları) bir hukuk uzmanıyla netleştirilmeli.

**Veri envanteri (koddan çıkarıldı):**

| Veri | Nerede | Kaynak |
|---|---|---|
| E-posta, kullanıcı adı, şifre (yalnızca argon2 özeti) | Kendi PostgreSQL'imiz, `users` | Kayıt |
| Oturum yenileme token'ı (yalnızca SHA-256 özeti, IP/cihaz bilgisi tutulmaz) | PostgreSQL `refresh_tokens` | Giriş |
| Şifre sıfırlama token'ı (SHA-256 özeti, 1 saat; kullanılınca/yenisi gelince silinir) | PostgreSQL `password_reset_tokens` | "Şifremi unuttum" |
| E-posta adresi + sıfırlama bağlantısı | SMTP sağlayıcısına iletilir | "Şifremi unuttum" |
| Kaydedilen planlar (durak, konum, `user_id`) | PostgreSQL `saved_plans` | Kullanıcı |
| Favori mekanlar (ad, adres — koordinat YOK, bkz. Milestone 4 "Üçüncü taraf ToS uyumluluğu") | PostgreSQL `favorite_places` | Kullanıcı |
| Ziyaret geçmişi (mekan adı/adresi — koordinat YOK, ziyaret sayısı, son ziyaret zamanı) | PostgreSQL `visited_places` | "Ulaşıldı" işaretlemesi |
| Şehir/adres metni, koordinat, serbest metin, tercihler | Backend isteği; Google/Groq/Open-Meteo'ya iletilir; kısmen log'a düşer | Plan formu |
| IP adresi | Rate limit ve misafir kotası (bellekte), uvicorn erişim log'u | Her istek |
| Anlık cihaz konumu (navigasyon) | `watchPosition` → `/route/approach` → Google Routes; kodda kalıcı saklandığı yer görülmedi | Cihaz |
| Erişim token'ı (15 dk), tema, misafir plan sayacı | Tarayıcı `localStorage` | İstemci |
| Refresh token (30 gün) | **Çerez** (`bugunluk_refresh`, `HttpOnly`, `SameSite=Strict`, `Secure`) | Giriş |

**Üçüncü taraflar / yurt dışı aktarım:** E-posta (SMTP) sağlayıcısı (seçilince; yalnızca şifre sıfırlama e-postasının adresi ve içeriği), Google (Geocoding, Places, Routes),
Groq (serbest metin, tercihler, mekan listesi LLM'e gider), Open-Meteo
(koordinat). Hesap ve kayıtlar artık üçüncü tarafta değil, kendi
sunucumuzdaki PostgreSQL'de (Supabase'e yurt dışı aktarım kalktı; sunucunun
konumu ve barındırıcı yine aydınlatma metninde belirtilmeli). Her birinin
sunucu bölgesi ve sözleşme koşulları kontrol edilip aydınlatma metninde
yazılmalı; yurt dışına aktarım şartları hukuken değerlendirilmeli.

**Yapılacaklar:**
- [ ] **Aydınlatma metni** — **taslak yapıldı** (`frontend/src/screens/PrivacyScreen.tsx`; ana ekrandaki konum notundan ve giriş/kayıt formundan açılır). **Açık:** veri sorumlusu adı, KVKK başvuru adresi ve barındırıcı yer tutucu (`[...]`), yayından önce doldurulmalı; metin hukukçuya gösterilmeli; saklama süreleri (log) henüz yazılamadı. Metin şunları kapsamalı: veri sorumlusu kimliği ve iletişim, hangi verinin
  hangi amaçla ve hangi hukuki sebeple işlendiği, kimlere aktarıldığı, saklama
  süresi, ilgili kişi hakları ve başvuru yolu. Kayıt/giriş ekranından ve
  alt bilgiden erişilebilir olmalı.
- [ ] **Gizlilik metnindeki yer tutucuları doldur (yayın engeli)**:
  `frontend/src/screens/PrivacyScreen.tsx` en üstündeki üç sabit hâlâ `[...]`
  olarak ekranda görünüyor, doldurulmadan yayına çıkılmamalı:
  - `CONTROLLER`: veri sorumlusunun adı/unvanı (kişi mi, şirket mi?).
  - `CONTACT`: KVKK başvuru e-posta adresi (şifre sıfırlamadaki SMTP'den bağımsız,
    yalnızca kullanıcıların bize yazacağı adres).
  - `HOSTING`: barındırıcı ve sunucunun ülkesi (barındırma kararı verilince).
  Ayrıca metin hukukçuya gösterilmeli ve log saklama süresi netleşince
  "Ne kadar saklıyoruz?" bölümüne eklenmeli.
- [x] **Tarayıcı konum izninden önce kısa açıklama** (arayüz kısmı yapıldı):
  `DetailScreen.tsx` artık detay ekranı açılır açılmaz konumu otomatik istemiyor.
  Önce `navigator.permissions.query({name:'geolocation'})` ile mevcut izin
  durumuna bakıyor: zaten verilmiş/reddedilmişse (tarayıcı zaten karar vermiş,
  yeniden sormak anlamsız) doğrudan ister; durum `"prompt"` ise (ya da
  Permissions API desteklenmiyorsa) tarayıcı diyaloğu açılmadan önce kısa bir
  açıklama kartı gösterir ("yalnızca ilk durağa olan mesafeyi hesaplamak için
  kullanılır, hiçbir yerde saklanmaz") + "Konumumu Kullan" düğmesi; diyalog
  ancak buna basınca açılır.
- [ ] **Konum için bilgilendirme/rıza metni (hukuki kısım açık)**: şehir
  yazarak plan, cihaz konumu (navigasyon) ve ziyaret geçmişi ayrı ayrı
  anlatılsın; konumun açık rıza gerektirip gerektirmediği hukuki olarak
  netleştirilsin. (Ana ekranda kısa not ve gizlilik metnine bağlantı var;
  ayrı/resmi bir rıza metni hâlâ yok — bu bir hukukçu kararı.)
- [ ] **Silme hakkı**: hesap silme akışı (`users`, `saved_plans`,
  `favorite_places`, `visited_places`, `refresh_tokens`). **Backend yapıldı:**
  `DELETE /me` (şifre doğrulamalı, tek işlemde hepsini kalıcı siler — soft
  delete yok, e-posta/kullanıcı adı da tutulmaz; silinen hesabın erişim
  token'ı anında 401 verir). **Frontend yapıldı:** Hesabım'da "Hesabımı sil"
  (ne silineceği yazılı, şifre ister, başarıda oturum kapanır ve bilgi mesajı
  gösterilir). **Açık:** yedeklerde/log'larda kalan verinin saklama süresi.
  Ziyaret geçmişini temizleme **yapıldı**: `DELETE /visits` (tümü) ve
  `DELETE /visits/{place_id}`.
- [ ] **Erişim / taşınabilirlik**: kullanıcının kendi verisini görebilmesi ve
  dışa aktarabilmesi (Hesabım'dan JSON indir gibi).
- [ ] **Paylaşılan planlar**: toptan listelenebilme sorunu düzeltildi (bkz.
  "IDOR / sahiplik" maddesi), ama kullanıcının paylaştığı bir planı
  "paylaşımdan kaldır" diye ayrı bir seçeneği yok — şu an tek yol favoriden
  çıkarıp (`deleteSavedPlan`) planı tamamen silmek. KVKK açısından bunun
  yeterli olup olmadığı değerlendirilmeli.
- [ ] **Saklama süreleri**: log'lar, `visited_places` (ziyaret geçmişi),
  kullanılmayan hesaplar için süre belirlenip uygulanmalı.
- [ ] **Veri ihlali süreci**: sızıntı olursa kim, neyi, kime ne zamana kadar
  bildirir (mevzuattaki süreler hukuki olarak doğrulanmalı); log ve audit
  kayıtları buna dayanak olacak.
- [ ] **VERBİS / kayıt yükümlülüğü**: uygulamanın işletici statüsüne göre
  gerekip gerekmediği hukuken kontrol edilmeli.
- [ ] **Sağlayıcı sözleşmeleri**: Google, Groq ve barındırıcı için veri işleme
  şartları/DPA incelenmeli; Groq'a giden kullanıcı serbest metninin
  eğitimde kullanılmadığı ayarı doğrulanmalı.
- [ ] **Çocuklar**: yaş sınırı ve ebeveyn onayı gerekliliği değerlendirilmeli.
- [x] **Frontend testleri**: Vitest kuruldu (`npm test`, CI'da ayrı adım).
  104 test (74 saf mantık + 25 `auth.ts` + 5 `App.tsx` bileşen testi, aşağıya bkz).
  Saf mantık: `api.ts` (sahte `fetch`: hata/limit bayrakları, 401 kancası, iptal),
  `prefs.ts`, `nav.ts`, `geo.ts`, `meta.ts`, `guestLimit.ts`, `authErrors.ts`
  (`authErrorText` bu yüzden `AccountScreen`'den ayrı dosyaya taşındı). `meta.test.ts`
  ayrıca frontend `THEME_TYPES`'ının backend `themes.py` ile birebir aynı olduğunu
  doğrular. `auth.ts` da testli (`auth.test.ts`, 25 test: açılışta sessiz geri kazanma, süre dolmadan
  yenileme, 401/ağ hatası, başka sekmeyle senkron, görünürlük, giriş/çıkış/hesap silme).
  **Açık:** Web Locks gerçek tarayıcıda iki sekmeyle elle denenmedi (testte kilit sahte).
- [x] **Ekran/bileşen testi (jsdom + Testing Library)**: `jsdom`,
  `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`
  eklendi (yalnızca `src/App.test.tsx`'te `// @vitest-environment jsdom` ile devreye
  giriyor — diğer testler hâlâ varsayılan `node` ortamında, daha hızlı). `App.test.tsx`
  (5 test) tam olarak sayfa yenileme/plan geri yükleme akışını (az önceki madde) gerçek
  `<App />` render ederek doğruluyor: misafir + geçerli kayıt → doğrudan sonuç ekranı
  (konum ekranına düşülmüyor); kayıt yok → konum ekranı; bozuk/eski sürüm kayıt →
  çökme yok, konum ekranına düşer; 12 saatten eski kayıt → geçersiz sayılır; `detail`
  görünümünden kaydedilmiş bir plan → doğru alternatifin detayına döner (sonuç
  listesine değil). `DetailScreen`/Leaflet testlerde hiç mount olmuyor (view hep
  `results`'ta kalıyor), o yüzden `L.map()` jsdom'da hiç çağrılmıyor — gerçek bir
  harita render riski yok. `window.matchMedia`/`scrollTo` jsdom'da yok, testte
  sahteleniyor; `@testing-library/react`'in otomatik cleanup'ı olmadığı için
  `afterEach(cleanup)` şart (yoksa önceki testin `App`'i mount'ta kalıp
  `localStorage.clear()`'ı geçersiz kılıyor).
- [x] **Gerçek bir güvenilirlik hatası bulundu ve düzeltildi**: gerçek çıktılarla
  kontrol ederken `/plan` neredeyse her zaman 502 ("Plan servisi yanıt vermedi")
  dönüyordu. Sebep: `DayPlan.place_pool` (Supabase→Postgres geçişinde eklenen,
  tamamen sistemin doldurduğu bir alan) `app/services/planner.py::_SYSTEM_FILLED`'e
  hiç eklenmemişti — LLM'e gönderilen JSON şemasına tüm mekan havuzunu (`Place`
  tanımıyla) da üretmesi gerekiyormuş gibi giriyordu, model bunu üretmeye
  çalışırken geçersiz JSON'a düşüyordu. Düzeltme: `place_pool`'u `_SYSTEM_FILLED`'e
  ekledik (şema ~%28 küçüldü, `Place` $defs'ten düştü); ayrıca `create_plan`'ın
  deneme bütçesi artık yalnızca "az alternatif" durumunda değil, Groq'un
  tamamen başarısız olduğu durumda da (ekstra çağrı eklemeden, aynı
  `MAX_ATTEMPTS` içinde) yeniden deniyor. Regresyon testleri:
  `tests/test_planner_llm.py::test_llm_semasi_sistemin_doldurdugu_alanlari_icermez`
  (artık `place_pool`/`user_rating_count` de kontrol ediyor) ve
  `test_create_plan_ilk_deneme_basarisizsa_ikincide_toparlanir`.
- [ ] **LLM çıktı kalitesi (ölçüm hâlâ açık)**: düzeltmeden sonra bile Groq
  ara sıra (gözlemlenen oran: birkaç denemeden biri) `json_object` modunda
  geçersiz/boş yanıt üretiyor — bu muhtemelen sağlayıcı/model tarafı bir
  tutarsızlık, tamamen giderilemedi, yalnızca retry ile tolere ediliyor.
  Planların Türkçe dönmesi prompt'ta zorlandı ama rastgele kayma (konu dışı
  öneri, tutarsız süre vb.) tamamen ölçülmedi; birkaç gerçek çıktıyla daha
  kontrol, gerekirse `temperature` (şu an 0.8) düşürme denenebilir.
- [ ] **Dil tutarlılığı ve "sadece Türkiye için mi?" sorusu (2026-11-17,
  Afragül'den gelen soru, henüz yapılmadı)**: kod incelendi, bulgular:
  - **Yalnızca Türkiye'ye özel değil, ama tüm metin çıktısı Türkçe'ye sabit.**
    Konum/hava/mekan/rota API'leri (Google Places/Geocoding/Routes, Open-Meteo)
    koordinat tabanlı ve dünyanın her yerinde çalışıyor — bu yüzden fonksiyonel
    olarak uygulama herhangi bir şehir için plan kurabiliyor. Ama görünen metin
    her zaman Türkçe, dile bakılmaksızın: `planner.py::SYSTEM_INSTRUCTION`
    LLM'e "Tüm metin alanlarını ... TÜRKÇE yaz" diye talimat veriyor (koşulsuz);
    `places.py` (x2) ve `routes.py` (x2) `languageCode: "tr"` sabit (mekan adı/adres,
    adım adım yol tarifi hep Türkçe gelir); `weather.py::WEATHER_CODES` hava durumu
    açıklamasını Türkçe sabit bir sözlükten okuyor. `PlanRequest`'te bir `language`
    alanı yok, frontend'de de bir dil seçici yok — yani şu an "siteye İngilizce
    eklenirse" diye bir dal zaten çalışmaz, hepsi sabit Türkçe'ye kodlanmış.
  - **Küçük bir ek nüans**: hesap günlük kota sıfırlanması Türkiye saatine
    (sabit UTC+3) göre — yurt dışından kullanan biri için "gün" yanlış saatte
    döner (işlevi bozmaz, küçük bir UX tutarsızlığı).
  - **Afragül'ün istediği davranış** ("Türkçe seçiliyse Türkçe, ek istek olmadıkça;
    İngilizce eklenirse İngilizce") şu an koda yansımıyor çünkü dil hiç
    parametre değil — yapılacaksa `PlanRequest.language` eklenip
    `orchestrator.py` → `planner.py` (prompt'taki "TÜRKÇE yaz" satırı dinamik
    olmalı) → `places.py`/`routes.py`/`geocoding.py`'deki `languageCode`/`language`
    → frontend'de arayüz dili seçici kadar uçtan uca bir iş; henüz yapılmadı,
    yalnızca not edildi.

## Milestone 5 — Supabase'ten kendi PostgreSQL'imize geçiş

Gerekçe: kullanıcı verilerinin kendi sunucumuzda tutulması. Sıra: altyapı →
modeller/migration → auth → veri endpoint'leri → frontend → refresh token →
hesap silme → günlük kota → migration otomasyonu → CI → şifre sıfırlama.
Eski Supabase kullanıcıları taşınmadı (sıfırdan başlandı).

**Yapıldı:**
- [x] **Altyapı**: `docker-compose.yml` (`db`: `postgres:16-alpine`, host portu
  `127.0.0.1:5433`; `api`), `Dockerfile`, `.dockerignore`. Port 5433 çünkü 5432
  geliştirme makinesinde başka bir süreçte kullanımda.
- [x] **Veritabanı katmanı**: SQLAlchemy 2 (async) + asyncpg + Alembic
  (`app/db/`, `migrations/`). Tablolar: `users` (Supabase `auth.users` +
  `profiles` birleşti), `saved_plans`, `favorite_places`, `visited_places`,
  `refresh_tokens`, `daily_usage`, `password_reset_tokens`. Migration'lar: 0001
  ilk şema, 0002 büyük/küçük harf duyarsız benzersiz kullanıcı adı, 0003 refresh
  token, 0004 günlük kullanım sayacı, 0005 şifre sıfırlama tokeni. Testler
  bellekte SQLite ile koşar (gerçek Postgres gerekmez).
- [x] **Kendi auth'umuz**: `/auth/register`, `/auth/login`, `/auth/refresh`,
  `/auth/logout`, `/me` (profil, kullanıcı adı), `/me/password`. Şifre argon2;
  erişim token'ı 15 dk'lık HS256 JWT; giriş hatası kullanıcının var olup
  olmadığını sızdırmaz; e-posta küçük harfe normalize edilir.
- [x] **Refresh token**: `httpOnly`/`SameSite=Strict` çerez, veritabanında yalnızca
  SHA-256 özeti, her yenilemede döner, iptal edilmiş token süre dışı tekrar
  gelirse tüm aile kapanır (10 sn tolerans: iki sekme aynı anda yenileyebilir),
  şifre değişince diğer oturumlar kapanır.
- [x] **Veri endpoint'leri** (hepsi sahiplik kontrollü, girdi sınırlı):
  `/plans` + `/shared/{id}` (girişsiz; sahibin kimliği dönmez, yerine `is_owner`),
  `/favorites`, `/visits` (atomik sayaç, geçmişi temizleme).
- [x] **Frontend**: `@supabase/supabase-js` ve `supabase.ts` kaldırıldı;
  `auth.ts` kendi oturum deposu + sessiz yenileme; veri modülleri backend'i çağırır.
- [x] **Sahiplik/IDOR**: Supabase RLS'in yerine her sorguda `WHERE user_id = :me`;
  başkasının kaynağı ile olmayan kaynak aynı 404'ü verir. Testlerle doğrulandı.
- [x] **Hesap silme**: `DELETE /me` (şifre doğrulamalı, tek işlemde kalıcı) ve
  Hesabım'da "Hesabımı sil" akışı. Ayrıntı: aşağıdaki KVKK "Silme hakkı" maddesi.
- [x] **Günlük kota (giriş yapanlar)**: `daily_usage`, atomik sayaç; ayrıntı:
  Milestone 4 "Rate limit — giriş yapanlar için günlük üst sınır" maddesi.
- [x] **Migration'ın otomatik çalışması**: `docker-entrypoint.sh` açılışta
  `alembic upgrade head` uygular, başarısızsa konteyner hatayla çıkar. Boş
  veritabanı, ikinci açılış, bozuk bağlantı ve `RUN_MIGRATIONS=false` denendi.
- [x] **CI**: GitHub Actions; ayrıntı: Milestone 4 "CI" maddesi.
- [x] **Şifre sıfırlama ("şifremi unuttum")**: `/auth/forgot`, `/auth/reset`,
  `/auth/capabilities`; genel SMTP (stdlib `smtplib`, yeni bağımlılık yok: TLS için
  `certifi`), token tek kullanımlık/1 saat/özet olarak saklanır ve bağlantıda
  fragment'te (`#reset=`), hesap var/yok aynı cevap, e-posta arka planda, hesap
  başına 60 sn bekleme, sıfırlama tüm oturumları kapatır. **SMTP yoksa özellik
  kapalı** ve arayüz bağlantıyı göstermez. Doğrulama: yerel sahte SMTP sunucusuyla
  uçtan uca; gerçek sağlayıcı (Resend, `ssl`/465) sunucusuna bağlanıp kimlik
  doğrulama başarılı (e-posta gönderimi bu aşamada yapılmadı).
  Çıkan sorunlar: python.org macOS Python'unda kök sertifika deposu olmadığı için
  `smtplib` "unable to get local issuer certificate" ile düşüyordu (artık certifi);
  ayrıca bir test `.env`'deki gerçek SMTP ayarını görüp gerçek sağlayıcıya bağlanmayı
  denemişti (artık `conftest` SMTP_* değerlerini boşa zorluyor).

**Açık:**
- [ ] **Şifre sıfırlama RAFTA (karar)**: kod duruyor ama bilerek KAPALI (`SMTP_*` boş →
  `/auth/forgot` 503, arayüz bağlantıyı göstermez). Sebep: e-posta adresi + sıfırlama
  bağlantısı üçüncü taraf bir sağlayıcıya (Resend, yurt dışı) gidiyor; KVKK yurt dışı
  aktarım riski. Açmadan önce: yurt içi/AB sağlayıcı seç ve aydınlatma metnine yaz;
  alan adı doğrula (Resend deneme modu yalnızca hesabın kendi adresine gönderir; SPF/DKIM,
  `SMTP_FROM` o alan adından, `FRONTEND_BASE_URL` gerçek adres). Yayında `SMTP_*` tanımlama.
  Açık kalan işler: şifre sıfırlama arayüzü ve `starttls` modu**: forgot/reset formları tarayıcıda
  elle denenmedi; `starttls` yalnızca birim testle (gerçek sunucuyla denenmedi).
- [ ] **E-posta doğrulama**: yok; kayıt olan herkes e-postası doğrulanmadan
  oturum açıyor (başkasının adresiyle de hesap açılabilir).
- [ ] **Güvenlik bildirimi e-postaları**: şifre değişince/sıfırlanınca/hesap
  silinince bilgilendirme e-postası gitmiyor (karar: şimdilik gerek yok).
- [ ] **Hesap bazlı brute-force koruması**: yalnızca IP bazlı limit var.
- [ ] **Tüm cihazlardan çıkış** düğmesi (backend `revoke_all_for_user` hazır).
- [ ] **Frontend'in oturum mantığı tarayıcıda otomatik test edilmiyor**
  (`auth.ts` zamanlayıcı/sekme senkronu, hesap silme/şifre sıfırlama formları elle denenmeli).
- [x] **Yedek ve geri yükleme — gerçek Postgres'te denendi (2026-11-17)**:
  `pg_dump -F c` + `pg_restore --clean --if-exists` ile tam bir döngü denendi
  (gerçek kullanıcı kaydı → yedek al → `drop schema public cascade` ile tam veri
  kaybı simülasyonu → geri yükle → `/auth/login` ile API üzerinden doğrulama,
  sorunsuz çalıştı). Komutlar ve notlar README.md "Yedekleme ve geri yükleme"
  bölümünde. **Açık kalan:** bu tek seferlik elle bir deneme — canlıda düzenli
  (ör. günlük) otomatik yedek + ayrı bir yerde/diskte saklama henüz kurulmadı
  (yukarıdaki "PostgreSQL canlı ayarları" maddesi); `alembic downgrade` (şema
  geri alma) bu denemenin KAPSAMI DIŞINDA — pg_dump geri yüklemesi farklı bir
  şey, downgrade migration'ları hâlâ denenmedi.
- [ ] **Eski Supabase verisi**: gerçek kullanıcı varsa taşıma yapılmadı.
- Veri dışa aktarma bilinçli olarak yapılmıyor (karar: hiçbir şekilde).

## Öncelik dışı / fikir aşamasında

- PDF/export olarak plan paylaşımı
