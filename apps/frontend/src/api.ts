/** Prefix every /api/... fetch with the configured base URL. */
declare const __API_BASE__: string

export const API_BASE: string =
  typeof __API_BASE__ !== 'undefined' ? __API_BASE__ : ''

export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, init)
}
