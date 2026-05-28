import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import {
  startAuthentication,
  browserSupportsWebAuthn,
} from '@simplewebauthn/browser'

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

interface MfaStatus {
  required?: boolean
  satisfied?: boolean
  grace_until?: number
  grace_expired?: boolean
  setup_required?: boolean
  recommended?: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(sessionStorage.getItem('auth_token'))
  const mfaStatus = ref<MfaStatus | null>(null)

  const isAuthenticated = computed(() => !!token.value && !!user.value)

  const hasPermission = (permission: string) => {
    if (!user.value) return false
    return user.value.permissions.includes(permission) ||
           user.value.permissions.includes(`${permission.split(':')[0]}:*`)
  }

  /** Setzt Token + User aus einer Login-Response und lädt das Profil nach. */
  const _finishLogin = async (data: any) => {
    token.value = data.access_token
    user.value = data.user
    mfaStatus.value = data.mfa || null  // Sprint ε Phase D
    sessionStorage.setItem('auth_token', token.value as string)
    axios.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
    // #413: Login-Response enthält nicht license_modules — Profile nachladen
    await loadProfile()
  }

  /** Erststufe: Email+Passwort. Bei aktivem 2FA wird ein `totp_required`-Flag
   * plus Challenge-Token + verfügbare Methoden zurückgegeben; das Frontend ruft
   * dann `verifyTotp()` (Code) oder `verifyPasskey()` (Passkey als 2. Faktor) auf. */
  const login = async (email: string, password: string): Promise<
    { ok: true } | { ok: false; error: string }
    | { ok: 'totp_required'; challenge: string; methods: string[] }
  > => {
    try {
      const response = await axios.post('/api/auth/login', { email, password }, {
        timeout: 30000,
        headers: { 'Content-Type': 'application/json' }
      })
      if (response.data?.totp_required) {
        return {
          ok: 'totp_required',
          challenge: response.data.challenge_token,
          methods: response.data.methods || ['totp'],
        }
      }
      await _finishLogin(response.data)
      return { ok: true }
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message || 'Login failed'
      console.error('Login failed:', errorMsg, error)
      return { ok: false, error: errorMsg }
    }
  }

  const passkeySupported = () => browserSupportsWebAuthn()

  /** Passwortloser Login per Passkey (discoverable credential). */
  const loginWithPasskey = async ():
    Promise<{ ok: true } | { ok: false; error: string }> => {
    try {
      const optRes = await axios.post('/api/auth/webauthn/login/options', {}, { timeout: 30000 })
      const { challenge_id, options } = optRes.data
      const assertion = await startAuthentication(options)
      const verifyRes = await axios.post('/api/auth/webauthn/login/verify',
        { challenge_id, credential: assertion }, { timeout: 30000 })
      await _finishLogin(verifyRes.data)
      return { ok: true }
    } catch (error: any) {
      if (error?.name === 'NotAllowedError' || error?.name === 'AbortError') {
        return { ok: false, error: 'Vorgang abgebrochen.' }
      }
      return { ok: false, error: error.response?.data?.error || error.message || 'Passkey-Login fehlgeschlagen' }
    }
  }

  /** Zweitstufe via Passkey: Challenge-Token (aus Passwort-Schritt) → Access-Token. */
  const verifyPasskey = async (challengeToken: string):
    Promise<{ ok: true } | { ok: false; error: string }> => {
    try {
      const optRes = await axios.post('/api/auth/webauthn/login/2fa-options',
        { challenge_token: challengeToken }, { timeout: 30000 })
      const { challenge_id, options } = optRes.data
      const assertion = await startAuthentication(options)
      const verifyRes = await axios.post('/api/auth/webauthn/login/2fa-verify',
        { challenge_token: challengeToken, challenge_id, credential: assertion }, { timeout: 30000 })
      await _finishLogin(verifyRes.data)
      return { ok: true }
    } catch (error: any) {
      if (error?.name === 'NotAllowedError' || error?.name === 'AbortError') {
        return { ok: false, error: 'Vorgang abgebrochen.' }
      }
      return { ok: false, error: error.response?.data?.error || error.message || 'Passkey-Verifizierung fehlgeschlagen' }
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
      await _finishLogin(response.data)
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
    mfaStatus.value = null
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
    mfaStatus,
    isAuthenticated,
    hasPermission,
    login,
    verifyTotp,
    loginWithPasskey,
    verifyPasskey,
    passkeySupported,
    logout,
    loadProfile
  }
})
