import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GUEST_PLAN_LIMIT, guestLimitReached, guestPlanCount, recordGuestPlan } from './guestLimit'

function stubStorage(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial))
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
  })
  return store
}

describe('guestLimit (localStorage sayacı)', () => {
  beforeEach(() => stubStorage())
  afterEach(() => vi.unstubAllGlobals())

  it('boşken sayaç 0 ve limit dolmamış', () => {
    expect(guestPlanCount()).toBe(0)
    expect(guestLimitReached()).toBe(false)
  })

  it('her plan sayacı bir artırır, limitte dolar', () => {
    for (let i = 0; i < GUEST_PLAN_LIMIT - 1; i++) recordGuestPlan()
    expect(guestLimitReached()).toBe(false)
    recordGuestPlan()
    expect(guestPlanCount()).toBe(GUEST_PLAN_LIMIT)
    expect(guestLimitReached()).toBe(true)
  })

  it('bozuk değer (sayı değil, negatif) 0 sayılır', () => {
    for (const bad of ['abc', '-5', 'NaN', '']) {
      stubStorage({ 'bugunluk-guest-plan-count': bad })
      expect(guestPlanCount()).toBe(0)
    }
  })

  it('localStorage erişilemezse (gizli sekme) sınırsız sayılır, hata fırlatmaz', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('erişim yok')
      },
      setItem: () => {
        throw new Error('erişim yok')
      },
    })
    expect(guestPlanCount()).toBe(0)
    expect(guestLimitReached()).toBe(false)
    expect(() => recordGuestPlan()).not.toThrow()
  })
})
