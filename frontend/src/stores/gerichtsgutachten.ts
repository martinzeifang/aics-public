// G7 — Pinia Store für BISG-Gerichtsgutachten (Backend: /api/gutachten/gerichts/*)
import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export const useGerichtsgutachtenStore = defineStore('gerichtsgutachten', () => {
  const projekte = ref<any[]>([])
  const aktuell = ref<any>(null)
  const beweisfragen = ref<any[]>([])
  const befunde = ref<any[]>([])
  const beurteilungen = ref<any[]>([])
  const assets = ref<any[]>([])
  const verfahrensereignisse = ref<any[]>([])
  const normen = ref<any[]>([])
  const werkzeuge = ref<any[]>([])
  const validatorErrors = ref<any[]>([])
  const validatorWarnings = ref<any[]>([])
  const loading = ref(false)
  const error = ref<string>('')

  const _err = (e: any) => { error.value = e?.response?.data?.error || e?.message || 'Fehler' }

  // ── Projekte ───────────────────────────────────────────
  const fetchProjekte = async () => {
    try { projekte.value = (await apiClient.get('/gutachten/gerichts')).data?.projekte || [] }
    catch (e) { _err(e) }
  }
  const fetchProjekt = async (name: string) => {
    try { aktuell.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}`)).data }
    catch (e) { _err(e) }
  }
  const createProjekt = async (data: any) => {
    try {
      const res = await apiClient.post('/gutachten/gerichts', data)
      await fetchProjekte()
      return res.data?.name
    } catch (e) { _err(e); return null }
  }
  const updateProjekt = async (name: string, data: any) => {
    try { await apiClient.put(`/gutachten/gerichts/${encodeURIComponent(name)}`, data); return true }
    catch (e) { _err(e); return false }
  }
  const deleteProjekt = async (name: string) => {
    try { await apiClient.delete(`/gutachten/gerichts/${encodeURIComponent(name)}`); await fetchProjekte(); return true }
    catch (e) { _err(e); return false }
  }

  // ── #969 Final-Archiv ──────────────────────────────────
  const finalExports = ref<any[]>([])
  const fetchFinalExports = async (name: string) => {
    try { finalExports.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}/final-exports`)).data?.final_exports || [] }
    catch (e) { _err(e) }
  }
  const uploadFinalExport = async (name: string, file: File, bemerkung = '') => {
    try {
      const fd = new FormData(); fd.append('file', file); fd.append('bemerkung', bemerkung)
      const res = await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(name)}/final-export`, fd,
        { headers: { 'Content-Type': 'multipart/form-data' } })
      await fetchFinalExports(name); return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Upload fehlgeschlagen'; return null }
  }
  const downloadFinalExport = async (name: string, id: number, dateiname: string) => {
    try {
      const res = await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}/final-export/${id}/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data); const a = document.createElement('a')
      a.href = url; a.download = dateiname || `final_${id}`; a.click(); URL.revokeObjectURL(url); return true
    } catch (e) { _err(e); return false }
  }
  const deleteFinalExport = async (name: string, id: number, reason: string) => {
    try { await apiClient.delete(`/gutachten/gerichts/${encodeURIComponent(name)}/final-export/${id}`, { data: { reason } }); await fetchFinalExports(name); return true }
    catch (e: any) {
      error.value = e?.response?.status === 403 ? 'Löschen nur für Administratoren.' : (e?.response?.data?.error || 'Löschen fehlgeschlagen')
      return false
    }
  }

  // ── Befangenheits-Check ────────────────────────────────
  const befangenheitsCheck = async (kunde: string, system = '', parteien: string[] = [], svUser = '') => {
    try {
      const res = await apiClient.post('/gutachten/befangenheits-check', { kunde, system, partei_namen: parteien, sv_user: svUser })
      return res.data
    } catch (e) { _err(e); return null }
  }

  // ── Beweisfragen / Befunde / Beurteilungen / Assets ────
  const _list = async (key: string, name: string, target: any) => {
    try { target.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}/${key}`)).data?.[key] || [] }
    catch (e) { _err(e) }
  }
  const fetchBeweisfragen = (n: string) => _list('beweisfragen', n, beweisfragen)
  const fetchBefunde = (n: string) => _list('befunde', n, befunde)
  const fetchBeurteilungen = (n: string) => _list('beurteilungen', n, beurteilungen)
  const fetchAssets = (n: string) => _list('assets', n, assets)
  const fetchVerfahren = async (n: string) => {
    try { verfahrensereignisse.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/verfahren`)).data?.ereignisse || [] }
    catch (e) { _err(e) }
  }

  const saveBeweisfrage = async (n: string, data: any) => {
    try { await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(n)}/beweisfragen`, data); await fetchBeweisfragen(n); return true }
    catch (e) { _err(e); return false }
  }
  const saveBefund = async (n: string, data: any) => {
    try { await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(n)}/befunde`, data); await fetchBefunde(n); return true }
    catch (e) { _err(e); return false }
  }
  const saveBeurteilung = async (n: string, data: any) => {
    try { await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(n)}/beurteilungen`, data); await fetchBeurteilungen(n); return true }
    catch (e) { _err(e); return false }
  }
  const saveAsset = async (n: string, data: any) => {
    try { await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(n)}/assets`, data); await fetchAssets(n); return true }
    catch (e) { _err(e); return false }
  }
  const saveVerfahren = async (n: string, data: any) => {
    try { await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(n)}/verfahren`, data); await fetchVerfahren(n); return true }
    catch (e) { _err(e); return false }
  }
  const reorderVerfahren = async (n: string, orderedIds: number[]) => {  // #979
    try { await apiClient.put(`/gutachten/gerichts/${encodeURIComponent(n)}/verfahren/reorder`, { ordered_ids: orderedIds }); await fetchVerfahren(n); return true }
    catch (e) { _err(e); return false }
  }

  const deleteBeweisfrage = async (id: number, n: string) => {
    try { await apiClient.delete(`/gutachten/gerichts/beweisfragen/${id}`); await fetchBeweisfragen(n); return true }
    catch (e) { _err(e); return false }
  }
  const deleteBefund = async (id: number, n: string) => {
    try { await apiClient.delete(`/gutachten/gerichts/befunde/${id}`); await fetchBefunde(n); return true }
    catch (e) { _err(e); return false }
  }
  const deleteBeurteilung = async (id: number, n: string) => {
    try { await apiClient.delete(`/gutachten/gerichts/beurteilungen/${id}`); await fetchBeurteilungen(n); return true }
    catch (e) { _err(e); return false }
  }
  const deleteAsset = async (id: number, n: string) => {
    try { await apiClient.delete(`/gutachten/gerichts/assets/${id}`); await fetchAssets(n); return true }
    catch (e) { _err(e); return false }
  }

  // ── SHA-256 Upload ─────────────────────────────────────
  const uploadAndHash = async (file: File): Promise<{sha256: string, size_bytes: number} | null> => {
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await apiClient.post('/gutachten/gerichts/sha256', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      return res.data
    } catch (e) { _err(e); return null }
  }

  // ── Normen + Werkzeuge ─────────────────────────────────
  const fetchNormen = async () => {
    try { normen.value = (await apiClient.get('/gutachten/normen')).data?.normen || [] }
    catch (e) { _err(e) }
  }
  const fetchWerkzeuge = async () => {
    try { werkzeuge.value = (await apiClient.get('/gutachten/werkzeuge')).data?.werkzeuge || [] }
    catch (e) { _err(e) }
  }
  const saveWerkzeug = async (data: any) => {
    try { await apiClient.post('/gutachten/werkzeuge', data); await fetchWerkzeuge(); return true }
    catch (e) { _err(e); return false }
  }

  // ── Wizards ────────────────────────────────────────────
  const selbstcheckFragen = ref<any[]>([])
  const fetchSelbstcheckFragen = async () => {
    try { selbstcheckFragen.value = (await apiClient.get('/gutachten/gerichts/wizards/selbstcheck-fragen')).data?.fragen || [] }
    catch (e) { _err(e) }
  }
  const runSelbstcheck = async (name: string, antworten: any, svUser = '') => {
    try { return (await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(name)}/wizards/selbstcheck`, { antworten, sv_user: svUser })).data }
    catch (e) { _err(e); return null }
  }
  const validateBefundText = async (text: string) => {
    try { return (await apiClient.post('/gutachten/gerichts/wizards/befund-validate', { text })).data }
    catch (e) { _err(e); return null }
  }
  const beurteilungPrompt = async (name: string, normId: string, subId: string | null, befundIds: number[] = []) => {
    try { return (await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(name)}/wizards/beurteilung/prompt`, { norm_id: normId, sub_id: subId, befund_ids: befundIds })).data?.prompt || '' }
    catch (e) { _err(e); return '' }
  }
  const beurteilungParse = async (name: string, response: string, normId: string, subId: string | null) => {
    try { return (await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(name)}/wizards/beurteilung/parse`, { response, norm_id: normId, sub_id: subId })).data }
    catch (e) { _err(e); return null }
  }

  // ── Validator ──────────────────────────────────────────
  const runSchlussValidator = async (name: string) => {
    try {
      const res = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}/wizards/schluss-validator`)).data
      validatorErrors.value = res.errors || []
      validatorWarnings.value = res.sprach_warnings || []
      return res
    } catch (e) { _err(e); return null }
  }

  // ── DOCX + Archiv ──────────────────────────────────────
  const downloadDocx = async (name: string, includeAnhang = true, templateId: number | null = null,
                              opts: { methodeWerkzeug?: boolean; beurteilungSubheadings?: boolean; verfahrenDatum?: boolean } = {}) => {
    try {
      const params = new URLSearchParams()
      if (!includeAnhang) params.set('include_anhang', 'false')
      if (opts.methodeWerkzeug === false) params.set('include_methode_werkzeug', 'false')
      if (opts.beurteilungSubheadings === false) params.set('include_beurteilung_subheadings', 'false')
      if (opts.verfahrenDatum === false) params.set('include_verfahren_datum', 'false')
      if (templateId) params.set('template_id', String(templateId))
      const q = params.toString() ? `?${params.toString()}` : ''
      const res = await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}/docx${q}`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `Gerichtsgutachten_${name}${includeAnhang ? '' : '_ohne-anhang'}.docx`
      a.click()
      URL.revokeObjectURL(url)
      return true
    } catch (e) { _err(e); return false }
  }
  const downloadArchiv = async (name: string) => {
    try {
      const res = await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}/archiv.zip`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `Archiv_${name}.zip`
      a.click()
      URL.revokeObjectURL(url)
      return true
    } catch (e) { _err(e); return false }
  }

  // ── Symmetrie + Non-liquet ─────────────────────────────
  const symmetrieCheck = async (name: string) => {
    try { return (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}/symmetrie-check`)).data }
    catch (e) { _err(e); return null }
  }

  // ── Honorar ────────────────────────────────────────────
  const honorarEintraege = ref<any[]>([])
  const honorarSummary = ref<any>(null)
  const fetchHonorar = async (name: string) => {
    try {
      honorarEintraege.value = (await apiClient.get(`/gutachten/honorar/eintraege?projekt_typ=gerichts&projekt_name=${encodeURIComponent(name)}`)).data?.eintraege || []
      honorarSummary.value = (await apiClient.get(`/gutachten/honorar/summary?projekt_typ=gerichts&projekt_name=${encodeURIComponent(name)}`)).data
    } catch (e) { _err(e) }
  }
  const saveHonorarEintrag = async (data: any) => {
    try { await apiClient.post('/gutachten/honorar/eintraege', data); return true }
    catch (e) { _err(e); return false }
  }

  // ── G4 Forensik ────────────────────────────────────────
  const macbEintraege = ref<any[]>([])
  const volatilityChecklist = ref<any[]>([])
  const werkzeugValidator = ref<any>(null)

  const fetchMacb = async (n: string) => {
    try { macbEintraege.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/macb`)).data?.eintraege || [] }
    catch (e) { _err(e) }
  }
  const saveMacb = async (n: string, data: any) => {
    try { await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(n)}/macb`, data); await fetchMacb(n); return true }
    catch (e) { _err(e); return false }
  }
  const deleteMacb = async (id: number, n: string) => {
    try { await apiClient.delete(`/gutachten/gerichts/macb/${id}`); await fetchMacb(n); return true }
    catch (e) { _err(e); return false }
  }
  const fetchVolatility = async () => {
    try { volatilityChecklist.value = (await apiClient.get('/gutachten/gerichts/volatility-checklist')).data?.checklist || [] }
    catch (e) { _err(e) }
  }
  const runWerkzeugValidator = async (n: string) => {
    try { werkzeugValidator.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/werkzeug-validator`)).data; return werkzeugValidator.value }
    catch (e) { _err(e); return null }
  }
  const classifyLogFile = async (file: File) => {
    try {
      const fd = new FormData()
      fd.append('file', file)
      return (await apiClient.post('/gutachten/gerichts/log-classify', fd,
        { headers: { 'Content-Type': 'multipart/form-data' } })).data
    } catch (e) { _err(e); return null }
  }

  // ── G5 Peer-Review + Aufbewahrung ──────────────────────
  const peerReviews = ref<any[]>([])
  const aufbewahrung = ref<any>(null)
  const fetchPeerReviews = async (n: string) => {
    try { peerReviews.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/peer-review`)).data?.reviews || [] }
    catch (e) { _err(e) }
  }
  const requestPeerReview = async (n: string, reviewer: string) => {
    try { await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(n)}/peer-review/request`, { reviewer_name: reviewer }); await fetchPeerReviews(n); return true }
    catch (e) { _err(e); return false }
  }
  const addPeerKommentar = async (rid: number, n: string, kapitel: string, text: string, author: string) => {
    try { await apiClient.post(`/gutachten/gerichts/peer-review/${rid}/kommentar`, { kapitel, text, author }); await fetchPeerReviews(n); return true }
    catch (e) { _err(e); return false }
  }
  const closePeerReview = async (rid: number, n: string) => {
    try { await apiClient.post(`/gutachten/gerichts/peer-review/${rid}/close`); await fetchPeerReviews(n); return true }
    catch (e) { _err(e); return false }
  }
  const setAufbewahrung = async (n: string, jahre = 10) => {
    try { return (await apiClient.post(`/gutachten/gerichts/${encodeURIComponent(n)}/aufbewahrung`, { jahre })).data }
    catch (e) { _err(e); return null }
  }
  const fetchAufbewahrung = async (n: string) => {
    try { aufbewahrung.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/aufbewahrung`)).data }
    catch (e) { aufbewahrung.value = null }
  }
  const fetchPdfHash = async (n: string) => {
    try { return (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/pdf/sha256`)).data }
    catch (e) { _err(e); return null }
  }

  // ── G6 Hypothesen + Drittgutachter + Anonymized ────────
  const hypothesen = ref<any[]>([])
  const fetchHypothesen = async (n: string) => {
    try { hypothesen.value = (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/hypothesen`)).data?.hypothesen || [] }
    catch (e) { _err(e) }
  }
  const saveHypothese = async (data: any, n: string) => {
    try { await apiClient.post('/gutachten/gerichts/hypothesen', data); await fetchHypothesen(n); return true }
    catch (e) { _err(e); return false }
  }
  const updateHypothese = async (hid: number, n: string, status: string, begruendung: string) => {
    try { await apiClient.put(`/gutachten/gerichts/hypothesen/${hid}`, { status, begruendung }); await fetchHypothesen(n); return true }
    catch (e) { _err(e); return false }
  }
  const deleteHypothese = async (hid: number, n: string) => {
    try { await apiClient.delete(`/gutachten/gerichts/hypothesen/${hid}`); await fetchHypothesen(n); return true }
    catch (e) { _err(e); return false }
  }
  const drittgutachterPrompt = async (befundId: number) => {
    try { return (await apiClient.post(`/gutachten/gerichts/befunde/${befundId}/drittgutachter/prompt`)).data?.prompt || '' }
    catch (e) { _err(e); return '' }
  }
  const drittgutachterAudit = async (data: any) => {
    try { return (await apiClient.post('/gutachten/gerichts/drittgutachter/audit', data)).data }
    catch (e) { _err(e); return null }
  }
  const crossRefCheck = async (n: string) => {
    try { return (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/cross-ref-check`)).data }
    catch (e) { _err(e); return null }
  }
  const fetchAnonymized = async (n: string) => {
    try { return (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(n)}/anonymized`)).data }
    catch (e) { _err(e); return null }
  }

  // ── BISG-Hilfen (#671) ─────────────────────────────────
  const fetchHelp = async (key: string) => {
    try { return (await apiClient.get(`/gutachten/help/${encodeURIComponent(key)}`)).data }
    catch (e) { return null }
  }

  // ── #955 Stammdaten: Gutachter + Hilfspersonen ───────────
  const gutachter = ref<any[]>([])
  const hilfspersonen = ref<any[]>([])
  const templates = ref<any[]>([])
  const fetchGutachter = async () => {
    try { gutachter.value = (await apiClient.get('/gutachten/gutachter')).data?.gutachter || [] }
    catch (e) { _err(e) }
  }
  const saveGutachter = async (data: any) => {
    try {
      if (data.id) await apiClient.put(`/gutachten/gutachter/${data.id}`, data)
      else await apiClient.post('/gutachten/gutachter', data)
      await fetchGutachter(); return true
    } catch (e) { _err(e); return false }
  }
  const deleteGutachter = async (id: number) => {
    try { await apiClient.delete(`/gutachten/gutachter/${id}`); await fetchGutachter(); return true }
    catch (e) { _err(e); return false }
  }
  const fetchHilfspersonen = async () => {
    try { hilfspersonen.value = (await apiClient.get('/gutachten/hilfspersonen')).data?.hilfspersonen || [] }
    catch (e) { _err(e) }
  }
  const saveHilfsperson = async (data: any) => {
    try {
      if (data.id) await apiClient.put(`/gutachten/hilfspersonen/${data.id}`, data)
      else await apiClient.post('/gutachten/hilfspersonen', data)
      await fetchHilfspersonen(); return true
    } catch (e) { _err(e); return false }
  }
  const deleteHilfsperson = async (id: number) => {
    try { await apiClient.delete(`/gutachten/hilfspersonen/${id}`); await fetchHilfspersonen(); return true }
    catch (e) { _err(e); return false }
  }
  const fetchProjektHilfspersonen = async (name: string) => {
    try { return (await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(name)}/hilfspersonen`)).data?.hilfspersonen || [] }
    catch (e) { _err(e); return [] }
  }
  const setProjektHilfspersonen = async (name: string, entries: any[]) => {
    try { await apiClient.put(`/gutachten/gerichts/${encodeURIComponent(name)}/hilfspersonen`, { hilfspersonen: entries }); return true }
    catch (e) { _err(e); return false }
  }

  // ── #957 Custom-Vorlagen ─────────────────────────────────
  const fetchTemplates = async () => {
    try { templates.value = (await apiClient.get('/gutachten/templates')).data?.templates || [] }
    catch (e) { _err(e) }
  }
  const uploadTemplate = async (file: File, name: string, art = 'beide') => {
    try {
      const fd = new FormData()
      fd.append('file', file); fd.append('name', name); fd.append('gutachten_art', art)
      const res = await apiClient.post('/gutachten/templates', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      await fetchTemplates(); return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Upload fehlgeschlagen'
      return null
    }
  }
  const setDefaultTemplate = async (id: number, art = 'beide') => {
    try { await apiClient.post(`/gutachten/templates/${id}/default`, { gutachten_art: art }); await fetchTemplates(); return true }
    catch (e) { _err(e); return false }
  }
  const fetchTemplateDetail = async (id: number) => {
    try { return (await apiClient.get(`/gutachten/templates/${id}`)).data }
    catch (e) { _err(e); return null }
  }
  const fetchTemplateSchema = async () => {
    try { return (await apiClient.get('/gutachten/templates/schema')).data?.variables || [] }
    catch (e) { _err(e); return [] }
  }
  const saveTemplateMapping = async (id: number, mapping: Record<string, string>) => {
    try { await apiClient.put(`/gutachten/templates/${id}/mapping`, { mapping }); return true }
    catch (e) { _err(e); return false }
  }
  const deleteTemplate = async (id: number) => {
    try { await apiClient.delete(`/gutachten/templates/${id}`); await fetchTemplates(); return true }
    catch (e) { _err(e); return false }
  }

  return {
    gutachter, hilfspersonen, templates,
    fetchGutachter, saveGutachter, deleteGutachter,
    fetchHilfspersonen, saveHilfsperson, deleteHilfsperson,
    fetchProjektHilfspersonen, setProjektHilfspersonen,
    fetchTemplates, uploadTemplate, setDefaultTemplate, deleteTemplate,
    fetchTemplateDetail, fetchTemplateSchema, saveTemplateMapping,
    finalExports, fetchFinalExports, uploadFinalExport, downloadFinalExport, deleteFinalExport,
    projekte, aktuell, beweisfragen, befunde, beurteilungen, assets, verfahrensereignisse,
    normen, werkzeuge, validatorErrors, validatorWarnings, loading, error,
    selbstcheckFragen, honorarEintraege, honorarSummary,
    macbEintraege, volatilityChecklist, werkzeugValidator,
    peerReviews, aufbewahrung, hypothesen,
    fetchProjekte, fetchProjekt, createProjekt, updateProjekt, deleteProjekt,
    befangenheitsCheck,
    fetchBeweisfragen, fetchBefunde, fetchBeurteilungen, fetchAssets, fetchVerfahren,
    saveBeweisfrage, saveBefund, saveBeurteilung, saveAsset, saveVerfahren, reorderVerfahren,
    deleteBeweisfrage, deleteBefund, deleteBeurteilung, deleteAsset,
    uploadAndHash,
    fetchNormen, fetchWerkzeuge, saveWerkzeug,
    fetchSelbstcheckFragen, runSelbstcheck, validateBefundText,
    beurteilungPrompt, beurteilungParse,
    runSchlussValidator, downloadDocx, downloadArchiv, symmetrieCheck,
    fetchHonorar, saveHonorarEintrag,
    // G4
    fetchMacb, saveMacb, deleteMacb, fetchVolatility, runWerkzeugValidator, classifyLogFile,
    // G5
    fetchPeerReviews, requestPeerReview, addPeerKommentar, closePeerReview,
    setAufbewahrung, fetchAufbewahrung, fetchPdfHash,
    // G6
    fetchHypothesen, saveHypothese, updateHypothese, deleteHypothese,
    drittgutachterPrompt, drittgutachterAudit, crossRefCheck, fetchAnonymized,
    // #671 Hilfen
    fetchHelp,
  }
})
