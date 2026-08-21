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

// `locale` so the public page can show a Tamil month beside Tamil text; the
// console always passes nothing and stays en-IN, which is what its case files
// are printed in.
// Percent above or below the reference rate. Derived, not stored: it was
// computed inline in Queue.jsx, so the case-file list silently rendered an empty
// column when it read a `gap` field that does not exist in the artifact. One
// definition, used by both.
export const gapPct = (flag) => {
  const rate = flag?.expected?.rate
  const median = flag?.observed?.median
  if (!rate || median == null) return null
  return (median / rate - 1) * 100
}

export const shortDate = (d, locale = 'en-IN') =>
  new Date(d + 'T00:00:00').toLocaleDateString(locale,
    { day: '2-digit', month: 'short' })
