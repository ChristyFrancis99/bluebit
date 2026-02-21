import { useEffect, useRef, useState, useCallback } from 'react'
import { createSubmissionWS } from '../api'

export function useSubmissionWS(submissionId) {
  const [events, setEvents] = useState([])
  const [moduleResults, setModuleResults] = useState({})
  const [completed, setCompleted] = useState(false)
  const [finalScore, setFinalScore] = useState(null)
  const [wsStatus, setWsStatus] = useState('idle') // idle|connecting|open|closed
  const wsRef = useRef(null)

  useEffect(() => {
    if (!submissionId) return
    setWsStatus('connecting')

    const ws = createSubmissionWS(submissionId, (event) => {
      setEvents(prev => [...prev, event])
      if (event.type === 'module_complete') {
        setModuleResults(prev => ({
          ...prev,
          [event.module_id]: {
            score: event.score,
            confidence: event.confidence,
            status: event.status,
            processing_ms: event.processing_ms,
          },
        }))
      }
      if (event.type === 'completed') {
        setCompleted(true)
        setFinalScore({ score: event.integrity_score, risk: event.risk_level })
        setWsStatus('closed')
      }
    })

    ws.onopen  = () => setWsStatus('open')
    ws.onclose = () => setWsStatus('closed')
    wsRef.current = ws
    return () => { ws.close(); setWsStatus('idle') }
  }, [submissionId])

  const reset = useCallback(() => {
    wsRef.current?.close()
    setEvents([]); setModuleResults({}); setCompleted(false); setFinalScore(null); setWsStatus('idle')
  }, [])

  return { events, moduleResults, completed, finalScore, wsStatus, reset }
}
