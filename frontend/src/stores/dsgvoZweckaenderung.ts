import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/dsgvo-zweckaenderung'

export interface Zweckaenderung {
  id: number
  za_id: string
  vvt_ref: string
  urspruenglicher_zweck: string
  neuer_zweck: string
  krit_zusammenhang: string
  krit_kontext: string
  krit_datenart: string
  krit_folgen: string
  krit_garantien: string
  ergebnis: string
  ergebnis_begruendung: string
  neue_rechtsgrundlage: string
  reviewer: string
  review_datum: string
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const useDsgvoZweckaenderungStore = defineStore('dsgvoZweckaenderung', () => {
  const items = ref<Zweckaenderung[]>([])
  const loading = ref(false)
  const error = ref('')

  async function fetchAll(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      items.value = (await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/zweckaenderungen`)).data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Zweckänderungen konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function save(projekt: string, data: Partial<Zweckaenderung>): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/zweckaenderungen`, data)
      await fetchAll(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function remove(projekt: string, id: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/zweckaenderungen/${id}`)
      await fetchAll(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function wizardPrompt(projekt: string, urspr: string, neu: string): Promise<string> {
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/zweckaenderungen/wizard/prompt`,
        { urspruenglicher_zweck: urspr, neuer_zweck: neu })
      return res.data?.prompt || ''
    } catch { return '' }
  }

  async function wizardParse(projekt: string, response: string): Promise<Partial<Zweckaenderung> | null> {
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/zweckaenderungen/wizard/parse`,
        { response })
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Antwort konnte nicht verarbeitet werden.'
      return null
    }
  }

  async function exportZa(projekt: string, id: number, format: 'docx' | 'pdf'): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/zweckaenderungen/${id}/export`,
        { params: { format }, responseType: 'blob', timeout: 120000 })
      triggerBlobDownload(res.data as Blob, `Zweckaenderung_${projekt}_${id}.${format}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.status === 503
        ? 'PDF-Konverter nicht verfügbar — bitte DOCX nutzen.'
        : 'Export fehlgeschlagen.'
      return false
    }
  }

  return { items, loading, error, fetchAll, save, remove, wizardPrompt, wizardParse, exportZa }
})
