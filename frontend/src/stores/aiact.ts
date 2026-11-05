import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'
import { fehlerText, type FehlerFall } from '../utils/fehler'

export interface AIActProjekt {
  id: string
  name: string
  organisation: string
  company: string
  produkt: string
  beschreibung: string
  description: string
  meta?: string
  /** #1541: 'organisation' (Firmen-Projekt) oder 'system' (KI-System je Produkt) */
  scope?: 'organisation' | 'system'
  created_at?: string
  updated_at?: string
}

/** #1541: Organisation + KI-Systeme einer Firma (GET /projekte/<p>/scope) */
export interface AIActScope {
  projekt: string
  scope: 'organisation' | 'system'
  /** #1562: Organisation mit KI-Systemen — keine System-Controls */
  locked: boolean
  org_has_data: boolean
  firma: string
  org_projekt: string
  systeme: Array<{ name: string; produkt: string }>
  firmen_produkte: Array<{ name: string; beschreibung: string; angelegt: boolean }>
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
      error.value = fehlerText(err, 'laden')
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
      error.value = fehlerText(err, 'anlegen')
      return null
    }
  }

  // #1541: hybrides Modell — Scope laden + KI-System zur Firma anlegen
  const fetchScope = async (name: string): Promise<AIActScope | null> => {
    try {
      const res = await apiClient.get(`/aiact/projekte/${encodeURIComponent(name)}/scope`)
      return res.data
    } catch {
      return null
    }
  }

  const createSystem = async (orgProjekt: string, produkt: string, beschreibung = '', uebernehmen = false) => {
    error.value = null
    try {
      const res = await apiClient.post(
        `/aiact/projekte/${encodeURIComponent(orgProjekt)}/systeme`, { produkt, beschreibung, uebernehmen })
      await fetchProjekte()
      return res.data as AIActProjekt & { created: boolean }
    } catch (err: any) {
      error.value = fehlerText(err, 'anlegen')
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
      error.value = fehlerText(err, 'aktualisieren')
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
      error.value = fehlerText(err, 'loeschen')
      return false
    }
  }

  const fetchAnforderungen = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/aiact/projekte/${encodeURIComponent(projektName)}/anforderungen`)
      anforderungen.value = res.data
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
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
      error.value = fehlerText(err, 'speichern')
      return false
    }
  }

  const fetchReifegrad = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/aiact/projekte/${encodeURIComponent(projektName)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = fehlerText(err, 'bewerten')
    }
  }

  const fetchOwaspLlm = async () => {
    if (owaspLlm.value) return owaspLlm.value
    try {
      const res = await apiClient.get('/aiact/owasp-llm')
      owaspLlm.value = res.data
      return res.data
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
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
      error.value = fehlerText(err, 'abgleichen')
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
    catch (e: any) { error.value = fehlerText(e, 'laden') }
  }
  const saveSystemDoku = async (data: any) => {
    try { await apiClient.post(_pjUrl('/system-doku'), data); await fetchSystemDoku(); await fetchPflichtDokuStatus(); return true }
    catch (e: any) { error.value = fehlerText(e, 'speichern'); return false }
  }

  const fetchDataGovernance = async () => {
    try { dataGovernance.value = (await apiClient.get(_pjUrl('/data-governance'))).data || {} }
    catch (e: any) { error.value = fehlerText(e, 'laden') }
  }
  const saveDataGovernance = async (data: any) => {
    try { await apiClient.post(_pjUrl('/data-governance'), data); await fetchDataGovernance(); await fetchPflichtDokuStatus(); return true }
    catch (e: any) { error.value = fehlerText(e, 'speichern'); return false }
  }

  const fetchHumanOversight = async () => {
    try { humanOversight.value = (await apiClient.get(_pjUrl('/human-oversight'))).data || {} }
    catch (e: any) { error.value = fehlerText(e, 'laden') }
  }
  const saveHumanOversight = async (data: any) => {
    try { await apiClient.post(_pjUrl('/human-oversight'), data); await fetchHumanOversight(); await fetchPflichtDokuStatus(); return true }
    catch (e: any) { error.value = fehlerText(e, 'speichern'); return false }
  }

  const fetchPmm = async () => {
    try { pmm.value = (await apiClient.get(_pjUrl('/pmm'))).data || {} }
    catch (e: any) { error.value = fehlerText(e, 'laden') }
  }
  const savePmm = async (data: any) => {
    try { await apiClient.post(_pjUrl('/pmm'), data); await fetchPmm(); await fetchPflichtDokuStatus(); return true }
    catch (e: any) { error.value = fehlerText(e, 'speichern'); return false }
  }

  const fetchPflichtDokuStatus = async () => {
    try { pflichtDokuStatus.value = (await apiClient.get(_pjUrl('/pflicht-doku'))).data }
    catch (e: any) { error.value = fehlerText(e, 'laden') }
  }

  // Phase B Wizards
  const fetchUseCaseTemplates = async () => {
    try { useCaseTemplates.value = (await apiClient.get('/aiact/wizards/use-case-templates')).data || [] }
    catch (e: any) { error.value = fehlerText(e, 'laden') }
  }
  const applyUseCaseTemplate = async (ucId: string) => {
    try { await apiClient.post(_pjUrl('/wizards/use-case-template/apply'), { use_case_id: ucId }); return true }
    catch (e: any) { error.value = fehlerText(e, 'uebernehmen'); return false }
  }
  const getWizardPrompt = async (wizard: 'risk-tier' | 'eu-doc' | 'transparency' | 'llm-card' | 'high-risk-doc' | 'prompt-injection-tests' | 'hitl-workflow' | 'eu-db-registration' | 'chat' | 'eu-office-report' | 'betriebsanleitung' | 'fria-doc') => {
    try { return (await apiClient.get(_pjUrl(`/wizards/${wizard}/prompt`))).data?.prompt || '' }
    catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return '' }
  }
  // #1242/#1244: Dokument-Prompts auf eigenen Blueprints (literacy/gpai). Liefern
  // nur einen Copy/Paste-Prompt; das Ergebnis wird via „Als Dokument speichern".
  const _projOnly = () => {
    if (!selectedProjekt.value) throw new Error('Kein AI-Act-Projekt gewählt')
    return encodeURIComponent(selectedProjekt.value)
  }
  const getLiteracyWizardPrompt = async () => {
    try { return (await apiClient.get(`/aiact-literacy/projekte/${_projOnly()}/wizard/prompt`)).data?.prompt || '' }
    catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return '' }
  }
  const parseLiteracyWizard = async (response: string, apply = true) => {
    try { return (await apiClient.post(`/aiact-literacy/projekte/${_projOnly()}/wizard/parse`, { response, apply })).data }
    catch (e: any) { error.value = fehlerText(e, 'auswerten'); return null }
  }
  const getGpaiDocPrompt = async (kind: 'copyright-policy' | 'training-summary') => {
    try { return (await apiClient.get(`/aiact-gpai/projekte/${_projOnly()}/wizard/${kind}/prompt`)).data?.prompt || '' }
    catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return '' }
  }
  const parseWizardResponse = async (wizard: 'risk-tier' | 'eu-doc' | 'transparency' | 'llm-card' | 'high-risk-doc' | 'prompt-injection-tests' | 'hitl-workflow' | 'eu-db-registration' | 'chat' | 'eu-office-report' | 'betriebsanleitung' | 'fria-doc', response: string, apply = true) => {
    try {
      const body: any = { response }
      if (!apply) body.dry_run = true
      const res = await apiClient.post(_pjUrl(`/wizards/${wizard}/parse`), body)
      return res.data
    } catch (e: any) { error.value = fehlerText(e, 'auswerten'); return null }
  }

  // Phase E (#546-#550)
  const getChatPrompt = async (frage: string) => {
    try { return (await apiClient.post(_pjUrl('/wizards/chat/prompt'), { frage })).data?.prompt || '' }
    catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return '' }
  }
  const getEuOfficeReportPrompt = async (incident: any) => {
    try { return (await apiClient.post(_pjUrl('/wizards/eu-office-report/prompt'), { incident })).data?.prompt || '' }
    catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return '' }
  }
  const importModelCard = async (text: string, format: string, apply = true) => {
    try {
      const body: any = { text, format }
      if (!apply) body.dry_run = true
      return (await apiClient.post(_pjUrl('/wizards/model-card-import'), body)).data
    } catch (e: any) { error.value = fehlerText(e, 'uebernehmen'); return null }
  }
  const fetchOwaspLlmWatch = async () => {
    try { return (await apiClient.get(_pjUrl('/owasp-llm-watch'))).data }
    catch (e: any) { error.value = fehlerText(e, 'laden'); return null }
  }

  // ──────────────────────────────────────────────────────────────────
  // Sprint #18 — Auto-Fill (A1/A2) + Wizards (A3/A4/A5)
  // ──────────────────────────────────────────────────────────────────

  const suggestSystemDoku = async (source: 'repo' | 'url', url?: string) => {
    try {
      const body: any = { source }
      if (url) body.url = url
      return (await apiClient.post(_pjUrl('/system-doku/suggest'), body)).data
    } catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return null }
  }
  const applySystemDoku = async (fields: Record<string, any>) => {
    try { await apiClient.post(_pjUrl('/system-doku/apply'), { fields }); return true }
    catch (e: any) { error.value = fehlerText(e, 'uebernehmen'); return false }
  }

  const suggestDataGovernance = async (source: 'repo' | 'url', url?: string) => {
    try {
      const body: any = { source }
      if (url) body.url = url
      return (await apiClient.post(_pjUrl('/data-governance/suggest'), body)).data
    } catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return null }
  }
  const applyDataGovernance = async (fields: Record<string, any>) => {
    try { await apiClient.post(_pjUrl('/data-governance/apply'), { fields }); return true }
    catch (e: any) { error.value = fehlerText(e, 'uebernehmen'); return false }
  }

  const hoWizardPrompt = async () => {
    try { return (await apiClient.post(_pjUrl('/human-oversight/wizard-prompt'), {})).data?.prompt || '' }
    catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return '' }
  }
  const hoWizardApply = async (response: string) => {
    try { return (await apiClient.post(_pjUrl('/human-oversight/wizard-apply'), { response })).data }
    catch (e: any) { error.value = fehlerText(e, 'uebernehmen'); return null }
  }

  const fetchPmmHelp = async () => {
    try { return (await apiClient.get('/aiact/pmm/help')).data }
    catch (e: any) { error.value = fehlerText(e, 'laden'); return null }
  }
  const pmmWizardPrompt = async () => {
    try { return (await apiClient.post(_pjUrl('/pmm/wizard-prompt'), {})).data?.prompt || '' }
    catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return '' }
  }
  const pmmWizardApply = async (response: string) => {
    try { return (await apiClient.post(_pjUrl('/pmm/wizard-apply'), { response })).data }
    catch (e: any) { error.value = fehlerText(e, 'uebernehmen'); return null }
  }

  // A3 via Risikobewertung-Verknüpfung (#1044)
  const fetchRiskLink = async () => {
    try { return (await apiClient.get(_pjUrl('/risk-link'))).data }
    catch (e: any) { error.value = fehlerText(e, 'laden'); return { linked_risk_projekt: null } }
  }
  const fetchRiskLinkCandidates = async () => {
    try { return (await apiClient.get(_pjUrl('/risk-link/candidates'))).data?.candidates || [] }
    catch (e: any) { error.value = fehlerText(e, 'laden'); return [] }
  }
  const setRiskLink = async (riskProjekt: string) => {
    try { return (await apiClient.put(_pjUrl('/risk-link'), { risk_projekt: riskProjekt })).data }
    catch (e: any) { error.value = fehlerText(e, 'verknuepfen'); return null }
  }
  const deleteRiskLink = async () => {
    try { await apiClient.delete(_pjUrl('/risk-link')); return true }
    catch (e: any) { error.value = fehlerText(e, 'entfernen'); return false }
  }
  const fetchLinkedRisks = async () => {
    try { return (await apiClient.get(_pjUrl('/linked-risks'))).data }
    catch (e: any) { error.value = fehlerText(e, 'laden'); return { linked: false, risiken: [] } }
  }
  const fetchPreMarketCheck = async () => {
    try { return (await apiClient.get(_pjUrl('/pre-market-check'))).data }
    catch (e: any) { error.value = fehlerText(e, 'laden'); return null }
  }

  // ── OWASP-LLM-Register (#1087, Sprint #21 S17) ──────────────────────────
  const owaspLlmItems = ref<any[]>([])
  const fetchOwaspLlmRegister = async () => {
    try {
      owaspLlmItems.value = (await apiClient.get(_pjUrl('/owasp-llm'))).data?.items || []
      return owaspLlmItems.value
    } catch (e: any) { error.value = fehlerText(e, 'laden'); return [] }
  }
  const saveOwaspLlmStatus = async (llmId: string, status: number, kommentar = '') => {
    try {
      await apiClient.post(_pjUrl(`/owasp-llm/${encodeURIComponent(llmId)}`), { status, kommentar })
      await fetchOwaspLlmRegister()
      return true
    } catch (e: any) { error.value = fehlerText(e, 'speichern'); return false }
  }
  const autodetectOwaspLlm = async (repo?: string, branch?: string) => {
    try {
      const res = await apiClient.post(_pjUrl('/owasp-llm/autodetect'),
        { repo, branch, apply: true })
      await fetchOwaspLlmRegister()
      return res.data
    } catch (e: any) { error.value = fehlerText(e, 'auswerten'); return null }
  }
  const owaspLlmWizardPrompt = async () => {
    try { return (await apiClient.get(_pjUrl('/owasp-llm/wizard/prompt'))).data?.prompt || '' }
    catch (e: any) { error.value = fehlerText(e, 'erzeugen'); return '' }
  }
  const owaspLlmWizardParse = async (response: string, apply = true) => {
    try {
      const res = await apiClient.post(_pjUrl('/owasp-llm/wizard/parse'), { response, apply })
      if (apply) await fetchOwaspLlmRegister()
      return res.data
    } catch (e: any) { error.value = fehlerText(e, 'uebernehmen'); return null }
  }
  const createOwaspLlmIssue = async (llmId: string, repo?: string) => {
    try {
      const res = await apiClient.post(
        _pjUrl(`/owasp-llm/${encodeURIComponent(llmId)}/issues`), { repo })
      await fetchOwaspLlmRegister()
      return res.data
    } catch (e: any) { error.value = fehlerText(e, 'anlegen'); return null }
  }
  const syncOwaspLlmIssues = async (llmId: string) => {
    try {
      const res = await apiClient.post(
        _pjUrl(`/owasp-llm/${encodeURIComponent(llmId)}/issues/sync`), {})
      await fetchOwaspLlmRegister()
      return res.data
    } catch (e: any) { error.value = fehlerText(e, 'abgleichen'); return null }
  }
  const unlinkOwaspLlmIssue = async (linkId: string) => {
    try {
      await apiClient.delete(_pjUrl(`/owasp-llm/issues/${encodeURIComponent(linkId)}`))
      await fetchOwaspLlmRegister()
      return true
    } catch (e: any) { error.value = fehlerText(e, 'entfernen'); return false }
  }

  // ── Änderungsverwaltung je KI-System (Art. 43 Abs. 4, #1756) ────────────
  // Eigener Blueprint (/api/aiact-aenderungen), deshalb eine eigene URL-Hilfe:
  // der Bindestrich-Prefix ist es, über den Authz und Lizenz-Gate das Modul
  // ``aiact`` erkennen (#1169).
  const aenderungen = ref<any[]>([])
  const aenderungKatalog = ref<any[]>([])
  const aenderungConstants = ref<any | null>(null)

  const _aendUrl = (suffix = '') => {
    if (!selectedProjekt.value) throw new Error('Kein AI-Act-Projekt gewählt')
    return `/aiact-aenderungen/projekte/${encodeURIComponent(selectedProjekt.value)}`
      + `/aenderungen${suffix}`
  }
  const _stand = (stand: string) => `/${encodeURIComponent(stand)}`
  const _aendFehler = (e: any, fall: FehlerFall) => {
    error.value = fehlerText(e, fall)
    return null
  }

  const fetchAenderungConstants = async () => {
    if (aenderungConstants.value) return aenderungConstants.value
    try {
      aenderungConstants.value = (await apiClient.get('/aiact-aenderungen/constants')).data
      return aenderungConstants.value
    } catch { return null }
  }
  const fetchAenderungen = async () => {
    try {
      const d = (await apiClient.get(_aendUrl())).data || {}
      aenderungen.value = d.aenderungen || []
      return d
    } catch (e: any) { aenderungen.value = []; return _aendFehler(e, 'laden') }
  }
  const fetchAenderungKatalog = async (wesentlich = '', grundArt = '') => {
    try {
      const d = (await apiClient.get(_aendUrl('/katalog'),
        { params: { wesentlich, grund_art: grundArt } })).data || {}
      aenderungKatalog.value = d.katalog || []
      return d
    } catch (e: any) { return _aendFehler(e, 'laden') }
  }
  /** Detail inkl. live gerechnetem Gate. Legt nichts an (#1747-Lehre). */
  const fetchAenderung = async (stand: string) => {
    try { return (await apiClient.get(_aendUrl(_stand(stand)))).data }
    catch (e: any) { return _aendFehler(e, 'laden') }
  }
  const createAenderung = async (data: Record<string, any>) => {
    try { return (await apiClient.post(_aendUrl(), data)).data }
    catch (e: any) { return _aendFehler(e, 'anlegen') }
  }
  const saveAenderungStammdaten = async (stand: string, data: Record<string, any>) => {
    try { return (await apiClient.put(_aendUrl(_stand(stand)), data)).data }
    catch (e: any) { return _aendFehler(e, 'speichern') }
  }
  const deleteAenderung = async (stand: string) => {
    try { await apiClient.delete(_aendUrl(_stand(stand))); return true }
    catch (e: any) { _aendFehler(e, 'aktualisieren'); return false }
  }
  /** Die Kernfrage: 'ja' | 'nein' | 'vorab_bewertet' (Art. 43 Abs. 4). */
  const setAenderungWesentlich = async (
    stand: string, wert: string, grund: string, vorabReferenz = '') => {
    try {
      return (await apiClient.put(_aendUrl(_stand(stand) + '/wesentliche-aenderung'),
        { wert, grund, vorab_referenz: vorabReferenz })).data
    } catch (e: any) { return _aendFehler(e, 'speichern') }
  }
  const setAenderungCheckliste = async (
    stand: string, itemId: string, status: string, begruendung: string) => {
    try {
      return (await apiClient.put(
        _aendUrl(_stand(stand) + `/checkliste/${encodeURIComponent(itemId)}`),
        { status, begruendung })).data
    } catch (e: any) { return _aendFehler(e, 'aktualisieren') }
  }
  const aenderungSchritt = async (
    stand: string, schritt: 'einreichen' | 'zurueckweisen' | 'freigeben' | 'umsetzen',
    body: Record<string, any> = {}) => {
    try { return (await apiClient.post(_aendUrl(_stand(stand) + '/' + schritt), body)).data }
    catch (e: any) { return _aendFehler(e, 'aktualisieren') }
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
    fetchScope,
    createSystem,
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
    // Sprint #28 — Dokument-Assistenten (#1242/#1244)
    getLiteracyWizardPrompt, parseLiteracyWizard, getGpaiDocPrompt,
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
    // #1756 — Änderungsverwaltung je KI-System (Art. 43 Abs. 4)
    aenderungen, aenderungKatalog, aenderungConstants,
    fetchAenderungConstants, fetchAenderungen, fetchAenderungKatalog,
    fetchAenderung, createAenderung, saveAenderungStammdaten, deleteAenderung,
    setAenderungWesentlich, setAenderungCheckliste, aenderungSchritt,
  }
})
