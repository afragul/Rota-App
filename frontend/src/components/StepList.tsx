import { useState } from 'react'
import { formatDistance } from '../meta'
import type { RouteStep } from '../types'
import { Icon } from './Icon'

// Google manevra kodu -> Material Symbols ikonu.
const MANEUVER_ICONS: Record<string, string> = {
  DEPART: 'navigation',
  TURN_LEFT: 'turn_left',
  TURN_RIGHT: 'turn_right',
  TURN_SLIGHT_LEFT: 'turn_slight_left',
  TURN_SLIGHT_RIGHT: 'turn_slight_right',
  TURN_SHARP_LEFT: 'turn_sharp_left',
  TURN_SHARP_RIGHT: 'turn_sharp_right',
  UTURN_LEFT: 'u_turn_left',
  UTURN_RIGHT: 'u_turn_right',
  STRAIGHT: 'straight',
  NAME_CHANGE: 'straight',
  RAMP_LEFT: 'ramp_left',
  RAMP_RIGHT: 'ramp_right',
  MERGE: 'merge',
  FORK_LEFT: 'fork_left',
  FORK_RIGHT: 'fork_right',
  ROUNDABOUT_LEFT: 'roundabout_left',
  ROUNDABOUT_RIGHT: 'roundabout_right',
  FERRY: 'directions_boat',
}

export function maneuverIcon(maneuver: string | null): string {
  return (maneuver && MANEUVER_ICONS[maneuver]) || 'arrow_upward'
}

function StepRow({ step }: { step: RouteStep }) {
  const t = step.transit

  if (t) {
    return (
      <li className="flex items-start gap-space-sm py-2">
        <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center shrink-0">
          <Icon name="directions_transit" className="text-[18px] text-ink" />
        </div>
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className="px-2 py-0.5 rounded font-label-sm text-label-sm font-bold bg-ink text-background"
              style={t.line_color ? { backgroundColor: t.line_color, color: t.line_text_color ?? '#fff' } : undefined}
            >
              {t.line_name ?? t.vehicle ?? 'Toplu taşıma'}
            </span>
            {t.vehicle && <span className="font-label-sm text-label-sm text-text-secondary">{t.vehicle}</span>}
            {t.headsign && <span className="font-body-sm text-body-sm text-text-secondary">• {t.headsign} yönü</span>}
          </div>
          <p className="font-body-md text-body-md text-ink">
            <strong className="font-semibold">{t.departure_stop ?? 'Durak'}</strong> durağından binin
            {t.departure_time ? ` (${t.departure_time})` : ''}
          </p>
          <p className="font-body-sm text-body-sm text-text-secondary">
            {t.stop_count ? `${t.stop_count} durak • ` : ''}
            {step.duration_minutes} dk • <strong className="font-semibold text-ink">{t.arrival_stop ?? 'Durak'}</strong>{' '}
            durağında inin
          </p>
        </div>
      </li>
    )
  }

  const icon = maneuverIcon(step.maneuver)
  return (
    <li className="flex items-start gap-space-sm py-2">
      <div className="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center shrink-0">
        <Icon name={icon} className="text-[18px] text-ink" />
      </div>
      <div className="flex flex-col min-w-0 pt-0.5">
        <p className="font-body-md text-body-md text-ink whitespace-pre-line">{step.instruction ?? 'Devam edin'}</p>
        {step.distance_meters > 0 && (
          <span className="font-body-sm text-body-sm text-text-secondary">{formatDistance(step.distance_meters)}</span>
        )}
      </div>
    </li>
  )
}

interface Props {
  steps: RouteStep[]
  title?: string
  defaultOpen?: boolean
}

// Açılır "Adım adım tarif" listesi. Adım yoksa (Google döndürmediyse) hiçbir şey çizmez.
export function StepList({ steps, title = 'Adım adım tarif', defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  if (steps.length === 0) return null

  return (
    <div className="flex flex-col">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full h-11 px-3 rounded-xl bg-surface-container-low text-ink font-label-md text-label-md"
      >
        <span className="flex items-center gap-1.5">
          <Icon name="alt_route" className="text-[18px] text-primary" />
          {title} ({steps.length})
        </span>
        <Icon name="expand_more" className={`text-[20px] text-text-secondary transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <ol className="flex flex-col divide-y divide-surface-variant/60 pt-1">{steps.map((s, i) => <StepRow key={i} step={s} />)}</ol>}
    </div>
  )
}
