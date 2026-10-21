import type { ApproachRoute, PlanRequest, PlanResponse, RouteLeg, TravelMode } from './types'

export class ApiError extends Error {
  status: number
  // Backend'in sunucu tarafı misafir kotası (X-Guest-Limit-Reached header'ı) mı
  // tetiklendi, yoksa genel bir hata/rate limit mi — App.tsx bu ikisini ayırt eder.
  guestLimit: boolean
  constructor(status: number, message: string, guestLimit = false) {
    super(message)
    this.status = status
    this.guestLimit = guestLimit
  }
}

export async function createPlan(
  request: PlanRequest,
  signal?: AbortSignal,
  accessToken?: string,
): Promise<PlanResponse> {
  let response: Response
  try {
    response = await fetch('/api/plan', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(request),
      signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'Sunucuya ulaşılamadı')
  }

  if (!response.ok) {
    let detail = 'Plan oluşturulamadı'
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* gövde JSON değilse varsayılan mesaj */
    }
    throw new ApiError(response.status, detail, response.headers.get('X-Guest-Limit-Reached') === '1')
  }
  return response.json()
}

export interface LatLng {
  latitude: number
  longitude: number
}

// Kullanıcının konumundan ilk durağa rota (plan çıktıktan sonra çağrılır).
export async function fetchApproach(
  origin: LatLng,
  destination: LatLng,
  travelMode: TravelMode,
  signal?: AbortSignal,
): Promise<ApproachRoute> {
  const response = await fetch('/api/route/approach', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      origin_latitude: origin.latitude,
      origin_longitude: origin.longitude,
      destination_latitude: destination.latitude,
      destination_longitude: destination.longitude,
      travel_mode: travelMode,
    }),
    signal,
  })
  if (!response.ok) throw new ApiError(response.status, 'Konumunuzdan rota alınamadı')
  return response.json()
}

export interface LegStop {
  order: number
  latitude: number
  longitude: number
}

// Durak silindiğinde/sırası değiştiğinde ayakları (mesafe/süre/çizgi) yeniden hesaplar.
// accessToken verilirse backend'in misafir günlük kotası (app/core/guest_limit.py) bu
// kullanıcıya uygulanmaz — verilmezse giriş yapmış kullanıcı da misafir sayılır.
export async function fetchLegs(
  stops: LegStop[],
  travelMode: TravelMode,
  signal?: AbortSignal,
  accessToken?: string,
): Promise<RouteLeg[]> {
  const response = await fetch('/api/route/legs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify({ stops, travel_mode: travelMode }),
    signal,
  })
  if (!response.ok) {
    throw new ApiError(response.status, 'Rota güncellenemedi', response.headers.get('X-Guest-Limit-Reached') === '1')
  }
  const data = await response.json()
  return data.legs
}

// Süresi dolmuş/geçersiz token'la 401 alınınca oturumu kapatmak için auth.ts kaydeder
// (api.ts auth.ts'i import etmesin diye döngüyü bu kanca kırıyor).
let unauthorizedHandler: (() => void) | null = null
export function setUnauthorizedHandler(handler: () => void) {
  unauthorizedHandler = handler
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  token?: string
  signal?: AbortSignal
}

// Hesap/plan/favori/ziyaret endpoint'leri için ortak fetch sarmalayıcı: backend'in
// (Türkçe) `detail` mesajını ApiError'a taşır, 204'te undefined döner.
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, token, signal } = options
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'Sunucuya ulaşılamadı')
  }

  if (!response.ok) {
    let detail = 'İşlem başarısız oldu'
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') detail = data.detail
      else if (response.status === 422) detail = 'Girilen bilgiler geçersiz'
    } catch {
      /* gövde JSON değilse varsayılan mesaj */
    }
    if (response.status === 401 && token) unauthorizedHandler?.()
    throw new ApiError(response.status, detail, response.headers.get('X-Guest-Limit-Reached') === '1')
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

// Veri modüllerinin (savedPlans/favoritePlaces/visitedPlaces) eski `{ data, error }`
// dönüş biçimini korur; böylece çağıran ekranlar try/catch'e çevrilmek zorunda kalmaz.
export type Result<T> = { data: T; error: null } | { data: null; error: ApiError }

export async function settle<T>(promise: Promise<T>): Promise<Result<T>> {
  try {
    return { data: await promise, error: null }
  } catch (err) {
    return { data: null, error: err instanceof ApiError ? err : new ApiError(0, 'Beklenmeyen hata') }
  }
}
