import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import { GROUPS } from '../meta'
import { locationLabel, type Preferences } from '../prefs'

const STEPS = [
  { title: 'Hava durumu kontrol ediliyor', desc: 'Planın hava koşullarına göre şekillenmesi için anlık durum alınıyor.' },
  { title: 'Yakındaki mekânlar aranıyor', desc: 'Seçtiğiniz aktivitelere uygun yakın mekânlar taranıyor...' },
  { title: 'Planın kuruluyor', desc: 'Duraklar, zaman çizelgesi ve duraklar arası rota hesaplanıyor.' },
]

// Backend tek istekte çalışır; adımlar zamanlayıcıyla sıralı hissettirilir ve
// sonuncu adım yanıt gelene kadar "devam ediyor" kalır.
export function LoadingScreen({ prefs, onCancel }: { prefs: Preferences; onCancel: () => void }) {
  const [active, setActive] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setActive((a) => Math.min(a + 1, STEPS.length - 1)), 2500)
    return () => clearInterval(id)
  }, [])

  const group = GROUPS.find((g) => g.value === prefs.group)!

  return (
    <div className="flex flex-col w-full pb-6">
      <div className="flex flex-col items-center justify-center pt-2 pb-6 px-space-xs text-center">
        <div className="relative w-20 h-20 flex items-center justify-center mb-space-md">
          <span className="absolute inline-flex h-full w-full rounded-full bg-primary-fixed opacity-40 animate-ping" />
          <span className="absolute inline-flex h-16 w-16 rounded-full bg-weather-good-bg opacity-70 animate-pulse" />
          <div className="relative z-10 w-14 h-14 rounded-full bg-surface shadow-sm flex items-center justify-center">
            <Icon name="explore" className="text-primary text-[28px] animate-spin [animation-duration:4s]" />
          </div>
        </div>
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-ink tracking-tight mb-space-xs">Rotanız Hazırlanıyor</h2>
        <p className="font-body-md text-body-md text-text-secondary max-w-xs leading-relaxed">
          {locationLabel(prefs)} çevresi için {group.phrase} ve {prefs.duration} saatlik süreye uygun duraklar derleniyor...
        </p>
      </div>

      <div className="w-full bg-surface rounded-xl shadow-sm p-margin mb-space-xl" aria-live="polite">
        {STEPS.map((step, i) => {
          const done = i < active
          const current = i === active
          const last = i === STEPS.length - 1
          return (
            <div key={step.title} className={`relative flex items-start gap-space-md ${last ? '' : 'pb-space-xl'}`}>
              {!last && <div className={`absolute left-4 top-8 -bottom-1 w-[2px] ${done ? 'bg-success' : 'bg-surface-variant'}`} />}
              {done ? (
                <div className="relative z-10 w-8 h-8 rounded-full bg-success flex items-center justify-center flex-shrink-0 shadow-sm">
                  <Icon name="check" className="text-surface text-[18px]" />
                </div>
              ) : current ? (
                <div className="relative z-10 w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center flex-shrink-0">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-primary opacity-30 animate-ping" />
                  <div className="w-3.5 h-3.5 rounded-full bg-primary animate-pulse" />
                </div>
              ) : (
                <div className="relative z-10 w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center flex-shrink-0">
                  <Icon name="hourglass_empty" className="text-text-secondary text-[16px]" />
                </div>
              )}
              <div className="flex-1 min-w-0 pt-0.5">
                <div className="flex items-center justify-between gap-space-xs mb-space-xs">
                  <span className={`font-label-md text-label-md font-semibold truncate ${current || done ? 'text-ink' : 'text-text-secondary'}`}>
                    {step.title}
                  </span>
                  {current && (
                    <span className="px-2 py-0.5 rounded-full bg-primary-fixed text-primary font-label-sm text-[11px] flex-shrink-0 font-medium">
                      Devam ediyor
                    </span>
                  )}
                  {!done && !current && (
                    <span className="px-2 py-0.5 rounded-full bg-surface-container text-text-secondary font-label-sm text-[11px] flex-shrink-0">
                      Sırada
                    </span>
                  )}
                </div>
                <p className="font-body-sm text-body-sm text-text-secondary leading-normal">{step.desc}</p>
              </div>
            </div>
          )
        })}
      </div>

      <div className="w-full bg-surface-container-low rounded-xl p-space-md flex flex-col gap-space-md">
        <div className="flex items-start gap-space-sm">
          <Icon name="info" className="text-text-secondary text-[20px] flex-shrink-0 mt-0.5" />
          <p className="font-body-sm text-body-sm text-text-secondary leading-relaxed">
            Bağlantı durumuna göre işlem birkaç saniye sürebilir.
          </p>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="w-full h-12 rounded-xl bg-surface text-ink font-label-md text-label-md flex items-center justify-center gap-space-xs active:bg-surface-variant transition-colors"
        >
          <Icon name="close" className="text-[18px]" />
          <span>İptal Et</span>
        </button>
      </div>
    </div>
  )
}
