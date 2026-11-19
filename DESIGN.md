# Bugünlük — UI Tasarım Dokümanı

Bu doküman henüz yazılmamış olan frontend/arayüz için bir başlangıç noktasıdır. Backend'de (`app/`) hazır olan uç noktalar ve şemalar (`PlanRequest`, `DayPlan`, `ClarificationNeeded`) referans alınarak hazırlandı; ekranlar ve alanlar API ile birebir eşleşecek şekilde tanımlandı. README.md'deki "Şu anki durum" bölümüyle tutarlı: burada tarif edilen bazı adımlar (şehir arama, indoor/outdoor rozeti, harita rotası) backend'de henüz karşılığı olmayan **hedef** akışlardır, ilgili yerlerde belirtildi.

## 1. Tasarım ilkeleri

- **Az adımda sonuç**: Kullanıcı 3 tıkla (konum → tercih → oluştur) bir plan görmeli. Bütçe ve aktivite türü opsiyonel olduğu için hiçbiri seçilmeden de "Plan Oluştur" aktif olabilmeli.
- **Serbest metin, seçim ekranlarının alternatifi değil tamamlayıcısı**: Kullanıcı chip'lerden seçim yapabilir, serbest metin yazabilir ya da ikisini birden kullanabilir (backend `categories` + `free_text`'i birlikte kabul ediyor).
- **Hava durumu görünür ve gerekçeli olsun**: Sistem neden indoor/karma önerdiğini kullanıcıya kısa bir rozet/cümleyle göstermeli, sonuçların arkasında "kara kutu" hissi olmamalı.
- **Bozulmadan bozulur (graceful degradation)**: Hava durumu alınamazsa (`weather_available: false`) uygulama çökmez, planı yine gösterir ama bunu açıkça belirtir.
- **Mobile-first**: Ana kullanım senaryosu "şu an dışarıdayız, ne yapsak" — küçük ekranda tek elle kullanılabilir olmalı.

## 2. Kullanıcı akışı

```
[1] Konum        [2] Tercihler          [3] Yükleniyor        [4] Sonuç              [5] Plan Detay
Konum izni ---->  Bütçe (opsiyonel) -->  Hava kontrol ----->  2-3 alternatif  ---->  Durak listesi
veya şehir        Aktivite (opsiyonel)   Mekan arama           plan kartı             + harita rota
arama             Serbest metin          Plan kuruluyor        (tema, özet,           + AI notu
                                                                 tahmini maliyet)
```

Geri dönüş: Sonuç ekranından "Tercihleri değiştir" ile 2. adıma, plan detayından "Diğer alternatifler" ile 4. adıma dönülebilir. Adım ilerledikçe önceki seçimler kaybolmaz (state korunur).

## 3. Ekranlar

### 3.1 Konum seçimi
- Birincil aksiyon: "Konumumu kullan" (tarayıcı/cihaz konumu → `latitude`/`longitude`).
- İkincil: şehir/semt arama kutusu. **Backend'de şehir adı → koordinat çözümleme henüz yok**, bu yüzden ilk sürümde arama kutusu bir haritalama servisine (ör. Google Geocoding) bağlanana kadar sadece "konumumu kullan" akışı gerçek veriyle çalışır; arama kutusu UI'da yer tutucu/gelecek özellik olarak işaretlenmeli.
- Devam butonu konum seçilene kadar pasif.

### 3.2 Tercihler
- **Bütçe** — segmented control, 3 seçenek + "farketmez": Düşük / Orta / Yüksek (`BudgetLevel`: `low` / `medium` / `high`). Hiçbiri seçilmezse varsayılan `medium` gönderilir, kullanıcıya bunu seçtirmeye zorlamayın.
- **Grup tipi** — tek seçim: Tek başıma / Çift / Arkadaşlar / Aile (`GroupType`). Varsayılan `friends`.
- **Süre** — saat girişi (stepper, 1-12 saat), varsayılan 4.
- **Aktivite türü** — çoklu seçim chip grubu, backend temalarıyla birebir: Tarihi, Alışveriş, Kafe, Yemek, Açık Hava, Eğlence (`THEME_TYPES` anahtarları: `tarihi`, `alisveris`, `kafe`, `yemek`, `acik_hava`, `eglence`). Hiçbiri seçilmezse `categories` gönderilmez.
- **Serbest metin** — genişleyebilen textarea, placeholder: *"Örn: Ailecek 4 saatimiz var, çocuklarla açık havada bir şeyler yapmak istiyoruz"*. Chip seçimiyle aynı anda kullanılabilir.
- **AI'nin soru sorması** — backend artık destekliyor: `free_text` belirsizse (`categories` boşken) `POST /plan`, `DayPlan` yerine `{"question": "..."}` döner. UI, serbest metin kutusunun altında bir sohbet balonu olarak soruyu göstermeli, kullanıcının cevabını almalı ve aynı `/plan` isteğini `previous_question`/`clarification_answer` alanlarıyla (orijinal tüm alanlarla birlikte) tekrar göndermeli. Backend stateless olduğu için bu iki alanı geri göndermek istemcinin sorumluluğu — istemci state'i kaybederse (ör. sayfa yenilenirse) yeniden başa dönülür, bu kabul edilebilir bir sınırlama.
- Alt bar: "Plan Oluştur" — her zaman aktif (tüm alanlar opsiyonel, sadece konum zorunlu).

### 3.3 Yükleniyor
Tek bir spinner yerine adım göstergesi (kullanıcı neyin beklendiğini görsün, backend paralel çağrı yapıyor ama UI'da sıralı hissettirilebilir):
1. "Hava durumu kontrol ediliyor"
2. "Yakındaki mekânlar aranıyor"
3. "Planın kuruluyor"

Zaman aşımı/hata durumunda (502) adımın kaldığı yerde hata mesajı + "Tekrar dene".

### 3.4 Sonuç — alternatif planlar
- 2-3 `PlanAlternative` kartı, yatay kaydırmalı (mobil) veya yan yana (tablet+).
- Kart içeriği: `theme`, `title`, `summary`, durak sayısı, toplam tahmini maliyet (durakların `estimated_cost` toplamı), ilk 2-3 durağın küçük ikon önizlemesi.
- Üstte **hava rozeti**: sıcaklık + durum + türetilmiş etiket ("Yağışlı — kapalı alan ağırlıklı öneriler" / "Açık — karma öneriler"). `weather_available: false` ise rozet yerine nötr uyarı: "Hava durumu alınamadı, planlar hava açık varsayılarak hazırlandı."
- Karta tıklayınca plan detayına gidilir.

### 3.5 Plan detay
- Üstte seçilen alternatifin başlığı/özeti, sekmeyle diğer alternatiflere geçiş.
- **Zaman çizelgesi (timeline)**: her `PlanStop` için sırayla — `order`, `arrival_time`, `duration_minutes`, `activity`, `recommendation`, `estimated_cost`, `name`. Dikey timeline, her durak bir kart.
- **Harita**: duraklar pin olarak işaretli, aralarında rota çizgisi. `PlanStop.latitude`/`.longitude` artık API'den geliyor, pin basmak için yeterli. **Rota verisi artık API'de**: `PlanAlternative.legs` her ardışık durak çifti için `from_order`/`to_order`, `travel_mode`, `distance_meters`, `duration_minutes` ve encoded `polyline` içeriyor. Duraklar arası "🚶 15 dk yürüyüş (1.1 km)" rozeti bu alanlardan beslenir (ikon/metin `travel_mode`'a göre: yürüyüş, toplu taşıma, araç; kullanıcı `PlanRequest.travel_mode` ile seçer, tercihler ekranına bir seçici eklenmeli); harita çizgisi için polyline decode edilir. `legs` boşsa sadece pin gösterilir; `routes_available=false` ise rota servisi çalışmadı demektir (UI "rota alınamadı" notu gösterebilir), tek duraklı planda ise `true` kalır. Adım adım talimat artık `legs[].steps` içinde: Türkçe `instruction`, `maneuver` (ikon), `distance_meters`; toplu taşıma adımlarında `transit` (hat, araç, yön, biniş/iniş durağı). Kullanıcının konumundan ilk durağa rota `POST /route/approach` ile alınır ve plan detayında gösterilir.
- Alt bar: "Bu planı paylaş" / "Tercihleri değiştir".

## 4. Bileşen envanteri

| Bileşen | Kullanıldığı ekran | Not |
| --- | --- | --- |
| `LocationPicker` | 3.1 | Konum izni + (ileride) şehir arama |
| `BudgetSegmentedControl` | 3.2 | 3 seçenek + "farketmez" |
| `GroupTypeSelector` | 3.2 | Tek seçim |
| `DurationStepper` | 3.2 | 1-12 saat |
| `ActivityChipGroup` | 3.2 | Çoklu seçim, backend tema anahtarlarıyla eşleşir |
| `FreeTextPrompt` | 3.2 | Textarea, chip seçimiyle birlikte kullanılabilir |
| `WeatherBadge` | 3.4, 3.5 | Sıcaklık + durum + indoor/karma etiketi; `weather_available=false` varyantı var |
| `StepProgress` | 3.3 | 3 adımlı yükleniyor göstergesi |
| `PlanAlternativeCard` | 3.4 | Tema, başlık, özet, toplam maliyet |
| `StopTimelineItem` | 3.5 | Tek durak kartı |
| `RouteMap` | 3.5 | v1: sadece pin'ler, v2: rota çizgisi |
| `ErrorBanner` | Tüm ekranlar | 502/boş sonuç durumları için |

## 5. Görsel dil (başlangıç önerisi)

Henüz sabit bir marka kimliği yok; aşağıdaki değerler ilk uygulama için öneridir, marka/tasarım sistemi netleştikçe güncellenmeli.

- **Renk**: Nötr bir taban (kırık beyaz/koyu gri) üzerine, hava durumuna göre değişen tek bir vurgu rengi — güneşli/açık için sıcak turuncu-sarı, yağışlı/kapalı için soğuk mavi-gri. Bu, "hava durumuna göre plan değişiyor" fikrini sezgisel olarak taşır.
- **Tipografi**: Başlıklarda karakterli, gövde metinde okunaklı bir sistem fontu (ör. Inter). Türkçe karakter desteği zorunlu.
- **İkonografi**: Aktivite türleri (tarihi, kafe, açık hava vb.) için tutarlı bir ikon seti — chip'lerde, timeline'da ve kartlarda aynı ikonlar tekrar kullanılmalı.
- **Boşluk/grid**: Mobilde tek kolon, kenar boşluğu geniş (dokunma hedefleri büyük — form aile/grup kullanımında telefon elden ele gezebilir).
- **Karanlık mod**: Uygulama açık hava aktivitesi önerdiği için gündüz kullanımı yoğun olacak; yine de sistem temasına uyan bir karanlık mod planlanmalı.

## 6. Durum (state) tasarımı

| Durum | Tetikleyici | Davranış |
| --- | --- | --- |
| Hava alınamadı | `weather_available: false` | Nötr uyarı rozeti, plan yine gösterilir |
| Mekân bulunamadı | `/plan` → 502 (`PlacesServiceError`) | "Bu bölgede uygun mekân bulunamadı" + konumu değiştirme önerisi |
| Plan üretilemedi | `/plan` → 502 (`PlannerServiceError`) | "Plan oluşturulamadı, tekrar dener misin?" + tekrar dene butonu |
| Bazı duraklar elendi | Backend geçersiz `place_id` içeren durakları sessizce eler | UI'da fark edilmez, kullanıcıya ayrıca gösterilmez — timeline zaten elenmiş listeyle gelir |
| Boş form | Hiçbir tercih seçilmedi | Sorun değil, varsayılanlarla (`medium` bütçe, `friends`, 4 saat, tema yok) devam edilir |
| Netleştirme gerekli | `/plan` → `{"question": "..."}` (`DayPlan` değil) | Soru sohbet balonu olarak gösterilir; cevap alınınca aynı istek `previous_question`/`clarification_answer` ile bir kez daha gönderilir |

## 7. API ↔ UI alan eşlemesi

| UI alanı | Backend alanı (`PlanRequest`) |
| --- | --- |
| Konum | `latitude`, `longitude` |
| Süre stepper | `duration_hours` |
| Bütçe segmented control | `budget` (`low`/`medium`/`high`) |
| Grup tipi | `group_type` (`solo`/`couple`/`friends`/`family`) |
| Aktivite chip'leri | `categories` |
| Serbest metin | `free_text` |

| UI alanı | Backend alanı (`DayPlan` / `PlanAlternative` / `PlanStop`) |
| --- | --- |
| Hava rozeti | `weather_available` |
| Alternatif kartı | `alternatives[].theme`, `.title`, `.summary` |
| Timeline item | `stops[].order`, `.arrival_time`, `.duration_minutes`, `.activity`, `.recommendation`, `.estimated_cost`, `.name` |
| Harita pin'i | `stops[].latitude`, `.longitude` |

## 8. Sonraki adımlar

- Bu dokümandaki bileşenlerden düşük dosyalık bir wireframe seti (Figma) çıkarılabilir.
- Harita/rota ve şehir arama bileşenleri, backend'deki ilgili özellikler (geocoding, rota üretimi) hazır olana kadar UI'da "yakında" durumunda tutulmalı, sahte veriyle tasarlanmamalı.