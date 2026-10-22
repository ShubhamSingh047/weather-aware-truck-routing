import { memo } from 'react'
import type { Checkpoint, Route } from '../api/types'
import { formatNumber, formatShortTime } from '../lib/format'
import { RISK_LABEL, riskCss } from '../lib/risk'

interface Props {
  route: Route
  onHover: (checkpoint: Checkpoint | null) => void
  onPick: (checkpoint: Checkpoint) => void
}

function CheckpointList({ route, onHover, onPick }: Props) {
  return (
    <section className="checkpoints" aria-label={`Checkpoints for route ${route.id}`}>
      <h2>
        Route {route.id} checkpoints <span className="muted">({route.checkpoints.length})</span>
      </h2>
      <p className="muted small">Weather at each point is the forecast for the truck's arrival time. Click a row to zoom the map and timeline to it.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA</th>
              <th>Risk</th>
              <th>Wind</th>
              <th>Rain</th>
              <th>Snow</th>
            </tr>
          </thead>
          <tbody onMouseLeave={() => onHover(null)}>
            {route.checkpoints.map((cp) => (
              <tr key={cp.mile} onMouseEnter={() => onHover(cp)} onClick={() => onPick(cp)}>
                <td>{cp.mile.toFixed(0)}</td>
                <td>{formatShortTime(cp.eta_ts)}</td>
                <td>
                  <span className="level" style={{ background: riskCss(cp.level) }}>
                    {cp.level ? RISK_LABEL[cp.level] : 'n/a'}
                  </span>
                </td>
                <td className={cp.drivers.includes('wind') ? 'driver' : undefined}>
                  {formatNumber(cp.wind_mph, 0, '')}
                  <span className="muted"> /{formatNumber(cp.gust_mph, 0, '')}</span>
                </td>
                <td className={cp.drivers.includes('rain') ? 'driver' : undefined}>{formatNumber(cp.rain_in_hr, 2, '')}</td>
                <td className={cp.drivers.includes('snow') ? 'driver' : undefined}>{formatNumber(cp.snow_in_hr, 2, '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">Wind in mph (sustained / gust); rain and snow in in/hr. Bold values set the risk level.</p>
    </section>
  )
}

export default memo(CheckpointList)
