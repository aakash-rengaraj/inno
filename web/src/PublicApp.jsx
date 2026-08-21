import React, { useEffect, useState } from 'react'
import { apiAvailable, apiGet } from './api.js'
import { loadAll } from './data.js'
import Landing from './Landing.jsx'
import { LANGS, useLang } from './i18n.js'
import Prices from './Prices.jsx'
import ReportForm from './ReportForm.jsx'

// The public surface. It is a separate build with a separate entry point, and
// its bundle carries only the aggregate counts in meta.json — never the flag
// queue, the case files or the charts. Flagged locations are an enforcement
// work product; a citizen page must not be able to name them, and this one
// cannot, because the data is not in it.
export default function PublicApp() {
  const { lang, setLang, t } = useLang()
  const [meta, setMeta] = useState(null)
  const [view, setView] = useState('landing')
  const [online, setOnline] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (await apiAvailable()) {
        try {
          const live = await apiGet('/api/public/meta')
          if (!cancelled) { setMeta(live); setOnline(true); return }
        } catch { /* fall through to the embedded copy */ }
      }
      const db = await loadAll(['meta'])
      if (!cancelled) setMeta(db.meta)
    })()
    return () => { cancelled = true }
  }, [])

  const langPicker = (
    <div className="langpick" role="group" aria-label="Language">
      {LANGS.map((l) => (
        <button key={l.id} className={lang === l.id ? 'on' : ''}
                lang={l.id} onClick={() => setLang(l.id)}>{l.label}</button>
      ))}
    </div>
  )

  if (!meta) return <div style={{ padding: 32 }} className="muted">{t('loading')}</div>

  if (view === 'report' || view === 'prices') {
    return (
      <div className="app">
        <header className="topbar">
          <h1 onClick={() => setView('landing')} style={{ cursor: 'pointer' }}>{t('title')}</h1>
          <nav className="topnav">
            <button className={view === 'prices' ? 'on' : ''}
                    onClick={() => setView('prices')}>{t('seePrices')}</button>
            <button className={view === 'report' ? 'on' : ''}
                    onClick={() => setView('report')}>{t('reportPrice')}</button>
          </nav>
          <span className="spacer" />
          {langPicker}
        </header>
        <main key={view}>
          {view === 'report'
            ? <ReportForm online={online} meta={meta} lang={lang} t={t}
                          onBack={() => setView('landing')} />
            : <Prices online={online} lang={lang} t={t} onBack={() => setView('landing')} />}
        </main>
      </div>
    )
  }

  return (
    <>
      <div className="lp-masthead">
        <div className="lp-masthead-inner">
          <span className="lp-mast-name">{t('office')}</span>
          <span className="lp-mast-sub">{t('district')}</span>
          <span className="spacer" style={{ flex: 1 }} />
          {langPicker}
        </div>
      </div>
      <Landing meta={meta} t={t} onReport={() => setView('report')}
               onPrices={() => setView('prices')} />
    </>
  )
}
