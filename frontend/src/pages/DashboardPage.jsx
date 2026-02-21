import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { SubmissionForm } from '../components/Upload/SubmissionForm'
import { SubmissionHistory } from '../components/Dashboard/SubmissionHistory'
import { WeightConfigurator } from '../components/Admin/WeightConfigurator'
import { AdminStats } from '../components/Admin/AdminStats'
import { AuditLog } from '../components/Admin/AuditLog'
import {
  Shield, Upload, Clock, Settings, LogOut,
  Activity, ChevronRight,
} from 'lucide-react'

const NAV = [
  { id: 'submit',  label: 'Submit',  icon: Upload,   roles: ['student','educator','admin'] },
  { id: 'history', label: 'History', icon: Clock,    roles: ['student','educator','admin'] },
  { id: 'admin',   label: 'Admin',   icon: Settings, roles: ['admin'] },
]

const PAGE_META = {
  submit:  { title: 'Submit Document',     sub: 'Upload a document for multi-modal integrity analysis' },
  history: { title: 'Submission History',  sub: 'Review past submissions and drill into reports' },
  admin:   { title: 'Admin Configuration', sub: 'Module weights, toggles, stats and audit log' },
}

export function DashboardPage() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [tab, setTab] = useState('submit')

  const userRole = user?.role || 'student'
  const visibleNav = NAV.filter(n => n.roles.includes(userRole))

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside style={{
        position: 'fixed', left: 0, top: 0, bottom: 0, width: 224,
        background: 'var(--navy-2)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', zIndex: 20,
      }}>
        {/* Logo */}
        <div style={{ padding: '22px 20px 18px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 10, background: 'rgba(0,212,255,0.12)',
              border: '1px solid rgba(0,212,255,0.22)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Shield size={17} style={{ color: 'var(--cyan)' }} />
            </div>
            <div>
              <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 14, fontWeight: 700, color: '#e2eaf7' }}>Integrity AI</div>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'rgba(168,184,216,0.5)', letterSpacing: 1.5 }}>v1.0.0</div>
            </div>
          </div>
        </div>

        {/* Status indicator */}
        <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--green)',
              boxShadow: '0 0 6px rgba(0,229,160,0.6)' }} />
            <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 1.5 }}>
              ALL SYSTEMS NOMINAL
            </span>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {visibleNav.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={tab === id ? 'nav-active' : ''}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 12px', borderRadius: 8,
                background: tab === id ? undefined : 'transparent',
                border: '1px solid transparent',
                color: tab === id ? 'var(--cyan)' : 'var(--slate-text)',
                fontFamily: 'DM Sans, sans-serif', fontSize: 14, fontWeight: 500,
                cursor: 'pointer', width: '100%', transition: 'all 0.15s',
              }}
              onMouseEnter={e => { if (tab !== id) e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
              onMouseLeave={e => { if (tab !== id) e.currentTarget.style.background = 'transparent' }}
            >
              <Icon size={16} /> {label}
            </button>
          ))}
        </nav>

        {/* User / logout */}
        <div style={{ padding: '12px 10px', borderTop: '1px solid var(--border)' }}>
          <div style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'rgba(0,212,255,0.12)',
              border: '1px solid rgba(0,212,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <span style={{ fontFamily: 'Syne, sans-serif', fontSize: 12, fontWeight: 700, color: 'var(--cyan)' }}>
                {(user?.email || 'U')[0].toUpperCase()}
              </span>
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: '#e2eaf7', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user?.email}
              </div>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 9, color: 'var(--slate-text)', letterSpacing: 1.5, textTransform: 'uppercase', marginTop: 1 }}>
                {user?.role}
              </div>
            </div>
          </div>
          <button onClick={() => { logout(); navigate('/login') }}
            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 12px', borderRadius: 8,
              background: 'transparent', border: 'none', cursor: 'pointer', color: 'rgba(168,184,216,0.5)',
              fontSize: 13, transition: 'color 0.15s' }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--red)'}
            onMouseLeave={e => e.currentTarget.style.color = 'rgba(168,184,216,0.5)'}
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <main style={{ marginLeft: 224, flex: 1, minHeight: '100vh' }} className="grid-bg">
        {/* Background glow */}
        <div style={{ position: 'fixed', top: 0, right: 0, width: 500, height: 400,
          background: 'radial-gradient(ellipse at top right, rgba(0,212,255,0.04) 0%, transparent 60%)',
          pointerEvents: 'none', zIndex: 0 }} />

        <div style={{ maxWidth: 820, margin: '0 auto', padding: '40px 32px', position: 'relative', zIndex: 1 }}>
          {/* Page header */}
          <div className="animate-fade-up" style={{ marginBottom: 28 }}>
            {/* Breadcrumb */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'rgba(168,184,216,0.4)', letterSpacing: 2 }}>DASHBOARD</span>
              <ChevronRight size={11} style={{ color: 'rgba(168,184,216,0.3)' }} />
              <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--cyan)', letterSpacing: 2 }}>
                {tab.toUpperCase()}
              </span>
            </div>
            <h1 style={{ fontFamily: 'Syne, sans-serif', fontSize: 26, fontWeight: 800, letterSpacing: -0.5, marginBottom: 4 }}>
              {PAGE_META[tab]?.title}
            </h1>
            <p style={{ fontSize: 14, color: 'var(--slate-text)', lineHeight: 1.5 }}>
              {PAGE_META[tab]?.sub}
            </p>
          </div>

          {/* Content */}
          {tab === 'submit' && <SubmissionForm />}
          {tab === 'history' && <SubmissionHistory />}
          {tab === 'admin' && userRole === 'admin' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <WeightConfigurator />
              <AdminStats />
              <AuditLog />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
