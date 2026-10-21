import { apiRequest, settle } from './api'
import type { PlanAlternative } from './types'

export interface SavedPlan {
  id: string
  theme: string
  title: string
  summary: string
  stops: PlanAlternative['stops']
  legs: PlanAlternative['legs']
  routes_available: boolean
  created_at: string
  /** Paylaşım linkini açan kişi planın sahibi mi (sahibin kimliği dönmez). */
  is_owner: boolean
}

export type SavedPlanSummary = Pick<SavedPlan, 'id' | 'theme' | 'title' | 'summary' | 'created_at'>

export function shareUrl(id: string): string {
  return `${window.location.origin}${window.location.pathname}?shared=${id}`
}

export function saveFavoritePlan(alt: PlanAlternative, token: string) {
  return settle(
    apiRequest<{ id: string }>('/plans', {
      method: 'POST',
      token,
      body: {
        theme: alt.theme,
        title: alt.title,
        summary: alt.summary,
        stops: alt.stops,
        legs: alt.legs,
        routes_available: alt.routes_available,
      },
    }),
  )
}

export function listSavedPlans(token: string) {
  return settle(apiRequest<SavedPlanSummary[]>('/plans', { token }))
}

export function deleteSavedPlan(id: string, token: string) {
  return settle(apiRequest<void>(`/plans/${id}`, { method: 'DELETE', token }))
}

// Paylaşım linki girişsiz de açılır; token verilirse backend `is_owner`'ı doldurur.
export function fetchSharedPlan(id: string, token?: string) {
  return settle(apiRequest<SavedPlan>(`/shared/${id}`, { token }))
}
