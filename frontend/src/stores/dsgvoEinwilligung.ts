import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export interface DsgvoEinwilligung {
  id: number
  projekt_name: string
  einwilligung_id: string
  zweck: string
  text_version: string
  einwilligung_text: string
  zeitpunkt: string
  kanal: string
  betroffener_quelle: string
  widerruf_zeitpunkt: string
  status: 'aktiv' | 'widerrufen' | 'abgelaufen' | string
  created_at?: string
  updated_at?: string
}

const BASE = 'dsgvo-einwilligung'

export const useDsgvoEinwilligungStore = defineStore('dsgvoEinwilligung', () => {
  const items = ref<DsgvoEinwilligung[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchEinwilligungen(projekt: string): Promise<void> {
    if (!projekt) return
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/einwilligungen`,
      )
      items.value = data.items || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
      items.value = []
    } finally {
      loading.value = false
    }
  }

  async function createEinwilligung(
    projekt: string,
    payload: Partial<DsgvoEinwilligung>,
  ): Promise<boolean> {
    error.value = null
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/einwilligungen`,
        payload,
      )
      await fetchEinwilligungen(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function updateEinwilligung(
    projekt: string,
    einwilligungId: string,
    payload: Partial<DsgvoEinwilligung>,
  ): Promise<boolean> {
    error.value = null
    try {
      await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/einwilligungen/${encodeURIComponent(einwilligungId)}`,
        payload,
      )
      await fetchEinwilligungen(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function widerrufEinwilligung(
    projekt: string,
    einwilligungId: string,
  ): Promise<boolean> {
    error.value = null
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/einwilligungen/${encodeURIComponent(einwilligungId)}/widerruf`,
        {},
      )
      await fetchEinwilligungen(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Widerruf fehlgeschlagen.'
      return false
    }
  }

  async function deleteEinwilligung(
    projekt: string,
    einwilligungId: string,
  ): Promise<boolean> {
    error.value = null
    try {
      await apiClient.delete(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/einwilligungen/${encodeURIComponent(einwilligungId)}`,
      )
      await fetchEinwilligungen(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function importCsv(
    projekt: string,
    csv: string,
  ): Promise<{ imported: number; skipped: number } | null> {
    error.value = null
    try {
      const { data } = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/einwilligungen/import`,
        { csv },
      )
      await fetchEinwilligungen(projekt)
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Import fehlgeschlagen.'
      return null
    }
  }

  return {
    items,
    loading,
    error,
    fetchEinwilligungen,
    createEinwilligung,
    updateEinwilligung,
    widerrufEinwilligung,
    deleteEinwilligung,
    importCsv,
  }
})
