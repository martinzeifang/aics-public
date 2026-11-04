import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Blueprint unter '/api/cra-korrektur'; apiClient.baseURL = '/api'.
const BASE = '/cra-korrektur'

export interface KorrekturAuditEvent {
  event: string
  ts: string
  [k: string]: any
}

export interface Korrektur {
  id: number
  projekt_name: string
  massnahmentyp: string
  titel: string
  ausloeser: string
  betroffene_versionen: string
  betroffene_ms: string
  behoerde_informiert: boolean
  behoerde_info_datum: string | null
  behoerde_name: string
  vuln_id: number | null
  meldung_id: number | null
  status: string
  beschreibung: string
  abgeschlossen_am: string | null
  audit_trail: KorrekturAuditEvent[]
}

export const useCraKorrekturStore = defineStore('craKorrektur', () => {
  const massnahmen = ref<Korrektur[]>([])
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

  async function fetchMassnahmen(projekt: string) {
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/korrekturmassnahmen`)
      massnahmen.value = data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Korrekturmaßnahmen konnten nicht geladen werden'
    } finally {
      loading.value = false
    }
  }

  async function createMassnahme(projekt: string, payload: Partial<Korrektur>) {
    error.value = null
    try {
      const { data } = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/korrekturmassnahmen`, payload)
      await fetchMassnahmen(projekt)
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Anlegen fehlgeschlagen'
      return null
    }
  }

  async function setStatus(projekt: string, id: number, newStatus: string) {
    error.value = null
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/korrekturmassnahmen/${id}/status`,
        { status: newStatus })
      await fetchMassnahmen(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Statuswechsel fehlgeschlagen'
      return false
    }
  }

  async function informBehoerde(projekt: string, id: number, behoerde_name: string, datum = '') {
    await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/korrekturmassnahmen/${id}/behoerde`,
      { behoerde_name, datum })
    await fetchMassnahmen(projekt)
  }

  async function deleteMassnahme(projekt: string, id: number) {
    await apiClient.delete(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/korrekturmassnahmen/${id}`)
    await fetchMassnahmen(projekt)
  }

  return {
    massnahmen, typen, status, loading, error,
    fetchConstants, fetchMassnahmen, createMassnahme, setStatus,
    informBehoerde, deleteMassnahme,
  }
})
