import { useState, useRef, useCallback } from 'react'
import { Video, Upload, X, AlertTriangle, Loader2, CheckCircle, Eye, Shield } from 'lucide-react'
import { videoProctoringApi } from '../../api'

const ACCEPTED_VIDEO_TYPES = ['.mp4', '.webm', '.mov', '.avi', '.mkv']

export function VideoUploadAnalyzer({ onAnalysisComplete, enabled = true }) {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const fileRef = useRef()

  const validate = useCallback((f) => {
    const ext = '.' + f.name.split('.').pop().toLowerCase()
    if (!ACCEPTED_VIDEO_TYPES.includes(ext)) {
      setError(`Unsupported video format. Accepted: ${ACCEPTED_VIDEO_TYPES.join(', ')}`)
      return false
    }
    if (f.size > 500 * 1024 * 1024) {
      setError('Video file too large (max 500MB)')
      return false
    }
    setError(null)
    return true
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f && validate(f)) setFile(f)
  }, [validate])

  const analyzeVideo = async () => {
    if (!file) return
    setAnalyzing(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('video', file)
      
      const res = await videoProctoringApi.analyzeVideo(formData)
      setResult(res)
      onAnalysisComplete?.(res)
    } catch (err) {
      setError(err.response?.data?.detail || 'Video analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleReset = () => {
    setFile(null)
    setResult(null)
    setError(null)
  }

  if (!enabled) {
    return null
  }

  // Show results
  if (result) {
    const riskLevel = result.risk_score > 0.6 ? 'high' : result.risk_score > 0.3 ? 'medium' : 'low'
    const riskColor = riskLevel === 'high' ? 'var(--red)' : riskLevel === 'medium' ? 'var(--yellow)' : 'var(--green)'

    return (
      <div className="video-analyzer-result glass" style={{ 
        borderRadius: 12, 
        padding: 20,
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid var(--border)',
      }}>
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          marginBottom: 16,
        }}>
          <div style={{ 
            fontFamily: 'Syne, sans-serif', 
            fontWeight: 600, 
            fontSize: 14,
            color: 'var(--slate-text)',
          }}>
            Video Analysis Results
          </div>
          <button 
            onClick={handleReset}
            style={{ 
              background: 'none', 
              border: 'none', 
              cursor: 'pointer',
              color: 'var(--slate-text)',
              padding: 4,
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Risk Score */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 16,
          marginBottom: 16,
          padding: 16,
          borderRadius: 8,
          background: 'rgba(0,0,0,0.2)',
        }}>
          <Shield size={32} style={{ color: riskColor }} />
          <div>
            <div style={{ 
              fontFamily: 'Syne, sans-serif', 
              fontWeight: 700, 
              fontSize: 24,
              color: riskColor,
              textTransform: 'uppercase',
            }}>
              {riskLevel} Risk
            </div>
            <div style={{ 
              fontFamily: 'DM Mono, monospace', 
              fontSize: 11,
              color: 'var(--slate-text)',
            }}>
              Risk Score: {(result.risk_score * 100).toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Stats */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
          marginBottom: 16,
        }}>
          <div style={{ 
            padding: 12, 
            borderRadius: 8, 
            background: 'rgba(255,255,255,0.02)',
          }}>
            <div style={{ 
              fontFamily: 'DM Mono, monospace', 
              fontSize: 10, 
              color: 'var(--slate-text)',
              marginBottom: 4,
            }}>
              MULTIPLE FACES
            </div>
            <div style={{ 
              fontFamily: 'Syne, sans-serif', 
              fontWeight: 700, 
              fontSize: 20,
              color: result.multiple_faces_frames > 0 ? 'var(--red)' : 'var(--green)',
            }}>
              {result.multiple_faces_frames}
            </div>
          </div>
          
          <div style={{ 
            padding: 12, 
            borderRadius: 8, 
            background: 'rgba(255,255,255,0.02)',
          }}>
            <div style={{ 
              fontFamily: 'DM Mono, monospace', 
              fontSize: 10, 
              color: 'var(--slate-text)',
              marginBottom: 4,
            }}>
              MAX FACES
            </div>
            <div style={{ 
              fontFamily: 'Syne, sans-serif', 
              fontWeight: 700, 
              fontSize: 20,
              color: result.max_faces_in_frame > 1 ? 'var(--yellow)' : 'var(--green)',
            }}>
              {result.max_faces_in_frame}
            </div>
          </div>
          
          <div style={{ 
            padding: 12, 
            borderRadius: 8, 
            background: 'rgba(255,255,255,0.02)',
          }}>
            <div style={{ 
              fontFamily: 'DM Mono, monospace', 
              fontSize: 10, 
              color: 'var(--slate-text)',
              marginBottom: 4,
            }}>
              FRAMES ANALYZED
            </div>
            <div style={{ 
              fontFamily: 'Syne, sans-serif', 
              fontWeight: 700, 
              fontSize: 20,
            }}>
              {result.total_frames_analyzed}
            </div>
          </div>
          
          <div style={{ 
            padding: 12, 
            borderRadius: 8, 
            background: 'rgba(255,255,255,0.02)',
          }}>
            <div style={{ 
              fontFamily: 'DM Mono, monospace', 
              fontSize: 10, 
              color: 'var(--slate-text)',
              marginBottom: 4,
            }}>
              DURATION
            </div>
            <div style={{ 
              fontFamily: 'Syne, sans-serif', 
              fontWeight: 700, 
              fontSize: 20,
            }}>
              {Math.floor(result.duration_seconds / 60)}:{(Math.floor(result.duration_seconds) % 60).toString().padStart(2, '0')}
            </div>
          </div>
        </div>

        {/* Flags */}
        {result.flags && result.flags.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ 
              fontFamily: 'DM Mono, monospace', 
              fontSize: 10, 
              color: 'var(--slate-text)',
              marginBottom: 8,
              letterSpacing: 1,
            }}>
              FLAGS
            </div>
            {result.flags.map((flag, i) => (
              <div key={i} style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 8,
                padding: '8px 12px',
                borderRadius: 6,
                background: 'rgba(255,100,100,0.1)',
                border: '1px solid rgba(255,100,100,0.2)',
                marginBottom: 6,
                fontSize: 12,
                color: 'var(--red)',
              }}>
                <AlertTriangle size={14} />
                {flag}
              </div>
            ))}
          </div>
        )}

        {/* Recommendation */}
        <div style={{ 
          padding: 12, 
          borderRadius: 8, 
          background: 'rgba(0,212,255,0.05)',
          border: '1px solid rgba(0,212,255,0.2)',
          fontSize: 13,
          color: 'var(--slate-text)',
          lineHeight: 1.5,
        }}>
          {result.recommendation}
        </div>
      </div>
    )
  }

  // Upload form
  return (
    <div className="video-upload-analyzer glass" style={{ 
      borderRadius: 12, 
      padding: 20,
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid var(--border)',
    }}>
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        marginBottom: 16,
      }}>
        <div style={{ 
          fontFamily: 'Syne, sans-serif', 
          fontWeight: 600, 
          fontSize: 14,
          color: 'var(--slate-text)',
        }}>
          Video Face Detection
        </div>
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 6,
          fontFamily: 'DM Mono, monospace',
          fontSize: 10,
          letterSpacing: 1,
          color: 'var(--cyan)',
        }}>
          <Eye size={12} />
          MULTIPLE FACE DETECTION
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        style={{
          border: `2px dashed ${file ? 'var(--green)' : dragging ? 'var(--cyan)' : 'rgba(255,255,255,0.1)'}`,
          borderRadius: 10, 
          padding: '32px 24px', 
          textAlign: 'center', 
          cursor: 'pointer',
          background: file ? 'rgba(0,229,160,0.03)' : dragging ? 'var(--cyan-glow-2)' : 'rgba(255,255,255,0.015)',
          transition: 'all 0.2s ease',
          marginBottom: 16,
        }}
      >
        <input ref={fileRef} type="file" style={{ display: 'none' }} accept={ACCEPTED_VIDEO_TYPES.join(',')}
          onChange={e => { const f = e.target.files[0]; if (f && validate(f)) setFile(f) }} />
        
        {file ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
            <Video size={24} style={{ color: 'var(--green)' }} />
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontFamily: 'Syne, sans-serif', fontWeight: 600, fontSize: 14, color: '#e2eaf7' }}>
                {file.name}
              </div>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', marginTop: 2 }}>
                {(file.size / (1024 * 1024)).toFixed(2)} MB
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
              Drop video here or click to browse
            </div>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--slate-text)', letterSpacing: 1 }}>
              {ACCEPTED_VIDEO_TYPES.join(' · ')} · MAX 500MB
            </div>
          </>
        )}
      </div>

      {error && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 8, 
          fontSize: 13, 
          color: 'var(--red)',
          background: 'rgba(255,71,87,0.08)', 
          border: '1px solid rgba(255,71,87,0.2)', 
          borderRadius: 8, 
          padding: '10px 14px',
          marginBottom: 16,
        }}>
          <AlertCircle size={15} /> {error}
        </div>
      )}

      <button 
        className="btn-primary" 
        onClick={analyzeVideo}
        disabled={!file || analyzing}
        style={{ 
          width: '100%', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          gap: 8,
          fontFamily: 'DM Mono, monospace', 
          fontSize: 12, 
          letterSpacing: 2, 
          padding: '13px',
        }}
      >
        {analyzing ? (
          <><Loader2 size={15} className="animate-spin-slow" /> ANALYZING…</>
        ) : (
          <><Video size={15} /> ANALYZE VIDEO</>
        )}
      </button>
    </div>
  )
}

export default VideoUploadAnalyzer

