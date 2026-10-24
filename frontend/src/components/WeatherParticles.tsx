import { WebMercatorViewport, type MapViewState } from '@deck.gl/core'
import { useEffect, useMemo, useRef } from 'react'
import type { PlanResponse } from '../api/types'
import type { Metric } from '../lib/risk'

/**
 * Rain streaks, snowflakes or wind streaks drawn over the map, only in the forecast cells that have
 * that weather at the slider's hour, and denser where it is heavier. A canvas on top of the map that
 * ignores the pointer. Wind shows strength only: the forecast has no direction, so streaks blow left to right.
 */
type Kind = 'rain' | 'snow' | 'wind'
const KIND: Partial<Record<Metric, Kind>> = { rain_in_hr: 'rain', snow_in_hr: 'snow', wind_mph: 'wind' }

// value at which a cell is at full density, and below which nothing is drawn
const SCALE: Record<Kind, { full: number; min: number }> = {
  rain: { full: 0.3, min: 0.005 },
  snow: { full: 1.0, min: 0.02 },
  wind: { full: 40, min: 8 },
}
const MAX_PER_CELL: Record<Kind, number> = { rain: 16, snow: 16, wind: 5 }
const BUDGET = 1200 // particles on screen at most

interface Particle {
  u: number // position inside the cell, 0..1
  v: number
  speed: number // 0.7..1.3 multiplier
  phase: number
}

interface Props {
  plan: PlanResponse | null
  metric: Metric
  hour: number
  enabled: boolean
  viewState: MapViewState
}

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export default function WeatherParticles({ plan, metric, hour, enabled, viewState }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const kind = enabled ? KIND[metric] : undefined

  // 0..1 intensity per heatmap cell at the current (fractional) hour
  const intensities = useMemo(() => {
    if (!plan || !kind) return null
    const { heatmap } = plan
    const values = heatmap[metric as 'rain_in_hr' | 'snow_in_hr' | 'wind_mph']
    const n = heatmap.cells.length
    const f0 = Math.min(Math.floor(hour), heatmap.frames - 1)
    const f1 = Math.min(f0 + 1, heatmap.frames - 1)
    const t = hour - f0
    const { full, min } = SCALE[kind]
    return heatmap.cells.map((_, i) => {
      const a = values[f0 * n + i] ?? 0
      const b = values[f1 * n + i] ?? a
      const v = a + (b - a) * t
      return v < min ? 0 : Math.min(1, 0.15 + (0.85 * v) / full)
    })
  }, [plan, kind, metric, hour])

  // the animation loop reads the latest values from refs so it never restarts on a slider move
  const live = useRef({ intensities, viewState, plan, kind })
  useEffect(() => {
    live.current = { intensities, viewState, plan, kind }
  }, [intensities, viewState, plan, kind])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !kind || reducedMotion()) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const pools = new Map<number, Particle[]>()
    const spawn = (): Particle => ({ u: Math.random(), v: Math.random(), speed: 0.7 + Math.random() * 0.6, phase: Math.random() * 6.28 })
    let frame = 0
    let last = performance.now()

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      const { intensities: level, viewState: vs, plan: p } = live.current
      const dpr = window.devicePixelRatio || 1
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr)
        canvas.height = Math.round(h * dpr)
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)
      if (!level || !p || !w || !h) {
        frame = requestAnimationFrame(draw)
        return
      }
      const viewport = new WebMercatorViewport({ ...vs, width: w, height: h })
      const pxPerDeg = (512 * 2 ** vs.zoom) / 360
      const step = p.heatmap.step_deg
      let budget = BUDGET

      if (kind === 'rain') {
        ctx.strokeStyle = 'rgba(29, 61, 140, 0.6)'
        ctx.lineWidth = 1.5
      } else if (kind === 'snow') {
        ctx.lineCap = 'round'
      } else {
        ctx.lineCap = 'round'
        ctx.lineWidth = 1.6
      }
      ctx.beginPath()

      p.heatmap.cells.forEach(([lat, lon], i) => {
        const intensity = level[i]
        if (!intensity) {
          pools.delete(i)
          return
        }
        const [cx, cy] = viewport.project([lon, lat])
        const cw = step * pxPerDeg
        const ch = cw / Math.cos((lat * Math.PI) / 180)
        if (cx < -cw || cx > w + cw || cy < -ch || cy > h + ch) return
        // more particles in bigger (zoomed-in) cells, fewer when zoomed out
        const area = Math.min(4, Math.max(kind === 'wind' ? 0.4 : 0.9, (cw * ch) / 3600))
        const want = Math.min(budget, Math.round(intensity * MAX_PER_CELL[kind] * area))
        budget -= want
        const pool = pools.get(i) ?? []
        while (pool.length < want) pool.push(spawn())
        pool.length = want
        pools.set(i, pool)

        for (const q of pool) {
          if (kind === 'rain') {
            q.v += ((480 + 260 * intensity) * q.speed * dt) / ch
            q.u -= (90 * q.speed * dt) / cw
          } else if (kind === 'snow') {
            q.v += ((35 + 30 * intensity) * q.speed * dt) / ch
            q.u += (Math.sin(now / 700 + q.phase) * 14 * dt) / cw
          } else {
            q.u += ((140 + 520 * intensity) * q.speed * dt) / cw
            q.v += (Math.sin(now / 400 + q.phase) * 6 * dt) / ch
          }
          q.u -= Math.floor(q.u)
          q.v -= Math.floor(q.v)
          const x = cx + (q.u - 0.5) * cw
          const y = cy + (q.v - 0.5) * ch
          if (kind === 'rain') {
            ctx.moveTo(x, y)
            ctx.lineTo(x - 3.5, y + 13)
          } else if (kind === 'snow') {
            // six-armed flake: three strokes through the centre, slowly turning
            const r = 2.6 + q.speed * 1.8
            const turn = now / 2400 + q.phase
            for (let k = 0; k < 3; k++) {
              const a = turn + (k * Math.PI) / 3
              const dx = Math.cos(a) * r
              const dy = Math.sin(a) * r
              ctx.moveTo(x - dx, y - dy)
              ctx.lineTo(x + dx, y + dy)
            }
          } else {
            const len = 14 + 22 * intensity * q.speed
            ctx.moveTo(x, y)
            ctx.lineTo(x + len, y)
          }
        }
        if (kind === 'wind') {
          ctx.strokeStyle = `rgba(25, 45, 75, ${0.2 + 0.4 * intensity})`
          ctx.stroke()
          ctx.beginPath()
        }
      })
      if (kind === 'snow') {
        ctx.strokeStyle = 'rgba(20, 60, 90, 0.45)' // halo so white flakes read on a pale map
        ctx.lineWidth = 3.2
        ctx.stroke()
        ctx.strokeStyle = '#ffffff'
        ctx.lineWidth = 1.5
        ctx.stroke()
      } else if (kind === 'rain') {
        ctx.stroke()
      }
      frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(frame)
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
  }, [kind])

  if (!kind) return null
  return <canvas ref={canvasRef} className="weather-particles" aria-hidden />
}
