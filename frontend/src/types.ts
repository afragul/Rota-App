// Backend şemalarının (app/schemas/plan.py) birebir karşılığı.

export type Budget = 'low' | 'medium' | 'high'
export type GroupType = 'solo' | 'couple' | 'friends' | 'family'
export type TravelMode = 'WALK' | 'TRANSIT' | 'DRIVE'

export interface PlanRequest {
  latitude?: number
  longitude?: number
  city?: string
  duration_hours: number
  budget: Budget
  group_type: GroupType
  travel_mode: TravelMode
  categories?: string[]
  free_text?: string
  previous_question?: string
  clarification_answer?: string
}

export interface PlanStop {
  place_id: string
  order: number
  arrival_time: string
  duration_minutes: number
  activity: string
  recommendation: string
  estimated_cost: number
  name: string | null
  latitude: number | null
  longitude: number | null
}

export interface TransitDetail {
  line_name: string | null
  line_color: string | null
  line_text_color: string | null
  vehicle: string | null
  headsign: string | null
  departure_stop: string | null
  arrival_stop: string | null
  departure_time: string | null
  stop_count: number | null
}

export interface RouteStep {
  travel_mode: TravelMode
  instruction: string | null
  maneuver: string | null
  distance_meters: number
  duration_minutes: number
  transit: TransitDetail | null
}

export interface RouteLeg {
  travel_mode: TravelMode
  from_order: number
  to_order: number
  distance_meters: number
  duration_minutes: number
  polyline: string
  steps: RouteStep[]
}

export interface PlanAlternative {
  theme: string
  title: string
  summary: string
  stops: PlanStop[]
  legs: RouteLeg[]
  routes_available: boolean
}

export interface WeatherSummary {
  temperature: number
  condition: string
  is_bad: boolean
}

export interface Place {
  place_id: string
  name: string
  address: string | null
  latitude: number
  longitude: number
  rating: number | null
  user_rating_count: number | null
  types: string[]
}

export interface DayPlan {
  weather_available: boolean
  weather: WeatherSummary | null
  alternatives: PlanAlternative[]
  place_pool: Place[]
}

export interface ClarificationNeeded {
  question: string
}

export type PlanResponse = DayPlan | ClarificationNeeded

export function isClarification(r: PlanResponse): r is ClarificationNeeded {
  return 'question' in r
}

export interface ApproachRoute {
  travel_mode: TravelMode
  distance_meters: number
  duration_minutes: number
  polyline: string
  steps: RouteStep[]
}
