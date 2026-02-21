import { useEffect, useState } from 'react'

export function IntegrityScoreGauge({ score = 0, riskLevel = 'LOW', size = 180 }) {
  const [display, setDisplay] = useState(0)

  const RISK = {
    LOW:    { color: 'var(--green)', label: 'LOW RISK',    glow: 'rgba(0,229,160,0.35)' },
    MEDIUM: { color: 'var(--amber)', label: 'MEDIUM RISK', glow: 'rgba(255,184,48,0.35)' },
    HIGH:   { color: 'var(--red)',   label: 'HIGH RISK',   glow: 'rgba(255,71,87,0.35)'  },
  }
  const cfg = RISK[riskLevel] || RISK.LOW

  useEffect(() => {
    let frame
    const start = performance.now()
    const from = display
    const to = score
    const dur = 1100
    const animate = (now) => {
      const p = Math.min((now - start) / dur, 1)
      const eased = 1 - Math.pow(1 - p, 4)
      setDisplay(from + (to - from) * eased)
      if (p < 1) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [score])

  const cx = size / 2, cy = size / 2
  const r = size / 2 - 18
  const circ = 2 * Math.PI * r
  const arc = circ * 0.75
  const fill = (display / 1) * arc
  const rot = -225

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      <div style={{ position: 'relative', width: size, height: size * 0.82 }}>
        <svg width={size} height={size * 0.9} style={{ overflow: 'visible' }}>
          <defs>
            <filter id="glow-gauge">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          {/* Track */}
          <circle cx={cx} cy={cy} r={r} fill="none"
            stroke="rgba(255,255,255,0.06)" strokeWidth={10}
            strokeDasharray={`${arc} ${circ}`} strokeLinecap="round"
            transform={`rotate(${rot} ${cx} ${cy})`}
          />
          {/* Fill */}
          <circle cx={cx} cy={cy} r={r} fill="none"
            stroke={cfg.color} strokeWidth={10}
            strokeDasharray={`${fill} ${circ}`} strokeLinecap="round"
            transform={`rotate(${rot} ${cx} ${cy})`}
            filter="url(#glow-gauge)"
            style={{ transition: 'stroke 0.4s ease' }}
          />
          {/* Center score */}
          <text x={cx} y={cy + 8} textAnchor="middle"
            style={{ fontFamily: 'Syne, sans-serif', fontSize: size * 0.22, fontWeight: 700, fill: cfg.color }}>
            {Math.round(display * 100)}
          </text>
          <text x={cx} y={cy + 26} textAnchor="middle"
            style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, fill: 'var(--slate-text)', letterSpacing: 2 }}>
            RISK SCORE
          </text>
        </svg>
      </div>
      <div style={{
        fontFamily: 'DM Mono, monospace', fontSize: 11, letterSpacing: 3, fontWeight: 500,
        color: cfg.color, padding: '5px 14px', borderRadius: 4,
        background: cfg.glow.replace('0.35', '0.1'),
        border: `1px solid ${cfg.glow.replace('0.35', '0.25')}`,
      }}>
        {cfg.label}
      </div>
    </div>
  )
}
