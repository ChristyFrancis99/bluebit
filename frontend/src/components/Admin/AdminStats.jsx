import { useEffect, useState } from 'react'
import { adminApi } from '../../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export function AdminStats() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    adminApi.getStats().then(setStats).catch(() => {})
  }, [])

  if (!stats) return null

  const riskData = [
    { name: 'LOW',    value: stats.reports?.by_risk?.LOW ?? 0,    color: 'var(--green)' },
    { name: 'MEDIUM', value: stats.reports?.by_risk?.MEDIUM ?? 0, color: 'var(--amber)' },
    { name: 'HIGH',   value: stats.reports?.by_risk?.HIGH ?? 0,   color: 'var(--red)' },
  ]

  const avgScore = stats.reports?.average_score ?? 0

  return (
    <div className="glass" style={{ borderRadius: 12, padding: 28 }}>
      <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 17, fontWeight: 700, marginBottom: 20 }}>
        Platform Statistics
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 28 }}>
        {[
          { label: 'TOTAL SUBMISSIONS', value: stats.submissions?.total ?? 0, color: 'var(--cyan)' },
          { label: 'AVG RISK SCORE', value: `${Math.round(avgScore * 100)}%`, color: avgScore >= 0.65 ? 'var(--red)' : avgScore >= 0.35 ? 'var(--amber)' : 'var(--green)' },
          { label: 'HIGH RISK', value: stats.reports?.by_risk?.HIGH ?? 0, color: 'var(--red)' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 8 }}>{label}</div>
            <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 26, fontWeight: 800, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Risk distribution chart */}
      <div>
        <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 14 }}>
          RISK DISTRIBUTION
        </div>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={riskData} barSize={40}>
            <XAxis dataKey="name" tick={{ fontFamily: 'DM Mono, monospace', fontSize: 10, fill: 'var(--slate-text)', letterSpacing: 2 }} axisLine={false} tickLine={false} />
            <YAxis hide />
            <Tooltip
              contentStyle={{ background: 'var(--navy-2)', border: '1px solid var(--border)', borderRadius: 8, fontFamily: 'DM Mono, monospace', fontSize: 12 }}
              labelStyle={{ color: '#e2eaf7' }}
              itemStyle={{ color: 'var(--slate-text)' }}
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {riskData.map((entry, i) => <Cell key={i} fill={entry.color} opacity={0.85} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
