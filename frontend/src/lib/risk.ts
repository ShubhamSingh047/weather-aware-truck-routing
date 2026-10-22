import type { RiskLevel } from '../api/types'

export type RGB = [number, number, number]

export const RISK_LEVELS: RiskLevel[] = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL']

export const RISK_LABEL: Record<RiskLevel, string> = {
  LOW: 'Low',
  MODERATE: 'Moderate',
  HIGH: 'High',
  SEVERE: 'Severe',
  NO_TRAVEL: 'No Travel',
}

export const RISK_RGB: Record<RiskLevel, RGB> = {
  LOW: [46, 158, 98],
  MODERATE: [234, 189, 46],
  HIGH: [240, 133, 45],
  SEVERE: [214, 52, 52],
  NO_TRAVEL: [118, 42, 140],
}

export const UNKNOWN_RGB: RGB = [150, 150, 150]

export const riskCss = (level: RiskLevel | null) => `rgb(${(level ? RISK_RGB[level] : UNKNOWN_RGB).join(',')})`

export type Metric = 'risk' | 'wind_mph' | 'rain_in_hr' | 'snow_in_hr'

interface MetricScale {
  label: string
  unit: string
  /** Heatmap weight for a raw value; values <= 0 are not drawn. */
  weight: (value: number) => number
  /** Weight at the top of the colour ramp. */
  max: number
  /** Weights below this fade out, so calm weather stays light and risk stands out. */
  fadeBelow: number
  /** [weight, colour] stops aligned with the assessment thresholds. */
  stops: [number, RGB][]
  legend: { label: string; color: RGB }[]
}

const c = RISK_RGB

export const METRICS: Record<Metric, MetricScale> = {
  risk: {
    label: 'Risk',
    unit: '',
    weight: (level) => level + 1, // Low (0) must still be visible
    max: 5,
    fadeBelow: 2.6,
    stops: [[1, c.LOW], [2, c.MODERATE], [3, c.HIGH], [4, c.SEVERE], [5, c.NO_TRAVEL]],
    legend: RISK_LEVELS.map((l) => ({ label: RISK_LABEL[l], color: c[l] })),
  },
  wind_mph: {
    label: 'Wind',
    unit: 'mph',
    weight: (mph) => mph,
    max: 60,
    fadeBelow: 25,
    stops: [[0, c.LOW], [22, c.LOW], [25, c.MODERATE], [35, c.HIGH], [45, c.SEVERE], [55, c.NO_TRAVEL]],
    legend: [
      { label: '<25', color: c.LOW },
      { label: '25', color: c.MODERATE },
      { label: '35', color: c.HIGH },
      { label: '45', color: c.SEVERE },
      { label: '55+', color: c.NO_TRAVEL },
    ],
  },
  rain_in_hr: {
    label: 'Rain',
    unit: 'in/hr',
    weight: (inches) => inches,
    max: 1.2,
    fadeBelow: 0.1,
    stops: [[0, c.LOW], [0.07, c.LOW], [0.1, c.MODERATE], [0.25, c.HIGH], [0.5, c.SEVERE], [1.0, c.NO_TRAVEL]],
    legend: [
      { label: '<0.1', color: c.LOW },
      { label: '0.1', color: c.MODERATE },
      { label: '0.25', color: c.HIGH },
      { label: '0.5', color: c.SEVERE },
      { label: '>1', color: c.NO_TRAVEL },
    ],
  },
  snow_in_hr: {
    label: 'Snow',
    unit: 'in/hr',
    weight: (inches) => inches,
    max: 3.5,
    fadeBelow: 0.5,
    stops: [[0, c.LOW], [0.4, c.LOW], [0.5, c.MODERATE], [1, c.HIGH], [2, c.SEVERE], [3, c.NO_TRAVEL]],
    legend: [
      { label: '<0.5', color: c.LOW },
      { label: '0.5', color: c.MODERATE },
      { label: '1', color: c.HIGH },
      { label: '2', color: c.SEVERE },
      { label: '>3', color: c.NO_TRAVEL },
    ],
  },
}

/**
 * Sample the stops into an evenly spaced colour ramp; the heatmap maps
 * weight / max linearly onto it.
 */
export function colorRamp(scale: MetricScale, size = 48): RGB[] {
  const { stops, max } = scale
  return Array.from({ length: size }, (_, i) => {
    const value = ((i + 0.5) / size) * max
    if (value <= stops[0][0]) return stops[0][1]
    for (let s = 1; s < stops.length; s++) {
      const [v1, c1] = stops[s]
      if (value <= v1) {
        const [v0, c0] = stops[s - 1]
        const t = (value - v0) / (v1 - v0)
        return c0.map((ch, k) => Math.round(ch + t * (c1[k] - ch))) as RGB
      }
    }
    return stops[stops.length - 1][1]
  })
}
