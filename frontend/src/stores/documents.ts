/**
 * Documents-Store (Sprint #24, S7) — generisches Dokumenten-Management.
 *
 * Verwaltet die Pflicht-/Weitere-Dokumente eines Moduls/Projekts gegen die
 * Backend-API `/<urlmod>-dokumente` (urlmod ∈ {aiact, cra, nis2, dsgvo, wiba}).
 *
 * State ist pro `${modul}:${projekt}` getrennt abgelegt, damit ein Wechsel des
 * Moduls oder Projekts keine Datenkollision verursacht.
 */
import { defineStore } from 'pinia'
import apiClient from '../api/client'

export type DocStatus = 'entwurf' | 'final' | 'freigegeben'
export type CatalogStatus = 'fehlt' | DocStatus

/** Ein im Backend gespeichertes Dokument. */
export interface Document {
  id: number
  projekt: string
  doc_type: string
  titel: string
  status: DocStatus
  content_html: string
  version: number
  source: string | null
  assistant_key: string | null
  sha256: string | null
  rechtsgrundlage: string | null
  katalog_titel: string | null
  meta: Record<string, any> | null
  updated_at: string | null
}

/** Ein Katalog-Eintrag (Pflichtdokument-Spezifikation). */
export interface DocSpec {
  doc_type: string
  titel: string
  rechtsgrundlage: string | null
  kategorie: string | null
  beschreibung: string | null
  suggested_assistant: string | null
  pflicht: boolean
  vorhanden: boolean
  status: CatalogStatus
  doc_id: number | null
}

/** Antwort des Katalog-Endpoints. */
export interface Catalog {
  katalog: DocSpec[]
  weitere: Document[]
}

/** Pro-Schlüssel-State (modul:projekt). */
interface KeyState {
  catalog: Catalog | null
  documents: Document[]
  current: Document | null
  loading: boolean
  error: string | null
}

interface DocumentsState {
  byKey: Record<string, KeyState>
}

function makeKey(modul: string, projekt: string): string {
  return `${modul}:${projekt}`
}

function emptyKeyState(): KeyState {
  return { catalog: null, documents: [], current: null, loading: false, error: null }
}

/** Basis-URL-Segment je Modul. */
function base(modul: string, projekt: string): string {
  return `/${modul}-dokumente/${encodeURIComponent(projekt)}`
}

function extractError(e: any, fallback: string): string {
  return e?.response?.data?.error || e?.message || fallback
}

export const useDocumentsStore = defineStore('documents', {
  state: (): DocumentsState => ({ byKey: {} }),

  getters: {
    /** Liefert (lazy) den State-Slice für modul:projekt. */
    keyState: (state) => {
      return (modul: string, projekt: string | null): KeyState => {
        if (!projekt) return emptyKeyState()
        return state.byKey[makeKey(modul, projekt)] ?? emptyKeyState()
      }
    },
  },

  actions: {
    /** Stellt sicher, dass ein State-Slice existiert, und gibt ihn zurück. */
    _ensure(modul: string, projekt: string): KeyState {
      const key = makeKey(modul, projekt)
      if (!this.byKey[key]) this.byKey[key] = emptyKeyState()
      return this.byKey[key]
    },

    async fetchCatalog(modul: string, projekt: string): Promise<Catalog | null> {
      const slice = this._ensure(modul, projekt)
      slice.loading = true
      slice.error = null
      try {
        const r = await apiClient.get(`${base(modul, projekt)}/catalog`)
        const cat: Catalog = {
          katalog: r.data?.katalog ?? [],
          weitere: r.data?.weitere ?? [],
        }
        slice.catalog = cat
        return cat
      } catch (e: any) {
        slice.error = extractError(e, 'Katalog konnte nicht geladen werden.')
        return null
      } finally {
        slice.loading = false
      }
    },

    async fetchDocuments(modul: string, projekt: string): Promise<Document[]> {
      const slice = this._ensure(modul, projekt)
      slice.loading = true
      slice.error = null
      try {
        const r = await apiClient.get(base(modul, projekt))
        slice.documents = Array.isArray(r.data) ? r.data : []
        return slice.documents
      } catch (e: any) {
        slice.error = extractError(e, 'Dokumente konnten nicht geladen werden.')
        return []
      } finally {
        slice.loading = false
      }
    },

    async fetchDocument(modul: string, projekt: string, id: number): Promise<Document | null> {
      const slice = this._ensure(modul, projekt)
      slice.error = null
      try {
        const r = await apiClient.get(`${base(modul, projekt)}/${id}`)
        slice.current = r.data ?? null
        return slice.current
      } catch (e: any) {
        slice.error = extractError(e, 'Dokument konnte nicht geladen werden.')
        return null
      }
    },

    async createDocument(
      modul: string,
      projekt: string,
      payload: {
        doc_type: string
        titel?: string
        content_html?: string
        source?: string
        assistant_key?: string
        meta?: Record<string, any>
      },
    ): Promise<number | null> {
      const slice = this._ensure(modul, projekt)
      slice.error = null
      try {
        const r = await apiClient.post(base(modul, projekt), payload)
        const id = r.data?.id ?? null
        await this.fetchCatalog(modul, projekt)
        return id
      } catch (e: any) {
        slice.error = extractError(e, 'Dokument konnte nicht angelegt werden.')
        return null
      }
    },

    async updateDocument(
      modul: string,
      projekt: string,
      id: number,
      payload: { titel?: string; content_html?: string; meta?: Record<string, any> },
    ): Promise<Document | null> {
      const slice = this._ensure(modul, projekt)
      slice.error = null
      try {
        const r = await apiClient.put(`${base(modul, projekt)}/${id}`, payload)
        const doc: Document | null = r.data?.dokument ?? null
        if (doc) slice.current = doc
        return doc
      } catch (e: any) {
        slice.error = extractError(e, 'Dokument konnte nicht gespeichert werden.')
        return null
      }
    },

    async setStatus(
      modul: string,
      projekt: string,
      id: number,
      status: DocStatus,
    ): Promise<Document | null> {
      const slice = this._ensure(modul, projekt)
      slice.error = null
      try {
        const r = await apiClient.post(`${base(modul, projekt)}/${id}/status`, { status })
        const doc: Document | null = r.data?.dokument ?? null
        if (doc) slice.current = doc
        return doc
      } catch (e: any) {
        slice.error = extractError(e, 'Status konnte nicht geändert werden.')
        return null
      }
    },

    async deleteDocument(modul: string, projekt: string, id: number): Promise<boolean> {
      const slice = this._ensure(modul, projekt)
      slice.error = null
      try {
        await apiClient.delete(`${base(modul, projekt)}/${id}`)
        if (slice.current?.id === id) slice.current = null
        await this.fetchCatalog(modul, projekt)
        return true
      } catch (e: any) {
        slice.error = extractError(e, 'Dokument konnte nicht gelöscht werden.')
        return false
      }
    },

    /**
     * Exportiert ein Dokument als DOCX/PDF und stößt den Browser-Download an.
     * Wirft bei Fehlern, damit der Aufrufer (z.B. 503 PDF-Konverter) reagieren kann.
     */
    async exportDocument(
      modul: string,
      projekt: string,
      id: number,
      format: 'docx' | 'pdf',
    ): Promise<void> {
      const r = await apiClient.post(
        `${base(modul, projekt)}/${id}/export?format=${format}`,
        {},
        { responseType: 'blob', timeout: 120000 },
      )
      const blob = r.data as Blob
      // Dateiname aus Content-Disposition wenn vorhanden, sonst Fallback.
      const cd = (r.headers?.['content-disposition'] || '') as string
      const match = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i)
      const filename = match
        ? decodeURIComponent(match[1])
        : `dokument_${id}.${format}`
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    },

    /**
     * Legt ein Dokument aus einem Assistenten-Ergebnis an (Block C, S8).
     * `content_html` ist bereits sanitisiertes HTML.
     */
    async createFromAssistant(
      modul: string,
      projekt: string,
      doc_type: string,
      assistant_key: string,
      content_html: string,
    ): Promise<number | null> {
      return this.createDocument(modul, projekt, {
        doc_type,
        content_html,
        source: 'assistant',
        assistant_key,
      })
    },
  },
})
