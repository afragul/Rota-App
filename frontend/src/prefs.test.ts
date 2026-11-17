import { describe, expect, it } from 'vitest'
import { DEFAULT_PREFS, hasLocation, locationLabel, toRequest, type Preferences } from './prefs'
import type { Place } from './types'

const prefs = (over: Partial<Preferences> = {}): Preferences => ({ ...DEFAULT_PREFS, ...over })

const place: Place = {
  place_id: 'ChIJabc',
  name: 'Kozahan',
  address: 'Bursa',
  latitude: 40.18,
  longitude: 29.06,
  rating: null,
  user_rating_count: null,
  types: ['shopping_mall'],
}

describe('hasLocation / locationLabel', () => {
  it('boş ya da yalnızca boşluk olan şehir konum sayılmaz', () => {
    expect(hasLocation(prefs())).toBe(false)
    expect(hasLocation(prefs({ cityInput: '   ' }))).toBe(false)
  })

  it('şehir yazılmışsa ya da anchor mekan varsa konum var', () => {
    expect(hasLocation(prefs({ cityInput: 'Bursa' }))).toBe(true)
    expect(hasLocation(prefs({ anchorPlace: place }))).toBe(true)
  })

  it('etiket: anchor varsa mekan adı, yoksa kırpılmış şehir', () => {
    expect(locationLabel(prefs({ anchorPlace: place, cityInput: 'başka' }))).toBe('Kozahan')
    expect(locationLabel(prefs({ cityInput: '  Bursa ' }))).toBe('Bursa')
  })
})

describe('toRequest', () => {
  it('konum yoksa istek üretilmez', () => {
    expect(toRequest(prefs())).toBeNull()
  })

  it('yalnızca şehirle: varsayılanlar dolar, opsiyoneller eklenmez', () => {
    const req = toRequest(prefs({ cityInput: ' Bursa ' }))

    expect(req).toEqual({
      city: 'Bursa',
      duration_hours: 4,
      budget: 'medium', // seçilmediyse "orta"
      group_type: 'friends',
      travel_mode: 'WALK',
    })
    expect(req).not.toHaveProperty('categories')
    expect(req).not.toHaveProperty('free_text')
    expect(req).not.toHaveProperty('start_time')
  })

  it('anchor mekanın koordinatları kullanılır, şehir (geocoding) gönderilmez', () => {
    const req = toRequest(prefs({ anchorPlace: place, cityInput: 'Bursa' }))

    expect(req).toMatchObject({ latitude: 40.18, longitude: 29.06, anchor_place: place })
    expect(req).not.toHaveProperty('city')
  })

  it('seçilen tercihler isteğe girer; boşluklu not kırpılır, yalnızca-boşluk not atılır', () => {
    const dolu = toRequest(
      prefs({
        cityInput: 'Bursa',
        budget: 'high',
        categories: ['kafe', 'tarihi'],
        note: '  sakin olsun ',
        startTime: '10:00',
        travelMode: 'TRANSIT',
      }),
    )
    expect(dolu).toMatchObject({
      budget: 'high',
      categories: ['kafe', 'tarihi'],
      free_text: 'sakin olsun',
      start_time: '10:00',
      travel_mode: 'TRANSIT',
    })

    expect(toRequest(prefs({ cityInput: 'Bursa', note: '   ' }))).not.toHaveProperty('free_text')
  })
})
