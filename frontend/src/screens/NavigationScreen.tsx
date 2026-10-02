import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchApproach } from '../api'
import { Icon } from '../components/Icon'
import { NavMap } from '../components/NavMap'
import { StepList } from '../components/StepList'
import { StepBanner } from '../components/StepBanner'
import { formatDistance, planStyle } from '../meta'
import { OFF_ROUTE_METERS, computeProgress, prepare, type PreparedSegment, type Segment } from '../nav'
import type { Pt } from '../geo'
import type { PlanAlternative } from '../types'

interface Props {
  alternative: PlanAlternative
  planIndex: number
  segments: Segment[]
  onExit: () => void
}

type Fix = { pos: Pt; accuracy: number }

// Google Haritalar benzeri canlı navigasyon: konum sürekli izlenir, adım konuma göre ilerler,
// rotadan çıkılınca yeniden hesaplanır, durağa varınca bir sonraki ayağa geçilir.
export function NavigationScreen({ alternative, planIndex, segments: initial, onExit }: Props) {
  const color = planStyle(planIndex).hex
  const [segments, setSegments] = useState<PreparedSegment[]>(() => initial.map(prepare))
  const [current, setCurrent] = useState(0)
  const [fix, setFix] = useState<Fix | null>(null)
  const [follow, setFollow] = useState(true)
  const [arrived, setArrived] = useState(false)
  const [rerouting, setRerouting] = useState(false)
  const [gpsError, setGpsError] = useState(false)
  const [showSteps, setShowSteps] = useState(false)
  const offCount = useRef(0)
  const reroutingRef = useRef(false)

  const seg = segments[current]
  const finished = arrived && current === segments.length - 1
  const progress = useMemo(() => (fix && seg ? computeProgress(seg, fix.pos) : null), [fix, seg])

  // Canlı konum
  useEffect(() => {
    if (!navigator.geolocation) {
      setGpsError(true)
      return
    }
    const id = navigator.geolocation.watchPosition(
      (p) => {
        setGpsError(false)
        setFix({ pos: [p.coords.latitude, p.coords.longitude], accuracy: p.coords.accuracy })
      },
      () => setGpsError(true),
      { enableHighAccuracy: true, maximumAge: 1000, timeout: 15000 },
    )
    return () => navigator.geolocation.clearWatch(id)
  }, [])

  // Navigasyon sırasında ekran kapanmasın
  useEffect(() => {
    let lock: WakeLockSentinel | null = null
    navigator.wakeLock?.request('screen').then((l) => (lock = l)).catch(() => {})
    return () => {
      lock?.release().catch(() => {})
    }
  }, [])

  const reroute = useCallback(
    async (from: Pt, target: PreparedSegment, index: number) => {
      reroutingRef.current = true
      setRerouting(true)
      try {
        const route = await fetchApproach({ latitude: from[0], longitude: from[1] }, { latitude: target.dest[0], longitude: target.dest[1] }, target.mode)
        const next: Segment = {
          id: target.id,
          title: target.title,
          stopOrder: target.stopOrder,
          dest: target.dest,
          mode: target.mode,
          steps: route.steps,
          distanceMeters: route.distance_meters,
          durationMinutes: route.duration_minutes,
          polyline: route.polyline,
        }
        setSegments((prev) => prev.map((s, i) => (i === index ? prepare(next) : s)))
      } catch {
        /* rota alınamazsa eski çizgiyle devam; bir sonraki sapmada tekrar denenir */
      } finally {
        reroutingRef.current = false
        setRerouting(false)
        offCount.current = 0
      }
    },
    [],
  )

  // Varış ve rotadan sapma kontrolü
  useEffect(() => {
    if (!progress || !fix || !seg || arrived) return
    if (progress.arrived) {
      setArrived(true)
      return
    }
    const threshold = Math.max(OFF_ROUTE_METERS, fix.accuracy * 1.5)
    if (progress.offRoute > threshold) {
      offCount.current += 1
      // Tek bir GPS sıçramasında değil, ardışık iki ölçümde sapma varsa yeniden hesapla
      if (offCount.current >= 2 && !reroutingRef.current) void reroute(fix.pos, seg, current)
    } else {
      offCount.current = 0
    }
  }, [progress, fix, seg, arrived, current, reroute])

  const nextSegment = () => {
    setArrived(false)
    setCurrent((c) => Math.min(c + 1, segments.length - 1))
    setFollow(true)
    offCount.current = 0
  }

  if (!seg) {
    return (
      <div className="fixed inset-0 z-[60] bg-background flex flex-col items-center justify-center gap-4 p-margin text-center">
        <p className="font-body-md text-body-md text-ink">Bu plan için rota bulunamadı.</p>
        <button onClick={onExit} className="h-12 px-6 rounded-xl bg-plan-a text-on-primary font-label-md text-label-md">
          Geri dön
        </button>
      </div>
    )
  }

  const stop = alternative.stops.find((s) => s.order === seg.stopOrder)
  const step = progress ? seg.steps[progress.stepIndex] : seg.steps[0]
  const nextStep = progress ? seg.steps[progress.stepIndex + 1] : seg.steps[1]
  const eta = progress ? new Date(Date.now() + progress.remainingMinutes * 60000) : null

  return (
    <div className="fixed inset-0 z-[60] bg-background">
      <NavMap
        segments={segments}
        current={current}
        pos={fix?.pos ?? null}
        follow={follow && !arrived}
        color={color}
        onUserPan={() => setFollow(false)}
      />

      {/* Üst: şimdi ne yapılacak */}
      <div className="absolute top-0 inset-x-0 z-10 pt-safe">
        <div className="max-w-md mx-auto p-space-md flex flex-col gap-space-sm">
          {arrived ? (
            <div className="bg-success text-white rounded-2xl p-space-md shadow-lg flex items-center gap-space-md" role="status">
              <Icon name="flag" fill className="text-[36px]" />
              <div className="min-w-0">
                <div className="font-headline-md text-headline-md">{finished ? 'Rota tamamlandı' : 'Durağa ulaştınız'}</div>
                <div className="font-body-md text-body-md opacity-90 truncate">{seg.title}</div>
              </div>
            </div>
          ) : (
            <StepBanner
              step={step}
              metersToStepEnd={progress?.metersToStepEnd ?? null}
              next={nextStep}
              waiting={!fix}
              gpsError={gpsError}
              rerouting={rerouting}
            />
          )}
        </div>
      </div>

      {/* Takibi geri aç */}
      {!follow && !arrived && fix && (
        <button
          onClick={() => setFollow(true)}
          aria-label="Konumuma dön"
          className="absolute right-4 bottom-[216px] z-10 w-12 h-12 rounded-full bg-surface shadow-lg flex items-center justify-center text-primary"
        >
          <Icon name="my_location" fill className="text-[24px]" />
        </button>
      )}

      {/* Alt: kalan süre/mesafe, varış, kontroller */}
      <div className="absolute bottom-0 inset-x-0 z-10 pb-safe">
        <div className="max-w-md mx-auto">
          <div className="bg-surface rounded-t-3xl shadow-[0_-4px_24px_rgba(0,0,0,0.15)] p-space-lg flex flex-col gap-space-md max-h-[60vh] overflow-y-auto">
            {arrived && stop ? (
              <div className="flex flex-col gap-space-sm">
                <h2 className="font-headline-md text-headline-md text-ink">{stop.name ?? stop.activity}</h2>
                <div className="bg-surface-container-low rounded-lg p-2.5 flex flex-col gap-1.5">
                  <p className="font-body-md text-body-md text-on-surface-variant">{stop.activity}</p>
                  <p className="font-body-md text-body-md text-on-surface-variant">💡 {stop.recommendation}</p>
                </div>
              </div>
            ) : (
              <div className="flex items-end justify-between gap-space-md">
                <div className="min-w-0">
                  <div className="font-label-sm text-label-sm text-text-secondary">{stop?.order}. durağa</div>
                  <div className="font-headline-md text-headline-md text-ink truncate">{seg.title}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-headline-lg-mobile text-headline-lg-mobile text-success leading-none">
                    {progress ? progress.remainingMinutes : seg.durationMinutes} dk
                  </div>
                  <div className="font-body-sm text-body-sm text-text-secondary">
                    {formatDistance(Math.round(progress ? progress.remainingMeters : seg.distanceMeters))}
                    {eta && ` • ${eta.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}`}
                  </div>
                </div>
              </div>
            )}

            {showSteps && !arrived && <StepList steps={seg.steps} title="Tüm adımlar" defaultOpen />}

            <div className="flex gap-space-sm">
              <button
                onClick={onExit}
                className="h-12 px-5 rounded-xl bg-surface-container-high text-ink font-label-md text-label-md flex items-center gap-1.5"
              >
                <Icon name="close" className="text-[18px]" />
                {finished ? 'Kapat' : 'Bitir'}
              </button>
              {arrived ? (
                !finished && (
                  <button
                    onClick={nextSegment}
                    className="flex-1 h-12 rounded-xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2"
                  >
                    <Icon name="navigation" fill className="text-[20px]" />
                    Sonraki durağa git
                  </button>
                )
              ) : (
                <button
                  onClick={() => setShowSteps(!showSteps)}
                  aria-expanded={showSteps}
                  className="flex-1 h-12 rounded-xl bg-surface-container-low text-ink font-label-md text-label-md flex items-center justify-center gap-1.5"
                >
                  <Icon name="list" className="text-[18px]" />
                  {showSteps ? 'Adımları gizle' : 'Tüm adımlar'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
