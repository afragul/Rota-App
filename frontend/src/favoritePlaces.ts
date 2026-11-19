import { apiRequest, settle } from './api'
import type { Place, PlaceWithoutLocation } from './types'

export interface FavoritePlace extends PlaceWithoutLocation {
  id: string
}

export function listFavoritePlaces(token: string) {
  return settle(apiRequest<FavoritePlace[]>('/favorites', { token }))
}

export function addFavoritePlace(place: Place, token: string) {
  return settle(apiRequest<FavoritePlace>('/favorites', { method: 'POST', body: place, token }))
}

export function removeFavoritePlace(placeId: string, token: string) {
  return settle(apiRequest<void>(`/favorites/${encodeURIComponent(placeId)}`, { method: 'DELETE', token }))
}
