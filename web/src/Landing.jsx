import React from 'react'

const VERTICALS = [
  { v: 'Commodities', ref: 'Agmarknet modal price + arrivals',
    obs: 'Mandi reports, retail field reports' },
  { v: 'Eggs', ref: 'NECC declared daily rate',
    obs: 'Quick-commerce listings, local shop reports' },
  { v: 'Autos', ref: 'TN gazetted fare schedule',
    obs: 'Ride-hailing estimates, street quote reports' },
]

const STEPS = [
  ['Reference rate', 'Every price is compared against a published rate — a mandi report, a declared egg rate, a notified fare schedule. The citation travels with the finding.'],
  ['Expected range', 'A quantile model sets the range a price should sit in, given supply, season and what neighbouring locations are doing.'],
  ['Four measures', 'Dispersion between sellers, correlation against costs versus against neighbours, how long a gap persists, and whether prices land on round numbers.'],
  ['Evidence floor', 'A pattern resting on fewer than three independent sellers is withheld, not published. Thin evidence is not an inspection target.'],
]

export default function Landing({ meta, onReport, onPrices }) {
  return (
    <div className="lp-page">
      {/* A masthead, so the page announces which office it belongs to before it
          says anything else -- the landing page previously opened straight onto
          a headline with no institutional frame. */}
      <div className="lp-masthead">
        <div className="lp-masthead-inner">
          <span className="lp-mast-name">Office of the District Supply Officer</span>
          <span className="lp-mast-sub">Vellore District &middot; Tamil Nadu</span>
        </div>
      </div>

      <div className="lp">
      <section className="lp-hero">
        <h1 className="lp-title">Price Review</h1>
        <p className="lp-lede">
          A screening tool that compares what people are charged against what the
          published rate says they should be charged — and turns the gaps that
          survive scrutiny into case files an officer can act on.
        </p>
        <div className="lp-actions">
          <button className="primary" onClick={onPrices}>See today&apos;s prices</button>
          <button onClick={onReport}>Report a price</button>
        </div>
      </section>

      <section className="lp-quote">
        <blockquote>Competitive prices track costs. Collusive prices track each other.</blockquote>
      </section>

      <section className="lp-stats">
        {[
          ['Observations', meta.observations.toLocaleString('en-IN')],
          ['Locations monitored', meta.locations_monitored],
          ['Flagged for investigation', meta.flags_in_queue],
          ['Withheld — evidence floor', meta.flags_excluded_evidence_floor],
        ].map(([k, v]) => (
          <div className="lp-stat" key={k}>
            <div className="lp-stat-value num">{v}</div>
            <div className="label">{k}</div>
          </div>
        ))}
      </section>

      <section className="lp-section">
        <h2>What is compared</h2>
        <table className="grid">
          <thead>
            <tr><th>Vertical</th><th>Reference rate</th><th>Observed price</th></tr>
          </thead>
          <tbody>
            {VERTICALS.map((r) => (
              <tr key={r.v}>
                <td><strong>{r.v}</strong></td>
                <td className="muted">{r.ref}</td>
                <td className="muted">{r.obs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="lp-section">
        <h2>How a flag is made</h2>
        <ol className="lp-steps">
          {STEPS.map(([h, b]) => (
            <li key={h}>
              <div className="lp-step-head">{h}</div>
              <div className="lp-step-body">{b}</div>
            </li>
          ))}
        </ol>
      </section>

      <section className="lp-section lp-limits">
        <h2>What this does not do</h2>
        <p>
          The system flags patterns <strong>for investigation</strong>. It does not
          establish that any party has set prices unlawfully, and no output of it
          should be read as saying so. Sellers are never named: commercial sources
          are pseudonymised, and field reports identify a ~50m location grid, never
          a trader.
        </p>
        <p>
          A range defined against neighbouring locations cannot detect a pattern that
          moves every location at once. The cost-correlation measure partly covers
          that gap by comparing each seller against the published rate rather than
          against its neighbours.
        </p>
      </section>

      <footer className="lp-foot">
        <span className="mono small muted">
          Data through {meta.data_through} · {meta.sources.join(' · ')}
        </span>
      </footer>
      </div>
    </div>
  )
}
