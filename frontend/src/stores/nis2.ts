import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface NIS2Projekt {
  id: string
  name: string
  company: string
  unternehmen: string
  einrichtungsklasse: string
  beschreibung: string
  description: string
  berater: string
  created_at?: string
  updated_at?: string
}

export interface NIS2Anforderung {
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
  verantwortlich: string
  zieldatum: string
  status: 'pending' | 'partial' | 'complete'
  updated_at?: string
}

export interface ReifegradResult {
  gesamt: { prozent: number; punkte_aktuell: number; punkte_max: number; ampel: string }
  kapitel: Record<string, { prozent: number; ampel: string; bewertet: number; gesamt: number }>
  luecken: Array<{ id: string; kapitel: string; titel: string; bewertung: number; gewichtung: number }>
}

export const useNis2Store = defineStore('nis2', () => {
  const projekte = ref<NIS2Projekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const anforderungen = ref<NIS2Anforderung[]>([])
  const reifegrad = ref<ReifegradResult | null>(null)
  const customAnforderungen = ref<any[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  const massnahmen = computed(() => anforderungen.value)

  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/nis2/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<NIS2Projekt>): Promise<NIS2Projekt | null> => {
    try {
      const res = await apiClient.post('/nis2/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<NIS2Projekt>): Promise<NIS2Projekt | null> => {
    try {
      const res = await apiClient.put(`/nis2/projekte/${encodeURIComponent(name)}`, data)
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
      await apiClient.delete(`/nis2/projekte/${encodeURIComponent(name)}`)
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
      const res = await apiClient.get(`/nis2/projekte/${encodeURIComponent(projektName)}/anforderungen`)
      anforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Anforderungen'
    }
  }

  const fetchMassnahmen = fetchAnforderungen

  const saveBewertung = async (projektName: string, anforderungId: string, payload: Partial<NIS2Anforderung>) => {
    try {
      await apiClient.post(
        `/nis2/projekte/${encodeURIComponent(projektName)}/bewertungen`,
        {
          anforderung_id: anforderungId,
          bewertung: payload.bewertung ?? payload.score ?? 0,
          kommentar: payload.kommentar ?? '',
          massnahme: payload.massnahme ?? '',
          verantwortlich: payload.verantwortlich ?? '',
          zieldatum: payload.zieldatum ?? '',
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

  const fetchReifegrad = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/nis2/projekte/${encodeURIComponent(projektName)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Reifegrad'
    }
  }

  const fetchCustomAnforderungen = async () => {
    try {
      const res = await apiClient.get('/nis2/anforderungen/custom')
      customAnforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
    }
  }

  const saveCustomAnforderung = async (data: any) => {
    try {
      await apiClient.post('/nis2/anforderungen/custom', data)
      await fetchCustomAnforderungen()
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  const deleteCustomAnforderung = async (id: string) => {
    try {
      await apiClient.delete(`/nis2/anforderungen/custom/${encodeURIComponent(id)}`)
      customAnforderungen.value = customAnforderungen.value.filter(c => c.id !== id)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  return {
    projekte,
    selectedProjekt,
    selectedProjektObj,
    anforderungen,
    massnahmen,
    reifegrad,
    customAnforderungen,
    loading,
    error,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchAnforderungen,
    fetchMassnahmen,
    saveBewertung,
    fetchReifegrad,
    fetchCustomAnforderungen,
    saveCustomAnforderung,
    deleteCustomAnforderung,
  }
})
