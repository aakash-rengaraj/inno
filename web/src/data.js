// Everything is static JSON on disk. There is no API server, and the demo path
// never touches the network.
export async function loadAll() {
  // when the app is served as a single self-contained page, the artifacts are
  // inlined ahead of the bundle instead of fetched
  if (globalThis.__CASE_DATA__) return globalThis.__CASE_DATA__
  const names = ['queue', 'flags', 'cases', 'charts', 'meta']
  const parts = await Promise.all(
    names.map((n) => fetch(`/data/${n}.json`).then((r) => r.json()))
  )
  return Object.fromEntries(names.map((n, i) => [n, parts[i]]))
}

export const inr = (v, dp = 2) =>
  v == null || Number.isNaN(v) ? '—' : `₹${Number(v).toFixed(dp)}`

export const pct = (v, dp = 0) =>
  v == null || Number.isNaN(v) ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(dp)}%`

export const prettyLocation = (s) =>
  s.replace('vellore_', '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const prettyItem = (s) =>
  ({ auto_ride: 'Autorickshaw fares', egg_table: 'Table eggs',
     tomato: 'Tomato', onion: 'Onion' }[s] || s)

export const UNIT = { per_kg: 'per kg', per_piece: 'per piece',
                      per_ride: 'per ride', per_km: 'per km' }

export const DETECTOR_LABEL = {
  variance_collapse: 'Prices stopped varying between sellers',
  cost_correlation: 'Prices track each other, not costs',
  persistence: 'Sustained gap above reference rate',
  quantisation: 'Fares cluster at round values',
}

export const shortDate = (d) =>
  new Date(d + 'T00:00:00').toLocaleDateString('en-IN',
    { day: '2-digit', month: 'short' })
