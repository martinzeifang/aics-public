import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

/**
 * aiProvider-Store (#1342, Defekt A) — Single Source of Truth für den aktiven
 * KI-Provider-Status (GET /api/ai/provider-status).
 *
 * Die Topbar-Badge (AIProviderBadge.vue) liest reaktiv aus diesem Store, statt
 * den Status nur einmalig in onMounted lokal zu laden. Nach einem Provider-
 * Wechsel in den Einstellungen ruft der Speichern-Flow loadStatus() auf, sodass
 * die Badge ohne harten Browser-Reload aktualisiert.
 */
export interface ProviderStatus {
  provider: 'on_prem' | 'cloud' | 'none'
  label: string
  configured: boolean
  allow_data_egress: boolean
}

export const useAiProviderStore = defineStore('aiProvider', () => {
  const status = ref<ProviderStatus | null>(null)
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  const loadStatus = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get<ProviderStatus>('/ai/provider-status')
      status.value = res.data
      loaded.value = true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'KI-Provider-Status konnte nicht geladen werden'
    } finally {
      loading.value = false
    }
  }

  return {
    status,
    loading,
    loaded,
    error,
    loadStatus,
  }
})
