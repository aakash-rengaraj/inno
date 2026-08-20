// Everything is static JSON on disk. There is no API server, and the demo path
// never touches the network.
const CONSOLE_ARTIFACTS = ['queue', 'flags', 'cases', 'charts', 'meta', 'heatmap']

// The public build ships meta.json alone — tools/build_web deletes the rest, so
// asking for them here would 404 and blank the page. A missing artifact is a
// withheld artifact, not an error.
export async function loadAll(names = CONSOLE_ARTIFACTS) {
  // when the app is served as a single self-contained page, the artifacts are
  // inlined ahead of the bundle instead of fetched
  if (globalThis.__CASE_DATA__) return globalThis.__CASE_DATA__
  const parts = await Promise.all(
    names.map((n) =>
      fetch(`/data/${n}.json`)
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null))
  )
  return Object.fromEntries(names.map((n, i) => [n, parts[i]]))
}

export const inr = (v, dp = 2) =>
  v == null || Number.isNaN(v) ? '—' : `₹${Number(v).toFixed(dp)}`

export const pct = (v, dp = 0) =>
  v == null || Number.isNaN(v) ? '—' : `${v > 0 ? '+' : ''}${Number(v).toFixed(dp)}%`

// Market ids are <town>_apmc / <town>_sandhai; zone ids are vellore_<zone>.
// Stripping the "vellore_" prefix first turns `vellore_apmc` into "Apmc" and
// loses the town entirely, so the queue showed "Banana - Apmc" for the
// district's principal mandi. Take the suffix off first; strip the prefix only
// for the report zones, which have no suffix. Mirrors engine.report_places.
const titleCase = (s) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const prettyLocation = (s) => {
  if (s.endsWith('_sandhai')) return `${titleCase(s.slice(0, -'_sandhai'.length))} Sandhai`
  if (s.endsWith('_apmc')) return `${titleCase(s.slice(0, -'_apmc'.length))} APMC`
  return titleCase(s.replace(/^vellore_/, ''))
}

// Display names come from the data itself (meta.item_labels), so the console
// shows the source's own wording — "Mint(Pudina)", not "Mint Pudina".
const ITEM_LABELS = {}

export function setItemLabels(labels) {
  Object.keys(ITEM_LABELS).forEach((k) => delete ITEM_LABELS[k])
  Object.assign(ITEM_LABELS, labels || {})
}

export const prettyItem = (s) =>
  ITEM_LABELS[s] || ({ auto_ride: 'Autorickshaw fares', egg_table: 'Table eggs' }[s]
    || s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()))

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
