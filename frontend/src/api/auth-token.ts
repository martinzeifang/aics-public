/**
 * Zentraler Zugriff auf das Auth-Token (#1190).
 *
 * Komponenten dürfen NICHT direkt auf `sessionStorage`/`localStorage` zugreifen, um das
 * Token zu lesen. Streaming-/SSE-/Download-Flows, die nicht über den axios-`apiClient`
 * (mit Request-Interceptor) laufen, holen das Bearer-Token ausschließlich hier.
 *
 * Dies ist der EINZIGE Ort, der beim Wechsel auf HttpOnly/SameSite-Cookies (Zielbild)
 * angepasst werden muss — siehe docs/security/token-storage.md.
 */
import { useAuthStore } from '../stores/auth'

export function bearerToken(): string {
  try {
    return useAuthStore().token || ''
  } catch {
    return ''
  }
}

export function authHeader(): Record<string, string> {
  const t = bearerToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}
