import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { DashboardPage } from './pages/DashboardPage'
import { useAuthStore } from './store/authStore'

function Private({ children }) {
  const { token } = useAuthStore()
  return token ? children : <Navigate to="/login" replace />
}
function Public({ children }) {
  const { token } = useAuthStore()
  return token ? <Navigate to="/" replace /> : children
}

export default function App() {
  const { token, fetchMe } = useAuthStore()
  useEffect(() => { if (token) fetchMe() }, [token])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login"    element={<Public><LoginPage /></Public>} />
        <Route path="/register" element={<Public><RegisterPage /></Public>} />
        <Route path="/"         element={<Private><DashboardPage /></Private>} />
        <Route path="*"         element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
