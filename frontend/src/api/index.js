import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', timeout: 30000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }).then(r => r.data),
  register: (data) => api.post('/auth/register', data).then(r => r.data),
  me: () => api.get('/auth/me').then(r => r.data),
}

export const submissionsApi = {
  create: (formData) => api.post('/submissions', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data),
  list: (params) => api.get('/submissions', { params }).then(r => r.data),
  getStatus: (id) => api.get(`/submissions/${id}/status`).then(r => r.data),
  getReport: (id) => api.get(`/submissions/${id}/report`).then(r => r.data),
}

export const modulesApi = {
  list: () => api.get('/modules').then(r => r.data),
  toggle: (moduleId, enabled) => api.put(`/modules/${moduleId}/toggle`, { enabled }).then(r => r.data),
}

export const adminApi = {
  getConfig: () => api.get('/admin/config').then(r => r.data),
  updateWeights: (weights, apply_to = 'institution') =>
    api.put('/admin/weights', { weights, apply_to }).then(r => r.data),
  getStats: () => api.get('/admin/stats').then(r => r.data),
  getAuditLog: (limit = 50) => api.get('/admin/audit-log', { params: { limit } }).then(r => r.data),
}

export const videoProctoringApi = {
  // Sessions
  startSession: (data) => api.post('/video-proctoring/sessions', data).then(r => r.data),
  endSession: (sessionId) => api.delete(`/video-proctoring/sessions/${sessionId}`).then(r => r.data),
  getSessionStatus: (sessionId) => api.get(`/video-proctoring/sessions/${sessionId}`).then(r => r.data),
  
  // Events
  reportEvent: (sessionId, eventData) => 
    api.post(`/video-proctoring/sessions/${sessionId}/events`, eventData).then(r => r.data),
  
  // Video Upload for Analysis
  analyzeVideo: (formData) => api.post('/video-proctoring/analyze-video', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data),
  
  analyzeVideoUrl: (videoUrl, submissionId = null) => 
    api.post('/video-proctoring/analyze-video-url', { video_url: videoUrl, submission_id: submissionId }).then(r => r.data),
  
  // WebSocket
  createSessionWS: (sessionId) => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return new WebSocket(`${proto}://${location.host}/api/v1/video-proctoring/ws/sessions/${sessionId}`)
  },
}

export const createSubmissionWS = (submissionId, onEvent) => {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/submissions/${submissionId}`)
  ws.onmessage = (e) => { try { onEvent(JSON.parse(e.data)) } catch {} }
  ws.onerror = (e) => console.error('WS error', e)
  return ws
}

export default api
