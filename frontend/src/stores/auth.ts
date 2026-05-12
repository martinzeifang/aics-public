import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

interface User {
  id: string
  email: string
  roles: string[]
  permissions: string[]
  extra_permissions?: string[]
  allowed_modules?: string[] | null
  display_name?: string
  license_modules?: string[]  // #413: vom /auth/profile geliefert
  license_state?: any
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(sessionStorage.getItem('auth_token'))

  const isAuthenticated = computed(() => !!token.value && !!user.value)

  const hasPermission = (permission: string) => {
    if (!user.value) return false
    return user.value.permissions.includes(permission) ||
           user.value.permissions.includes(`${permission.split(':')[0]}:*`)
  }

  /** Erststufe: Email+Passwort. Bei aktivem 2FA wird ein `totp_required`-Flag
   * plus Challenge-Token zurückgegeben; das Frontend muss dann `verifyTotp()` aufrufen. */
  const login = async (email: string, password: string): Promise<
    { ok: true } | { ok: false; error: string } | { ok: 'totp_required'; challenge: string }
  > => {
    try {
      const response = await axios.post('/api/auth/login', { email, password }, {
        timeout: 30000,
        headers: { 'Content-Type': 'application/json' }
      })
      if (response.data?.totp_required) {
        return { ok: 'totp_required', challenge: response.data.challenge_token }
      }
      token.value = response.data.access_token
      user.value = response.data.user
      sessionStorage.setItem('auth_token', token.value)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      // #413: Login-Response enthält nicht license_modules — Profile nachladen
      await loadProfile()
      return { ok: true }
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message || 'Login failed'
      console.error('Login failed:', errorMsg, error)
      return { ok: false, error: errorMsg }
    }
  }

  /** Zweitstufe: Challenge-Token + TOTP-/Backup-Code → Access-Token. */
  const verifyTotp = async (challenge: string, code: string):
    Promise<{ ok: true } | { ok: false; error: string }> => {
    try {
      const response = await axios.post('/api/auth/login/verify-2fa',
        { challenge_token: challenge, code }, {
        timeout: 30000,
        headers: { 'Content-Type': 'application/json' }
      })
      token.value = response.data.access_token
      user.value = response.data.user
      sessionStorage.setItem('auth_token', token.value)
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      await loadProfile()
      return { ok: true }
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message || '2FA-Verifizierung fehlgeschlagen'
      return { ok: false, error: errorMsg }
    }
  }

  const logout = async () => {
    // Backend benachrichtigen, damit Token in Blacklist eingetragen wird
    if (token.value) {
      try {
        await axios.post('/api/auth/logout', {}, {
          headers: { 'Authorization': `Bearer ${token.value}` },
          timeout: 3000,
        })
      } catch {
        // Ignore — auch ohne Server-Response lokalen Logout durchführen
      }
    }
    token.value = null
    user.value = null
    sessionStorage.removeItem('auth_token')
    delete axios.defaults.headers.common['Authorization']
  }

  const loadProfile = async () => {
    if (!token.value) return false

    try {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
      const response = await axios.get('/api/auth/profile')
      user.value = response.data
      return true
    } catch (error) {
      logout()
      return false
    }
  }

  return {
    user,
    token,
    isAuthenticated,
    hasPermission,
    login,
    verifyTotp,
    logout,
    loadProfile
  }
})
