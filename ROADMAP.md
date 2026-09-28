# Yol Haritası

Backend önce tamamlanıp sonra frontend'e geçilecek şekilde sıralandı. README.md "Şu anki durum" ve DESIGN.md "Sonraki adımlar" bölümleriyle tutarlıdır; oradaki eksikler burada somut görevlere bölündü.

## Milestone 1 — Backend'i tamamla

- [x] **Şehir/adres → koordinat çözümleme**: `/plan` artık `latitude`/`longitude` ikilisi yerine `city` de kabul ediyor (`app/services/geocoding.py`, Google Geocoding API). `MAPS_API_KEY` bunun için kullanılmaya başlandı. Bağımsız test için `GET /geocode` eklendi.
- [x] **Hava durumuna göre kural bazlı indoor/outdoor ağırlıklandırma**: `app/services/weather.py::is_bad_weather` yağış/fırtına kodlarını işaretliyor, `app/core/themes.py::filter_for_bad_weather` kötü havada `acik_hava` temasını mekan aramasından önce eliyor (`orchestrator.py::build_day_plan`). Not: bu artık hava sonucunun mekan aramasından önce beklenmesini gerektiriyor — hava/mekan paralel çekimi kayboldu, tema çözümleme (LLM) ile hava paralel kaldı. Ayrıca `_weather_summary`'deki `weather.description` (var olmayan alan) hatası `weather.condition` olarak düzeltildi.
- [x] **Rota/harita verisi — pin'ler**: Stitch UI tasarımı incelenirken fark edildi: haritada pin basmak için bile `PlanStop`'ta koordinat yoktu. `PlanStop`'a `name`/`latitude`/`longitude` eklendi; LLM bunları üretmiyor (null bırakıyor), `planner.py::_validate_and_enrich_stops` doğrulanmış mekan havuzundan dolduruyor.
- [ ] **Rota/harita verisi — çizgi**: Duraklar arasında mesafe/süre/rota çizgisi (ör. Google Directions API) hâlâ eksik. Frontend şimdilik sadece pin gösterebilir, adım adım yol tarifi yok (bkz. DESIGN.md 3.5).
- [ ] **Eksik test kapsamı**: `planner.py`'de sadece `_validate_and_enrich_stops` test edildi; Groq çağrısının kendisi (`create_plan`, `resolve_themes`) ve `build_day_plan`'ın uçtan uca akışı hâlâ test edilmiyor.
- [ ] **`.env.example` doldurulması**: Şu an boş dosya; `PLACES_API_KEY`, `MAPS_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL` için placeholder değerlerle doldurulmalı ki yeni katkıda bulunan biri (veya arkadaşın) hızlı kurulum yapabilsin.

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
