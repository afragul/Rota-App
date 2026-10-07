import type { Budget, GroupType, Place, PlanRequest, TravelMode } from './types'

export interface Preferences {
  cityInput: string
  group: GroupType
  duration: number
  budget: Budget | null
  travelMode: TravelMode
  categories: string[]
  note: string
  // "HH:MM" — null iken PreferencesScreen bir sonraki tam saati varsayılan
  // olarak önerir ama kullanıcı değiştirebilir (bkz. PreferencesScreen).
  startTime: string | null
  // Ana sayfada "sık gidilen yer" tıklanınca dolar; doluyken bu mekan
  // plana garanti edilir (backend: PlanRequest.anchor_place). Serbest
  // arama kutusuna elle yazmaya başlanınca sıfırlanır (bkz. LocationScreen).
  anchorPlace: Place | null
}

export const DEFAULT_PREFS: Preferences = {
  cityInput: '',
  group: 'friends',
  duration: 4,
  budget: null,
  travelMode: 'WALK',
  categories: [],
  note: '',
  startTime: null,
  anchorPlace: null,
}

export function hasLocation(p: Preferences): boolean {
  return p.cityInput.trim() !== '' || p.anchorPlace !== null
}

export function locationLabel(p: Preferences): string {
  return p.anchorPlace ? p.anchorPlace.name : p.cityInput.trim()
}

// Hiçbir tercih zorunlu değil (DESIGN.md §1) — yalnızca konum gerekli.
export function toRequest(p: Preferences): PlanRequest | null {
  if (!hasLocation(p)) return null
  return {
    // anchorPlace varsa kendi koordinatları kullanılır: geocoding'e gerek
    // kalmaz (ücretsiz) ve mekan havuzu anchor'ın gerçek konumu etrafında
    // aranır (daha isabetli).
    ...(p.anchorPlace
      ? { latitude: p.anchorPlace.latitude, longitude: p.anchorPlace.longitude, anchor_place: p.anchorPlace }
      : { city: p.cityInput.trim() }),
    duration_hours: p.duration,
    budget: p.budget ?? 'medium',
    group_type: p.group,
    travel_mode: p.travelMode,
    ...(p.categories.length ? { categories: p.categories } : {}),
    ...(p.note.trim() ? { free_text: p.note.trim() } : {}),
    ...(p.startTime ? { start_time: p.startTime } : {}),
  }
}
