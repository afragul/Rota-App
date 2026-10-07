import type { Session } from '@supabase/supabase-js'
import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import { RouteMap } from '../components/RouteMap'
import { formatCost, formatHours, mapsUrl, planStyle, TRAVEL_MODES, formatDistance } from '../meta'
import { deleteSavedPlan, fetchSharedPlan, type SavedPlan } from '../savedPlans'

interface Props {
  planId: string
  session: Session | null
  onClose: () => void
  onCreateOwn: () => void
}

type State = { status: 'loading' } | { status: 'error' } | { status: 'ready'; plan: SavedPlan }

// Link ile paylaşılan bir rotayı salt-okunur gösterir; App'in normal Shell/view
// akışının dışında, tek başına bir sayfa (bkz. App.tsx'teki ?shared= kontrolü).
export function SharedPlanScreen({ planId, session, onClose, onCreateOwn }: Props) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    setState({ status: 'loading' })
    fetchSharedPlan(planId).then(({ data, error }) => {
      if (error || !data) setState({ status: 'error' })
      else setState({ status: 'ready', plan: data })
    })
  }, [planId])

  const removeFavorite = async () => {
    setDeleting(true)
    await deleteSavedPlan(planId)
    onClose()
  }

  if (state.status === 'loading') {
    return (
      <div className="fixed inset-0 z-[60] bg-background flex items-center justify-center">
        <p className="font-body-md text-body-md text-text-secondary">Rota yükleniyor...</p>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="fixed inset-0 z-[60] bg-background flex flex-col items-center justify-center gap-4 p-margin text-center">
        <Icon name="link_off" className="text-[40px] text-text-secondary" />
        <p className="font-body-md text-body-md text-ink">Bu rota artık mevcut değil.</p>
        <button onClick={onCreateOwn} className="h-12 px-6 rounded-xl bg-plan-a text-on-primary font-label-md text-label-md">
          Kendi rotanı oluştur
        </button>
      </div>
    )
  }

  const { plan } = state
  const s = planStyle(0)
  const stops = [...plan.stops].sort((a, b) => a.order - b.order)
  const minutes = stops.reduce((sum, st) => sum + st.duration_minutes, 0)
  const cost = stops.reduce((sum, st) => sum + st.estimated_cost, 0)

  return (
    <div className="fixed inset-0 z-[60] bg-background overflow-y-auto">
      <div className="max-w-md mx-auto px-margin pt-safe pb-space-lg flex flex-col w-full">
        <div className="flex items-center justify-between py-space-md">
          <span className="font-label-sm text-label-sm text-text-secondary uppercase tracking-wider">Paylaşılan Rota</span>
          <div className="flex items-center gap-1">
            {session?.user.id === plan.user_id && (
              <button
                onClick={removeFavorite}
                disabled={deleting}
                aria-label="Favorilerden kaldır"
                className="w-10 h-10 rounded-full flex items-center justify-center text-weather-good disabled:opacity-50"
              >
                <Icon name="star" fill className="text-[22px]" />
              </button>
            )}
            <button onClick={onClose} aria-label="Kapat" className="w-10 h-10 rounded-full flex items-center justify-center text-ink">
              <Icon name="close" className="text-[22px]" />
            </button>
          </div>
        </div>

        <div className="bg-surface rounded-xl p-space-md shadow-sm mb-space-lg">
          <span className="font-label-sm text-label-sm text-text-secondary bg-surface-container px-2.5 py-1 rounded-full">
            Toplam {formatHours(minutes)}
          </span>
          <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-ink mt-space-xs mb-space-xs">{plan.title}</h2>
          <p className="font-body-md text-body-md text-text-secondary leading-relaxed">
            {plan.summary} • Kişi başı {formatCost(cost)}
          </p>
        </div>

        <div className="bg-surface-container rounded-xl p-space-sm shadow-sm mb-space-xl">
          <RouteMap alternative={plan} color={s.hex} />
          {!plan.routes_available && (
            <p className="font-body-sm text-[11px] text-text-secondary text-center pt-space-xs">
              Rota çizgisi alınamadı, yalnızca duraklar gösteriliyor.
            </p>
          )}
        </div>

        <ol className="relative pl-6 mb-space-xl">
          <div className="absolute left-[13px] top-4 bottom-6 w-0.5 bg-surface-variant" />
          {stops.map((stop, i) => {
            const leg = plan.legs.find((l) => l.from_order === stop.order)
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
                  <div className="flex items-center gap-1.5 mb-space-xs">
                    <h3 className="font-headline-md text-headline-md text-ink">{stop.name ?? stop.activity}</h3>
                    <a
                      href={mapsUrl(stop)}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label="Google Maps'te gör"
                      className="text-text-secondary hover:text-primary flex-shrink-0"
                    >
                      <Icon name="open_in_new" className="text-[16px]" />
                    </a>
                  </div>
                  <div className="bg-surface-container-low rounded-lg p-2.5 mt-space-xs mb-space-xs flex flex-col gap-1.5">
                    <p className="font-body-md text-body-md text-on-surface-variant">{stop.activity}</p>
                    <p className="font-body-md text-body-md text-on-surface-variant">💡 {stop.recommendation}</p>
                  </div>
                  <span className="inline-flex items-center gap-1 font-label-sm text-label-sm text-ink bg-surface-container px-2 py-1 rounded-full">
                    💰 {formatCost(stop.estimated_cost)} / kişi
                  </span>
                </div>

                {leg && i < stops.length - 1 && (
                  <div className="relative ml-2 my-space-sm pl-4 flex items-center gap-2 py-1">
                    <div className="inline-flex self-start items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-highest text-ink font-label-sm text-label-sm">
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

        <button
          onClick={onCreateOwn}
          className="h-12 rounded-xl bg-plan-a text-on-primary font-label-md text-label-md flex items-center justify-center gap-1.5"
        >
          <Icon name="add_road" className="text-[18px]" />
          Kendi rotanı oluştur
        </button>
      </div>
    </div>
  )
}
