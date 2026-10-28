import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface NIS2Projekt {
  id: string
  name: string
  company: string
  unternehmen: string
  einrichtungsklasse: string
  beschreibung: string
  description: string
  berater: string
  created_at?: string
  updated_at?: string
}

export interface NIS2Anforderung {
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

export interface ReifegradResult {
  gesamt: { prozent: number; punkte_aktuell: number; punkte_max: number; ampel: string }
  kapitel: Record<string, { prozent: number; ampel: string; bewertet: number; gesamt: number }>
  luecken: Array<{ id: string; kapitel: string; titel: string; bewertung: number; gewichtung: number }>
}

export const useNis2Store = defineStore('nis2', () => {
  const projekte = ref<NIS2Projekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const anforderungen = ref<NIS2Anforderung[]>([])
  const reifegrad = ref<ReifegradResult | null>(null)
  const customAnforderungen = ref<any[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  const massnahmen = computed(() => anforderungen.value)

  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/nis2/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<NIS2Projekt>): Promise<NIS2Projekt | null> => {
    try {
      const res = await apiClient.post('/nis2/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<NIS2Projekt>): Promise<NIS2Projekt | null> => {
    try {
      const res = await apiClient.put(`/nis2/projekte/${encodeURIComponent(name)}`, data)
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
      await apiClient.delete(`/nis2/projekte/${encodeURIComponent(name)}`)
      projekte.value = projekte.value.filter(p => p.name !== name)
      if (selectedProjekt.value === name) selectedProjekt.value = null
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Löschen'
      return false
    }
  }

  const fetchAnforderungen = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/nis2/projekte/${encodeURIComponent(projektName)}/anforderungen`)
      anforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Anforderungen'
    }
  }

  const fetchMassnahmen = fetchAnforderungen

  const saveBewertung = async (projektName: string, anforderungId: string, payload: Partial<NIS2Anforderung>) => {
    try {
      await apiClient.post(
        `/nis2/projekte/${encodeURIComponent(projektName)}/bewertungen`,
        {
          anforderung_id: anforderungId,
          bewertung: payload.bewertung ?? payload.score ?? 0,
          kommentar: payload.kommentar ?? '',
          massnahme: payload.massnahme ?? '',
          verantwortlich: payload.verantwortlich ?? '',
          zieldatum: payload.zieldatum ?? '',
        },
      )
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
      const res = await apiClient.get(`/nis2/projekte/${encodeURIComponent(projektName)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Reifegrad'
    }
  }

  const fetchCustomAnforderungen = async () => {
    try {
      const res = await apiClient.get('/nis2/anforderungen/custom')
      customAnforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
    }
  }

  const saveCustomAnforderung = async (data: any) => {
    try {
      await apiClient.post('/nis2/anforderungen/custom', data)
      await fetchCustomAnforderungen()
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  const deleteCustomAnforderung = async (id: string) => {
    try {
      await apiClient.delete(`/nis2/anforderungen/custom/${encodeURIComponent(id)}`)
      customAnforderungen.value = customAnforderungen.value.filter(c => c.id !== id)
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
      return false
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Phase A — Pflicht-Doku-Manager (#579)
  // ──────────────────────────────────────────────────────────────────

  const assets = ref<any[]>([])
  const risiken = ref<any[]>([])
  const incidentResponse = ref<any>({})
  const vendors = ref<any[]>([])
  const bcp = ref<any>({})
  const pflichtDokuStatus = ref<any | null>(null)

  const _pjUrl = (suffix: string) => {
    if (!selectedProjekt.value) throw new Error('Kein NIS2-Projekt gewählt')
    return `/nis2/projekte/${encodeURIComponent(selectedProjekt.value)}${suffix}`
  }

  // N1 Assets
  const fetchAssets = async () => {
    try { assets.value = (await apiClient.get(_pjUrl('/assets'))).data || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveAsset = async (data: any) => {
    try { await apiClient.post(_pjUrl('/assets'), data); await fetchAssets(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  const deleteAsset = async (id: number) => {
    try { await apiClient.delete(_pjUrl(`/assets/${id}`)); await fetchAssets(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  // N2 Risiken
  const fetchRisiken = async (status?: string) => {
    try {
      const q = status ? `?status=${status}` : ''
      risiken.value = (await apiClient.get(_pjUrl(`/risiken${q}`))).data || []
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveRisiko = async (data: any) => {
    try { await apiClient.post(_pjUrl('/risiken'), data); await fetchRisiken(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  const deleteRisiko = async (id: number) => {
    try { await apiClient.delete(_pjUrl(`/risiken/${id}`)); await fetchRisiken(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  // N3 Incident-Response
  const fetchIncidentResponse = async () => {
    try { incidentResponse.value = (await apiClient.get(_pjUrl('/incident-response'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveIncidentResponse = async (data: any) => {
    try { await apiClient.post(_pjUrl('/incident-response'), data); await fetchIncidentResponse(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  // N4 Vendors
  const fetchVendors = async () => {
    try { vendors.value = (await apiClient.get(_pjUrl('/vendors'))).data || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveVendor = async (data: any) => {
    try { await apiClient.post(_pjUrl('/vendors'), data); await fetchVendors(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  const deleteVendor = async (id: number) => {
    try { await apiClient.delete(_pjUrl(`/vendors/${id}`)); await fetchVendors(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  // N5 BCP
  const fetchBcp = async () => {
    try { bcp.value = (await apiClient.get(_pjUrl('/bcp'))).data || {} }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const saveBcp = async (data: any) => {
    try { await apiClient.post(_pjUrl('/bcp'), data); await fetchBcp(); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }

  const fetchPflichtDokuStatus = async () => {
    try { pflichtDokuStatus.value = (await apiClient.get(_pjUrl('/pflicht-doku'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }

  // Phase B — KI-Wizards (#580)
  const sektorTemplates = ref<any[]>([])
  const fetchSektorTemplates = async () => {
    try { sektorTemplates.value = (await apiClient.get('/nis2/wizards/sektor-templates')).data || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const applySektorTemplate = async (sektorId: string) => {
    try { await apiClient.post(_pjUrl('/wizards/sektor-template/apply'), { sektor_id: sektorId }); return true }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
  }
  // #1240: Doc-only-Generatoren (Art. 21(2)) liefern editier-/exportierbare
  // managed_docs — Prompt per GET, Ergebnis über „Als Dokument speichern".
  const DOC_WIZARDS: ReadonlySet<string> = new Set([
    'is-leitlinie', 'incident-handling-konzept', 'bcm-dr-plan',
    'lieferketten-richtlinie', 'krypto-richtlinie', 'zugriffskontroll-policy',
  ])
  const getWizardPrompt = async (wizard: 'klassifikator' | 'incident-notification' | 'supply-chain' | 'incident-24h' | 'incident-72h' | 'incident-final' | 'cyberhygiene-quiz' | 'vendor-tiering' | 'is-leitlinie' | 'incident-handling-konzept' | 'bcm-dr-plan' | 'lieferketten-richtlinie' | 'krypto-richtlinie' | 'zugriffskontroll-policy', body: any = {}) => {
    try {
      const url = _pjUrl(`/wizards/${wizard}/prompt`)
      const res = (wizard === 'klassifikator' || DOC_WIZARDS.has(wizard))
        ? await apiClient.get(url)
        : await apiClient.post(url, body)
      return res.data?.prompt || ''
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const parseWizardResponse = async (wizard: 'klassifikator' | 'incident-notification' | 'supply-chain' | 'incident-24h' | 'incident-72h' | 'incident-final' | 'cyberhygiene-quiz' | 'vendor-tiering' | 'is-leitlinie' | 'incident-handling-konzept' | 'bcm-dr-plan' | 'lieferketten-richtlinie' | 'krypto-richtlinie' | 'zugriffskontroll-policy', response: string, extra: any = {}, apply = true) => {
    try {
      const body: any = { response, ...extra }
      if (!apply) body.dry_run = true
      const res = await apiClient.post(_pjUrl(`/wizards/${wizard}/parse`), body)
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }

  // ──────────────────────────────────────────────────────────────────
  // Sprint #21 — N1–N5 Repo-Scan Auto-Fill + N1-Wizard (#1072–#1076)
  // ──────────────────────────────────────────────────────────────────

  // N1 Asset-Repo-Scan (#1072)
  const suggestAssets = async (repo?: string, branch?: string) => {
    try {
      const res = await apiClient.post(_pjUrl('/assets/suggest'), { repo, branch })
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Repo-Scan fehlgeschlagen'; return null }
  }

  // N1 Asset-Wizard (Copy-Paste) (#1072)
  const getAssetWizardPrompt = async () => {
    try { return (await apiClient.get(_pjUrl('/wizards/asset-inventory/prompt'))).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const parseAssetWizardResponse = async (response: string, apply = true) => {
    try {
      const body: any = { response }
      if (!apply) body.dry_run = true
      const res = await apiClient.post(_pjUrl('/wizards/asset-inventory/parse'), body)
      if (apply) await fetchAssets()
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }

  // N3 Incident-Response CSIRT-Scan (#1074)
  const suggestIncidentResponse = async (repo?: string, branch?: string) => {
    try {
      const res = await apiClient.post(_pjUrl('/incident-response/suggest'), { repo, branch })
      return res.data?.suggestion || {}
    } catch (e: any) { error.value = e?.response?.data?.error || 'Repo-Scan fehlgeschlagen'; return null }
  }

  // N4 Vendor-Scan (#1075)
  const suggestVendors = async (repo?: string, branch?: string) => {
    try {
      const res = await apiClient.post(_pjUrl('/vendors/suggest'), { repo, branch })
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Repo-Scan fehlgeschlagen'; return null }
  }

  // N5 BCP-Backup-Scan (#1076)
  const suggestBcp = async (repo?: string, branch?: string) => {
    try {
      const res = await apiClient.post(_pjUrl('/bcp/suggest'), { repo, branch })
      return res.data?.suggestion || {}
    } catch (e: any) { error.value = e?.response?.data?.error || 'Repo-Scan fehlgeschlagen'; return null }
  }

  // #582 RB-Import
  const fetchRbRisks = async () => {
    try {
      const res = await apiClient.get(_pjUrl('/wizards/rb-risks'))
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Laden der RB-Risiken'; return null }
  }
  const importRbRisks = async (riskIds: number[]) => {
    try {
      const res = await apiClient.post(_pjUrl('/wizards/import-rb-risks/apply'), { risk_ids: riskIds })
      await fetchRisiken()
      await fetchPflichtDokuStatus()
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler beim Import'; return null }
  }

  return {
    projekte,
    selectedProjekt,
    selectedProjektObj,
    anforderungen,
    massnahmen,
    reifegrad,
    customAnforderungen,
    loading,
    error,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchAnforderungen,
    fetchMassnahmen,
    saveBewertung,
    fetchReifegrad,
    fetchCustomAnforderungen,
    saveCustomAnforderung,
    deleteCustomAnforderung,
    // Phase A
    assets, risiken, incidentResponse, vendors, bcp, pflichtDokuStatus,
    fetchAssets, saveAsset, deleteAsset,
    fetchRisiken, saveRisiko, deleteRisiko,
    fetchIncidentResponse, saveIncidentResponse,
    fetchVendors, saveVendor, deleteVendor,
    fetchBcp, saveBcp,
    fetchPflichtDokuStatus,
    // Phase B
    sektorTemplates,
    fetchSektorTemplates,
    applySektorTemplate,
    getWizardPrompt,
    parseWizardResponse,
    fetchRbRisks,
    importRbRisks,
    // Sprint #21 — N1–N5 Repo-Scan Auto-Fill (#1072–#1076)
    suggestAssets,
    getAssetWizardPrompt,
    parseAssetWizardResponse,
    suggestIncidentResponse,
    suggestVendors,
    suggestBcp,
  }
})
