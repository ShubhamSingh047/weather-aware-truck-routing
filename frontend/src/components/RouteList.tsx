import { memo } from 'react'
import type { PlanResponse, Route } from '../api/types'
import { formatDuration, formatMiles, formatShortTime } from '../lib/format'
import { RISK_LABEL, RISK_LEVELS, riskCss } from '../lib/risk'

interface Props {
  plan: PlanResponse
  selectedRouteId: string | null
  onSelect: (id: string) => void
}

function RouteList({ plan, selectedRouteId, onSelect }: Props) {
  const recommended = plan.routes.find((r) => r.recommended)
  return (
    <section className="results" aria-label="Route options">
      {recommended && (
        <button type="button" className="recommendation" onClick={() => onSelect(recommended.id)}>
          <span className="recommendation-title">
            Recommended: <strong>Route {recommended.id}</strong>
            {recommended.roads && <span className="muted"> via {recommended.roads}</span>}
          </span>
          <span className="recommendation-reason">{plan.recommendation_reason}</span>
        </button>
      )}
      {plan.routes.length < 3 && (
        <p className="notice">Only {plan.routes.length} distinct route(s) exist between these places.</p>
      )}
      <p className="notice">Click a route (or the recommendation) to zoom to it, and again to zoom in on its truck.</p>
      <ul className="route-cards">
        {plan.routes.map((route) => (
          <li key={route.id}>
            <RouteCard
              route={route}
              departureTs={plan.departure_ts}
              selected={route.id === selectedRouteId}
              onSelect={() => onSelect(route.id)}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}

function RouteCard({ route, departureTs, selected, onSelect }: {
  route: Route
  departureTs: number
  selected: boolean
  onSelect: () => void
}) {
  const m = route.miles_by_level
  return (
    <button
      type="button"
      className={`route-card${selected ? ' selected' : ''}`}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <div className="route-card-head">
        <span className={`route-badge route-${route.id}`}>{route.id}</span>
        <span className="route-roads">
          {route.roads || 'Route ' + route.id}
          {route.via && <span className="muted"> · via {route.via}</span>}
        </span>
        {route.recommended ? <span className="pill best">Recommended</span> : <span className="pill">#{route.rank}</span>}
      </div>
      <div className="route-stats">
        <span><strong>{formatDuration(route.duration_s)}</strong></span>
        <span>{formatMiles(route.distance_miles)}</span>
        <span className="muted">arrive {formatShortTime(departureTs + route.duration_s)}</span>
      </div>
      <RiskBar route={route} />
      <div className="route-risk">
        <span>Severe <strong>{m.SEVERE.toFixed(0)} mi</strong></span>
        <span>High <strong>{m.HIGH.toFixed(0)} mi</strong></span>
        <span>Avg risk <strong>{route.average_risk.toFixed(2)}</strong></span>
      </div>
      {m.NO_TRAVEL > 0 && (
        <p className="warning">⚠ {m.NO_TRAVEL.toFixed(0)} mi of No Travel conditions on this route</p>
      )}
      {route.unknown_miles > 0 && (
        <p className="notice">{route.unknown_miles.toFixed(0)} mi beyond the forecast window</p>
      )}
    </button>
  )
}

function RiskBar({ route }: { route: Route }) {
  const total = route.distance_miles || 1
  const title = RISK_LEVELS.filter((l) => route.miles_by_level[l] > 0)
    .map((l) => `${RISK_LABEL[l]}: ${route.miles_by_level[l].toFixed(0)} mi`)
    .join(' · ')
  return (
    <div className="risk-bar" title={title} aria-label={`Risk by miles: ${title}`}>
      {RISK_LEVELS.map((level) => {
        const share = route.miles_by_level[level] / total
        return share > 0 ? (
          <span key={level} style={{ width: `${share * 100}%`, background: riskCss(level) }} />
        ) : null
      })}
    </div>
  )
}

export default memo(RouteList)
