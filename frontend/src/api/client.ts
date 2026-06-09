import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const apiClient = axios.create({
  baseURL: '/api',
  // 10s war zu knapp: das SPA feuert beim Projekt-/Tab-Wechsel ~10 parallele
  // Calls; unter Last (v.a. der Dev-Server) brauchen spätere Requests mehrere
  // Sekunden → liefen sonst in Status-0/Timeout (Dropdown/Nachweis lud nicht).
  // In Produktion sind Requests <1s, daher unkritisch.
  timeout: 30000,
})

// Request interceptor to add token
apiClient.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
}, (error) => {
  return Promise.reject(error)
})

// 401 wird global in main.ts via install401Interceptor() behandelt —
// hier nur Request-Header-Setup.

export default apiClient
