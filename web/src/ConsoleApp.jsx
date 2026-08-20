import React, { useCallback, useEffect, useState } from 'react'
import { apiAvailable, apiGet, clearToken, getToken } from './api.js'
import { loadAll, setItemLabels } from './data.js'
import TokenGate from './TokenGate.jsx'
import ActionBoard from './ActionBoard.jsx'
import CaseFile from './CaseFile.jsx'
import FlagDetail from './FlagDetail.jsx'
import Heatmap from './Heatmap.jsx'
import Queue from './Queue.jsx'
import Reports from './Reports.jsx'

const CONSOLE_VIEWS = ['queue', 'map', 'board', 'detail']

export default function ConsoleApp() {
  const [db, setDb] = useState(null)
  const [selected, setSelected] = useState(null)
  const [view, setView] = useState('queue')
  const [mode, setMode] = useState('checking')   // checking | gate | live | static

  const loadLive = useCallback(async () => {
    const [queue, flags, cases, charts, meta, heatmap] = await Promise.all([
      apiGet('/api/queue', true), apiGet('/api/flags', true), apiGet('/api/cases', true),
      apiGet('/api/charts', true), apiGet('/api/meta', true), apiGet('/api/heatmap', true),
    ])
    setItemLabels(meta.item_labels)
    setDb({ queue, flags, cases, charts, meta, heatmap })
  }, [])

  const boot = useCallback(async () => {
    if (await apiAvailable()) {
      if (!getToken()) { setMode('gate'); return }
      try { await loadLive(); setMode('live'); return }
      catch { clearToken(); setMode('gate'); return }
    }
    // no server: fall back to the artifacts built into the page
    const local = await loadAll()
    setItemLabels(local.meta?.item_labels)
    setDb(local)
    setMode('static')
  }, [loadLive])

  useEffect(() => { boot() }, [boot])

  if (mode === 'gate') {
    return <TokenGate onUnlocked={async () => { await loadLive(); setMode('live') }} />
  }
  if (!db) return <div style={{ padding: 32 }} className="muted">Loading case data…</div>

  const flag = db.queue.find((f) => f.flag_id === selected) || null
  const open = (id) => { setSelected(id); setView('detail') }

  if (view === 'case' && flag) {
    return <CaseFile caseFile={db.cases[flag.flag_id]} live={mode === 'live'}
                     onBack={() => setView('detail')} />
  }

  const inConsole = CONSOLE_VIEWS.includes(view)

  return (
    <div className="app">
      <header className="topbar">
        <h1 onClick={() => setView('queue')} style={{ cursor: 'pointer' }}>Price Review</h1>
        <span className="sub">Vellore District · Supply &amp; Enforcement</span>
        <nav className="topnav">
          {[['queue', 'Queue'], ['map', 'Map'], ['board', 'Action board'],
            ...(mode === 'live' ? [['reports', 'Citizen reports']] : [])]
            .map(([v, label]) => (
              <button key={v} className={view === v ? 'on' : ''}
                      onClick={() => setView(v)}>{label}</button>
            ))}
        </nav>
        <span className="spacer" />
        <span className="sub mono">
          data through {db.meta.data_through} · {db.meta.observations.toLocaleString('en-IN')} observations
        </span>
        <span className={`conn ${mode}`} title={mode === 'live'
          ? 'Connected to the review service' : 'Reading the build shipped with this page'}>
          {mode === 'live' ? 'Live' : 'Static build'}
        </span>
      </header>

      {inConsole && (
        <div className="framing">
          <div className="line">
            <strong>{db.meta.locations_monitored}</strong> locations monitored,{' '}
            <strong>{db.meta.inspections ?? db.meta.flags_in_queue}</strong> flagged for
            inspection — here are the {db.meta.inspections ?? db.meta.flags_in_queue}.
            {db.meta.inspections != null && (
              <span className="muted small" style={{ marginLeft: 8 }}>
                {db.meta.flags_in_queue} findings in total
              </span>
            )}
          </div>
          <span className="spacer" style={{ flex: 1 }} />
          {db.meta.flags_excluded_evidence_floor > 0 && (
            <div className="small muted">
              {db.meta.flags_excluded_evidence_floor} pattern
              {db.meta.flags_excluded_evidence_floor > 1 ? 's' : ''} withheld — evidence floor not met
            </div>
          )}
        </div>
      )}

      <main>
        {view === 'queue' && <Queue db={db} onOpen={open} />}
        {view === 'map' && <Heatmap heatmap={db.heatmap} />}
        {view === 'board' && <ActionBoard db={db} onOpen={open} live={mode === 'live'} />}
        {view === 'reports' && <Reports />}
        {view === 'detail' && (
          <FlagDetail db={db} flag={flag} onBack={() => setView('queue')}
                      onCase={() => setView('case')} />
        )}
      </main>
    </div>
  )
}
