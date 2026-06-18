import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface DoraProjekt {
  id: string
  name: string
  unternehmen: string
  company: string
  finanzeinrichtung_klasse: string
  beschreibung: string
  description: string
  berater: string
  meta_json?: string
  meta?: string
  created_at?: string
  updated_at?: string
}

export interface DoraAnforderung {
  id: string
  pfeiler: string
  kapitel?: string
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

export interface DoraTPP {
  id: string
  name: string
  kategorie: string
  kritisch: number | boolean
  beschreibung: string
  vertrag_url: string
  ansprechpartner: string
  risiko_score: number
  status: string
  meta_json?: string
}

export interface DoraTest {
  id: string
  test_typ: string
  scope: string
  frequenz: string
  naechster_termin: string
  status: string
  verantwortlich: string
  ergebnis: string
}

export const useDoraStore = defineStore('dora', () => {
  const projekte = ref<DoraProjekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const anforderungen = ref<DoraAnforderung[]>([])
  const reifegrad = ref<any | null>(null)
  const customAnforderungen = ref<any[]>([])
  const tpps = ref<DoraTPP[]>([])
  const tests = ref<DoraTest[]>([])
  const constants = ref<any | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  const fetchConstants = async () => {
    if (constants.value) return constants.value
    try {
      const res = await apiClient.get('/dora/constants')
      constants.value = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return null
    }
  }

  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/dora/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<DoraProjekt>) => {
    try {
      const res = await apiClient.post('/dora/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<DoraProjekt>) => {
    try {
      const res = await apiClient.put(`/dora/projekte/${encodeURIComponent(name)}`, data)
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
      await apiClient.delete(`/dora/projekte/${encodeURIComponent(name)}`)
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
      const res = await apiClient.get(`/dora/projekte/${encodeURIComponent(projektName)}/anforderungen`)
      anforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    }
  }

  const saveBewertung = async (projektName: string, anforderungId: string, payload: any) => {
    try {
      await apiClient.post(`/dora/projekte/${encodeURIComponent(projektName)}/bewertungen`, {
        anforderung_id: anforderungId,
        bewertung: payload.bewertung ?? payload.score ?? 0,
        kommentar: payload.kommentar ?? '',
        massnahme: payload.massnahme ?? '',
        verantwortlich: payload.verantwortlich ?? '',
        zieldatum: payload.zieldatum ?? '',
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
      const res = await apiClient.get(`/dora/projekte/${encodeURIComponent(projektName)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Reifegrad'
    }
  }

  const fetchCustomAnforderungen = async () => {
    try {
      const res = await apiClient.get('/dora/anforderungen/custom')
      customAnforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
    }
  }

  const saveCustomAnforderung = async (data: any) => {
    try {
      await apiClient.post('/dora/anforderungen/custom', data)
      await fetchCustomAnforderungen()
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  const deleteCustomAnforderung = async (id: string) => {
    try {
      await apiClient.delete(`/dora/anforderungen/custom/${encodeURIComponent(id)}`)
      customAnforderungen.value = customAnforderungen.value.filter(c => c.id !== id)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  // ---- TPP ----
  const fetchTPPs = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/dora/projekte/${encodeURIComponent(projektName)}/tpp`)
      tpps.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden TPPs'
    }
  }

  const saveTPP = async (projektName: string, data: Partial<DoraTPP>) => {
    try {
      const url = data.id
        ? `/dora/projekte/${encodeURIComponent(projektName)}/tpp/${data.id}`
        : `/dora/projekte/${encodeURIComponent(projektName)}/tpp`
      const method = data.id ? 'put' : 'post'
      await (apiClient as any)[method](url, data)
      await fetchTPPs(projektName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  const deleteTPP = async (projektName: string, tppId: string) => {
    try {
      await apiClient.delete(`/dora/projekte/${encodeURIComponent(projektName)}/tpp/${tppId}`)
      tpps.value = tpps.value.filter(t => t.id !== tppId)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  // ---- Tests ----
  const fetchTests = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/dora/projekte/${encodeURIComponent(projektName)}/testing`)
      tests.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden Tests'
    }
  }

  const saveTest = async (projektName: string, data: Partial<DoraTest>) => {
    try {
      const url = data.id
        ? `/dora/projekte/${encodeURIComponent(projektName)}/testing/${data.id}`
        : `/dora/projekte/${encodeURIComponent(projektName)}/testing`
      const method = data.id ? 'put' : 'post'
      await (apiClient as any)[method](url, data)
      await fetchTests(projektName)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  const deleteTest = async (projektName: string, testId: string) => {
    try {
      await apiClient.delete(`/dora/projekte/${encodeURIComponent(projektName)}/testing/${testId}`)
      tests.value = tests.value.filter(t => t.id !== testId)
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
    reifegrad,
    customAnforderungen,
    tpps,
    tests,
    constants,
    loading,
    error,
    fetchConstants,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchAnforderungen,
    saveBewertung,
    fetchReifegrad,
    fetchCustomAnforderungen,
    saveCustomAnforderung,
    deleteCustomAnforderung,
    fetchTPPs,
    saveTPP,
    deleteTPP,
    fetchTests,
    saveTest,
    deleteTest,
  }
})
