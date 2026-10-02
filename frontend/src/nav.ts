import { cumulative, decodePath, haversine, project, type Pt } from './geo'
import type { ApproachRoute, PlanAlternative, RouteStep, TravelMode } from './types'

/** Navigasyonun tek ayağı: önceki noktadan (konum ya da önceki durak) bir sonraki durağa. */
export interface Segment {
  id: string
  /** Varış noktasının adı (durak adı) */
  title: string
  stopOrder: number
  dest: Pt
  mode: TravelMode
  steps: RouteStep[]
  distanceMeters: number
  durationMinutes: number
  polyline: string
}

export interface PreparedSegment extends Segment {
  path: Pt[]
  cum: number[]
  length: number
  /** Her adımın rota boyunca bittiği mesafe (metre), çizgi uzunluğuna ölçeklenmiş */
  stepEnds: number[]
}

export interface Progress {
  stepIndex: number
  metersToStepEnd: number
  remainingMeters: number
  remainingMinutes: number
  offRoute: number
  arrived: boolean
}

export const ARRIVE_METERS = 30
export const OFF_ROUTE_METERS = 50

/** Plan sırasıyla ayaklar: [konumun → 1. durak, 1 → 2, 2 → 3, ...] */
export function buildSegments(alt: PlanAlternative, approach: ApproachRoute): Segment[] {
  const stops = [...alt.stops].sort((a, b) => a.order - b.order)
  const first = stops[0]
  const segments: Segment[] = []

  if (first?.latitude != null && first.longitude != null) {
    segments.push({
      id: `approach-${first.order}`,
      title: first.name ?? first.activity,
      stopOrder: first.order,
      dest: [first.latitude, first.longitude],
      mode: approach.travel_mode,
      steps: approach.steps,
      distanceMeters: approach.distance_meters,
      durationMinutes: approach.duration_minutes,
      polyline: approach.polyline,
    })
  }

  for (const leg of alt.legs) {
    const to = stops.find((s) => s.order === leg.to_order)
    if (!to || to.latitude == null || to.longitude == null) continue
    segments.push({
      id: `leg-${leg.from_order}-${leg.to_order}`,
      title: to.name ?? to.activity,
      stopOrder: to.order,
      dest: [to.latitude, to.longitude],
      mode: leg.travel_mode,
      steps: leg.steps,
      distanceMeters: leg.distance_meters,
      durationMinutes: leg.duration_minutes,
      polyline: leg.polyline,
    })
  }
  return segments
}

export function prepare(seg: Segment): PreparedSegment {
  const path = decodePath(seg.polyline)
  const cum = cumulative(path)
  const length = cum[cum.length - 1] || seg.distanceMeters
  const total = seg.steps.reduce((sum, s) => sum + s.distance_meters, 0)
  const scale = total > 0 ? length / total : 1
  let acc = 0
  const stepEnds = seg.steps.map((s) => (acc += s.distance_meters * scale))
  return { ...seg, path, cum, length, stepEnds }
}

/** Konumdan: hangi adımdayız, bir sonraki manevraya/varışa ne kadar kaldı, rotadan saptık mı. */
export function computeProgress(seg: PreparedSegment, pos: Pt): Progress {
  const { traveled, offRoute } = project(seg.path, seg.cum, pos)
  const remainingMeters = Math.max(0, seg.length - traveled)
  const idx = seg.stepEnds.findIndex((end) => end > traveled)
  const stepIndex = idx === -1 ? Math.max(0, seg.steps.length - 1) : idx
  const stepEnd = seg.stepEnds[stepIndex] ?? seg.length
  const arrived = remainingMeters <= ARRIVE_METERS || haversine(pos, seg.dest) <= ARRIVE_METERS
  return {
    stepIndex,
    metersToStepEnd: Math.max(0, stepEnd - traveled),
    remainingMeters,
    remainingMinutes: seg.length > 0 ? Math.max(1, Math.round((seg.durationMinutes * remainingMeters) / seg.length)) : 0,
    offRoute,
    arrived,
  }
}
