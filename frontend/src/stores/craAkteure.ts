import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Blueprint unter '/api/cra-akteure'; apiClient.baseURL = '/api'.
const BASE = '/cra-akteure'

export interface Akteur {
  id: number
  projekt_name: string
  rolle: string
  name: string
  anschrift: string
  kontakt: string
  produkt: string
  checkliste: Record<string, boolean>
  soll_nachweise: string[]
  checkliste_vollstaendig: boolean
  mandat_ref: string
  aufgabenumfang: string
  status: string
  notizen: string
}

export const useCraAkteureStore = defineStore('craAkteure', () => {
  const akteure = ref<Akteur[]>([])
  const rollen = ref<string[]>([])
  const status = ref<string[]>([])
  const checkliste = ref<Record<string, string[]>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchConstants() {
    try {
      const { data } = await apiClient.get(`${BASE}/constants`)
      rollen.value = data.rollen || []
      status.value = data.status || []
      checkliste.value = data.checkliste || {}
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden'
    }
  }

  async function fetchAkteure(projekt: string) {
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/akteure`)
      akteure.value = data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Akteure konnten nicht geladen werden'
    } finally {
      loading.value = false
    }
  }

  async function createAkteur(projekt: string, payload: Partial<Akteur>) {
    error.value = null
    try {
      const { data } = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/akteure`, payload)
      await fetchAkteure(projekt)
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Anlegen fehlgeschlagen'
      return null
    }
  }

  async function updateAkteur(projekt: string, id: number, payload: Partial<Akteur>) {
    error.value = null
    try {
      await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/akteure/${id}`, payload)
      await fetchAkteure(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
      return false
    }
  }

  async function deleteAkteur(projekt: string, id: number) {
    await apiClient.delete(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/akteure/${id}`)
    await fetchAkteure(projekt)
  }

  return {
    akteure, rollen, status, checkliste, loading, error,
    fetchConstants, fetchAkteure, createAkteur, updateAkteur, deleteAkteur,
  }
})
