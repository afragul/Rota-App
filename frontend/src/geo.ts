import polyline from '@mapbox/polyline'

export type Pt = [number, number] // [lat, lng]

const R = 6371000
const rad = (d: number) => (d * Math.PI) / 180

export function haversine(a: Pt, b: Pt): number {
  const dLat = rad(b[0] - a[0])
  const dLng = rad(b[1] - a[1])
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

export const decodePath = (encoded: string): Pt[] => polyline.decode(encoded) as Pt[]

/** Başlangıçtan her noktaya kümülatif mesafe (metre). */
export function cumulative(path: Pt[]): number[] {
  const cum = [0]
  for (let i = 1; i < path.length; i++) cum.push(cum[i - 1] + haversine(path[i - 1], path[i]))
  return cum
}

/**
 * Konumu çizgi üzerine izdüşürür: rota boyunca ne kadar yol alındığı (traveled)
 * ve çizgiye olan uzaklık (offRoute), ikisi de metre. Kısa mesafede düzlem
 * yaklaşımı yeterli.
 */
export function project(path: Pt[], cum: number[], p: Pt): { traveled: number; offRoute: number } {
  let best = { traveled: 0, offRoute: Infinity }
  const kx = Math.cos(rad(p[0])) * 111320
  const ky = 110540
  for (let i = 0; i < path.length - 1; i++) {
    const [aLat, aLng] = path[i]
    const [bLat, bLng] = path[i + 1]
    const abx = (bLng - aLng) * kx
    const aby = (bLat - aLat) * ky
    const apx = (p[1] - aLng) * kx
    const apy = (p[0] - aLat) * ky
    const len2 = abx * abx + aby * aby
    const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, (apx * abx + apy * aby) / len2))
    const off = Math.hypot(apx - t * abx, apy - t * aby)
    if (off < best.offRoute) best = { offRoute: off, traveled: cum[i] + t * (cum[i + 1] - cum[i]) }
  }
  return best
}
