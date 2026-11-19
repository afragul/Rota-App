// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_PREFS } from './prefs'
import type { DayPlan } from './types'

// App.tsx bütün ekranları (DetailScreen/Leaflet dahil) statik import ediyor ama bu testte
// view hep 'results'ta kalıyor — DetailScreen hiç mount olmadığı için Leaflet'in `L.map()`'i
// hiç çağrılmıyor, jsdom'da gerçek bir harita render etmeye çalışmıyoruz.
//
// auth.ts modül yüklenirken localStorage'daki "giriş ipucu"nu okuyup gerekiyorsa sessizce
// /auth/refresh çağırır (bkz. auth.test.ts); bu testlerde o ipucu hiç set edilmediği için
// (misafir senaryosu) fetch'e hiç dokunulmaz — yine de gerçek bir ağ isteği olursa testin
// patlaması için fetch'i reddeden bir sahteyle değiştiriyoruz.

const PLAN: DayPlan = {
  weather_available: false,
  weather: null,
  alternatives: [
    { theme: 'kafe', title: 'Geri Yüklenen Plan', summary: 'Test özeti.', stops: [], legs: [], routes_available: true },
  ],
  place_pool: [],
}

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.reject(new Error('Bu testte gerçek bir ağ isteği yapılmamalı'))),
  )
  // jsdom window.scrollTo'yu uygulamıyor; App.tsx her view değişiminde çağırıyor.
  vi.stubGlobal('scrollTo', vi.fn())
  // jsdom window.matchMedia'yı da uygulamıyor; theme.ts sistem temasını buradan okuyor.
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
})

afterEach(() => {
  // cleanup() olmadan önceki testin App'i mount'ta kalır; onun saveState efekti
  // sonraki testin localStorage.clear()'ını geçersiz kılabilir.
  cleanup()
  vi.unstubAllGlobals()
  vi.resetModules()
})

describe('sayfa yenilenince/siteye tekrar girince plan geri yüklenir (planStorage.ts + App.tsx)', () => {
  it('misafir: localStorage\'da geçerli bir plan varsa doğrudan sonuç ekranı gösterilir, konum ekranına düşülmez', async () => {
    const { saveState } = await import('./planStorage')
    saveState({
      plan: PLAN,
      prefs: { ...DEFAULT_PREFS, cityInput: 'Bursa' },
      view: { name: 'results' },
      createdAt: Date.now(),
    })

    const { default: App } = await import('./App')
    render(<App />)

    expect(await screen.findByText('Geri Yüklenen Plan')).toBeInTheDocument()
    expect(screen.queryByText('Hangi semtte olacaksınız?')).not.toBeInTheDocument()
  })

  it('hiçbir kayıt yoksa normal şekilde konum ekranından başlar', async () => {
    const { default: App } = await import('./App')
    render(<App />)

    expect(await screen.findByText('Hangi semtte olacaksınız?')).toBeInTheDocument()
  })

  it('bozuk/eski sürüm bir kayıt sessizce yok sayılır, uygulama çökmez ve konum ekranına düşer', async () => {
    localStorage.setItem('bugunluk.lastPlan', JSON.stringify({ v: 999, garbage: true }))

    const { default: App } = await import('./App')
    expect(() => render(<App />)).not.toThrow()
    expect(await screen.findByText('Hangi semtte olacaksınız?')).toBeInTheDocument()
  })

  it('12 saatten eski bir plan geçersiz sayılır, konum ekranına düşülür (süre createdAt\'tan sayılır)', async () => {
    const { saveState, MAX_AGE_MS } = await import('./planStorage')
    saveState({
      plan: PLAN,
      prefs: { ...DEFAULT_PREFS, cityInput: 'Bursa' },
      view: { name: 'results' },
      createdAt: Date.now() - MAX_AGE_MS - 1000,
    })

    const { default: App } = await import('./App')
    render(<App />)

    expect(await screen.findByText('Hangi semtte olacaksınız?')).toBeInTheDocument()
    expect(screen.queryByText('Geri Yüklenen Plan')).not.toBeInTheDocument()
  })

  it('detay ekranından yenilenirse doğrudan o alternatifin detayına döner, sonuç listesine değil', async () => {
    const { saveState } = await import('./planStorage')
    const twoAlternatives: DayPlan = {
      ...PLAN,
      alternatives: [
        { ...PLAN.alternatives[0], summary: 'Birinci alternatifin özeti' },
        { ...PLAN.alternatives[0], summary: 'İkinci alternatifin özeti' },
      ],
    }
    saveState({
      plan: twoAlternatives,
      prefs: { ...DEFAULT_PREFS, cityInput: 'Bursa' },
      view: { name: 'detail', index: 1 },
      createdAt: Date.now(),
    })

    const { default: App } = await import('./App')
    render(<App />)

    // Detay ekranı: seçili (index 1) alternatifin özeti görünür, diğerininki değil —
    // "sonuç listesine düşülmedi, doğru alternatifin detayına dönüldü" demek bu.
    // exact:false: özet metni aynı <p> içinde "• Kişi başı ..." gibi başka metinle birlikte basılıyor.
    expect(await screen.findByText('İkinci alternatifin özeti', { exact: false })).toBeInTheDocument()
    expect(screen.queryByText('Birinci alternatifin özeti', { exact: false })).not.toBeInTheDocument()
  })
})
