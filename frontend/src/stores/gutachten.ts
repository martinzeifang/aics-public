import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface GutachtenProjekt {
  id: string
  name: string
  frameworks: string[]
  pruefungsfokus: string
  meta: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface GutachtenFrage {
  id: number
  question_num: number
  framework: string
  section_ref: string
  thema: string
  frage: string
  antwort: string
  bewertung: string
  kommentar: string
  source_file?: string
}

export interface FragenPrompt {
  framework: string
  content: string
  filename: string
  section_count: number
}

export const useGutachtenStore = defineStore('gutachten', () => {
  const projekte = ref<GutachtenProjekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const fragen = ref<GutachtenFrage[]>([])
  const sectionsCount = ref<Record<string, number>>({})
  const draftPayload = ref<any | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  // ────── Projekte
  const fetchProjekte = async () => {
    loading.value = true
    try {
      const res = await apiClient.get('/gutachten/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<GutachtenProjekt>) => {
    try {
      const res = await apiClient.post('/gutachten', data)
      projekte.value.push(res.data)
      return res.data as GutachtenProjekt
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<GutachtenProjekt>) => {
    try {
      const res = await apiClient.put(`/gutachten/${encodeURIComponent(name)}`, data)
      const idx = projekte.value.findIndex(p => p.name === name)
      if (idx >= 0) projekte.value[idx] = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Aktualisieren'
      return null
    }
  }

  const deleteProjekt = async (name: string) => {
    try {
      await apiClient.delete(`/gutachten/${encodeURIComponent(name)}`)
      projekte.value = projekte.value.filter(p => p.name !== name)
      if (selectedProjekt.value === name) selectedProjekt.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  // ────── Fragen
  const fetchFragen = async (projekt: string) => {
    try {
      const res = await apiClient.get(`/gutachten/${encodeURIComponent(projekt)}/questions`)
      fragen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    }
  }

  const updateFrage = async (id: number, data: Partial<GutachtenFrage>) => {
    try {
      await apiClient.put(`/gutachten/questions/${id}`, data)
      const idx = fragen.value.findIndex(f => f.id === id)
      if (idx >= 0) fragen.value[idx] = { ...fragen.value[idx], ...data } as GutachtenFrage
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern'
      return false
    }
  }

  const deleteFrage = async (id: number) => {
    try {
      await apiClient.delete(`/gutachten/questions/${id}`)
      fragen.value = fragen.value.filter(f => f.id !== id)
      if (selectedProjekt.value) await fetchFragen(selectedProjekt.value)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  const addFrage = async (projekt: string, data: Partial<GutachtenFrage>) => {
    try {
      await apiClient.post(`/gutachten/${encodeURIComponent(projekt)}/questions`, data)
      await fetchFragen(projekt)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return false
    }
  }

  // ────── Sections
  const fetchSectionsCount = async () => {
    try {
      const res = await apiClient.get('/gutachten/sections/count')
      sectionsCount.value = res.data || {}
    } catch (err: any) {
      sectionsCount.value = {}
    }
  }

  // ────── Prompt-Generierung
  const buildFragenPrompt = async (projekt: string, batchSize = 15, testMode = false) => {
    try {
      const res = await apiClient.post(
        `/gutachten/${encodeURIComponent(projekt)}/fragen/prompt`,
        { batch_size: batchSize, test_mode: testMode },
        { timeout: 60000 },
      )
      return res.data as { prompts: FragenPrompt[]; frameworks: string[]; sections_total: number }
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler bei Prompt-Erstellung'
      return null
    }
  }

  const importFragen = async (projekt: string, raw: string, replace = false) => {
    try {
      const res = await apiClient.post(
        `/gutachten/${encodeURIComponent(projekt)}/fragen/import`,
        { raw, replace },
      )
      await fetchFragen(projekt)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Import fehlgeschlagen'
      return null
    }
  }

  // ────── Gutachten
  const buildGutachtenPrompt = async (projekt: string) => {
    try {
      const res = await apiClient.post(
        `/gutachten/${encodeURIComponent(projekt)}/gutachten/prompt`,
        {},
        { timeout: 60000 },
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler bei Prompt-Erstellung'
      return null
    }
  }

  const importGutachten = async (projekt: string, raw: string) => {
    try {
      const res = await apiClient.post(
        `/gutachten/${encodeURIComponent(projekt)}/gutachten/import`,
        { raw },
      )
      draftPayload.value = res.data.draft
      return res.data.draft
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Import fehlgeschlagen'
      return null
    }
  }

  const fetchDraft = async (projekt: string) => {
    try {
      const res = await apiClient.get(`/gutachten/${encodeURIComponent(projekt)}/gutachten/draft`)
      draftPayload.value = res.data.draft
      return res.data.draft
    } catch {
      draftPayload.value = null
      return null
    }
  }

  const saveDraft = async (projekt: string, draft: any) => {
    try {
      await apiClient.put(`/gutachten/${encodeURIComponent(projekt)}/gutachten/draft`, draft)
      draftPayload.value = draft
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern'
      return false
    }
  }

  return {
    projekte,
    selectedProjekt,
    selectedProjektObj,
    fragen,
    sectionsCount,
    draftPayload,
    loading,
    error,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchFragen,
    updateFrage,
    deleteFrage,
    addFrage,
    fetchSectionsCount,
    buildFragenPrompt,
    importFragen,
    buildGutachtenPrompt,
    importGutachten,
    fetchDraft,
    saveDraft,
  }
})
