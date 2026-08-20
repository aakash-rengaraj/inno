import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { apiGet, apiPost } from './api.js'
import {
  OUTCOMES, STATUSES, STATUS_LABEL, getActions, logAction, resetAll, statusOf, subscribe,
} from './store.js'
import { inr, prettyItem, prettyLocation } from './data.js'

const OFFICERS = ['DSO-1', 'DSO-2', 'RTO-1', 'RTO-2']

const NEXT = { queued: 'assigned', assigned: 'inspected', inspected: 'closed', closed: null }
const NEXT_VERB = {
  queued: 'Assign', assigned: 'Record inspection', inspected: 'Close', closed: null,
}

const ago = (iso) => {
  const s = Math.max(0, (Date.now() - new Date(iso)) / 1000)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
}

export default function ActionBoard({ db, onOpen, live = false }) {
  const [actions, setActions] = useState(getActions())
  const [officer, setOfficer] = useState(OFFICERS[0])
  const [tick, setTick] = useState(0)

  // With a server, actions are shared across machines and survive a browser
  // reset. Without one, they are local to this browser and sync across its tabs.
  const refresh = useCallback(async () => {
    if (!live) { setActions(getActions()); return }
    try { setActions(await apiGet('/api/actions', true)) } catch { /* keep last */ }
  }, [live])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => (live ? undefined : subscribe(() => setActions(getActions()))), [live])
  useEffect(() => {
    if (!live) return undefined
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [live, refresh])
  // keep the relative timestamps honest without a server
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 30000)
    return () => clearInterval(t)
  }, [])

  const rows = useMemo(
    () => db.queue.map((f) => ({ ...f, status: statusOf(actions, f.flag_id) })),
    [db.queue, actions]
  )

  const counts = useMemo(() => {
    const c = Object.fromEntries(STATUSES.map((s) => [s, 0]))
    rows.forEach((r) => { c[r.status] += 1 })
    return c
  }, [rows])

  const advance = async (flag, note) => {
    const to = NEXT[flag.status]
    if (!to) return
    if (live) {
      await apiPost('/api/actions',
        { flag_id: flag.flag_id, from: flag.status, to, officer, note }, true)
      await refresh()
    } else {
      logAction({ flag_id: flag.flag_id, from: flag.status, to, officer, note })
    }
  }

  return (
    <div className="ab" data-tick={tick}>
      <div className="ab-head">
        <div>
          <h2 style={{ margin: 0, fontSize: 21, fontWeight: 600 }}>Action board</h2>
          <p className="small muted" style={{ margin: '2px 0 0' }}>
            {/* The old copy claimed there was no server, which was true when the
                board was localStorage-only and is a false statement about where
                the record lives now that actions are persisted. */}
            What is under review, and what has been done about it.{' '}
            {live
              ? 'Actions are recorded on the review service and shared by everyone signed in.'
              : 'Actions are held in this browser and shared across open tabs on this device only.'}
          </p>
        </div>
        <span style={{ flex: 1 }} />
        <label className="ab-officer">
          <span className="label">Acting as</span>
          <select value={officer} onChange={(e) => setOfficer(e.target.value)}>
            {OFFICERS.map((o) => <option key={o}>{o}</option>)}
          </select>
        </label>
      </div>

      <div className="ab-stats">
        {STATUSES.map((s) => (
          <div className={`ab-stat s-${s}`} key={s}>
            <div className="ab-stat-value num">{counts[s]}</div>
            <div className="label">{STATUS_LABEL[s]}</div>
          </div>
        ))}
      </div>

      <div className="split">
        <div className="panel">
          <h2>Under review</h2>
          <div className="body" style={{ padding: 0 }}>
            <div className="grid-scroll">
            <table className="grid">
              <thead>
                <tr>
                  <th>Ref</th><th>Item</th><th>Location</th>
                  <th className="right">Observed</th><th>Status</th><th>Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((f) => (
                  <tr key={f.flag_id} className={f.tier === 3 ? 't3' : ''}>
                    <td className="num small nowrap">
                      <a href="#" onClick={(e) => { e.preventDefault(); onOpen(f.flag_id) }}>
                        {f.flag_id}
                      </a>
                    </td>
                    <td>{prettyItem(f.item)}</td>
                    <td>{prettyLocation(f.location)}</td>
                    <td className="num right">{inr(f.observed.median)}</td>
                    <td><span className={`ab-pill s-${f.status}`}>{STATUS_LABEL[f.status]}</span></td>
                    <td>
                      {NEXT[f.status] ? (
                        <StatusAction flag={f} onAdvance={advance} />
                      ) : (
                        <span className="small muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Activity ({actions.length})</h2>
          <div className="body">
            {actions.length === 0 ? (
              <p className="small muted" style={{ margin: 0 }}>
                No action recorded yet. Assign a flag to start the log.
              </p>
            ) : (
              <ol className="ab-log">
                {actions.slice(0, 14).map((a) => (
                  <li key={a.id}>
                    <div className="ab-log-top">
                      <span className="mono small">{a.flag_id}</span>
                      <span className="small muted">{ago(a.at)}</span>
                    </div>
                    <div className="small">
                      <strong>{a.officer}</strong> — {STATUS_LABEL[a.to].toLowerCase()}
                    </div>
                    {a.note && <div className="small muted">{a.note}</div>}
                  </li>
                ))}
              </ol>
            )}
            {actions.length > 0 && !live && (
              <button onClick={resetAll} style={{ marginTop: 14 }}>Clear log</button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatusAction({ flag, onAdvance }) {
  const [note, setNote] = useState('')
  const needsOutcome = flag.status === 'assigned'
  return (
    <div className="ab-action">
      {needsOutcome && (
        <select value={note} onChange={(e) => setNote(e.target.value)}>
          <option value="">Outcome…</option>
          {OUTCOMES.map((o) => <option key={o}>{o}</option>)}
        </select>
      )}
      <button
        onClick={() => onAdvance(flag, note)}
        disabled={needsOutcome && !note}
      >
        {NEXT_VERB[flag.status]}
      </button>
    </div>
  )
}
