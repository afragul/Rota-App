import { supabase } from './supabase'
import type { Place } from './types'

export interface FavoritePlace extends Place {
  id: string
}

export function listFavoritePlaces(userId: string) {
  return supabase
    .from('favorite_places')
    .select('id, place_id, name, address, latitude, longitude, rating, user_rating_count, types')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
}

export function addFavoritePlace(place: Place, userId: string) {
  return supabase.from('favorite_places').insert({
    user_id: userId,
    place_id: place.place_id,
    name: place.name,
    address: place.address,
    latitude: place.latitude,
    longitude: place.longitude,
    rating: place.rating,
    user_rating_count: place.user_rating_count,
    types: place.types,
  })
}

export function removeFavoritePlace(userId: string, placeId: string) {
  return supabase.from('favorite_places').delete().eq('user_id', userId).eq('place_id', placeId)
}
