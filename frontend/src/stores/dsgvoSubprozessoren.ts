import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/dsgvo-subprozessoren'

export interface AvvEintrag {
  id: number
  auftragsverarbeiter: string
  leistung: string
  avv_vorhanden: number
  status: string
  sub_gesamt: number
  sub_ausstehend: number
  review_faellig: boolean
}

export interface Subprozessor {
  id: number
  avv_pk: number
  name: string
  leistung: string
  drittland: number
  drittland_garantie: string
  genehmigung_status: string
  genehmigung_datum: string
  sub_avv_vorhanden: number
  sub_avv_url: string
  sub_avv_datum: string
  pflichten_backtoback: number
  notizen: string
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const useDsgvoSubprozessorenStore = defineStore('dsgvoSubprozessoren', () => {
  const avv = ref<AvvEintrag[]>([])
  const subs = ref<Record<number, Subprozessor[]>>({})
  const loading = ref(false)
  const error = ref('')

  async function fetchAvv(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      avv.value = (await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/avv`)).data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'AVV-Liste konnte nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function fetchSubs(projekt: string, avvPk: number) {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/avv/${avvPk}/subprozessoren`)
      subs.value = { ...subs.value, [avvPk]: res.data || [] }
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Subprozessoren konnten nicht geladen werden.'
    }
  }

  async function createSub(projekt: string, avvPk: number, data: Partial<Subprozessor>): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/avv/${avvPk}/subprozessoren`, data)
      await fetchSubs(projekt, avvPk)
      await fetchAvv(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Subprozessor konnte nicht angelegt werden.'
      return false
    }
  }

  async function updateSub(projekt: string, avvPk: number, pk: number, data: Partial<Subprozessor>): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/subprozessoren/${pk}`, data)
      await fetchSubs(projekt, avvPk)
      await fetchAvv(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Subprozessor konnte nicht gespeichert werden.'
      return false
    }
  }

  async function setGenehmigung(projekt: string, avvPk: number, pk: number, status: string, datum: string): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/subprozessoren/${pk}/genehmigung`,
        { status, datum })
      await fetchSubs(projekt, avvPk)
      await fetchAvv(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Genehmigung fehlgeschlagen.'
      return false
    }
  }

  async function deleteSub(projekt: string, avvPk: number, pk: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/subprozessoren/${pk}`)
      await fetchSubs(projekt, avvPk)
      await fetchAvv(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function exportBericht(projekt: string, format: 'docx' | 'pdf'): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/avv-bericht`,
        { params: { format }, responseType: 'blob', timeout: 120000 })
      triggerBlobDownload(res.data as Blob, `AVV-Bericht_${projekt}.${format}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.status === 503
        ? 'PDF-Konverter nicht verfügbar — bitte DOCX nutzen.'
        : 'Export fehlgeschlagen.'
      return false
    }
  }

  return { avv, subs, loading, error, fetchAvv, fetchSubs, createSub, updateSub, setGenehmigung, deleteSub, exportBericht }
})
