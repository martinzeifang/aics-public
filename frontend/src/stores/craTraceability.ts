import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Blueprint unter '/api/cra-traceability'; apiClient.baseURL = '/api'.
const BASE = '/cra-traceability'

export interface ReqTrace {
  anforderung_id: string
  kapitel: string
  titel: string
  nachweise: { id: number; doc_name: string; doc_type: string }[]
  nachweis_count: number
  hat_bewertung: boolean
  ampel: 'belegt' | 'fehlt'
}

export interface AnnexBaustein {
  key: string
  label: string
  nachweise: { id: number | null; doc_name: string; doc_type: string }[]
  nachweis_count: number
  ampel: 'belegt' | 'fehlt'
}

export interface AnnexStatus {
  projekt_name: string
  bausteine: AnnexBaustein[]
  belegt_count: number
  gesamt_count: number
  vollstaendig: boolean
  vollstaendigkeit_pct: number
}

export const useCraTraceabilityStore = defineStore('craTraceability', () => {
  const requirements = ref<ReqTrace[]>([])
  const annex = ref<AnnexStatus | null>(null)
  const dokumente = ref<any[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchAll(projekt: string) {
    loading.value = true
    error.value = null
    try {
      const enc = encodeURIComponent(projekt)
      const [rt, av, dk] = await Promise.all([
        apiClient.get(`${BASE}/projekte/${enc}/requirement-traceability`),
        apiClient.get(`${BASE}/projekte/${enc}/annex-vii-status`),
        apiClient.get(`${BASE}/projekte/${enc}/dokumente`),
      ])
      requirements.value = rt.data
      annex.value = av.data
      dokumente.value = dk.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Traceability konnte nicht geladen werden'
    } finally {
      loading.value = false
    }
  }

  async function createDokument(projekt: string, payload: Record<string, any>) {
    error.value = null
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/dokumente`, payload)
      await fetchAll(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Anlegen fehlgeschlagen'
      return false
    }
  }

  async function linkDokument(projekt: string, id: number, payload: Record<string, any>) {
    await apiClient.put(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/dokumente/${id}/link`, payload)
    await fetchAll(projekt)
  }

  return {
    requirements, annex, dokumente, loading, error,
    fetchAll, createDokument, linkDokument,
  }
})
