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

### Sırada / fikir aşamasında

- [ ] **Mekan fotoğrafı/yorumları**: Google Places'te ek maliyetli
  (fotoğraf: mekan+fotoğraf başına ayrı çağrı; yorumlar: daha pahalı bir
  fiyat katmanı + ayrı Place Details çağrısı gerektiriyor). Ücretsiz bir
  yol bulunursa değerlendirilecek, şu an öncelik değil.
- [ ] **Mekan bazlı favorileme**: rota değil, tekil bir mekanı favorileme
  (basit `user_id` + `place_id` tablosu — rota favorilemeden daha küçük bir
  iş, bilinçli olarak sonraya bırakıldı).
- [ ] **Sık gidilen yerler / rutin önerisi**: zamanla kullanıcının
  ziyaret ettiği yerlerden bir "sık gidilenler" listesi çıkarma.
- [ ] **Mekan değiştirirken AI'ya sorma**: şu an sadece kategori chip
  filtresi var (ücretsiz); kullanıcının serbest metinle ("bunu beğenmedim,
  daha sakin bir yer olsun" gibi) tarif etmesi ve LLM'in havuzdan/yeni
  aramadan seçmesi — maliyet/karmaşıklık nedeniyle kapsam dışı tutuldu.
- [ ] **Profil fotoğrafı**: Supabase Storage'da yeni bir bucket + RLS
  policy'leri gerekiyor, henüz kurulmadı.
- [ ] **Backend'in Supabase JWT doğrulaması**: şu an hiçbir endpoint
  kullanıcı kimliği istemiyor; kullanıcıya özel backend mantığı gerekirse
  (ör. plan geçmişini backend'in de görmesi) eklenecek;
  misafir rota limitini sunucuda zorlamak (IP/cihaz bazlı sayaç) da buna bağlı.

## Milestone 4 — Public'e açılış hazırlığı

Uygulama şu an tek kullanıcılı/demo kullanımına göre kuruldu. Herkese açık
yayınlamadan önce yapılacaklar; öncelik sırasıyla (güvenlik/maliyet önce).

### Yayın öncesi zorunlu

- [ ] **`/plan` ve `/route/*` için istek sınırı (rate limit)**: hiçbir endpoint
  kimlik ya da istek sınırı istemiyor; adresi bulan biri döngüyle çağırıp
  Groq/Google kotasını ve faturasını tüketebilir. IP bazlı limit (ör.
  `slowapi`) ilk adım. Misafir limiti (frontend) bunu korumaz.
- [ ] **Backend'de Supabase JWT doğrulaması**: geçerli token varsa oturumlu
  kullanıcı, yoksa misafir. Misafir limitini sunucuda zorlamanın ön koşulu
  (kalıcı sayaç için Supabase tablosu ya da Redis; bellekte tutulursa yeniden
  başlayınca sıfırlanır; aşılınca `429`, frontend limit ekranına çevirir).
- [ ] **Girdi sınırları**: `PlanRequest.free_text`, `city` ve benzeri alanlara
  `max_length`; `duration_hours` ve mekan havuzu için üst sınır. Serbest metin
  doğrudan LLM prompt'una giriyor, uzunluk sınırı hem maliyeti hem
  prompt-injection yüzeyini küçültür.
- [ ] **CORS ve yayın yapılandırması**: `app/main.py`'de CORS ayarı yok (dev'de
  Vite proxy'si gerekeni örtüyor). Yayında frontend'in alan adına özel
  `allow_origins`, `/docs` ve `/openapi.json`'un kapatılması/korunması.
- [ ] **Supabase RLS denetimi**: `profiles`, `saved_plans` kuralları tek tek
  gözden geçirilsin (sahibi dışında yazma/silme yok; `saved_plans` herkese
  açık okunabilir, gizlilik yalnızca uuid'nin tahmin edilememesine dayanıyor;
  hassas veri konmamalı). Anon key'in herkese açık olduğu varsayılarak test.
- [ ] **API anahtarı kısıtları ve bütçe uyarısı**: Google anahtarları IP/API
  bazında kısıtlansın (Places, Routes, Geocoding ayrı anahtarlar zaten), Google
  Cloud ve Groq'ta kota + bütçe alarmı kurulsun.
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
