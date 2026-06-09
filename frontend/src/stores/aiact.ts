import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface AIActProjekt {
  id: string
  name: string
  organisation: string
  company: string
  produkt: string
  beschreibung: string
  description: string
  meta?: string
  created_at?: string
  updated_at?: string
}

export interface AIActAnforderung {
  id: string
  kapitel: string
  titel: string
  title?: string
  beschreibung: string
  description?: string
  hinweise: string
  guidance: string
  evidence: string[]
  rubric: any
  ref: string
  gewichtung: number
  owasp_llm: Array<{ id: string; title: string; ref: string }>
  bewertung: number
  score?: number
  kommentar: string
  notes?: string
  massnahme: string
  verantwortlich: string
  zieldatum: string
  status: 'pending' | 'partial' | 'complete'
}

export const useAiActStore = defineStore('aiact', () => {
  const projekte = ref<AIActProjekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const anforderungen = ref<AIActAnforderung[]>([])
  const reifegrad = ref<any>(null)
  const owaspLlm = ref<any | null>(null)
  const repoSuggestions = ref<any[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/aiact/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<AIActProjekt>) => {
    try {
      const res = await apiClient.post('/aiact/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<AIActProjekt>) => {
    try {
      const res = await apiClient.put(`/aiact/projekte/${encodeURIComponent(name)}`, data)
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
      await apiClient.delete(`/aiact/projekte/${encodeURIComponent(name)}`)
      projekte.value = projekte.value.filter(p => p.name !== name)
      if (selectedProjekt.value === name) selectedProjekt.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  const fetchAnforderungen = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/aiact/projekte/${encodeURIComponent(projektName)}/anforderungen`)
      anforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    }
  }

  const saveBewertung = async (projektName: string, anforderungId: string, payload: any) => {
    try {
      await apiClient.post(`/aiact/projekte/${encodeURIComponent(projektName)}/bewertungen`, {
        anforderung_id: anforderungId,
        bewertung: payload.bewertung ?? payload.score ?? 0,
        kommentar: payload.kommentar ?? '',
        massnahme: payload.massnahme ?? '',
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

  const fetchReifegrad = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/aiact/projekte/${encodeURIComponent(projektName)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Reifegrad'
    }
  }

  const fetchOwaspLlm = async () => {
    if (owaspLlm.value) return owaspLlm.value
    try {
      const res = await apiClient.get('/aiact/owasp-llm')
      owaspLlm.value = res.data
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return null
    }
  }

  const repoScan = async (projektName: string, repo: string, branch: string = '') => {
    try {
      const res = await apiClient.post(
        `/aiact/projekte/${encodeURIComponent(projektName)}/repo-scan`,
        { repo, branch },
      )
      repoSuggestions.value = res.data.suggestions || []
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Repo-Scan'
      return null
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Sprint γ Phase A — Pflicht-Doku-Manager (#583)
  // ──────────────────────────────────────────────────────────────────

  const systemDoku = ref<any>({})
  const dataGovernance = ref<any>({})
  const humanOversight = ref<any>({})
  const pmm = ref<any>({})
  const pflichtDokuStatus = ref<any | null>(null)
  const useCaseTemplates = ref<any[]>([])

  const _pjUrl = (suffix: string) => {
    if (!selectedProjekt.value) throw new Error('Kein AI-Act-Projekt gewählt')
    return `/aiact/projekte/${encodeURIComponent(selectedProjekt.value)}${suffix}`
  }

  const fetchSystemDoku = async () => {
    try { systemDoku.value = (await apiClient.get(_pjUrl('/system-doku'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveSystemDoku = async (data: any) => {
    try { await apiClient.post(_pjUrl('/system-doku'), data); await fetchSystemDoku(); await fetchPflichtDokuStatus(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchDataGovernance = async () => {
    try { dataGovernance.value = (await apiClient.get(_pjUrl('/data-governance'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveDataGovernance = async (data: any) => {
    try { await apiClient.post(_pjUrl('/data-governance'), data); await fetchDataGovernance(); await fetchPflichtDokuStatus(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchHumanOversight = async () => {
    try { humanOversight.value = (await apiClient.get(_pjUrl('/human-oversight'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveHumanOversight = async (data: any) => {
    try { await apiClient.post(_pjUrl('/human-oversight'), data); await fetchHumanOversight(); await fetchPflichtDokuStatus(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchPmm = async () => {
    try { pmm.value = (await apiClient.get(_pjUrl('/pmm'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const savePmm = async (data: any) => {
    try { await apiClient.post(_pjUrl('/pmm'), data); await fetchPmm(); await fetchPflichtDokuStatus(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchPflichtDokuStatus = async () => {
    try { pflichtDokuStatus.value = (await apiClient.get(_pjUrl('/pflicht-doku'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }

  // Phase B Wizards
  const fetchUseCaseTemplates = async () => {
    try { useCaseTemplates.value = (await apiClient.get('/aiact/wizards/use-case-templates')).data || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const applyUseCaseTemplate = async (ucId: string) => {
    try { await apiClient.post(_pjUrl('/wizards/use-case-template/apply'), { use_case_id: ucId }); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  const getWizardPrompt = async (wizard: 'risk-tier' | 'eu-doc' | 'transparency' | 'llm-card' | 'high-risk-doc' | 'prompt-injection-tests' | 'hitl-workflow' | 'eu-db-registration' | 'chat' | 'eu-office-report') => {
    try { return (await apiClient.get(_pjUrl(`/wizards/${wizard}/prompt`))).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const parseWizardResponse = async (wizard: 'risk-tier' | 'eu-doc' | 'transparency' | 'llm-card' | 'high-risk-doc' | 'prompt-injection-tests' | 'hitl-workflow' | 'eu-db-registration' | 'chat' | 'eu-office-report', response: string, apply = true) => {
    try {
      const body: any = { response }
      if (!apply) body.dry_run = true
      const res = await apiClient.post(_pjUrl(`/wizards/${wizard}/parse`), body)
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }

  // Phase E (#546-#550)
  const getChatPrompt = async (frage: string) => {
    try { return (await apiClient.post(_pjUrl('/wizards/chat/prompt'), { frage })).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const getEuOfficeReportPrompt = async (incident: any) => {
    try { return (await apiClient.post(_pjUrl('/wizards/eu-office-report/prompt'), { incident })).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const importModelCard = async (text: string, format: string, apply = true) => {
    try {
      const body: any = { text, format }
      if (!apply) body.dry_run = true
      return (await apiClient.post(_pjUrl('/wizards/model-card-import'), body)).data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }
  const fetchOwaspLlmWatch = async () => {
    try { return (await apiClient.get(_pjUrl('/owasp-llm-watch'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }

  // ──────────────────────────────────────────────────────────────────
  // Sprint #18 — Auto-Fill (A1/A2) + Wizards (A3/A4/A5)
  // ──────────────────────────────────────────────────────────────────

  const suggestSystemDoku = async (source: 'repo' | 'url', url?: string) => {
    try {
      const body: any = { source }
      if (url) body.url = url
      return (await apiClient.post(_pjUrl('/system-doku/suggest'), body)).data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Vorschlagen'; return null }
  }
  const applySystemDoku = async (fields: Record<string, any>) => {
    try { await apiClient.post(_pjUrl('/system-doku/apply'), { fields }); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Übernehmen'; return false }
  }

  const suggestDataGovernance = async (source: 'repo' | 'url', url?: string) => {
    try {
      const body: any = { source }
      if (url) body.url = url
      return (await apiClient.post(_pjUrl('/data-governance/suggest'), body)).data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Vorschlagen'; return null }
  }
  const applyDataGovernance = async (fields: Record<string, any>) => {
    try { await apiClient.post(_pjUrl('/data-governance/apply'), { fields }); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Übernehmen'; return false }
  }

  const hoWizardPrompt = async () => {
    try { return (await apiClient.post(_pjUrl('/human-oversight/wizard-prompt'), {})).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const hoWizardApply = async (response: string) => {
    try { return (await apiClient.post(_pjUrl('/human-oversight/wizard-apply'), { response })).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Übernehmen'; return null }
  }

  const fetchPmmHelp = async () => {
    try { return (await apiClient.get('/aiact/pmm/help')).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }
  const pmmWizardPrompt = async () => {
    try { return (await apiClient.post(_pjUrl('/pmm/wizard-prompt'), {})).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const pmmWizardApply = async (response: string) => {
    try { return (await apiClient.post(_pjUrl('/pmm/wizard-apply'), { response })).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Übernehmen'; return null }
  }

  // A3 via Risikobewertung-Verknüpfung (#1044)
  const fetchRiskLink = async () => {
    try { return (await apiClient.get(_pjUrl('/risk-link'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return { linked_risk_projekt: null } }
  }
  const fetchRiskLinkCandidates = async () => {
    try { return (await apiClient.get(_pjUrl('/risk-link/candidates'))).data?.candidates || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return [] }
  }
  const setRiskLink = async (riskProjekt: string) => {
    try { return (await apiClient.put(_pjUrl('/risk-link'), { risk_projekt: riskProjekt })).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Verknüpfen'; return null }
  }
  const deleteRiskLink = async () => {
    try { await apiClient.delete(_pjUrl('/risk-link')); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Lösen'; return false }
  }
  const fetchLinkedRisks = async () => {
    try { return (await apiClient.get(_pjUrl('/linked-risks'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return { linked: false, risiken: [] } }
  }
  const fetchPreMarketCheck = async () => {
    try { return (await apiClient.get(_pjUrl('/pre-market-check'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }

  // ── OWASP-LLM-Register (#1087, Sprint #21 S17) ──────────────────────────
  const owaspLlmItems = ref<any[]>([])
  const fetchOwaspLlmRegister = async () => {
    try {
      owaspLlmItems.value = (await apiClient.get(_pjUrl('/owasp-llm'))).data?.items || []
      return owaspLlmItems.value
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return [] }
  }
  const saveOwaspLlmStatus = async (llmId: string, status: number, kommentar = '') => {
    try {
      await apiClient.post(_pjUrl(`/owasp-llm/${encodeURIComponent(llmId)}`), { status, kommentar })
      await fetchOwaspLlmRegister()
      return true
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Speichern'; return false }
  }
  const autodetectOwaspLlm = async (repo?: string, branch?: string) => {
    try {
      const res = await apiClient.post(_pjUrl('/owasp-llm/autodetect'),
        { repo, branch, apply: true })
      await fetchOwaspLlmRegister()
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Auto-Detect fehlgeschlagen'; return null }
  }
  const owaspLlmWizardPrompt = async () => {
    try { return (await apiClient.get(_pjUrl('/owasp-llm/wizard/prompt'))).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const owaspLlmWizardParse = async (response: string, apply = true) => {
    try {
      const res = await apiClient.post(_pjUrl('/owasp-llm/wizard/parse'), { response, apply })
      if (apply) await fetchOwaspLlmRegister()
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Übernehmen'; return null }
  }
  const createOwaspLlmIssue = async (llmId: string, repo?: string) => {
    try {
      const res = await apiClient.post(
        _pjUrl(`/owasp-llm/${encodeURIComponent(llmId)}/issues`), { repo })
      await fetchOwaspLlmRegister()
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Issue-Anlage fehlgeschlagen'; return null }
  }
  const syncOwaspLlmIssues = async (llmId: string) => {
    try {
      const res = await apiClient.post(
        _pjUrl(`/owasp-llm/${encodeURIComponent(llmId)}/issues/sync`), {})
      await fetchOwaspLlmRegister()
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Sync fehlgeschlagen'; return null }
  }
  const unlinkOwaspLlmIssue = async (linkId: string) => {
    try {
      await apiClient.delete(_pjUrl(`/owasp-llm/issues/${encodeURIComponent(linkId)}`))
      await fetchOwaspLlmRegister()
      return true
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Entfernen'; return false }
  }

  return {
    projekte,
    selectedProjekt,
    selectedProjektObj,
    anforderungen,
    reifegrad,
    owaspLlm,
    repoSuggestions,
    loading,
    error,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchAnforderungen,
    saveBewertung,
    fetchReifegrad,
    fetchOwaspLlm,
    repoScan,
    // Phase A
    systemDoku, dataGovernance, humanOversight, pmm, pflichtDokuStatus,
    fetchSystemDoku, saveSystemDoku,
    fetchDataGovernance, saveDataGovernance,
    fetchHumanOversight, saveHumanOversight,
    fetchPmm, savePmm,
    fetchPflichtDokuStatus,
    // Phase B
    useCaseTemplates,
    fetchUseCaseTemplates, applyUseCaseTemplate,
    getWizardPrompt, parseWizardResponse,
    // Phase E
    getChatPrompt, getEuOfficeReportPrompt,
    importModelCard, fetchOwaspLlmWatch, fetchPreMarketCheck,
    // Sprint #18 — Auto-Fill + Wizards
    suggestSystemDoku, applySystemDoku,
    suggestDataGovernance, applyDataGovernance,
    hoWizardPrompt, hoWizardApply,
    fetchPmmHelp, pmmWizardPrompt, pmmWizardApply,
    fetchRiskLink, fetchRiskLinkCandidates, setRiskLink, deleteRiskLink, fetchLinkedRisks,
    // Sprint #21 S17 — OWASP-LLM-Register (#1087)
    owaspLlmItems,
    fetchOwaspLlmRegister, saveOwaspLlmStatus, autodetectOwaspLlm,
    owaspLlmWizardPrompt, owaspLlmWizardParse,
    createOwaspLlmIssue, syncOwaspLlmIssues, unlinkOwaspLlmIssue,
  }
})
