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
      <div className="fd-head">
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

          {/* The loop, closed. A person who files a report gets a reference
              number and, until now, no way of ever seeing it again. These are
              the reports that are part of *this* finding's evidence -- matched
              on item, location and window, the same test the pipeline applies,
              so it is not a decorative badge. */}
          {flag.citizen_reports?.length > 0 && (
            <div className="panel">
              <h2>Citizen reports in this evidence</h2>
              <div className="body">
                <table className="grid" style={{ fontSize: 12 }}>
                  <tbody>
                    {flag.citizen_reports.slice(0, 8).map((r) => (
                      <tr key={r.reference}>
                        <td className="mono">{r.reference}</td>
                        <td className="num right">{inr(r.price_inr)}</td>
                        <td className="small muted right nowrap">
                          {String(r.submitted_at).slice(0, 10)}
                        </td>
                        {/* whether it falls inside the run the detector measured
                            is a different fact from whether it concerns this
                            market, and both are worth stating */}
                        <td className="small right nowrap">
                          {r.in_window
                            ? <span className="inwin">in window</span>
                            : <span className="muted">outside window</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {flag.citizen_reports.length > 8 && (
                  <p className="small muted" style={{ marginBottom: 0 }}>
                    and {flag.citizen_reports.length - 8} more
                  </p>
                )}
                <p className="small muted" style={{ marginBottom: 0, marginTop: 12 }}>
                  Reports about this market and item. Counted as tier C, the lowest
                  evidence weight &mdash; reports alone cannot put a finding in the
                  queue, which needs three independent localities.
                </p>
              </div>
            </div>
          )}

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
