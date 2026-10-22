import type { Place, PlanRequest } from '../api/types'

export interface TripFormValues {
  origin: Place | null
  destination: Place | null
  departure: string // datetime-local value
  loadLbs: string
  interval: PlanRequest['interval_miles']
  demoStorm: boolean
}

export const PRESETS: { label: string; origin: Place; destination: Place }[] = [
  {
    label: 'Chicago → Denver',
    origin: { label: 'Chicago, Illinois', lat: 41.8781, lon: -87.6298 },
    destination: { label: 'Denver, Colorado', lat: 39.7392, lon: -104.9903 },
  },
  {
    label: 'Seattle → Salt Lake City',
    origin: { label: 'Seattle, Washington', lat: 47.6062, lon: -122.3321 },
    destination: { label: 'Salt Lake City, Utah', lat: 40.7608, lon: -111.891 },
  },
  {
    label: 'Dallas → Atlanta',
    origin: { label: 'Dallas, Texas', lat: 32.7767, lon: -96.797 },
    destination: { label: 'Atlanta, Georgia', lat: 33.749, lon: -84.388 },
  },
]
