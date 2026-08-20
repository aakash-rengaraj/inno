import React, { useEffect, useMemo, useState } from 'react'
import { inr, pct, prettyItem, shortDate } from './data.js'

// The frame is fixed. No pan, no zoom, no scroll: the map is the jurisdiction,
// and a map you can drag off its own district invites reading a neighbouring
// district's prices as this district's problem. Everything is drawn into one
// viewBox that always fits its container.
const W = 1000
const H = 372          // 2.7:1, the aspect of the frame at this latitude

// Diverging scale centred on the modelled band, saturating at +/-30%. Beyond
// that the colour stops changing: the point is "well outside", not a contest
// over which cell is worst.
const CAP = 0.30
const MIN_PX = 7       // a 150 m cell is ~5 px at this scale; too small to hit

// Drawing order matters: water under roads under rail, all of it under the
// cells. A road drawn over a hot cell reads as a boundary of it.
const BASE_LAYERS = ['waterbody', 'water', 'street', 'minor', 'major', 'rail']

function colour(dev) {
  const t = Math.max(-1, Math.min(1, dev / CAP))
  if (t >= 0) {
    // pale slate -> amber -> red
    const r = Math.round(120 + t * 135)
    const g = Math.round(140 - t * 105)
    const b = Math.round(160 - t * 130)
    return `rgb(${r},${g},${b})`
  }
  const u = -t
  return `rgb(${Math.round(120 - u * 50)},${Math.round(140 + u * 40)},${Math.round(160 + u * 60)})`
}

export default function Heatmap({ heatmap }) {
  const [item, setItem] = useState(null)
  const [hover, setHover] = useState(null)
  const [base, setBase] = useState(null)

  // 313 kB of OSM geometry, fetched only when the map is opened rather than on
  // every console boot. Its absence is not an error: the frame still draws.
  useEffect(() => {
    let dead = false
    fetch(new URL('data/basemap.json', document.baseURI))
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => { if (!dead) setBase(b) })
      .catch(() => {})
    return () => { dead = true }
  }, [])

  const grid = heatmap
  const cells = useMemo(
    () => (grid?.cells || []).filter((c) => !item || c.item === item),
    [grid, item],
  )

  if (!grid || !grid.frame) {
    return (
      <div className="panel">
        <p className="muted">
          No heatmap in this build. Run <code>python -m pipeline.build</code> to generate it.
        </p>
      </div>
    )
  }

  const f = grid.frame
  const x = (lng) => ((lng - f.lng_min) / (f.lng_max - f.lng_min)) * W
  const y = (lat) => (1 - (lat - f.lat_min) / (f.lat_max - f.lat_min)) * H

  // one cell, in viewBox units
  const cw = Math.max(MIN_PX, (grid.cell_m / 108400) / (f.lng_max - f.lng_min) * W)
  const ch = Math.max(MIN_PX, (grid.cell_m / 110574) / (f.lat_max - f.lat_min) * H)

  const maxN = Math.max(1, ...cells.map((c) => c.n))
  const opacity = (n) => 0.35 + 0.65 * Math.min(1, Math.log1p(n) / Math.log1p(maxN))

  // scale bar: 5 km
  const kmPx = (5000 / 108400) / (f.lng_max - f.lng_min) * W

  return (
    <div className="panel heatmap">
      <div className="hm-head">
        <div>
          <h2>Where reported prices sit against the band</h2>
          <p className="muted small">
            {grid.totals.reports_shown?.toLocaleString('en-IN')} field reports binned to{' '}
            {grid.cell_m} m cells over Vellore district. Colour is the median gap between what
            reporters paid and the middle of the modelled band {'—'} not how many people
            reported. Cells with fewer than {grid.min_reports} reports are not drawn.
          </p>
        </div>
        <div className="hm-items">
          <button className={!item ? 'on' : ''} onClick={() => setItem(null)}>All</button>
          {grid.items.map((it) => (
            <button key={it} className={item === it ? 'on' : ''} onClick={() => setItem(it)}>
              {prettyItem(it)}
            </button>
          ))}
        </div>
      </div>

      <div className="hm-frame">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img"
             aria-label="Price deviation by report location across Vellore district">
          <rect x="0" y="0" width={W} height={H} className="hm-bg" />

          {base && (
            <g className="hm-base" clipPath="url(#hm-clip)">
              {BASE_LAYERS.map((name) => (
                base.paths[name]
                  ? <path key={name} className={`hm-${name}`} d={base.paths[name]} />
                  : null
              ))}
            </g>
          )}

          <defs>
            <clipPath id="hm-clip">
              <rect x="0" y="0" width={W} height={H} />
            </clipPath>
          </defs>

          {grid.places.map((p) => (
            <circle key={p.id} className={`hm-place ${p.kind}`}
                    cx={x(p.lng)} cy={y(p.lat)} r={p.kind === 'market' ? 4 : 3} />
          ))}

          {cells.map((c, i) => (
            <rect key={i} className="hm-cell"
                  x={x(c.lng) - cw / 2} y={y(c.lat) - ch / 2} width={cw} height={ch}
                  fill={colour(c.deviation)} opacity={opacity(c.n)}
                  onMouseEnter={() => setHover(c)} onMouseLeave={() => setHover(null)} />
          ))}

          {/* labels last: drawn under the cells they name, they were unreadable */}
          {grid.places.map((p) => (
            <text key={p.id} className={`hm-label ${p.kind}`}
                  x={x(p.lng) + 7} y={y(p.lat) + 4}>{p.label}</text>
          ))}

          {hover && (
            <rect className="hm-ring" x={x(hover.lng) - cw / 2 - 2} y={y(hover.lat) - ch / 2 - 2}
                  width={cw + 4} height={ch + 4} />
          )}

          <g className="hm-scale" transform={`translate(24 ${H - 22})`}>
            <line x1="0" y1="0" x2={kmPx} y2="0" />
            <line x1="0" y1="-4" x2="0" y2="4" />
            <line x1={kmPx} y1="-4" x2={kmPx} y2="4" />
            <text x={kmPx / 2} y="-8">5 km</text>
          </g>

          {base && (
            <text className="hm-attrib" x={W - 8} y={H - 8}>{base.attribution}</text>
          )}
        </svg>

        <div className="hm-tip" aria-live="polite">
          {hover ? (
            <>
              <strong>{prettyItem(hover.item)}</strong>
              {/* `pct` takes a percentage, and deviation is a fraction. Colour
                  keys off band_gap, not the sign: +0.3% is inside the band and
                  must not read as red. */}
              <span className={hover.band_gap > 0 ? 'over' : 'under'}>
                {pct(hover.deviation * 100, 1)} vs band midpoint
              </span>
              <span className="mono">{inr(hover.median_price)} median</span>
              <span className="muted">
                {hover.n} reports · {hover.localities} localit{hover.localities === 1 ? 'y' : 'ies'}
                {' · '}{hover.above_band} above band
              </span>
              <span className="muted">{shortDate(hover.first)} {'–'} {shortDate(hover.last)}</span>
            </>
          ) : (
            <span className="muted">Hover a cell for the reports behind it.</span>
          )}
        </div>
      </div>

      <div className="hm-legend">
        <span className="muted small">At or below band</span>
        <div className="hm-ramp">
          {Array.from({ length: 21 }, (_, i) => {
            const d = -CAP + (i / 20) * (2 * CAP)
            return <i key={i} style={{ background: colour(d) }} />
          })}
        </div>
        <span className="muted small">{'≥'} +30% over band</span>
        <span className="spacer" />
        <span className="muted small">
          Opacity is report volume. {grid.suppressed_cells} cell
          {grid.suppressed_cells === 1 ? '' : 's'} withheld below the evidence floor.
        </span>
      </div>

      <p className="muted small hm-caveat">
        A hot cell is a place to send an inspector, not a finding against any business.
        Field reports are pseudonymised to a {grid.cell_m} m cell {'—'} the same radius the
        generaliser merges reporting points at {'—'} so a cell is a street, never a shop.
      </p>
    </div>
  )
}
