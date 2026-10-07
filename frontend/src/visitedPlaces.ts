import { supabase } from './supabase'
import type { Place } from './types'

export interface VisitedPlace extends Place {
  visit_count: number
  last_visited_at: string
}

// "Sık gidilen yerler" (ana sayfa): en çok "Ulaşıldı" işaretlenen mekanlar.
export function listFrequentPlaces(userId: string, limit = 5) {
  return supabase
    .from('visited_places')
    .select(
      'place_id, name, address, latitude, longitude, rating, user_rating_count, types, visit_count, last_visited_at',
    )
    .eq('user_id', userId)
    .order('visit_count', { ascending: false })
    .order('last_visited_at', { ascending: false })
    .limit(limit)
}

// Bir durak "Ulaşıldı" işaretlenince çağrılır (DetailScreen::toggleArrived).
// Kritik değil: çağıran taraf bunu await'siz/fire-and-forget çağırır.
export async function recordVisit(place: Place, userId: string): Promise<void> {
  const { data: existing } = await supabase
    .from('visited_places')
    .select('id, visit_count')
    .eq('user_id', userId)
    .eq('place_id', place.place_id)
    .maybeSingle()

  if (existing) {
    await supabase
      .from('visited_places')
      .update({ visit_count: existing.visit_count + 1, last_visited_at: new Date().toISOString() })
      .eq('id', existing.id)
  } else {
    await supabase.from('visited_places').insert({
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
}
