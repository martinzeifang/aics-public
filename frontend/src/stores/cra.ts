import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import apiClient from '../api/client'

export interface CRAProjekt {
  id: string
  name: string
  unternehmen: string
  company: string
  produkt: string
  produktklasse: string
  beschreibung: string
  description: string
  berater: string
  meta_json?: string
  created_at?: string
  updated_at?: string
}

export interface CRAAnforderung {
  id: string
  kapitel: string
  ref: string
  titel: string
  title?: string
  beschreibung: string
  description?: string
  hinweise: string
  gewichtung: number
  quelle: string
  bewertung: number
  score?: number
  kommentar: string
  notes?: string
  massnahme: string
  verantwortlich: string
  zieldatum: string
  status: 'pending' | 'partial' | 'complete'
  updated_at?: string
}

export interface OwaspControl {
  id: string
  control_number: string
  title: string
  description: string
  cra_articles: string[]
  ref: string
  evidence_hint: string
  status: number
  score: number
  kommentar: string
  evidence: any[]
  updated_at?: string
}

/** Phase 1 (#1746): Feststellung „das Produkt ist CRA-ready", nicht ein Rechenstand. */
export interface CraReady {
  status: string
  von?: string
  am?: string | null
  entzug_grund?: string
  ueberholt?: boolean
  gate?: any
  gate_bei_feststellung?: any
}

export interface RepoSuggestion {
  field_id: string
  score: number
  kommentar: string
  confidence: number
  rationale: string
  citations: any[]
}

export const useCraStore = defineStore('cra', () => {
  const projekte = ref<CRAProjekt[]>([])
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
  const anforderungen = ref<CRAAnforderung[]>([])
  const owaspControls = ref<OwaspControl[]>([])
  const reifegrad = ref<any | null>(null)
  const customAnforderungen = ref<any[]>([])
  const owaspSuggestions = ref<RepoSuggestion[]>([])
  const requirementSuggestions = ref<RepoSuggestion[]>([])
  const constants = ref<any | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  // ---- Konstanten ----
  const fetchConstants = async () => {
    if (constants.value) return constants.value
    try {
      const res = await apiClient.get('/cra/constants')
      constants.value = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return null
    }
  }

  // ---- Projekte ----
  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/cra/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<CRAProjekt>) => {
    try {
      const res = await apiClient.post('/cra/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<CRAProjekt>) => {
    try {
      const res = await apiClient.put(`/cra/projekte/${encodeURIComponent(name)}`, data)
      const idx = projekte.value.findIndex(p => p.name === name)
      if (idx >= 0) projekte.value[idx] = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return null
    }
  }

  const deleteProjekt = async (name: string) => {
    try {
      await apiClient.delete(`/cra/projekte/${encodeURIComponent(name)}`)
      projekte.value = projekte.value.filter(p => p.name !== name)
      if (selectedProjekt.value === name) selectedProjekt.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  // ---- Anforderungen ----
  const fetchAnforderungen = async (projekt: string) => {
    try {
      const res = await apiClient.get(`/cra/projekte/${encodeURIComponent(projekt)}/anforderungen`)
      anforderungen.value = res.data
      selectedProjekt.value = projekt
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    }
  }

  const saveBewertung = async (anforderungId: string, payload: any) => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.post(`/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/bewertungen`, {
        anforderung_id: anforderungId,
        bewertung: payload.bewertung ?? payload.score ?? 0,
        kommentar: payload.kommentar ?? '',
        massnahme: payload.massnahme ?? '',
        verantwortlich: payload.verantwortlich ?? '',
        zieldatum: payload.zieldatum ?? '',
      })
      const idx = anforderungen.value.findIndex(a => a.id === anforderungId)
      if (idx >= 0) {
        anforderungen.value[idx] = { ...anforderungen.value[idx], ...payload }
      }
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern'
      return false
    }
  }

  // ---- OWASP ----
  const fetchOwaspControls = async (projekt: string) => {
    try {
      const res = await apiClient.get(`/cra/projekte/${encodeURIComponent(projekt)}/owasp`)
      owaspControls.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    }
  }

  const updateOwaspControl = async (owaspId: string, payload: any) => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.put(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}`,
        {
          status: payload.status ?? payload.score ?? 0,
          kommentar: payload.kommentar ?? '',
          evidence: payload.evidence ?? [],
        },
      )
      const idx = owaspControls.value.findIndex(c => c.id === owaspId)
      if (idx >= 0) {
        owaspControls.value[idx] = { ...owaspControls.value[idx], ...payload }
      }
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Speichern'
      return false
    }
  }

  const addOwaspEvidence = async (owaspId: string, evidence: any) => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}/evidence`,
        { evidence },
      )
      await fetchOwaspControls(selectedProjekt.value)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  // ---- Anforderungen: Prompt + JSON-Parse + Issue-Linking ----

  const getAnforderungPrompt = async (reqId: string): Promise<string | null> => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.get(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/anforderungen/${encodeURIComponent(reqId)}/prompt`,
      )
      return res.data.prompt || null
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Generieren des Prompts'
      return null
    }
  }

  const parseAnforderungResponse = async (reqId: string, raw: string, apply: boolean = true) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/anforderungen/${encodeURIComponent(reqId)}/parse-response`,
        { raw, apply },
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Parsen'
      return null
    }
  }

  const fetchAnforderungIssues = async (reqId: string) => {
    if (!selectedProjekt.value) return []
    try {
      const res = await apiClient.get(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/anforderungen/${encodeURIComponent(reqId)}/issues`,
      )
      return res.data || []
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Issues'
      return []
    }
  }

  const createAnforderungIssue = async (reqId: string, payload: any) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/anforderungen/${encodeURIComponent(reqId)}/issues`,
        payload,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Erstellen des Issues'
      return null
    }
  }

  const linkAnforderungIssue = async (reqId: string, payload: any) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/anforderungen/${encodeURIComponent(reqId)}/issues/link`,
        payload,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Verknüpfen'
      return null
    }
  }

  const syncAnforderungIssues = async (reqId: string) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/anforderungen/${encodeURIComponent(reqId)}/issues/sync`,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Sync'
      return null
    }
  }

  const unlinkAnforderungIssue = async (reqId: string, linkId: string) => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.delete(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/anforderungen/${encodeURIComponent(reqId)}/issues/${linkId}`,
      )
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Entfernen'
      return false
    }
  }

  // ---- OWASP: Prompt + JSON-Parse + Issue-Linking ----

  const getOwaspPrompt = async (owaspId: string): Promise<string | null> => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.get(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}/prompt`,
      )
      return res.data.prompt || null
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Generieren des Prompts'
      return null
    }
  }

  const parseOwaspResponse = async (owaspId: string, raw: string, apply: boolean = true) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}/parse-response`,
        { raw, apply },
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Parsen'
      return null
    }
  }

  const fetchOwaspIssues = async (owaspId: string) => {
    if (!selectedProjekt.value) return []
    try {
      const res = await apiClient.get(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}/issues`,
      )
      return res.data || []
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Issues'
      return []
    }
  }

  const createOwaspIssue = async (owaspId: string, payload: any) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}/issues`,
        payload,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Erstellen des Issues'
      return null
    }
  }

  const linkOwaspIssue = async (owaspId: string, payload: any) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}/issues/link`,
        payload,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Verknüpfen'
      return null
    }
  }

  const syncOwaspIssues = async (owaspId: string) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}/issues/sync`,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Sync'
      return null
    }
  }

  const unlinkOwaspIssue = async (owaspId: string, linkId: string) => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.delete(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/${owaspId}/issues/${linkId}`,
      )
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Entfernen'
      return false
    }
  }

  // ---- Risiken: Issue-Linking (#1008) ----

  const fetchRisiken = async () => {
    if (!selectedProjekt.value) return { linked: false, risiken: [] }
    try {
      const res = await apiClient.get(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/risiken`,
      )
      return res.data || { linked: false, risiken: [] }
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Risiken'
      return { linked: false, risiken: [] }
    }
  }

  const fetchRiskIssues = async (riskId: string | number) => {
    if (!selectedProjekt.value) return []
    try {
      const res = await apiClient.get(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/risiken/${riskId}/issues`,
      )
      return res.data || []
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Issues'
      return []
    }
  }

  const createRiskIssue = async (riskId: string | number, payload: any = {}) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/risiken/${riskId}/issues`,
        payload,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Erstellen des Issues'
      return null
    }
  }

  const syncRiskIssues = async (riskId: string | number) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/risiken/${riskId}/issues/sync`,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Sync'
      return null
    }
  }

  const unlinkRiskIssue = async (riskId: string | number, linkId: string) => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.delete(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/risiken/${riskId}/issues/${linkId}`,
      )
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Entfernen'
      return false
    }
  }

  // ---- Schwachstellen (CVE): Issue-Linking (#1041) ----

  const fetchVulnIssues = async (vulnId: string | number) => {
    if (!selectedProjekt.value) return []
    try {
      const res = await apiClient.get(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/vulns/${vulnId}/issues`,
      )
      return res.data || []
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Issues'
      return []
    }
  }

  const createVulnIssue = async (vulnId: string | number, payload: any = {}) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/vulns/${vulnId}/issues`,
        payload,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Erstellen des Issues'
      return null
    }
  }

  const syncVulnIssues = async (vulnId: string | number) => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/vulns/${vulnId}/issues/sync`,
      )
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Sync'
      return null
    }
  }

  const unlinkVulnIssue = async (linkId: string) => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.delete(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/vulns/issues/${linkId}`,
      )
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Entfernen'
      return false
    }
  }

  const owaspRepoAlignment = async (repoUrl: string, branch: string = '') => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/owasp/repo-alignment`,
        { repo_url: repoUrl, branch },
        { timeout: 120000 },
      )
      return res.data
    } catch (err: any) {
      if (err?.code === 'ECONNABORTED') {
        error.value = 'Repo-Alignment-Timeout — bitte erneut versuchen.'
      } else {
        error.value = err?.response?.data?.error || err?.message || 'Fehler beim Repo-Alignment'
      }
      return null
    }
  }

  // ---- Reifegrad ----
  const fetchReifegrad = async (projekt: string) => {
    try {
      const res = await apiClient.get(`/cra/projekte/${encodeURIComponent(projekt)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Reifegrad'
    }
  }

  // ---- Custom-Anforderungen ----
  const fetchCustomAnforderungen = async () => {
    try {
      const res = await apiClient.get('/cra/anforderungen/custom')
      customAnforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
    }
  }

  const saveCustomAnforderung = async (data: any) => {
    try {
      await apiClient.post('/cra/anforderungen/custom', data)
      await fetchCustomAnforderungen()
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  const deleteCustomAnforderung = async (id: string) => {
    try {
      await apiClient.delete(`/cra/anforderungen/custom/${encodeURIComponent(id)}`)
      customAnforderungen.value = customAnforderungen.value.filter(c => c.id !== id)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  // ---- Repo-Scan + Prefill ----
  const fullRepoScan = async (repoUrl: string, branch: string = '') => {
    if (!selectedProjekt.value) return null
    try {
      const res = await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/repo-scan`,
        { repo_url: repoUrl, branch },
        { timeout: 120000 },  // Repo-Scan kann 30–60s dauern
      )
      owaspSuggestions.value = res.data.owasp_suggestions || []
      requirementSuggestions.value = res.data.requirement_suggestions || []
      return res.data
    } catch (err: any) {
      const data = err?.response?.data
      if (err?.code === 'ECONNABORTED') {
        error.value = 'Repo-Scan dauerte zu lange (Timeout). Bitte erneut versuchen.'
      } else if (data?.error === 'kein-github-token') {
        // Klare Anleitung statt nur "Fehler"
        error.value = data.message || 'GitHub-Token erforderlich — Einstellungen → 🐙 GitHub'
      } else {
        error.value = data?.message || data?.error || err?.message || 'Fehler beim Repo-Scan'
      }
      return null
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Phase A — Pflicht-Doku-Manager (Issues #472-#476)
  // ──────────────────────────────────────────────────────────────────

  const sboms = ref<any[]>([])
  const psirt = ref<any>({})
  const vulns = ref<any[]>([])
  const supportPeriod = ref<any>({})
  const threatModel = ref<any>({})
  const pflichtDokuStatus = ref<any | null>(null)

  // C3 In-App-Sync (#947/#948)
  const syncState = ref<any | null>(null)
  const syncRuns = ref<any[]>([])
  const syncRunning = ref(false)

  const _pjUrl = (suffix: string) => {
    if (!selectedProjekt.value) throw new Error('Kein Projekt ausgewählt')
    return `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}${suffix}`
  }

  const fetchSboms = async () => {
    try { sboms.value = (await apiClient.get(_pjUrl('/sbom'))).data || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim SBOM-Laden' }
  }
  const saveSbom = async (data: any) => {
    try { await apiClient.post(_pjUrl('/sbom'), data); await fetchSboms(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  const deleteSbom = async (id: number) => {
    try { await apiClient.delete(_pjUrl(`/sbom/${id}`)); await fetchSboms(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  /** #1770: SBOM-Attestation am Image holen (Container-Produkte). */
  const sbomAusRegistry = async (sbomId: number): Promise<any | null> => {
    try {
      const { data } = await apiClient.post(_pjUrl(`/sbom/${sbomId}/aus-registry`))
      await fetchSboms()
      await fetchSbomKomponenten(sbomId)
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Attestation nicht abrufbar'
      return null
    }
  }
  /** #1823: Das SBOM-Dokument herunterladen — egal, wo es liegt.
   *
   * Für eine Image-Referenz holt der Server die Attestation; für den
   * Ablageort liefert er die Datei. Eine externe http(s)-Adresse ruft er
   * bewusst nicht ab (SSRF, #1761) — dort antwortet er mit 409 und der URL,
   * und wir öffnen sie direkt.
   */
  const sbomHerunterladen = async (sbom: any): Promise<boolean> => {
    try {
      const res = await apiClient.get(_pjUrl(`/sbom/${sbom.id}/download`),
                                      { responseType: 'blob' })
      const name = (res.headers?.['content-disposition'] || '')
        .match(/filename="?([^";]+)"?/)?.[1]
        || `sbom-${sbom.release_version || 'export'}.json`
      const url = URL.createObjectURL(new Blob([res.data],
                                               { type: 'application/json' }))
      const a = document.createElement('a')
      a.href = url
      a.download = name
      a.click()
      URL.revokeObjectURL(url)
      return true
    } catch (e: any) {
      // Der Fehlertext steckt bei responseType 'blob' im Blob, nicht im Objekt.
      let daten: any = e?.response?.data
      if (daten instanceof Blob) {
        try { daten = JSON.parse(await daten.text()) } catch { daten = null }
      }
      if (daten?.error === 'url-extern' && daten.url) {
        window.open(daten.url, '_blank', 'noopener')
        return true
      }
      error.value = daten?.message || daten?.error || 'Download fehlgeschlagen'
      return false
    }
  }
  /** #1769: SBOMs aus dem Ablageort im Dateisystem übernehmen. */
  const einleseSboms = async (): Promise<any | null> => {
    try {
      const { data } = await apiClient.post(_pjUrl('/sbom/einlesen'))
      if ((data?.angelegt || []).length) await fetchSboms()
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Einlesen fehlgeschlagen'
      return null
    }
  }

  // C1: Komponentenliste je SBOM + Release-Vergleich (Art. 13 Abs. 5, #1761).
  // `cra_sbom` hielt nur eine Komponenten-Zahl; damit war der Release-Punkt
  // „neue oder angehobene Fremdkomponenten bewertet" unbeantwortbar.
  const sbomKomponenten = ref<Record<string, any[]>>({})
  const sbomBefund = ref<any | null>(null)

  const fetchSbomKomponenten = async (sbomId: number) => {
    try {
      const { data } = await apiClient.get(_pjUrl(`/sbom/${sbomId}/komponenten`))
      sbomKomponenten.value = { ...sbomKomponenten.value, [String(sbomId)]: data || [] }
      return data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden der Komponenten'
      return []
    }
  }
  /** `payload` ist entweder `{ sbom: '<Dateiinhalt>' }` oder `{ komponenten: [...] }`. */
  const importSbomKomponenten = async (sbomId: number, payload: any) => {
    try {
      const { data } = await apiClient.post(_pjUrl(`/sbom/${sbomId}/komponenten`), payload)
      await fetchSbomKomponenten(sbomId)
      await fetchSboms()
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Einlesen der SBOM'
      return null
    }
  }
  const bewerteSbomKomponenten = async (ids: number[], status: string, notiz: string) => {
    try {
      await apiClient.put(_pjUrl('/sbom/komponenten/bewertung'), { ids, status, notiz })
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler bei der Bewertung'
      return false
    }
  }
  const fetchSbomVergleich = async (version: string, vorgaenger = '') => {
    try {
      const q = new URLSearchParams({ version })
      if (vorgaenger) q.set('vorgaenger', vorgaenger)
      const { data } = await apiClient.get(_pjUrl(`/sbom/vergleich?${q.toString()}`))
      sbomBefund.value = data
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Release-Vergleich'
      return null
    }
  }

  // #1773: Komponenten in Klassen bewerten. Eine echte SBOM führt 184
  // Komponenten; beim Erst-Release gilt jede als neu. 184 Einzelentscheidungen
  // sind der Punkt, an dem ein Prüfpunkt umgangen statt beantwortet wird.
  const fetchKomponentenKlassen = async (sbomId: number, version = '') => {
    try {
      const q = version ? `?version=${encodeURIComponent(version)}` : ''
      const { data } = await apiClient.get(_pjUrl(`/sbom/${sbomId}/klassen${q}`))
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden der Klassen'
      return null
    }
  }
  /** Prompt für den Begründungs-Entwurf einer Gruppe — gebaut vom Server. */
  const klassenPrompt = async (sbomId: number, gruppe: string, version = '') => {
    try {
      const { data } = await apiClient.post(
        _pjUrl(`/sbom/${sbomId}/klassen/prompt`), { gruppe, version })
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Prompt konnte nicht gebaut werden'
      return null
    }
  }
  /**
   * Begründung für eine ganze Gruppe übernehmen.
   * Rückgabe `{ ok }` oder `{ confirm: true, ... }` bei 428 — die Gruppe
   * „Einzelprüfung" (offener Befund) verlangt eine ausdrückliche Bestätigung.
   */
  const uebernehmeKlasse = async (sbomId: number, payload: any) => {
    try {
      const { data } = await apiClient.post(
        _pjUrl(`/sbom/${sbomId}/klassen/uebernehmen`), payload)
      return { ok: true, ...data }
    } catch (e: any) {
      const res = e?.response
      if (res?.status === 428) return { confirm: true, ...(res.data || {}) }
      error.value = res?.data?.error || 'Übernahme fehlgeschlagen'
      return { ok: false }
    }
  }

  // C3: Meldung an den Hersteller der Fremdkomponente (Art. 13 Abs. 6, #1761).
  const upstreamBefund = ref<any | null>(null)
  const upstreamPflicht = ref<Record<string, any>>({})

  const fetchUpstreamStatus = async () => {
    try {
      const { data } = await apiClient.get(_pjUrl('/vuln/upstream'))
      upstreamBefund.value = data?.befund || null
      upstreamPflicht.value = data?.pflicht || {}
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Laden der Meldepflichten'
      return null
    }
  }
  const setUpstreamMeldung = async (vulnId: number, payload: any) => {
    try {
      await apiClient.put(_pjUrl(`/vuln/${vulnId}/upstream`), payload)
      await fetchVulns()
      await fetchUpstreamStatus()
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Fehler beim Speichern der Meldung'
      return false
    }
  }

  const fetchPsirt = async () => {
    try { psirt.value = (await apiClient.get(_pjUrl('/psirt'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const savePsirt = async (data: any) => {
    try { await apiClient.post(_pjUrl('/psirt'), data); await fetchPsirt(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchVulns = async (status?: string) => {
    try {
      const q = status ? `?status=${status}` : ''
      vulns.value = (await apiClient.get(_pjUrl(`/vuln${q}`))).data || []
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveVuln = async (data: any) => {
    try { await apiClient.post(_pjUrl('/vuln'), data); await fetchVulns(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  const deleteVuln = async (id: number) => {
    try { await apiClient.delete(_pjUrl(`/vuln/${id}`)); await fetchVulns(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchSupportPeriod = async () => {
    try { supportPeriod.value = (await apiClient.get(_pjUrl('/support-period'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  // #1762: Die Pflichtangaben werden serverseitig geprüft (Support unter 5 Jahren
  // ohne Begründung, unbrauchbare Kaufhinweis-Adresse). Die Meldung des Servers
  // sagt, was fehlt und warum — sie gehört an das Formular und nicht in die
  // allgemeine Fehlerzeile, wo sie zwischen Sync-Meldungen untergeht.
  const supportPeriodFehler = ref<string | null>(null)
  const saveSupportPeriod = async (data: any) => {
    supportPeriodFehler.value = null
    try {
      const res = await apiClient.post(_pjUrl('/support-period'), data)
      supportPeriod.value = res.data?.data || {}
      await fetchSupportFristen()
      return true
    } catch (e: any) {
      const msg = e?.response?.data?.error || 'Fehler'
      supportPeriodFehler.value = msg
      error.value = msg
      return false
    }
  }

  // #1762: Fristenlauf der Aufbewahrungs-/Update-Verfügbarkeitsfristen. Bisher
  // wurden die Daten nur angezeigt; eine Frist ohne Ampel fällt niemandem auf.
  const supportFristen = ref<any>({ fristen: [], berechenbar: false })
  const fetchSupportFristen = async () => {
    try {
      supportFristen.value =
        (await apiClient.get(_pjUrl('/support-period/fristen'))).data || {}
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }

  // #1207: PSIRT-SLA-Tracking gegen offene CVEs.
  const slaStatus = ref<any>({ items: [], violations: 0, due_soon: 0, total_open: 0 })
  const fetchSlaStatus = async () => {
    try { slaStatus.value = (await apiClient.get(_pjUrl('/vuln/sla-status'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }

  const fetchThreatModel = async () => {
    try { threatModel.value = (await apiClient.get(_pjUrl('/threatmodel'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveThreatModel = async (data: any) => {
    try { await apiClient.post(_pjUrl('/threatmodel'), data); await fetchThreatModel(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchPflichtDokuStatus = async () => {
    try { pflichtDokuStatus.value = (await apiClient.get(_pjUrl('/pflicht-doku'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }

  const autodetectPflichtDoku = async (repo: string, dryRun = false) => {
    try {
      const q = dryRun ? '?dry_run=true' : ''
      const res = await apiClient.post(_pjUrl(`/pflicht-doku/autodetect${q}`), { repo })
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler bei Auto-Detection'; return null }
  }

  // ── C3 In-App-Sync (#947/#948) ───────────────────────────────────────────
  const fetchSyncStatus = async () => {
    if (!selectedProjekt.value) return
    try {
      const res = await apiClient.get(`/cra/sync-vulns/status?projekt=${encodeURIComponent(selectedProjekt.value)}`)
      syncState.value = res.data?.last_sync || null
      syncRunning.value = !!res.data?.running
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Sync-Status' }
  }
  const fetchSyncRuns = async () => {
    if (!selectedProjekt.value) return
    try {
      const res = await apiClient.get(`/cra/sync-vulns/runs?projekt=${encodeURIComponent(selectedProjekt.value)}&limit=20`)
      syncRuns.value = res.data?.runs || []
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler bei Sync-Historie' }
  }
  // Startet den Sync und pollt bis Abschluss; liefert den letzten Report.
  const startVulnSync = async (source = 'all', repo = '') => {
    if (!selectedProjekt.value) return null
    try {
      const body: any = { projekt: selectedProjekt.value, source }
      if (repo) body.repo = repo
      const res = await apiClient.post('/cra/sync-vulns', body)
      syncRunning.value = true
      const runId = res.data?.run_id
      // Polling alle 2s bis kein laufender Run mehr
      for (let i = 0; i < 150; i++) {
        await new Promise(r => setTimeout(r, 2000))
        await fetchSyncStatus()
        if (!syncRunning.value) break
      }
      await Promise.all([fetchSyncRuns(), fetchVulns()])
      const last = syncRuns.value.find((r: any) => r.id === runId) || syncRuns.value[0]
      return last?.report || syncState.value
    } catch (e: any) {
      syncRunning.value = false
      const st = e?.response?.status
      error.value = st === 409
        ? 'Ein Sync läuft bereits für dieses Projekt.'
        : (e?.response?.data?.error || 'Sync fehlgeschlagen')
      return null
    }
  }

  // Phase B — KI-Wizards
  const branchenTemplates = ref<any[]>([])
  const fetchBranchenTemplates = async () => {
    try { branchenTemplates.value = (await apiClient.get('/cra/wizards/branchen-templates')).data || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const applyBranchenTemplate = async (brancheId: string) => {
    try { await apiClient.post(_pjUrl('/wizards/branchen-template/apply'), { branche_id: brancheId }); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  // #1237/#1239: eu-doc + sbom-doc liefern editier-/exportierbare Dokumente
  // (Persistenz über „Als Dokument speichern"), daher kein apply-Pfad.
  type CraWizardKind = 'klassifikator' | 'vuln-policy' | 'update-policy' | 'eu-doc' | 'sbom-doc' | 'version-changes'
  const getWizardPrompt = async (wizard: CraWizardKind) => {
    try { return (await apiClient.get(_pjUrl(`/wizards/${wizard}/prompt`))).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }

  // #1247: Klassifizierung (C6/C7) read-back + manuelle Produktklasse setzen.
  const fetchKlassifizierung = async () => {
    try { return (await apiClient.get(_pjUrl('/klassifizierung'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }
  const setKlassifizierung = async (produktklasse: string, begruendung?: string) => {
    try {
      const res = await apiClient.put(_pjUrl('/klassifizierung'), { produktklasse, begruendung })
      const idx = projekte.value.findIndex(p => p.name === selectedProjekt.value)
      if (idx >= 0) projekte.value[idx] = res.data
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }

  // #1248: Versions-Änderungen aus GitHub/GitLab importieren.
  const fetchRepoVersions = async () => {
    try { return (await apiClient.get(_pjUrl('/versions'))).data }
    catch (e: any) { return { error: e?.response?.data?.error || 'Fehler beim Laden der Versionen' } }
  }
  const fetchVersionDiff = async (base: string, head: string) => {
    try {
      const res = await apiClient.get(_pjUrl('/version-diff'), { params: { base, head } })
      return res.data
    } catch (e: any) { return { error: e?.response?.data?.error || 'Fehler beim Laden der Änderungen' } }
  }
  const parseWizardResponse = async (wizard: CraWizardKind, response: string, apply = true) => {
    try {
      // #567: apply ist Backend-Default; dry_run nur explizit setzen wenn !apply
      const body: any = { response }
      if (!apply) body.dry_run = true
      const res = await apiClient.post(_pjUrl(`/wizards/${wizard}/parse`), body)
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }

  const acceptSuggestion = async (fieldId: string, score: number, kommentar: string, target: 'requirement' | 'owasp' = 'requirement') => {
    if (!selectedProjekt.value) return false
    try {
      await apiClient.post(
        `/cra/projekte/${encodeURIComponent(selectedProjekt.value)}/prefill/accept`,
        { field_id: fieldId, score, kommentar, target },
      )
      // Suggestion lokal entfernen
      if (target === 'owasp') {
        owaspSuggestions.value = owaspSuggestions.value.filter(s => s.field_id !== fieldId)
      } else {
        requirementSuggestions.value = requirementSuggestions.value.filter(s => s.field_id !== fieldId)
      }
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Release-Vorgänge + Phase-1-Feststellung (#1742/#1747) — v8.0.0
  //
  // CRA zerfällt für den Anwender in zwei Phasen: das Produkt einmalig in den
  // konformen Zustand bringen (Phase 1, „CRA-ready"), und danach bei jedem
  // Release nachweisen, dass es dabei geblieben ist (Phase 2, der Vorgang).
  // Beide hängen am selben Projekt, deshalb liegen sie hier zusammen.
  //
  // Die Schreibfunktionen werfen bewusst durch: Jede Regelverletzung kommt vom
  // Backend als 409 mit erklärendem Klartext („Wer einreicht, darf nicht
  // freigeben …"). Diesen Text soll der Anwender lesen — eine eigene Meldung im
  // Frontend wäre eine zweite, schlechtere Wahrheit.
  // ──────────────────────────────────────────────────────────────────

  const releases = ref<any[]>([])
  const releaseKatalog = ref<any[]>([])
  const craReady = ref<CraReady | null>(null)
  const aktuelleVersion = ref('')

  /** #1747: Dashboard-KPI — Vorgänge, die auf die Prüfung durch Compliance warten. */
  const releasesInPruefung = computed(
    () => releases.value.filter(r => r.freigabe_status === 'in_pruefung').length)

  const _relUrl = (suffix = '') => {
    if (!selectedProjekt.value) throw new Error('Kein Projekt ausgewählt')
    return `/cra-konformitaet/projekte/${encodeURIComponent(selectedProjekt.value)}${suffix}`
  }

  /** Liste der Vorgänge + Phase-1-Zeile in einem Aufruf (so liefert sie das Backend). */
  const fetchReleases = async () => {
    if (!selectedProjekt.value) return
    try {
      const d = (await apiClient.get(_relUrl('/releases'))).data || {}
      releases.value = d.releases || []
      aktuelleVersion.value = d.aktuelle_version || ''
      craReady.value = d.cra_ready || null
    } catch (e: any) {
      releases.value = []
      error.value = e?.response?.data?.error || 'Fehler beim Laden der Releases'
    }
  }

  const fetchReleaseKatalog = async () => {
    try {
      const d = (await apiClient.get(_relUrl('/releases/katalog'))).data || {}
      releaseKatalog.value = d.katalog || []
      return d
    } catch { return { katalog: [] } }
  }

  const fetchReleaseDetail = async (version: string) =>
    (await apiClient.get(_relUrl(`/releases/${encodeURIComponent(version)}`))).data

  // Ein GET legt bewusst keinen Vorgang an — sonst erzeugte ein Deep-Link mit
  // Tippfehler in der Version einen leeren Entwurf. Angelegt wird ausdrücklich.
  const releaseAnlegen = async (version: string) =>
    (await apiClient.post(_relUrl(`/releases/${encodeURIComponent(version)}`))).data

  const setReleaseChecklistItem = async (
    version: string, itemId: string, status: string, begruendung: string) =>
    (await apiClient.put(
      _relUrl(`/releases/${encodeURIComponent(version)}/checkliste/${encodeURIComponent(itemId)}`),
      { status, begruendung })).data

  // #1793: Die Art erklären. Die Antwort kommt mit einem Vorschlag für die
  // Kernfrage zurück — der füllt das Formular, gespeichert wird er erst mit
  // setWesentlicheAenderung.
  const setReleaseArt = async (version: string, art: string) =>
    (await apiClient.put(
      _relUrl(`/releases/${encodeURIComponent(version)}/art`), { art })).data

  const setWesentlicheAenderung = async (version: string, wert: string, grund: string) =>
    (await apiClient.put(
      _relUrl(`/releases/${encodeURIComponent(version)}/wesentliche-aenderung`),
      { wert, grund })).data

  const releaseEinreichen = async (version: string) =>
    (await apiClient.post(_relUrl(`/releases/${encodeURIComponent(version)}/einreichen`))).data

  const releaseZurueckweisen = async (version: string, grund: string) =>
    (await apiClient.post(
      _relUrl(`/releases/${encodeURIComponent(version)}/zurueckweisen`), { grund })).data

  const releaseVeroeffentlichen = async (version: string) =>
    (await apiClient.post(_relUrl(`/releases/${encodeURIComponent(version)}/veroeffentlichen`))).data

  /** Freigabe ist der bestehende Governance-Sign-off (#1220-A), kein neuer Endpunkt. */
  const releaseFreigeben = async (version: string) =>
    (await apiClient.post(_relUrl('/konformitaet/freigeben'), { release_version: version })).data

  const fetchCraReady = async () => {
    const d = (await apiClient.get(_relUrl('/cra-ready'))).data
    craReady.value = d
    return d
  }

  const craReadyFeststellen = async () =>
    (await apiClient.post(_relUrl('/cra-ready/feststellen'))).data

  const craReadyEntziehen = async (grund: string) =>
    (await apiClient.post(_relUrl('/cra-ready/entziehen'), { grund })).data

  return {
    projekte,
    selectedProjekt,
    selectedFirma,
    firmaTab,
    openFirma,
    selectedProjektObj,
    anforderungen,
    owaspControls,
    reifegrad,
    customAnforderungen,
    owaspSuggestions,
    requirementSuggestions,
    constants,
    loading,
    error,
    fetchConstants,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchAnforderungen,
    saveBewertung,
    fetchOwaspControls,
    updateOwaspControl,
    addOwaspEvidence,
    owaspRepoAlignment,
    getAnforderungPrompt,
    parseAnforderungResponse,
    fetchAnforderungIssues,
    createAnforderungIssue,
    linkAnforderungIssue,
    syncAnforderungIssues,
    unlinkAnforderungIssue,
    getOwaspPrompt,
    parseOwaspResponse,
    fetchOwaspIssues,
    createOwaspIssue,
    linkOwaspIssue,
    syncOwaspIssues,
    unlinkOwaspIssue,
    fetchRisiken,
    fetchRiskIssues,
    createRiskIssue,
    syncRiskIssues,
    unlinkRiskIssue,
    fetchVulnIssues,
    createVulnIssue,
    syncVulnIssues,
    unlinkVulnIssue,
    fetchReifegrad,
    fetchCustomAnforderungen,
    saveCustomAnforderung,
    deleteCustomAnforderung,
    fullRepoScan,
    acceptSuggestion,
    // Phase A — Pflicht-Doku
    sboms,
    psirt,
    vulns,
    supportPeriod,
    supportPeriodFehler,
    supportFristen,
    threatModel,
    pflichtDokuStatus,
    fetchSboms,
    einleseSboms,
    sbomAusRegistry,
    sbomHerunterladen,
    saveSbom,
    deleteSbom,
    // #1761 — Komponentenliste, Release-Vergleich, Upstream-Meldung
    sbomKomponenten,
    sbomBefund,
    fetchSbomKomponenten,
    importSbomKomponenten,
    bewerteSbomKomponenten,
    fetchSbomVergleich,
    // #1773: Gruppierung nach Klasse + KI-Entwurf je Gruppe
    fetchKomponentenKlassen,
    klassenPrompt,
    uebernehmeKlasse,
    upstreamBefund,
    upstreamPflicht,
    fetchUpstreamStatus,
    setUpstreamMeldung,
    fetchPsirt,
    savePsirt,
    fetchVulns,
    saveVuln,
    deleteVuln,
    fetchSupportPeriod,
    saveSupportPeriod,
    fetchSupportFristen,
    slaStatus,
    fetchSlaStatus,
    fetchThreatModel,
    saveThreatModel,
    fetchPflichtDokuStatus,
    autodetectPflichtDoku,
    // C3 In-App-Sync (#947/#948)
    syncState,
    syncRuns,
    syncRunning,
    fetchSyncStatus,
    fetchSyncRuns,
    startVulnSync,
    // Phase B
    branchenTemplates,
    fetchBranchenTemplates,
    applyBranchenTemplate,
    getWizardPrompt,
    parseWizardResponse,
    // #1247 Klassifizierung · #1248 Versions-Import
    fetchKlassifizierung,
    setKlassifizierung,
    fetchRepoVersions,
    fetchVersionDiff,
    // Release-Vorgänge + Phase 1 (#1742/#1747)
    releases,
    releaseKatalog,
    craReady,
    aktuelleVersion,
    releasesInPruefung,
    fetchReleases,
    fetchReleaseKatalog,
    fetchReleaseDetail,
    releaseAnlegen,
    setReleaseChecklistItem,
    setReleaseArt, setWesentlicheAenderung,
    releaseEinreichen,
    releaseZurueckweisen,
    releaseVeroeffentlichen,
    releaseFreigeben,
    fetchCraReady,
    craReadyFeststellen,
    craReadyEntziehen,
  }
})
