import { useEffect, useId, useState } from 'react'
import { searchPlaces } from '../api/client'
import type { Place } from '../api/types'

interface Props {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
}

export default function PlaceInput({ label, value, onChange }: Props) {
  const id = useId()
  const [text, setText] = useState(value?.label ?? '')
  const [options, setOptions] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('') // what the user typed; drives the search
  const [shownValue, setShownValue] = useState(value)

  // Reflect external changes (e.g. presets) in the text box.
  if (value !== shownValue) {
    setShownValue(value)
    if (value) setText(value.label)
  }

  useEffect(() => {
    if (query.trim().length < 2) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchPlaces(query, controller.signal)
        .then((places) => {
          setOptions(places)
          setActive(0)
          setOpen(true)
          setError(null)
        })
        .catch((e: Error) => {
          if (e.name !== 'AbortError') setError(e.message)
        })
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  const choose = (place: Place) => {
    onChange(place)
    setOpen(false)
  }

  return (
    <div className="field place-input">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={text}
        placeholder="City or address"
        autoComplete="off"
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={`${id}-list`}
        onChange={(e) => {
          setText(e.target.value)
          setQuery(e.target.value)
          if (e.target.value.trim().length < 2) setOptions([])
          if (value) onChange(null)
        }}
        onFocus={() => options.length && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (!open || !options.length) return
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActive((a) => (a + 1) % options.length)
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActive((a) => (a - 1 + options.length) % options.length)
          } else if (e.key === 'Enter') {
            e.preventDefault()
            choose(options[active])
          } else if (e.key === 'Escape') {
            setOpen(false)
          }
        }}
      />
      {open && options.length > 0 && (
        <ul className="suggestions" id={`${id}-list`} role="listbox">
          {options.map((place, i) => (
            <li
              key={`${place.label}-${place.lat}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? 'active' : undefined}
              onMouseDown={(e) => {
                e.preventDefault()
                choose(place)
              }}
            >
              {place.label}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="field-hint error">{error}</p>}
      {!value && text && !open && !error && <p className="field-hint">Pick a place from the suggestions.</p>}
    </div>
  )
}
