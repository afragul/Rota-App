import polyline from '@mapbox/polyline'
import L from 'leaflet'
import { useEffect, useRef } from 'react'
import type { PlanAlternative } from '../types'

export function RouteMap({ alternative, color }: { alternative: PlanAlternative; color: string }) {
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

    for (const stop of alternative.stops) {
      if (stop.latitude == null || stop.longitude == null) continue
      const pos: L.LatLngTuple = [stop.latitude, stop.longitude]
      L.marker(pos, {
        icon: L.divIcon({
          className: '',
          html: `<div class="rota-pin" style="background:${color}">${stop.order}</div>`,
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
  }, [alternative, color])

  return <div ref={el} className="w-full h-44 rounded-lg overflow-hidden z-0" role="img" aria-label="Durakları ve rotayı gösteren harita" />
}
