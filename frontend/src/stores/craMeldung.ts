import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Blueprint unter '/api/cra-meldung'; apiClient.baseURL = '/api'.
const BASE = '/cra-meldung'

export interface MeldungDeadlineStage {
  key: string
  label: string
  due_at: string
  hours_left: number
  ampel: 'gruen' | 'gelb' | 'rot' | 'overdue'
  overdue: boolean
}

export interface MeldungDeadlines {
  stages: MeldungDeadlineStage[]
  next_due: string | null
  any_overdue: boolean
}

export interface Meldung {
  id: number
  projekt_name: string
  vuln_id: number | null
  typ: string
  titel: string
  status: string
  erkannt_am: string
  betroffene_ms: string
  vermutete_ursache: string
  mitigation: string
  beschreibung: string
  early_warning_gemeldet_am: string | null
  notification_gemeldet_am: string | null
  final_report_gemeldet_am: string | null
  advisory: Record<string, any>
  deadlines: MeldungDeadlines | null
}

export const useCraMeldungStore = defineStore('craMeldung', () => {
  const meldungen = ref<Meldung[]>([])
  const typen = ref<string[]>([])
  const status = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchConstants() {
    try {
      const { data } = await apiClient.get(`${BASE}/constants`)
      typen.value = data.typen || []
      status.value = data.status || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden'
    }
  }

  async function fetchMeldungen(projekt: string) {
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen`)
      meldungen.value = data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Meldungen konnten nicht geladen werden'
    } finally {
      loading.value = false
    }
  }

  async function createMeldung(projekt: string, payload: Partial<Meldung>) {
    const { data } = await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen`, payload)
    await fetchMeldungen(projekt)
    return data
  }

  async function setStufe(projekt: string, id: number, newStatus: string) {
    await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}/stufe`,
      { status: newStatus })
    await fetchMeldungen(projekt)
  }

  async function saveAdvisory(projekt: string, id: number, advisory: Record<string, any>) {
    await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}/nutzer-advisory`,
      advisory)
    await fetchMeldungen(projekt)
  }

  async function deleteMeldung(projekt: string, id: number) {
    await apiClient.delete(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}`)
    await fetchMeldungen(projekt)
  }

  function exportUrl(projekt: string, id: number) {
    return `/api${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}/export?format=json`
  }

  return {
    meldungen, typen, status, loading, error,
    fetchConstants, fetchMeldungen, createMeldung, setStufe,
    saveAdvisory, deleteMeldung, exportUrl,
  }
})
