import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Frist-Engine (#1193). CRUD der Datenpannen bleibt in /api/dsgvo.
const BASE = '/dsgvo-datenpannen'
const CRUD = '/dsgvo'

export interface PanneFrist {
  due_at: string
  hours_left: number | null
  overdue: boolean
  ampel: 'gruen' | 'gelb' | 'rot' | 'grau'
  label: string
  deadline_hours: number
}

export interface Datenpanne {
  id: number
  panne_id: string
  titel: string
  beschreibung: string
  art: string
  festgestellt_am: string
  betroffene_anzahl: number
  datenkategorien: string
  risikoeinschaetzung: string
  meldung_aufsicht_pflicht: number
  meldung_aufsicht_datum: string | null
  meldung_betroffene_pflicht: number
  sofortmassnahmen: string
  ursache: string
  lessons_learned: string
  status: string
  notizen: string
  frist: PanneFrist
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const useDsgvoDatenpannenStore = defineStore('dsgvoDatenpannen', () => {
  const pannen = ref<Datenpanne[]>([])
  const loading = ref(false)
  const error = ref('')

  async function fetchPannen(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      const res = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/datenpannen`)
      pannen.value = res.data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Datenpannen konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function savePanne(projekt: string, data: Partial<Datenpanne>): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(`${CRUD}/projekte/${encodeURIComponent(projekt)}/datenpannen`, data)
      await fetchPannen(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Datenpanne konnte nicht gespeichert werden.'
      return false
    }
  }

  async function deletePanne(projekt: string, id: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${CRUD}/projekte/${encodeURIComponent(projekt)}/datenpannen/${id}`)
      await fetchPannen(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function exportMeldeformular(
    projekt: string,
    panneId: number,
    format: 'docx' | 'pdf',
  ): Promise<{ ok: boolean; status?: number }> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/datenpannen/${panneId}/meldeformular`,
        { params: { format }, responseType: 'blob', timeout: 120000 },
      )
      triggerBlobDownload(res.data as Blob, `Art33-Meldeformular_${projekt}_${panneId}.${format}`)
      return { ok: true }
    } catch (e: any) {
      const status = e?.response?.status
      error.value = status === 503
        ? 'PDF-Konverter nicht verfügbar — bitte DOCX-Export nutzen.'
        : 'Export fehlgeschlagen.'
      return { ok: false, status }
    }
  }

  return { pannen, loading, error, fetchPannen, savePanne, deletePanne, exportMeldeformular }
})
