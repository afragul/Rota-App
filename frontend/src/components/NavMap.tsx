import L from 'leaflet'
import { useEffect, useRef } from 'react'
import type { Pt } from '../geo'
import type { PreparedSegment } from '../nav'

interface Props {
  segments: PreparedSegment[]
  current: number
  pos: Pt | null
  follow: boolean
  color: string
  onUserPan: () => void
}

const NAV_ZOOM = 17

// Navigasyon haritası: harita bir kez kurulur, konum/ayak değişince katmanlar güncellenir.
export function NavMap({ segments, current, pos, follow, color, onUserPan }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const routeLayer = useRef<L.LayerGroup | null>(null)
  const me = useRef<L.Marker | null>(null)
  const programmatic = useRef(false)
  const panCb = useRef(onUserPan)
  panCb.current = onUserPan

  useEffect(() => {
    if (!el.current) return
    const m = L.map(el.current, { zoomControl: false, attributionControl: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(m)
    routeLayer.current = L.layerGroup().addTo(m)
    // Kullanıcı haritayı elle kaydırınca takip modu kapanır (Google Haritalar gibi)
    m.on('dragstart', () => {
      if (!programmatic.current) panCb.current()
    })
    m.setView([39, 35], 5)
    map.current = m
    return () => {
      m.remove()
      map.current = null
    }
  }, [])

  // Rota çizgileri: aktif ayak dolu çizgi, diğerleri soluk kesikli; duraklar numaralı pin
  useEffect(() => {
    const layer = routeLayer.current
    if (!layer) return
    layer.clearLayers()
    segments.forEach((seg, i) => {
      if (i === current) return
      L.polyline(seg.path, { color, weight: 4, opacity: 0.35, dashArray: '2 8' }).addTo(layer)
    })
    const active = segments[current]
    if (active) L.polyline(active.path, { color, weight: 7, opacity: 0.9 }).addTo(layer)
    for (const seg of segments) {
      L.marker(seg.dest, {
        icon: L.divIcon({
          className: '',
          html: `<div class="rota-pin" style="background:${color}">${Number(seg.stopOrder)}</div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        }),
        title: seg.title,
      }).addTo(layer)
    }
    if (active && !pos && map.current) map.current.fitBounds(active.path, { padding: [60, 60] })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segments, current, color])

  // Konum noktası + takip
  useEffect(() => {
    const m = map.current
    if (!m || !pos) return
    if (!me.current) {
      me.current = L.marker(pos, {
        icon: L.divIcon({ className: '', html: '<div class="rota-me"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }),
        title: 'Konumunuz',
        zIndexOffset: 1000,
      }).addTo(m)
    } else {
      me.current.setLatLng(pos)
    }
    if (follow) {
      programmatic.current = true
      m.setView(pos, Math.max(m.getZoom(), NAV_ZOOM), { animate: true })
      setTimeout(() => (programmatic.current = false), 400)
    }
  }, [pos, follow])

  return <div ref={el} className="absolute inset-0 z-0" role="img" aria-label="Canlı navigasyon haritası" />
}
