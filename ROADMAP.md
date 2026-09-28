# Yol Haritası

Backend önce tamamlanıp sonra frontend'e geçilecek şekilde sıralandı. README.md "Şu anki durum" ve DESIGN.md "Sonraki adımlar" bölümleriyle tutarlıdır; oradaki eksikler burada somut görevlere bölündü.

## Milestone 1 — Backend'i tamamla

- [x] **Şehir/adres → koordinat çözümleme**: `/plan` artık `latitude`/`longitude` ikilisi yerine `city` de kabul ediyor (`app/services/geocoding.py`, Google Geocoding API). `MAPS_API_KEY` bunun için kullanılmaya başlandı. Bağımsız test için `GET /geocode` eklendi.
- [ ] **Hava durumuna göre kural bazlı indoor/outdoor ağırlıklandırma**: Şu an hava durumu sadece metin olarak LLM'e veriliyor, karar tamamen modele bırakılmış. `orchestrator.py` ya da `planner.py` seviyesinde açık bir kural eklenmeli (ör. yağmur/kar kodlarında tema havuzu otomatik olarak indoor ağırlıklı türlere daraltılsın).
- [ ] **Rota/harita verisi**: Planlanan duraklar arasında mesafe/süre/rota (ör. Google Directions API) üretilip `PlanStop`'a veya `DayPlan`'a eklenmeli, frontend'in haritada çizgi çizebilmesi için.
- [ ] **Eksik test kapsamı**: `weather.py`, `planner.py`, `orchestrator.py` için hiç test yok (sadece `places.py` test edilmiş). En azından hata yollarını (Groq çağrısı başarısız, şema uymuyor, hava alınamıyor) kapsayan testler eklenmeli.
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
