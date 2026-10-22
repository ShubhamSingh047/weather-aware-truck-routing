import type { Heatmap } from '../api/types'
import { METRICS, colorRamp, type Metric, type RGB } from './risk'

/**
 * The weather heatmap is a regular lat/lon grid, so it is drawn as a tiny image
 * (one pixel per grid cell) that the GPU stretches over the map with bilinear
 * filtering. That gives a smooth field with soft edges, and redrawing it for a
 * new slider position only touches a few hundred pixels.
 */
export interface GridLayout {
  cols: number
  rows: number
  /** Pixel index for each heatmap cell. */
  pixel: Int32Array
  /** [west, south, east, north] edges of the image in degrees. */
  bounds: [number, number, number, number]
}

const RAMP_SIZE = 256
const MAX_ALPHA = 0.72
const MIN_ALPHA_SHARE = 0.3 // calm-but-present weather stays faintly visible

export function gridLayout(heatmap: Heatmap): GridLayout {
  const step = heatmap.step_deg
  const lats = heatmap.cells.map((c) => c[0])
  const lons = heatmap.cells.map((c) => c[1])
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  const minLon = Math.min(...lons)
  const maxLon = Math.max(...lons)
  const cols = Math.round((maxLon - minLon) / step) + 1
  const rows = Math.round((maxLat - minLat) / step) + 1
  const pixel = new Int32Array(heatmap.cells.length)
  heatmap.cells.forEach(([lat, lon], i) => {
    const col = Math.round((lon - minLon) / step)
    const row = Math.round((maxLat - lat) / step) // row 0 is the northern edge
    pixel[i] = row * cols + col
  })
  // Pixel centres sit on cell centres, so the image extends half a cell beyond them.
  const half = step / 2
  return { cols, rows, pixel, bounds: [minLon - half, minLat - half, maxLon + half, maxLat + half] }
}

const ramps = new Map<Metric, RGB[]>()
function rampFor(metric: Metric): RGB[] {
  let ramp = ramps.get(metric)
  if (!ramp) {
    ramp = colorRamp(METRICS[metric], RAMP_SIZE)
    ramps.set(metric, ramp)
  }
  return ramp
}

/** Render the heatmap at a fractional hour, blending the two neighbouring hourly frames. */
export function renderHeatmap(heatmap: Heatmap, layout: GridLayout, metric: Metric, hour: number): ImageData {
  const scale = METRICS[metric]
  const ramp = rampFor(metric)
  const values = metric === 'risk' ? heatmap.risk : heatmap[metric]
  const n = heatmap.cells.length
  const f0 = Math.min(Math.floor(hour), heatmap.frames - 1)
  const f1 = Math.min(f0 + 1, heatmap.frames - 1)
  const t = hour - f0

  const { cols, rows, pixel } = layout
  const data = new Uint8ClampedArray(cols * rows * 4)
  for (let i = 0; i < n; i++) {
    let a = values[f0 * n + i]
    let b = values[f1 * n + i]
    if (a === null && b === null) continue
    a ??= b as number
    b ??= a
    const weight = scale.weight(a + (b - a) * t)
    if (weight <= 0) continue
    const color = ramp[Math.min(RAMP_SIZE - 1, Math.floor((weight / scale.max) * RAMP_SIZE))]
    const alpha = MAX_ALPHA * Math.min(1, Math.max(MIN_ALPHA_SHARE, weight / scale.fadeBelow))
    const p = pixel[i] * 4
    data[p] = color[0]
    data[p + 1] = color[1]
    data[p + 2] = color[2]
    data[p + 3] = Math.round(alpha * 255)
  }
  bleedColors(data, cols, rows)
  return new ImageData(data, cols, rows)
}

/**
 * Give transparent pixels the colour of a visible neighbour (alpha stays 0), so
 * bilinear filtering fades edges out in the right hue instead of towards black.
 */
function bleedColors(data: Uint8ClampedArray, cols: number, rows: number) {
  const source = data.slice()
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const p = (row * cols + col) * 4
      if (source[p + 3] > 0) continue
      for (const [dr, dc] of NEIGHBOURS) {
        const r = row + dr
        const c = col + dc
        if (r < 0 || r >= rows || c < 0 || c >= cols) continue
        const q = (r * cols + c) * 4
        if (source[q + 3] > 0) {
          data[p] = source[q]
          data[p + 1] = source[q + 1]
          data[p + 2] = source[q + 2]
          break
        }
      }
    }
  }
}

const NEIGHBOURS = [
  [0, 1],
  [0, -1],
  [1, 0],
  [-1, 0],
  [1, 1],
  [1, -1],
  [-1, 1],
  [-1, -1],
] as const
