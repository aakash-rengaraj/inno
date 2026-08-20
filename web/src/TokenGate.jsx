import React, { useState } from 'react'
import { ApiError, apiGet, setToken } from './api.js'

// Not user accounts — one shared passphrase, so the citizen surface and the
// enforcement surface are not equally open now that the console names flagged
// locations over the network.
export default function TokenGate({ onUnlocked }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    setToken(value.trim())
    try {
      await apiGet('/api/meta', true)
      onUnlocked()
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401
        ? 'That passphrase was not accepted.'
        : 'Could not reach the review service.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="gate">
      <form className="gate-card" onSubmit={submit}>
        <div className="lp-eyebrow">Office of the District Supply Officer</div>
        <h1 className="gate-title">Enforcement console</h1>
        <p className="small muted" style={{ marginTop: 0 }}>
          This console names locations flagged for investigation. Access is restricted
          to authorised staff.
        </p>
        <label className="gate-field">
          <span className="label">Passphrase</span>
          <input type="password" value={value} autoFocus autoComplete="off"
                 onChange={(e) => setValue(e.target.value)} placeholder="••••••••" />
        </label>
        {error && <div className="small rp-warn">{error}</div>}
        <button className="primary" type="submit" disabled={!value.trim() || busy}>
          {busy ? 'Checking…' : 'Enter console'}
        </button>
      </form>
    </div>
  )
}
