import { apiRequest, settle } from './api'
import type { Place, PlaceWithoutLocation } from './types'

export interface VisitedPlace extends PlaceWithoutLocation {
  visit_count: number
  last_visited_at: string
}

// "Sık gidilen yerler" (ana sayfa): en çok "Ulaşıldı" işaretlenen mekanlar.
export function listFrequentPlaces(token: string, limit = 5) {
  return settle(apiRequest<VisitedPlace[]>(`/visits?limit=${limit}`, { token }))
}

// Bir durak "Ulaşıldı" işaretlenince çağrılır (DetailScreen::toggleArrived).
// Kritik değil: çağıran taraf bunu await'siz/fire-and-forget çağırır. Sayaç artırma
// sunucuda atomik yapılır (backend app/services/visits.py).
export async function recordVisit(place: Place, token: string): Promise<void> {
  await settle(apiRequest<void>('/visits', { method: 'POST', body: place, token }))
}
