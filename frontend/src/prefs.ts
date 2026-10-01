import type { Budget, GroupType, PlanRequest, TravelMode } from './types'

export interface Preferences {
  coords: { latitude: number; longitude: number; accuracy: number } | null
  cityInput: string
  group: GroupType
  duration: number
  budget: Budget | null
  travelMode: TravelMode
  categories: string[]
  note: string
}

export const DEFAULT_PREFS: Preferences = {
  coords: null,
  cityInput: '',
  group: 'friends',
  duration: 4,
  budget: null,
  travelMode: 'WALK',
  categories: [],
  note: '',
}

export function hasLocation(p: Preferences): boolean {
  return p.coords !== null || p.cityInput.trim() !== ''
}

export function locationLabel(p: Preferences): string {
  return p.coords ? 'Konumunuz' : p.cityInput.trim()
}

// Hiçbir tercih zorunlu değil (DESIGN.md §1) — yalnızca konum gerekli.
export function toRequest(p: Preferences): PlanRequest | null {
  if (!hasLocation(p)) return null
  const city = p.cityInput.trim()
  return {
    ...(p.coords ? { latitude: p.coords.latitude, longitude: p.coords.longitude } : { city }),
    duration_hours: p.duration,
    budget: p.budget ?? 'medium',
    group_type: p.group,
    travel_mode: p.travelMode,
    ...(p.categories.length ? { categories: p.categories } : {}),
    ...(p.note.trim() ? { free_text: p.note.trim() } : {}),
  }
}
