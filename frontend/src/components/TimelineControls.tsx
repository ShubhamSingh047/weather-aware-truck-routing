import { formatTime } from '../lib/format'
import { METRICS, type Metric } from '../lib/risk'

interface Props {
  hour: number
  /** End of the timeline: when the last truck reaches the destination. */
  maxHour: number
  departureTs: number
  playing: boolean
  metric: Metric
  showHeatmap: boolean
  onHourChange: (hour: number) => void
  onTogglePlay: () => void
  onMetricChange: (metric: Metric) => void
  onToggleHeatmap: () => void
}

export default function TimelineControls(props: Props) {
  const { hour, maxHour, departureTs, playing, metric, showHeatmap } = props
  const scale = METRICS[metric]
  const whole = Math.floor(hour)
  const minutes = Math.round((hour - whole) * 60)
  return (
    <div className="timeline">
      <div className="timeline-row">
        <button
          type="button"
          className="play"
          onClick={props.onTogglePlay}
          aria-label={playing ? 'Pause forecast animation' : 'Play forecast animation'}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <div className="timeline-slider">
          <input
            type="range"
            min={0}
            max={maxHour}
            step={0.25}
            value={hour}
            onChange={(e) => props.onHourChange(Number(e.target.value))}
            aria-label="Hours after departure"
            aria-valuetext={`${whole} hours ${minutes} minutes after departure`}
          />
          <div className="timeline-ticks" aria-hidden>
            {ticks(maxHour).map((h) => (
              <span key={h} style={{ left: `${(h / maxHour) * 100}%` }}>
                {h}h
              </span>
            ))}
            <span className="end" style={{ left: '100%' }} title="Last truck arrives">
              {Math.floor(maxHour)}h {String(Math.round((maxHour % 1) * 60)).padStart(2, '0')}m
            </span>
          </div>
        </div>
        <div className="timeline-time">
          <strong>+{whole}h{minutes ? ` ${minutes}m` : ''}</strong>
          <span>{formatTime(departureTs + hour * 3600)}</span>
        </div>
      </div>
      <div className="timeline-row secondary">
        <label className="toggle">
          <input type="checkbox" checked={showHeatmap} onChange={props.onToggleHeatmap} />
          Heatmap
        </label>
        <div className="segmented small" role="radiogroup" aria-label="Heatmap layer">
          {(Object.keys(METRICS) as Metric[]).map((m) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={metric === m}
              className={metric === m ? 'on' : undefined}
              disabled={!showHeatmap}
              onClick={() => props.onMetricChange(m)}
            >
              {METRICS[m].label}
            </button>
          ))}
        </div>
        <div className="legend" aria-label={`${scale.label} legend`}>
          {scale.legend.map((item) => (
            <span key={item.label}>
              <i style={{ background: `rgb(${item.color.join(',')})` }} />
              {item.label}
            </span>
          ))}
          {scale.unit && <span className="muted">{scale.unit}</span>}
        </div>
      </div>
    </div>
  )
}

/** Whole-hour ticks at a round spacing, about five across the timeline. */
function ticks(maxHour: number): number[] {
  const step = [1, 2, 3, 4, 6, 12, 24].find((s) => maxHour / s <= 6) ?? 24
  const out = []
  for (let h = 0; h <= maxHour - step * 0.75; h += step) out.push(h) // keep clear of the end label
  return out
}
