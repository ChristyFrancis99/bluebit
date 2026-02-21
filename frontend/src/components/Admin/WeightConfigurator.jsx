import { useState, useEffect } from 'react'
import { Sliders, Save, CheckCircle, AlertCircle, ToggleLeft, ToggleRight } from 'lucide-react'
import { adminApi, modulesApi } from '../../api'

const MODULE_META = {
  ai_detection:    { label: 'AI Detection',   desc: 'RoBERTa transformer classifier' },
  plagiarism:      { label: 'Plagiarism',      desc: 'MinHash LSH similarity' },
  writing_profile: { label: 'Writing Profile', desc: 'Stylometric deviation' },
  proctoring:      { label: 'Proctoring',      desc: 'Behavioral signals' },
}

export function WeightConfigurator() {
  const [weights, setWeights] = useState({
    ai_detection: 0.35, plagiarism: 0.40, writing_profile: 0.25, proctoring: 0.00,
  })
  const [enabled, setEnabled] = useState({
    ai_detection: true, plagiarism: true, writing_profile: true, proctoring: false,
  })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    adminApi.getConfig().then(cfg => {
      if (cfg.weights) setWeights(cfg.weights)
      if (cfg.modules) {
        const e = {}
        cfg.modules.forEach(m => { e[m.module_id] = m.enabled })
        setEnabled(e)
      }
    }).catch(() => {})
  }, [])

  const total = Object.values(weights).reduce((a, b) => a + b, 0)
  const valid = Math.abs(total - 1.0) < 0.06

  const save = async () => {
    setSaving(true); setMsg(null)
    try {
      await adminApi.updateWeights(weights)
      setMsg({ ok: true, text: 'Configuration saved' })
    } catch (e) {
      setMsg({ ok: false, text: e.response?.data?.detail || 'Save failed' })
    } finally {
      setSaving(false)
      setTimeout(() => setMsg(null), 4000)
    }
  }

  const toggle = async (id) => {
    const next = !enabled[id]
    try {
      await modulesApi.toggle(id, next)
      setEnabled(prev => ({ ...prev, [id]: next }))
    } catch {}
  }

  return (
    <div className="glass" style={{ borderRadius: 12, padding: 28, display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Sliders size={18} style={{ color: 'var(--cyan)' }} />
        <div>
          <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 17, fontWeight: 700 }}>Module Configuration</div>
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 1, marginTop: 2 }}>
            ADJUST WEIGHTS AND ENABLE/DISABLE MODULES
          </div>
        </div>
      </div>

      {/* Weight total indicator */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', borderRadius: 8,
        background: valid ? 'rgba(0,229,160,0.07)' : 'rgba(255,184,48,0.07)',
        border: `1px solid ${valid ? 'rgba(0,229,160,0.2)' : 'rgba(255,184,48,0.2)'}`,
      }}>
        <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 1 }}>TOTAL WEIGHT</span>
        <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 14, fontWeight: 600, color: valid ? 'var(--green)' : 'var(--amber)' }}>
          {(total * 100).toFixed(0)}% {valid ? '✓' : '≠ 100%'}
        </span>
      </div>

      {/* Sliders */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {Object.entries(MODULE_META).map(([id, meta]) => {
          const w = weights[id] ?? 0
          const isOn = enabled[id] ?? false
          return (
            <div key={id}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {/* Toggle */}
                  <button onClick={() => toggle(id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: isOn ? 'var(--cyan)' : 'rgba(168,184,216,0.3)', padding: 0, display: 'flex' }}>
                    {isOn ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                  </button>
                  <div>
                    <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 14, fontWeight: 600, color: isOn ? '#e2eaf7' : 'rgba(226,234,247,0.4)' }}>
                      {meta.label}
                    </div>
                    <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'rgba(168,184,216,0.4)', letterSpacing: 0.5, marginTop: 1 }}>
                      {meta.desc}
                    </div>
                  </div>
                </div>
                <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 15, fontWeight: 600,
                  color: isOn ? 'var(--cyan)' : 'rgba(168,184,216,0.3)', minWidth: 42, textAlign: 'right' }}>
                  {Math.round(w * 100)}%
                </div>
              </div>
              <input type="range" min={0} max={100} value={Math.round(w * 100)} disabled={!isOn}
                onChange={e => setWeights(prev => ({ ...prev, [id]: Number(e.target.value) / 100 }))}
              />
            </div>
          )
        })}
      </div>

      {msg && (
        <div className="animate-fade-in" style={{
          display: 'flex', alignItems: 'center', gap: 8, fontSize: 13,
          color: msg.ok ? 'var(--green)' : 'var(--red)',
          background: msg.ok ? 'rgba(0,229,160,0.08)' : 'rgba(255,71,87,0.08)',
          border: `1px solid ${msg.ok ? 'rgba(0,229,160,0.2)' : 'rgba(255,71,87,0.2)'}`,
          borderRadius: 8, padding: '10px 14px',
        }}>
          {msg.ok ? <CheckCircle size={15} /> : <AlertCircle size={15} />}
          {msg.text}
        </div>
      )}

      <button className="btn-primary" onClick={save} disabled={saving || !valid}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          fontFamily: 'DM Mono, monospace', fontSize: 12, letterSpacing: 2, padding: 13 }}>
        <Save size={14} />
        {saving ? 'SAVING…' : 'SAVE CONFIGURATION'}
      </button>
    </div>
  )
}
