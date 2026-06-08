import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export interface BetroffenenrechtAntrag {
  id: number
  projekt_name: string
  antrag_id: string
  typ: string
  eingang_datum: string
  frist_datum: string
  verlaengert: number
  identitaet_geprueft: number
  status: string
  bearbeiter: string
  ergebnis: string
  notizen: string
  overdue: boolean
  days_left: number | null
  created_at?: string
  updated_at?: string
}

const BASE = '/dsgvo-betroffenenrechte'

export const useDsgvoBetroffenenrechteStore = defineStore('dsgvoBetroffenenrechte', () => {
  const antraege = ref<BetroffenenrechtAntrag[]>([])
  const typen = ref<string[]>([])
  const statusOptions = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchConstants() {
    try {
      const res = await apiClient.get(`${BASE}/constants`)
      typen.value = res.data.typen || []
      statusOptions.value = res.data.status || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden.'
    }
  }

  async function fetchAntraege(projektName: string) {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projektName)}/antraege`,
      )
      antraege.value = res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Anträge konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function createAntrag(projektName: string, payload: Partial<BetroffenenrechtAntrag>) {
    error.value = null
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projektName)}/antraege`,
        payload,
      )
      antraege.value.unshift(res.data)
      return res.data as BetroffenenrechtAntrag
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Antrag konnte nicht angelegt werden.'
      return null
    }
  }

  async function updateAntrag(id: number, payload: Partial<BetroffenenrechtAntrag>) {
    error.value = null
    try {
      const res = await apiClient.put(`${BASE}/antraege/${id}`, payload)
      const idx = antraege.value.findIndex(a => a.id === id)
      if (idx >= 0) antraege.value[idx] = res.data
      return res.data as BetroffenenrechtAntrag
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Antrag konnte nicht gespeichert werden.'
      return null
    }
  }

  async function deleteAntrag(id: number) {
    error.value = null
    try {
      await apiClient.delete(`${BASE}/antraege/${id}`)
      antraege.value = antraege.value.filter(a => a.id !== id)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Antrag konnte nicht gelöscht werden.'
      return false
    }
  }

  return {
    antraege,
    typen,
    statusOptions,
    loading,
    error,
    fetchConstants,
    fetchAntraege,
    createAntrag,
    updateAntrag,
    deleteAntrag,
  }
})
