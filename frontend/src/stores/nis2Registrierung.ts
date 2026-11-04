import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/nis2-registrierung'

export interface Bestaetigung {
  ampel: 'grey' | 'green' | 'amber' | 'red'
  status: string
  due_at: string
  days_left?: number
  hinweis: string
}

export interface Registrierung {
  id?: number
  projekt_name?: string
  name: string
  sektor: string
  subsektor: string
  einrichtungsart: string
  anschrift: string
  eu_niederlassungen: string
  kontakt_email: string
  kontakt_telefon: string
  mitgliedstaaten: string
  ip_bereiche: string
  status: string
  registrierungs_datum: string
  bestaetigungs_referenz: string
  naechste_jahres_bestaetigung: string
  notizen: string
  fehlende_pflichtfelder?: string[]
  vollstaendig?: boolean
  bestaetigung?: Bestaetigung
}

export interface RegConstants {
  status: string[]
  pflichtfelder: string[]
}

export const useNis2RegistrierungStore = defineStore('nis2Registrierung', () => {
  const constants = ref<RegConstants | null>(null)
  const registrierung = ref<Registrierung | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function fetchConstants() {
    if (constants.value) return
    try {
      constants.value = (await apiClient.get(`${BASE}/constants`)).data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden.'
    }
  }

  async function fetchRegistrierung(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/registrierung`,
      )
      registrierung.value = res.data && Object.keys(res.data).length ? res.data : null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Registrierung konnte nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function saveRegistrierung(projekt: string, data: Partial<Registrierung>): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/registrierung`,
        data,
      )
      registrierung.value = res.data?.registrierung ?? null
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function fetchPrefill(projekt: string): Promise<Partial<Registrierung>> {
    try {
      return (await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/registrierung/prefill`,
      )).data || {}
    } catch {
      return {}
    }
  }

  async function exportRegistrierung(projekt: string, format: 'md' | 'json'): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/registrierung/export?format=${format}`,
        { responseType: 'blob' },
      )
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `NIS2-Registrierung_${projekt}.${format}`
      a.click()
      URL.revokeObjectURL(url)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Export fehlgeschlagen.'
      return false
    }
  }

  return {
    constants,
    registrierung,
    loading,
    error,
    fetchConstants,
    fetchRegistrierung,
    saveRegistrierung,
    fetchPrefill,
    exportRegistrierung,
  }
})
