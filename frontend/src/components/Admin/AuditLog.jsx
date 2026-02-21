import { useEffect, useState } from 'react'
import { adminApi } from '../../api'
import { Loader2 } from 'lucide-react'

export function AuditLog() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi.getAuditLog(30).then(d => setLogs(d.logs || [])).catch(() => {}).finally(() => setLoading(false))
  }, [])

  return (
    <div className="glass" style={{ borderRadius: 12, padding: 28 }}>
      <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 17, fontWeight: 700, marginBottom: 20 }}>Audit Log</div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <Loader2 size={20} className="animate-spin-slow" style={{ color: 'var(--cyan)', margin: '0 auto' }} />
        </div>
      ) : logs.length === 0 ? (
        <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 1, textAlign: 'center', padding: 32 }}>
          NO AUDIT ENTRIES
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {logs.map((log, i) => (
            <div key={log.id} style={{
              display: 'flex', alignItems: 'flex-start', gap: 14, padding: '12px 0',
              borderBottom: i < logs.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'rgba(168,184,216,0.4)', letterSpacing: 0.5, flexShrink: 0, marginTop: 1 }}>
                {new Date(log.created_at).toLocaleTimeString()}
              </div>
              <div style={{ flex: 1 }}>
                <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--cyan)', letterSpacing: 1 }}>{log.action}</span>
                {log.resource_type && (
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', marginLeft: 8 }}>
                    {log.resource_type}:{log.resource_id?.slice(0,8)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
