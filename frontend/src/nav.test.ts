import polyline from '@mapbox/polyline'
import { describe, expect, it } from 'vitest'
import { cumulative } from './geo'
import { ARRIVE_METERS, OFF_ROUTE_METERS, buildSegments, computeProgress, prepare } from './nav'
import type { ApproachRoute, PlanAlternative, PlanStop, RouteLeg, RouteStep } from './types'

const step = (meters: number, text: string): RouteStep => ({
  travel_mode: 'WALK',
  instruction: text,
  maneuver: null,
  distance_meters: meters,
  duration_minutes: 1,
  transit: null,
})

const stop = (order: number, lat: number | null, lng: number | null): PlanStop => ({
  place_id: `p${order}`,
  order,
  arrival_time: '10:00',
  duration_minutes: 30,
  activity: `aktivite ${order}`,
  recommendation: '',
  estimated_cost: 0,
  name: `Durak ${order}`,
  latitude: lat,
  longitude: lng,
})

const leg = (from: number, to: number): RouteLeg => ({
  travel_mode: 'WALK',
  from_order: from,
  to_order: to,
  distance_meters: 100,
  duration_minutes: 2,
  polyline: polyline.encode([
    [0, 0],
    [0, 0.001],
  ]),
  steps: [step(100, 'düz git')],
})

const approach: ApproachRoute = {
  travel_mode: 'WALK',
  distance_meters: 50,
  duration_minutes: 1,
  polyline: polyline.encode([
    [0, -0.0005],
    [0, 0],
  ]),
  steps: [step(50, 'yaklaş')],
}

const alt = (stops: PlanStop[], legs: RouteLeg[]): PlanAlternative => ({
  theme: 'kafe',
  title: 'Plan',
  summary: '',
  stops,
  legs,
  routes_available: true,
})

describe('buildSegments', () => {
  it('önce konum→1. durak (yaklaşma), sonra her ayak plan sırasıyla', () => {
    // Duraklar karışık sırada gelse de order'a göre dizilir
    const a = alt([stop(2, 0, 0.001), stop(1, 0, 0)], [leg(1, 2)])
    const segs = buildSegments(a, approach)

    expect(segs.map((s) => s.id)).toEqual(['approach-1', 'leg-1-2'])
    expect(segs[0].title).toBe('Durak 1')
    expect(segs[1].dest).toEqual([0, 0.001])
  })

  it('koordinatsız ilk durak olursa yaklaşma ayağı eklenmez', () => {
    const segs = buildSegments(alt([stop(1, null, null)], []), approach)

    expect(segs).toEqual([])
  })

  it('varış durağı bulunamayan ya da koordinatsız ayak atlanır', () => {
    const a = alt([stop(1, 0, 0), stop(2, null, null)], [leg(1, 2), leg(2, 3)])

    expect(buildSegments(a, approach).map((s) => s.id)).toEqual(['approach-1'])
  })
})

describe('prepare', () => {
  it('adım mesafeleri çizgi uzunluğuna ölçeklenir; son adım çizginin sonunda biter', () => {
    const [, seg] = buildSegments(alt([stop(1, 0, 0), stop(2, 0, 0.001)], [leg(1, 2)]), approach)
    const p = prepare(seg)

    expect(p.length).toBeCloseTo(111.2, 0)
    expect(p.stepEnds[p.stepEnds.length - 1]).toBeCloseTo(p.length, 6)
  })

  it('adımsız segmentte ölçek 1, stepEnds boş', () => {
    const [, seg] = buildSegments(alt([stop(1, 0, 0), stop(2, 0, 0.001)], [{ ...leg(1, 2), steps: [] }]), approach)

    expect(prepare(seg).stepEnds).toEqual([])
  })
})

describe('computeProgress', () => {
  // İki adımlı, ~222 m'lik düz rota: 0 → 0.002 boylam
  const twoStep = prepare({
    id: 's',
    title: 'Hedef',
    stopOrder: 2,
    dest: [0, 0.002],
    mode: 'WALK',
    steps: [step(111, 'ilk'), step(111, 'ikinci')],
    distanceMeters: 222,
    durationMinutes: 10,
    polyline: polyline.encode([
      [0, 0],
      [0, 0.001],
      [0, 0.002],
    ]),
  })

  it('başlangıçta ilk adımda, rotada, varmamış', () => {
    const p = computeProgress(twoStep, [0, 0.0001])

    expect(p.stepIndex).toBe(0)
    expect(p.arrived).toBe(false)
    expect(p.offRoute).toBeLessThan(1)
    expect(p.remainingMeters).toBeGreaterThan(200)
  })

  it('ilk adımı geçince ikinci adıma ve kalan süre azalır', () => {
    const p = computeProgress(twoStep, [0, 0.0015])

    expect(p.stepIndex).toBe(1)
    expect(p.remainingMinutes).toBeLessThan(10)
    expect(p.metersToStepEnd).toBeGreaterThan(0)
  })

  it(`hedefe ${ARRIVE_METERS} m kala varılmış sayılır`, () => {
    const p = computeProgress(twoStep, [0, 0.0019])

    expect(p.arrived).toBe(true)
    expect(p.remainingMeters).toBeLessThanOrEqual(ARRIVE_METERS)
  })

  it(`rotadan ${OFF_ROUTE_METERS} m'den fazla uzaklaşınca offRoute bunu gösterir`, () => {
    const p = computeProgress(twoStep, [0.001, 0.001]) // ~110 m kuzeyde

    expect(p.offRoute).toBeGreaterThan(OFF_ROUTE_METERS)
  })

  it('en az 1 dakika kalır gösterilir (0 değil), varışta bile', () => {
    expect(computeProgress(twoStep, [0, 0.002]).remainingMinutes).toBeGreaterThanOrEqual(1)
  })

  it('kümülatif mesafe ile uyumlu: toplam uzunluk çizgiyle aynı', () => {
    const cum = cumulative(twoStep.path)

    expect(twoStep.length).toBeCloseTo(cum[cum.length - 1], 6)
  })
})
