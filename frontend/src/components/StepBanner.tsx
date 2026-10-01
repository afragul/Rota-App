import { formatDistance } from '../meta'
import type { RouteStep } from '../types'
import { Icon } from './Icon'
import { maneuverIcon } from './StepList'

interface Props {
  step: RouteStep | undefined
  metersToStepEnd: number | null
  next: RouteStep | undefined
  waiting: boolean
  gpsError: boolean
  rerouting: boolean
}

function describe(step: RouteStep | undefined): { icon: string; text: string } {
  if (!step) return { icon: 'navigation', text: 'Rotayı takip edin' }
  const t = step.transit
  if (t) {
    return {
      icon: 'directions_transit',
      text: `${t.line_name ?? t.vehicle ?? 'Toplu taşıma'}${t.headsign ? ` (${t.headsign} yönü)` : ''} — ${t.departure_stop ?? 'durak'} durağından binin`,
    }
  }
  return { icon: maneuverIcon(step.maneuver), text: step.instruction ?? 'Devam edin' }
}

// Navigasyonun üst kartı: Google Haritalar'daki "şimdi şunu yap" bandı.
export function StepBanner({ step, metersToStepEnd, next, waiting, gpsError, rerouting }: Props) {
  const now = describe(step)
  const after = next ? describe(next) : null

  return (
    <div className="bg-ink text-background rounded-2xl shadow-lg overflow-hidden" role="status" aria-live="polite">
      <div className="p-space-md flex items-center gap-space-md">
        <Icon name={now.icon} className="text-[44px] shrink-0" />
        <div className="min-w-0">
          {metersToStepEnd !== null && !rerouting && (
            <div className="font-headline-lg-mobile text-headline-lg-mobile leading-none mb-1">
              {formatDistance(Math.round(metersToStepEnd))}
            </div>
          )}
          <div className="font-label-lg text-label-lg whitespace-pre-line leading-snug">
            {rerouting ? 'Rota yeniden hesaplanıyor…' : waiting ? (gpsError ? 'Konum alınamıyor' : 'Konumunuz bekleniyor…') : now.text}
          </div>
        </div>
      </div>
      {after && !rerouting && !waiting && (
        <div className="bg-background/15 px-space-md py-2 flex items-center gap-2 font-body-sm text-body-sm">
          <span className="opacity-80">Sonra</span>
          <Icon name={after.icon} className="text-[18px]" />
          <span className="truncate">{after.text}</span>
        </div>
      )}
      {gpsError && !waiting && (
        <div className="bg-error text-on-error px-space-md py-2 font-body-sm text-body-sm">Konum sinyali zayıf</div>
      )}
    </div>
  )
}
