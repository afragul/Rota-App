import { useState } from 'react'
import { Icon } from '../components/Icon'
import { hasLocation, locationLabel, type Preferences } from '../prefs'

interface Props {
  prefs: Preferences
  onChange: (p: Preferences) => void
  onContinue: () => void
}

type Geo = 'idle' | 'loading' | 'error'

export function LocationScreen({ prefs, onChange, onContinue }: Props) {
  const [geo, setGeo] = useState<Geo>('idle')
  const ready = hasLocation(prefs)

  const useMyLocation = () => {
    if (!navigator.geolocation) return setGeo('error')
    setGeo('loading')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeo('idle')
        onChange({
          ...prefs,
          cityInput: '',
          coords: {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy: Math.round(pos.coords.accuracy),
          },
        })
      },
      () => setGeo('error'),
      { timeout: 10000 },
    )
  }

  return (
    <div className="flex flex-col w-full pb-6 flex-1">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5 bg-surface-container px-3 py-1 rounded-full">
          <span className="w-2 h-2 rounded-full bg-plan-a animate-pulse" />
          <span className="font-label-sm text-label-sm text-ink font-semibold">Adım 1 / 3</span>
        </div>
        <span className="font-label-sm text-label-sm text-text-secondary">Hızlı Rota Başlangıcı</span>
      </div>

      <div className="flex flex-col gap-1.5 mb-6">
        <h2 className="font-headline-xl-mobile text-headline-xl-mobile text-ink tracking-tight">Nereden başlayalım?</h2>
        <p className="font-body-md text-body-md text-text-secondary">
          Gününüzü planlamak için mevcut konumunuzu belirleyin.
        </p>
      </div>

      <section className="bg-surface rounded-2xl p-5 shadow-sm mb-6 flex flex-col gap-4" aria-labelledby="gps-card-title">
        <div className="flex items-start gap-3.5">
          <div className="relative w-12 h-12 rounded-2xl bg-primary-fixed/50 flex items-center justify-center flex-shrink-0">
            <Icon name="near_me" fill className="text-primary text-[28px]" />
            {geo === 'loading' && <span className="absolute inset-0 rounded-2xl bg-primary/10 animate-ping pointer-events-none" />}
          </div>
          <div className="flex flex-col min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 id="gps-card-title" className="font-label-lg text-label-lg text-ink font-semibold">
                Mevcut Konumumu Kullan
              </h3>
              {prefs.coords && (
                <span className="inline-flex items-center gap-1 bg-surface-container-high px-2 py-0.5 rounded text-[11px] font-medium text-success">
                  <span className="w-1.5 h-1.5 rounded-full bg-success" />
                  Canlı GPS
                </span>
              )}
            </div>
            {prefs.coords ? (
              <>
                <p className="font-body-md text-body-md text-ink font-medium mt-0.5">Konumunuz alındı</p>
                <div className="flex items-center gap-1.5 text-text-secondary mt-1">
                  <Icon name="my_location" className="text-[16px]" />
                  <span className="font-label-sm text-label-sm">Doğruluk: ~{prefs.coords.accuracy} metre</span>
                </div>
              </>
            ) : (
              <p className="font-body-sm text-body-sm text-text-secondary mt-0.5">
                Yakındaki mekânları ve hava durumunu bulmak için konum izni verin.
              </p>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={useMyLocation}
          disabled={geo === 'loading'}
          className="w-full h-[52px] bg-plan-a hover:bg-primary-strong active:bg-primary-strong text-on-primary font-label-lg text-label-lg rounded-2xl flex items-center justify-center gap-2 shadow-sm transition-transform active:scale-[0.98] disabled:opacity-60"
        >
          <Icon name="explore" className="text-[20px]" />
          <span>{geo === 'loading' ? 'Konum alınıyor…' : prefs.coords ? 'Konumu Yenile' : 'Konumumu Kullan'}</span>
        </button>
        {geo === 'error' && (
          <p className="font-body-sm text-body-sm text-error" role="alert">
            Konum alınamadı. Aşağıdan şehir veya semt yazabilirsiniz.
          </p>
        )}
      </section>

      <div className="relative flex items-center justify-center my-2">
        <div className="w-full h-px bg-surface-variant" />
        <span className="absolute bg-background px-4 font-label-md text-label-md text-text-secondary lowercase">veya</span>
      </div>

      <div className="flex flex-col gap-2 mt-4 mb-5">
        <label htmlFor="district-search" className="font-label-md text-label-md text-ink font-semibold">
          Şehir veya semt ara
        </label>
        <div className="relative flex items-center">
          <Icon name="search" className="text-text-secondary absolute left-3.5 text-[20px] pointer-events-none" />
          <input
            id="district-search"
            type="text"
            value={prefs.cityInput}
            onChange={(e) => onChange({ ...prefs, cityInput: e.target.value, coords: null })}
            placeholder="Örn: Beşiktaş, Moda, Alsancak..."
            className="w-full h-12 pl-11 pr-4 bg-surface-container-low text-ink font-body-md text-body-md rounded-xl placeholder:text-text-secondary/70 focus:outline-none focus:bg-surface"
          />
        </div>
      </div>

      <div className="bg-surface-container p-3.5 rounded-xl flex items-center gap-3 mt-1 mb-8">
        <Icon name="shield" className="text-ink text-[20px] flex-shrink-0" />
        <p className="font-body-sm text-body-sm text-text-secondary leading-snug">
          Konumunuz yalnızca rota mesafelerini ve anlık hava durumunu hesaplamak için geçici olarak işlenir; kaydedilmez.
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
                {ready ? `${locationLabel(prefs)} seçildi` : 'Konum seçilmedi'}
              </span>
              <span className="text-[11px] text-text-secondary">{ready ? 'Hazır' : 'Devam etmek için konum seçin'}</span>
            </div>
          </div>
          <button
            type="button"
            disabled={!ready}
            onClick={onContinue}
            className={`h-11 px-6 font-label-md text-label-md rounded-xl flex items-center gap-1.5 transition-all active:scale-[0.98] disabled:opacity-50 ${
              ready ? 'bg-plan-a text-on-primary shadow-sm' : 'bg-surface-container-high text-ink'
            }`}
          >
            <span>Devam Et</span>
            <Icon name="arrow_forward" className="text-[18px]" />
          </button>
        </div>
      </div>
    </div>
  )
}
