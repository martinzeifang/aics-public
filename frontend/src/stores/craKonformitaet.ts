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
  // #1824: Anhang I Teil II Nr. 3. Der Befund wird **nicht** im Frontend
  // gerechnet — er kommt fertig vom Server (dieselbe Funktion, die das Gate
  // benutzt). Die Regeln hier nachzubauen wäre die Lehre aus #1703/S9.
  const testArten = ref<{ wert: string; label: string }[]>([])
  const testBefund = ref<Record<string, any>>({})
  const testRegeln = ref<{ min_begruendung: number; max_monate: number }>(
    { min_begruendung: 20, max_monate: 18 })

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

  async function fetchSicherheitstests(projekt: string, release = '') {
    try {
      const { data } = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/konformitaet/sicherheitstests`,
        { params: { release } })
      testArten.value = data.arten || []
      testBefund.value = data.befund || {}
      testRegeln.value = { min_begruendung: data.min_begruendung ?? 20,
                           max_monate: data.max_monate ?? 18 }
    } catch (e: any) {
      error.value = e?.response?.data?.error
        || 'Stand der Sicherheitstests konnte nicht geladen werden'
    }
  }

  async function saveSicherheitstests(projekt: string, payload: Record<string, any>,
                                      release = '') {
    error.value = null
    try {
      const { data } = await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/konformitaet/sicherheitstests`,
        { ...payload, release_version: release })
      record.value = data.vorgang || record.value
      testBefund.value = data.befund || {}
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
      return false
    }
  }

  return { record, wege, ceStatus, checkliste, error, testArten, testBefund,
           testRegeln, fetchConstants, fetch, save, issueDoc,
           fetchSicherheitstests, saveSicherheitstests }
})
