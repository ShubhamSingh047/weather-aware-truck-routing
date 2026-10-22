import { useCallback, useEffect, useRef, useState } from 'react'
import { planTrip } from './api/client'
import type { Checkpoint, PlanRequest, PlanResponse } from './api/types'
import CheckpointList from './components/CheckpointList'
import RiskRules from './components/RiskRules'
import RouteList from './components/RouteList'
import TimelineControls from './components/TimelineControls'
import TripForm from './components/TripForm'
import TripMap, { type TripMapHandle } from './components/TripMap'
import { formatTime, toLocalInputValue } from './lib/format'
import type { Metric } from './lib/risk'
import { PRESETS, type TripFormValues } from './lib/trip'

const PLAYBACK_SECONDS = 12 // a full trip plays in about this long, whatever its length

function nextHour(): string {
  const d = new Date()
  d.setHours(d.getHours() + 1, 0, 0, 0)
  return toLocalInputValue(d)
}

const INITIAL_FORM: TripFormValues = {
  origin: PRESETS[0].origin,
  destination: PRESETS[0].destination,
  departure: nextHour(),
  loadLbs: '42000',
  interval: 25,
  // ?demo=storm starts with the simulated storm on, handy for recording a walkthrough.
  demoStorm: new URLSearchParams(window.location.search).get('demo') === 'storm',
}

export default function App() {
  const [form, setForm] = useState<TripFormValues>(INITIAL_FORM)
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [hoveredCheckpoint, setHoveredCheckpoint] = useState<Checkpoint | null>(null)
  const [hour, setHour] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [metric, setMetric] = useState<Metric>('risk')
  const [showHeatmap, setShowHeatmap] = useState(true)
  const inflight = useRef<AbortController | null>(null)
  const mapRef = useRef<TripMapHandle>(null)
  const lastZoomedRoute = useRef<string | null>(null)

  const runPlan = useCallback(async (values: TripFormValues) => {
    if (!values.origin || !values.destination) return
    inflight.current?.abort()
    const controller = new AbortController()
    inflight.current = controller
    setLoading(true)
    setError(null)
    const request: PlanRequest = {
      origin: values.origin,
      destination: values.destination,
      departure: new Date(values.departure).toISOString(),
      load_lbs: Number(values.loadLbs),
      interval_miles: values.interval,
      demo_storm: values.demoStorm,
    }
    try {
      const result = await planTrip(request, controller.signal)
      setPlan(result)
      lastZoomedRoute.current = result.recommended_route_id // the map zooms to it for a new plan
      setSelectedRouteId(result.recommended_route_id)
      setHoveredCheckpoint(null)
      setHour(0)
      setPlaying(false)
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message)
    } finally {
      if (inflight.current === controller) setLoading(false)
    }
  }, [])

  // Plan the default trip on first load so the map is never empty.
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- fetching on mount is the external sync
    runPlan(INITIAL_FORM)
    return () => inflight.current?.abort()
  }, [runPlan])

  // The timeline runs from departure until the last truck arrives.
  const maxHour = plan ? Math.max(...plan.routes.map((r) => r.duration_s)) / 3600 : 1

  // Forecast playback.
  const hourRef = useRef(hour)
  useEffect(() => {
    hourRef.current = hour
  }, [hour])

  useEffect(() => {
    if (!playing) return
    let frame = 0
    let last = performance.now()
    const tick = (now: number) => {
      const speed = Math.max(1, maxHour / PLAYBACK_SECONDS) // hours per second
      const next = Math.min(maxHour, hourRef.current + ((now - last) / 1000) * speed)
      last = now
      hourRef.current = next
      setHour(next)
      if (next >= maxHour) setPlaying(false)
      else frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing, maxHour])

  const selectedRoute = plan?.routes.find((r) => r.id === selectedRouteId) ?? null

  // First click zooms to the route; clicking the same route again zooms in on its truck.
  const selectRouteFromPanel = useCallback((id: string) => {
    setPlaying(false)
    setSelectedRouteId(id)
    if (lastZoomedRoute.current === id) mapRef.current?.zoomToTruck(id)
    else mapRef.current?.zoomToRoute(id)
    lastZoomedRoute.current = id
  }, [])

  const pickCheckpoint = useCallback(
    (cp: Checkpoint) => {
      if (!plan) return
      setPlaying(false)
      setHour(Math.max(0, Math.min(maxHour, (cp.eta_ts - plan.departure_ts) / 3600)))
      mapRef.current?.zoomToPoint([cp.lon, cp.lat])
      lastZoomedRoute.current = null
    },
    [plan, maxHour],
  )

  return (
    <div className="app">
      <aside className="panel">
        <header className="brand">
          <h1>Weather-Aware Truck Routing</h1>
          <p>Compare three routes by forecast weather at the truck's arrival time, load weight and drive time.</p>
        </header>
        <TripForm
          values={form}
          loading={loading}
          onChange={setForm}
          onSubmit={() => runPlan(form)}
          onIntervalChange={(interval) => {
            const next = { ...form, interval }
            setForm(next)
            if (plan) runPlan(next)
          }}
          onPreset={(values) => {
            setForm(values)
            runPlan(values)
          }}
        />
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
        {plan?.demo_storm && (
          <p className="demo-banner" role="status">
            <strong>Simulated storm.</strong> A demo storm peaking at {formatTime(plan.demo_storm.peak_ts)} is added
            to the real forecast. Risk levels and the recommendation below use the combined weather.
          </p>
        )}
        {plan && (
          <div className={loading ? 'stale' : undefined}>
            <RouteList plan={plan} selectedRouteId={selectedRouteId} onSelect={selectRouteFromPanel} />
            {selectedRoute && (
              <CheckpointList route={selectedRoute} onHover={setHoveredCheckpoint} onPick={pickCheckpoint} />
            )}
          </div>
        )}
        <RiskRules />
        {plan && (
          <footer className="meta">
            Routing: {plan.meta.routing_source === 'tomtom' ? 'TomTom truck profile' : 'OSRM (speeds capped at 65 mph)'} ·
            Weather: Open-Meteo, {plan.meta.weather_locations_fetched} locations fetched,{' '}
            {plan.meta.weather_locations_cached} cached · {(plan.meta.elapsed_ms / 1000).toFixed(1)} s
          </footer>
        )}
      </aside>
      <main className="map-area">
        <TripMap
          plan={plan}
          selectedRouteId={selectedRouteId}
          hour={hour}
          metric={metric}
          showHeatmap={showHeatmap}
          hoveredCheckpoint={hoveredCheckpoint}
          onSelectRoute={setSelectedRouteId}
          ref={mapRef}
        />
        {loading && <div className="map-loading">Fetching routes and forecasts…</div>}
        {plan?.demo_storm && !loading && <div className="map-chip">Simulated storm</div>}
        {plan && (
          <TimelineControls
            hour={hour}
            maxHour={maxHour}
            departureTs={plan.departure_ts}
            playing={playing}
            metric={metric}
            showHeatmap={showHeatmap}
            onHourChange={(h) => {
              setPlaying(false)
              setHour(h)
            }}
            onTogglePlay={() => {
              if (playing) {
                setPlaying(false)
                return
              }
              if (hour >= maxHour) setHour(0)
              // Keep all three routes in view while the trucks move; scroll to zoom in.
              mapRef.current?.showAllRoutes()
              lastZoomedRoute.current = null
              setPlaying(true)
            }}
            onMetricChange={setMetric}
            onToggleHeatmap={() => setShowHeatmap((s) => !s)}
          />
        )}
      </main>
    </div>
  )
}
