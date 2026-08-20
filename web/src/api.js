// Talking to the API server.
//
// Base URL resolution, in order:
//   1. VITE_API_BASE at build time  (vite dev on :5173 -> api on :8000)
//   2. same origin                  (served by the API server itself)
//
// Every call degrades: if the server is unreachable the caller falls back to the
// data embedded in the page. A dead server must not blank the screen mid-demo.

const BASE = (import.meta.env?.VITE_API_BASE ?? '').replace(/\/$/, '')

export const apiUrl = (path) => `${BASE}${path}`

const TOKEN_KEY = 'pmr.console.token'

export const getToken = () => {
  try { return sessionStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}
export const setToken = (t) => {
  try { sessionStorage.setItem(TOKEN_KEY, t) } catch { /* private mode */ }
}
export const clearToken = () => {
  try { sessionStorage.removeItem(TOKEN_KEY) } catch { /* private mode */ }
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`)
    this.status = status
  }
}

async function request(path, { method = 'GET', body, auth = false } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) headers['X-Console-Token'] = getToken()
  const res = await fetch(apiUrl(path), {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = ''
    try { detail = (await res.json()).detail } catch { /* non-JSON error */ }
    throw new ApiError(res.status, detail)
  }
  return res.status === 204 ? null : res.json()
}

export const apiGet = (path, auth = false) => request(path, { auth })
export const apiPost = (path, body, auth = false) =>
  request(path, { method: 'POST', body, auth })

/** Is a server there at all? Resolves false rather than throwing. */
export async function apiAvailable() {
  try {
    const c = new AbortController()
    const t = setTimeout(() => c.abort(), 2500)
    const res = await fetch(apiUrl('/api/health'), { signal: c.signal })
    clearTimeout(t)
    return res.ok
  } catch {
    return false
  }
}
