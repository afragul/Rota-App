import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MAX_AGE_MS, clearState, loadState, saveState, type SavedState } from './planStorage'
import { DEFAULT_PREFS } from './prefs'
import type { DayPlan } from './types'

const store = new Map<string, string>()

beforeEach(() => {
  store.clear()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
})
afterEach(() => vi.unstubAllGlobals())

const alt = (title: string) => ({
  theme: 'kafe',
  title,
  summary: '',
  stops: [],
  legs: [],
  routes_available: true,
})
const plan = (n = 2): DayPlan => ({
  weather_available: false,
  weather: null,
  alternatives: Array.from({ length: n }, (_, i) => alt(`Plan ${i}`)),
  place_pool: [],
})
const NOW = 1_800_000_000_000
const state = (over: Partial<SavedState> = {}): SavedState => ({
  plan: plan(),
  prefs: { ...DEFAULT_PREFS, cityInput: 'Bursa', categories: ['kafe'] },
  view: { name: 'results' },
  createdAt: NOW - 1000,
  ...over,
})

describe('planStorage', () => {
  it('kaydedilen durum aynen geri gelir', () => {
    saveState(state({ view: { name: 'detail', index: 1 } }))

    expect(loadState(NOW)).toEqual(state({ view: { name: 'detail', index: 1 } }))
  })

  it('kayıt yoksa null', () => {
    expect(loadState(NOW)).toBeNull()
  })

  it('12 saatten eski plan geri yüklenmez; sınırda yüklenir', () => {
    saveState(state({ createdAt: NOW - MAX_AGE_MS }))
    expect(loadState(NOW)).not.toBeNull()

    saveState(state({ createdAt: NOW - MAX_AGE_MS - 1 }))
    expect(loadState(NOW)).toBeNull()
  })

  it('gelecekten (saat bozuk) tarihli kayıt reddedilir', () => {
    saveState(state({ createdAt: NOW + 3_600_000 }))

    expect(loadState(NOW)).toBeNull()
  })

  it('yeniden kaydetmek süreyi UZATMAZ: süre üretim anından sayılır', () => {
    saveState(state({ createdAt: NOW - MAX_AGE_MS + 1000 }))
    // yenileme/düzenleme: aynı createdAt ile tekrar yazılır
    saveState(state({ createdAt: NOW - MAX_AGE_MS + 1000 }))

    expect(loadState(NOW + 2000)).toBeNull()
  })

  it('detay indeksi geçersizse (aralık dışı, tamsayı değil, negatif) sonuçlara düşer', () => {
    for (const index of [5, -1, 0.5, Number.NaN]) {
      store.set(
        'rota.lastPlan',
        JSON.stringify({ v: 1, ...state(), view: { name: 'detail', index } }),
      )
      expect(loadState(NOW)?.view).toEqual({ name: 'results' })
    }
  })

  it('bilinmeyen sürüm, bozuk JSON ve şekilsiz plan yok sayılır, hata fırlatmaz', () => {
    store.set('rota.lastPlan', JSON.stringify({ v: 99, ...state() }))
    expect(loadState(NOW)).toBeNull()

    store.set('rota.lastPlan', '{bozuk')
    expect(loadState(NOW)).toBeNull()

    for (const bad of [null, {}, { alternatives: [] }, { alternatives: [{ stops: 'x', legs: [], title: 't' }] }]) {
      store.set('rota.lastPlan', JSON.stringify({ v: 1, ...state(), plan: bad }))
      expect(loadState(NOW)).toBeNull()
    }
  })

  it('eksik tercih alanları varsayılanla tamamlanır; geçersiz tercih kaydı reddedilir', () => {
    store.set(
      'rota.lastPlan',
      JSON.stringify({ v: 1, ...state(), prefs: { cityInput: 'İzmir', duration: 3, note: '', categories: [] } }),
    )
    expect(loadState(NOW)?.prefs).toMatchObject({ cityInput: 'İzmir', duration: 3, group: DEFAULT_PREFS.group })

    store.set('rota.lastPlan', JSON.stringify({ v: 1, ...state(), prefs: { cityInput: 5 } }))
    expect(loadState(NOW)).toBeNull()
  })

  it('clearState kaydı siler', () => {
    saveState(state())
    clearState()

    expect(loadState(NOW)).toBeNull()
  })

  it('localStorage erişilemezse hiçbiri hata fırlatmaz', () => {
    const boom = () => {
      throw new Error('erişim yok')
    }
    vi.stubGlobal('localStorage', { getItem: boom, setItem: boom, removeItem: boom })

    expect(() => saveState(state())).not.toThrow()
    expect(loadState(NOW)).toBeNull()
    expect(() => clearState()).not.toThrow()
  })
})
