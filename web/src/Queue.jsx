import React, { useMemo, useState } from 'react'
import { DETECTOR_LABEL, UNIT, inr, pct, prettyItem, prettyLocation } from './data.js'

const vertical = (item) =>
  item === 'auto_ride' ? 'Autos' : item === 'egg_table' ? 'Eggs' : 'Commodities'

export default function Queue({ db, onOpen }) {
  const [filter, setFilter] = useState('all')

  const rows = useMemo(() => {
    return db.queue
      .map((f) => ({
        ...f,
        gap: (f.observed.median / f.expected.rate - 1) * 100,
      }))
      .filter((f) => filter === 'all' || vertical(f.item) === filter)
  }, [db.queue, filter])

  const verticals = ['all', 'Commodities', 'Eggs', 'Autos']

  return (
    <>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'baseline' }}>
        <span className="label" style={{ marginRight: 4 }}>Vertical</span>
        {verticals.map((v) => (
          <button key={v} className={filter === v ? 'primary' : ''} onClick={() => setFilter(v)}>
            {v === 'all' ? 'All' : v}
          </button>
        ))}
      </div>

      <table className="grid">
        <thead>
          <tr>
            <th style={{ width: 84 }}>Priority</th>
            <th style={{ width: 74 }}>Ref</th>
            <th>Item</th>
            <th>Location</th>
            <th>Finding</th>
            <th className="right">Observed</th>
            <th className="right">Reference</th>
            <th className="right">Gap</th>
            <th className="right">Days</th>
            <th className="right">Obs</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((f) => {
            const days =
              (new Date(f.window.end) - new Date(f.window.start)) / 86400000 + 1
            return (
              <tr key={f.flag_id} className={`row t${f.tier}`} onClick={() => onOpen(f.flag_id)}>
                <td>
                  <span className={`tier t${f.tier}`}>
                    {f.tier === 3 ? 'Priority' : f.tier === 2 ? 'Review' : 'Withheld'}
                  </span>
                </td>
                <td className="num small nowrap">{f.flag_id}</td>
                <td>{prettyItem(f.item)}</td>
                <td>{prettyLocation(f.location)}</td>
                <td className="small">{DETECTOR_LABEL[f.detector]}</td>
                <td className="num right">{inr(f.observed.median)}</td>
                <td className="num right muted">{inr(f.expected.rate)}</td>
                <td className="num right" style={{ fontWeight: 600 }}>{pct(f.gap)}</td>
                <td className="num right">{days}</td>
                <td className="num right muted">{f.observed.n}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <p className="small muted" style={{ marginTop: 12, maxWidth: 760 }}>
        Sorted by priority, then by distance from the reference rate. Every row is a
        statistical pattern flagged for investigation; none of them establishes that a
        price was set unlawfully. Units are {UNIT[db.queue[0]?.expected.unit] || ''} unless
        stated on the case file.
      </p>
    </>
  )
}
