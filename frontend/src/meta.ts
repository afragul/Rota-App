import type { Budget, GroupType, TravelMode } from './types'

// Backend THEME_TYPES anahtarlarıyla birebir; ikonlar Material Symbols adları.
export const THEMES = [
  { key: 'tarihi', label: 'Tarihi', icon: 'account_balance' },
  { key: 'alisveris', label: 'Alışveriş', icon: 'shopping_bag' },
  { key: 'kafe', label: 'Kafe', icon: 'local_cafe' },
  { key: 'yemek', label: 'Yemek', icon: 'restaurant' },
  { key: 'acik_hava', label: 'Açık Hava', icon: 'park' },
  { key: 'eglence', label: 'Eğlence', icon: 'attractions' },
]

// Backend app/core/themes.py::THEME_TYPES ile birebir — durak değiştirirken
// havuzu kategoriye göre filtrelemek için (ücretsiz, Google'a yeni çağrı yok).
export const THEME_TYPES: Record<string, string[]> = {
  tarihi: ['historical_landmark', 'museum', 'tourist_attraction'],
  alisveris: ['shopping_mall', 'clothing_store', 'market'],
  kafe: ['cafe', 'bakery', 'coffee_shop'],
  yemek: ['restaurant', 'meal_takeaway'],
  acik_hava: ['park', 'garden', 'hiking_area'],
  eglence: ['movie_theater', 'amusement_park', 'bowling_alley'],
}

export const GROUPS: { value: GroupType; label: string; icon: string; phrase: string }[] = [
  { value: 'solo', label: 'Tek başıma', icon: 'person', phrase: 'tek kişilik' },
  { value: 'couple', label: 'Çift', icon: 'favorite', phrase: 'çift' },
  { value: 'friends', label: 'Arkadaşlar', icon: 'diversity_3', phrase: 'arkadaş grubu' },
  { value: 'family', label: 'Aile', icon: 'family_restroom', phrase: 'aile' },
]

export const BUDGETS: { value: Budget | null; label: string }[] = [
  { value: null, label: 'Farketmez' },
  { value: 'low', label: 'Düşük' },
  { value: 'medium', label: 'Orta' },
  { value: 'high', label: 'Yüksek' },
]

export const TRAVEL_MODES: Record<TravelMode, { label: string; verb: string; icon: string; emoji: string }> = {
  WALK: { label: 'Yürüyüş', verb: 'yürüyüş', icon: 'directions_walk', emoji: '🚶' },
  TRANSIT: { label: 'Toplu taşıma', verb: 'toplu taşıma', icon: 'directions_transit', emoji: '🚌' },
  DRIVE: { label: 'Araba', verb: 'araç', icon: 'directions_car', emoji: '🚗' },
}

// Tailwind sınıfları tam yazılmalı (dinamik birleştirme purge edilir).
export const PLAN_STYLES = [
  { name: 'Plan A', bg: 'bg-plan-a', text: 'text-plan-a', hex: '#E8603C' },
  { name: 'Plan B', bg: 'bg-plan-b', text: 'text-plan-b', hex: '#7A4FD1' },
  { name: 'Plan C', bg: 'bg-plan-c', text: 'text-plan-c', hex: '#C2185B' },
]
export const planStyle = (i: number) => PLAN_STYLES[i % PLAN_STYLES.length]

export function formatDistance(meters: number): string {
  return meters < 1000 ? `${meters} m` : `${(meters / 1000).toFixed(1)} km`
}

export function formatCost(tl: number): string {
  return tl > 0 ? `~${tl} ₺` : 'Ücretsiz'
}

export function formatHours(minutes: number): string {
  const h = Math.round((minutes / 60) * 2) / 2
  return `${String(h).replace('.', ',')} Saat`
}

// Mekanın Google Maps sayfasına link (gerçek görseller/yorumlar için) — ekstra
// API çağrısı gerektirmez, zaten elimizdeki place_id ile kurulur.
export function mapsUrl(stop: { place_id: string; name: string | null; activity: string }): string {
  const query = encodeURIComponent(stop.name ?? stop.activity)
  return `https://www.google.com/maps/search/?api=1&query=${query}&query_place_id=${stop.place_id}`
}
