import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export interface LoeschRegel {
  id: number
  projekt_name: string
  regel_id: string
  datenkategorie: string
  aufbewahrungsfrist: string
  rechtsgrundlage_frist: 'gesetzlich' | 'zweckbindung'
  loeschklasse: string
  loesch_trigger: string
  verantwortlich: string
  status: string
  vvt_ref: string
  created_at?: string
  updated_at?: string
}

const BASE = '/dsgvo-loeschkonzept'

export const useDsgvoLoeschkonzeptStore = defineStore('dsgvoLoeschkonzept', () => {
  const regeln = ref<LoeschRegel[]>([])
  const faellig = ref<LoeschRegel[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchRegeln(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/regeln`)
      regeln.value = res.data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
    } finally {
      loading.value = false
    }
  }

  async function fetchFaellig(projekt: string) {
    if (!projekt) return
    try {
      const res = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/faellig`)
      faellig.value = res.data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
    }
  }

  async function createRegel(projekt: string, payload: Partial<LoeschRegel>): Promise<boolean> {
    error.value = null
    try {
      await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/regeln`, payload)
      await fetchRegeln(projekt)
      await fetchFaellig(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Anlegen fehlgeschlagen.'
      return false
    }
  }

  async function updateRegel(projekt: string, pk: number, payload: Partial<LoeschRegel>): Promise<boolean> {
    error.value = null
    try {
      await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/regeln/${pk}`, payload)
      await fetchRegeln(projekt)
      await fetchFaellig(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function setStatus(projekt: string, pk: number, status: string): Promise<boolean> {
    error.value = null
    try {
      await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/regeln/${pk}/status`, { status })
      await fetchRegeln(projekt)
      await fetchFaellig(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Status-Update fehlgeschlagen.'
      return false
    }
  }

  async function deleteRegel(projekt: string, pk: number): Promise<boolean> {
    error.value = null
    try {
      await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/regeln/${pk}`)
      await fetchRegeln(projekt)
      await fetchFaellig(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  return {
    regeln, faellig, loading, error,
    fetchRegeln, fetchFaellig, createRegel, updateRegel, setStatus, deleteRegel,
  }
})
