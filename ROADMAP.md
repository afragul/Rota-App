# Yol Haritası

Backend önce tamamlanıp sonra frontend'e geçilecek şekilde sıralandı. README.md "Şu anki durum" ve DESIGN.md "Sonraki adımlar" bölümleriyle tutarlıdır; oradaki eksikler burada somut görevlere bölündü.

## Milestone 1 — Backend'i tamamla

- [x] **Şehir/adres → koordinat çözümleme**: `/plan` artık `latitude`/`longitude` ikilisi yerine `city` de kabul ediyor (`app/services/geocoding.py`, Google Geocoding API). `GEOCODING_API_KEY` bunun için kullanılıyor. Bağımsız test için `GET /geocode` eklendi.
- [x] **Hava durumuna göre kural bazlı indoor/outdoor ağırlıklandırma**: `app/services/weather.py::is_bad_weather` yağış/fırtına kodlarını işaretliyor, `app/core/themes.py::filter_for_bad_weather` kötü havada `acik_hava` temasını mekan aramasından önce eliyor (`orchestrator.py::build_day_plan`). Not: bu artık hava sonucunun mekan aramasından önce beklenmesini gerektiriyor — hava/mekan paralel çekimi kayboldu, tema çözümleme (LLM) ile hava paralel kaldı. Ayrıca `_weather_summary`'deki `weather.description` (var olmayan alan) hatası `weather.condition` olarak düzeltildi.
- [x] **Rota/harita verisi — pin'ler**: Stitch UI tasarımı incelenirken fark edildi: haritada pin basmak için bile `PlanStop`'ta koordinat yoktu. `PlanStop`'a `name`/`latitude`/`longitude` eklendi; LLM bunları üretmiyor (null bırakıyor), `planner.py::_validate_and_enrich_stops` doğrulanmış mekan havuzundan dolduruyor.
- [x] **Rota/harita verisi — çizgi**: `PlanAlternative.legs` ardışık duraklar arası ayakları (`travel_mode`, `distance_meters`, `duration_minutes`, encoded `polyline`) taşıyor. Ulaşım şeklini kullanıcı seçiyor: `PlanRequest.travel_mode` (`WALK` varsayılan, `TRANSIT`, `DRIVE`). `app/services/routes.py` Google Routes API'yi (`computeRoutes`) çağırıyor: `WALK`/`DRIVE` için alternatif başına tek istek, `TRANSIT` intermediates desteklemediği için ardışık çift başına ayrı istek. `orchestrator.py::build_day_plan` planı kurduktan sonra ekliyor. Rota kritik değil: servis çökerse `legs` boş kalır, plan yine döner.
  - Log sorunu çözüldü: hata log'u artık HTTP durum kodu, ulaşım modu ve Google'ın hata gövdesini (ör. "Routes API has not been used in project...") içeriyor; istemci için `PlanAlternative.routes_available` (`weather_available` ile aynı desen) rota alınamadığını bildiriyor.
  - Kapsam dışı: adım adım talimat (Stitch tasarımındaki "Moda Çıkmazı yönü" ipucu `steps` verisi ister), bisiklet/motosiklet modları.
- [x] **Eksik test kapsamı**: `planner.py`'de `create_plan` ve `resolve_themes` (Groq `conftest.py::fake_groq` ile sahtelenir: geçerli/bozuk/boş yanıt, Groq hatası, uydurma id/tema) ve `orchestrator.py::build_day_plan` uçtan uca (geocoding, hava, mekan, rota HTTP'si `respx` ile; kötü hava daraltması, hava/rota servisi çökmesi, kısmi tema hatası, mekan yokluğu, ulaşım modu) test ediliyor. Testler sahte key'lerle çalışır, `.env` gerekmez.
- [x] **`.env.example` doldurulması**: `PLACES_API_KEY`, `GEOCODING_API_KEY`, `ROUTES_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL` için placeholder değerlerle dolduruldu, hangi Google API'lerinin etkin olması gerektiği yorum olarak yazıldı. Kurulum: `cp .env.example .env`.

## Milestone 2 — AI'nin soru sorabilmesi

- [ ] Kullanıcının serbest metni belirsiz/eksikse (ör. süre veya kaç kişi olduğu net değilse) planner'ın doğrudan plan yerine bir netleştirme sorusu döndürebilmesi.
- [ ] Bunun için backend'in şu anki stateless yapısı yetmez — bir konuşma geçmişi (session/conversation id) tutulmalı. Kapsam: yeni bir tablo/state deposu mu, yoksa istemcinin geçmişi her istekte geri göndermesi mi — bu bir tasarım kararı, uygulamaya geçmeden önce konuşulmalı.
- [ ] `/plan` endpoint'inin ya çok turlu hale getirilmesi ya da ayrı bir `/plan/clarify` akışı eklenmesi.

## Milestone 3 — Frontend

DESIGN.md'deki ekranlara birebir karşılık gelir.

- [ ] Teknoloji seçimi (framework, state yönetimi, harita kütüphanesi).
- [ ] Konum/şehir seçimi ekranı (Milestone 1'deki geocoding'e bağlı).
- [ ] Tercihler ekranı (bütçe, grup tipi, süre, aktivite türü chip'leri, serbest metin).
- [ ] Sonuç ekranı — alternatif plan kartları + hava rozeti.
- [ ] Plan detay ekranı — durak zaman çizelgesi + harita (Milestone 1'deki rota verisine bağlı).
- [ ] Hata/boş durum ekranları (mekân bulunamadı, plan üretilemedi, hava alınamadı).

## Öncelik dışı / fikir aşamasında

- Plan paylaşımı (link ile paylaşma, PDF/export)
- Kullanıcı hesabı, geçmiş planları kaydetme
