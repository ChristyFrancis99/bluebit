import { useEffect, useState } from 'react'
import { FileText, Download, RefreshCw, Loader2, ChevronRight } from 'lucide-react'
import { submissionsApi } from '../../api'
import { IntegrityScoreGauge } from './IntegrityScoreGauge'
import { ModuleResultCard } from './ModuleResultCard'

export function SubmissionHistory({ onSelectReport }) {
  const [submissions, setSubmissions] = useState([])
  const [loading, setLoading] = useState(true)
  const [reports, setReports] = useState({})
  const [selected, setSelected] = useState(null)

  const fetch = async () => {
    setLoading(true)
    try {
      const data = await submissionsApi.list({ limit: 30 })
      setSubmissions(data.submissions || [])
      const done = (data.submissions || []).filter(s => s.status === 'done')
      const rMap = {}
      await Promise.all(done.map(async s => {
        try { rMap[s.id] = await submissionsApi.getReport(s.id) } catch {}
      }))
      setReports(rMap)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetch() }, [])

  const riskCls = { LOW: 'risk-low', MEDIUM: 'risk-medium', HIGH: 'risk-high' }

  if (selected) {
    const report = reports[selected.id]
    return (
      <div className="animate-fade-up" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Back */}
        <button onClick={() => setSelected(null)} style={{
          display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none',
          color: 'var(--slate-text)', cursor: 'pointer', fontSize: 13, fontFamily: 'DM Mono, monospace',
          letterSpacing: 1, padding: 0,
        }}>
          ← BACK TO HISTORY
        </button>

        {/* Report header card */}
        <div className="glass" style={{ borderRadius: 12, padding: 24, display: 'flex', gap: 24, alignItems: 'center' }}>
          <IntegrityScoreGauge score={report?.integrity_score ?? 0} riskLevel={report?.risk_level ?? 'LOW'} size={140} />
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 18, fontWeight: 700, marginBottom: 6 }}>
              {selected.original_filename}
            </div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 1, marginBottom: 12 }}>
              {selected.id?.slice(0, 16)}… · {selected.word_count?.toLocaleString()} words
            </div>
            {report?.recommendation && (
              <div style={{ fontSize: 13, color: 'var(--slate-text)', lineHeight: 1.6, maxWidth: 420 }}>
                {report.recommendation}
              </div>
            )}
            <div style={{ marginTop: 14 }}>
              <a href={`/api/v1/submissions/${selected.id}/report/pdf`} download
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'DM Mono, monospace',
                  fontSize: 11, letterSpacing: 1, color: 'var(--cyan)', background: 'rgba(0,212,255,0.08)',
                  border: '1px solid rgba(0,212,255,0.2)', borderRadius: 6, padding: '7px 14px', textDecoration: 'none',
                  transition: 'all 0.2s' }}>
                <Download size={12} /> DOWNLOAD PDF
              </a>
            </div>
          </div>
        </div>

        {/* Module results */}
        {report && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {Object.entries(report.modules || {}).map(([moduleId, mod]) => (
              <ModuleResultCard key={moduleId} moduleId={moduleId}
                data={{ score: mod.score, confidence: mod.confidence ?? 0.7, weight: mod.weight, evidence: mod.evidence, processing_ms: mod.processing_ms }}
              />
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={fetch} className="btn-ghost" style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '7px 14px' }}>
          <RefreshCw size={13} className={loading ? 'animate-spin-slow' : ''} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="glass" style={{ borderRadius: 12, padding: 48, textAlign: 'center' }}>
          <Loader2 size={24} className="animate-spin-slow" style={{ color: 'var(--cyan)', margin: '0 auto 12px' }} />
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 2 }}>LOADING…</div>
        </div>
      ) : submissions.length === 0 ? (
        <div className="glass" style={{ borderRadius: 12, padding: 56, textAlign: 'center' }}>
          <FileText size={32} style={{ color: 'rgba(168,184,216,0.3)', margin: '0 auto 12px' }} />
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 2 }}>NO SUBMISSIONS YET</div>
        </div>
      ) : (
        <div className="glass stagger" style={{ borderRadius: 12, overflow: 'hidden' }}>
          {submissions.map((sub, i) => {
            const report = reports[sub.id]
            const isProcessing = sub.status === 'processing' || sub.status === 'pending'
            return (
              <div key={sub.id}
                onClick={() => report && setSelected(sub)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px',
                  borderBottom: i < submissions.length - 1 ? '1px solid var(--border)' : 'none',
                  cursor: report ? 'pointer' : 'default',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => { if (report) e.currentTarget.style.background = 'rgba(255,255,255,0.025)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
              >
                <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(255,255,255,0.04)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <FileText size={15} style={{ color: 'var(--slate-text)' }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 14, fontWeight: 600,
                    color: '#e2eaf7', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {sub.original_filename || 'Untitled'}
                  </div>
                  <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 0.5, marginTop: 3 }}>
                    {sub.word_count?.toLocaleString() ?? 0} words · {new Date(sub.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                  {isProcessing ? (
                    <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--cyan)', letterSpacing: 1 }}>
                      <Loader2 size={12} className="animate-spin-slow" style={{ display: 'inline', marginRight: 4 }} />PROCESSING
                    </span>
                  ) : report ? (
                    <>
                      <span className={`mono ${riskCls[report.risk_level] || 'risk-low'}`}
                        style={{ fontSize: 10, letterSpacing: 2, padding: '3px 8px', borderRadius: 4, fontWeight: 600 }}>
                        {report.risk_level}
                      </span>
                      <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 14, fontWeight: 600, color: '#e2eaf7', minWidth: 36, textAlign: 'right' }}>
                        {Math.round(report.integrity_score * 100)}%
                      </span>
                      <ChevronRight size={14} style={{ color: 'var(--slate-text)' }} />
                    </>
                  ) : (
                    <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'rgba(168,184,216,0.4)', letterSpacing: 1 }}>
                      {sub.status?.toUpperCase()}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
