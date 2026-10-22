export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE' | 'NO_TRAVEL'

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface PlanRequest {
  origin: Place
  destination: Place
  departure: string // ISO 8601 with offset
  load_lbs: number
  interval_miles: 10 | 25 | 50
  /** Overlay a simulated storm on the real forecast (for demos). */
  demo_storm: boolean
}

export interface Checkpoint {
  mile: number
  lat: number
  lon: number
  eta_ts: number
  covers: [number, number]
  level: RiskLevel | null
  drivers: string[]
  wind_mph: number | null
  gust_mph: number | null
  rain_in_hr: number | null
  snow_in_hr: number | null
}

export interface Route {
  id: string
  rank: number
  recommended: boolean
  roads: string
  /** Town the route was forced through to find an alternative, if any */
  via: string
  distance_miles: number
  duration_s: number
  average_risk: number
  worst_level: RiskLevel | null
  miles_by_level: Record<RiskLevel, number>
  unknown_miles: number
  /** [lat, lon, seconds from departure, mile] */
  path: [number, number, number, number][]
  checkpoints: Checkpoint[]
}

export interface Heatmap {
  start_ts: number
  frames: number
  step_deg: number
  cells: [number, number][]
  /** frame-major: value for cell i at frame f is at f * cells.length + i */
  risk: (number | null)[]
  wind_mph: (number | null)[]
  rain_in_hr: (number | null)[]
  snow_in_hr: (number | null)[]
}

export interface PlanResponse {
  departure_ts: number
  load_lbs: number
  interval_miles: number
  recommended_route_id: string
  recommendation_reason: string
  /** Present only when a simulated storm was overlaid: centre and time at its peak. */
  demo_storm: { lat: number; lon: number; peak_ts: number } | null
  routes: Route[]
  heatmap: Heatmap
  meta: {
    routing_source: string
    weather_source: string
    checkpoint_grid_deg: number
    weather_locations_fetched: number
    weather_locations_cached: number
    elapsed_ms: number
  }
}
