import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// ──────────────────────────────────────────────────────────────────────────
// SOC — Security Operations Center (Wazuh-Alarm-Triage & Incidents)
// Alle Endpoints unter /api/soc (apiClient.baseURL == '/api'). Sprint #29 / #1254.
// ──────────────────────────────────────────────────────────────────────────

export interface SocConnection {
  id?: number
  name: string
  modus: 'pull' | 'push'
  url: string
  username: string
  verify_tls: boolean
  index_pattern: string
  min_level: number
  enabled: boolean
  has_secret?: boolean
  has_push_token?: boolean
}

export const useSocStore = defineStore('soc', () => {
  const loading = ref(false)
  const error = ref<string | null>(null)

  const constants = ref<any>({})
  const kpis = ref<any>({})
  const slaKpis = ref<any>({})
  const connections = ref<SocConnection[]>([])
  const alerts = ref<any[]>([])
  const groups = ref<any[]>([])
  const incidents = ref<any[]>([])
  const currentIncident = ref<any | null>(null)
  const assets = ref<any[]>([])
  const suppressions = ref<any[]>([])

  function _err(e: any, fallback: string): never {
    const msg = e?.response?.data?.error || e?.message || fallback
    error.value = msg
    throw e
  }

  // ── Stammdaten ───────────────────────────────────────────────────────────
  async function fetchConstants() {
    try { constants.value = (await apiClient.get('/soc/constants')).data }
    catch (e) { _err(e, 'Konstanten konnten nicht geladen werden') }
  }
  async function fetchKpis() {
    try { kpis.value = (await apiClient.get('/soc/kpis')).data }
    catch (e) { _err(e, 'KPIs konnten nicht geladen werden') }
  }
  const controlEvidence = ref<any>({})
  async function fetchControlEvidence() {
    try { controlEvidence.value = (await apiClient.get('/soc/control-evidence')).data }
    catch (e) { _err(e, 'Nachweis konnte nicht geladen werden') }
  }
  async function fetchLikelihood(agent?: string) {
    try { return (await apiClient.get('/soc/likelihood', { params: agent ? { agent } : {} })).data }
    catch (e) { _err(e, 'Eintrittswahrscheinlichkeit konnte nicht ermittelt werden') }
  }
  async function lageberichtPrompt() {
    try { return (await apiClient.get('/soc/lagebericht/prompt')).data.prompt }
    catch (e) { _err(e, 'Lagebericht-Prompt fehlgeschlagen') }
  }
  async function runLagebericht(response?: string) {
    try { return (await apiClient.post('/soc/lagebericht', response ? { response } : {})).data.report }
    catch (e) { _err(e, 'Lagebericht fehlgeschlagen') }
  }
  async function fetchOwaspLlm() {
    try { return (await apiClient.get('/soc/owasp-llm')).data.detections || [] }
    catch (e) { _err(e, 'OWASP-LLM-Erkennung fehlgeschlagen') }
  }
  async function pushOwaspLlm(projekt: string) {
    try { return (await apiClient.post('/soc/owasp-llm/push', { projekt_name: projekt })).data }
    catch (e) { _err(e, 'Push ins AI-Act-Register fehlgeschlagen') }
  }

  // ── Verbindung / Einrichtung ─────────────────────────────────────────────
  async function fetchConnections() {
    try { connections.value = (await apiClient.get('/soc/connection')).data.connections || [] }
    catch (e) { _err(e, 'Verbindungen konnten nicht geladen werden') }
  }
  async function saveConnection(payload: any) {
    try { return (await apiClient.post('/soc/connection', payload)).data }
    catch (e) { _err(e, 'Verbindung konnte nicht gespeichert werden') }
  }
  async function deleteConnection(name: string) {
    try { await apiClient.delete(`/soc/connection/${encodeURIComponent(name)}`); await fetchConnections() }
    catch (e) { _err(e, 'Verbindung konnte nicht gelöscht werden') }
  }
  async function testConnection(payload: any) {
    try { return (await apiClient.post('/soc/connection/test', payload)).data }
    catch (e) { _err(e, 'Verbindungstest fehlgeschlagen') }
  }
  async function sync(name = 'default') {
    try { return (await apiClient.post('/soc/sync', { name })).data }
    catch (e) { _err(e, 'Sync fehlgeschlagen') }
  }
  async function fetchSnippet(token: string, level: number) {
    try { return (await apiClient.get('/soc/integration-snippet', { params: { token, level } })).data }
    catch (e) { _err(e, 'Snippet konnte nicht erzeugt werden') }
  }

  // ── Alarme ───────────────────────────────────────────────────────────────
  async function fetchAlerts(params: any = {}) {
    loading.value = true
    try { alerts.value = (await apiClient.get('/soc/alerts', { params })).data.alerts || [] }
    catch (e) { _err(e, 'Alarme konnten nicht geladen werden') }
    finally { loading.value = false }
  }
  async function fetchGroups(params: any = {}) {
    try { groups.value = (await apiClient.get('/soc/groups', { params })).data.groups || [] }
    catch (e) { _err(e, 'Gruppen konnten nicht geladen werden') }
  }
  async function triageAlert(uid: string, status: string) {
    try { return (await apiClient.post(`/soc/alerts/${encodeURIComponent(uid)}/triage`, { status })).data }
    catch (e) { _err(e, 'Triage fehlgeschlagen') }
  }
  async function alertPrompt(uid: string) {
    try { return (await apiClient.get(`/soc/alerts/${encodeURIComponent(uid)}/analyze/prompt`)).data.prompt }
    catch (e) { _err(e, 'Prompt konnte nicht erzeugt werden') }
  }
  async function analyzeAlert(uid: string, response?: string) {
    try { return (await apiClient.post(`/soc/alerts/${encodeURIComponent(uid)}/analyze`, response ? { response } : {})).data.analysis }
    catch (e) { _err(e, 'Analyse fehlgeschlagen') }
  }

  // ── Suppressions ─────────────────────────────────────────────────────────
  async function fetchSuppressions() {
    try { suppressions.value = (await apiClient.get('/soc/suppressions')).data.suppressions || [] }
    catch (e) { _err(e, 'Suppressions konnten nicht geladen werden') }
  }
  async function addSuppression(payload: any) {
    try { const r = (await apiClient.post('/soc/suppressions', payload)).data; await fetchSuppressions(); return r }
    catch (e) { _err(e, 'Suppression konnte nicht angelegt werden') }
  }
  async function deleteSuppression(id: number) {
    try { await apiClient.delete(`/soc/suppressions/${id}`); await fetchSuppressions() }
    catch (e) { _err(e, 'Suppression konnte nicht gelöscht werden') }
  }
  async function dryRunSuppression(payload: any) {
    try { return (await apiClient.post('/soc/suppressions/dry-run', payload)).data }
    catch (e) { _err(e, 'Dry-Run fehlgeschlagen') }
  }

  // ── Assets ───────────────────────────────────────────────────────────────
  async function fetchAssets() {
    try { assets.value = (await apiClient.get('/soc/assets')).data.assets || [] }
    catch (e) { _err(e, 'Assets konnten nicht geladen werden') }
  }
  async function saveAsset(payload: any) {
    try { const r = (await apiClient.post('/soc/assets', payload)).data; await fetchAssets(); return r }
    catch (e) { _err(e, 'Asset konnte nicht gespeichert werden') }
  }
  async function refreshAssets(payload: any) {
    try { const r = (await apiClient.post('/soc/assets/refresh', payload)).data; await fetchAssets(); return r }
    catch (e) { _err(e, 'Asset-Refresh fehlgeschlagen') }
  }
  // #1347 — agentlose Syslog-Quellen read-only erkennen / als Asset anlegen
  async function discoverSyslog(hours = 2) {
    try { return (await apiClient.get('/soc/assets/discover-syslog', { params: { hours } })).data }
    catch (e) { _err(e, 'Syslog-Discovery fehlgeschlagen'); return { ok: false, sources: [] } }
  }
  async function createAssetsFromSyslog(sources: any[]) {
    try { const r = (await apiClient.post('/soc/assets/from-syslog', { sources })).data; await fetchAssets(); return r }
    catch (e) { _err(e, 'Syslog-Quellen konnten nicht angelegt werden') }
  }
  const currentAsset = ref<any | null>(null)
  async function fetchAssetDetail(id: number) {
    try { currentAsset.value = (await apiClient.get(`/soc/assets/${id}/detail`)).data; return currentAsset.value }
    catch (e) { _err(e, 'Asset-Detail konnte nicht geladen werden') }
  }
  async function deleteAsset(id: number) {
    try { await apiClient.delete(`/soc/assets/${id}`); await fetchAssets() }
    catch (e) { _err(e, 'Asset konnte nicht gelöscht werden') }
  }
  async function assignAlert(uid: string, assetId: number | null) {
    try { await apiClient.post(`/soc/alerts/${encodeURIComponent(uid)}/assign`, { asset_id: assetId }) }
    catch (e) { _err(e, 'Alarm-Zuordnung fehlgeschlagen') }
  }
  async function assignIncident(id: number, assetId: number | null) {
    try { await apiClient.post(`/soc/incidents/${id}/assign`, { asset_id: assetId }); await getIncident(id) }
    catch (e) { _err(e, 'Incident-Zuordnung fehlgeschlagen') }
  }

  // ── Incidents + Meldepflicht-Router ──────────────────────────────────────
  async function fetchIncidents(params: any = {}) {
    try { incidents.value = (await apiClient.get('/soc/incidents', { params })).data.incidents || [] }
    catch (e) { _err(e, 'Incidents konnten nicht geladen werden') }
  }
  async function getIncident(id: number) {
    try { currentIncident.value = (await apiClient.get(`/soc/incidents/${id}`)).data; return currentIncident.value }
    catch (e) { _err(e, 'Incident konnte nicht geladen werden') }
  }
  // #1454: aktualisierte Incident-Felder in currentIncident mergen statt einen
  // zweiten (teuren) GET /incidents/<id> abzusetzen. Vorhandene Detail-Keys
  // (timeline, sla, escalation_path, pir …) bleiben erhalten, wenn das
  // Action-Endpoint sie nicht mitliefert.
  function _mergeCurrentIncident(id: number, inc: any) {
    if (!inc) return
    if (currentIncident.value && currentIncident.value.id === id) {
      currentIncident.value = { ...currentIncident.value, ...inc }
    } else {
      currentIncident.value = inc
    }
  }
  async function createIncident(payload: any) {
    try { const r = (await apiClient.post('/soc/incidents', payload)).data; await fetchIncidents(); return r }
    catch (e) { _err(e, 'Incident konnte nicht angelegt werden') }
  }
  async function updateIncident(id: number, payload: any) {
    try { const r = (await apiClient.put(`/soc/incidents/${id}`, payload)).data; _mergeCurrentIncident(id, r); return r }
    catch (e) { _err(e, 'Incident konnte nicht aktualisiert werden') }
  }
  async function setIncidentStatus(id: number, status: string) {
    try { const r = (await apiClient.post(`/soc/incidents/${id}/status`, { status })).data; _mergeCurrentIncident(id, r.incident || { status: r.status }); return r }
    catch (e) { _err(e, 'Statuswechsel fehlgeschlagen') }
  }
  async function addNote(id: number, detail: string) {
    try { await apiClient.post(`/soc/incidents/${id}/timeline`, { detail }); await getIncident(id) }
    catch (e) { _err(e, 'Notiz konnte nicht gespeichert werden') }
  }
  async function fetchIncidentIssues(id: number) {
    try { return (await apiClient.get(`/soc/incidents/${id}/issues`)).data.issues || [] }
    catch (e) { _err(e, 'Issues konnten nicht geladen werden') }
  }
  async function createIncidentIssue(id: number, payload: any) {
    try { return (await apiClient.post(`/soc/incidents/${id}/issues`, payload)).data }
    catch (e) { _err(e, 'Issue-Erstellung fehlgeschlagen') }
  }
  async function deleteIncidentIssue(id: number, linkId: string) {
    try { await apiClient.delete(`/soc/incidents/${id}/issues/${linkId}`) }
    catch (e) { _err(e, 'Issue-Verknüpfung konnte nicht gelöscht werden') }
  }
  const playbookCatalog = ref<any[]>([])
  async function fetchPlaybooks() {
    try { playbookCatalog.value = (await apiClient.get('/soc/playbooks')).data.playbooks || []; return playbookCatalog.value }
    catch (e) { _err(e, 'Playbook-Katalog konnte nicht geladen werden') }
  }
  async function fetchIncidentPlaybooks(id: number) {
    try { return (await apiClient.get(`/soc/incidents/${id}/playbooks`)).data }
    catch (e) { _err(e, 'Incident-Playbooks konnten nicht geladen werden') }
  }
  async function assignPlaybook(id: number, playbookId: number) {
    try { return (await apiClient.post(`/soc/incidents/${id}/playbooks`, { playbook_id: playbookId })).data }
    catch (e) { _err(e, 'Playbook-Zuordnung fehlgeschlagen') }
  }
  async function togglePlaybookStep(id: number, instanceId: number, stepId: number, done: boolean) {
    try { await apiClient.post(`/soc/incidents/${id}/playbooks/${instanceId}/step`, { step_id: stepId, done }) }
    catch (e) { _err(e, 'Schritt konnte nicht aktualisiert werden') }
  }
  async function fetchSlaKpis() {
    try { slaKpis.value = (await apiClient.get('/soc/sla-kpis')).data; return slaKpis.value }
    catch (e) { _err(e, 'SLA-Kennzahlen konnten nicht geladen werden') }
  }
  // Betrieb: Handover / Eskalation / RACI (#1318)
  const handovers = ref<any[]>([])
  const escalation = ref<any[]>([])
  const raci = ref<any[]>([])
  async function fetchHandovers() {
    try { handovers.value = (await apiClient.get('/soc/handover')).data.handovers || []; return handovers.value }
    catch (e) { _err(e, 'Schichtübergaben konnten nicht geladen werden') }
  }
  async function saveHandover(payload: any) {
    try { const r = (await apiClient.post('/soc/handover', payload)).data; await fetchHandovers(); return r }
    catch (e) { _err(e, 'Schichtübergabe konnte nicht gespeichert werden') }
  }
  async function deleteHandover(id: number) {
    try { await apiClient.delete(`/soc/handover/${id}`); await fetchHandovers() }
    catch (e) { _err(e, 'Schichtübergabe konnte nicht gelöscht werden') }
  }
  async function fetchEscalation() {
    try { escalation.value = (await apiClient.get('/soc/escalation')).data.escalation || []; return escalation.value }
    catch (e) { _err(e, 'Eskalationsmatrix konnte nicht geladen werden') }
  }
  async function saveEscalation(payload: any) {
    try { const r = (await apiClient.post('/soc/escalation', payload)).data; await fetchEscalation(); return r }
    catch (e) { _err(e, 'Eskalationszeile konnte nicht gespeichert werden') }
  }
  async function deleteEscalation(id: number) {
    try { await apiClient.delete(`/soc/escalation/${id}`); await fetchEscalation() }
    catch (e) { _err(e, 'Eskalationszeile konnte nicht gelöscht werden') }
  }
  async function fetchRaci() {
    try { raci.value = (await apiClient.get('/soc/raci')).data.raci || []; return raci.value }
    catch (e) { _err(e, 'RACI konnte nicht geladen werden') }
  }
  async function saveRaci(payload: any) {
    try { const r = (await apiClient.post('/soc/raci', payload)).data; await fetchRaci(); return r }
    catch (e) { _err(e, 'RACI-Zeile konnte nicht gespeichert werden') }
  }
  async function deleteRaci(id: number) {
    try { await apiClient.delete(`/soc/raci/${id}`); await fetchRaci() }
    catch (e) { _err(e, 'RACI-Zeile konnte nicht gelöscht werden') }
  }
  async function escalateIncident(id: number, stufe: number) {
    try { const r = (await apiClient.post(`/soc/incidents/${id}/escalate`, { stufe })).data; await getIncident(id); return r }
    catch (e) { _err(e, 'Eskalation fehlgeschlagen') }
  }
  // Detection-Use-Cases + ATT&CK-Coverage (#1321)
  const usecases = ref<any[]>([])
  const detectionStates = ref<string[]>([])
  const coverage = ref<any>(null)
  const coverageSource = ref<'alarme' | 'regelwerk' | 'beides'>('beides') // #1349 Quellen-Umschalter
  async function fetchUsecases() {
    try { const d = (await apiClient.get('/soc/detection/usecases')).data; usecases.value = d.usecases || []; detectionStates.value = d.states || []; return usecases.value }
    catch (e) { _err(e, 'Detection-Use-Cases konnten nicht geladen werden') }
  }
  async function saveUsecase(payload: any) {
    try { const r = (await apiClient.post('/soc/detection/usecases', payload)).data; await fetchUsecases(); await fetchCoverage(); return r }
    catch (e) { _err(e, 'Use-Case konnte nicht gespeichert werden') }
  }
  async function deleteUsecase(id: number) {
    try { await apiClient.delete(`/soc/detection/usecases/${id}`); await fetchUsecases(); await fetchCoverage() }
    catch (e) { _err(e, 'Use-Case konnte nicht gelöscht werden') }
  }
  async function fetchCoverage(source?: 'alarme' | 'regelwerk' | 'beides') {
    if (source) coverageSource.value = source
    try { coverage.value = (await apiClient.get('/soc/detection/coverage', { params: { source: coverageSource.value } })).data; return coverage.value }
    catch (e) { _err(e, 'Coverage konnte nicht geladen werden') }
  }
  // #1349 — Regelwerk-Abdeckung + 1-Klick-Bestätigung von Use-Case-Kandidaten
  async function confirmUsecase(payload: { technique: string; rule_ids?: number[]; existing_usecase_id?: number | null }) {
    try { const r = (await apiClient.post('/soc/detection/use-cases/confirm', payload)).data; await fetchUsecases(); await fetchCoverage(); return r }
    catch (e) { _err(e, 'Use-Case konnte nicht bestätigt werden') }
  }
  // #1400: Alle Regelwerk-Kandidaten auf einmal bestätigen (eine Refetch am Ende).
  async function confirmUsecasesBulk(candidates: { technique: string; rule_ids?: number[]; existing_usecase_id?: number | null }[]) {
    try {
      for (const c of candidates) {
        await apiClient.post('/soc/detection/use-cases/confirm',
          { technique: c.technique, rule_ids: c.rule_ids, existing_usecase_id: c.existing_usecase_id })
      }
      await fetchUsecases(); await fetchCoverage()
    } catch (e) { _err(e, 'Massen-Bestätigung der Use-Cases fehlgeschlagen') }
  }
  // Regelwerk-Explorer (#1348) — read-only Wazuh-Regelwerk
  const rules = ref<any[]>([])
  const rulesTotal = ref(0)
  const rulesShown = ref(0)
  const rulesSync = ref<any>(null)
  const rulesLoading = ref(false)
  async function fetchRules(filters: any = {}) {
    try {
      const params: any = {}
      if (filters.q) params.q = filters.q
      if (filters.group) params.group = filters.group
      if (filters.mitre) params.mitre = filters.mitre
      if (filters.min_level != null && filters.min_level !== '') params.min_level = filters.min_level
      if (filters.status) params.status = filters.status
      const d = (await apiClient.get('/soc/rules', { params })).data
      rules.value = d.rules || []; rulesTotal.value = d.total || 0
      rulesShown.value = d.shown || 0; rulesSync.value = d.sync || null
      return d
    } catch (e) { _err(e, 'Regelwerk konnte nicht geladen werden') }
  }
  async function syncRules() {
    rulesLoading.value = true
    try {
      const r = (await apiClient.post('/soc/rules/sync', {})).data
      rulesSync.value = r.sync || rulesSync.value
      await fetchRules()
      return r
    } catch (e) { _err(e, 'Regelwerk konnte nicht geladen werden (Manager-API/„rules:read“ prüfen)') }
    finally { rulesLoading.value = false }
  }
  // SOC-Reifegrad-Self-Assessment (#1326)
  const assessment = ref<any>(null)
  async function fetchAssessment() {
    try { assessment.value = (await apiClient.get('/soc/assessment/catalog')).data; return assessment.value }
    catch (e) { _err(e, 'Reifegrad-Katalog konnte nicht geladen werden') }
  }
  async function saveAssessment(payload: any) {
    try { const r = (await apiClient.post('/soc/assessment', payload)).data; await fetchAssessment(); return r }
    catch (e) { _err(e, 'Assessment konnte nicht gespeichert werden') }
  }
  async function exportAssessment(format: string) {
    try {
      const resp = await apiClient.get('/soc/assessment/export', { params: { format }, responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = `soc-reifegrad.${format}`; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e: any) {
      if (e?.response?.data instanceof Blob) { try { error.value = JSON.parse(await e.response.data.text()).error } catch { error.value = 'Export fehlgeschlagen' } }
      else _err(e, 'Export fehlgeschlagen')
    }
  }
  // Management-Reporting (#1325)
  const mgmtReport = ref<any>(null)
  async function fetchMgmtReport(period = 'monat') {
    try { mgmtReport.value = (await apiClient.get('/soc/mgmt-report', { params: { period } })).data; return mgmtReport.value }
    catch (e) { _err(e, 'Management-Report konnte nicht geladen werden') }
  }
  async function downloadMgmtReport(period: string, format: string) {
    try {
      const resp = await apiClient.get('/soc/mgmt-report/export', { params: { period, format }, responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = `soc-management-report-${period}.${format}`; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e: any) {
      if (e?.response?.data instanceof Blob) { try { error.value = JSON.parse(await e.response.data.text()).error } catch { error.value = 'Report fehlgeschlagen' } }
      else _err(e, 'Report fehlgeschlagen')
    }
  }
  // Berichts-Center (#1350)
  const berichtTypen = ref<Array<{ key: string; titel: string; norm: string; beschreibung: string }>>([])
  const berichtRuns = ref<any[]>([])
  async function fetchBerichte() {
    try {
      const r = (await apiClient.get('/soc/berichte')).data
      berichtTypen.value = r.typen || []
      berichtRuns.value = r.runs || []
      return r
    } catch (e) { _err(e, 'Berichts-Katalog konnte nicht geladen werden') }
  }
  async function downloadBericht(typ: string, von: string | null, bis: string | null, format: string) {
    try {
      const params: Record<string, string> = { format }
      if (von) params.von = von
      if (bis) params.bis = bis
      const resp = await apiClient.get(`/soc/berichte/${encodeURIComponent(typ)}`, { params, responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = `soc-bericht-${typ}.${format}`; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e: any) {
      if (e?.response?.data instanceof Blob) { try { error.value = JSON.parse(await e.response.data.text()).error } catch { error.value = 'Bericht fehlgeschlagen' } }
      else _err(e, 'Bericht fehlgeschlagen')
    }
  }
  async function generateBericht(typ: string, von: string | null, bis: string | null, format: string) {
    try {
      const r = (await apiClient.post(`/soc/berichte/${encodeURIComponent(typ)}/generate`, { von, bis, format })).data
      await fetchBerichte()
      return r
    } catch (e) { _err(e, 'Bericht konnte nicht erzeugt werden') }
  }
  async function downloadBerichtRun(runId: number, dateiname: string) {
    try {
      const resp = await apiClient.get(`/soc/berichte/runs/${runId}/download`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = dateiname || `soc-bericht-${runId}`; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) { _err(e, 'Download fehlgeschlagen') }
  }

  // Log-Source-/Coverage-Management (#1324)
  const logHealth = ref<any>(null)
  async function fetchLogSources() {
    try { logHealth.value = (await apiClient.get('/soc/log-sources')).data; return logHealth.value }
    catch (e) { _err(e, 'Log-Quellen konnten nicht geladen werden') }
  }
  async function saveLogSource(payload: any) {
    try { const r = (await apiClient.post('/soc/log-sources', payload)).data; await fetchLogSources(); return r }
    catch (e) { _err(e, 'Log-Quelle konnte nicht gespeichert werden') }
  }
  async function deleteLogSource(id: number) {
    try { await apiClient.delete(`/soc/log-sources/${id}`); await fetchLogSources() }
    catch (e) { _err(e, 'Log-Quelle konnte nicht gelöscht werden') }
  }
  // Threat-Hunting (#1323)
  const hunts = ref<any[]>([])
  async function fetchHunts() {
    try { hunts.value = (await apiClient.get('/soc/hunts')).data.hunts || []; return hunts.value }
    catch (e) { _err(e, 'Hunts konnten nicht geladen werden') }
  }
  async function saveHunt(payload: any) {
    try { const r = (await apiClient.post('/soc/hunts', payload)).data; await fetchHunts(); return r }
    catch (e) { _err(e, 'Hunt konnte nicht gespeichert werden') }
  }
  async function deleteHunt(id: number) {
    try { await apiClient.delete(`/soc/hunts/${id}`); await fetchHunts() }
    catch (e) { _err(e, 'Hunt konnte nicht gelöscht werden') }
  }
  async function runHuntQuery(query: string, limit = 50) {
    try { return (await apiClient.post('/soc/hunts/query', { query, limit })).data }
    catch (e: any) { return { ok: false, error: e?.response?.data?.error || 'Query fehlgeschlagen' } }
  }
  async function escalateHunt(id: number, payload: any) {
    try { const r = (await apiClient.post(`/soc/hunts/${id}/escalate`, payload)).data; await fetchHunts(); return r }
    catch (e) { _err(e, 'Eskalation fehlgeschlagen') }
  }
  // Threat-Intelligence / IOC (#1322)
  const iocs = ref<any[]>([])
  const iocTypes = ref<string[]>([])
  const iocAlerts = ref<any[]>([])
  async function fetchIocs() {
    try { const d = (await apiClient.get('/soc/iocs')).data; iocs.value = d.iocs || []; iocTypes.value = d.types || []; iocAlerts.value = d.alerts_with_iocs || []; return iocs.value }
    catch (e) { _err(e, 'IOCs konnten nicht geladen werden') }
  }
  async function saveIoc(payload: any) {
    try { const r = (await apiClient.post('/soc/iocs', payload)).data; await fetchIocs(); return r }
    catch (e) { _err(e, 'IOC konnte nicht gespeichert werden') }
  }
  async function importIocs(text: string, quelle: string) {
    try { const r = (await apiClient.post('/soc/iocs/import', { text, quelle })).data; await fetchIocs(); return r }
    catch (e) { _err(e, 'IOC-Import fehlgeschlagen') }
  }
  async function deleteIoc(id: number) {
    try { await apiClient.delete(`/soc/iocs/${id}`); await fetchIocs() }
    catch (e) { _err(e, 'IOC konnte nicht gelöscht werden') }
  }
  async function rescanIocs() {
    try { const r = (await apiClient.post('/soc/iocs/rescan', {})).data; await fetchIocs(); return r }
    catch (e) { _err(e, 'Rescan fehlgeschlagen') }
  }
  // SOC-Übungen (#1319) + ISO-22398-Vollausbau (#1351)
  const uebungen = ref<any[]>([])
  const uebungMeta = ref<any>({ types: [], states: [], ergebnis: [], lifecycle: [],
    ziel_types: [], ziel_bewertung: [], inject_states: [], mass_states: [] })
  const currentUebung = ref<any>(null)
  async function fetchUebungen() {
    try {
      const d = (await apiClient.get('/soc/uebungen')).data
      uebungen.value = d.uebungen || []
      uebungMeta.value = { types: d.types, states: d.states, ergebnis: d.ergebnis,
        lifecycle: d.lifecycle || [], ziel_types: d.ziel_types || [],
        ziel_bewertung: d.ziel_bewertung || [], inject_states: d.inject_states || [],
        mass_states: d.mass_states || [] }
      return uebungen.value
    } catch (e) { _err(e, 'Übungen konnten nicht geladen werden') }
  }
  async function fetchUebung(id: number) {
    try {
      currentUebung.value = (await apiClient.get(`/soc/uebungen/${id}`)).data.uebung
      return currentUebung.value
    } catch (e) { _err(e, 'Übung konnte nicht geladen werden') }
  }
  async function saveUebung(payload: any) {
    try { const r = (await apiClient.post('/soc/uebungen', payload)).data; await fetchUebungen(); return r }
    catch (e) { _err(e, 'Übung konnte nicht gespeichert werden') }
  }
  async function deleteUebung(id: number) {
    try { await apiClient.delete(`/soc/uebungen/${id}`); await fetchUebungen() }
    catch (e) { _err(e, 'Übung konnte nicht gelöscht werden') }
  }
  // Ziele
  async function saveUebungZiel(uebungId: number, payload: any) {
    try { const r = (await apiClient.post(`/soc/uebungen/${uebungId}/ziele`, payload)).data; await fetchUebung(uebungId); return r }
    catch (e) { _err(e, 'Ziel konnte nicht gespeichert werden') }
  }
  async function deleteUebungZiel(uebungId: number, zielId: number) {
    try { await apiClient.delete(`/soc/uebungen/ziele/${zielId}`); await fetchUebung(uebungId) }
    catch (e) { _err(e, 'Ziel konnte nicht gelöscht werden') }
  }
  // MSEL-Injects
  async function saveUebungInject(uebungId: number, payload: any) {
    try { const r = (await apiClient.post(`/soc/uebungen/${uebungId}/injects`, payload)).data; await fetchUebung(uebungId); return r }
    catch (e) { _err(e, 'Inject konnte nicht gespeichert werden') }
  }
  async function deleteUebungInject(uebungId: number, injectId: number) {
    try { await apiClient.delete(`/soc/uebungen/injects/${injectId}`); await fetchUebung(uebungId) }
    catch (e) { _err(e, 'Inject konnte nicht gelöscht werden') }
  }
  // Improvement Plan / Korrekturmaßnahmen
  async function saveUebungMassnahme(uebungId: number, payload: any) {
    try { const r = (await apiClient.post(`/soc/uebungen/${uebungId}/massnahmen`, payload)).data; await fetchUebung(uebungId); return r }
    catch (e) { _err(e, 'Maßnahme konnte nicht gespeichert werden') }
  }
  async function setUebungMassnahmeStatus(uebungId: number, massnahmeId: number, status: string) {
    try { await apiClient.post(`/soc/uebungen/massnahmen/${massnahmeId}/status`, { status }); await fetchUebung(uebungId) }
    catch (e) { _err(e, 'Status konnte nicht gesetzt werden') }
  }
  async function deleteUebungMassnahme(uebungId: number, massnahmeId: number) {
    try { await apiClient.delete(`/soc/uebungen/massnahmen/${massnahmeId}`); await fetchUebung(uebungId) }
    catch (e) { _err(e, 'Maßnahme konnte nicht gelöscht werden') }
  }
  async function exportAar(uebungId: number, fmt: 'docx' | 'pdf') {
    try {
      const resp = await apiClient.get(`/soc/uebungen/${uebungId}/aar`, {
        params: { format: fmt }, responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = `soc-aar-${uebungId}.${fmt}`; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) { _err(e, 'AAR-Export fehlgeschlagen') }
  }
  async function exportUebungen() {
    try {
      const resp = await apiClient.get('/soc/uebungen/export', { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = 'soc-uebungen.csv'; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) { _err(e, 'Export fehlgeschlagen') }
  }
  // Beweissicherung / Asservaten (#1317)
  async function fetchEvidence(id: number) {
    try { return (await apiClient.get(`/soc/incidents/${id}/evidence`)).data.evidence || [] }
    catch (e) { _err(e, 'Asservate konnten nicht geladen werden') }
  }
  async function uploadEvidence(id: number, file: File, retentionDays: number, beschreibung: string) {
    try {
      const fd = new FormData(); fd.append('file', file)
      fd.append('retention_days', String(retentionDays)); fd.append('beschreibung', beschreibung)
      return (await apiClient.post(`/soc/incidents/${id}/evidence`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })).data
    } catch (e) { _err(e, 'Asservat konnte nicht gespeichert werden') }
  }
  async function freezeSnapshot(id: number) {
    try { return (await apiClient.post(`/soc/incidents/${id}/evidence/snapshot`, {})).data }
    catch (e) { _err(e, 'Rohlog-Snapshot fehlgeschlagen') }
  }
  async function fetchCustody(evidenceId: number) {
    try { return (await apiClient.get(`/soc/evidence/${evidenceId}/custody`)).data }
    catch (e) { _err(e, 'Chain of Custody konnte nicht geladen werden') }
  }
  async function downloadEvidence(evidenceId: number, filename: string) {
    try {
      const resp = await apiClient.get(`/soc/evidence/${evidenceId}/download`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = filename || 'asservat'; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) { _err(e, 'Download fehlgeschlagen') }
  }
  async function deleteEvidence(evidenceId: number, reason: string) {
    try { return (await apiClient.delete(`/soc/evidence/${evidenceId}`, { data: { reason } })).data }
    catch (e) { _err(e, 'Asservat konnte nicht gelöscht werden') }
  }
  const pirActions = ref<any[]>([])
  async function savePir(id: number, payload: any) {
    try { const r = (await apiClient.put(`/soc/incidents/${id}/pir`, payload)).data; await getIncident(id); return r }
    catch (e) { _err(e, 'PIR konnte nicht gespeichert werden') }
  }
  async function createPirAction(id: number, payload: any) {
    try { const r = (await apiClient.post(`/soc/incidents/${id}/pir/actions`, payload)).data; await getIncident(id); return r }
    catch (e) { _err(e, 'Maßnahme konnte nicht angelegt werden') }
  }
  async function updatePirAction(actionId: number, payload: any) {
    try { await apiClient.put(`/soc/pir/actions/${actionId}`, payload) }
    catch (e) { _err(e, 'Maßnahme konnte nicht aktualisiert werden') }
  }
  async function deletePirAction(actionId: number) {
    try { await apiClient.delete(`/soc/pir/actions/${actionId}`) }
    catch (e) { _err(e, 'Maßnahme konnte nicht gelöscht werden') }
  }
  async function fetchPirActions(onlyOpen = true) {
    try { pirActions.value = (await apiClient.get('/soc/pir/actions', { params: { only_open: onlyOpen ? 1 : 0 } })).data.actions || []; return pirActions.value }
    catch (e) { _err(e, 'Maßnahmen konnten nicht geladen werden') }
  }
  async function exportPirActions() {
    try {
      const resp = await apiClient.get('/soc/pir/actions/export', { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = 'soc-massnahmen.csv'; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e) { _err(e, 'Export fehlgeschlagen') }
  }
  async function saveSla(payload: any) {
    try { const r = (await apiClient.post('/soc/sla', payload)).data; await fetchSlaKpis(); return r }
    catch (e) { _err(e, 'SLA-Ziel konnte nicht gespeichert werden') }
  }
  async function setRegimes(id: number, flags: any) {
    try { await apiClient.put(`/soc/incidents/${id}/regimes`, flags); await getIncident(id) }
    catch (e) { _err(e, 'Regelwerke konnten nicht gespeichert werden') }
  }
  async function evaluateIncident(id: number) {
    try { const r = (await apiClient.post(`/soc/incidents/${id}/evaluate`)).data; await getIncident(id); return r }
    catch (e) { _err(e, 'Meldepflicht-Prüfung fehlgeschlagen') }
  }
  async function runBridge(id: number, regime: string, projekt: string, extra: any = {}) {
    try { const r = (await apiClient.post(`/soc/incidents/${id}/bridge/${regime}`, { projekt_name: projekt, ...extra })).data; await getIncident(id); return r }
    catch (e) { _err(e, 'Brücke fehlgeschlagen') }
  }
  async function closeIncident(id: number, reason: string) {
    try { const r = (await apiClient.post(`/soc/incidents/${id}/close`, { reason })).data; _mergeCurrentIncident(id, r.incident); return r }
    catch (e) { _err(e, 'Schließen fehlgeschlagen') }
  }
  async function downloadReport(ids: number[], format = 'pdf') {
    try {
      const resp = await apiClient.post('/soc/incidents/report', { ids, format }, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([resp.data]))
      const a = document.createElement('a'); a.href = url; a.download = `soc-incidents.${format}`; a.click()
      window.URL.revokeObjectURL(url)
    } catch (e: any) {
      // Blob-Fehlerantwort lesbar machen
      if (e?.response?.data instanceof Blob) { try { error.value = JSON.parse(await e.response.data.text()).error } catch { error.value = 'Report fehlgeschlagen' } }
      else _err(e, 'Report fehlgeschlagen')
    }
  }
  async function getAlert(uid: string) {
    try { return (await apiClient.get(`/soc/alerts/${encodeURIComponent(uid)}`)).data }
    catch (e) { _err(e, 'Alarm-Detail konnte nicht geladen werden') }
  }
  async function linkIncidentAlerts(id: number, alertUids: string[]) {
    try { return (await apiClient.post(`/soc/incidents/${id}/alerts`, { alert_uids: alertUids })).data }
    catch (e) { _err(e, 'Alarme konnten nicht zugeordnet werden') }
  }
  async function unlinkIncidentAlert(id: number, uid: string) {
    try { return (await apiClient.delete(`/soc/incidents/${id}/alerts/${encodeURIComponent(uid)}`)).data }
    catch (e) { _err(e, 'Alarm konnte nicht entfernt werden') }
  }
  async function incidentAlerts(id: number) {
    try { return (await apiClient.get(`/soc/incidents/${id}/alerts`)).data.alerts || [] }
    catch (e) { _err(e, 'Verknüpfte Alarme konnten nicht geladen werden') }
  }
  async function incidentPrompt(id: number) {
    try { return (await apiClient.get(`/soc/incidents/${id}/analyze/prompt`)).data.prompt }
    catch (e) { _err(e, 'Incident-Prompt konnte nicht erzeugt werden') }
  }
  async function analyzeIncident(id: number, response?: string) {
    try { const r = (await apiClient.post(`/soc/incidents/${id}/analyze`, response ? { response } : {})).data.analysis; await getIncident(id); return r }
    catch (e) { _err(e, 'Incident-Analyse fehlgeschlagen') }
  }

  // ── Schwachstellen-Register (#1343) ──────────────────────────────────────
  const vulnerabilities = ref<any[]>([])
  const vulnKpi = ref<any>({})
  const vulnTriageStates = ref<string[]>([])
  async function fetchVulnerabilities(params: any = {}) {
    loading.value = true
    try {
      const d = (await apiClient.get('/soc/vulnerabilities', { params })).data
      vulnerabilities.value = d.vulnerabilities || []
      vulnKpi.value = d.kpi || {}
      vulnTriageStates.value = d.triage_states || []
      return vulnerabilities.value
    } catch (e) { _err(e, 'Schwachstellen konnten nicht geladen werden') }
    finally { loading.value = false }
  }
  async function syncVulnerabilities(name = 'default') {
    try { return (await apiClient.post('/soc/vulnerabilities/sync', { name })).data }
    catch (e: any) { return { ok: false, error: e?.response?.data?.error || 'Schwachstellen-Sync fehlgeschlagen' } }
  }
  async function vulnSyncStatus(name = 'default') {
    try { return (await apiClient.get('/soc/vulnerabilities/sync/status', { params: { name } })).data }
    catch (e) { _err(e, 'Sync-Status konnte nicht geladen werden') }
  }
  async function triageVulnerability(id: number, triageStatus: string, kommentar?: string) {
    try { return (await apiClient.post(`/soc/vulnerabilities/${id}/triage`, { triage_status: triageStatus, kommentar })).data }
    catch (e) { _err(e, 'Triage fehlgeschlagen') }
  }
  async function bulkTriageVulnerabilities(ids: number[], triageStatus: string, kommentar?: string) {
    try { return (await apiClient.post('/soc/vulnerabilities/bulk-triage', { ids, triage_status: triageStatus, kommentar })).data }
    catch (e) { _err(e, 'Sammel-Triage fehlgeschlagen') }
  }
  async function promoteVulnerability(id: number, target: 'alert' | 'incident') {
    try { return (await apiClient.post(`/soc/vulnerabilities/${id}/promote`, { target })).data }
    catch (e: any) { return { ok: false, error: e?.response?.data?.error || 'Aufnehmen fehlgeschlagen', status: e?.response?.status } }
  }

  return {
    loading, error, constants, kpis, connections, alerts, groups, incidents,
    currentIncident, assets, suppressions, controlEvidence,
    fetchConstants, fetchKpis, fetchControlEvidence, fetchLikelihood,
    lageberichtPrompt, runLagebericht, fetchOwaspLlm, pushOwaspLlm,
    fetchConnections, saveConnection, deleteConnection, testConnection, sync, fetchSnippet,
    fetchAlerts, fetchGroups, triageAlert, alertPrompt, analyzeAlert,
    fetchSuppressions, addSuppression, deleteSuppression, dryRunSuppression,
    fetchAssets, saveAsset, refreshAssets, discoverSyslog, createAssetsFromSyslog, currentAsset, fetchAssetDetail, deleteAsset, assignAlert, assignIncident,
    fetchIncidents, getIncident, createIncident, updateIncident, setIncidentStatus, addNote, evaluateIncident, runBridge, setRegimes,
    getAlert, incidentAlerts, incidentPrompt, analyzeIncident, closeIncident, downloadReport,
    linkIncidentAlerts, unlinkIncidentAlert,
    fetchIncidentIssues, createIncidentIssue, deleteIncidentIssue,
    playbookCatalog, fetchPlaybooks, fetchIncidentPlaybooks, assignPlaybook, togglePlaybookStep,
    slaKpis, fetchSlaKpis, saveSla,
    fetchEvidence, uploadEvidence, freezeSnapshot, fetchCustody, downloadEvidence, deleteEvidence,
    handovers, escalation, raci, fetchHandovers, saveHandover, deleteHandover,
    fetchEscalation, saveEscalation, deleteEscalation, fetchRaci, saveRaci, deleteRaci, escalateIncident,
    uebungen, uebungMeta, currentUebung, fetchUebungen, fetchUebung, saveUebung, deleteUebung, exportUebungen,
    saveUebungZiel, deleteUebungZiel, saveUebungInject, deleteUebungInject,
    saveUebungMassnahme, setUebungMassnahmeStatus, deleteUebungMassnahme, exportAar,
    usecases, detectionStates, coverage, coverageSource, fetchUsecases, saveUsecase, deleteUsecase, fetchCoverage, confirmUsecase, confirmUsecasesBulk,
    rules, rulesTotal, rulesShown, rulesSync, rulesLoading, fetchRules, syncRules,
    iocs, iocTypes, iocAlerts, fetchIocs, saveIoc, importIocs, deleteIoc, rescanIocs,
    hunts, fetchHunts, saveHunt, deleteHunt, runHuntQuery, escalateHunt,
    logHealth, fetchLogSources, saveLogSource, deleteLogSource,
    mgmtReport, fetchMgmtReport, downloadMgmtReport,
    berichtTypen, berichtRuns, fetchBerichte, downloadBericht, generateBericht, downloadBerichtRun,
    assessment, fetchAssessment, saveAssessment, exportAssessment,
    pirActions, savePir, createPirAction, updatePirAction, deletePirAction, fetchPirActions, exportPirActions,
    vulnerabilities, vulnKpi, vulnTriageStates,
    fetchVulnerabilities, syncVulnerabilities, vulnSyncStatus,
    triageVulnerability, bulkTriageVulnerabilities, promoteVulnerability,
  }
})
