export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h ? `${h} h ${String(m).padStart(2, '0')} m` : `${m} m`
}

const timeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

const shortTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
})

export const formatTime = (unixSeconds: number) => timeFormat.format(new Date(unixSeconds * 1000))
export const formatShortTime = (unixSeconds: number) => shortTimeFormat.format(new Date(unixSeconds * 1000))

export const formatMiles = (miles: number) => `${Math.round(miles).toLocaleString()} mi`

export const formatNumber = (value: number | null, digits: number, unit: string) =>
  value === null ? '—' : `${value.toFixed(digits)} ${unit}`

/** Value for <input type="datetime-local"> in the browser's time zone. */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
