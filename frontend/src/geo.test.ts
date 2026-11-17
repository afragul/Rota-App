import polyline from '@mapbox/polyline'
import { describe, expect, it } from 'vitest'
import { cumulative, decodePath, haversine, project, type Pt } from './geo'

// Boylam boyunca ~111 km/derece (ekvatorda): kolay hesaplanan düz bir çizgi.
const line: Pt[] = [
  [0, 0],
  [0, 0.001],
  [0, 0.002],
]

describe('haversine', () => {
  it('aynı nokta 0', () => {
    expect(haversine([40, 29], [40, 29])).toBe(0)
  })

  it('1 derece enlem ≈ 111,2 km', () => {
    expect(haversine([0, 0], [1, 0])).toBeCloseTo(111_195, -2)
  })

  it('simetrik', () => {
    const a: Pt = [40.18, 29.06]
    const b: Pt = [41.01, 28.97]
    expect(haversine(a, b)).toBeCloseTo(haversine(b, a), 6)
  })
})

describe('decodePath / cumulative', () => {
  it('encode edilmiş çizgiyi noktalara çevirir', () => {
    const encoded = polyline.encode(line)
    const decoded = decodePath(encoded)

    expect(decoded).toHaveLength(3)
    expect(decoded[2][1]).toBeCloseTo(0.002, 5)
  })

  it('kümülatif mesafe 0 ile başlar ve artar', () => {
    const cum = cumulative(line)

    expect(cum[0]).toBe(0)
    expect(cum[1]).toBeCloseTo(111.2, 0)
    expect(cum[2]).toBeCloseTo(222.4, 0)
  })

  it('tek noktalı çizgi: [0]', () => {
    expect(cumulative([[1, 1]])).toEqual([0])
  })
})

describe('project (konumu çizgiye izdüşürme)', () => {
  const cum = cumulative(line)

  it('çizgi üzerindeki nokta: offRoute ≈ 0, traveled doğru', () => {
    const r = project(line, cum, [0, 0.0015])

    expect(r.offRoute).toBeLessThan(0.5)
    expect(r.traveled).toBeCloseTo(166.8, 0)
  })

  it('çizgiden yana kayık nokta: offRoute ≈ yanal uzaklık (~11 m)', () => {
    const r = project(line, cum, [0.0001, 0.001])

    expect(r.offRoute).toBeCloseTo(11, 0)
    expect(r.traveled).toBeCloseTo(111.2, 0)
  })

  it('çizginin başından önceki nokta başa, sonundan sonraki sona sabitlenir', () => {
    expect(project(line, cum, [0, -0.001]).traveled).toBe(0)
    expect(project(line, cum, [0, 0.01]).traveled).toBeCloseTo(cum[2], 6)
  })
})
