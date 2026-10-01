import { useState } from 'react'
import { Icon } from '../components/Icon'
import { WeatherBadge } from '../components/WeatherBadge'
import { TRAVEL_MODES, formatCost, formatHours, planStyle } from '../meta'
import { locationLabel, type Preferences } from '../prefs'
import type { DayPlan } from '../types'

interface Props {
  plan: DayPlan
  prefs: Preferences
  onOpen: (index: number) => void
  onPrefs: () => void
}

export function ResultsScreen({ plan, prefs, onOpen, onPrefs }: Props) {
  const [selected, setSelected] = useState(0)
  const mode = TRAVEL_MODES[prefs.travelMode]
  const n = plan.alternatives.length

  return (
    <div className="flex flex-col w-full gap-space-lg pb-6">
      <WeatherBadge plan={plan} />

      <div className="pt-1">
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-ink">{n} Hazır Rota Bulundu</h2>
        <p className="font-body-sm text-body-sm text-text-secondary">{locationLabel(prefs)} • Bugün için hazırlandı</p>
      </div>

      <div className="flex flex-col gap-space-lg" role="radiogroup" aria-label="Alternatif planlar">
        {plan.alternatives.map((alt, i) => {
          const s = planStyle(i)
          const minutes = alt.stops.reduce((sum, st) => sum + st.duration_minutes, 0)
          const cost = alt.stops.reduce((sum, st) => sum + st.estimated_cost, 0)
          const on = selected === i
          return (
            <article
              key={alt.title}
              role="radio"
              aria-checked={on}
              tabIndex={0}
              onClick={() => setSelected(i)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  setSelected(i)
                }
              }}
              className={`w-full bg-surface rounded-2xl shadow-sm overflow-hidden flex flex-col transition-transform active:scale-[0.99] cursor-pointer ${
                on ? 'ring-2 ring-plan-a/40' : ''
              }`}
            >
              <div className={`w-full h-1.5 ${s.bg}`} />
              <div className="p-space-lg flex flex-col gap-space-md">
                <div className="flex items-center justify-between gap-space-sm">
                  <div className="flex items-center gap-space-xs min-w-0">
                    <span className={`px-2.5 py-0.5 rounded-full ${s.bg} text-on-primary font-label-sm text-label-sm uppercase tracking-wide shrink-0`}>
                      {s.name}
                    </span>
                    <span className="font-label-sm text-label-sm text-text-secondary truncate">{alt.theme}</span>
                  </div>
                  <Icon name={on ? 'check_circle' : mode.icon} fill={on} className={`text-[20px] ${on ? 'text-plan-a' : 'text-text-secondary'}`} />
                </div>

                <div>
                  <h3 className="font-headline-md text-headline-md text-ink">{alt.title}</h3>
                  <p className="font-body-md text-body-md text-text-secondary mt-1">{alt.summary}</p>
                </div>

                <div className="flex items-center gap-3 bg-surface-container-low px-space-md py-2 rounded-xl text-xs font-label-sm text-ink">
                  <div className="flex items-center gap-1">
                    <Icon name="schedule" className={`text-[16px] ${s.text}`} />
                    <span>{formatHours(minutes)}</span>
                  </div>
                  <span className="text-text-secondary">•</span>
                  <div className="flex items-center gap-1">
                    <Icon name="location_on" className={`text-[16px] ${s.text}`} />
                    <span>{alt.stops.length} Durak</span>
                  </div>
                  <span className="text-text-secondary">•</span>
                  <div className="flex items-center gap-1">
                    <Icon name="payments" className={`text-[16px] ${s.text}`} />
                    <span>{formatCost(cost)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 overflow-x-auto py-1 text-xs font-label-sm text-ink">
                  {alt.stops.map((stop, j) => (
                    <div key={stop.order} className="flex items-center gap-2 shrink-0">
                      {j > 0 && <Icon name="arrow_forward" className="text-text-secondary text-[14px]" />}
                      <div className="flex items-center gap-1 bg-surface-container px-2.5 py-1.5 rounded-lg">
                        <Icon name="location_on" className={`text-[16px] ${s.text}`} />
                        <span>{stop.name ?? stop.activity}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="pt-1">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      onOpen(i)
                    }}
                    className="w-full h-12 bg-surface-container-low hover:bg-surface-container text-ink font-label-lg text-label-lg rounded-xl flex items-center justify-center gap-2 transition-colors"
                  >
                    <span>Planı İncele</span>
                    <Icon name="arrow_forward" className="text-[18px]" />
                  </button>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      <div className="flex flex-col gap-space-sm pt-space-sm">
        <button
          type="button"
          onClick={() => onOpen(selected)}
          className="w-full h-[52px] rounded-2xl bg-plan-a hover:bg-primary-strong active:bg-primary-strong text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2 shadow-lg transition-transform active:scale-[0.99]"
        >
          <Icon name="check_circle" className="text-[20px]" />
          <span>Seçili Planı Başlat ({planStyle(selected).name})</span>
        </button>
        <button
          type="button"
          onClick={onPrefs}
          className="w-full h-12 rounded-xl bg-surface text-ink font-label-md text-label-md flex items-center justify-center gap-space-xs shadow-sm"
        >
          <Icon name="tune" className="text-[18px]" />
          Tercihleri Değiştir
        </button>
      </div>
    </div>
  )
}
