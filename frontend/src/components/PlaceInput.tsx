import { useEffect, useId, useRef, useState } from 'react'
import { searchPlaces } from '../api/client'
import type { Place } from '../api/types'

interface Props {
  label: string
  value: Place | null
  /** The picked place (or null) and the text now in the box. */
  onChange: (place: Place | null, text: string) => void
}

export default function PlaceInput({ label, value, onChange }: Props) {
  const id = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [text, setText] = useState(value?.label ?? '')
  const [options, setOptions] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('') // what the user typed; drives the search
  const [shownValue, setShownValue] = useState(value)
  // The last place picked here: typing its name back (e.g. after an undo) picks it again.
  const [lastPicked, setLastPicked] = useState(value)

  // Reflect external changes (presets, a place resolved at planning) in the text box and drop stale suggestions.
  if (value !== shownValue) {
    setShownValue(value)
    if (value) {
      setText(value.label)
      setLastPicked(value)
      setQuery('')
      setOptions([])
      setOpen(false)
    }
  }

  useEffect(() => {
    if (query.trim().length < 2) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      searchPlaces(query, controller.signal)
        .then((places) => {
          setOptions(places)
          setActive(0)
          // a late answer must not pop the list open after the person has moved on
          setOpen(document.activeElement === inputRef.current)
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
    onChange(place, place.label)
    setOpen(false)
  }

  return (
    <div className="field place-input">
      <label htmlFor={id}>{label}</label>
      <input
        ref={inputRef}
        id={id}
        value={text}
        placeholder="City or address"
        autoComplete="off"
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={`${id}-list`}
        onChange={(e) => {
          const next = e.target.value
          setText(next)
          setQuery(next)
          if (next.trim().length < 2) setOptions([])
          onChange(lastPicked && next.trim() === lastPicked.label ? lastPicked : null, next)
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
      {!value && text.trim().length >= 2 && !open && !error && (
        <p className="field-hint">Plan routes will use the best match for this.</p>
      )}
    </div>
  )
}
