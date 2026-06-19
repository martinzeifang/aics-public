import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

// ──────────────────────────────────────────────────────────────────────────
// WiBA — „Weg in die Basis-Absicherung" (BSI IT-Grundschutz)
// Frontend-Store. Spiegelt Fehler-/Loading-Stil von stores/cra.ts.
// Alle Endpoints liegen unter /api/wiba (apiClient.baseURL == '/api').
// ──────────────────────────────────────────────────────────────────────────

export interface WiBAProjekt {
  id?: string
  name: string
  unternehmen: string
  beschreibung: string
  berater: string
  firmen_id?: number | null
  meta_json?: string
  created_at?: string
  updated_at?: string
}

export interface WiBAPrueffrage {
  control_id: string
  nr: string
  frage: string
  hilfsmittel: string
  aufwand: string
  status: string
  notiz: string
  verantwortlich: string
  zieldatum: string
  evidence_doc_ids: (string | number)[]
}

export interface WiBAThema {
  theme_key: string
  titel: string
  bausteine: string[]
  ziel: string
  hinweis: string
  weiterfuehrend: string
  prueffragen: WiBAPrueffrage[]
}

export interface WiBAReifegrad {
  gesamt_pct: number
  bewertet: number
  in_scope: number
  themen: Record<string, {
    titel: string
    total: number
    ja: number
    nein: number
    offen: number
    nicht_relevant: number
    pct: number
  }>
}

export const useWibaStore = defineStore('wiba', () => {
  const projekte = ref<WiBAProjekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const themen = ref<WiBAThema[]>([])
  const reifegrad = ref<WiBAReifegrad | null>(null)
  const constants = ref<any | null>(null)
  const catalogStatus = ref<any | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  const _pjUrl = (suffix: string): string => {
    if (!selectedProjekt.value) throw new Error('Kein Projekt ausgewählt')
    return `/wiba/projekte/${encodeURIComponent(selectedProjekt.value)}${suffix}`
  }

  // ──────────────────────────────────────────────────────────────────────
  // Konstanten + Katalog
  // ──────────────────────────────────────────────────────────────────────
  const fetchConstants = async () => {
    if (constants.value) return constants.value
    try {
      const res = await apiClient.get('/wiba/constants')
      constants.value = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Konstanten'
      return null
    }
  }

  const fetchCatalogStatus = async () => {
    try {
      const res = await apiClient.get('/wiba/catalog/status')
      catalogStatus.value = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden des Katalog-Status'
      return null
    }
  }

  const downloadCatalog = async () => {
    try {
      const res = await apiClient.post('/wiba/catalog/download', {}, { timeout: 600000 })
      catalogStatus.value = res.data?.meta || catalogStatus.value
      return res.data
    } catch (err: any) {
      const data = err?.response?.data
      error.value = data?.error || err?.message || 'Fehler beim Download des Katalogs'
      return data || null
    }
  }

  const ingestCatalog = async () => {
    try {
      const res = await apiClient.post('/wiba/catalog/ingest', {}, { timeout: 600000 })
      catalogStatus.value = res.data?.meta || catalogStatus.value
      return res.data
    } catch (err: any) {
      const data = err?.response?.data
      error.value = data?.error || err?.message || 'Fehler beim Import des Katalogs'
      return data || null
    }
  }

  const refreshCatalog = async () => {
    try {
      const res = await apiClient.post('/wiba/catalog/refresh', {}, { timeout: 600000 })
      catalogStatus.value = res.data?.meta || catalogStatus.value
      return res.data
    } catch (err: any) {
      const data = err?.response?.data
      error.value = data?.error || err?.message || 'Fehler beim Aktualisieren des Katalogs'
      return data || null
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // Projekte
  // ──────────────────────────────────────────────────────────────────────
  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/wiba/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Projekte'
    } finally {
      loading.value = false
    }
  }

  const fetchProjekt = async (name: string) => {
    try {
      const res = await apiClient.get(`/wiba/projekte/${encodeURIComponent(name)}`)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden des Projekts'
      return null
    }
  }

  const createProjekt = async (data: Partial<WiBAProjekt>) => {
    try {
      const res = await apiClient.post('/wiba/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<WiBAProjekt>) => {
    try {
      const res = await apiClient.put(`/wiba/projekte/${encodeURIComponent(name)}`, data)
      const idx = projekte.value.findIndex(p => p.name === name)
      if (idx >= 0) projekte.value[idx] = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern'
      return null
    }
  }

  const deleteProjekt = async (name: string) => {
    try {
      await apiClient.delete(`/wiba/projekte/${encodeURIComponent(name)}`)
      projekte.value = projekte.value.filter(p => p.name !== name)
      if (selectedProjekt.value === name) selectedProjekt.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // Controls (Themen + Prüffragen) + Reifegrad
  // ──────────────────────────────────────────────────────────────────────
  const fetchControls = async (projekt?: string) => {
    const p = projekt || selectedProjekt.value
    if (!p) return null
    try {
      const res = await apiClient.get(`/wiba/projekte/${encodeURIComponent(p)}/controls`)
      themen.value = res.data?.themen || []
      reifegrad.value = res.data?.reifegrad || null
      if (projekt) selectedProjekt.value = projekt
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Prüffragen'
      return null
    }
  }

  const saveAntwort = async (payload: {
    control_id: string
    status?: string
    notiz?: string
    verantwortlich?: string
    zieldatum?: string
    evidence_doc_ids?: (string | number)[]
  }) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(_pjUrl('/antworten'), payload)
      // Reifegrad aus Antwort übernehmen + lokale Frage patchen
      if (res.data?.reifegrad) reifegrad.value = res.data.reifegrad
      for (const t of themen.value) {
        const f = t.prueffragen.find(q => q.control_id === payload.control_id)
        if (f) {
          if (payload.status !== undefined) f.status = payload.status
          if (payload.notiz !== undefined) f.notiz = payload.notiz
          if (payload.verantwortlich !== undefined) f.verantwortlich = payload.verantwortlich
          if (payload.zieldatum !== undefined) f.zieldatum = payload.zieldatum
          if (payload.evidence_doc_ids !== undefined) f.evidence_doc_ids = payload.evidence_doc_ids
          break
        }
      }
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern der Antwort'
      return null
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // Repo-Config (pro Projekt)
  // ──────────────────────────────────────────────────────────────────────
  const getRepoConfig = async () => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.get(_pjUrl('/repo-config'))
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Repo-Konfiguration'
      return null
    }
  }

  const putRepoConfig = async (vcs_publish: Record<string, any>) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.put(_pjUrl('/repo-config'), { vcs_publish })
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern der Repo-Konfiguration'
      return null
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // Issue-Verknüpfung pro Prüffrage (control)
  // ──────────────────────────────────────────────────────────────────────
  const fetchControlIssues = async (controlId: string) => {
    if (!selectedProjekt.value) return []
    try {
      const res = await apiClient.get(
        _pjUrl(`/controls/${encodeURIComponent(controlId)}/issues`),
      )
      return res.data || []
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Issues'
      return []
    }
  }

  const createControlIssue = async (controlId: string, payload: any = {}) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        _pjUrl(`/controls/${encodeURIComponent(controlId)}/issues`),
        payload,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Erstellen des Issues'
      return null
    }
  }

  const syncControlIssues = async (controlId: string) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        _pjUrl(`/controls/${encodeURIComponent(controlId)}/issues/sync`),
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Sync der Issues'
      return null
    }
  }

  const unlinkControlIssue = async (controlId: string, linkId: string | number) => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.delete(
        _pjUrl(`/controls/${encodeURIComponent(controlId)}/issues/${linkId}`),
      )
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Entfernen des Issues'
      return false
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // KI-Prompt + JSON-Parse pro Prüffrage
  // ──────────────────────────────────────────────────────────────────────
  const buildPrompt = async (controlId: string, includeEvidence: boolean = true) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        _pjUrl(`/controls/${encodeURIComponent(controlId)}/prompt`),
        { include_evidence: includeEvidence },
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Erzeugen des Prompts'
      return null
    }
  }

  const parseResponse = async (controlId: string, raw: string, apply: boolean = true) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        _pjUrl(`/controls/${encodeURIComponent(controlId)}/parse-response`),
        { raw, apply },
      )
      if (apply && res.data?.reifegrad) reifegrad.value = res.data.reifegrad
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Parsen der Antwort'
      return null
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // Risiko-Übernahme + Risiken-Liste
  // ──────────────────────────────────────────────────────────────────────
  const promoteRisk = async (controlId: string, felder: Record<string, any> = {}) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        _pjUrl(`/controls/${encodeURIComponent(controlId)}/risk`),
        { felder },
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Übernehmen als Risiko'
      return null
    }
  }

  const fetchRisiken = async () => {
    if (!selectedProjekt.value) return { rb_projekt: null, risiken: [] }
    try {
      const res = await apiClient.get(_pjUrl('/risiken'))
      return res.data || { rb_projekt: null, risiken: [] }
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Risiken'
      return { rb_projekt: null, risiken: [] }
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // Nachweise (Firmen-Dokumente + DSGVO-TOM)
  // ──────────────────────────────────────────────────────────────────────
  const fetchFirmenEvidence = async () => {
    if (!selectedProjekt.value) return { firma: null, dokumente: [] }
    try {
      const res = await apiClient.get(_pjUrl('/firmen-evidence'))
      return res.data || { firma: null, dokumente: [] }
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Firmen-Nachweise'
      return { firma: null, dokumente: [] }
    }
  }

  const fetchTomEvidence = async () => {
    if (!selectedProjekt.value) return { firma: null, massnahmen: [] }
    try {
      const res = await apiClient.get(_pjUrl('/tom-evidence'))
      return res.data || { firma: null, massnahmen: [] }
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der TOM-Nachweise'
      return { firma: null, massnahmen: [] }
    }
  }

  return {
    // State
    projekte,
    selectedProjekt,
    selectedProjektObj,
    themen,
    reifegrad,
    constants,
    catalogStatus,
    loading,
    error,
    // Konstanten + Katalog
    fetchConstants,
    fetchCatalogStatus,
    downloadCatalog,
    ingestCatalog,
    refreshCatalog,
    // Projekte
    fetchProjekte,
    fetchProjekt,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    // Controls
    fetchControls,
    saveAntwort,
    // Repo
    getRepoConfig,
    putRepoConfig,
    // Issues
    fetchControlIssues,
    createControlIssue,
    syncControlIssues,
    unlinkControlIssue,
    // KI
    buildPrompt,
    parseResponse,
    // Risiko
    promoteRisk,
    fetchRisiken,
    // Nachweise
    fetchFirmenEvidence,
    fetchTomEvidence,
  }
})
