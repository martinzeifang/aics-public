import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Backend mountet den Blueprint unter '/api/aiact-art5'.
const BASE = '/aiact-art5'

export interface Art5Befund {
  code: string
  kurz: string
  ref: string
  beschreibung: string
  betroffen: string
  begruendung: string
  geprueft_von: string
  geprueft_am: string
}

export interface Art5Summary {
  has_prohibited: boolean
  treffer: string[]
  complete: boolean
  offen: number
  gesamt: number
}

export const useAiactArt5Store = defineStore('aiactArt5', () => {
  const items = ref<Art5Befund[]>([])
  const summary = ref<Art5Summary | null>(null)
  const betroffenWerte = ref<string[]>([])
  const loading = ref(false)
  const error = ref('')

  async function loadCatalog() {
    try {
      const r = await apiClient.get(`${BASE}/catalog`)
      betroffenWerte.value = r.data?.betroffen || []
    } catch { /* ignore */ }
  }

  async function load(projekt: string) {
    loading.value = true
    error.value = ''
    try {
      const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/screening`)
      items.value = r.data?.items || []
      summary.value = r.data?.summary || null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
    } finally {
      loading.value = false
    }
  }

  async function saveBefund(projekt: string, code: string, payload: Partial<Art5Befund>) {
    const r = await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/screening/${code}`,
      payload,
    )
    summary.value = r.data?.summary || summary.value
    await load(projekt)
  }

  async function gate(projekt: string) {
    const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/gate`)
    return r.data
  }

  async function wizardPrompt(projekt: string): Promise<string> {
    const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/wizard/prompt`)
    return r.data?.prompt || ''
  }

  async function wizardParse(projekt: string, response: string, apply = true) {
    const r = await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/wizard/parse`,
      { response, apply },
    )
    if (apply) await load(projekt)
    return r.data
  }

  function exportUrl(projekt: string): string {
    return `/api${BASE}/projekte/${encodeURIComponent(projekt)}/export`
  }

  return {
    items, summary, betroffenWerte, loading, error,
    loadCatalog, load, saveBefund, gate, wizardPrompt, wizardParse, exportUrl,
  }
})
