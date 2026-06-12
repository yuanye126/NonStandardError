declare const __API_BASE__: string

// VITE_API_BASE baked in at build time; falls back to the Render backend URL
// when the env var was not set before the Vercel build.
const _baked: string = typeof __API_BASE__ !== 'undefined' ? __API_BASE__ : ''

export const API_BASE: string =
  _baked !== ''
    ? _baked
    : window.location.hostname === 'localhost'
      ? ''
      : 'https://nse-backend.onrender.com'

if (window.location.hostname !== 'localhost') {
  console.info('[NSE] API_BASE =', API_BASE || '(same-origin)')
}

export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, init)
}
