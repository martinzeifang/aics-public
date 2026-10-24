import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/cra-release'

export interface ReleaseSnapshot {
  id: number
  version: string
  grund: string
  eingefroren_am: string
}

export const useCraReleaseStore = defineStore('craRelease', () => {
  const release = ref<any>({})
  const snapshots = ref<ReleaseSnapshot[]>([])
  const reassessItems = ref<string[]>([])
  const error = ref<string | null>(null)

  async function fetch(projekt: string) {
    try {
      const { data } = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/release`)
      release.value = data || {}
      snapshots.value = data.snapshots || []
      reassessItems.value = data.reassess_items || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen'
    }
  }

  async function substantialModification(projekt: string, neueVersion: string, grund: string) {
    error.value = null
    try {
      const { data } = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/substantial-modification`,
        { neue_version: neueVersion, grund })
      release.value = data.release || {}
      snapshots.value = data.snapshots || []
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Aktion fehlgeschlagen'
      return false
    }
  }

  // #1666: einen Re-Assessment-Punkt nach der wesentlichen Änderung als erledigt markieren.
  async function setReassess(projekt: string, key: string, value: 'offen' | 'erledigt') {
    error.value = null
    const next = { ...(release.value.reassess || {}), [key]: value }
    try {
      const { data } = await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/release`,
        { aktuelle_version: release.value.aktuelle_version, reassess: next })
      release.value = { ...release.value, ...(data || {}), reassess: next }
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Aktion fehlgeschlagen'
      return false
    }
  }

  return { release, snapshots, reassessItems, error, fetch, substantialModification, setReassess }
})
