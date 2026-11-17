import { describe, expect, it } from 'vitest'
import themesPy from '../../app/core/themes.py?raw'
import { THEME_TYPES, THEMES, formatCost, formatDistance, formatHours, mapsUrl, planStyle } from './meta'

describe('biçimleyiciler', () => {
  it('mesafe: 1 km altı metre, üstü km (1 ondalık)', () => {
    expect(formatDistance(450)).toBe('450 m')
    expect(formatDistance(999)).toBe('999 m')
    expect(formatDistance(1000)).toBe('1.0 km')
    expect(formatDistance(2350)).toBe('2.4 km')
  })

  it('maliyet: 0 ücretsiz', () => {
    expect(formatCost(0)).toBe('Ücretsiz')
    expect(formatCost(150)).toBe('~150 ₺')
  })

  it('süre: yarım saate yuvarlar, virgüllü yazar', () => {
    expect(formatHours(60)).toBe('1 Saat')
    expect(formatHours(90)).toBe('1,5 Saat')
    expect(formatHours(100)).toBe('1,5 Saat')
    expect(formatHours(130)).toBe('2 Saat')
  })

  it('plan stili 3 renkte döner (taşınca başa sarar)', () => {
    expect(planStyle(0).name).toBe('Plan A')
    expect(planStyle(3)).toBe(planStyle(0))
    expect(planStyle(4).name).toBe('Plan B')
  })
})

describe('mapsUrl', () => {
  it('ad ve place_id URL için kaçışlanır', () => {
    const url = mapsUrl({ place_id: 'ChIJ a&b', name: 'Çarşı & Han' })

    expect(url).toContain('query=%C3%87ar%C5%9F%C4%B1%20%26%20Han')
    expect(url).toContain('query_place_id=ChIJ%20a%26b')
  })

  it('ad yoksa activity, o da yoksa boş sorgu', () => {
    expect(mapsUrl({ place_id: 'x', name: null, activity: 'Kahve' })).toContain('query=Kahve')
    expect(mapsUrl({ place_id: 'x', name: null })).toContain('query=&')
  })
})

describe('tema eşlemesi', () => {
  it('THEMES anahtarları ile THEME_TYPES anahtarları birebir aynı', () => {
    expect(THEMES.map((t) => t.key).sort()).toEqual(Object.keys(THEME_TYPES).sort())
  })

  it('her temanın en az bir Google türü var', () => {
    for (const types of Object.values(THEME_TYPES)) expect(types.length).toBeGreaterThan(0)
  })
})

describe('backend ile eşleşme', () => {
  it("THEME_TYPES, backend'in app/core/themes.py::THEME_TYPES'ı ile birebir aynı", () => {
    // meta.ts "birebir" olmak zorunda (durak değiştirirken havuzu istemcide süzer); biri
    // değişip diğeri unutulursa sessizce yanlış sonuç verirdi. CI'da repo kökü erişilebilir.
    const block = /THEME_TYPES[^=]*=\s*\{(.*?)\n\}/s.exec(themesPy)?.[1] ?? ''
    const backend: Record<string, string[]> = {}
    for (const m of block.matchAll(/"([a-z_]+)":\s*\[([^\]]*)\]/g)) {
      backend[m[1]] = [...m[2].matchAll(/"([a-z_]+)"/g)].map((x) => x[1])
    }

    expect(Object.keys(backend).length).toBeGreaterThan(0)
    expect(THEME_TYPES).toEqual(backend)
  })
})
