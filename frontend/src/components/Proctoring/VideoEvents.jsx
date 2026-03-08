import { useState, useCallback, useRef, useEffect } from 'react'
import { videoProctoringApi } from '../../api'

// Video event types matching backend
export const VideoEventType = {
  FACE_DETECTED: 'face_detected',
  FACE_LOST: 'face_lost',
  MULTIPLE_FACES: 'multiple_faces',
  LOW_LIGHT: 'low_light',
  DEVICE_CHANGE: 'device_change',
  SCREEN_CAPTURE: 'screen_capture',
  SESSION_START: 'session_start',
  SESSION_END: 'session_end',
}

export function useVideoProctoring(enabled = false) {
  const [sessionId, setSessionId] = useState(null)
  const [isActive, setIsActive] = useState(false)
  const [error, setError] = useState(null)
  const [metrics, setMetrics] = useState({
    faceDetectedCount: 0,
    faceLostCount: 0,
    multipleFacesDetectedCount: 0,
    lowLightCount: 0,
    deviceChangeCount: 0,
    screenCaptureDetected: false,
    noFaceDurationSeconds: 0,
    totalDurationSeconds: 0,
  })
  const [sessionStatus, setSessionStatus] = useState(null)

  const startTimeRef = useRef(null)
  const eventQueueRef = useRef([])
  const flushIntervalRef = useRef(null)
  const durationIntervalRef = useRef(null)

  // Start a new proctoring session
  const startSession = useCallback(async (submissionId = null, assignmentId = null) => {
    if (!enabled) return null

    try {
      setError(null)
      const response = await videoProctoringApi.startSession({
        submission_id: submissionId,
        assignment_id: assignmentId,
      })

      setSessionId(response.session_id)
      setIsActive(true)
      startTimeRef.current = Date.now()

      // Reset metrics
      setMetrics({
        faceDetectedCount: 0,
        faceLostCount: 0,
        multipleFacesDetectedCount: 0,
        lowLightCount: 0,
        deviceChangeCount: 0,
        screenCaptureDetected: false,
        noFaceDurationSeconds: 0,
        totalDurationSeconds: 0,
      })

      // Clear any existing intervals
      if (flushIntervalRef.current) {
        clearInterval(flushIntervalRef.current)
      }
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current)
      }

      // Start periodic flush of event queue
      flushIntervalRef.current = setInterval(() => {
        flushEventQueue()
      }, 5000)

      // Update duration every second using functional update to prevent stale closures
      let seconds = 0
      durationIntervalRef.current = setInterval(() => {
        seconds += 1
        setMetrics(prev => ({ ...prev, totalDurationSeconds: seconds }))
      }, 1000)

      return response.session_id
    } catch (err) {
      console.error('Failed to start video proctoring session:', err)
      setError(err.message || 'Failed to start session')
      return null
    }
  }, [enabled])

  // End the current session
  const endSession = useCallback(async () => {
    if (!sessionId) return null

    try {
      // Clear intervals
      if (flushIntervalRef.current) {
        clearInterval(flushIntervalRef.current)
        flushIntervalRef.current = null
      }

      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current)
        durationIntervalRef.current = null
      }

      // Flush remaining events
      await flushEventQueue()

      const response = await videoProctoringApi.endSession(sessionId)

      setIsActive(false)
      setSessionStatus(response)

      return response
    } catch (err) {
      console.error('Failed to end video proctoring session:', err)
      setError(err.message || 'Failed to end session')
      return null
    }
  }, [sessionId])

  // Report a video event
  const reportEvent = useCallback(async (eventType, durationSeconds = 0, metadata = {}) => {
    if (!enabled || !sessionId) return

    // Queue event for batch sending
    eventQueueRef.current.push({
      event_type: eventType,
      duration_seconds: durationSeconds,
      metadata,
    })

    // Update local metrics using functional update
    setMetrics(prev => {
      const newMetrics = { ...prev }

      switch (eventType) {
        case VideoEventType.FACE_DETECTED:
          newMetrics.faceDetectedCount += 1
          break
        case VideoEventType.FACE_LOST:
          newMetrics.faceLostCount += 1
          newMetrics.noFaceDurationSeconds += durationSeconds
          break
        case VideoEventType.MULTIPLE_FACES:
          newMetrics.multipleFacesDetectedCount += 1
          break
        case VideoEventType.LOW_LIGHT:
          newMetrics.lowLightCount += 1
          break
        case VideoEventType.DEVICE_CHANGE:
          newMetrics.deviceChangeCount += 1
          break
        case VideoEventType.SCREEN_CAPTURE:
          newMetrics.screenCaptureDetected = true
          break
      }

      return newMetrics
    })
  }, [enabled, sessionId])

  // Flush queued events to backend
  const flushEventQueue = useCallback(async () => {
    if (!sessionId || eventQueueRef.current.length === 0) return

    const events = [...eventQueueRef.current]
    eventQueueRef.current = []

    try {
      await Promise.all(
        events.map(event =>
          videoProctoringApi.reportEvent(sessionId, event)
        )
      )
    } catch (err) {
      console.error('Failed to flush video events:', err)
      // Re-queue failed events
      eventQueueRef.current = [...events, ...eventQueueRef.current]
    }
  }, [sessionId])

  // Get session status
  const getSessionStatus = useCallback(async () => {
    if (!sessionId) return null

    try {
      const status = await videoProctoringApi.getSessionStatus(sessionId)
      setSessionStatus(status)
      return status
    } catch (err) {
      console.error('Failed to get session status:', err)
      return null
    }
  }, [sessionId])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (flushIntervalRef.current) {
        clearInterval(flushIntervalRef.current)
      }
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current)
      }
    }
  }, [])

  return {
    sessionId,
    isActive,
    error,
    metrics,
    sessionStatus,
    startSession,
    endSession,
    reportEvent,
    getSessionStatus,
  }
}

// Component wrapper for VideoEvents
export function VideoEventsHandler({
  children,
  enabled = false,
  submissionId,
  assignmentId,
}) {
  const proctoring = useVideoProctoring(enabled)

  return children({
    ...proctoring,
    enabled,
    submissionId,
    assignmentId,
  })
}

export default useVideoProctoring

