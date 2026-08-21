import React from 'react'

// The public front page. It was carrying the methodology -- a "what is
// compared" table, a four-step account of how a flag is made, two paragraphs of
// caveat -- which is the right material for the README and the wrong material
// for somebody who wants to know what tomatoes cost. Nine sections became four:
// what this is, the two things you can do, how much is being watched, and the
// one caveat that must never be dropped.
//
// That caveat stays. It is the sentence that keeps the page from reading as an
// accusation, and shortening it is as far as it may be taken.
export default function Landing({ meta, onReport, onPrices, t }) {
  return (
    <div className="lp-page">
      <div className="lp">
        <section className="lp-hero">
          <h1 className="lp-title">{t('title')}</h1>
          <p className="lp-lede">{t('lede')}</p>
        </section>

        <section className="lp-cards">
          <button className="lp-card primary" onClick={onPrices}>
            <span className="lp-card-title">{t('seePrices')}</span>
            <span className="lp-card-sub">{t('seePricesSub')}</span>
          </button>
          <button className="lp-card" onClick={onReport}>
            <span className="lp-card-title">{t('reportPrice')}</span>
            <span className="lp-card-sub">{t('reportPriceSub')}</span>
          </button>
        </section>

        <section className="lp-stats">
          <div className="lp-stat">
            <div className="lp-stat-value num">
              {Number(meta.observations).toLocaleString('en-IN')}
            </div>
            <div className="label">{t('statObservations')}</div>
          </div>
          <div className="lp-stat">
            <div className="lp-stat-value num">{meta.locations_monitored}</div>
            <div className="label">{t('statLocations')}</div>
          </div>
          <div className="lp-stat">
            <div className="lp-stat-value num">{meta.flags_in_queue}</div>
            <div className="label">{t('statFlagged')}</div>
          </div>
        </section>

        <p className="lp-caveat">{t('caveat')}</p>

        <footer className="lp-foot">
          <span className="mono small muted">
            {t('dataThrough')} {meta.data_through}
          </span>
        </footer>
      </div>
    </div>
  )
}
