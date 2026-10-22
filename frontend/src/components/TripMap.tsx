import { COORDINATE_SYSTEM, FlyToInterpolator, WebMercatorViewport, type MapViewState, type PickingInfo } from '@deck.gl/core'
import { BitmapLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import DeckGL from '@deck.gl/react'
import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState, type Ref } from 'react'
import { Map } from 'react-map-gl/maplibre'
import type { Checkpoint, PlanResponse, Route } from '../api/types'
import { formatNumber, formatTime } from '../lib/format'
import { gridLayout, renderHeatmap } from '../lib/heatmapRaster'
import { RISK_LABEL, RISK_RGB, UNKNOWN_RGB, type Metric } from '../lib/risk'
import { bounds, positionAt, riskSegments, type LonLat, type RiskSegment } from '../lib/route'

const MAP_STYLE = 'https://tiles.openfreemap.org/styles/positron'
const CLOSE_UP_ZOOM = 8 // roughly 100 miles across: individual checkpoints and towns
const TIMELINE_ROOM = 110 // px hidden behind the timeline panel at the bottom
const INITIAL_VIEW: MapViewState = { longitude: -96, latitude: 39, zoom: 3.6, pitch: 0, bearing: 0 }
const ROUTE_RGB: Record<string, [number, number, number]> = {
  A: [29, 78, 216],
  B: [14, 116, 144],
  C: [87, 83, 78],
}

interface Props {
  plan: PlanResponse | null
  selectedRouteId: string | null
  hour: number
  metric: Metric
  showHeatmap: boolean
  hoveredCheckpoint: Checkpoint | null
  onSelectRoute: (id: string) => void
  ref?: Ref<TripMapHandle>
}

/** Camera moves the side panel can ask for. */
export interface TripMapHandle {
  /** Fit one route tightly. */
  zoomToRoute: (routeId: string) => void
  /** Close-up on a route's truck at the current slider time. */
  zoomToTruck: (routeId: string) => void
  /** Close-up on a point, e.g. a checkpoint. */
  zoomToPoint: (position: LonLat) => void
  /** Fit all routes in view. */
  showAllRoutes: () => void
}

export default function TripMap(props: Props) {
  const { plan, selectedRouteId, hour, metric, showHeatmap, hoveredCheckpoint, onSelectRoute, ref } = props
  const [viewState, setViewState] = useState<MapViewState>(INITIAL_VIEW)
  const containerRef = useRef<HTMLDivElement>(null)

  const fitRoutes = useCallback((target: Route[], tight: boolean) => {
    if (!target.length || !containerRef.current) return
    const { clientWidth: width, clientHeight: height } = containerRef.current
    const padding = tight ? 32 : Math.min(80, Math.round(Math.min(width, height) / 6))
    const { longitude, latitude, zoom } = new WebMercatorViewport({ width, height }).fitBounds(bounds(target), {
      padding: { top: padding, left: padding, right: padding, bottom: padding + TIMELINE_ROOM },
    })
    setViewState((v) => ({
      ...v,
      longitude,
      latitude,
      zoom: Math.min(zoom, 11),
      transitionDuration: 900,
      transitionInterpolator: new FlyToInterpolator(),
    }))
  }, [])

  const closeUp = useCallback(([longitude, latitude]: LonLat) => {
    setViewState((v) => ({
      ...v,
      longitude,
      latitude,
      zoom: Math.max(v.zoom, CLOSE_UP_ZOOM),
      transitionDuration: 900,
      transitionInterpolator: new FlyToInterpolator(),
    }))
  }, [])

  // Zoom to the recommended route when a new plan arrives.
  useEffect(() => {
    if (!plan) return
    const recommended = plan.routes.find((r) => r.recommended)
    fitRoutes(recommended ? [recommended] : plan.routes, true)
  }, [plan, fitRoutes])

  useImperativeHandle(
    ref,
    () => {
      const find = (id: string) => plan?.routes.find((r) => r.id === id)
      return {
        zoomToRoute: (id) => {
          const route = find(id)
          if (route) fitRoutes([route], true)
        },
        zoomToTruck: (id) => {
          const route = find(id)
          if (route) closeUp(positionAt(route, hour * 3600))
        },
        zoomToPoint: closeUp,
        showAllRoutes: () => {
          if (plan) fitRoutes(plan.routes, false)
        },
      }
    },
    [plan, hour, fitRoutes, closeUp],
  )

  const routes = useMemo(() => plan?.routes ?? [], [plan])
  const selected = routes.find((r) => r.id === selectedRouteId) ?? null
  const paths = useMemo(
    () => routes.map((r) => ({ route: r, path: r.path.map(([lat, lon]) => [lon, lat] as LonLat) })),
    [routes],
  )
  const segments = useMemo(() => (selected ? riskSegments(selected) : []), [selected])

  const layout = useMemo(() => (plan ? gridLayout(plan.heatmap) : null), [plan])
  const heatmapLayer = useMemo(() => {
    if (!plan || !layout || !showHeatmap) return null
    return new BitmapLayer({
      id: 'weather-heatmap',
      image: renderHeatmap(plan.heatmap, layout, metric, hour),
      bounds: layout.bounds,
      // Grid rows are evenly spaced in latitude, not in Web Mercator.
      _imageCoordinateSystem: COORDINATE_SYSTEM.LNGLAT,
      textureParameters: { minFilter: 'linear', magFilter: 'linear' },
    })
  }, [plan, layout, showHeatmap, metric, hour])

  const layers = [
    heatmapLayer,
    new PathLayer<(typeof paths)[number]>({
      id: 'routes',
      data: paths,
      getPath: (d) => d.path,
      getColor: (d) => (d.route.id === selectedRouteId ? [20, 28, 38, 255] : [...ROUTE_RGB[d.route.id], 170]),
      getWidth: (d) => (d.route.id === selectedRouteId ? 10 : 5),
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 90],
      onClick: ({ object }) => object && onSelectRoute(object.route.id),
      updateTriggers: { getColor: selectedRouteId, getWidth: selectedRouteId },
    }),
    new PathLayer<RiskSegment>({
      id: 'selected-route-risk',
      data: segments,
      getPath: (d) => d.path,
      getColor: (d) => (d.level ? RISK_RGB[d.level] : UNKNOWN_RGB),
      getWidth: 5,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
    }),
    new ScatterplotLayer<Checkpoint>({
      id: 'checkpoints',
      data: selected?.checkpoints ?? [],
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: (d) => (d.level ? RISK_RGB[d.level] : UNKNOWN_RGB),
      getLineColor: [255, 255, 255],
      getRadius: (d) => (d === hoveredCheckpoint ? 10 : 5.5),
      radiusUnits: 'pixels',
      lineWidthUnits: 'pixels',
      getLineWidth: 2,
      stroked: true,
      pickable: true,
      updateTriggers: { getRadius: hoveredCheckpoint },
    }),
    new ScatterplotLayer<{ position: LonLat; kind: string }>({
      id: 'endpoints',
      data: selected
        ? [
            { position: [selected.path[0][1], selected.path[0][0]], kind: 'origin' },
            { position: [selected.path.at(-1)![1], selected.path.at(-1)![0]], kind: 'destination' },
          ]
        : [],
      getPosition: (d) => d.position,
      getFillColor: (d) => (d.kind === 'origin' ? [255, 255, 255] : [20, 28, 38]),
      getLineColor: [20, 28, 38],
      getRadius: 8,
      radiusUnits: 'pixels',
      lineWidthUnits: 'pixels',
      getLineWidth: 3,
      stroked: true,
    }),
    ...truckLayers(routes, selectedRouteId, hour),
  ]

  return (
    <div className="map" ref={containerRef}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: next }) => setViewState(next as MapViewState)}
        controller={{ dragRotate: false, touchRotate: false }}
        layers={layers}
        getTooltip={tooltip}
        getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
      >
        <Map mapStyle={MAP_STYLE} reuseMaps attributionControl={{ compact: true }} />
      </DeckGL>
    </div>
  )
}

function truckLayers(routes: Route[], selectedRouteId: string | null, hour: number) {
  // Draw the selected truck last so it sits on top.
  const ordered = [...routes].sort((a, b) => Number(a.id === selectedRouteId) - Number(b.id === selectedRouteId))
  const trucks = ordered.map((route) => ({ route, position: positionAt(route, hour * 3600) }))
  return [
    new ScatterplotLayer<(typeof trucks)[number]>({
      id: 'trucks',
      data: trucks,
      getPosition: (d) => d.position,
      getFillColor: (d) => (d.route.id === selectedRouteId ? [20, 28, 38] : [...ROUTE_RGB[d.route.id], 230]),
      getLineColor: [255, 255, 255],
      getRadius: (d) => (d.route.id === selectedRouteId ? 11 : 8),
      radiusUnits: 'pixels',
      lineWidthUnits: 'pixels',
      getLineWidth: 2.5,
      stroked: true,
      updateTriggers: { getFillColor: selectedRouteId, getRadius: selectedRouteId },
    }),
    new TextLayer<(typeof trucks)[number]>({
      id: 'truck-labels',
      data: trucks,
      getPosition: (d) => d.position,
      getText: (d) => d.route.id,
      getSize: (d) => (d.route.id === selectedRouteId ? 13 : 11),
      getColor: [255, 255, 255],
      fontWeight: 700,
      fontFamily: 'system-ui, sans-serif',
      updateTriggers: { getSize: selectedRouteId },
    }),
  ]
}

function tooltip({ object, layer }: PickingInfo) {
  if (!object || !layer) return null
  if (layer.id === 'checkpoints') {
    const cp = object as Checkpoint
    const level = cp.level ? RISK_LABEL[cp.level] : 'No forecast'
    const driver = cp.drivers.length ? ` (${cp.drivers.join(', ')})` : ''
    return {
      html: `<strong>Mile ${cp.mile.toFixed(0)} · ${level}${driver}</strong><br/>
        ETA ${formatTime(cp.eta_ts)}<br/>
        Wind ${formatNumber(cp.wind_mph, 0, 'mph')} (gusts ${formatNumber(cp.gust_mph, 0, 'mph')})<br/>
        Rain ${formatNumber(cp.rain_in_hr, 2, 'in/hr')} · Snow ${formatNumber(cp.snow_in_hr, 2, 'in/hr')}`,
      className: 'map-tooltip',
    }
  }
  if (layer.id === 'routes') {
    return { text: `Route ${(object as { route: Route }).route.id}`, className: 'map-tooltip' }
  }
  return null
}
