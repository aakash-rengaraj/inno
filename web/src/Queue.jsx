import React, { useMemo, useState } from 'react'
import { DETECTOR_LABEL, UNIT, inr, pct, prettyItem, prettyLocation } from './data.js'

const vertical = (item) =>
  item === 'auto_ride' ? 'Autos' : item === 'egg_table' ? 'Eggs' : 'Commodities'

export default function Queue({ db, onOpen }) {
  const [filter, setFilter] = useState('all')

  const [open, setOpen] = useState({})

  // One row per market: an officer makes a visit, not a flag. Supporting
  // findings at the same market sit under it rather than competing with it.
  const groups = useMemo(() => {
    const withGap = db.queue.map((f) => ({
      ...f, gap: (f.observed.median / f.expected.rate - 1) * 100,
    }))
    const filtered = withGap.filter(
      (f) => filter === 'all' || vertical(f.item) === filter)
    const out = []
    filtered.forEach((f) => {
      const last = out[out.length - 1]
      if (last && last.location === f.location) last.members.push(f)
      else out.push({ location: f.location, members: [f] })
    })
    return out
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

      <div className="grid-scroll">
      <table className="grid">
        <thead>
          <tr>
            <th style={{ width: 84 }}>Priority</th>
            <th style={{ width: 74 }}>Ref</th>
            <th>Item</th>
            <th>Market</th>
            <th>Finding</th>
            <th className="right">Observed</th>
            <th className="right">Reference</th>
            <th className="right">Gap</th>
            <th className="right">Days</th>
            <th className="right">Obs</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => {
            const rest = g.members.slice(1)
            const expanded = !!open[g.location]
            const shown = expanded ? g.members : [g.members[0]]
            return (
              <React.Fragment key={g.location}>
                {shown.map((f, i) => {
                  const days =
                    (new Date(f.window.end) - new Date(f.window.start)) / 86400000 + 1
                  const isLead = i === 0
                  return (
                    <tr key={f.flag_id}
                        className={`row t${f.tier} ${isLead ? '' : 'supporting'}`}
                        onClick={() => onOpen(f.flag_id)}>
                      <td>
                        {isLead ? (
                          <span className={`tier t${f.tier}`}>
                            {f.tier === 3 ? 'Priority' : 'Review'}
                          </span>
                        ) : <span className="also">also</span>}
                      </td>
                      <td className="num small nowrap">{f.flag_id}</td>
                      <td>{prettyItem(f.item)}</td>
                      <td>
                        {isLead ? prettyLocation(f.location) : ''}
                        {isLead && rest.length > 0 && (
                          <button className="more" onClick={(e) => {
                            e.stopPropagation()
                            setOpen((o) => ({ ...o, [g.location]: !expanded }))
                          }}>
                            {expanded ? 'hide' : `+${rest.length} more`}
                          </button>
                        )}
                      </td>
                      <td className="small">{DETECTOR_LABEL[f.detector]}</td>
                      <td className="num right">{inr(f.observed.median)}</td>
                      <td className="num right muted">{inr(f.expected.rate)}</td>
                      <td className="num right" style={{ fontWeight: 600 }}>{pct(f.gap)}</td>
                      <td className="num right">{days}</td>
                      <td className="num right muted">{f.observed.n}</td>
                    </tr>
                  )
                })}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
      </div>

      <p className="small muted" style={{ marginTop: 12, maxWidth: 760 }}>
        One row per market, strongest finding first &mdash; an inspection is a visit, not
        a flag. Supporting findings at the same market are grouped under it. Every row is
        a statistical pattern flagged for investigation; none of them establishes that a
        price was set unlawfully.
      </p>
    </>
  )
}
