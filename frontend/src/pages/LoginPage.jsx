import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { AlertCircle, Loader2, Shield } from 'lucide-react'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { login, loading, error } = useAuthStore()
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    try { await login(email, password); navigate('/') } catch {}
  }

  return (
    <div className="grid-bg" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      {/* Background glow */}
      <div style={{ position: 'fixed', top: '20%', left: '50%', transform: 'translateX(-50%)',
        width: 600, height: 300, background: 'radial-gradient(ellipse, rgba(0,212,255,0.06) 0%, transparent 70%)',
        pointerEvents: 'none' }} />

      <div className="animate-fade-up" style={{ width: '100%', maxWidth: 420 }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{ width: 52, height: 52, borderRadius: 14, background: 'rgba(0,212,255,0.1)',
            border: '1px solid rgba(0,212,255,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <Shield size={24} style={{ color: 'var(--cyan)' }} />
          </div>
          <h1 style={{ fontFamily: 'Syne, sans-serif', fontSize: 26, fontWeight: 800, letterSpacing: -0.5, marginBottom: 6 }}>
            Integrity AI
          </h1>
          <p style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 2 }}>
            SIGN IN TO CONTINUE
          </p>
        </div>

        <div className="glass" style={{ borderRadius: 14, padding: 32 }}>
          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 7 }}>EMAIL</label>
              <input className="field" type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="you@university.edu" />
            </div>
            <div>
              <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 7 }}>PASSWORD</label>
              <input className="field" type="password" value={password} onChange={e => setPassword(e.target.value)} required placeholder="••••••••" />
            </div>

            {error && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--red)',
                background: 'rgba(255,71,87,0.08)', border: '1px solid rgba(255,71,87,0.2)', borderRadius: 8, padding: '10px 14px' }}>
                <AlertCircle size={15} /> {error}
              </div>
            )}

            <button className="btn-primary" type="submit" disabled={loading}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 6,
                fontFamily: 'DM Mono, monospace', fontSize: 12, letterSpacing: 2, padding: 13, width: '100%' }}>
              {loading ? <><Loader2 size={15} className="animate-spin-slow" /> SIGNING IN…</> : 'SIGN IN'}
            </button>
          </form>

          <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--border)', textAlign: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--slate-text)' }}>No account? </span>
            <Link to="/register" style={{ fontSize: 13, color: 'var(--cyan)', textDecoration: 'none', fontWeight: 600 }}>Register</Link>
          </div>

          {/* Demo hint */}
          <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: 'rgba(0,212,255,0.04)', border: '1px solid rgba(0,212,255,0.1)' }}>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 2, marginBottom: 6 }}>DEMO ACCOUNTS</div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'rgba(168,184,216,0.6)', lineHeight: 1.8 }}>
              admin@demo.edu / admin123<br />student@demo.edu / student123
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
