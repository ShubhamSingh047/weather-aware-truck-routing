import type { Place, PlanRequest, PlanResponse } from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError('Could not reach the server. Check your connection and try again.')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(errorMessage(body) ?? `Request failed (${response.status})`)
  }
  return body as T
}

/** Flatten DRF error bodies ({detail} or {field: [messages]}) into one line. */
function errorMessage(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null
  const record = body as Record<string, unknown>
  if (typeof record.detail === 'string') return record.detail
  const messages = Object.entries(record).flatMap(([field, value]) => {
    const list = Array.isArray(value) ? value : [value]
    return list.map((m) => (field === 'non_field_errors' ? String(m) : `${field.replace('_', ' ')}: ${m}`))
  })
  return messages.length ? messages.join(' ') : null
}

export function planTrip(body: PlanRequest, signal?: AbortSignal): Promise<PlanResponse> {
  return request('/api/trips/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const data = await request<{ results: Place[] }>(`/api/geocode?q=${encodeURIComponent(query)}`, { signal })
  return data.results
}
