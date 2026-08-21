import React, { useEffect, useState } from 'react'
import { ApiError, apiPost } from './api.js'
import { REPORT_COLUMNS, addReport, getReports, reportsToCsv, subscribe } from './store.js'
import { ITEMS_TA } from './items.ta.js'

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

// Unit hints go through i18n like everything else: "Price paid — Rs per kg"
// half-translated is the sort of thing that survives a demo unnoticed.
const UNIT_KEY = { per_kg: 'unitPerKg', per_piece: 'unitPerPiece', per_ride: 'unitPerRide' }

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

export default function ReportForm({ onBack, online = false, meta = null,
                                    lang = 'en', t = (k) => k }) {
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
    idle: t('geoIdle'),
    locating: t('geoLocating'),
    denied: t('geoDenied'),
    timeout: t('geoTimeout'),
    unavailable: t('geoUnavailable'),
    insecure: t('geoInsecure'),
    outside: geoInfo
      ? t('geoOutsideKm', { km: geoInfo.km.toFixed(0), place: geoInfo.label })
      : t('geoOutside'),
  }

  // Item names follow the price list: Tamil where we have it, the source's
  // English otherwise. The <option> value is always the id, so what the form
  // submits is unaffected by which language is showing.
  const itemLabel = (i) => (lang === 'ta' && ITEMS_TA[i.id]) || i.label

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
        : t('rpUnreachable'))
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
        <button onClick={onBack}>← {t('back')}</button>
        <h2 style={{ margin: 0, fontSize: 21, fontWeight: 600 }}>{t('rpTitle')}</h2>
      </div>

      <div className="split">
        <div className="panel">
          <h2>{t('rpWhat')}</h2>
          <div className="body">
            <form onSubmit={submit} className="rp-form">
              <label>
                <span className="label">{t('rpItem')}</span>
                <select value={item} onChange={(e) => { setItem(e.target.value); setPlace('') }}>
                  {allItems.map((i) => <option key={i.id} value={i.id}>{itemLabel(i)}</option>)}
                </select>
              </label>

              <label>
                <span className="label">
                  {`${t('rpPricePaid')} \u2014 ${UNIT_KEY[spec?.unit] ? t(UNIT_KEY[spec.unit]) : '\u20b9'}`}
                </span>
                <input type="number" step="0.01" min="0" value={price} inputMode="decimal"
                       onChange={(e) => setPrice(e.target.value)} placeholder="0.00" />
              </label>

              {item === 'auto_ride' && (
                <label>
                  <span className="label">{t('rpDistance')}</span>
                  <input type="number" step="0.1" min="0" value={distance} inputMode="decimal"
                         onChange={(e) => setDistance(e.target.value)} placeholder="0.0" />
                </label>
              )}

              <label>
                <span className="label">{t('rpWhere')}</span>
                <select value={chosen?.id || ''}
                        onChange={(e) => { setPlace(e.target.value); setCoords(null) }}
                        disabled={!!coords}>
                  {places.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
              </label>

              <div className="rp-geo">
                {coords ? (
                  <button type="button" onClick={clearLocation}>{t('rpUseArea')}</button>
                ) : (
                  <button type="button" onClick={useMyLocation}
                          disabled={geoState === 'locating'}>
                    {geoState === 'locating' ? t('rpLocating')
                      : geoState === 'idle' ? t('rpUseLocation')
                      : t('rpTryAgain')}
                  </button>
                )}
                {coords ? (
                  <span className="small">
                    <strong>{t('rpCaptured')}</strong>{' '}
                    <span className="mono">
                      {coords[0].toFixed(5)}, {coords[1].toFixed(5)}
                    </span>
                    {accuracy != null && (
                      <span className="muted"> &plusmn;{Math.round(accuracy)}m</span>
                    )}
                    {geoInfo && (
                      <span className="muted">
                        {' '}&middot; {t('rpFiledAgainst')} {geoInfo.label} ({geoInfo.km.toFixed(1)} km)
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
                <span className="label">{t('rpNote')}</span>
                <input value={note} maxLength={60} onChange={(e) => setNote(e.target.value)}
                       placeholder={t('rpNotePlaceholder')} />
              </label>

              <div className="rp-submit">
                <button className="primary" type="submit" disabled={!canSubmit || busy}>
                  {busy ? t('rpSubmitting') : t('rpSubmit')}
                </button>
                {!priceOk && price !== '' && (
                  <span className="small rp-warn">{t('rpPriceError')}</span>
                )}
                {error && <span className="small rp-warn">{error}</span>}
              </div>
            </form>

            {saved && (
              <div className="rp-receipt">
                {receipt && (
                  <>
                    <div className="rp-reference">
                      <span className="label">{t('rpReference')}</span>
                      <span className="rp-reference-id">{receipt.reference}</span>
                    </div>
                    {/* The server's own confirmation is English and says "tier C
                        observation" -- internal vocabulary, on the one page that is
                        certainly being read by the public. The client states it in
                        the reader's language instead; the server text is still in
                        the response for anyone reading the API. */}
                    <p className="small" style={{ marginTop: 0 }}>
                      {t('rpRecorded')} {t('rpQuoteRef')}
                    </p>
                  </>
                )}
                <div className="label" style={{ marginBottom: 6 }}>{t('rpRecordedAs')}</div>
                <div className="mono small rp-csv">
                  {REPORT_COLUMNS.join(',')}<br />
                  {REPORT_COLUMNS.map((c) => saved[c]).join(',')}
                </div>
                <p className="small muted" style={{ marginBottom: 0 }}>
                  {t('rpGridNote')}
                </p>
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div className="panel">
            <h2>{t('rpHappens')}</h2>
            <div className="body small">
              {/* "tier C observation", "independent localities" and "inspection
                  queue" were internal vocabulary on a page for the public. Same
                  five facts, said plainly, and now translatable as whole
                  sentences rather than as fragments around <strong> tags. */}
              <ol className="rp-flow">
                <li>{t('rpStep1')}</li>
                <li>{t('rpStep2')}</li>
                <li>{t('rpStep3')}</li>
                <li>{t('rpStep4')}</li>
                <li>{t('rpStep5')}</li>
              </ol>
              <p className="muted" style={{ marginBottom: 0 }}>{t('rpOneReport')}</p>
            </div>
          </div>

          <div className="panel">
            <h2>{`${t('rpSubmittedHere')} (${rows.length})`}</h2>
            <div className="body">
              {rows.length === 0 ? (
                <p className="small muted" style={{ margin: 0 }}>{t('rpNothingYet')}</p>
              ) : (
                <>
                  <table className="grid small">
                    <tbody>
                      {rows.slice(0, 6).map((r, i) => (
                        <tr key={i}>
                          <td>{(() => { const m = allItems.find((x) => x.id === r.item)
                                 return m ? itemLabel(m) : r.item })()}</td>
                          <td className="num right">₹{Number(r.price_inr).toFixed(2)}</td>
                          <td className="muted small">{r.submitted_at.slice(0, 10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <button onClick={download} style={{ marginTop: 12 }}>
                    {t('rpDownload')}
                  </button>
                  <p className="small muted" style={{ marginBottom: 0, marginTop: 8 }}>
                    {online ? t('rpSentOnline') : t('rpOffline')}
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
