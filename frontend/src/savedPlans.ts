import { supabase } from './supabase'
import type { PlanAlternative } from './types'

export interface SavedPlan {
  id: string
  user_id: string
  theme: string
  title: string
  summary: string
  stops: PlanAlternative['stops']
  legs: PlanAlternative['legs']
  routes_available: boolean
  created_at: string
}

export function shareUrl(id: string): string {
  return `${window.location.origin}${window.location.pathname}?shared=${id}`
}

export function saveFavoritePlan(alt: PlanAlternative, userId: string) {
  return supabase
    .from('saved_plans')
    .insert({
      user_id: userId,
      theme: alt.theme,
      title: alt.title,
      summary: alt.summary,
      stops: alt.stops,
      legs: alt.legs,
      routes_available: alt.routes_available,
    })
    .select('id')
    .single()
}

export function listSavedPlans(userId: string) {
  return supabase
    .from('saved_plans')
    .select('id, theme, title, summary, created_at')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
}

export function deleteSavedPlan(id: string) {
  return supabase.from('saved_plans').delete().eq('id', id)
}

export function fetchSharedPlan(id: string) {
  return supabase.from('saved_plans').select('*').eq('id', id).single<SavedPlan>()
}
