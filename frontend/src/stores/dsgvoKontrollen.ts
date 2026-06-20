import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Backend mountet die Blueprints unter '/api/dsgvo-kontrollen' bzw.
// '/api/dsgvo-jahresbericht'. apiClient.baseURL ist '/api' -> Pfade hier ohne '/api'.
const BASE = '/dsgvo-kontrollen'
const JB = '/dsgvo-jahresbericht'

export interface KontrolleAnhang {
  id: number
  filename: string
  sha256: string
  mime: string
  size: number
  uploaded_at: string
}

export interface Kontrolle {
  id: number
  kontroll_id: string
  titel: string
  bereich: string
  jahr: number
  frequenz: string
  verantwortlich: string
  status: string
  geplant_am: string
  durchgefuehrt_am: string
  durchgefuehrt_von: string
  ergebnis: string
  bezug_ref: string
  freigabe_von: string
  freigabe_am: string
  anhaenge: number | KontrolleAnhang[]
}

export interface KontrollenConstants {
  status: string[]
  bereiche: string[]
  frequenz: string[]
}

export interface JahresberichtSignoff {
  status: 'entwurf' | 'freigegeben' | 'signiert'
  freigabe_von: string
  freigabe_am: string
  signatur_von: string
  signatur_name: string
  signatur_am: string
  sha256: string
}

export interface Jahresbericht {
  projekt: { name: string; unternehmen: string; berater: string }
  jahr: number
  erstellt_am: string
  meta: {
    anzahl_kontrollen: number
    anzahl_dsfa: number
    anzahl_datenpannen: number
    anzahl_betroffenenrechte: number
    anzahl_risiken: number
    tom_reifegrad: number
  }
  kontrollen_summary: { gesamt: number; abgeschlossen: number; offen: number }
  kontrollen: any[]
  dsfa: any[]
  datenpannen: any[]
  betroffenenrechte: any[]
  einwilligung_widerrufe: any[]
  tom: { pct: number; gesamt: number; umgesetzt: number }
  risiken: Array<{ quelle: string; titel: string; schwere: string; projekt: string }>
  signoff: JahresberichtSignoff
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const useDsgvoKontrollenStore = defineStore('dsgvoKontrollen', () => {
  const constants = ref<KontrollenConstants | null>(null)
  const kontrollen = ref<Kontrolle[]>([])
  const loading = ref(false)
  const error = ref('')

  // ── Konstanten ─────────────────────────────────────────────────────────
  async function fetchConstants() {
    if (constants.value) return
    try {
      const res = await apiClient.get(`${BASE}/constants`)
      constants.value = res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden.'
    }
  }

  // ── Kontrollen ─────────────────────────────────────────────────────────
  async function fetchKontrollen(projekt: string, jahr: number) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/kontrollen`,
        { params: { jahr } },
      )
      kontrollen.value = res.data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Kontrollen konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function createKontrolle(
    projekt: string,
    data: Partial<Kontrolle>,
  ): Promise<{ ok: boolean; id?: number }> {
    error.value = ''
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/kontrollen`,
        data,
      )
      return { ok: true, id: res.data?.id }
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Kontrolle konnte nicht angelegt werden.'
      return { ok: false }
    }
  }

  async function seedKontrollen(projekt: string, jahr: number): Promise<number | null> {
    error.value = ''
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/kontrollen/seed`,
        { jahr },
      )
      return res.data?.angelegt ?? 0
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Standard-Kontrollen konnten nicht angelegt werden.'
      return null
    }
  }

  async function fetchKontrolle(pk: number): Promise<Kontrolle | null> {
    error.value = ''
    try {
      const res = await apiClient.get(`${BASE}/kontrollen/${pk}`)
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Kontrolle konnte nicht geladen werden.'
      return null
    }
  }

  async function freigebenKontrolle(pk: number): Promise<Kontrolle | null> {
    error.value = ''
    try {
      const res = await apiClient.post(`${BASE}/kontrollen/${pk}/freigeben`, {})
      return res.data?.kontrolle ?? null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Freigabe fehlgeschlagen.'
      return null
    }
  }

  async function dokumentierenKontrolle(
    pk: number,
    payload: {
      durchgefuehrt_am: string
      durchgefuehrt_von: string
      ergebnis: string
      abschliessen: boolean
    },
  ): Promise<Kontrolle | null> {
    error.value = ''
    try {
      const res = await apiClient.post(`${BASE}/kontrollen/${pk}/dokumentieren`, payload)
      return res.data?.kontrolle ?? null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Dokumentation fehlgeschlagen.'
      return null
    }
  }

  async function deleteKontrolle(pk: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${BASE}/kontrollen/${pk}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  // ── Anhänge ────────────────────────────────────────────────────────────
  async function fetchAnhaenge(pk: number): Promise<KontrolleAnhang[]> {
    error.value = ''
    try {
      const res = await apiClient.get(`${BASE}/kontrollen/${pk}/anhaenge`)
      return res.data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Anhänge konnten nicht geladen werden.'
      return []
    }
  }

  async function uploadAnhang(pk: number, file: File): Promise<boolean> {
    error.value = ''
    try {
      const fd = new FormData()
      fd.append('file', file)
      await apiClient.post(`${BASE}/kontrollen/${pk}/anhaenge`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Upload fehlgeschlagen.'
      return false
    }
  }

  async function downloadAnhang(anhangId: number, filename: string): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(`${BASE}/anhaenge/${anhangId}/download`, {
        responseType: 'blob',
      })
      triggerBlobDownload(res.data as Blob, filename)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Download fehlgeschlagen.'
      return false
    }
  }

  async function deleteAnhang(anhangId: number, reason: string): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${BASE}/anhaenge/${anhangId}`, { data: { reason } })
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  // ── Jahresbericht ──────────────────────────────────────────────────────
  async function fetchJahresbericht(projekt: string, jahr: number): Promise<Jahresbericht | null> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${JB}/projekte/${encodeURIComponent(projekt)}/jahresbericht/${jahr}`,
      )
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Jahresbericht konnte nicht geladen werden.'
      return null
    }
  }

  async function exportJahresbericht(
    projekt: string,
    jahr: number,
    format: 'docx' | 'pdf',
  ): Promise<{ ok: boolean; status?: number }> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${JB}/projekte/${encodeURIComponent(projekt)}/jahresbericht/${jahr}/export`,
        { params: { format }, responseType: 'blob', timeout: 120000 },
      )
      triggerBlobDownload(
        res.data as Blob,
        `DSGVO-Jahresbericht_${projekt}_${jahr}.${format}`,
      )
      return { ok: true }
    } catch (e: any) {
      const status = e?.response?.status
      if (status === 503) {
        error.value = 'PDF-Konverter nicht verfügbar — bitte DOCX-Export nutzen.'
      } else {
        // Blob-Fehlerantworten enthalten die Meldung als Blob → generischer Text.
        error.value = 'Export fehlgeschlagen.'
      }
      return { ok: false, status }
    }
  }

  async function freigebenJahresbericht(
    projekt: string,
    jahr: number,
  ): Promise<JahresberichtSignoff | null> {
    error.value = ''
    try {
      const res = await apiClient.post(
        `${JB}/projekte/${encodeURIComponent(projekt)}/jahresbericht/${jahr}/freigeben`,
        {},
      )
      return res.data?.signoff ?? null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Freigabe fehlgeschlagen.'
      return null
    }
  }

  async function signierenJahresbericht(
    projekt: string,
    jahr: number,
    name: string,
  ): Promise<JahresberichtSignoff | null> {
    error.value = ''
    try {
      const res = await apiClient.post(
        `${JB}/projekte/${encodeURIComponent(projekt)}/jahresbericht/${jahr}/signieren`,
        { name },
      )
      return res.data?.signoff ?? null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Signatur fehlgeschlagen.'
      return null
    }
  }

  return {
    constants,
    kontrollen,
    loading,
    error,
    fetchConstants,
    fetchKontrollen,
    createKontrolle,
    seedKontrollen,
    fetchKontrolle,
    freigebenKontrolle,
    dokumentierenKontrolle,
    deleteKontrolle,
    fetchAnhaenge,
    uploadAnhang,
    downloadAnhang,
    deleteAnhang,
    fetchJahresbericht,
    exportJahresbericht,
    freigebenJahresbericht,
    signierenJahresbericht,
  }
})
