import React from 'react'
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ResponsiveContainer,
  Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import { shortDate } from './data.js'

const AXIS = { stroke: '#6b7681', fontSize: 11, fontFamily: 'ui-monospace, Menlo, monospace' }
const GRID = '#e3e6e9'
const BAND = '#c9d3da'
const OBSERVED = '#1f3a4d'
const ACCENT = '#a8201a'

const tip = {
  contentStyle: {
    background: '#fff', border: '1px solid #9aa3ad', borderRadius: 2,
    fontSize: 12, fontFamily: 'ui-monospace, Menlo, monospace',
  },
}

/* (a) expected band shaded behind actual, flagged window marked */
export function BandChart({ chart }) {
  const data = chart.daily.map((d) => ({ ...d, range: [d.lo, d.hi] }))
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} tickFormatter={shortDate} minTickGap={40}
               stroke="#9aa3ad" />
        <YAxis tick={AXIS} stroke="#9aa3ad" width={52}
               tickFormatter={(v) => `₹${v.toFixed(0)}`} domain={['auto', 'auto']} />
        <Tooltip {...tip} formatter={(v, n) =>
          Array.isArray(v) ? [`₹${v[0].toFixed(2)} – ₹${v[1].toFixed(2)}`, 'Expected range']
                           : [`₹${Number(v).toFixed(2)}`, n === 'price' ? 'Observed' : n]} />
        <ReferenceArea x1={chart.window.start} x2={chart.window.end}
                       fill={ACCENT} fillOpacity={0.07} stroke={ACCENT}
                       strokeOpacity={0.35} strokeDasharray="3 3" />
        <Area dataKey="range" stroke="none" fill={BAND} fillOpacity={0.75}
              isAnimationActive={false} name="Expected range" />
        <Line dataKey="price" stroke={OBSERVED} strokeWidth={1.6} dot={false}
              isAnimationActive={false} name="Observed" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

/* (b) egg spread: three lines, gap shaded */
export function SpreadChart({ chart }) {
  const data = chart.lines.map((d) => ({
    ...d,
    gap: d.listed != null && d.declared != null ? [d.declared, d.listed] : null,
  }))
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="date" tick={AXIS} tickFormatter={shortDate} minTickGap={40}
               stroke="#9aa3ad" />
        <YAxis tick={AXIS} stroke="#9aa3ad" width={52}
               tickFormatter={(v) => `₹${v.toFixed(1)}`} domain={['auto', 'auto']} />
        <Tooltip {...tip} formatter={(v, n) =>
          Array.isArray(v) ? [`₹${(v[1] - v[0]).toFixed(2)}`, 'Gap over declared']
                           : [`₹${Number(v).toFixed(2)}`, n]} />
        <ReferenceArea x1={chart.window.start} x2={chart.window.end}
                       fill={ACCENT} fillOpacity={0.05} stroke={ACCENT}
                       strokeOpacity={0.3} strokeDasharray="3 3" />
        <Area dataKey="gap" stroke="none" fill={ACCENT} fillOpacity={0.13}
              isAnimationActive={false} name="Gap over declared rate" />
        <Line dataKey="declared" stroke="#2f4858" strokeWidth={1.8} dot={false}
              isAnimationActive={false} name="NECC declared rate" />
        <Line dataKey="listed" stroke={ACCENT} strokeWidth={1.6} dot={false}
              isAnimationActive={false} name="Commercial listings" />
        <Line dataKey="reported" stroke="#6b7681" strokeWidth={1.2} dot={false}
              strokeDasharray="4 3" isAnimationActive={false} name="Field reports" />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} iconType="plainline" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

/* (c) auto quantisation scatter with the gazetted-fare line overlaid */
export function ScatterFareChart({ chart }) {
  const pts = chart.points.map((p) => ({ km: p.km, fare: p.price }))
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart margin={{ top: 8, right: 16, bottom: 34, left: 0 }}>
        <CartesianGrid stroke={GRID} />
        <XAxis type="number" dataKey="km" tick={AXIS} stroke="#9aa3ad"
               domain={[0, 9]} tickFormatter={(v) => `${v} km`}
               label={{ value: 'Trip distance', position: 'insideBottom', offset: -24,
                        fontSize: 11, fill: '#6b7681' }} />
        <YAxis type="number" dataKey="fare" tick={AXIS} stroke="#9aa3ad" width={52}
               tickFormatter={(v) => `₹${v}`} domain={[0, 'auto']} />
        <Tooltip {...tip} cursor={{ strokeDasharray: '3 3' }}
                 formatter={(v, n) => [n === 'km' ? `${v} km` : `₹${Number(v).toFixed(0)}`,
                                        n === 'km' ? 'Distance' : 'Fare']} />
        <Scatter data={pts} fill={ACCENT} fillOpacity={0.42} name="Quoted fare"
                 isAnimationActive={false} />
        <Line data={chart.gazette_line} dataKey="fare" stroke="#2f4858" strokeWidth={2}
              dot={false} isAnimationActive={false} name="Notified fare" type="linear" />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 2 }} iconType="plainline"
                verticalAlign="top" align="right" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

export default function Chart({ chart }) {
  if (!chart) return null
  if (chart.kind === 'spread') return <SpreadChart chart={chart} />
  if (chart.kind === 'scatter') return <ScatterFareChart chart={chart} />
  return <BandChart chart={chart} />
}
