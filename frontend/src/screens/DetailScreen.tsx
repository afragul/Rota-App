import { useState } from 'react'
import { Icon } from '../components/Icon'
import { RouteMap } from '../components/RouteMap'
import { TRAVEL_MODES, formatCost, formatDistance, formatHours, planStyle } from '../meta'
import type { DayPlan } from '../types'

interface Props {
  plan: DayPlan
  index: number
  onSelect: (index: number) => void
  onPrefs: () => void
}

export function DetailScreen({ plan, index, onSelect, onPrefs }: Props) {
  const alt = plan.alternatives[index]
  const s = planStyle(index)
  const stops = [...alt.stops].sort((a, b) => a.order - b.order)
  const minutes = stops.reduce((sum, st) => sum + st.duration_minutes, 0)
  const cost = stops.reduce((sum, st) => sum + st.estimated_cost, 0)
  const [arrived, setArrived] = useState<Set<number>>(new Set())
  const [shared, setShared] = useState(false)
  const w = plan.weather

  const toggleArrived = (order: number) =>
    setArrived((prev) => {
      const next = new Set(prev)
      if (!next.delete(order)) next.add(order)
      return next
    })

  const share = async () => {
    const text = `${alt.title}\n${stops.map((st) => `${st.arrival_time} ${st.name ?? st.activity}`).join('\n')}`
    try {
      if (navigator.share) await navigator.share({ title: alt.title, text })
      else {
        await navigator.clipboard.writeText(text)
        setShared(true)
        setTimeout(() => setShared(false), 2000)
      }
    } catch {
      /* paylaşım iptal edildi */
    }
  }

  return (
    <div className="flex flex-col w-full pb-24">
      <div role="tablist" className="flex items-center gap-space-xs mb-space-lg overflow-x-auto py-space-xs">
        {plan.alternatives.map((a, i) => {
          const st = planStyle(i)
          const on = i === index
          return (
            <button
              key={a.title}
              role="tab"
              aria-selected={on}
              onClick={() => onSelect(i)}
              className={`h-10 px-space-md rounded-full flex items-center gap-space-xs shadow-sm flex-shrink-0 transition-transform active:scale-95 ${
                on ? `${st.bg} text-on-primary` : 'bg-surface text-ink hover:bg-surface-container-low'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${on ? 'bg-on-primary' : st.bg}`} />
              <span className="font-label-md text-label-md whitespace-nowrap">
                {st.name} · {a.theme}
              </span>
            </button>
          )
        })}
      </div>

      <div className="bg-surface rounded-xl p-space-md shadow-sm mb-space-lg">
        <div className="flex items-center justify-between gap-space-xs mb-space-xs">
          {w ? (
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-label-sm text-label-sm ${
                w.is_bad ? 'bg-weather-bad-bg text-ink' : 'bg-weather-good-bg text-tertiary'
              }`}
            >
              <Icon
                name={w.is_bad ? 'rainy' : 'wb_sunny'}
                fill
                className={`text-[16px] ${w.is_bad ? 'text-weather-bad' : 'text-weather-good'}`}
              />
              <span className="capitalize">{w.condition}</span> • {Math.round(w.temperature)}°C
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-weather-unknown-bg text-weather-unknown font-label-sm text-label-sm">
              <Icon name="cloud_off" className="text-[16px]" />
              Hava bilgisi yok
            </span>
          )}
          <span className="font-label-sm text-label-sm text-text-secondary bg-surface-container px-2.5 py-1 rounded-full">
            Toplam {formatHours(minutes)}
          </span>
        </div>
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-ink mb-space-xs">{alt.title}</h2>
        <p className="font-body-md text-body-md text-text-secondary leading-relaxed">
          {alt.summary} • Kişi başı {formatCost(cost)}
        </p>
      </div>

      <div className="bg-surface-container rounded-xl p-space-sm shadow-sm mb-space-xl">
        <RouteMap alternative={alt} color={s.hex} />
        {!alt.routes_available && (
          <p className="font-body-sm text-[11px] text-text-secondary text-center pt-space-xs">
            Rota çizgisi alınamadı, yalnızca duraklar gösteriliyor.
          </p>
        )}
      </div>

      <ol className="relative pl-6 mb-space-xl">
        <div className="absolute left-[13px] top-4 bottom-6 w-0.5 bg-surface-variant" />
        {stops.map((stop, i) => {
          const leg = alt.legs.find((l) => l.from_order === stop.order)
          const done = arrived.has(stop.order)
          return (
            <li key={stop.order} className="relative">
              <div
                className={`absolute -left-6 top-1.5 w-7 h-7 rounded-full ${s.bg} text-on-primary flex items-center justify-center font-label-md text-label-md shadow-sm ring-4 ring-background`}
              >
                {stop.order}
              </div>
              <div className="bg-surface rounded-xl p-space-md shadow-sm ml-2">
                <div className="flex items-center gap-1.5 mb-space-xs">
                  <span className={`font-label-md text-label-md ${s.text}`}>{stop.order}. Durak</span>
                  <span className="text-text-secondary text-xs">•</span>
                  <span className="font-label-sm text-label-sm text-text-secondary">
                    {stop.arrival_time} ({stop.duration_minutes} dk)
                  </span>
                </div>
                <h3 className="font-headline-md text-headline-md text-ink mb-space-xs">{stop.name ?? stop.activity}</h3>
                <div className="bg-surface-container-low rounded-lg p-2.5 mt-space-xs mb-space-xs flex flex-col gap-1.5">
                  <p className="font-body-md text-body-md text-on-surface-variant">{stop.activity}</p>
                  <p className="font-body-md text-body-md text-on-surface-variant">💡 {stop.recommendation}</p>
                </div>
                <div className="flex items-center justify-between pt-space-xs">
                  <span className="inline-flex items-center gap-1 font-label-sm text-label-sm text-ink bg-surface-container px-2 py-1 rounded-full">
                    💰 {formatCost(stop.estimated_cost)} / kişi
                  </span>
                  <button
                    type="button"
                    aria-pressed={done}
                    onClick={() => toggleArrived(stop.order)}
                    className={`flex items-center gap-1 text-xs font-label-sm transition-colors ${
                      done ? 'text-success' : 'text-text-secondary hover:text-ink'
                    }`}
                  >
                    <Icon name="check_circle" fill={done} className="text-[18px]" />
                    <span>Ulaşıldı</span>
                  </button>
                </div>
              </div>

              {leg && i < stops.length - 1 && (
                <div className="relative ml-2 my-space-sm pl-4 flex items-center gap-2 py-1">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-highest text-ink font-label-sm text-label-sm">
                    <span aria-hidden>{TRAVEL_MODES[leg.travel_mode].emoji}</span>
                    <span>
                      {leg.duration_minutes} dk {TRAVEL_MODES[leg.travel_mode].verb} ({formatDistance(leg.distance_meters)})
                    </span>
                  </div>
                </div>
              )}
              {i < stops.length - 1 && !leg && <div className="h-space-lg" />}
            </li>
          )
        })}
      </ol>

      <div className="fixed bottom-16 left-0 right-0 z-40 bg-gradient-to-t from-background via-background/95 to-transparent pt-4 pb-3 px-margin">
        <div className="max-w-md mx-auto flex gap-space-sm">
          <button
            type="button"
            onClick={onPrefs}
            className="flex-1 h-12 rounded-xl bg-surface text-ink font-label-md text-label-md flex items-center justify-center gap-space-xs shadow-sm"
          >
            <Icon name="tune" className="text-[18px]" />
            Tercihleri Değiştir
          </button>
          <button
            type="button"
            onClick={share}
            className="flex-1 h-12 rounded-xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-md text-label-md flex items-center justify-center gap-space-xs shadow-sm"
          >
            <Icon name={shared ? 'check' : 'share'} className="text-[18px]" />
            {shared ? 'Kopyalandı' : 'Bu Planı Paylaş'}
          </button>
        </div>
      </div>
    </div>
  )
}
