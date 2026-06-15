import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Backend mountet den Blueprint unter '/api/nis2-scoping'. apiClient.baseURL
// ist '/api' -> Pfade hier ohne '/api'.
const BASE = '/nis2-scoping'

export interface Scoping {
  id?: number
  projekt_name?: string
  mitarbeiterzahl: number
  jahresumsatz: number
  bilanzsumme: number
  sektor: string
  subsektor: string
  anhang: string
  konzernverbund: string
  size_class: string
  size_begruendung: string
  hauptniederlassung: string
  zustaendige_behoerde: string
  eu_niedergelassen: number
  eu_vertreter: string
  version?: number
  scoping_datum: string
  notizen: string
}

export interface ScopingConstants {
  anhang: string[]
  size_class: string[]
}

export const useNis2ScopingStore = defineStore('nis2Scoping', () => {
  const constants = ref<ScopingConstants | null>(null)
  const scoping = ref<Scoping | null>(null)
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

  async function fetchScoping(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/scoping`,
      )
      scoping.value = res.data && Object.keys(res.data).length ? res.data : null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Scoping konnte nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function saveScoping(projekt: string, data: Partial<Scoping>): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/scoping`,
        data,
      )
      scoping.value = res.data?.scoping ?? null
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function previewSizeClass(
    data: Partial<Scoping>,
  ): Promise<{ size_class: string; size_begruendung: string } | null> {
    try {
      return (await apiClient.post(`${BASE}/preview-size-class`, data)).data
    } catch {
      return null
    }
  }

  async function exportScoping(projekt: string, format: 'md' | 'json'): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/scoping/export?format=${format}`,
        { responseType: 'blob' },
      )
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `NIS2-Scoping_${projekt}.${format}`
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
    scoping,
    loading,
    error,
    fetchConstants,
    fetchScoping,
    saveScoping,
    previewSizeClass,
    exportScoping,
  }
})
