import type { Route, RiskLevel } from '../api/types'

export type LonLat = [number, number]

/** Truck position `seconds` after departure, interpolated along the path. */
export function positionAt(route: Route, seconds: number): LonLat {
  const path = route.path
  if (seconds <= 0) return [path[0][1], path[0][0]]
  const last = path[path.length - 1]
  if (seconds >= last[2]) return [last[1], last[0]]
  let lo = 0
  let hi = path.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (path[mid][2] <= seconds) lo = mid
    else hi = mid
  }
  const [lat0, lon0, s0] = path[lo]
  const [lat1, lon1, s1] = path[hi]
  const t = s1 === s0 ? 0 : (seconds - s0) / (s1 - s0)
  return [lon0 + t * (lon1 - lon0), lat0 + t * (lat1 - lat0)]
}

export interface RiskSegment {
  path: LonLat[]
  level: RiskLevel | null
}

/**
 * Split a route into runs of road coloured by the checkpoint each stretch is
 * attributed to (the same attribution the backend uses for risk miles).
 */
export function riskSegments(route: Route): RiskSegment[] {
  const segments: RiskSegment[] = []
  let cp = 0
  let current: RiskSegment | null = null
  for (const [lat, lon, , mile] of route.path) {
    while (cp < route.checkpoints.length - 1 && mile > route.checkpoints[cp].covers[1]) cp++
    const level = route.checkpoints[cp]?.level ?? null
    const point: LonLat = [lon, lat]
    if (!current || current.level !== level) {
      if (current) current.path.push(point) // share the boundary vertex so lines join
      current = { path: [point], level }
      segments.push(current)
    } else {
      current.path.push(point)
    }
  }
  return segments.filter((s) => s.path.length > 1)
}

export function bounds(routes: Route[]): [[number, number], [number, number]] {
  let minLon = Infinity
  let minLat = Infinity
  let maxLon = -Infinity
  let maxLat = -Infinity
  for (const route of routes) {
    for (const [lat, lon] of route.path) {
      minLon = Math.min(minLon, lon)
      maxLon = Math.max(maxLon, lon)
      minLat = Math.min(minLat, lat)
      maxLat = Math.max(maxLat, lat)
    }
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ]
}
