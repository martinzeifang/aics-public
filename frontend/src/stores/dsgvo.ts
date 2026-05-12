import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface DsgvoProjekt {
  id: string
  name: string
  unternehmen: string
  company: string
  organisationstyp: string
  beschreibung: string
  description: string
  berater: string
  meta_json?: string
  created_at?: string
  updated_at?: string
}

export interface DsgvoAnforderung {
  id: string
  kapitel: string
  ref: string
  titel: string
  title?: string
  beschreibung: string
  description?: string
  hinweise: string
  gewichtung: number
  quelle: string
  bewertung: number
  score?: number
  kommentar: string
  notes?: string
  massnahme: string
  verantwortlich?: string
  zieldatum?: string
  status: 'pending' | 'partial' | 'complete'
  updated_at?: string
}

export interface ReifegradResult {
  ampel: string
  bewertete_count: number
  gesamt_count: number
  gesamt_pct: number
  kapitel_pct: Record<string, number>
}

export const useDsgvoStore = defineStore('dsgvo', () => {
  const projekte = ref<DsgvoProjekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const anforderungen = ref<DsgvoAnforderung[]>([])
  const reifegrad = ref<ReifegradResult | null>(null)
  const customAnforderungen = ref<any[]>([])
  const constants = ref<any | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  const fetchConstants = async () => {
    try {
      const res = await apiClient.get('/dsgvo/constants')
      constants.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Constants'
    }
  }

  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/dsgvo/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<DsgvoProjekt>): Promise<DsgvoProjekt | null> => {
    try {
      const res = await apiClient.post('/dsgvo/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<DsgvoProjekt>): Promise<DsgvoProjekt | null> => {
    try {
      const res = await apiClient.put(`/dsgvo/projekte/${encodeURIComponent(name)}`, data)
      const idx = projekte.value.findIndex(p => p.name === name)
      if (idx >= 0) projekte.value[idx] = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Aktualisieren'
      return null
    }
  }

  const deleteProjekt = async (name: string): Promise<boolean> => {
    try {
      await apiClient.delete(`/dsgvo/projekte/${encodeURIComponent(name)}`)
      projekte.value = projekte.value.filter(p => p.name !== name)
      if (selectedProjekt.value === name) selectedProjekt.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  const fetchAnforderungen = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/dsgvo/projekte/${encodeURIComponent(projektName)}/anforderungen`)
      anforderungen.value = res.data
      selectedProjekt.value = projektName
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Anforderungen'
    }
  }

  const fetchReifegrad = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/dsgvo/projekte/${encodeURIComponent(projektName)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Reifegrad'
    }
  }

  const saveBewertung = async (projektName: string, anforderungId: string, payload: Partial<DsgvoAnforderung>) => {
    try {
      await apiClient.post(
        `/dsgvo/projekte/${encodeURIComponent(projektName)}/bewertungen`,
        {
          anforderung_id: anforderungId,
          bewertung: payload.bewertung ?? payload.score ?? 0,
          kommentar: payload.kommentar ?? '',
          massnahme: payload.massnahme ?? '',
        },
      )
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

  const fetchCustomAnforderungen = async () => {
    try {
      const res = await apiClient.get('/dsgvo/anforderungen/custom')
      customAnforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
    }
  }

  return {
    projekte,
    selectedProjekt,
    selectedProjektObj,
    anforderungen,
    reifegrad,
    customAnforderungen,
    constants,
    loading,
    error,
    fetchConstants,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchAnforderungen,
    fetchReifegrad,
    saveBewertung,
    fetchCustomAnforderungen,
  }
})
