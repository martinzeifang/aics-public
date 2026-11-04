import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export interface Dsb {
  id: number
  projekt_name: string
  typ: string
  name: string
  bestelldatum: string
  kontakt_email: string
  kontakt_veroeffentlicht: number
  gemeldet_aufsicht: number
  aufgaben_nachweis: string
  taetigkeitsbericht: string
  notizen: string
  created_at?: string
  updated_at?: string
}

const BASE = '/dsgvo-dsb'

export const useDsgvoDsbStore = defineStore('dsgvoDsb', () => {
  const dsb = ref<Dsb | null>(null)
  const typen = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchConstants() {
    try {
      const res = await apiClient.get(`${BASE}/constants`)
      typen.value = res.data.typen || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden.'
    }
  }

  async function fetchDsb(projektName: string) {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projektName)}/dsb`,
      )
      dsb.value = res.data.dsb
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'DSB-Daten konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function saveDsb(projektName: string, payload: Partial<Dsb>) {
    error.value = null
    try {
      const res = await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projektName)}/dsb`,
        payload,
      )
      dsb.value = res.data.dsb
      return res.data.dsb as Dsb
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'DSB-Daten konnten nicht gespeichert werden.'
      return null
    }
  }

  async function deleteDsb(projektName: string) {
    error.value = null
    try {
      await apiClient.delete(
        `${BASE}/projekte/${encodeURIComponent(projektName)}/dsb`,
      )
      dsb.value = null
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'DSB-Datensatz konnte nicht gelöscht werden.'
      return false
    }
  }

  return {
    dsb,
    typen,
    loading,
    error,
    fetchConstants,
    fetchDsb,
    saveDsb,
    deleteDsb,
  }
})
