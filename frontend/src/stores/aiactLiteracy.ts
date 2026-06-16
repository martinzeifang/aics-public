import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/aiact-literacy'

export interface LiteracyNachweis {
  id?: number
  rolle: string
  person: string
  schulungsmodul: string
  kompetenzlevel: string
  durchgefuehrt_am: string
  gueltig_bis: string
  nachweis_ref: string
  oversight_person: string
  kommentar: string
  ablauf_status?: string
}

export interface LiteracySummary {
  gesamt: number
  abgelaufen: number
  bald_faellig: number
  personen: number
}

export const useAiactLiteracyStore = defineStore('aiactLiteracy', () => {
  const konzept = ref<{ konzept: string; stand: string }>({ konzept: '', stand: '' })
  const nachweise = ref<LiteracyNachweis[]>([])
  const summary = ref<LiteracySummary | null>(null)
  const oversightPersonen = ref<string[]>([])
  const kompetenzlevel = ref<string[]>([])
  const loading = ref(false)
  const error = ref('')

  async function loadConstants() {
    try {
      const r = await apiClient.get(`${BASE}/constants`)
      kompetenzlevel.value = r.data?.kompetenzlevel || []
    } catch { /* ignore */ }
  }

  async function load(projekt: string) {
    loading.value = true
    error.value = ''
    try {
      const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/literacy`)
      konzept.value = r.data?.konzept || { konzept: '', stand: '' }
      nachweise.value = r.data?.nachweise || []
      summary.value = r.data?.summary || null
      oversightPersonen.value = r.data?.oversight_personen || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
    } finally {
      loading.value = false
    }
  }

  async function saveKonzept(projekt: string, text: string) {
    await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/konzept`, { konzept: text })
    await load(projekt)
  }

  async function saveNachweis(projekt: string, n: LiteracyNachweis) {
    await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/nachweise`, n)
    await load(projekt)
  }

  async function deleteNachweis(projekt: string, id: number) {
    await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/nachweise/${id}`)
    await load(projekt)
  }

  return {
    konzept, nachweise, summary, oversightPersonen, kompetenzlevel, loading, error,
    loadConstants, load, saveKonzept, saveNachweis, deleteNachweis,
  }
})
