import polyline from '@mapbox/polyline'
import L from 'leaflet'
import { useEffect, useRef } from 'react'
import type { LatLng } from '../api'
import type { ApproachRoute, PlanAlternative } from '../types'

interface Props {
  alternative: PlanAlternative
  color: string
  origin?: LatLng | null
  approach?: ApproachRoute | null
  /** "Ulaşıldı" işaretlenen durakların order değerleri; pinleri soluklaşır. */
  arrivedOrders?: Set<number>
}

export function RouteMap({ alternative, color, origin, approach, arrivedOrders }: Props) {
  const el = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!el.current) return
    const map = L.map(el.current, { scrollWheelZoom: false, attributionControl: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(map)

    const bounds: L.LatLngTuple[] = []

    for (const leg of alternative.legs) {
      const points = polyline.decode(leg.polyline) as L.LatLngTuple[]
      L.polyline(points, { color, weight: 5, opacity: 0.85 }).addTo(map)
      bounds.push(...points)
    }

    // Kullanıcının konumundan ilk durağa kesikli çizgi + "Siz" noktası
    if (origin) {
      const here: L.LatLngTuple = [origin.latitude, origin.longitude]
      if (approach) {
        const points = polyline.decode(approach.polyline) as L.LatLngTuple[]
        L.polyline(points, { color, weight: 4, opacity: 0.7, dashArray: '2 8' }).addTo(map)
        bounds.push(...points)
      }
      L.marker(here, {
        icon: L.divIcon({
          className: '',
          html: '<div class="rota-me"></div>',
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        }),
        title: 'Konumunuz',
      }).addTo(map)
      bounds.push(here)
    }

    for (const stop of alternative.stops) {
      if (stop.latitude == null || stop.longitude == null) continue
      const pos: L.LatLngTuple = [stop.latitude, stop.longitude]
      const done = arrivedOrders?.has(stop.order)
      L.marker(pos, {
        icon: L.divIcon({
          className: '',
          html: done
            ? `<div class="rota-pin rota-pin-done" style="background:${color}"><span class="material-symbols-outlined" style="font-size:16px">check</span></div>`
            : `<div class="rota-pin" style="background:${color}">${Number(stop.order)}</div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        }),
        title: stop.name ?? undefined,
      }).addTo(map)
      bounds.push(pos)
    }

    if (bounds.length) map.fitBounds(bounds, { padding: [28, 28] })
    else map.setView([39, 35], 5)

    return () => {
      map.remove()
    }
  }, [alternative, color, origin, approach, arrivedOrders])

  return <div ref={el} className="w-full h-44 rounded-lg overflow-hidden z-0" role="img" aria-label="Durakları ve rotayı gösteren harita" />
}
