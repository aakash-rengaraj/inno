import React from 'react'
import Chart from './Charts.jsx'
import {
  DETECTOR_LABEL, UNIT, inr, pct, prettyItem, prettyLocation,
} from './data.js'

const TIER_SOURCE = { A: 'Authoritative', B: 'Commercial listing', C: 'Field report' }

export default function FlagDetail({ db, flag, onBack, onCase }) {
  if (!flag) return null
  const chart = db.charts[flag.flag_id]
  const c = db.cases[flag.flag_id]
  const gap = (flag.observed.median / flag.expected.rate - 1) * 100
  const unit = UNIT[flag.expected.unit] || flag.expected.unit

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 16 }}>
        <button onClick={onBack}>← Queue</button>
        <span className={`tier t${flag.tier}`}>
          {flag.tier === 3 ? 'Priority' : 'Review'}
        </span>
        <h2 style={{ margin: 0, fontSize: 21, fontWeight: 600 }}>
          {prettyItem(flag.item)} — {prettyLocation(flag.location)}
        </h2>
        <span className="mono muted small">{flag.flag_id}</span>
        <span style={{ flex: 1 }} />
        <button className="primary" onClick={onCase}>Open case file</button>
      </div>

      <div className="split">
        <div className="panel">
          <h2>{DETECTOR_LABEL[flag.detector]}</h2>
          <div className="body">
            <Chart chart={chart} />
            <p className="narrative" style={{ marginTop: 20 }}>{flag.narrative}</p>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div className="panel">
            <h2>Evidence</h2>
            <div className="body">
              <dl className="kv">
                <dt>Reference rate</dt><dd>{inr(flag.expected.rate)} {unit}</dd>
                <dt>Expected range</dt>
                <dd>{inr(flag.expected.band[0])} – {inr(flag.expected.band[1])}</dd>
                <dt>Observed median</dt><dd>{inr(flag.observed.median)}</dd>
                <dt>Gap</dt><dd style={{ fontWeight: 700 }}>{pct(gap, 1)}</dd>
                <dt>Window</dt>
                <dd className="small">{flag.window.start} → {flag.window.end}</dd>
                <dt>Residual s.d.</dt><dd>{flag.residual_sd}</dd>
              </dl>
              <hr style={{ border: 0, borderTop: '1px solid var(--rule)', margin: '16px 0' }} />
              <div className="label" style={{ marginBottom: 6 }}>Provenance</div>
              <table className="grid" style={{ fontSize: 12 }}>
                <tbody>
                  {Object.entries(flag.observed.tier_mix).sort().map(([t, n]) => (
                    <tr key={t}>
                      <td>Tier {t}</td>
                      <td className="muted small">{TIER_SOURCE[t]}</td>
                      <td className="num right">{n}</td>
                    </tr>
                  ))}
                  <tr>
                    <td colSpan={2}><strong>Independent localities</strong></td>
                    <td className="num right"><strong>{flag.distinct_sellers}</strong></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h2>Measure</h2>
            <div className="body">
              <dl className="kv">
                <dt>{flag.statistic.name.replace(/_/g, ' ')}</dt>
                <dd style={{ fontWeight: 700 }}>{flag.statistic.value}</dd>
                <dt>Threshold</dt><dd>{flag.statistic.threshold}</dd>
                {Object.entries(flag.statistic)
                  .filter(([k]) => !['name', 'value', 'threshold'].includes(k))
                  .map(([k, v]) => (
                    <React.Fragment key={k}>
                      <dt>{k.replace(/_/g, ' ')}</dt><dd>{v}</dd>
                    </React.Fragment>
                  ))}
              </dl>
              <p className="small muted" style={{ marginTop: 14, marginBottom: 0 }}>
                {c?.measure?.explanation}
              </p>
            </div>
          </div>

          <div className="panel">
            <h2>Peer comparison</h2>
            <div className="body small">
              {flag.peers_in_band.length ? (
                <>
                  <p style={{ marginTop: 0 }}>
                    These locations stayed inside their expected range over the same window:
                  </p>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {flag.peers_in_band.map((p) => <li key={p}>{prettyLocation(p)}</li>)}
                  </ul>
                  <p className="muted" style={{ marginBottom: 0 }}>
                    A district-wide supply shock would have moved these too.
                  </p>
                </>
              ) : (
                <p className="muted" style={{ margin: 0 }}>No peer location stayed in-band.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
