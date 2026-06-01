import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 10000,
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
