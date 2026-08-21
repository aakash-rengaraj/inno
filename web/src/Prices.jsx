import React, { useEffect, useMemo, useState } from 'react'
import { apiGet } from './api.js'
import { inr, shortDate } from './data.js'
import { ITEMS_TA } from './items.ta.js'

// Public. One row per commodity: low, typical, high. Nothing else — no market
// names, no modelled band, no flags. See pipeline/prices.py for why each of
// those is absent rather than merely unrendered.
export default function Prices({ online, onBack, lang = 'en', t = (k) => k }) {
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
    // Carry the English name alongside the Tamil one and search both: a shopper
    // typing "tomato" on the Tamil page should still find தக்காளி, and an
    // untranslated item is findable by the only name it has.
    const named = data.items.map((i) => ({
      ...i,
      name: (lang === 'ta' && ITEMS_TA[i.item]) || i.label,
      alt: lang === 'ta' && ITEMS_TA[i.item] ? i.label : '',
    }))
    const needle = q.trim().toLowerCase()
    if (!needle) return named
    return named.filter((i) => `${i.name} ${i.alt}`.toLowerCase().includes(needle))
  }, [data, q, lang])

  if (error) return <div className="panel"><div className="body muted">{t('unavailable')}</div></div>
  if (!data) return <div className="panel"><div className="body muted">{t('loading')}</div></div>

  return (
    <div className="panel prices">
      <div className="pr-head">
        <div>
          <h2>{t('pricesTitle')}, {shortDate(data.date, lang === 'ta' ? 'ta-IN' : 'en-IN')}</h2>
          <p className="muted small">{t('pricesNote')}</p>
        </div>
        <input className="pr-search" type="search" value={q} placeholder={t('findItem')}
               onChange={(e) => setQ(e.target.value)} aria-label={t('findItem')} />
      </div>

      {/* Eggs and fares before the commodity table: both are things a household
          buys daily and can check against a published rate, which is the whole
          point of the page. Each states its reference beside what people pay --
          the gap between the two is the reader's to judge, and neither block
          calls that gap anything. */}
      {data.eggs && (
        <section className="pr-block">
          <h3>{t('eggsTitle')}</h3>
          <div className="pr-pair">
            <div>
              <span className="label">{t('eggsDeclared')}</span>
              <span className="pr-big mono">{inr(data.eggs.declared)}</span>
              <span className="muted small"> {t('perPiece')}</span>
            </div>
            <div>
              <span className="label">{t('eggsShops')}</span>
              {data.eggs.observed ? (
                <span className="pr-big mono">
                  {inr(data.eggs.observed.low)} – {inr(data.eggs.observed.high)}
                </span>
              ) : <span className="muted small">{t('notEnough')}</span>}
            </div>
          </div>
          <p className="muted small pr-block-note">{t('eggsNote')}</p>
        </section>
      )}

      {data.autos && (
        <section className="pr-block">
          <h3>{t('autosTitle')}</h3>
          <div className="pr-scroll">
            <table className="pr-table pr-fares">
              <thead>
                <tr>
                  <th>{t('distance')}</th>
                  <th className="num">{t('autosNotified')}</th>
                  <th className="num">{t('autosPaid')}</th>
                </tr>
              </thead>
              <tbody>
                {data.autos.rows.map((r) => (
                  <tr key={r.km}>
                    <td className="mono">{r.km} km</td>
                    <td className="num mono strong">{inr(r.notified, 0)}</td>
                    <td className="num mono">
                      {r.observed
                        ? `${inr(r.observed.low, 0)} – ${inr(r.observed.high, 0)}`
                        : <span className="muted">{t('notEnough')}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small pr-block-note">{t('autosNote')}</p>
        </section>
      )}

      <h3 className="pr-block-head">{t('commoditiesTitle')}</h3>
      <p className="muted small pr-block-note" style={{ margin: '0 0 var(--s3)' }}>
        {t('commoditiesNote')}
      </p>
      <div className="pr-scroll">
      <table className="pr-table">
        <thead>
          <tr>
            <th>{t('commodity')}</th>
            <th className="num">{t('lowest')}</th>
            <th className="num">{t('typical')}</th>
            <th className="num">{t('highest')}</th>
            <th className="num">{t('mandis')}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.item}>
              <td>
                {i.name}
                {i.alt && <span className="pr-alt">{i.alt}</span>}
              </td>
              <td className="num mono">{inr(i.low, 0)}</td>
              <td className="num mono strong">{inr(i.typical, 0)}</td>
              <td className="num mono">{inr(i.high, 0)}</td>
              <td className="num muted">{i.markets}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>

      {items.length === 0 && <p className="muted body">{t('noMatch')} {`"${q}"`}</p>}

      <p className="muted small pr-note">{t('pricesSource')}</p>

      {onBack && <button onClick={onBack}>{t('back')}</button>}
    </div>
  )
}
