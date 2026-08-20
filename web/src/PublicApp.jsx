import React, { useEffect, useState } from 'react'
import { apiAvailable, apiGet } from './api.js'
import { loadAll } from './data.js'
import Landing from './Landing.jsx'
import ReportForm from './ReportForm.jsx'

// The public surface. It is a separate build with a separate entry point, and
// its bundle carries only the aggregate counts in meta.json — never the flag
// queue, the case files or the charts. Flagged locations are an enforcement
// work product; a citizen page must not be able to name them, and this one
// cannot, because the data is not in it.
export default function PublicApp() {
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

  if (!meta) return <div style={{ padding: 32 }} className="muted">Loading…</div>

  if (view === 'report') {
    return (
      <div className="app">
        <header className="topbar">
          <h1 onClick={() => setView('landing')} style={{ cursor: 'pointer' }}>Price Review</h1>
          <span className="sub">Vellore District</span>
          <span className="spacer" />
          <span className="sub mono">data through {meta.data_through}</span>
        </header>
        <main>
          <ReportForm online={online} meta={meta} onBack={() => setView('landing')} />
        </main>
      </div>
    )
  }

  return <Landing meta={meta} onReport={() => setView('report')} />
}
