import React from 'react'
import { apiUrl, getToken } from './api.js'
import { inr, pct } from './data.js'

const Field = ({ label, children, wide }) => (
  <div className={wide ? 'cf-field wide' : 'cf-field'}>
    <div className="cf-field-label">{label}</div>
    <div className="cf-field-value">{children}</div>
  </div>
)

export default function CaseFile({ caseFile: c, onBack, live = false }) {
  if (!c) return null

  // Fetched with the console token, then handed over as a file — the XML is
  // behind the same gate as the case file it describes.
  const downloadXml = async () => {
    const res = await fetch(apiUrl(`/api/cases/${c.flag_id}.xml`),
      { headers: { 'X-Console-Token': getToken() } })
    if (!res.ok) return
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url
    a.download = `${c.flag_id}.xml`
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="cf-page">
      <div className="cf-toolbar no-print">
        <button onClick={onBack}>← Back to flag</button>
        <span style={{ flex: 1 }} />
        {live && (
          <button onClick={downloadXml} title="Schema-valid XML for filing">
            Export XML
          </button>
        )}
        <button className="primary" onClick={() => window.print()}>Print case file</button>
      </div>

      <article className="cf-sheet">
        <header className="cf-head">
          <div className="cf-issuer">
            <div className="cf-issuer-name">Office of the District Supply Officer</div>
            <div className="cf-issuer-sub">Vellore District · Tamil Nadu</div>
          </div>
          <div className="cf-ref">
            <div className="cf-field-label">Reference</div>
            <div className="cf-ref-id">{c.flag_id}</div>
          </div>
        </header>

        <div className="cf-title-block">
          <div className="cf-doctype">Price Observation Record — Flagged for Investigation</div>
          <h1 className="cf-title">{c.title}</h1>
          <div className="cf-finding">{c.finding}</div>
        </div>

        <section className="cf-grid">
          <Field label="Priority">{c.tier_label}</Field>
          <Field label="Observation window">
            {c.window.start} → {c.window.end}
          </Field>
          <Field label="Duration">{c.duration_days} days</Field>
          <Field label="Observations">{c.observed.n}</Field>
        </section>

        <section className="cf-section">
          <h2>1 · Reference rate</h2>
          <div className="cf-rate-row">
            <div className="cf-rate">
              <span className="cf-rate-value">{inr(c.reference.rate)}</span>
              <span className="cf-rate-unit">{c.reference.unit}</span>
            </div>
            <div className="cf-rate-band">
              expected range {inr(c.reference.band[0])} – {inr(c.reference.band[1])}
            </div>
          </div>
          <div className="cf-basis">{c.reference.basis}</div>
          <blockquote className="cf-citation">{c.reference.citation}</blockquote>
        </section>

        <section className="cf-section">
          <h2>2 · Observed</h2>
          <div className="cf-rate-row">
            <div className="cf-rate">
              <span className="cf-rate-value accent">{inr(c.observed.median)}</span>
              <span className="cf-rate-unit">{c.observed.unit} (median)</span>
            </div>
            <div className="cf-rate-band accent">
              {pct(c.observed.pct_vs_reference, 1)} relative to reference rate
            </div>
          </div>
          <table className="cf-table">
            <thead>
              <tr><th>Tier</th><th>Source class</th><th className="right">Observations</th></tr>
            </thead>
            <tbody>
              {c.observed.provenance.map((p) => (
                <tr key={p.tier}>
                  <td>{p.tier}</td><td>{p.label}</td><td className="right num">{p.n}</td>
                </tr>
              ))}
              <tr className="cf-total">
                <td colSpan={2}>Independent localities</td>
                <td className="right num">{c.observed.distinct_localities}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="cf-section">
          <h2>3 · Measure applied</h2>
          <div className="cf-measure">
            <div className="cf-measure-stat">
              <span className="cf-field-label">{c.measure.name.replace(/_/g, ' ')}</span>
              <span className="cf-measure-value">{c.measure.value}</span>
              <span className="cf-measure-thr">threshold {c.measure.threshold}</span>
            </div>
            {Object.entries(c.measure.extra || {}).length > 0 && (
              <ul className="cf-measure-extra">
                {Object.entries(c.measure.extra).map(([k, v]) => (
                  <li key={k}><span>{k.replace(/_/g, ' ')}</span><b className="num">{v}</b></li>
                ))}
              </ul>
            )}
          </div>
          <p className="cf-explain">{c.measure.explanation}</p>
        </section>

        <section className="cf-section">
          <h2>4 · Peer comparison</h2>
          {c.peers_in_band.length ? (
            <p className="cf-body-text">
              Over the same window, the following locations remained inside their expected
              range: <strong>{c.peers_in_band.join(', ')}</strong>. A district-wide supply
              shock would be expected to move these locations as well.
            </p>
          ) : (
            <p className="cf-body-text">No comparable location remained in-band.</p>
          )}
          <p className="cf-body-text">
            Residual standard deviation over the window: <span className="num">{c.residual_sd}</span>.
          </p>
        </section>

        <section className="cf-section">
          <h2>5 · Summary</h2>
          <p className="cf-narrative">{c.narrative}</p>
        </section>

        {c.evidence_floor && (
          <section className="cf-section">
            <h2>Evidence floor</h2>
            <p className="cf-body-text">{c.evidence_floor}</p>
          </section>
        )}

        <footer className="cf-foot">
          <div className="cf-caveat">{c.caveat}</div>
          <div className="cf-sign">
            <div className="cf-sign-line">Reviewing officer</div>
            <div className="cf-sign-line">Date</div>
          </div>
        </footer>
      </article>
    </div>
  )
}
