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

// Beyond this from every known market, the report is outside the district this
// system covers. Attributing it to the "nearest" market anyway would file it
// against somewhere the reporter has never been.
const MAX_DISTANCE_KM = 30

const distanceKm = (aLat, aLng, bLat, bLng) => {
  const R = 6371
  const rad = (d) => (d * Math.PI) / 180
  const dLat = rad(bLat - aLat)
  const dLng = rad(bLng - aLng)
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(aLat)) * Math.cos(rad(bLat)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

// The list arrives sorted alphabetically, so places[0] is "Ambur" — 51km from
// Vellore town and wrong for almost every reporter. Default to the district
// headquarters instead, and let a real position fix override it.
const defaultPlace = (list) =>
  list.find((p) => p.id === 'vellore_apmc')
  || list.find((p) => p.id === 'vellore_katpadi')
  || list.find((p) => p.id.startsWith('vellore'))
  || list[0]

const nearestPlace = (places, lat, lng) =>
  places.reduce((best, p) => {
    const d = distanceKm(lat, lng, p.lat, p.lng)
    return !best || d < best.km ? { place: p, km: d } : best
  }, null)

export default function ReportForm({ onBack, online = false, meta = null }) {
  const allItems = meta?.report_items?.length ? meta.report_items : FALLBACK_ITEMS
  const allPlaces = meta?.report_places?.length ? meta.report_places : FALLBACK_PLACES

  const [item, setItem] = useState(allItems[0]?.id || 'egg_table')
  const [price, setPrice] = useState('')
  const [distance, setDistance] = useState('')
  const [place, setPlace] = useState('')
  const [coords, setCoords] = useState(null)
  const [accuracy, setAccuracy] = useState(null)
  const [geoInfo, setGeoInfo] = useState(null)
  const [geoState, setGeoState] = useState('idle')
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [rows, setRows] = useState(getReports())

  useEffect(() => subscribe(() => setRows(getReports())), [])

  const spec = allItems.find((i) => i.id === item) || allItems[0]

  // A market report belongs at a market and a zone report in a zone: the egg
  // vertical has no reference rate at a mandi, and vice versa.
  const places = allPlaces.filter((p) => p.kind === (spec?.kind || 'zone'))
  const chosen = places.find((p) => p.id === place) || defaultPlace(places)

  const useMyLocation = () => {
    // Geolocation is only available in a secure context. Opened over plain HTTP
    // on a LAN address it fails silently, which looks like a broken button.
    if (!window.isSecureContext) { setGeoState('insecure'); return }
    if (!navigator.geolocation) { setGeoState('unavailable'); return }

    setGeoState('locating')
    navigator.geolocation.getCurrentPosition(
      (p) => {
        const { latitude, longitude, accuracy } = p.coords
        const near = nearestPlace(places, latitude, longitude)
        if (near && near.km > MAX_DISTANCE_KM) {
          // Keep the dropdown rather than file the report against a market
          // tens of kilometres from where the reporter actually stood.
          setCoords(null)
          setGeoState('outside')
          setGeoInfo({ km: near.km, label: near.place.label })
          return
        }
        setCoords([latitude, longitude])
        setAccuracy(accuracy)
        setGeoInfo(near ? { km: near.km, label: near.place.label } : null)
        // Move the dropdown to the market the report will actually be filed
        // against, so the screen agrees with what gets submitted.
        if (near) setPlace(near.place.id)
        setGeoState('ok')
      },
      (err) => {
        // Distinguish the three cases: one is permanent, two are worth retrying.
        const byCode = { 1: 'denied', 2: 'unavailable', 3: 'timeout' }
        setGeoState(byCode[err.code] || 'unavailable')
      },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 60000 }
    )
  }

  const clearLocation = () => {
    setCoords(null)
    setAccuracy(null)
    setGeoInfo(null)
    setGeoState('idle')
  }

  const GEO_MESSAGE = {
    idle: 'Optional. More precise reports carry further.',
    locating: 'Waiting for a position fix\u2026',
    denied: 'Location permission is blocked. Allow it in your browser settings, '
      + 'or just pick the area below.',
    timeout: 'Could not get a fix in time. Try again, or pick the area below.',
    unavailable: 'Your device could not provide a position. Pick the area below.',
    insecure: 'Location needs a secure connection (https or localhost). '
      + 'Pick the area below.',
    outside: geoInfo
      ? `You appear to be ${geoInfo.km.toFixed(0)} km from the nearest covered `
        + `market (${geoInfo.label}). This service covers Vellore district only \u2014 `
        + 'pick an area below if you are reporting on its behalf.'
      : 'You appear to be outside the covered district.',
  }

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
                {coords ? (
                  <button type="button" onClick={clearLocation}>Use the area instead</button>
                ) : (
                  <button type="button" onClick={useMyLocation}
                          disabled={geoState === 'locating'}>
                    {geoState === 'locating' ? 'Locating\u2026'
                      : geoState === 'idle' ? 'Use my exact location'
                      : 'Try location again'}
                  </button>
                )}
                {coords ? (
                  <span className="small">
                    <strong>Location captured.</strong>{' '}
                    <span className="mono">
                      {coords[0].toFixed(5)}, {coords[1].toFixed(5)}
                    </span>
                    {accuracy != null && (
                      <span className="muted"> &plusmn;{Math.round(accuracy)}m</span>
                    )}
                    {geoInfo && (
                      <span className="muted">
                        {' '}&middot; filed against {geoInfo.label} ({geoInfo.km.toFixed(1)} km)
                      </span>
                    )}
                  </span>
                ) : (
                  <span className={`small ${geoState === 'idle' || geoState === 'locating'
                    ? 'muted' : 'rp-warn'}`}>
                    {GEO_MESSAGE[geoState]}
                  </span>
                )}
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
                  <>
                    <div className="rp-reference">
                      <span className="label">Your reference</span>
                      <span className="rp-reference-id">{receipt.reference}</span>
                    </div>
                    <p className="small" style={{ marginTop: 0 }}>
                      {receipt.message} Quote this reference if you contact the
                      district office about it.
                    </p>
                  </>
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
