import { create } from 'zustand'
import { authApi } from '../api'

export const useAuthStore = create((set, get) => ({
  user: null,
  token: localStorage.getItem('token'),
  loading: false,
  error: null,

  login: async (email, password) => {
    set({ loading: true, error: null })
    try {
      const data = await authApi.login(email, password)
      localStorage.setItem('token', data.access_token)
      set({ token: data.access_token, user: data, loading: false })
      return data
    } catch (err) {
      set({ error: err.response?.data?.detail || 'Login failed', loading: false })
      throw err
    }
  },

  register: async (formData) => {
    set({ loading: true, error: null })
    try {
      const data = await authApi.register(formData)
      localStorage.setItem('token', data.access_token)
      set({ token: data.access_token, user: data, loading: false })
      return data
    } catch (err) {
      set({ error: err.response?.data?.detail || 'Registration failed', loading: false })
      throw err
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ user: null, token: null })
  },

  fetchMe: async () => {
    try {
      const user = await authApi.me()
      set({ user })
    } catch {
      get().logout()
    }
  },
}))
