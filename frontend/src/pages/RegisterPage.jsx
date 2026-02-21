import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { AlertCircle, Loader2, Shield } from 'lucide-react'

export function RegisterPage() {
  const [form, setForm] = useState({ email: '', password: '', full_name: '', role: 'student' })
  const { register, loading, error } = useAuthStore()
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    try { await register(form); navigate('/') } catch {}
  }

  const roles = [
    { id: 'student',  label: 'Student' },
    { id: 'educator', label: 'Educator' },
    { id: 'admin',    label: 'Administrator' },
  ]

  return (
    <div className="grid-bg" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ position: 'fixed', top: '20%', left: '50%', transform: 'translateX(-50%)',
        width: 600, height: 300, background: 'radial-gradient(ellipse, rgba(0,212,255,0.06) 0%, transparent 70%)',
        pointerEvents: 'none' }} />

      <div className="animate-fade-up" style={{ width: '100%', maxWidth: 420 }}>
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{ width: 52, height: 52, borderRadius: 14, background: 'rgba(0,212,255,0.1)',
            border: '1px solid rgba(0,212,255,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <Shield size={24} style={{ color: 'var(--cyan)' }} />
          </div>
          <h1 style={{ fontFamily: 'Syne, sans-serif', fontSize: 26, fontWeight: 800, letterSpacing: -0.5, marginBottom: 6 }}>
            Create Account
          </h1>
          <p style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 2 }}>
            JOIN THE INTEGRITY PLATFORM
          </p>
        </div>

        <div className="glass" style={{ borderRadius: 14, padding: 32 }}>
          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 7 }}>FULL NAME</label>
              <input className="field" value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} required placeholder="Jane Smith" />
            </div>
            <div>
              <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 7 }}>EMAIL</label>
              <input className="field" type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required placeholder="you@university.edu" />
            </div>
            <div>
              <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 7 }}>PASSWORD</label>
              <input className="field" type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required minLength={6} placeholder="min 6 characters" />
            </div>
            <div>
              <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 9 }}>ROLE</label>
              <div style={{ display: 'flex', gap: 8 }}>
                {roles.map(r => (
                  <button key={r.id} type="button" onClick={() => setForm({...form, role: r.id})}
                    style={{
                      flex: 1, padding: '9px 4px', borderRadius: 8, cursor: 'pointer',
                      fontFamily: 'DM Mono, monospace', fontSize: 10, letterSpacing: 1,
                      border: `1px solid ${form.role === r.id ? 'var(--cyan-dim)' : 'var(--border)'}`,
                      background: form.role === r.id ? 'rgba(0,212,255,0.1)' : 'transparent',
                      color: form.role === r.id ? 'var(--cyan)' : 'var(--slate-text)',
                      transition: 'all 0.2s',
                    }}>
                    {r.label}
                  </button>
                ))}
              </div>
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
              {loading ? <><Loader2 size={15} className="animate-spin-slow" /> CREATING ACCOUNT…</> : 'CREATE ACCOUNT'}
            </button>
          </form>

          <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--border)', textAlign: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--slate-text)' }}>Have an account? </span>
            <Link to="/login" style={{ fontSize: 13, color: 'var(--cyan)', textDecoration: 'none', fontWeight: 600 }}>Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
