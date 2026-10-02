import type { ApproachRoute, PlanRequest, PlanResponse, TravelMode } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function createPlan(request: PlanRequest, signal?: AbortSignal): Promise<PlanResponse> {
  let response: Response
  try {
    response = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
    throw new ApiError(response.status, detail)
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
