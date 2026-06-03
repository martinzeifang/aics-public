import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export interface DsgvoProjekt {
  id: string
  name: string
  unternehmen: string
  company: string
  organisationstyp: string
  beschreibung: string
  description: string
  berater: string
  meta_json?: string
  created_at?: string
  updated_at?: string
}

export interface DsgvoAnforderung {
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
  verantwortlich?: string
  zieldatum?: string
  status: 'pending' | 'partial' | 'complete'
  updated_at?: string
}

export interface ReifegradResult {
  ampel: string
  bewertete_count: number
  gesamt_count: number
  gesamt_pct: number
  kapitel_pct: Record<string, number>
}

export const useDsgvoStore = defineStore('dsgvo', () => {
  const projekte = ref<DsgvoProjekt[]>([])
  const selectedProjekt = ref<string | null>(null)
  const anforderungen = ref<DsgvoAnforderung[]>([])
  const reifegrad = ref<ReifegradResult | null>(null)
  const customAnforderungen = ref<any[]>([])
  const constants = ref<any | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedProjektObj = computed(() =>
    projekte.value.find(p => p.name === selectedProjekt.value) || null,
  )

  const fetchConstants = async () => {
    try {
      const res = await apiClient.get('/dsgvo/constants')
      constants.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Constants'
    }
  }

  const fetchProjekte = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/dsgvo/projekte')
      projekte.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden'
    } finally {
      loading.value = false
    }
  }

  const createProjekt = async (data: Partial<DsgvoProjekt>): Promise<DsgvoProjekt | null> => {
    try {
      const res = await apiClient.post('/dsgvo/projekte', data)
      projekte.value.push(res.data)
      return res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Anlegen'
      return null
    }
  }

  const updateProjekt = async (name: string, data: Partial<DsgvoProjekt>): Promise<DsgvoProjekt | null> => {
    try {
      const res = await apiClient.put(`/dsgvo/projekte/${encodeURIComponent(name)}`, data)
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
      await apiClient.delete(`/dsgvo/projekte/${encodeURIComponent(name)}`)
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
      const res = await apiClient.get(`/dsgvo/projekte/${encodeURIComponent(projektName)}/anforderungen`)
      anforderungen.value = res.data
      selectedProjekt.value = projektName
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Anforderungen'
    }
  }

  const fetchReifegrad = async (projektName: string) => {
    try {
      const res = await apiClient.get(`/dsgvo/projekte/${encodeURIComponent(projektName)}/reifegrad`)
      reifegrad.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Reifegrad'
    }
  }

  const saveBewertung = async (projektName: string, anforderungId: string, payload: Partial<DsgvoAnforderung>) => {
    try {
      await apiClient.post(
        `/dsgvo/projekte/${encodeURIComponent(projektName)}/bewertungen`,
        {
          anforderung_id: anforderungId,
          bewertung: payload.bewertung ?? payload.score ?? 0,
          kommentar: payload.kommentar ?? '',
          massnahme: payload.massnahme ?? '',
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

  const fetchCustomAnforderungen = async () => {
    try {
      const res = await apiClient.get('/dsgvo/anforderungen/custom')
      customAnforderungen.value = res.data
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler'
    }
  }

  // Sprint δ Phase A — Pflicht-Doku-Manager (#584)
  const vvt = ref<any[]>([])
  const tom = ref<any[]>([])
  const dpia = ref<any[]>([])
  const avv = ref<any[]>([])
  const datenpannen = ref<any[]>([])
  const pflichtDokuStatus = ref<any | null>(null)
  const branchenTemplates = ref<any[]>([])

  const _pjUrl = (suffix: string) => {
    if (!selectedProjekt.value) throw new Error('Kein DSGVO-Projekt gewählt')
    return `/dsgvo/projekte/${encodeURIComponent(selectedProjekt.value)}${suffix}`
  }

  function _makeCrud(slug: string, ref: any) {
    return {
      fetch: async () => {
        try { ref.value = (await apiClient.get(_pjUrl(`/${slug}`))).data || [] }
        catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
      },
      save: async (data: any) => {
        try { await apiClient.post(_pjUrl(`/${slug}`), data); return true }
        catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
      },
      remove: async (id: number) => {
        try { await apiClient.delete(_pjUrl(`/${slug}/${id}`)); return true }
        catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return false }
      },
    }
  }

  const vvtCrud = _makeCrud('vvt', vvt)
  const tomCrud = _makeCrud('tom', tom)
  const dpiaCrud = _makeCrud('dpia', dpia)
  const avvCrud = _makeCrud('avv', avv)
  const pannenCrud = _makeCrud('datenpannen', datenpannen)

  const fetchVvt = async () => { await vvtCrud.fetch() }
  const saveVvt = async (d: any) => { const ok = await vvtCrud.save(d); if (ok) await fetchVvt(); return ok }
  const deleteVvt = async (id: number) => { const ok = await vvtCrud.remove(id); if (ok) await fetchVvt(); return ok }
  const fetchTom = async () => { await tomCrud.fetch() }
  const saveTom = async (d: any) => { const ok = await tomCrud.save(d); if (ok) await fetchTom(); return ok }
  const deleteTom = async (id: number) => { const ok = await tomCrud.remove(id); if (ok) await fetchTom(); return ok }
  const fetchDpia = async () => { await dpiaCrud.fetch() }
  const saveDpia = async (d: any) => { const ok = await dpiaCrud.save(d); if (ok) await fetchDpia(); return ok }
  const deleteDpia = async (id: number) => { const ok = await dpiaCrud.remove(id); if (ok) await fetchDpia(); return ok }
  const fetchAvv = async () => { await avvCrud.fetch() }
  const saveAvv = async (d: any) => { const ok = await avvCrud.save(d); if (ok) await fetchAvv(); return ok }
  const deleteAvv = async (id: number) => { const ok = await avvCrud.remove(id); if (ok) await fetchAvv(); return ok }
  const fetchPannen = async () => { await pannenCrud.fetch() }
  const savePanne = async (d: any) => { const ok = await pannenCrud.save(d); if (ok) await fetchPannen(); return ok }
  const deletePanne = async (id: number) => { const ok = await pannenCrud.remove(id); if (ok) await fetchPannen(); return ok }

  const fetchPflichtDokuStatus = async () => {
    try { pflichtDokuStatus.value = (await apiClient.get(_pjUrl('/pflicht-doku'))).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }

  // Phase B Wizards
  const fetchBranchenTemplates = async () => {
    try { branchenTemplates.value = (await apiClient.get('/dsgvo/wizards/branchen-templates')).data || [] }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler' }
  }
  const applyBranchenTemplate = async (brancheId: string) => {
    try { const res = await apiClient.post(_pjUrl('/wizards/branchen-template/apply'), { branche_id: brancheId }); return res.data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }
  const getWizardPrompt = async (wizard: 'rechtsgrundlage' | 'datenpanne-meldung' | 'betroffenenrechte', body: any = {}) => {
    try { return (await apiClient.post(_pjUrl(`/wizards/${wizard}/prompt`), body)).data?.prompt || '' }
    catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return '' }
  }
  const parseWizardResponse = async (wizard: string, response: string, extra: any = {}, apply = true) => {
    try {
      const body: any = { response, ...extra }
      if (!apply) body.dry_run = true
      return (await apiClient.post(_pjUrl(`/wizards/${wizard}/parse`), body)).data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Fehler'; return null }
  }

  return {
    projekte,
    selectedProjekt,
    selectedProjektObj,
    anforderungen,
    reifegrad,
    customAnforderungen,
    constants,
    loading,
    error,
    fetchConstants,
    fetchProjekte,
    createProjekt,
    updateProjekt,
    deleteProjekt,
    fetchAnforderungen,
    fetchReifegrad,
    saveBewertung,
    fetchCustomAnforderungen,
    // Phase A Pflicht-Doku
    vvt, tom, dpia, avv, datenpannen, pflichtDokuStatus,
    fetchVvt, saveVvt, deleteVvt,
    fetchTom, saveTom, deleteTom,
    fetchDpia, saveDpia, deleteDpia,
    fetchAvv, saveAvv, deleteAvv,
    fetchPannen, savePanne, deletePanne,
    fetchPflichtDokuStatus,
    // Phase B
    branchenTemplates,
    fetchBranchenTemplates, applyBranchenTemplate,
    getWizardPrompt, parseWizardResponse,
  }
})
