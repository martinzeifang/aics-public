import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/nis2-fristen'

export interface FristItem {
  bereich: string
  ref: string
  titel: string
  quelle_feld: string
  ampel: 'grey' | 'green' | 'amber' | 'red'
  status: string
  due_at: string
  days_left: number | null
}

export interface FristenResult {
  items: FristItem[]
  counts: { ueberfaellig: number; faellig: number; on_track: number; grey: number }
  overall_ampel: 'grey' | 'green' | 'amber' | 'red'
}

export const useNis2FristenStore = defineStore('nis2Fristen', () => {
  const result = ref<FristenResult | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function fetchFristen(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      result.value = (await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/fristen`)).data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fristen konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  return { result, loading, error, fetchFristen }
})
