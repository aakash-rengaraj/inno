import React, { useEffect, useMemo, useState } from 'react'
import { apiGet } from './api.js'
import { inr, shortDate } from './data.js'

// Public. One row per commodity: low, typical, high. Nothing else — no market
// names, no modelled band, no flags. See pipeline/prices.py for why each of
// those is absent rather than merely unrendered.
export default function Prices({ online, onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)
  const [q, setQ] = useState('')

  useEffect(() => {
    let dead = false
    const load = online
      ? apiGet('/api/public/prices')
      : fetch(new URL('data/prices.json', document.baseURI)).then((r) => r.json())
    load.then((d) => { if (!dead) setData(d) }).catch(() => { if (!dead) setError(true) })
    return () => { dead = true }
  }, [online])

  const items = useMemo(() => {
    if (!data?.items) return []
    const needle = q.trim().toLowerCase()
    return needle ? data.items.filter((i) => i.label.toLowerCase().includes(needle)) : data.items
  }, [data, q])

  if (error) return <div className="panel"><div className="body muted">Prices are unavailable right now.</div></div>
  if (!data) return <div className="panel"><div className="body muted">Loading prices…</div></div>

  return (
    <div className="panel prices">
      <div className="pr-head">
        <div>
          <h2>Wholesale prices, {shortDate(data.date)}</h2>
          <p className="muted small">
            What each commodity sold for across {data.min_markets}+ mandis in the district,
            per kg. These are <strong>wholesale</strong> rates {'—'} what traders paid at the
            market, not shop prices. Retail is normally higher.
          </p>
        </div>
        <input className="pr-search" type="search" value={q} placeholder="Find a commodity"
               onChange={(e) => setQ(e.target.value)} aria-label="Find a commodity" />
      </div>

      <table className="pr-table">
        <thead>
          <tr>
            <th>Commodity</th>
            <th className="num">Lowest</th>
            <th className="num">Typical</th>
            <th className="num">Highest</th>
            <th className="num">Mandis</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.item}>
              <td>{i.label}</td>
              <td className="num mono">{inr(i.low, 0)}</td>
              <td className="num mono strong">{inr(i.typical, 0)}</td>
              <td className="num mono">{inr(i.high, 0)}</td>
              <td className="num muted">{i.markets}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {items.length === 0 && <p className="muted body">No commodity matches {`"${q}"`}.</p>}

      <p className="muted small pr-note">
        Source: {data.source}. A commodity is listed only when at least{' '}
        {data.min_markets} mandis reported it that day {'—'} fewer than that is not a range.
      </p>

      {onBack && <button className="link" onClick={onBack}>Back</button>}
    </div>
  )
}
