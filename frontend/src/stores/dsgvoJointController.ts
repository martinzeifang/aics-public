import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/dsgvo-joint'

export interface JointController {
  id: number
  jc_id: string
  partner: string
  partner_kontakt: string
  vvt_ref: string
  verarbeitung: string
  zweck_mittel: string
  anlaufstelle_betroffene: string
  pflicht_information: string
  pflicht_tom: string
  pflicht_meldung: string
  vereinbarung_vorhanden: number
  vereinbarung_url: string
  vereinbarung_datum: string
  zusammenfassung_status: string
  zusammenfassung_text: string
  zusammenfassung_url: string
  reviewer: string
  review_datum: string
  review_zyklus_monate: number
  naechstes_review: string
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

export const useDsgvoJointControllerStore = defineStore('dsgvoJointController', () => {
  const items = ref<JointController[]>([])
  const constants = ref<{ anlaufstelle: string[]; zusammenfassung_status: string[] } | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function fetchConstants() {
    if (constants.value) return
    try {
      constants.value = (await apiClient.get(`${BASE}/constants`)).data
    } catch { /* ignore */ }
  }

  async function fetchItems(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      items.value = (await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/joint`)).data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Joint-Controller-Register konnte nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function save(projekt: string, data: Partial<JointController>): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/joint`, data)
      await fetchItems(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstellation konnte nicht gespeichert werden.'
      return false
    }
  }

  async function remove(projekt: string, id: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/joint/${id}`)
      await fetchItems(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function exportItem(projekt: string, id: number, format: 'docx' | 'pdf'): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/joint/${id}/export`,
        { params: { format }, responseType: 'blob', timeout: 120000 },
      )
      triggerBlobDownload(res.data as Blob, `JointController_${projekt}_${id}.${format}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.status === 503
        ? 'PDF-Konverter nicht verfügbar — bitte DOCX nutzen.'
        : 'Export fehlgeschlagen.'
      return false
    }
  }

  return { items, constants, loading, error, fetchConstants, fetchItems, save, remove, exportItem }
})
