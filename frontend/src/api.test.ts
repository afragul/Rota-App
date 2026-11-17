import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiRequest, createPlan, fetchLegs, searchPlaces, setUnauthorizedHandler, settle } from './api'
import type { PlanRequest } from './types'

const fetchMock = vi.fn()

const json = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' }, ...init })

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  setUnauthorizedHandler(() => {})
})
afterEach(() => vi.unstubAllGlobals())

/** Son fetch çağrısının [url, init] değerleri. */
const lastCall = () => fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [string, RequestInit]

describe('ApiError', () => {
  it('limit bayrakları varsayılan olarak kapalı', () => {
    const e = new ApiError(500, 'x')

    expect(e.guestLimit).toBe(false)
    expect(e.userLimit).toBe(false)
    expect(e.message).toBe('x')
  })
})

describe('apiRequest', () => {
  it('GET: /api önekiyle gider, gövde ve Content-Type yok, token varsa Authorization', async () => {
    fetchMock.mockResolvedValue(json({ ok: 1 }))

    expect(await apiRequest('/me', { token: 'tkn' })).toEqual({ ok: 1 })

    const [url, init] = lastCall()
    expect(url).toBe('/api/me')
    expect(init.method).toBe('GET')
    expect(init.headers).toEqual({ Authorization: 'Bearer tkn' })
    expect(init.body).toBeUndefined()
  })

  it('POST: gövde JSON olarak gider', async () => {
    fetchMock.mockResolvedValue(json({}))

    await apiRequest('/x', { method: 'POST', body: { a: 1 } })

    const [, init] = lastCall()
    expect(init.body).toBe('{"a":1}')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
  })

  it('204: undefined döner', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))

    expect(await apiRequest('/x', { method: 'DELETE' })).toBeUndefined()
  })

  it("hata: backend'in Türkçe detail mesajı ApiError'a taşınır", async () => {
    fetchMock.mockResolvedValue(json({ detail: 'Bu kullanıcı adı alınmış' }, { status: 409 }))

    await expect(apiRequest('/x')).rejects.toMatchObject({ status: 409, message: 'Bu kullanıcı adı alınmış' })
  })

  it('422 ve detail bir liste ise (FastAPI doğrulama): genel Türkçe mesaj', async () => {
    fetchMock.mockResolvedValue(json({ detail: [{ msg: 'field required' }] }, { status: 422 }))

    await expect(apiRequest('/x')).rejects.toMatchObject({ status: 422, message: 'Girilen bilgiler geçersiz' })
  })

  it('JSON olmayan hata gövdesinde varsayılan mesaj', async () => {
    fetchMock.mockResolvedValue(new Response('<html>502</html>', { status: 502 }))

    await expect(apiRequest('/x')).rejects.toMatchObject({ status: 502, message: 'İşlem başarısız oldu' })
  })

  it('limit başlıkları bayraklara çevrilir (misafir ve hesap ayrı)', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'd' }, { status: 429, headers: { 'X-Guest-Limit-Reached': '1' } }))
    await expect(apiRequest('/x')).rejects.toMatchObject({ guestLimit: true, userLimit: false })

    fetchMock.mockResolvedValueOnce(json({ detail: 'd' }, { status: 429, headers: { 'X-User-Limit-Reached': '1' } }))
    await expect(apiRequest('/x')).rejects.toMatchObject({ guestLimit: false, userLimit: true })
  })

  it('token ile 401: oturum kapatma kancası çağrılır; tokensız 401: çağrılmaz', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    fetchMock.mockResolvedValue(json({ detail: 'x' }, { status: 401 }))

    await expect(apiRequest('/me')).rejects.toBeInstanceOf(ApiError)
    expect(handler).not.toHaveBeenCalled()

    await expect(apiRequest('/me', { token: 't' })).rejects.toBeInstanceOf(ApiError)
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('ağ hatası: status 0 ApiError', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(apiRequest('/x')).rejects.toMatchObject({ status: 0, message: 'Sunucuya ulaşılamadı' })
  })

  it('iptal (AbortError) ApiError\'a çevrilmez, aynen fırlatılır', async () => {
    fetchMock.mockRejectedValue(new DOMException('iptal', 'AbortError'))

    await expect(apiRequest('/x')).rejects.toMatchObject({ name: 'AbortError' })
  })
})

describe('settle', () => {
  it('başarıda { data, error: null }', async () => {
    expect(await settle(Promise.resolve(5))).toEqual({ data: 5, error: null })
  })

  it('ApiError aynen, başka hata "Beklenmeyen hata" olarak döner', async () => {
    const api = new ApiError(404, 'yok')
    expect((await settle(Promise.reject(api))).error).toBe(api)
    expect((await settle(Promise.reject(new Error('x')))).error?.message).toBe('Beklenmeyen hata')
  })
})

describe('createPlan', () => {
  const request: PlanRequest = {
    city: 'Bursa',
    duration_hours: 4,
    budget: 'medium',
    group_type: 'friends',
    travel_mode: 'WALK',
  }

  it('isteği /api/plan adresine gönderir, token varsa Authorization ekler', async () => {
    fetchMock.mockResolvedValue(json({ alternatives: [] }))

    await createPlan(request, undefined, 'tkn')

    const [url, init] = lastCall()
    expect(url).toBe('/api/plan')
    expect(init.headers).toMatchObject({ Authorization: 'Bearer tkn' })
    expect(JSON.parse(init.body as string)).toEqual(request)
  })

  it('misafir kotası dolunca guestLimit bayrağı', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'doldu' }, { status: 429, headers: { 'X-Guest-Limit-Reached': '1' } }))

    await expect(createPlan(request)).rejects.toMatchObject({ status: 429, guestLimit: true, message: 'doldu' })
  })
})

describe('fetchLegs', () => {
  it('ayakları döndürür; misafir kotasında guestLimit bayrağı', async () => {
    fetchMock.mockResolvedValueOnce(json({ legs: [{ from_order: 1 }] }))
    expect(await fetchLegs([], 'WALK')).toEqual([{ from_order: 1 }])

    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 429, headers: { 'X-Guest-Limit-Reached': '1' } }))
    await expect(fetchLegs([], 'WALK')).rejects.toMatchObject({ guestLimit: true })
  })
})

describe('searchPlaces', () => {
  const near = { latitude: 40.18, longitude: 29.06 }

  it('sorguyu ve konumu query string olarak gönderir (kaçışlı), token varsa Authorization', async () => {
    fetchMock.mockResolvedValue(json([{ place_id: 'a' }]))

    const result = await searchPlaces('Çarşı & Han', near, undefined, 'tkn')

    expect(result).toEqual([{ place_id: 'a' }])
    const [url, init] = lastCall()
    const parsed = new URL(url, 'http://x')
    expect(parsed.pathname).toBe('/api/places/search')
    expect(parsed.searchParams.get('q')).toBe('Çarşı & Han')
    expect(parsed.searchParams.get('latitude')).toBe('40.18')
    expect(parsed.searchParams.get('longitude')).toBe('29.06')
    expect(init.headers).toEqual({ Authorization: 'Bearer tkn' })
  })

  it('tokensız çağrıda Authorization yok', async () => {
    fetchMock.mockResolvedValue(json([]))

    await searchPlaces('kahve', near)

    expect(lastCall()[1].headers).toEqual({})
  })

  it('kota ve hata durumları', async () => {
    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 429, headers: { 'X-User-Limit-Reached': '1' } }))
    await expect(searchPlaces('kahve', near)).rejects.toMatchObject({ status: 429, userLimit: true })

    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 429, headers: { 'X-Guest-Limit-Reached': '1' } }))
    await expect(searchPlaces('kahve', near)).rejects.toMatchObject({ guestLimit: true, userLimit: false })

    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 422 }))
    await expect(searchPlaces('k', near)).rejects.toMatchObject({ status: 422, message: 'Arama metni geçersiz' })

    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 502 }))
    await expect(searchPlaces('kahve', near)).rejects.toMatchObject({ status: 502, message: 'Arama yapılamadı' })
  })

  it('ağ hatası status 0, iptal aynen fırlatılır', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('x'))
    await expect(searchPlaces('kahve', near)).rejects.toMatchObject({ status: 0 })

    fetchMock.mockRejectedValueOnce(new DOMException('iptal', 'AbortError'))
    await expect(searchPlaces('kahve', near)).rejects.toMatchObject({ name: 'AbortError' })
  })
})
