import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/dsgvo-eu-vertreter'

export interface EuVertreter {
  id?: number
  projekt_name?: string
  // Anwendbarkeitsprüfung Art. 3(2)
  niederlassung_ausserhalb_eu: number
  angebot_eu_betroffene: number
  verhaltensbeobachtung: number
  ausnahme_art27_2: number
  pruefung_notiz: string
  // Benennungs-Mini-Register
  vertreter_name: string
  vertreter_anschrift: string
  vertreter_kontakt: string
  mandat_vorhanden: number
  mandat_datum: string
  in_datenschutzhinweis: number
  notizen: string
  // abgeleitet (read-only vom Server)
  einschlaegig?: boolean
  benennung_vollstaendig?: boolean
}

export const useDsgvoEuVertreterStore = defineStore('dsgvoEuVertreter', () => {
  const record = ref<EuVertreter | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function fetchRecord(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      const data = (await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/eu-vertreter`)).data
      record.value = data && Object.keys(data).length ? data : null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'EU-Vertreter-Daten konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function save(projekt: string, data: Partial<EuVertreter>): Promise<boolean> {
    error.value = ''
    try {
      record.value = (await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/eu-vertreter`, data)).data
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  return { record, loading, error, fetchRecord, save }
})
