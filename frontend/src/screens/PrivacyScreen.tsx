import type { ReactNode } from 'react'

// TODO(yayın öncesi): veri sorumlusu bilgileri ve barındırıcı netleşince doldurulacak;
// metnin tamamı ayrıca bir hukuk uzmanına gösterilmeli (bkz. ROADMAP "KVKK hazırlığı").
const CONTROLLER = '[Veri sorumlusunun adı / unvanı]'
const CONTACT = '[KVKK başvuru e-posta adresi]'
const HOSTING = '[Barındırıcı ve sunucunun bulunduğu ülke]'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-space-xs">
      <h3 className="font-headline-md text-headline-md text-ink">{title}</h3>
      <div className="font-body-md text-body-md text-text-secondary flex flex-col gap-space-xs">{children}</div>
    </section>
  )
}

// Gizlilik ve aydınlatma metni: ne toplanıyor, nereye gidiyor, ne kadar tutuluyor, hakların neler.
// İçerik, ROADMAP'teki "veri envanteri"nden çıkarıldı; kodda veri akışı değişince burası da güncellenmeli.
export function PrivacyScreen() {
  return (
    <div className="flex flex-col gap-space-lg pt-space-lg pb-space-lg">
      <div className="flex flex-col gap-1.5">
        <h2 className="font-headline-xl-mobile text-headline-xl-mobile text-ink tracking-tight">
          Gizlilik ve Aydınlatma Metni
        </h2>
        <p className="font-body-md text-body-md text-text-secondary">
          6698 sayılı Kişisel Verilerin Korunması Kanunu kapsamında, verilerinin nasıl işlendiğini burada anlatıyoruz.
        </p>
      </div>

      <Section title="Veri sorumlusu">
        <p>{CONTROLLER}</p>
        <p>İletişim: {CONTACT}</p>
      </Section>

      <Section title="Hangi verileri işliyoruz?">
        <p>
          <strong className="text-ink">Rota planı isteği (hesap gerekmez):</strong> yazdığın şehir/semt, seçtiğin
          aktivite türleri, süre, bütçe, grup türü ve varsa serbest metin. Plan oluşturmak için kullanılır.
        </p>
        <p>
          <strong className="text-ink">Cihaz konumu:</strong> yalnızca rota/navigasyon için ve sen tarayıcı izni
          verirsen alınır. Bulunduğun yerden ilk durağa yol tarifi hesaplamak için gönderilir; sunucumuzda kalıcı
          olarak saklanmaz.
        </p>
        <p>
          <strong className="text-ink">Hesap (isteğe bağlı):</strong> e-posta adresi, kullanıcı adı ve şifren (şifre
          yalnızca geri döndürülemez özet olarak tutulur). Hesabınla kaydettiğin planlar, favori mekanların ve
          &ldquo;Ulaşıldı&rdquo; dediğin mekanların ziyaret geçmişi.
        </p>
        <p>
          <strong className="text-ink">Teknik veriler:</strong> IP adresin hız sınırı ve günlük kullanım kotası için
          kullanılır ve sunucu erişim kayıtlarında yer alabilir. Oturumun için tarayıcında bir erişim anahtarı, tema
          ve misafir plan sayacı ile bir oturum çerezi (<code>bugunluk_refresh</code>) tutulur. Sayfayı yenileyince planın kaybolmasın diye son planın, tercihlerin ve açık ekranın yalnızca bu cihazın tarayıcısında saklanır (12 saat sonra geçersiz sayılır); sunucuya gönderilmez, çıkış yapınca ya da hesabını silince temizlenir.
        </p>
      </Section>

      <Section title="Neden ve hangi hukuki sebeple?">
        <p>
          Verilerini planı oluşturmak, hesabını yönetmek ve hizmeti kötüye kullanıma karşı korumak için işliyoruz.
          Sözleşmenin kurulması ve ifası ile meşru menfaatimiz bu işlemlerin dayanağıdır. Konum verisi için açık
          rıza gerekip gerekmediği ayrıca değerlendirilmektedir; konum izni her zaman tarayıcı izni olarak sana
          sorulur ve istediğin an geri çekebilirsin.
        </p>
      </Section>

      <Section title="Verilerin kimlere aktarılıyor?">
        <p>Hizmeti sunabilmek için aşağıdaki sağlayıcılara yalnızca gerekli veri gönderilir:</p>
        <ul className="list-disc pl-5 flex flex-col gap-1">
          <li>
            <strong className="text-ink">Google</strong> (Geocoding, Places, Routes): yazdığın yer, arama konumu ve
            rota hesabı için konumlar.
          </li>
          <li>
            <strong className="text-ink">Groq</strong> (yapay zekâ): tercihlerin, varsa serbest metnin ve bulunan
            mekân listesi; planı yazmak için.
          </li>
          <li>
            <strong className="text-ink">Open-Meteo</strong>: hava durumu için konum koordinatı.
          </li>
          <li>
            <strong className="text-ink">Barındırıcı</strong>: {HOSTING}. Hesap verilerin bu sunucudaki veritabanında
            durur.
          </li>
        </ul>
        <p>
          Bu sağlayıcılar yurt dışında olabilir; bu durum verilerin yurt dışına aktarılması anlamına gelir. Verilerini
          reklam için satmayız veya paylaşmayız.
        </p>
      </Section>

      <Section title="Ne kadar saklıyoruz?">
        <p>
          Hesap verilerin, sen hesabını silene kadar saklanır. Hesabım ekranındaki &ldquo;Hesabımı sil&rdquo; ile hesabın
          ve ona bağlı tüm veriler (kayıtlı planlar, favoriler, ziyaret geçmişi, oturumlar) kalıcı olarak silinir. Misafir
          olarak yaptığın plan istekleri hesabına bağlanmaz.
        </p>
      </Section>

      <Section title="Haklarının neler?">
        <p>KVKK madde 11 uyarınca şunları isteyebilirsin:</p>
        <ul className="list-disc pl-5 flex flex-col gap-1">
          <li>Verilerinin işlenip işlenmediğini öğrenmek ve bilgi talep etmek,</li>
          <li>İşlenme amacını ve amacına uygun kullanılıp kullanılmadığını öğrenmek,</li>
          <li>Yurt içinde/dışında aktarıldığı kişileri bilmek,</li>
          <li>Eksik veya yanlış işlenmişse düzeltilmesini istemek,</li>
          <li>Silinmesini veya yok edilmesini istemek (hesabını uygulamadan kendin silebilirsin),</li>
          <li>İşlemeye itiraz etmek ve zarar görürsen tazminat talep etmek.</li>
        </ul>
        <p>Başvuruların için: {CONTACT}</p>
      </Section>
    </div>
  )
}
