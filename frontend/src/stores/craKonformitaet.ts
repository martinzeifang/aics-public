import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/cra-konformitaet'

export interface Konformitaet {
  id?: number
  projekt_name?: string
  release_version: string
  bewertungsweg: string
  produktklasse: string
  checkliste: Record<string, boolean>
  soll_nachweise: string[]
  bewertung_abgeschlossen: boolean
  nb_kennnummer: string
  eucc_level: string
  ce_status: string
  doc: Record<string, any>
  doc_version: number
  doc_ausgestellt: boolean
  doc_ausgestellt_am?: string | null
  notizen: string
}

export const useCraKonformitaetStore = defineStore('craKonformitaet', () => {
  const record = ref<Partial<Konformitaet>>({})
  const wege = ref<string[]>([])
  const ceStatus = ref<string[]>([])
  const checkliste = ref<Record<string, string[]>>({})
  const error = ref<string | null>(null)

  async function fetchConstants() {
    try {
      const { data } = await apiClient.get(`${BASE}/constants`)
      wege.value = data.wege || []
      ceStatus.value = data.ce_status || []
      checkliste.value = data.checkliste || {}
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden'
    }
  }

  async function fetch(projekt: string, release = '') {
    try {
      const { data } = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/konformitaet`,
        { params: { release } })
      record.value = data || {}
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen'
    }
  }

  async function save(projekt: string, payload: Partial<Konformitaet>) {
    try {
      const { data } = await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/konformitaet`, payload)
      record.value = data
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
      return false
    }
  }

  async function issueDoc(projekt: string, doc: Record<string, any>, release = '') {
    error.value = null
    try {
      const { data } = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/konformitaet/doc`,
        { doc, release_version: release })
      record.value = data
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'DoC konnte nicht ausgestellt werden'
      return false
    }
  }

  return { record, wege, ceStatus, checkliste, error, fetchConstants, fetch, save, issueDoc }
})
