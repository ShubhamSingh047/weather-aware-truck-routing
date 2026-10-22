import type { SyntheticEvent } from 'react'
import type { PlanRequest } from '../api/types'
import { PRESETS, type TripFormValues } from '../lib/trip'
import PlaceInput from './PlaceInput'

const INTERVALS: PlanRequest['interval_miles'][] = [10, 25, 50]

interface Props {
  values: TripFormValues
  loading: boolean
  onChange: (values: TripFormValues) => void
  onSubmit: () => void
  onIntervalChange: (interval: PlanRequest['interval_miles']) => void
  /** Replace the form values and plan straight away (presets, demo storm toggle). */
  onPreset: (values: TripFormValues) => void
}

export default function TripForm({ values, loading, onChange, onSubmit, onIntervalChange, onPreset }: Props) {
  const set = <K extends keyof TripFormValues>(key: K, value: TripFormValues[K]) => onChange({ ...values, [key]: value })
  const load = Number(values.loadLbs)
  const loadValid = values.loadLbs !== '' && load >= 0 && load <= 80_000
  const canSubmit = Boolean(values.origin && values.destination && values.departure && loadValid)

  const submit = (e: SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (canSubmit && !loading) onSubmit()
  }

  return (
    <form className="trip-form" onSubmit={submit}>
      <PlaceInput label="Origin" value={values.origin} onChange={(p) => set('origin', p)} />
      <PlaceInput label="Destination" value={values.destination} onChange={(p) => set('destination', p)} />
      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={values.departure}
            onChange={(e) => set('departure', e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            min={0}
            max={80000}
            step={500}
            value={values.loadLbs}
            onChange={(e) => set('loadLbs', e.target.value)}
            aria-invalid={!loadValid}
          />
        </div>
      </div>
      <div className="field">
        <span className="label">Weather checkpoint every</span>
        <div className="segmented" role="radiogroup" aria-label="Checkpoint interval">
          {INTERVALS.map((miles) => (
            <button
              key={miles}
              type="button"
              role="radio"
              aria-checked={values.interval === miles}
              className={values.interval === miles ? 'on' : undefined}
              onClick={() => onIntervalChange(miles)}
            >
              {miles} mi
            </button>
          ))}
        </div>
      </div>
      <label className="demo-toggle">
        <input
          type="checkbox"
          checked={values.demoStorm}
          onChange={(e) => (canSubmit ? onPreset({ ...values, demoStorm: e.target.checked }) : set('demoStorm', e.target.checked))}
        />
        <span>
          <strong>Demo storm</strong> — overlay a simulated storm on the real forecast, on the fastest route
        </span>
      </label>
      <button className="primary" type="submit" disabled={!canSubmit || loading}>
        {loading ? 'Planning…' : 'Plan routes'}
      </button>
      <div className="presets">
        <span>Try:</span>
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="link"
            disabled={loading}
            onClick={() => onPreset({ ...values, origin: preset.origin, destination: preset.destination })}
          >
            {preset.label}
          </button>
        ))}
      </div>
    </form>
  )
}
