import { useState, useRef, useEffect, useCallback } from 'react'
import { Camera, CameraOff, AlertTriangle, CheckCircle, XCircle, Video, VideoOff, FileScan } from 'lucide-react'

// Video event types matching backend
const VideoEventType = {
  FACE_DETECTED: 'face_detected',
  FACE_LOST: 'face_lost',
  MULTIPLE_FACES: 'multiple_faces',
  LOW_LIGHT: 'low_light',
  DEVICE_CHANGE: 'device_change',
  SCREEN_CAPTURE: 'screen_capture',
  DOCUMENT_DETECTED: 'document_detected',
  SESSION_START: 'session_start',
  SESSION_END: 'session_end',
}

export function VideoRecorder({
  onSessionStart,
  onSessionEnd,
  onEvent,
  sessionId,
  enabled = true,
  documentScanningEnabled = false,
  onDocumentScan = null,
}) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const canvasRef = useRef(null)
  const overlayCanvasRef = useRef(null)
  const animationFrameRef = useRef(null)
  const lastDetectionTimeRef = useRef(0)
  const lastDocumentScanTimeRef = useRef(0)
  const timerIntervalRef = useRef(null)
  const lastFaceDetectedRef = useRef(true)
  const lastFaceLostTimeRef = useRef(null)
  const faceHistoryRef = useRef([])

  const [isActive, setIsActive] = useState(false)
  const [cameraOn, setCameraOn] = useState(true)
  const [scanningMode, setScanningMode] = useState('face')
  const [error, setError] = useState(null)
  const [status, setStatus] = useState('idle')
  const [brightness, setBrightness] = useState(100)
  const [faceBox, setFaceBox] = useState(null)
  const [lastScannedDocument, setLastScannedDocument] = useState(null)
  const [metrics, setMetrics] = useState({
    faceDetected: false,
    faceLostCount: 0,
    multipleFacesCount: 0,
    lowLightCount: 0,
    deviceChangeCount: 0,
    documentsScanned: 0,
    duration: 0,
  })

  // Improved skin detection with ellipse-based face region analysis
  const detectFaceRegion = useCallback((imageData, width, height) => {
    const data = imageData.data

    // Calculate center region (where face is expected)
    const centerX = width / 2
    const centerY = height / 2
    const regionWidth = width * 0.4
    const regionHeight = height * 0.4

    let skinPixels = 0
    let totalPixels = 0
    let totalBrightness = 0

    // Analyze center region with ellipse mask
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        // Skip pixels outside ellipse
        const dx = (x - centerX) / (regionWidth / 2)
        const dy = (y - centerY) / (regionHeight / 2)
        if (dx * dx + dy * dy > 1) continue

        const i = (y * width + x) * 4
        const r = data[i]
        const g = data[i + 1]
        const b = data[i + 2]

        totalBrightness += (r + g + b) / 3
        totalPixels++

        // Improved skin detection using RGB and HSV-like rules
        const isSkin = (
          r > 95 && g > 40 && b > 20 &&
          r > g && r > b &&
          Math.abs(r - g) > 15 &&
          r - b > 15 &&
          (r - g) <= 100 &&
          r > 100
        )

        if (isSkin) skinPixels++
      }
    }

    const avgBrightness = totalPixels > 0 ? totalBrightness / totalPixels : 0
    const skinRatio = totalPixels > 0 ? skinPixels / totalPixels : 0

    // Check if face is likely present
    const faceDetected = skinRatio > 0.08 && avgBrightness >= 50 && avgBrightness <= 220
    const isLowLight = avgBrightness < 50

    // Estimate face bounding box if detected
    let box = null
    if (faceDetected) {
      box = {
        x: centerX - regionWidth / 2,
        y: centerY - regionHeight / 2,
        width: regionWidth,
        height: regionHeight,
        confidence: Math.min(skinRatio * 3, 0.95),
      }
    }

    return {
      faceDetected,
      isLowLight,
      brightness: avgBrightness,
      skinRatio,
      box,
    }
  }, [])

  // Process video frame
  const processFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) {
      animationFrameRef.current = requestAnimationFrame(processFrame)
      return
    }

    const video = videoRef.current

    if (video.readyState !== 4) {
      animationFrameRef.current = requestAnimationFrame(processFrame)
      return
    }

    // Limit to ~15 FPS
    const now = Date.now()
    const elapsed = now - lastDetectionTimeRef.current
    if (elapsed < 66) {
      animationFrameRef.current = requestAnimationFrame(processFrame)
      return
    }
    lastDetectionTimeRef.current = now

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d', { willReadFrequently: true })

    // Use actual video dimensions
    const width = Math.min(video.videoWidth || 320, 320)
    const height = Math.min(video.videoHeight || 240, 240)

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width
      canvas.height = height
    }

    // Draw and get image data
    ctx.drawImage(video, 0, 0, width, height)
    const imageData = ctx.getImageData(0, 0, width, height)

    // Run face detection
    const result = detectFaceRegion(imageData, width, height)

    setBrightness(Math.round(result.brightness))
    setFaceBox(result.box)

    // Smooth detection using history
    faceHistoryRef.current.push(result.faceDetected)
    if (faceHistoryRef.current.length > 5) {
      faceHistoryRef.current.shift()
    }

    // Require 2 out of 3 consecutive detections for stability
    const recentHistory = faceHistoryRef.current.slice(-3)
    const stableDetection = recentHistory.filter(d => d).length >= 2

    // Face state changes
    if (stableDetection && !lastFaceDetectedRef.current) {
      if (lastFaceLostTimeRef.current) {
        const duration = (Date.now() - lastFaceLostTimeRef.current) / 1000
        onEvent?.(VideoEventType.FACE_DETECTED, { duration })
      }
      lastFaceDetectedRef.current = true
      lastFaceLostTimeRef.current = null
      setMetrics(prev => ({ ...prev, faceDetected: true }))
    } else if (!stableDetection && lastFaceDetectedRef.current) {
      onEvent?.(VideoEventType.FACE_LOST, { duration: 2 })
      lastFaceDetectedRef.current = false
      lastFaceLostTimeRef.current = Date.now()
      setMetrics(prev => ({ ...prev, faceDetected: false, faceLostCount: prev.faceLostCount + 1 }))
    }

    // Low light
    if (result.isLowLight && result.brightness < 50) {
      setMetrics(prev => ({ ...prev, lowLightCount: prev.lowLightCount + 1 }))
      onEvent?.(VideoEventType.LOW_LIGHT, { brightness: result.brightness })
    }

    // Document scanning (every 1 second)
    if (scanningMode === 'document' || documentScanningEnabled) {
      if (now - lastDocumentScanTimeRef.current > 1000) {
        lastDocumentScanTimeRef.current = now

        // Resize for document
        canvas.width = 640
        canvas.height = 480
        ctx.drawImage(video, 0, 0, 640, 480)

        // Convert to grayscale
        const grayData = ctx.getImageData(0, 0, 640, 480)
        const data = grayData.data
        for (let i = 0; i < data.length; i += 4) {
          const avg = (data[i] + data[i + 1] + data[i + 2]) / 3
          data[i] = data[i + 1] = data[i + 2] = avg
        }
        ctx.putImageData(grayData, 0, 0)

        const imageDataBase64 = canvas.toDataURL('image/jpeg', 0.6)

        setMetrics(prev => ({ ...prev, documentsScanned: prev.documentsScanned + 1 }))
        setLastScannedDocument({ timestamp: now, preview: imageDataBase64 })

        if (onDocumentScan) {
          onDocumentScan(imageDataBase64)
        }

        onEvent?.(VideoEventType.DOCUMENT_DETECTED, { timestamp: now })
      }
    }

    animationFrameRef.current = requestAnimationFrame(processFrame)
  }, [scanningMode, documentScanningEnabled, onEvent, onDocumentScan, detectFaceRegion])

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
        audio: false,
      })

      streamRef.current = stream

      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }

      setStatus('active')
      setIsActive(true)
      setCameraOn(true)

      // Initialize history
      faceHistoryRef.current = []

      // Start processing
      processFrame()

      // Start duration timer
      let seconds = 0
      timerIntervalRef.current = setInterval(() => {
        seconds += 1
        setMetrics(prev => ({ ...prev, duration: seconds }))
      }, 1000)

    } catch (err) {
      console.error('Camera error:', err)
      setError(err.message || 'Failed to access camera')
      setStatus('error')
    }
  }, [enabled, processFrame])

  // Stop camera
  const stopCamera = useCallback(async () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }

    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }

    setIsActive(false)
    setStatus('idle')
    setFaceBox(null)
    setLastScannedDocument(null)
    faceHistoryRef.current = []
    lastFaceDetectedRef.current = true
    lastFaceLostTimeRef.current = null
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

  // Toggle scanning mode
  const toggleScanningMode = useCallback(() => {
    setScanningMode(prev => prev === 'face' ? 'document' : 'face')
  }, [])

  // Draw bounding box
  useEffect(() => {
    if (!overlayCanvasRef.current || !videoRef.current) return

    const canvas = overlayCanvasRef.current
    const ctx = canvas.getContext('2d')

    canvas.width = videoRef.current.videoWidth || 320
    canvas.height = videoRef.current.videoHeight || 240

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (faceBox && scanningMode === 'face') {
      const { x, y, width, height, confidence } = faceBox

      ctx.strokeStyle = confidence > 0.3 ? '#00ff88' : '#ffaa00'
      ctx.lineWidth = 2
      ctx.strokeRect(x, y, width, height)

      ctx.fillStyle = confidence > 0.3 ? 'rgba(0,255,136,0.2)' : 'rgba(255,170,0,0.2)'
      ctx.fillRect(x, y, width, height)

      ctx.fillStyle = '#fff'
      ctx.font = '12px DM Mono'
      ctx.fillText(`${Math.round(confidence * 100)}%`, x, y - 5)
    }
  }, [faceBox, scanningMode])

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
      {/* Hidden canvas */}
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
            transform: 'scaleX(-1)',
            display: isActive ? 'block' : 'none',
          }}
        />

        {/* Face detection overlay */}
        <canvas
          ref={overlayCanvasRef}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
            transform: 'scaleX(-1)',
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

        {/* Face detection status */}
        {isActive && scanningMode === 'face' && (
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

        {/* Brightness indicator */}
        {isActive && (
          <div style={{
            position: 'absolute',
            top: 8,
            right: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '4px 8px',
            borderRadius: 4,
            background: brightness >= 50 ? 'rgba(0,200,100,0.8)' : 'rgba(255,170,0,0.8)',
            fontSize: 10,
            fontFamily: 'DM Mono, monospace',
          }}>
            ☀ {brightness}%
          </div>
        )}

        {/* Document scanning indicator */}
        {isActive && (scanningMode === 'document' || documentScanningEnabled) && (
          <div style={{
            position: 'absolute',
            bottom: 8,
            left: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 8px',
            borderRadius: 4,
            background: 'rgba(0,150,255,0.8)',
            fontSize: 10,
            fontFamily: 'DM Mono, monospace',
          }}>
            <FileScan size={12} />
            Doc Scan: {metrics.documentsScanned}
          </div>
        )}
      </div>

      {/* Controls */}
      <div style={{
        display: 'flex',
        gap: 8,
        justifyContent: 'center',
        flexWrap: 'wrap',
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

            {documentScanningEnabled && (
              <button
                onClick={toggleScanningMode}
                className="btn-ghost"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: 11,
                  padding: '8px 12px',
                }}
              >
                <FileScan size={14} />
                {scanningMode === 'face' ? 'Face Mode' : 'Doc Mode'}
              </button>
            )}

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
            <div>Docs Scanned: {metrics.documentsScanned}</div>
            <div style={{ gridColumn: '1 / -1' }}>
              Duration: {Math.floor(metrics.duration / 60)}:{(metrics.duration % 60).toString().padStart(2, '0')}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default VideoRecorder


