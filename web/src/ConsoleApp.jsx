import React, { useCallback, useEffect, useState } from 'react'
import { apiAvailable, apiGet, clearToken, getToken } from './api.js'
import { loadAll, setItemLabels } from './data.js'
import TokenGate from './TokenGate.jsx'
import ActionBoard from './ActionBoard.jsx'
import CaseFile from './CaseFile.jsx'
import FlagDetail from './FlagDetail.jsx'
import Heatmap from './Heatmap.jsx'
import CaseFiles from './CaseFiles.jsx'
import Queue from './Queue.jsx'
import Reports from './Reports.jsx'

const CONSOLE_VIEWS = ['queue', 'map', 'board', 'cases', 'detail']

export default function ConsoleApp() {
  const [db, setDb] = useState(null)
  const [selected, setSelected] = useState(null)
  const [view, setView] = useState('queue')
  // where 'Back' returns to: the case file is reachable from the flag
  // detail and from the case-file list, and landing on the wrong one is
  // disorienting mid-demo.
  const [caseFrom, setCaseFrom] = useState('detail')
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
  const signOut = () => { clearToken(); setDb(null); setSelected(null); setMode('gate') }
  const open = (id) => { setSelected(id); setView('detail') }
  const openCase = (id) => { setSelected(id); setCaseFrom('cases'); setView('case') }

  if (view === 'case' && flag) {
    return <CaseFile caseFile={db.cases[flag.flag_id]} live={mode === 'live'}
                     onBack={() => setView(caseFrom)} />
  }

  const inConsole = CONSOLE_VIEWS.includes(view)

  return (
    <div className="app">
      {/* Two rows, as an administrative system is normally laid out: the office
          it belongs to on top, what you can do with it underneath. Navigation
          was competing with the masthead for the same line, and the data-through
          line was taking width from the tabs to say something nobody navigates by. */}
      <header className="topbar">
        <h1 onClick={() => setView('queue')} style={{ cursor: 'pointer' }}>FairMark</h1>
        <span className="sub">Vellore District &middot; Supply &amp; Enforcement</span>
        <span className="spacer" />
        <span className="chip mono" title={mode === 'live'
          ? 'Connected to the review service'
          : 'Reading the build shipped with this page'}>
          {mode === 'live' ? 'console' : 'static build'}
        </span>
        {mode === 'live' && (
          <button className="ghost" onClick={signOut}>Sign out</button>
        )}
      </header>

      <nav className="subnav">
        {[['queue', 'Queue'], ['map', 'Map'], ['board', 'Action board'],
          ['cases', 'Case files'],
          ...(mode === 'live' ? [['reports', 'Citizen reports']] : [])]
          .map(([v, label]) => (
            <button key={v} className={view === v ? 'on' : ''}
                    onClick={() => { setSelected(null); setView(v) }}>{label}</button>
          ))}
        <span className="spacer" />
        <span className="subnav-meta mono">
          data through {db.meta.data_through} &middot;{' '}
          {db.meta.observations.toLocaleString('en-IN')} observations
        </span>
      </nav>

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

      {/* keyed on the view so React remounts on navigation: without it the
          content swaps in place and the mount animation never runs. The flag
          id is in the key too, so moving between two flags animates as well. */}
      <main key={`${view}:${selected || ''}`}>
        {view === 'queue' && <Queue db={db} onOpen={open} />}
        {view === 'map' && <Heatmap heatmap={db.heatmap} />}
        {view === 'cases' && <CaseFiles db={db} onOpen={openCase} />}
        {view === 'board' && <ActionBoard db={db} onOpen={open} live={mode === 'live'} />}
        {view === 'reports' && <Reports />}
        {view === 'detail' && (
          <FlagDetail db={db} flag={flag} onBack={() => setView('queue')}
                      onCase={() => { setCaseFrom('detail'); setView('case') }} />
        )}
      </main>
    </div>
  )
}
