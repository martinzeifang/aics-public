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
  const aiactRisks = ref<any[]>([])
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
    try { await apiClient.post(_pjUrl('/system-doku'), data); await fetchSystemDoku(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchDataGovernance = async () => {
    try { dataGovernance.value = (await apiClient.get(_pjUrl('/data-governance'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveDataGovernance = async (data: any) => {
    try { await apiClient.post(_pjUrl('/data-governance'), data); await fetchDataGovernance(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchAiactRisks = async () => {
    try { aiactRisks.value = (await apiClient.get(_pjUrl('/risks'))).data || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveAiactRisk = async (data: any) => {
    try { await apiClient.post(_pjUrl('/risks'), data); await fetchAiactRisks(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  const deleteAiactRisk = async (id: number) => {
    try { await apiClient.delete(_pjUrl(`/risks/${id}`)); await fetchAiactRisks(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchHumanOversight = async () => {
    try { humanOversight.value = (await apiClient.get(_pjUrl('/human-oversight'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveHumanOversight = async (data: any) => {
    try { await apiClient.post(_pjUrl('/human-oversight'), data); await fetchHumanOversight(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchPmm = async () => {
    try { pmm.value = (await apiClient.get(_pjUrl('/pmm'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const savePmm = async (data: any) => {
    try { await apiClient.post(_pjUrl('/pmm'), data); await fetchPmm(); return true }
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
  const getWizardPrompt = async (wizard: 'risk-tier' | 'eu-doc' | 'transparency') => {
    try { return (await apiClient.get(_pjUrl(`/wizards/${wizard}/prompt`))).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const parseWizardResponse = async (wizard: 'risk-tier' | 'eu-doc' | 'transparency', response: string, apply = true) => {
    try {
      const body: any = { response }
      if (!apply) body.dry_run = true
      const res = await apiClient.post(_pjUrl(`/wizards/${wizard}/parse`), body)
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
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
    systemDoku, dataGovernance, aiactRisks, humanOversight, pmm, pflichtDokuStatus,
    fetchSystemDoku, saveSystemDoku,
    fetchDataGovernance, saveDataGovernance,
    fetchAiactRisks, saveAiactRisk, deleteAiactRisk,
    fetchHumanOversight, saveHumanOversight,
    fetchPmm, savePmm,
    fetchPflichtDokuStatus,
    // Phase B
    useCaseTemplates,
    fetchUseCaseTemplates, applyUseCaseTemplate,
    getWizardPrompt, parseWizardResponse,
  }
})
