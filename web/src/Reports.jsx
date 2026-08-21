import React, { useCallback, useEffect, useState } from 'react'
import { apiGet } from './api.js'
import { prettyItem, prettyLocation } from './data.js'

const UNIT = { per_kg: 'per kg', per_piece: 'per piece', per_ride: 'per ride' }

// Reports arrive from the public page and count as tier-C evidence on arrival.
// This screen is the record of what came in, including what the reporter wrote —
// an officer needs the comment as much as the number.
export default function Reports() {
  const [rows, setRows] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const [reports, health] = await Promise.all([
        apiGet('/api/reports', true),
        apiGet('/api/health'),
      ])
      setRows(reports)
      setBusy(!!health.recomputing)
      setError('')
    } catch {
      setError('Could not load reports from the review service.')
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load])

  return (
    <>
      <div className="ab-head">
        <div>
          <h2 style={{ margin: 0, fontSize: 21, fontWeight: 600 }}>Citizen reports</h2>
          <p className="small muted" style={{ margin: '2px 0 0' }}>
            Every price submitted from the public page, newest first. Each counts as a
            tier-C observation and is attributed to the nearest covered market.
          </p>
        </div>
        <span style={{ flex: 1 }} />
        {busy && <span className="conn live busy-pulse">Updating detection…</span>}
      </div>

      {error && <div className="recompute-note">{error}</div>}

      <div className="panel">
        <h2>Received ({rows.length})</h2>
        <div className="body" style={{ padding: 0 }}>
          {rows.length === 0 ? (
            <p className="small muted" style={{ padding: 16, margin: 0 }}>
              No reports submitted yet.
            </p>
          ) : (
            <div className="grid-scroll">
            <table className="grid">
              <thead>
                <tr>
                  <th style={{ width: 86 }}>Reference</th>
                  <th>Submitted</th>
                  <th>Item</th>
                  <th className="right">Price</th>
                  <th>Attributed to</th>
                  <th>Grid cell</th>
                  <th>Comment</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="num small nowrap">{r.reference}</td>
                    <td className="num small nowrap">
                      {String(r.submitted_at).slice(0, 10)}
                      <span className="muted"> {String(r.submitted_at).slice(11, 16)}</span>
                    </td>
                    <td>{prettyItem(r.item)}</td>
                    <td className="num right nowrap">
                      ₹{Number(r.price_inr).toFixed(2)}
                      <span className="muted small"> {UNIT[r.unit] || r.unit}</span>
                      {r.distance_km ? (
                        <span className="muted small"> · {r.distance_km} km</span>
                      ) : null}
                    </td>
                    <td>{r.attributed_to ? prettyLocation(r.attributed_to) : '—'}</td>
                    <td className="num small muted">
                      {Number(r.lat).toFixed(4)}, {Number(r.lng).toFixed(4)}
                    </td>
                    <td className="small">
                      {r.note ? r.note : <span className="muted">no comment</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </div>

      <p className="small muted" style={{ marginTop: 12, maxWidth: 760 }}>
        Reporters are identified only by a ~50m grid cell, never a name or address.
        Reports close together quoting the same price are counted as one locality, so
        repeat submissions from one spot do not build corroboration.
      </p>
    </>
  )
}
