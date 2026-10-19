/**
 * Globaler 401-Interceptor (#414).
 *
 * Wird beim App-Boot installiert und gilt für:
 *  - axios (raw) — z.B. die meisten Stores
 *  - apiClient — der App-eigene Wrapper
 *
 * Bei 401:
 *  1. authStore.logout() → token + user clearen
 *  2. router.push('/login') statt window.location (kein Reload, kein Flackern)
 *
 * Da App.vue an `authStore.isAuthenticated` bindet (v-if), verschwindet
 * AppLayout sofort sobald der Store gecleart ist.
 *
 * Endlosschleife-Schutz: 401 vom Login/Refresh selbst wird ignoriert.
 */

import axios, { type AxiosInstance } from 'axios'
import type { Router } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const SAFE_PATHS = ['/api/auth/login', '/api/auth/login/verify-2fa', '/api/auth/refresh',
                    // #1049: Logout-Call selbst darf kein rekursives 401-Handling auslösen
                    '/api/auth/logout']

function isSafe401(url: string | undefined): boolean {
  if (!url) return false
  return SAFE_PATHS.some(p => url.includes(p))
}

let installed = false

export function install401Interceptor(router: Router, ...instances: AxiosInstance[]): void {
  if (installed) return
  installed = true

  const handler = (instance: AxiosInstance) => {
    instance.interceptors.response.use(
      r => r,
      (error) => {
        const status = error?.response?.status
        const url = error?.config?.url
        if (status === 401 && !isSafe401(url)) {
          try {
            const auth = useAuthStore()
            auth.logout()
          } catch { /* store ggf. noch nicht initialisiert */ }
          if (router.currentRoute.value.path !== '/login') {
            router.push('/login')
          }
        }
        return Promise.reject(error)
      },
    )
  }

  handler(axios)
  for (const i of instances) handler(i)
}
