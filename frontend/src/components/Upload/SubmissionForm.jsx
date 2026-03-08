import { useState, useRef, useCallback } from 'react'
import { Upload, File, X, AlertCircle, Loader2, CheckCircle } from 'lucide-react'
import { submissionsApi } from '../../api'
import { useSubmissionWS } from '../../hooks/useSubmissionWS'
import { IntegrityScoreGauge } from '../Dashboard/IntegrityScoreGauge'
import { ModuleResultCard } from '../Dashboard/ModuleResultCard'
import { VideoRecorder } from '../Proctoring/VideoRecorder'
import { VideoUploadAnalyzer } from '../Proctoring/VideoUploadAnalyzer'
import { useVideoProctoring } from '../Proctoring/VideoEvents'

const ACCEPTED = ['.txt', '.docx', '.pdf', '.md']
const MODULES = [
  { id: 'ai_detection', label: 'AI Detection' },
  { id: 'plagiarism', label: 'Plagiarism' },
  { id: 'writing_profile', label: 'Writing Profile' },
  { id: 'proctoring', label: 'Proctoring' },
]

export function SubmissionForm({ onComplete }) {
  const [file, setFile]           = useState(null)
  const [dragging, setDragging]   = useState(false)
  const [error, setError]         = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [submissionId, setSubmissionId] = useState(null)
  const [assignmentId, setAssignmentId] = useState('')
  const [modules, setModules]     = useState(['ai_detection', 'plagiarism', 'writing_profile'])
  const [report, setReport]       = useState(null)
  const [videoProctoringEnabled, setVideoProctoringEnabled] = useState(false)
  const [videoAnalysisResult, setVideoAnalysisResult] = useState(null)
  const [proctoringMode, setProctoringMode] = useState('live') // 'live' or 'upload'
  const fileRef = useRef()

  const { moduleResults, completed, finalScore, wsStatus, reset } = useSubmissionWS(submissionId)
  
  // Video proctoring hook
  const proctoring = useVideoProctoring(videoProctoringEnabled)
  
  // Handle video event from recorder
  const handleVideoEvent = useCallback((eventType, data = {}) => {
    proctoring.reportEvent(eventType, data.duration || 0, data.metadata || {})
  }, [proctoring])
  
  // Handle session start
  const handleSessionStart = useCallback(async () => {
    const sessionId = await proctoring.startSession(null, assignmentId || null)
    return sessionId
  }, [proctoring, assignmentId])
  
  // Handle session end
  const handleSessionEnd = useCallback(async () => {
    return await proctoring.endSession()
  }, [proctoring])

  const validate = (f) => {
    const ext = '.' + f.name.split('.').pop().toLowerCase()
    if (!ACCEPTED.includes(ext)) { setError(`Unsupported type. Accepted: ${ACCEPTED.join(', ')}`); return false }
    if (f.size > 50 * 1024 * 1024) { setError('File too large (max 50 MB)'); return false }
    setError(null); return true
  }

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f && validate(f)) setFile(f)
  }, [])

  const handleSubmit = async () => {
    if (!file || modules.length === 0) return
    setSubmitting(true); setError(null)
    try {
      // End video proctoring session if active (live mode)
      let videoSessionId = null
      if (videoProctoringEnabled && proctoringMode === 'live' && proctoring.sessionId) {
        await proctoring.endSession()
        videoSessionId = proctoring.sessionId
      }
      
      const fd = new FormData()
      fd.append('file', file)
      if (assignmentId) fd.append('assignment_id', assignmentId)
      fd.append('modules', modules.join(','))
      if (videoSessionId) fd.append('video_session_id', videoSessionId)
      
      // Include video analysis result if in upload mode
      if (videoProctoringEnabled && proctoringMode === 'upload' && videoAnalysisResult) {
        fd.append('video_analysis_id', videoAnalysisResult.analysis_id)
        fd.append('video_risk_score', videoAnalysisResult.risk_score)
      }
      
      const res = await submissionsApi.create(fd)
      setSubmissionId(res.submission_id)
    } catch (err) {
      setError(err.response?.data?.detail || 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  const loadReport = async (sid) => {
    try {
      const r = await submissionsApi.getReport(sid)
      setReport(r)
      onComplete?.(r)
    } catch {}
  }

  if (completed && submissionId && !report) loadReport(submissionId)

  const handleReset = () => {
    reset(); setSubmissionId(null); setFile(null); setReport(null)
    setError(null); setAssignmentId('')
  }

  // ── Analyzing / results view ──────────────────────────────────────────────
  if (submissionId) {
    return (
      <div className="animate-fade-up" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Status header */}
        <div className="glass" style={{ borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 20 }}>
            <div>
              <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
                {completed ? 'Analysis Complete' : 'Analyzing Document…'}
              </div>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 1 }}>
                {submissionId.slice(0, 16)}… · {wsStatus.toUpperCase()}
              </div>
            </div>
            {finalScore && (
              <IntegrityScoreGauge score={finalScore.score} riskLevel={finalScore.risk} size={130} />
            )}
          </div>
        </div>

        {/* Module cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {MODULES.filter(m => modules.includes(m.id)).map(({ id }) => (
            <ModuleResultCard key={id} moduleId={id}
              data={moduleResults[id]
                ? { ...moduleResults[id], weight: report?.modules?.[id]?.weight, evidence: report?.modules?.[id]?.evidence }
                : null}
              loading={!!submissionId && !moduleResults[id] && !completed}
            />
          ))}
        </div>

        {/* Recommendation + actions */}
        {completed && report && (
          <div className="glass-cyan animate-fade-in" style={{ borderRadius: 12, padding: 20 }}>
            <div style={{ fontSize: 14, color: 'var(--slate-text)', lineHeight: 1.6, marginBottom: 16 }}>
              {report.recommendation}
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <a href={`/api/v1/submissions/${submissionId}/report/pdf`} download
                className="btn-primary" style={{ fontSize: 12, letterSpacing: 1, padding: '9px 18px',
                  fontFamily: 'DM Mono, monospace', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                DOWNLOAD PDF REPORT
              </a>
              <button onClick={handleReset} className="btn-ghost" style={{ fontSize: 12, letterSpacing: 1, padding: '9px 18px', fontFamily: 'DM Mono, monospace' }}>
                NEW SUBMISSION
              </button>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Upload form ───────────────────────────────────────────────────────────
  return (
    <div className="animate-fade-up glass" style={{ borderRadius: 12, padding: 28, display: 'flex', flexDirection: 'column', gap: 22 }}>
      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        style={{
          border: `2px dashed ${file ? 'var(--green)' : dragging ? 'var(--cyan)' : 'rgba(255,255,255,0.1)'}`,
          borderRadius: 10, padding: '36px 24px', textAlign: 'center', cursor: 'pointer',
          background: file ? 'rgba(0,229,160,0.03)' : dragging ? 'var(--cyan-glow-2)' : 'rgba(255,255,255,0.015)',
          transition: 'all 0.2s ease',
        }}
      >
        <input ref={fileRef} type="file" style={{ display: 'none' }} accept={ACCEPTED.join(',')}
          onChange={e => { const f = e.target.files[0]; if (f && validate(f)) setFile(f) }} />
        {file ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
            <CheckCircle size={20} style={{ color: 'var(--green)' }} />
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontFamily: 'Syne, sans-serif', fontWeight: 600, fontSize: 14, color: '#e2eaf7' }}>{file.name}</div>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', marginTop: 2 }}>
                {(file.size / 1024).toFixed(1)} KB
              </div>
            </div>
            <button onClick={e => { e.stopPropagation(); setFile(null) }}
              style={{ marginLeft: 8, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--slate-text)', padding: 4 }}>
              <X size={16} />
            </button>
          </div>
        ) : (
          <>
            <Upload size={28} style={{ color: dragging ? 'var(--cyan)' : 'rgba(168,184,216,0.4)', margin: '0 auto 12px' }} />
            <div style={{ fontFamily: 'Syne, sans-serif', fontWeight: 600, fontSize: 15, color: dragging ? 'var(--cyan)' : '#e2eaf7', marginBottom: 6 }}>
              Drop file here or click to browse
            </div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 1 }}>
              {ACCEPTED.join(' · ')} · MAX 50MB
            </div>
          </>
        )}
      </div>

      {/* Assignment ID */}
      <div>
        <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 8 }}>
          ASSIGNMENT ID <span style={{ opacity: 0.5 }}>(OPTIONAL)</span>
        </label>
        <input className="field" value={assignmentId} onChange={e => setAssignmentId(e.target.value)}
          placeholder="e.g. CS101-HW3" />
      </div>

      {/* Video Proctoring Toggle */}
      <div>
        <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 10 }}>
          VIDEO PROCTORING <span style={{ opacity: 0.5 }}>(OPTIONAL)</span>
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            type="button"
            onClick={() => setVideoProctoringEnabled(!videoProctoringEnabled)}
            style={{
              position: 'relative',
              width: 44,
              height: 24,
              borderRadius: 12,
              border: 'none',
              cursor: 'pointer',
              background: videoProctoringEnabled ? 'var(--cyan)' : 'rgba(255,255,255,0.1)',
              transition: 'all 0.2s',
            }}
          >
            <span style={{
              position: 'absolute',
              top: 2,
              left: videoProctoringEnabled ? 22 : 2,
              width: 20,
              height: 20,
              borderRadius: '50%',
              background: '#fff',
              transition: 'all 0.2s',
            }} />
          </button>
          <span style={{ 
            fontFamily: 'DM Mono, monospace', 
            fontSize: 11, 
            color: videoProctoringEnabled ? 'var(--cyan)' : 'var(--slate-text)',
          }}>
            {videoProctoringEnabled ? 'Enabled' : 'Disabled'}
          </span>
        </div>
      </div>

      {/* Proctoring Mode Toggle */}
      {videoProctoringEnabled && (
        <div>
          <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 10 }}>
            PROCTORING MODE
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={() => setProctoringMode('live')}
              style={{
                flex: 1,
                fontFamily: 'DM Mono, monospace',
                fontSize: 11,
                letterSpacing: 1,
                padding: '8px 12px',
                borderRadius: 6,
                cursor: 'pointer',
                border: `1px solid ${proctoringMode === 'live' ? 'var(--cyan)' : 'var(--border)'}`,
                background: proctoringMode === 'live' ? 'rgba(0,212,255,0.1)' : 'transparent',
                color: proctoringMode === 'live' ? 'var(--cyan)' : 'var(--slate-text)',
                transition: 'all 0.2s',
              }}
            >
              🔴 Live Recording
            </button>
            <button
              type="button"
              onClick={() => setProctoringMode('upload')}
              style={{
                flex: 1,
                fontFamily: 'DM Mono, monospace',
                fontSize: 11,
                letterSpacing: 1,
                padding: '8px 12px',
                borderRadius: 6,
                cursor: 'pointer',
                border: `1px solid ${proctoringMode === 'upload' ? 'var(--cyan)' : 'var(--border)'}`,
                background: proctoringMode === 'upload' ? 'rgba(0,212,255,0.1)' : 'transparent',
                color: proctoringMode === 'upload' ? 'var(--cyan)' : 'var(--slate-text)',
                transition: 'all 0.2s',
              }}
            >
              📤 Upload Video
            </button>
          </div>
          <div style={{ 
            fontFamily: 'DM Mono, monospace', 
            fontSize: 10, 
            color: 'var(--slate-text)',
            marginTop: 8,
            opacity: 0.7,
          }}>
            {proctoringMode === 'live' 
              ? 'Record your session in real-time with face detection'
              : 'Upload a pre-recorded video to detect multiple faces'
            }
          </div>
        </div>
      )}

      {/* Video Recorder */}
      {videoProctoringEnabled && proctoringMode === 'live' && (
        <VideoRecorder
          enabled={videoProctoringEnabled}
          sessionId={proctoring.sessionId}
          onSessionStart={handleSessionStart}
          onSessionEnd={handleSessionEnd}
          onEvent={handleVideoEvent}
        />
      )}

      {/* Video Upload Analyzer (for multiple face detection) */}
      {videoProctoringEnabled && proctoringMode === 'upload' && (
        <VideoUploadAnalyzer
          enabled={videoProctoringEnabled}
          onAnalysisComplete={setVideoAnalysisResult}
        />
      )}

      {/* Module selector */}
      <div>
        <label style={{ fontFamily: 'DM Mono, monospace', fontSize: 10, color: 'var(--slate-text)', letterSpacing: 2, display: 'block', marginBottom: 10 }}>
          ANALYSIS MODULES
        </label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {MODULES.map(({ id, label }) => {
            const active = modules.includes(id)
            return (
              <button key={id} onClick={() => setModules(prev => active ? prev.filter(m => m !== id) : [...prev, id])}
                style={{
                  fontFamily: 'DM Mono, monospace', fontSize: 11, letterSpacing: 1,
                  padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
                  border: `1px solid ${active ? 'var(--cyan-dim)' : 'var(--border)'}`,
                  background: active ? 'rgba(0,212,255,0.1)' : 'transparent',
                  color: active ? 'var(--cyan)' : 'var(--slate-text)',
                  transition: 'all 0.2s',
                }}>
                {label}
              </button>
            )
          })}
        </div>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--red)',
          background: 'rgba(255,71,87,0.08)', border: '1px solid rgba(255,71,87,0.2)', borderRadius: 8, padding: '10px 14px' }}>
          <AlertCircle size={15} /> {error}
        </div>
      )}

      <button className="btn-primary" onClick={handleSubmit}
        disabled={!file || submitting || modules.length === 0}
        style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          fontFamily: 'DM Mono, monospace', fontSize: 12, letterSpacing: 2, padding: '13px' }}>
        {submitting
          ? <><Loader2 size={15} className="animate-spin-slow" /> SUBMITTING…</>
          : 'ANALYZE DOCUMENT'}
      </button>
    </div>
  )
}
