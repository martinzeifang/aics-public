import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/dsgvo-lia'

export interface Lia {
  id: number
  lia_id: string
  vvt_ref: string
  verarbeitung: string
  stage: string
  zweck: string
  berechtigtes_interesse: string
  legitim: number
  erforderlichkeit: string
  mildere_mittel_geprueft: number
  mildere_mittel_ergebnis: string
  interessen_betroffener: string
  vernuenftige_erwartung: string
  garantien_optout: string
  ergebnis: string
  ergebnis_begruendung: string
  reviewer: string
  review_datum: string
  review_zyklus_monate: number
  naechstes_review: string
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const useDsgvoLiaStore = defineStore('dsgvoLia', () => {
  const items = ref<Lia[]>([])
  const constants = ref<{ stage: string[]; ergebnis: string[] } | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function fetchConstants() {
    if (constants.value) return
    try {
      constants.value = (await apiClient.get(`${BASE}/constants`)).data
    } catch { /* ignore */ }
  }

  async function fetchLia(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      items.value = (await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/lia`)).data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'LIA-Register konnte nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function saveLia(projekt: string, data: Partial<Lia>): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/lia`, data)
      await fetchLia(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'LIA konnte nicht gespeichert werden.'
      return false
    }
  }

  async function deleteLia(projekt: string, id: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/lia/${id}`)
      await fetchLia(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function exportLia(projekt: string, id: number, format: 'docx' | 'pdf'): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/lia/${id}/export`,
        { params: { format }, responseType: 'blob', timeout: 120000 },
      )
      triggerBlobDownload(res.data as Blob, `LIA_${projekt}_${id}.${format}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.status === 503
        ? 'PDF-Konverter nicht verfügbar — bitte DOCX nutzen.'
        : 'Export fehlgeschlagen.'
      return false
    }
  }

  return { items, constants, loading, error, fetchConstants, fetchLia, saveLia, deleteLia, exportLia }
})
