import { DEFAULT_PREFS, type Preferences } from './prefs'
import type { DayPlan } from './types'

// Son plan, tercihler ve açık ekran bu cihazın localStorage'ında tutulur: sayfa yenilenince ya da
// siteden çıkıp girince plan kaybolmasın (yeniden üretmek ücretli bir Google + Groq çağrısı).
// Yalnızca bu tarayıcıda durur, sunucuya gitmez; çıkış yapınca/hesap silinince temizlenir.
const KEY = 'bugunluk.lastPlan'
const VERSION = 1
// Hava durumu ve saatler bayatlar: bundan eski plan geri yüklenmez. Süre planın ÜRETİLDİĞİ
// andan sayılır (her kayıtta ya da yenilemede uzamaz).
export const MAX_AGE_MS = 12 * 60 * 60 * 1000

export type SavedView = { name: 'results' } | { name: 'detail'; index: number }

export interface SavedState {
  plan: DayPlan
  prefs: Preferences
  view: SavedView
  /** Planın üretildiği an (epoch ms). */
  createdAt: number
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null

// Başka bir sürümün/bozuk kaydın uygulamayı çökertmemesi için şekil kontrolü: şüphe varsa
// kayıt yok sayılır (kullanıcı yalnızca ana ekrandan başlar).
function isPlan(v: unknown): v is DayPlan {
  if (!isObject(v) || !Array.isArray(v.alternatives) || v.alternatives.length === 0) return false
  if (v.place_pool !== undefined && !Array.isArray(v.place_pool)) return false
  return v.alternatives.every(
    (a) => isObject(a) && Array.isArray(a.stops) && Array.isArray(a.legs) && typeof a.title === 'string',
  )
}

function toPrefs(v: unknown): Preferences | null {
  if (!isObject(v)) return null
  const p = { ...DEFAULT_PREFS, ...v } as Preferences
  const ok =
    typeof p.cityInput === 'string' &&
    typeof p.duration === 'number' &&
    typeof p.note === 'string' &&
    Array.isArray(p.categories)
  return ok ? p : null
}

export function saveState(state: SavedState): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ v: VERSION, ...state }))
  } catch {
    /* depolama kapalı ya da dolu: plan yalnızca bu oturumda kalır */
  }
}

export function loadState(now = Date.now()): SavedState | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const data: unknown = JSON.parse(raw)
    if (!isObject(data) || data.v !== VERSION || typeof data.createdAt !== 'number') return null
    if (now - data.createdAt > MAX_AGE_MS || data.createdAt > now + 60_000) return null
    if (!isPlan(data.plan)) return null
    const prefs = toPrefs(data.prefs)
    if (!prefs) return null

    const saved = isObject(data.view) ? data.view : {}
    const index = saved.index
    const view: SavedView =
      saved.name === 'detail' && typeof index === 'number' && Number.isInteger(index) &&
      index >= 0 && index < data.plan.alternatives.length
        ? { name: 'detail', index }
        : { name: 'results' }
    return { plan: data.plan, prefs, view, createdAt: data.createdAt }
  } catch {
    return null
  }
}

export function clearState(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* erişilemiyorsa silinecek bir şey de yok */
  }
}
