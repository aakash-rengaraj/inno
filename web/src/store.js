// Local persistence for the two things the static artifacts cannot hold:
// citizen reports, and what the regulator has actually done about a flag.
//
// There is no server (CLAUDE.md section 0), so this is localStorage. It is live
// across tabs via the browser's own `storage` event, which fires in every OTHER
// tab on the same origin — so two people on one machine see each other's actions
// immediately. It is not networked, and nothing here pretends otherwise.

const K_REPORTS = 'pmr.reports.v1'
const K_ACTIONS = 'pmr.actions.v1'
const EVENT = 'pmr.change'

const read = (key) => {
  try { return JSON.parse(localStorage.getItem(key) ?? memory[key]) || [] }
  catch { try { return JSON.parse(memory[key]) || [] } catch { return [] } }
}

// Sandboxed frames can refuse storage entirely. Keep an in-memory fallback so the
// board still works for a viewer, rather than throwing on first click.
const memory = {}

const write = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    memory[key] = JSON.stringify(value)
  }
  // `storage` does not fire in the tab that wrote, so announce locally too
  window.dispatchEvent(new CustomEvent(EVENT))
}

export const subscribe = (fn) => {
  const onStorage = (e) => { if (!e.key || e.key.startsWith('pmr.')) fn() }
  window.addEventListener('storage', onStorage)
  window.addEventListener(EVENT, fn)
  return () => {
    window.removeEventListener('storage', onStorage)
    window.removeEventListener(EVENT, fn)
  }
}

// --- citizen reports -------------------------------------------------------

export const getReports = () => read(K_REPORTS)

export const addReport = (row) => {
  const rows = read(K_REPORTS)
  rows.unshift(row)
  write(K_REPORTS, rows)
  return row
}

export const REPORT_COLUMNS =
  ['submitted_at', 'lat', 'lng', 'item', 'price_inr', 'unit', 'distance_km', 'note']

// exactly the shape pipeline/ingest/reports.py parses
export const reportsToCsv = (rows) =>
  [REPORT_COLUMNS.join(','),
   ...rows.map((r) => REPORT_COLUMNS.map((c) => r[c] ?? '').join(','))].join('\n') + '\n'

// --- regulator actions -----------------------------------------------------

export const STATUSES = ['queued', 'assigned', 'inspected', 'closed']

export const STATUS_LABEL = {
  queued: 'Awaiting review',
  assigned: 'Assigned for inspection',
  inspected: 'Inspection completed',
  closed: 'Closed',
}

export const OUTCOMES = [
  'Inspection scheduled',
  'Visited — prices verified against notified rate',
  'Notice issued under review',
  'No discrepancy found on inspection',
  'Referred to enforcement desk',
]

export const getActions = () => read(K_ACTIONS)

export const logAction = ({ flag_id, from, to, officer, note }) => {
  const rows = read(K_ACTIONS)
  rows.unshift({
    id: `ACT-${String(rows.length + 1).padStart(4, '0')}`,
    flag_id, from, to, officer, note: note || '',
    at: new Date().toISOString(),
  })
  write(K_ACTIONS, rows)
}

// current status of a flag = the destination of its most recent action
export const statusOf = (actions, flagId) => {
  const last = actions.find((a) => a.flag_id === flagId)
  return last ? last.to : 'queued'
}

export const resetAll = () => {
  try { localStorage.removeItem(K_REPORTS); localStorage.removeItem(K_ACTIONS) } catch {}
  delete memory[K_REPORTS]; delete memory[K_ACTIONS]
  window.dispatchEvent(new CustomEvent(EVENT))
}
