// #1410/#1412: Portal-Modus (SOC-Operations-Portal) — app-weit verfügbar.
//
// Liest die (pre-auth lesbare) Public-Config einmalig beim App-Start. Steuert
// Modul-Gating (nur SOC sichtbar), Routing-Redirect, Login-/Shell-Branding und den
// Admin-Schalter (portal_enabled, #1474). Im Suite-Modus bleibt alles unverändert.
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const usePortalStore = defineStore('portal', () => {
  const portal = ref<'suite' | 'soc'>('suite')
  const portalName = ref('AI Compliance Suite')
  const portalModules = ref<string[]>([])
  const portalEnabled = ref(true)
  const loaded = ref(false)

  async function load() {
    try {
      const r = await axios.get('/api/auth/public-config', { timeout: 5000 })
      portal.value = r.data?.portal === 'soc' ? 'soc' : 'suite'
      portalName.value = r.data?.portal_name || portalName.value
      portalModules.value = Array.isArray(r.data?.portal_modules) ? r.data.portal_modules : []
      portalEnabled.value = r.data?.portal_enabled !== false
    } catch {
      // best-effort: bei Fehler bleibt Suite-Default (keine Einschränkung)
    } finally {
      loaded.value = true
    }
  }

  const isSoc = computed(() => portal.value === 'soc')
  // Portal nutzbar = im Portal-Modus + vom Admin aktiviert (Suite immer true).
  const isActive = computed(() => !isSoc.value || portalEnabled.value)

  return { portal, portalName, portalModules, portalEnabled, loaded, load, isSoc, isActive }
})
