import type { Budget, GroupType, PlanRequest, TravelMode } from './types'

export interface Preferences {
  cityInput: string
  group: GroupType
  duration: number
  budget: Budget | null
  travelMode: TravelMode
  categories: string[]
  note: string
}

export const DEFAULT_PREFS: Preferences = {
  cityInput: '',
  group: 'friends',
  duration: 4,
  budget: null,
  travelMode: 'WALK',
  categories: [],
  note: '',
}

export function hasLocation(p: Preferences): boolean {
  return p.cityInput.trim() !== ''
}

export function locationLabel(p: Preferences): string {
  return p.cityInput.trim()
}

// Hiçbir tercih zorunlu değil (DESIGN.md §1) — yalnızca konum gerekli.
export function toRequest(p: Preferences): PlanRequest | null {
  if (!hasLocation(p)) return null
  return {
    city: p.cityInput.trim(),
    duration_hours: p.duration,
    budget: p.budget ?? 'medium',
    group_type: p.group,
    travel_mode: p.travelMode,
    ...(p.categories.length ? { categories: p.categories } : {}),
    ...(p.note.trim() ? { free_text: p.note.trim() } : {}),
  }
}
