import { useState } from 'react'
import { ChevronDown, Brain, Search, User, Camera, AlertTriangle } from 'lucide-react'

const META = {
  ai_detection:   { label: 'AI Detection',    icon: Brain,  desc: 'RoBERTa transformer model' },
  plagiarism:     { label: 'Plagiarism',       icon: Search, desc: 'MinHash LSH similarity' },
  writing_profile:{ label: 'Writing Profile',  icon: User,   desc: 'Stylometric deviation' },
  proctoring:     { label: 'Proctoring',       icon: Camera, desc: 'Behavioral analysis' },
}

function riskOf(score) {
  if (score >= 0.65) return { color: 'var(--red)',   bg: 'rgba(255,71,87,0.08)',   border: 'rgba(255,71,87,0.2)' }
  if (score >= 0.35) return { color: 'var(--amber)', bg: 'rgba(255,184,48,0.08)',  border: 'rgba(255,184,48,0.2)' }
  return              { color: 'var(--green)',  bg: 'rgba(0,229,160,0.08)',  border: 'rgba(0,229,160,0.2)' }
}

export function ModuleResultCard({ moduleId, data, loading = false }) {
  const [open, setOpen] = useState(false)
  const meta = META[moduleId] || { label: moduleId, icon: Brain, desc: '' }
  const Icon = meta.icon
  const score = data?.score ?? 0
  const risk = riskOf(score)

  return (
    <div className="module-card" style={{
      borderRadius: 10, border: '1px solid var(--border)',
      background: 'rgba(15,23,41,0.6)', overflow: 'hidden',
      transition: 'border-color 0.2s, background 0.2s',
    }}>
      <div
        onClick={() => data && setOpen(o => !o)}
        style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px', cursor: data ? 'pointer' : 'default' }}
      >
        {/* Icon */}
        <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(255,255,255,0.04)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Icon size={16} style={{ color: loading ? 'var(--slate-text)' : risk.color }} />
        </div>

        {/* Label + bar */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 7 }}>
            <span style={{ fontFamily: 'Syne, sans-serif', fontSize: 13, fontWeight: 600, color: '#e2eaf7' }}>
              {meta.label}
            </span>
            {loading ? (
              <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 1 }}>
                SCANNING…
              </span>
            ) : data ? (
              <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 13, fontWeight: 500, color: risk.color }}>
                {Math.round(score * 100)}%
              </span>
            ) : null}
          </div>
          <div style={{ height: 3, borderRadius: 99, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
            {loading ? (
              <div className="shimmer" style={{ height: '100%', borderRadius: 99 }} />
            ) : data ? (
              <div style={{
                height: '100%', borderRadius: 99,
                background: risk.color,
                width: `${score * 100}%`,
                boxShadow: `0 0 8px ${risk.color}`,
                transition: 'width 0.9s cubic-bezier(0.16,1,0.3,1)',
              }} />
            ) : null}
          </div>
        </div>

        {/* Chevron */}
        {data && (
          <ChevronDown size={14} style={{
            color: 'var(--slate-text)', flexShrink: 0,
            transform: open ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s ease',
          }} />
        )}
      </div>

      {/* Evidence panel */}
      {open && data && (
        <div className="animate-fade-in" style={{
          borderTop: '1px solid var(--border)', padding: '14px 16px',
          background: 'rgba(0,0,0,0.2)',
        }}>
          {/* Stats row */}
          <div style={{ display: 'flex', gap: 20, marginBottom: 12 }}>
            {[
              ['Confidence', `${Math.round((data.confidence ?? 0) * 100)}%`],
              ['Weight', data.weight ?? '—'],
              ['Time', `${data.processing_ms ?? 0}ms`],
            ].map(([k, v]) => (
              <div key={k}>
                <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 2 }}>{k}</div>
                <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 12, color: '#e2eaf7', fontWeight: 500 }}>{v}</div>
              </div>
            ))}
          </div>
          <EvidencePanel moduleId={moduleId} evidence={data.evidence} />
        </div>
      )}
    </div>
  )
}

function Tag({ children, color }) {
  return (
    <span style={{
      display: 'inline-block', fontFamily: 'DM Mono, monospace', fontSize: 10,
      padding: '2px 8px', borderRadius: 4,
      background: `${color}15`, border: `1px solid ${color}33`, color,
    }}>{children}</span>
  )
}

function EvidencePanel({ moduleId, evidence }) {
  if (!evidence) return null

  if (moduleId === 'ai_detection') {
    const chunks = evidence.chunk_scores || []
    const flagged = evidence.flagged_segments || []
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {chunks.length > 0 && (
          <div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 6 }}>CHUNK SCORES</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {chunks.map((s, i) => (
                <Tag key={i} color={s >= 0.65 ? 'var(--red)' : s >= 0.35 ? 'var(--amber)' : 'var(--green)'}>
                  {Math.round(s * 100)}%
                </Tag>
              ))}
            </div>
          </div>
        )}
        {flagged.length > 0 && (
          <div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 6 }}>FLAGGED SEGMENTS</div>
            {flagged.slice(0, 3).map((f, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--slate-text)', background: 'rgba(255,71,87,0.06)', border: '1px solid rgba(255,71,87,0.15)', borderRadius: 6, padding: '8px 10px', marginBottom: 4 }}>
                <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--red)', marginRight: 6 }}>#{f.index} {Math.round(f.score * 100)}%</span>
                {f.snippet}
              </div>
            ))}
          </div>
        )}
        {evidence.model_version && (
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'rgba(168,184,216,0.5)' }}>
            model: {evidence.model_version}
          </div>
        )}
      </div>
    )
  }

  if (moduleId === 'plagiarism') {
    const matches = evidence.matches || []
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {matches.length > 0 ? (
          <div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 6 }}>MATCHES FOUND ({matches.length})</div>
            {matches.slice(0, 5).map((m, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '6px 10px', borderRadius: 6, background: 'rgba(255,184,48,0.05)', border: '1px solid rgba(255,184,48,0.12)', marginBottom: 3 }}>
                <span style={{ fontFamily: 'DM Mono, monospace', color: 'var(--slate-text)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.doc_id?.slice(0, 24)}…</span>
                <Tag color="var(--amber)">{Math.round(m.similarity * 100)}%</Tag>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--green)' }}>✓ No external matches found</div>
        )}
        {(evidence.suspicious_phrases || []).length > 0 && (
          <div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 4 }}>SUSPICIOUS PHRASES</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {evidence.suspicious_phrases.map((p, i) => <Tag key={i} color="var(--amber)">{p}</Tag>)}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (moduleId === 'writing_profile') {
    const flagged = evidence.flagged_features || []
    if (evidence.status === 'baseline_created') {
      return <div style={{ fontSize: 12, color: 'var(--cyan)' }}>ℹ First submission — writing baseline established</div>
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 12, color: 'var(--slate-text)' }}>
          deviation from baseline:{' '}
          <span style={{ color: flagged.length > 2 ? 'var(--red)' : 'var(--green)' }}>
            {Math.round((evidence.deviation_score || 0) * 100)}%
          </span>
        </div>
        {flagged.length > 0 && (
          <div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 4 }}>ANOMALOUS FEATURES</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {flagged.map((f, i) => <Tag key={i} color="var(--amber)">{f}</Tag>)}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (moduleId === 'proctoring') {
    const flags = evidence.flags || []
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {[
            ['paste events', evidence.paste_events ?? 0],
            ['tab switches', evidence.tab_switches ?? 0],
            ['focus lost', evidence.focus_lost_count ?? 0],
          ].map(([k, v]) => (
            <div key={k}>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 1, marginBottom: 2 }}>{k}</div>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 13, color: v > 3 ? 'var(--red)' : '#e2eaf7' }}>{v}</div>
            </div>
          ))}
        </div>
        {flags.map((f, i) => (
          <div key={i} style={{ fontSize: 12, color: 'var(--amber)', background: 'rgba(255,184,48,0.06)', border: '1px solid rgba(255,184,48,0.15)', borderRadius: 6, padding: '6px 10px' }}>
            <AlertTriangle size={11} style={{ marginRight: 6, display: 'inline' }} />{f}
          </div>
        ))}
      </div>
    )
  }

  return null
}
