import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import apiClient from '../api/client'

export interface Risiko {
  id?: number
  projekt: string
  nr?: number
  name?: string
  risk_name?: string
  beschreibung?: string
  framework: string
  felder: Record<string, any>
  risikowert?: number | null
  wert?: number | null
  risiko_label?: string
  level?: string
  detail_text?: string
  bewertung_text?: string
  prompt_text?: string
  is_resolved?: boolean
  resolved_at?: string
  resolved_reason?: string
  farbe?: string
  status?: string
  created_at?: string
  updated_at?: string
}

export interface RBProjekt {
  id: string
  name: string
  framework: string
  beschreibung: string
  description: string
  // Issue #428: Firma-Verknüpfung wie in cra/nis2/dsgvo/aiact
  unternehmen?: string
  company?: string
  produkt?: string
  berater?: string
  // #764 Repo-Anbindung / #766 Software-Beschreibung + Doku-URLs
  vcs_publish?: VcsPublish
  software?: SoftwareMeta
  // #17 Stufe 1: Rück-Verknüpfung auf ein CRA-Projekt (rein informativ)
  linked_cra_projekt?: string | null
  risiken_count: number
  created_at?: string
  updated_at?: string
}

export interface VcsPublish {
  provider?: string
  repo?: string
  base_url?: string
  branch?: string
  token_env?: string
  path?: string
  // #784: ob ein (verschlüsselt gespeicherter) Token hinterlegt ist; der Wert
  // selbst wird nie ausgeliefert.
  has_token?: boolean
}

export interface SoftwareMeta {
  description?: string
  doc_urls?: string[]
}

export interface RBAttachment {
  id: string
  filename: string
  doc_type?: string
  doc_kind?: string
  url?: string
  tags?: string[]
  added_at?: number
}

export interface FrameworkInfo {
  id: string
  label: string
  description: string
}

export interface FrameworkField {
  key: string
  label: string
  typ: string
  optionen?: string[]
  gruppe?: string
}

/** #1764: Kennzahlen eines Projekts für Sortierung/Filter der Sidebar. */
export interface RisikoStats {
  gesamt: number
  offen: number
  reassess: number
}

/** #1520/#1526: Marker, den der Issue-Sync score-neutral in `bewertung_text` schreibt. */
// Eine Stelle fürs ganze Frontend (#1850); hier nur re-exportiert,
// damit die Bestands-Importe dieses Stores weiter gelten.
export { NEUBEWERTUNG_MARKER as REASSESS_MARKER } from '../utils/neubewertung'

export const useRisikobewertungStore = defineStore('risikobewertung', () => {
  const projekte = ref<RBProjekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  // #1569: Firmen-Übersicht (Produkte + Risiko-Cockpit) — Sicht über alle
  // Produktprojekte einer Firma; schließt sich mit einem gewählten Projekt aus.
  const selectedFirma = ref<string | null>(null)
  const firmaTab = ref<'produkte' | 'cockpit'>('produkte')
  watch(selectedProjekt, (v) => { if (v) selectedFirma.value = null })
  const openFirma = (firma: string, tab: 'produkte' | 'cockpit' = 'produkte') => {
    selectedProjekt.value = null
    selectedFirma.value = firma
    firmaTab.value = tab
  }
  const risiken = ref<Risiko[]>([])
  // #1764: Kennzahlen je Projekt (offene Risiken, „Neubewertung erforderlich")
  // für Sortierung und Filter der Sidebar — überlebt das Umschalten auf ein
  // einzelnes Projekt, weil `risiken` dabei ersetzt wird.
  const risikoStats = ref<Record<string, RisikoStats>>({})
  const frameworks = ref<FrameworkInfo[]>([])
  const frameworkFields = ref<Record<string, FrameworkField[]>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  const filteredRisiken = computed(() => {
    if (!selectedProjekt.value) return risiken.value
    return risiken.value.filter(r => r.projekt === selectedProjekt.value)
  })

  const selectedProjektObj = computed(() => {
    return projekte.value.find(p => p.name === selectedProjekt.value) || null
  })

  const maturityScore = computed(() => {
    const list = filteredRisiken.value
    if (list.length === 0) return 0
    // Vereinfacht: höhere Risikowerte = niedrigere Maturity
    const totalRisks = list.length
    const resolved = list.filter(r => r.is_resolved).length
    return Math.round((resolved / totalRisks) * 100)
  })

  const stats = computed(() => {
    const list = filteredRisiken.value
    return {
      total: list.length,
      kritisch: list.filter(r => (r.risiko_label || '').toLowerCase().includes('kritisch')).length,
      hoch: list.filter(r => (r.risiko_label || '').toLowerCase().includes('hoch')).length,
      mittel: list.filter(r => (r.risiko_label || '').toLowerCase().includes('mittel')).length,
      niedrig: list.filter(r => (r.risiko_label || '').toLowerCase().includes('niedrig')).length,
      resolved: list.filter(r => r.is_resolved).length,
    }
  })

  // ---- Frameworks ----

  const fetchFrameworks = async () => {
    if (frameworks.value.length > 0) return
    try {
      const res = await apiClient.get('/risikobewertung/frameworks')
      frameworks.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Frameworks'
    }
  }

  const fetchFrameworkFields = async (frameworkId: string): Promise<FrameworkField[]> => {
    if (frameworkFields.value[frameworkId]) return frameworkFields.value[frameworkId]
    try {
      const res = await apiClient.get(`/risikobewertung/frameworks/${frameworkId}/felder`)
      frameworkFields.value[frameworkId] = res.data.felder || []
      return frameworkFields.value[frameworkId]
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Framework-Felder'
      return []
    }
  }

  const calculateScore = async (frameworkId: string, felder: Record<string, any>) => {
    try {
      const res = await apiClient.post(`/risikobewertung/frameworks/${frameworkId}/calculate`, { felder })
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Berechnen'
      return null
    }
  }

  // ---- Projekte ----

  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/risikobewertung/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Projekte'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<RBProjekt>): Promise<RBProjekt | null> => {
    try {
      const res = await apiClient.post('/risikobewertung/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen des Projekts'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<RBProjekt>): Promise<RBProjekt | null> => {
    try {
      const res = await apiClient.put(`/risikobewertung/projekte/${encodeURIComponent(name)}`, data)
      const idx = projekte.value.findIndex(p => p.name === name)
      if (idx >= 0) projekte.value[idx] = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Aktualisieren'
      return null
    }
  }

  const deleteProjekt = async (name: string): Promise<boolean> => {
    try {
      await apiClient.delete(`/risikobewertung/projekte/${encodeURIComponent(name)}`)
      projekte.value = projekte.value.filter(p => p.name !== name)
      if (selectedProjekt.value === name) selectedProjekt.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  // ---- Risiken ----

  const fetchRisikenForProjekt = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken`)
      risiken.value = res.data
      aktualisiereRisikoStats(res.data, projektName)
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Risiken'
    }
  }

  /** Lädt alle Risiken über alle Projekte (Kompatibilität mit RisikobewertungSidebar). */
  const fetchRisiken = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/risikobewertung')
      risiken.value = res.data
      aktualisiereRisikoStats(res.data)
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  /**
   * #1764: Kennzahlen je Projekt für Sortierung und Filter der Sidebar.
   *
   * `risiken` wird beim Öffnen eines Projekts auf dessen Risiken reduziert —
   * die Sidebar braucht die Zahlen aber für **alle** Projekte. Deshalb werden
   * sie beim Laden mitgeschrieben und bleiben erhalten, auch wenn `risiken`
   * später nur noch ein Projekt enthält. Kein zusätzlicher Request.
   */
  const aktualisiereRisikoStats = (liste: Risiko[], nurProjekt?: string) => {
    const naechste: Record<string, RisikoStats> = nurProjekt
      ? { ...risikoStats.value, [nurProjekt]: { gesamt: 0, offen: 0, reassess: 0 } }
      : {}
    for (const r of liste || []) {
      const key = r.projekt || (r as any).projekt_name || nurProjekt
      if (!key) continue
      if (nurProjekt && key !== nurProjekt) continue
      const eintrag = naechste[key] ?? { gesamt: 0, offen: 0, reassess: 0 }
      eintrag.gesamt += 1
      if (!r.is_resolved) eintrag.offen += 1
      // #1520/#1526: Marker aus dem Issue-Sync, score-neutral im Bewertungstext.
      if (String(r.bewertung_text || '').includes(REASSESS_MARKER)) eintrag.reassess += 1
      naechste[key] = eintrag
    }
    risikoStats.value = naechste
  }

  const createRisiko = async (projektName: string, data: Partial<Risiko>): Promise<Risiko | null> => {
    try {
      const res = await apiClient.post(`/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken`, data)
      risiken.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateRisiko = async (projektName: string, riskId: number, data: Partial<Risiko>): Promise<Risiko | null> => {
    try {
      const res = await apiClient.put(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}`,
        data,
      )
      const idx = risiken.value.findIndex(r => r.id === riskId)
      if (idx >= 0) risiken.value[idx] = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Aktualisieren'
      return null
    }
  }

  const deleteRisiko = async (riskId: number, projektName?: string): Promise<boolean> => {
    try {
      if (projektName) {
        await apiClient.delete(`/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}`)
      } else {
        await apiClient.delete(`/risikobewertung/${riskId}`)
      }
      risiken.value = risiken.value.filter(r => r.id !== riskId)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  // #1674: formale Risikobehandlung inkl. CRA-konformer Akzeptanz
  const setBehandlung = async (projektName: string, riskId: number, payload: Record<string, any>) => {
    try {
      await apiClient.patch(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/behandlung`,
        payload,
      )
      const r = risiken.value.find(x => x.id === riskId)
      if (r) {
        r.behandlung = payload.behandlung
        r.akzeptanz_kategorie = payload.kategorie || ''
        r.akzeptanz_grund = payload.grund || ''
        r.akzeptanz_von = payload.von || ''
        if (payload.behandlung === 'akzeptiert') { r.is_resolved = true; r.status = 'Resolved' }
      }
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler bei der Risikobehandlung'
      return false
    }
  }

  const resolveRisiko = async (projektName: string, riskId: number, resolved: boolean, reason: string = '') => {
    try {
      await apiClient.patch(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/resolve`,
        { resolved, reason },
      )
      const r = risiken.value.find(x => x.id === riskId)
      if (r) {
        r.is_resolved = resolved
        r.resolved_reason = reason
        r.status = resolved ? 'Resolved' : 'Aktiv'
      }
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Resolve'
      return false
    }
  }

  // ---- Single-Risk Prompts + Ollama + Issue ----

  const getRiskPrompt = async (projektName: string, riskId: number): Promise<string | null> => {
    try {
      const res = await apiClient.get(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/prompt`,
      )
      return res.data.prompt || null
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Generieren des Prompts'
      return null
    }
  }

  const parseRiskResponse = async (projektName: string, riskId: number, raw: string, apply: boolean = true) => {
    try {
      const res = await apiClient.post(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/parse-response`,
        { raw, apply },
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Parsen der Antwort'
      return null
    }
  }

  const ollamaSingleRisk = async (projektName: string, riskId: number) => {
    try {
      const res = await apiClient.post(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/ollama`,
      )
      return res.data
    } catch (err: any) {
      // Mehrere Detail-Quellen sammeln (Issue: "Details werden nicht angezeigt")
      const data = err?.response?.data || {}
      const parts: string[] = []
      if (data.error) parts.push(String(data.error))
      if (data.ollama_url) parts.push(`URL: ${data.ollama_url}`)
      if (data.ollama_model) parts.push(`Model: ${data.ollama_model}`)
      if (data.raw_preview) parts.push(`Antwort: ${String(data.raw_preview).slice(0, 200)}`)
      if (!parts.length && err?.message) parts.push(err.message)
      if (!parts.length) parts.push('Fehler bei Ollama-Bewertung')
      error.value = parts.join(' · ')
      return null
    }
  }

  const reAssessmentPrompt = async (projektName: string, riskId: number, issueContext: string): Promise<string | null> => {
    try {
      const res = await apiClient.post(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/re-assessment-prompt`,
        { issue_context: issueContext },
      )
      return res.data.prompt || null
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Generieren des Re-Assessment-Prompts'
      return null
    }
  }

  const importIssueText = async (projektName: string, riskId: number, issueContext: string) => {
    try {
      const res = await apiClient.post(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/import-issue`,
        { issue_context: issueContext },
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Importieren'
      return null
    }
  }

  // ---- Issue-Verknüpfung (bestehende Issues, #1685) ----

  const listRiskIssues = async (projektName: string, riskId: number) => {
    try {
      const res = await apiClient.get(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/linked-issues`,
      )
      return res.data?.items || []
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden verknüpfter Issues'
      return []
    }
  }

  const linkRiskIssue = async (projektName: string, riskId: number, url: string) => {
    try {
      const res = await apiClient.post(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/issues/link`,
        { url },
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Verknüpfen fehlgeschlagen'
      return null
    }
  }

  const unlinkRiskIssue = async (projektName: string, riskId: number, linkId: string) => {
    try {
      await apiClient.delete(
        `/risikobewertung/projekte/${encodeURIComponent(projektName)}/risiken/${riskId}/issues/${encodeURIComponent(linkId)}`,
      )
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Entfernen fehlgeschlagen'
      return false
    }
  }

  // ---- Audit ----
  //
  // `fetchAudit` stand hier bis v8.2.0 und las `{events, total}` aus der
  // modul-eigenen Route. Die Route gibt es weiter, sie kommt aber seit #1851
  // aus `shared/audit_api` und liefert `{eintraege, …}` aus **zwei** Quellen
  // (Revisionspfad + Änderungsprotokoll). Die Funktion hier stehen zu lassen
  // hieße, einen Leseweg zu behalten, der stillschweigend eine leere Liste
  // ergibt — `res.data.events` ist dann `undefined`. Geladen wird in
  // `components/shared/AuditLogModal.vue`, in allen sechs Modulen gleich.

  return {
    projekte,
    selectedProjekt,
    selectedFirma,
    firmaTab,
    openFirma,
    selectedProjektObj,
    risiken,
    risikoStats,
    filteredRisiken,
    frameworks,
    frameworkFields,
    loading,
    error,
    maturityScore,
    stats,
    fetchFrameworks,
    fetchFrameworkFields,
    calculateScore,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchRisiken,
    fetchRisikenForProjekt,
    createRisiko,
    updateRisiko,
    deleteRisiko,
    resolveRisiko,
    setBehandlung,
    getRiskPrompt,
    parseRiskResponse,
    ollamaSingleRisk,
    reAssessmentPrompt,
    importIssueText,
    listRiskIssues,
    linkRiskIssue,
    unlinkRiskIssue,
  }
})
