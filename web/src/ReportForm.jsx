import React, { useEffect, useState } from 'react'
import { ApiError, apiPost } from './api.js'
import { REPORT_COLUMNS, addReport, getReports, reportsToCsv, subscribe } from './store.js'

// Fallback only. The real list comes from the server, so the form cannot drift
// out of step with the places and commodities the pipeline actually knows.
const FALLBACK_ITEMS = [
  { id: 'egg_table', label: 'Table eggs', unit: 'per_piece', kind: 'zone' },
  { id: 'auto_ride', label: 'Autorickshaw fare', unit: 'per_ride', kind: 'zone' },
]
const FALLBACK_PLACES = [
  { id: 'vellore_katpadi', label: 'Katpadi', lat: 12.9698, lng: 79.1325, kind: 'zone' },
  { id: 'vellore_bagayam', label: 'Bagayam', lat: 12.906, lng: 79.093, kind: 'zone' },
  { id: 'vellore_sathuvachari', label: 'Sathuvachari', lat: 12.934, lng: 79.156, kind: 'zone' },
  { id: 'vellore_thorapadi', label: 'Thorapadi', lat: 12.901, lng: 79.142, kind: 'zone' },
]

const UNIT_HINT = { per_kg: '\u20b9 per kg', per_piece: '\u20b9 per egg',
                    per_ride: '\u20b9 for the trip' }

export default function ReportForm({ onBack, online = false, meta = null }) {
  const allItems = meta?.report_items?.length ? meta.report_items : FALLBACK_ITEMS
  const allPlaces = meta?.report_places?.length ? meta.report_places : FALLBACK_PLACES

  const [item, setItem] = useState(allItems[0]?.id || 'egg_table')
  const [price, setPrice] = useState('')
  const [distance, setDistance] = useState('')
  const [place, setPlace] = useState('')
  const [coords, setCoords] = useState(null)
  const [geoState, setGeoState] = useState('idle')
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [rows, setRows] = useState(getReports())

  useEffect(() => subscribe(() => setRows(getReports())), [])

  const useMyLocation = () => {
    if (!navigator.geolocation) { setGeoState('unavailable'); return }
    setGeoState('locating')
    navigator.geolocation.getCurrentPosition(
      (p) => { setCoords([p.coords.latitude, p.coords.longitude]); setGeoState('ok') },
      () => setGeoState('denied'),
      { timeout: 8000 }
    )
  }

  const spec = allItems.find((i) => i.id === item) || allItems[0]

  // A market report belongs at a market and a zone report in a zone: the egg
  // vertical has no reference rate at a mandi, and vice versa.
  const places = allPlaces.filter((p) => p.kind === (spec?.kind || 'zone'))
  const chosen = places.find((p) => p.id === place) || places[0]
  const effective = coords || (chosen ? [chosen.lat, chosen.lng] : null)
  const priceOk = price !== '' && Number(price) > 0
  const distanceOk = item !== 'auto_ride' || (distance !== '' && Number(distance) > 0)
  const canSubmit = priceOk && distanceOk && effective

  const submit = async (e) => {
    e.preventDefault()
    if (!canSubmit || busy) return
    setError(''); setBusy(true)
    const row = {
      submitted_at: new Date().toISOString(),
      lat: Number(effective[0].toFixed(6)),
      lng: Number(effective[1].toFixed(6)),
      item,
      price_inr: Number(Number(price).toFixed(2)),
      unit: spec.unit,
      distance_km: item === 'auto_ride' ? Number(distance) : '',
      note: note.replace(/[,\n]/g, ' ').slice(0, 60),
    }
    try {
      if (online) {
        const ack = await apiPost('/api/reports', {
          item, price_inr: row.price_inr, lat: row.lat, lng: row.lng,
          distance_km: item === 'auto_ride' ? Number(distance) : null,
          note: row.note, submitted_at: row.submitted_at,
        })
        setReceipt(ack)
      } else {
        setReceipt(null)
      }
      addReport(row)
      setSaved(row)
      setPrice(''); setDistance(''); setNote('')
    } catch (err) {
      setError(err instanceof ApiError
        ? err.message
        : 'Could not reach the service. Your report was kept on this device.')
      if (!(err instanceof ApiError)) { addReport(row); setSaved(row) }
    } finally {
      setBusy(false)
    }
  }

  const download = () => {
    const blob = new Blob([reportsToCsv(rows)], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'field_reports.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="rp">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 20 }}>
        <button onClick={onBack}>← Back</button>
        <h2 style={{ margin: 0, fontSize: 21, fontWeight: 600 }}>Report a price</h2>
      </div>

      <div className="split">
        <div className="panel">
          <h2>What were you charged?</h2>
          <div className="body">
            <form onSubmit={submit} className="rp-form">
              <label>
                <span className="label">Item</span>
                <select value={item} onChange={(e) => { setItem(e.target.value); setPlace('') }}>
                  {allItems.map((i) => <option key={i.id} value={i.id}>{i.label}</option>)}
                </select>
              </label>

              <label>
                <span className="label">{`Price paid \u2014 ${UNIT_HINT[spec?.unit] || '\u20b9'}`}</span>
                <input type="number" step="0.01" min="0" value={price} inputMode="decimal"
                       onChange={(e) => setPrice(e.target.value)} placeholder="0.00" />
              </label>

              {item === 'auto_ride' && (
                <label>
                  <span className="label">Trip distance (km)</span>
                  <input type="number" step="0.1" min="0" value={distance} inputMode="decimal"
                         onChange={(e) => setDistance(e.target.value)} placeholder="0.0" />
                </label>
              )}

              <label>
                <span className="label">Where</span>
                <select value={chosen?.id || ''}
                        onChange={(e) => { setPlace(e.target.value); setCoords(null) }}
                        disabled={!!coords}>
                  {places.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
              </label>

              <div className="rp-geo">
                <button type="button" onClick={useMyLocation} disabled={geoState === 'locating'}>
                  {coords ? 'Location captured' : geoState === 'locating'
                    ? 'Locating…' : 'Use my exact location'}
                </button>
                <span className="small muted">
                  {coords
                    ? `${coords[0].toFixed(5)}, ${coords[1].toFixed(5)}`
                    : geoState === 'denied' ? 'Denied — using the selected area instead'
                    : geoState === 'unavailable' ? 'Unavailable — using the selected area'
                    : 'Optional. More precise reports carry further.'}
                </span>
              </div>

              <label>
                <span className="label">Note (optional)</span>
                <input value={note} maxLength={60} onChange={(e) => setNote(e.target.value)}
                       placeholder="e.g. roadside shop, evening" />
              </label>

              <div className="rp-submit">
                <button className="primary" type="submit" disabled={!canSubmit || busy}>
                  {busy ? 'Submitting…' : 'Submit report'}
                </button>
                {!priceOk && price !== '' && (
                  <span className="small rp-warn">Enter a price above zero.</span>
                )}
                {error && <span className="small rp-warn">{error}</span>}
              </div>
            </form>

            {saved && (
              <div className="rp-receipt">
                {receipt && (
                  <p className="small" style={{ marginTop: 0 }}>
                    <strong>Report #{receipt.id} received.</strong> {receipt.message}
                  </p>
                )}
                <div className="label" style={{ marginBottom: 6 }}>Recorded as</div>
                <div className="mono small rp-csv">
                  {REPORT_COLUMNS.join(',')}<br />
                  {REPORT_COLUMNS.map((c) => saved[c]).join(',')}
                </div>
                <p className="small muted" style={{ marginBottom: 0 }}>
                  This is exactly the row the pipeline ingests. Your coordinates will be
                  rounded to a ~50m grid before anything is published — the record
                  identifies a location, never a trader.
                </p>
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div className="panel">
            <h2>What happens to this</h2>
            <div className="body small">
              <ol className="rp-flow">
                <li>Recorded as a <strong>tier C</strong> observation — the lowest
                    evidence weight the system has.</li>
                <li>Rejected outright if it lacks a geotag or a timestamp.</li>
                <li>Compared against the published reference rate for that item and area.</li>
                <li>Reports close together quoting the same price are treated as
                    <strong> one locality</strong>, so repeat reports from one spot do
                    not add weight.</li>
                <li>A pattern built only from field reports needs
                    <strong> three independent localities</strong> before it can enter
                    the inspection queue. Below that it is withheld.</li>
              </ol>
              <p className="muted" style={{ marginBottom: 0 }}>
                One report does not flag anyone. It is one observation among thousands.
              </p>
            </div>
          </div>

          <div className="panel">
            <h2>{online ? `Submitted from this device (${rows.length})`
                        : `Reports on this device (${rows.length})`}</h2>
            <div className="body">
              {rows.length === 0 ? (
                <p className="small muted" style={{ margin: 0 }}>Nothing submitted yet.</p>
              ) : (
                <>
                  <table className="grid small">
                    <tbody>
                      {rows.slice(0, 6).map((r, i) => (
                        <tr key={i}>
                          <td>{allItems.find((i) => i.id === r.item)?.label || r.item}</td>
                          <td className="num right">₹{Number(r.price_inr).toFixed(2)}</td>
                          <td className="muted small">{r.submitted_at.slice(0, 10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <button onClick={download} style={{ marginTop: 12 }}>
                    Download field_reports.csv
                  </button>
                  <p className="small muted" style={{ marginBottom: 0, marginTop: 8 }}>
                    {online
                      ? 'Sent to the district office for review. This copy is yours.'
                      : 'Offline — reports stay on this device until the CSV is handed '
                        + 'to the pipeline.'}
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
