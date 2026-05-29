import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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
  const saveSupportPeriod = async (data: any) => {
    try {
      const res = await apiClient.post(_pjUrl('/support-period'), data)
      supportPeriod.value = res.data?.data || {}
      return true
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
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
  const getWizardPrompt = async (wizard: 'klassifikator' | 'vuln-policy' | 'update-policy') => {
    try { return (await apiClient.get(_pjUrl(`/wizards/${wizard}/prompt`))).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const parseWizardResponse = async (wizard: 'klassifikator' | 'vuln-policy' | 'update-policy', response: string, apply = true) => {
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

  return {
    projekte,
    selectedProjekt,
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
    threatModel,
    pflichtDokuStatus,
    fetchSboms,
    saveSbom,
    deleteSbom,
    fetchPsirt,
    savePsirt,
    fetchVulns,
    saveVuln,
    deleteVuln,
    fetchSupportPeriod,
    saveSupportPeriod,
    fetchThreatModel,
    saveThreatModel,
    fetchPflichtDokuStatus,
    autodetectPflichtDoku,
    // Phase B
    branchenTemplates,
    fetchBranchenTemplates,
    applyBranchenTemplate,
    getWizardPrompt,
    parseWizardResponse,
  }
})
