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
  async function createIncident(payload: any) {
    try { const r = (await apiClient.post('/soc/incidents', payload)).data; await fetchIncidents(); return r }
    catch (e) { _err(e, 'Incident konnte nicht angelegt werden') }
  }
  async function updateIncident(id: number, payload: any) {
    try { const r = (await apiClient.put(`/soc/incidents/${id}`, payload)).data; currentIncident.value = r; return r }
    catch (e) { _err(e, 'Incident konnte nicht aktualisiert werden') }
  }
  async function setIncidentStatus(id: number, status: string) {
    try { const r = (await apiClient.post(`/soc/incidents/${id}/status`, { status })).data; await getIncident(id); return r }
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
    try { const r = (await apiClient.post(`/soc/incidents/${id}/close`, { reason })).data; await getIncident(id); return r }
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

  return {
    loading, error, constants, kpis, connections, alerts, groups, incidents,
    currentIncident, assets, suppressions, controlEvidence,
    fetchConstants, fetchKpis, fetchControlEvidence, fetchLikelihood,
    lageberichtPrompt, runLagebericht, fetchOwaspLlm, pushOwaspLlm,
    fetchConnections, saveConnection, deleteConnection, testConnection, sync, fetchSnippet,
    fetchAlerts, fetchGroups, triageAlert, alertPrompt, analyzeAlert,
    fetchSuppressions, addSuppression, deleteSuppression, dryRunSuppression,
    fetchAssets, saveAsset, refreshAssets, currentAsset, fetchAssetDetail, deleteAsset, assignAlert, assignIncident,
    fetchIncidents, getIncident, createIncident, updateIncident, setIncidentStatus, addNote, evaluateIncident, runBridge, setRegimes,
    getAlert, incidentAlerts, incidentPrompt, analyzeIncident, closeIncident, downloadReport,
    fetchIncidentIssues, createIncidentIssue, deleteIncidentIssue,
  }
})
