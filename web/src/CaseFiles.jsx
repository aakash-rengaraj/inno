import React, { useMemo, useState } from 'react'
import { gapPct, inr, pct, prettyItem, prettyLocation, shortDate } from './data.js'

// Every case file in one place. Previously a case file was reachable only by
// opening its flag first, which is the right path when you are working a
// finding and the wrong one when you are looking for a document you already
// know exists -- an officer asked to bring "the Katpadi autorickshaw file" was
// three clicks from it.
export default function CaseFiles({ db, onOpen }) {
  const [q, setQ] = useState('')

  const files = useMemo(() => {
    const rows = db.queue.map((f) => ({
      id: f.flag_id,
      item: prettyItem(f.item),
      place: prettyLocation(f.location),
      tier: f.tier,
      gap: gapPct(f),
      observed: f.observed?.median,
      window: f.window,
      obs: f.observed?.n,
    }))
    const needle = q.trim().toLowerCase()
    if (!needle) return rows
    return rows.filter((r) =>
      `${r.id} ${r.item} ${r.place}`.toLowerCase().includes(needle))
  }, [db, q])

  return (
    <div className="panel cf-list">
      <div className="hm-head">
        <div>
          <h2>Case files</h2>
          <p className="muted small">
            One printable document per finding in the queue, each carrying its
            reference rate, its citation and the caveat. {db.queue.length} in total.
          </p>
        </div>
        <input className="pr-search" type="search" value={q} placeholder="Find a case file"
               onChange={(e) => setQ(e.target.value)} aria-label="Find a case file" />
      </div>

      <div className="grid-scroll">
        <table className="grid">
          <thead>
            <tr>
              <th style={{ width: 84 }}>Priority</th>
              <th style={{ width: 74 }}>Ref</th>
              <th>Item</th>
              <th>Market</th>
              <th>Window</th>
              <th className="right">Observed</th>
              <th className="right">Gap</th>
              <th className="right">Obs</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {files.map((r) => (
              <tr key={r.id} onClick={() => onOpen(r.id)} style={{ cursor: 'pointer' }}>
                <td>
                  <span className={`tier t${r.tier}`}>
                    {r.tier === 3 ? 'Priority' : 'Review'}
                  </span>
                </td>
                <td className="num small nowrap">{r.id}</td>
                <td>{r.item}</td>
                <td>{r.place}</td>
                <td className="small muted nowrap">
                  {shortDate(r.window.start)} – {shortDate(r.window.end)}
                </td>
                <td className="num right">{inr(r.observed)}</td>
                <td className="num right" style={{ fontWeight: 600 }}>{pct(r.gap)}</td>
                <td className="num right muted">{r.obs}</td>
                <td className="right">
                  <button onClick={(e) => { e.stopPropagation(); onOpen(r.id) }}>Open</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {files.length === 0 && <p className="muted small">No case file matches {`"${q}"`}.</p>}

      <p className="muted small" style={{ maxWidth: '76ch' }}>
        Each file states a statistical pattern flagged for investigation. None of them
        establishes that a price was set unlawfully.
      </p>
    </div>
  )
}
