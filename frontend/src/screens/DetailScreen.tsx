import { useEffect, useState } from 'react'
import { fetchApproach, type LatLng } from '../api'
import { Icon } from '../components/Icon'
import { RouteMap } from '../components/RouteMap'
import { TRAVEL_MODES, formatCost, formatDistance, formatHours, planStyle } from '../meta'
import type { ApproachRoute, DayPlan, TravelMode } from '../types'

export type UserLocation =
  | { status: 'idle' | 'loading' | 'denied' }
  | { status: 'ready'; coords: LatLng }

interface Props {
  plan: DayPlan
  index: number
  travelMode: TravelMode
  userLoc: UserLocation
  onRequestLocation: () => void
  onSelect: (index: number) => void
  onPrefs: () => void
  onStartNavigation: (approach: ApproachRoute) => void
}

type Approach = { state: 'idle' } | { state: 'loading' } | { state: 'error' } | { state: 'ready'; route: ApproachRoute }

export function DetailScreen({ plan, index, travelMode, userLoc, onRequestLocation, onSelect, onPrefs, onStartNavigation }: Props) {
  const alt = plan.alternatives[index]
  const s = planStyle(index)
  const stops = [...alt.stops].sort((a, b) => a.order - b.order)
  const minutes = stops.reduce((sum, st) => sum + st.duration_minutes, 0)
  const cost = stops.reduce((sum, st) => sum + st.estimated_cost, 0)
  const [arrived, setArrived] = useState<Set<number>>(new Set())
  const [shared, setShared] = useState(false)
  const w = plan.weather

  // Konum plan çıkınca, ilk kez detay açıldığında istenir (başlangıçta değil).
  useEffect(() => {
    if (userLoc.status === 'idle') onRequestLocation()
  }, [userLoc.status, onRequestLocation])

  // Kullanıcının konumundan ilk durağa rota.
  const first = stops.find((st) => st.latitude != null && st.longitude != null)
  const origin = userLoc.status === 'ready' ? userLoc.coords : null
  const dest: LatLng | null = first ? { latitude: first.latitude!, longitude: first.longitude! } : null
  const [approach, setApproach] = useState<Approach>({ state: 'idle' })

  useEffect(() => {
    if (!origin || !dest) return
    const controller = new AbortController()
    setApproach({ state: 'loading' })
    fetchApproach(origin, dest, travelMode, controller.signal)
      .then((route) => setApproach({ state: 'ready', route }))
      .catch((err) => {
        if (!(err instanceof DOMException && err.name === 'AbortError')) setApproach({ state: 'error' })
      })
    return () => controller.abort()
    // origin/dest nesneleri her render yeni olur; değerleri bağımlılık olarak veriyoruz
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin?.latitude, origin?.longitude, dest?.latitude, dest?.longitude, travelMode])

  const approachRoute = approach.state === 'ready' ? approach.route : null

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
        <RouteMap alternative={alt} color={s.hex} origin={origin} approach={approachRoute} />
        {!alt.routes_available && (
          <p className="font-body-sm text-[11px] text-text-secondary text-center pt-space-xs">
            Rota çizgisi alınamadı, yalnızca duraklar gösteriliyor.
          </p>
        )}
      </div>

      <div className="bg-surface rounded-xl p-space-md shadow-sm mb-space-lg flex flex-col gap-space-md" aria-live="polite">
        <div className="flex items-center gap-space-sm">
          <div className="w-9 h-9 rounded-full bg-primary-fixed/50 flex items-center justify-center shrink-0">
            <Icon name="near_me" fill className="text-primary text-[20px]" />
          </div>
          <div className="flex flex-col min-w-0 flex-1">
            <span className="font-label-md text-label-md text-ink font-semibold">
              Konumunuzdan {first ? '1. durağa' : 'ilk durağa'}
            </span>
            {approach.state === 'ready' && (
              <span className="font-body-sm text-body-sm text-text-secondary">
                {TRAVEL_MODES[approach.route.travel_mode].emoji} {approach.route.duration_minutes} dk{' '}
                {TRAVEL_MODES[approach.route.travel_mode].verb} ({formatDistance(approach.route.distance_meters)})
              </span>
            )}
            {(userLoc.status === 'idle' || userLoc.status === 'loading' || approach.state === 'loading') && (
              <span className="font-body-sm text-body-sm text-text-secondary">Konumunuz alınıyor, rota hesaplanıyor…</span>
            )}
            {userLoc.status === 'denied' && (
              <span className="font-body-sm text-body-sm text-text-secondary">
                Konum izni verilmedi; rotayı başlatmak için konum gerekli.
              </span>
            )}
            {userLoc.status === 'ready' && approach.state === 'error' && (
              <span className="font-body-sm text-body-sm text-text-secondary">Konumunuzdan rota alınamadı.</span>
            )}
          </div>
        </div>
        {userLoc.status === 'denied' ? (
          <button
            type="button"
            onClick={onRequestLocation}
            className="w-full h-12 rounded-xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-md text-label-md flex items-center justify-center gap-space-xs"
          >
            <Icon name="my_location" className="text-[18px]" />
            Konumumu Kullan
          </button>
        ) : (
          <button
            type="button"
            disabled={approach.state !== 'ready'}
            onClick={() => approach.state === 'ready' && onStartNavigation(approach.route)}
            className="w-full h-[52px] rounded-2xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2 shadow-sm active:scale-[0.99] transition-transform disabled:opacity-50"
          >
            <Icon name="navigation" fill className="text-[22px]" />
            Rotayı Başlat
          </button>
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
