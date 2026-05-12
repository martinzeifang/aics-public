import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface AIActProjekt {
  id: string
  name: string
  organisation: string
  company: string
  produkt: string
  beschreibung: string
  description: string
  meta?: string
  created_at?: string
  updated_at?: string
}

export interface AIActAnforderung {
  id: string
  kapitel: string
  titel: string
  title?: string
  beschreibung: string
  description?: string
  hinweise: string
  guidance: string
  evidence: string[]
  rubric: any
  ref: string
  gewichtung: number
  owasp_llm: Array<{ id: string; title: string; ref: string }>
  bewertung: number
  score?: number
  kommentar: string
  notes?: string
  massnahme: string
  verantwortlich: string
  zieldatum: string
  status: 'pending' | 'partial' | 'complete'
}

export const useAiActStore = defineStore('aiact', () => {
  const projekte = ref<AIActProjekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const anforderungen = ref<AIActAnforderung[]>([])
  const reifegrad = ref<any>(null)
  const owaspLlm = ref<any | null>(null)
  const repoSuggestions = ref<any[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/aiact/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<AIActProjekt>) => {
    try {
      const res = await apiClient.post('/aiact/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<AIActProjekt>) => {
    try {
      const res = await apiClient.put(`/aiact/projekte/${encodeURIComponent(name)}`, data)
      const idx = projekte.value.findIndex(p => p.name === name)
      if (idx >= 0) projekte.value[idx] = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return null
    }
  }

  const deleteProjekt = async (name: string) => {
    try {
      await apiClient.delete(`/aiact/projekte/${encodeURIComponent(name)}`)
      projekte.value = projekte.value.filter(p => p.name !== name)
      if (selectedProjekt.value === name) selectedProjekt.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  const fetchAnforderungen = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/aiact/projekte/${encodeURIComponent(projektName)}/anforderungen`)
      anforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    }
  }

  const saveBewertung = async (projektName: string, anforderungId: string, payload: any) => {
    try {
      await apiClient.post(`/aiact/projekte/${encodeURIComponent(projektName)}/bewertungen`, {
        anforderung_id: anforderungId,
        bewertung: payload.bewertung ?? payload.score ?? 0,
        kommentar: payload.kommentar ?? '',
        massnahme: payload.massnahme ?? '',
      })
      const idx = anforderungen.value.findIndex(a => a.id === anforderungId)
      if (idx >= 0) {
        anforderungen.value[idx] = { ...anforderungen.value[idx], ...payload }
      }
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern'
      return false
    }
  }

  const fetchReifegrad = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/aiact/projekte/${encodeURIComponent(projektName)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Reifegrad'
    }
  }

  const fetchOwaspLlm = async () => {
    if (owaspLlm.value) return owaspLlm.value
    try {
      const res = await apiClient.get('/aiact/owasp-llm')
      owaspLlm.value = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return null
    }
  }

  const repoScan = async (projektName: string, repo: string, branch: string = '') => {
    try {
      const res = await apiClient.post(
        `/aiact/projekte/${encodeURIComponent(projektName)}/repo-scan`,
        { repo, branch },
      )
      repoSuggestions.value = res.data.suggestions || []
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Repo-Scan'
      return null
    }
  }

  return {
    projekte,
    selectedProjekt,
    selectedProjektObj,
    anforderungen,
    reifegrad,
    owaspLlm,
    repoSuggestions,
    loading,
    error,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchAnforderungen,
    saveBewertung,
    fetchReifegrad,
    fetchOwaspLlm,
    repoScan,
  }
})
