import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/nis2-dvo'

export interface DvoControl {
  id: string
  kapitel: string
  ref: string
  titel: string
  beschreibung: string
}

export interface DvoStatus {
  sektor: string
  relevant: boolean
  aktiv: boolean
  anzahl_controls: number
  controls: DvoControl[]
}

export interface Schwellenwert {
  diensttyp: string
  kriterien: string[]
}

export const useNis2DvoStore = defineStore('nis2Dvo', () => {
  const status = ref<DvoStatus | null>(null)
  const schwellenwerte = ref<Schwellenwert[]>([])
  const loading = ref(false)
  const error = ref('')

  async function fetchSchwellenwerte() {
    if (schwellenwerte.value.length) return
    try {
      schwellenwerte.value = (await apiClient.get(`${BASE}/schwellenwerte`)).data?.schwellenwerte || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Schwellenwerte konnten nicht geladen werden.'
    }
  }

  async function fetchStatus(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      status.value = (await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/status`)).data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Status konnte nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function activate(projekt: string): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/activate`)
      await fetchStatus(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Aktivierung fehlgeschlagen.'
      return false
    }
  }

  async function deactivate(projekt: string): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/deactivate`)
      await fetchStatus(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Deaktivierung fehlgeschlagen.'
      return false
    }
  }

  return { status, schwellenwerte, loading, error, fetchSchwellenwerte, fetchStatus, activate, deactivate }
})
