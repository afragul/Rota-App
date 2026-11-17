import type { Session } from '../auth'
import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import { hasLocation, locationLabel, type Preferences } from '../prefs'
import { listFrequentPlaces, type VisitedPlace } from '../visitedPlaces'

interface Props {
  prefs: Preferences
  onChange: (p: Preferences) => void
  onContinue: () => void
  // prefs'i güncelleyip aynı anda devam eden, atomik bir seçim — onChange +
  // onContinue'yu art arda çağırmak prefs'in henüz güncellenmemiş (stale)
  // haliyle onContinue'nun hasLocation kontrolüne takılmasına yol açardı.
  onPickFrequent: (place: VisitedPlace) => void
  session: Session | null
  onOpenPrivacy: () => void
}

// Başlangıçta yalnızca şehir/semt seçilir. Kullanıcının GPS konumu burada
// istenmez; plan çıktıktan sonra, ilk durağa nasıl gideceğini göstermek için
// plan detayında kullanılır.
export function LocationScreen({ prefs, onChange, onContinue, onPickFrequent, session, onOpenPrivacy }: Props) {
  const ready = hasLocation(prefs)
  const [frequent, setFrequent] = useState<VisitedPlace[]>([])

  useEffect(() => {
    if (!session) return setFrequent([])
    listFrequentPlaces(session.access_token).then(({ data }) => setFrequent(data ?? []))
  }, [session])

  return (
    <form
      className="flex flex-col w-full pb-6 flex-1"
      onSubmit={(e) => {
        e.preventDefault()
        if (ready) onContinue()
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5 bg-surface-container px-3 py-1 rounded-full">
          <span className="w-2 h-2 rounded-full bg-plan-a animate-pulse" />
          <span className="font-label-sm text-label-sm text-ink font-semibold">Adım 1 / 3</span>
        </div>
        <span className="font-label-sm text-label-sm text-text-secondary">Hızlı Rota Başlangıcı</span>
      </div>

      <div className="flex flex-col gap-1.5 mb-6">
        <h2 className="font-headline-xl-mobile text-headline-xl-mobile text-ink tracking-tight">Nerede plan yapalım?</h2>
        <p className="font-body-md text-body-md text-text-secondary">
          Gününüzü planlamak istediğiniz şehri veya semti yazın.
        </p>
      </div>

      <section className="bg-surface rounded-2xl p-5 shadow-sm mb-6 flex flex-col gap-4">
        <div className="flex items-start gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-primary-fixed/50 flex items-center justify-center flex-shrink-0">
            <Icon name="location_city" fill className="text-primary text-[28px]" />
          </div>
          <div className="flex flex-col min-w-0 flex-1">
            <label htmlFor="district-search" className="font-label-lg text-label-lg text-ink font-semibold">
              Şehir veya semt
            </label>
            <p className="font-body-sm text-body-sm text-text-secondary mt-0.5">
              Yakındaki mekânlar ve hava durumu bu bölgeye göre bulunur.
            </p>
          </div>
        </div>
        <div className="relative flex items-center">
          <Icon name="search" className="text-text-secondary absolute left-3.5 text-[20px] pointer-events-none" />
          <input
            id="district-search"
            type="text"
            autoFocus
            value={prefs.cityInput}
            onChange={(e) => onChange({ ...prefs, cityInput: e.target.value, anchorPlace: null })}
            placeholder="Örn: Beşiktaş, Moda, Alsancak..."
            className="w-full h-12 pl-11 pr-4 bg-surface-container-low text-ink font-body-md text-body-md rounded-xl placeholder:text-text-secondary/70 focus:outline-none focus:bg-surface"
          />
        </div>
      </section>

      {frequent.length > 0 && (
        <section className="bg-surface rounded-2xl p-5 shadow-sm mb-6 flex flex-col gap-3">
          <div className="flex flex-col min-w-0">
            <h3 className="font-label-lg text-label-lg text-ink font-semibold">Sık Gidilen Yerlerin</h3>
            <p className="font-body-sm text-body-sm text-text-secondary mt-0.5">
              Birine dokun, o mekan rotana garanti girsin — süre/bütçe gibi tercihleri yine soracağız.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            {frequent.map((place) => (
              <button
                key={place.place_id}
                type="button"
                onClick={() => onPickFrequent(place)}
                className="flex items-center gap-3 bg-surface-container-low rounded-xl p-3 text-left hover:bg-surface-container-high active:scale-[0.99] transition-all"
              >
                <Icon name="favorite" fill className="text-plan-a text-[20px] flex-shrink-0" />
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="font-label-md text-label-md text-ink truncate">{place.name}</span>
                  {place.address && (
                    <span className="font-body-sm text-body-sm text-text-secondary truncate">{place.address}</span>
                  )}
                </div>
                <Icon name="arrow_forward" className="text-text-secondary text-[18px] flex-shrink-0" />
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="bg-surface-container p-3.5 rounded-xl flex items-center gap-3 mt-1 mb-8">
        <Icon name="near_me" className="text-ink text-[20px] flex-shrink-0" />
        <p className="font-body-sm text-body-sm text-text-secondary leading-snug">
          Plan hazır olunca, bulunduğunuz yerden ilk durağa nasıl gideceğinizi göstermek için konumunuzu isteyeceğiz.{' '}
          <button type="button" onClick={onOpenPrivacy} className="text-primary underline">
            Gizlilik ve Aydınlatma Metni
          </button>
        </p>
      </div>

      <div className="sticky bottom-20 mt-auto pt-2 pb-1 z-30">
        <div className="bg-surface/95 backdrop-blur-md p-2 rounded-2xl shadow-md flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 pl-2 min-w-0">
            <Icon
              name={ready ? 'check_circle' : 'radio_button_unchecked'}
              className={`text-[20px] ${ready ? 'text-success' : 'text-text-secondary'}`}
            />
            <div className="flex flex-col min-w-0">
              <span className="font-label-sm text-label-sm text-ink font-semibold truncate">
                {ready ? `${locationLabel(prefs)} seçildi` : 'Bölge seçilmedi'}
              </span>
              <span className="text-[11px] text-text-secondary">{ready ? 'Hazır' : 'Devam etmek için yazın'}</span>
            </div>
          </div>
          <button
            type="submit"
            disabled={!ready}
            className={`h-11 px-6 font-label-md text-label-md rounded-xl flex items-center gap-1.5 transition-all active:scale-[0.98] disabled:opacity-50 ${
              ready ? 'bg-plan-a text-on-primary shadow-sm' : 'bg-surface-container-high text-ink'
            }`}
          >
            <span>Devam Et</span>
            <Icon name="arrow_forward" className="text-[18px]" />
          </button>
        </div>
      </div>
    </form>
  )
}
