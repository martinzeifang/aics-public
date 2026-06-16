import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/aiact-conformity'

export interface ConformityRecord {
  projekt_name?: string
  verfahren: string
  qms_geprueft: boolean
  techdoc_geprueft: boolean
  checkliste: Record<string, boolean>
  notified_body_name: string
  notified_body_kennnummer: string
  nb_zertifikat_datei: string
  nb_zertifikat_sha256: string
  ergebnis: string
  bewertungsdatum: string
  ce_angebracht_am: string
  wesentliche_aenderung_seit: string
  assessment_complete?: boolean
  reassessment_required?: boolean
  doc_allowed?: boolean
}

export interface DocGate {
  doc_allowed: boolean
  assessment_complete: boolean
  reassessment_required: boolean
  verfahren: string
  ergebnis: string
  ce_angebracht_am: string
}

export interface VerfahrenOption { code: string; label: string }
export interface ChecklistItem { key: string; label: string }

// #1243: Optionale CRA-Verknüpfung (read-only Referenz, jederzeit lösbar).
export interface CraLink {
  linked: boolean
  linked_cra_projekt: string
  manual_override: boolean
  cra_record: Record<string, any> | null
}

export const useAiactConformityStore = defineStore('aiactConformity', () => {
  const record = ref<ConformityRecord | null>(null)
  const docGate = ref<DocGate | null>(null)
  const verfahren = ref<VerfahrenOption[]>([])
  const checkliste = ref<ChecklistItem[]>([])
  const ergebnisWerte = ref<string[]>([])
  const craLink = ref<CraLink | null>(null)
  const craProjekte = ref<string[]>([])
  const loading = ref(false)
  const error = ref('')

  async function loadConstants() {
    try {
      const r = await apiClient.get(`${BASE}/constants`)
      verfahren.value = r.data?.verfahren || []
      checkliste.value = r.data?.checkliste || []
      ergebnisWerte.value = r.data?.ergebnis || []
    } catch { /* ignore */ }
  }

  async function load(projekt: string) {
    loading.value = true
    error.value = ''
    try {
      const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/conformity`)
      record.value = r.data?.record || null
      docGate.value = r.data?.doc_gate || null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
    } finally {
      loading.value = false
    }
  }

  async function save(projekt: string, rec: ConformityRecord) {
    const r = await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/conformity`, rec)
    record.value = r.data?.record || record.value
    docGate.value = r.data?.doc_gate || docGate.value
  }

  async function uploadCertificate(projekt: string, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    const r = await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/certificate`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    record.value = r.data?.record || record.value
    docGate.value = r.data?.doc_gate || docGate.value
  }

  // ── #1243 Optionale CRA-Verknüpfung ─────────────────────────────────────────
  async function loadCraLink(projekt: string) {
    try {
      const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/cra-link`)
      craLink.value = r.data || null
    } catch (e: any) { error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'; craLink.value = null }
  }

  async function loadCraProjekte() {
    try {
      const r = await apiClient.get(`${BASE}/cra-projekte`)
      craProjekte.value = r.data?.projekte || []
    } catch { craProjekte.value = [] }
  }

  async function setCraLink(projekt: string, payload: { linked_cra_projekt?: string; manual_override?: boolean }) {
    try {
      const r = await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/cra-link`, payload)
      craLink.value = r.data || craLink.value
      return true
    } catch (e: any) { error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'; return false }
  }

  return {
    record, docGate, verfahren, checkliste, ergebnisWerte, craLink, craProjekte, loading, error,
    loadConstants, load, save, uploadCertificate,
    loadCraLink, loadCraProjekte, setCraLink,
  }
})
