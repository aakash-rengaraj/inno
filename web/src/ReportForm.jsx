import React, { useEffect, useState } from 'react'
import { ApiError, apiPost } from './api.js'
import { REPORT_COLUMNS, addReport, getReports, reportsToCsv, subscribe } from './store.js'

// Coordinates for people who decline location access. Chosen from the same
// canonical locations the pipeline knows about.
const PLACES = {
  vellore_katpadi: [12.9698, 79.1325],
  vellore_bagayam: [12.9060, 79.0930],
  vellore_sathuvachari: [12.9340, 79.1560],
  vellore_thorapadi: [12.9010, 79.1420],
  vellore_market: [12.9165, 79.1325],
  vellore_gudiyatham: [12.9450, 78.8700],
  vellore_vaniyambadi: [12.6820, 78.6200],
  vellore_arakkonam: [13.0830, 79.6700],
}

const ITEMS = {
  tomato: { label: 'Tomato', unit: 'per_kg', hint: '₹ per kg' },
  onion: { label: 'Onion', unit: 'per_kg', hint: '₹ per kg' },
  egg_table: { label: 'Table eggs', unit: 'per_piece', hint: '₹ per egg' },
  auto_ride: { label: 'Autorickshaw fare', unit: 'per_ride', hint: '₹ for the trip' },
}

const pretty = (s) => s.replace('vellore_', '').replace(/_/g, ' ')
  .replace(/\b\w/g, (c) => c.toUpperCase())

export default function ReportForm({ onBack, online = false }) {
  const [item, setItem] = useState('egg_table')
  const [price, setPrice] = useState('')
  const [distance, setDistance] = useState('')
  const [place, setPlace] = useState('vellore_katpadi')
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

  const effective = coords || PLACES[place]
  const spec = ITEMS[item]
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
                <select value={item} onChange={(e) => setItem(e.target.value)}>
                  {Object.entries(ITEMS).map(([k, v]) =>
                    <option key={k} value={k}>{v.label}</option>)}
                </select>
              </label>

              <label>
                <span className="label">Price paid — {spec.hint}</span>
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
                <select value={place} onChange={(e) => { setPlace(e.target.value); setCoords(null) }}
                        disabled={!!coords}>
                  {Object.keys(PLACES).map((k) =>
                    <option key={k} value={k}>{pretty(k)}</option>)}
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
                          <td>{ITEMS[r.item]?.label || r.item}</td>
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
