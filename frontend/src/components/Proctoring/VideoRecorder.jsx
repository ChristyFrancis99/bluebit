import { useState, useRef, useEffect, useCallback } from 'react'
import { Camera, CameraOff, AlertTriangle, CheckCircle, XCircle, Mic, MicOff, Video, VideoOff } from 'lucide-react'

// Video event types matching backend
const VideoEventType = {
  FACE_DETECTED: 'face_detected',
  FACE_LOST: 'face_lost',
  MULTIPLE_FACES: 'multiple_faces',
  LOW_LIGHT: 'low_light',
  DEVICE_CHANGE: 'device_change',
  SCREEN_CAPTURE: 'screen_capture',
  SESSION_START: 'session_start',
  SESSION_END: 'session_end',
}

export function VideoRecorder({ 
  onSessionStart, 
  onSessionEnd, 
  onEvent,
  sessionId,
  enabled = true 
}) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const canvasRef = useRef(null)
  const faceDetectionRef = useRef(null)
  const eventIntervalRef = useRef(null)
  const noFaceTimerRef = useRef(null)
  
  const [isActive, setIsActive] = useState(false)
  const [cameraOn, setCameraOn] = useState(true)
  const [micOn, setMicOn] = useState(true)
  const [error, setError] = useState(null)
  const [status, setStatus] = useState('idle') // idle, starting, active, error
  const [metrics, setMetrics] = useState({
    faceDetected: false,
    faceLostCount: 0,
    multipleFacesCount: 0,
    lowLightCount: 0,
    deviceChangeCount: 0,
    duration: 0,
  })

  // Start camera
  const startCamera = useCallback(async () => {
    if (!enabled) return
    
    try {
      setStatus('starting')
      setError(null)
      
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user',
        },
        audio: false, // Audio not needed for basic proctoring
      })
      
      streamRef.current = stream
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      
      setStatus('active')
      setIsActive(true)
      setCameraOn(true)
      
      // Start face detection and event monitoring
      startMonitoring()
      
    } catch (err) {
      console.error('Camera error:', err)
      setError(err.message || 'Failed to access camera')
      setStatus('error')
    }
  }, [enabled])

  // Stop camera
  const stopCamera = useCallback(async () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    
    if (eventIntervalRef.current) {
      clearInterval(eventIntervalRef.current)
      eventIntervalRef.current = null
    }
    
    if (noFaceTimerRef.current) {
      clearTimeout(noFaceTimerRef.current)
      noFaceTimerRef.current = null
    }
    
    setIsActive(false)
    setStatus('idle')
  }, [])

  // Toggle camera
  const toggleCamera = useCallback(async () => {
    if (streamRef.current) {
      const videoTrack = streamRef.current.getVideoTracks()[0]
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled
        setCameraOn(videoTrack.enabled)
        
        if (!videoTrack.enabled) {
          onEvent?.(VideoEventType.FACE_LOST, { duration: 1 })
          setMetrics(prev => ({ ...prev, faceLostCount: prev.faceLostCount + 1 }))
        }
      }
    }
  }, [onEvent])

  // Simple face detection simulation using canvas brightness
  // In production, use a library like face-api.js or MediaPipe
  const detectFace = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return { faceDetected: false, brightness: 100 }
    
    const video = videoRef.current
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    
    // Set canvas size to video size
    canvas.width = video.videoWidth || 320
    canvas.height = video.videoHeight || 240
    
    // Draw current video frame
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    
    // Get image data for brightness analysis
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
    const data = imageData.data
    
    // Calculate average brightness
    let totalBrightness = 0
    for (let i = 0; i < data.length; i += 4) {
      totalBrightness += (data[i] + data[i + 1] + data[i + 2]) / 3
    }
    const avgBrightness = totalBrightness / (data.length / 4)
    
    // Brightness threshold for "low light"
    const isLowLight = avgBrightness < 50
    
    // Simple heuristic: assume face detected if brightness is in normal range
    // In production, use proper face detection library
    const faceDetected = avgBrightness >= 50 && avgBrightness <= 220
    
    return { faceDetected, brightness: avgBrightness, isLowLight }
  }, [])

  // Start monitoring loop
  const startMonitoring = useCallback(() => {
    let lastFaceDetected = true
    let lastFaceLostTime = null
    
    // Check every 2 seconds
    eventIntervalRef.current = setInterval(async () => {
      const { faceDetected, brightness, isLowLight } = detectFace()
      
      const newMetrics = { ...metrics }
      let eventSent = false
      
      // Face detected
      if (faceDetected && !lastFaceDetected) {
        // Face came back
        if (lastFaceLostTime) {
          const duration = (Date.now() - lastFaceLostTime) / 1000
          onEvent?.(VideoEventType.FACE_DETECTED, { duration })
        }
        lastFaceDetected = true
        lastFaceLostTime = null
        newMetrics.faceDetected = true
        eventSent = true
      } else if (!faceDetected && lastFaceDetected) {
        // Face lost
        onEvent?.(VideoEventType.FACE_LOST, { duration: 2 })
        lastFaceDetected = false
        lastFaceLostTime = Date.now()
        newMetrics.faceDetected = false
        newMetrics.faceLostCount += 1
        eventSent = true
      }
      
      // Low light detected
      if (isLowLight) {
        newMetrics.lowLightCount += 1
        onEvent?.(VideoEventType.LOW_LIGHT, { brightness })
        eventSent = true
      }
      
      // Update duration
      newMetrics.duration = (newMetrics.duration || 0) + 2
      
      setMetrics(newMetrics)
      
    }, 2000)
  }, [detectFace, onEvent, metrics])

  // Handle session start
  useEffect(() => {
    if (isActive && !sessionId) {
      onSessionStart?.()
    }
  }, [isActive, sessionId, onSessionStart])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera()
    }
  }, [stopCamera])

  // Handle session end
  const handleEndSession = useCallback(async () => {
    await stopCamera()
    onSessionEnd?.(metrics)
  }, [stopCamera, onSessionEnd, metrics])

  if (!enabled) {
    return null
  }

  return (
    <div className="video-recorder glass" style={{ 
      borderRadius: 12, 
      padding: 16,
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid var(--border)',
    }}>
      {/* Hidden canvas for face detection */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />
      
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        marginBottom: 12,
      }}>
        <div style={{ 
          fontFamily: 'Syne, sans-serif', 
          fontWeight: 600, 
          fontSize: 14,
          color: 'var(--slate-text)',
        }}>
          Video Proctoring
        </div>
        
        {/* Status indicator */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 6,
          fontFamily: 'DM Mono, monospace',
          fontSize: 10,
          letterSpacing: 1,
        }}>
          {isActive ? (
            <>
              <span style={{ 
                width: 8, 
                height: 8, 
                borderRadius: '50%', 
                background: 'var(--green)',
                animation: 'pulse 2s infinite',
              }} />
              <span style={{ color: 'var(--green)' }}>RECORDING</span>
            </>
          ) : status === 'error' ? (
            <>
              <XCircle size={12} style={{ color: 'var(--red)' }} />
              <span style={{ color: 'var(--red)' }}>ERROR</span>
            </>
          ) : (
            <>
              <span style={{ opacity: 0.5 }}>IDLE</span>
            </>
          )}
        </div>
      </div>

      {/* Video preview */}
      <div style={{ 
        position: 'relative',
        borderRadius: 8,
        overflow: 'hidden',
        background: '#000',
        aspectRatio: '4/3',
        marginBottom: 12,
      }}>
        <video 
          ref={videoRef}
          muted
          playsInline
          style={{ 
            width: '100%', 
            height: '100%', 
            objectFit: 'cover',
            transform: 'scaleX(-1)', // Mirror effect
            display: isActive ? 'block' : 'none',
          }}
        />
        
        {!isActive && status !== 'error' && (
          <div style={{ 
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
          }}>
            <CameraOff size={32} style={{ color: 'rgba(255,255,255,0.3)' }} />
            <span style={{ 
              color: 'rgba(255,255,255,0.5)', 
              fontSize: 12,
              fontFamily: 'DM Mono, monospace',
            }}>
              Click Start to begin video proctoring
            </span>
          </div>
        )}
        
        {error && (
          <div style={{ 
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            background: 'rgba(0,0,0,0.8)',
          }}>
            <AlertTriangle size={32} style={{ color: 'var(--red)' }} />
            <span style={{ 
              color: 'var(--red)', 
              fontSize: 12,
              fontFamily: 'DM Mono, monospace',
              textAlign: 'center',
              padding: '0 20px',
            }}>
              {error}
            </span>
          </div>
        )}
        
        {/* Face detection overlay */}
        {isActive && (
          <div style={{ 
            position: 'absolute',
            top: 8,
            left: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 8px',
            borderRadius: 4,
            background: metrics.faceDetected ? 'rgba(0,200,100,0.8)' : 'rgba(255,100,100,0.8)',
            fontSize: 10,
            fontFamily: 'DM Mono, monospace',
          }}>
            {metrics.faceDetected ? (
              <CheckCircle size={12} />
            ) : (
              <XCircle size={12} />
            )}
            {metrics.faceDetected ? 'Face Detected' : 'No Face'}
          </div>
        )}
      </div>

      {/* Controls */}
      <div style={{ 
        display: 'flex', 
        gap: 8,
        justifyContent: 'center',
      }}>
        {!isActive ? (
          <button 
            onClick={startCamera}
            disabled={status === 'starting'}
            className="btn-primary"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: 8,
              fontSize: 11,
              padding: '8px 16px',
            }}
          >
            <Camera size={14} />
            {status === 'starting' ? 'Starting...' : 'Start Recording'}
          </button>
        ) : (
          <>
            <button 
              onClick={toggleCamera}
              className="btn-ghost"
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 6,
                fontSize: 11,
                padding: '8px 12px',
              }}
            >
              {cameraOn ? <Video size={14} /> : <VideoOff size={14} />}
              {cameraOn ? 'Camera On' : 'Camera Off'}
            </button>
            
            <button 
              onClick={handleEndSession}
              className="btn-ghost"
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 6,
                fontSize: 11,
                padding: '8px 12px',
                color: 'var(--red)',
                borderColor: 'var(--red)',
              }}
            >
              <CameraOff size={14} />
              Stop Recording
            </button>
          </>
        )}
      </div>

      {/* Metrics display */}
      {isActive && (
        <div style={{ 
          marginTop: 12,
          padding: 10,
          borderRadius: 6,
          background: 'rgba(255,255,255,0.02)',
          fontSize: 10,
          fontFamily: 'DM Mono, monospace',
        }}>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: '1fr 1fr',
            gap: 6,
            color: 'var(--slate-text)',
          }}>
            <div>Face Lost: {metrics.faceLostCount}</div>
            <div>Multiple Faces: {metrics.multipleFacesCount}</div>
            <div>Low Light: {metrics.lowLightCount}</div>
            <div>Duration: {Math.floor(metrics.duration / 60)}:{(metrics.duration % 60).toString().padStart(2, '0')}</div>
          </div>
        </div>
      )}
    </div>
  )
}

export default VideoRecorder

