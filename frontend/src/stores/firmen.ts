import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'
import { fehlerText } from '../utils/fehler'
import { KI_LAUF_MS, OBJEKT_LAUF_MS, PROJEKT_LAUF_MS } from '../utils/langlauf'

export interface Firma {
  id: string
  name: string
  company: string
  unternehmen?: string
  advisor: string
  berater?: string
  description: string
  beschreibung?: string
  // #1892: Anschrift und gesetzlicher Vertreter des Mandanten. Sie speisen
  // jede Konformitätserklärung und jeden Briefkopf; `anschrift_text` kommt
  // fertig formatiert vom Server, damit nicht jedes Modul eigene
  // Zeilenumbrüche baut.
  rechtsform?: string
  anschrift?: string
  plz?: string
  ort?: string
  land?: string
  vertreter_name?: string
  vertreter_funktion?: string
  anschrift_text?: string
  // #1954: Inhaltssprache des Mandanten. `sprache` ist der rohe Wert
  // ('' = nie entschieden), `sprache_wirksam` der, der tatsächlich gilt --
  // die Maske muss den Unterschied zeigen können.
  sprache?: string
  sprache_wirksam?: string
  frameworks: string[]
  pruefungsfokus: string
  rb_framework: string
  produkt: string
  produktklasse: string
  modules: {
    risikobewertung: boolean
    gutachten: boolean
    cra: boolean
    dsgvo: boolean
    nis2: boolean
    ai_act: boolean
    wiba: boolean
    // #1713: eigenes Modul seit v7.4.0 (Spalte `module_compliance_audit`,
    // siehe `shared/licensing/modules.FIRMEN_MODULE_COLUMNS`). Fehlte hier,
    // obwohl `FirmenView` die Kachel dafür baut (#1858).
    compliance_audit: boolean
  }
  created_at?: string
  updated_at?: string
}

/**
 * #1861: Ein Zuordnungs-Vorschlag — noch **keine** Freigabe.
 *
 * Er liegt in `evidence_mappings_vorschlag`, nicht in
 * `evidence_mappings_approved`: Erst die Entscheidung eines Menschen macht aus
 * der Vermutung einen Beleg, der dann in jede KI-Bewertung einfließt (#1483).
 */
export interface EvidenceVorschlag {
  id: string
  doc_id: string
  modul: string
  requirement_id: string
  claim: string
  citations: { doc_id: string; chunk: number }[]
  confidence: number
  rationale: string
  provider: string
  erzeugt_am: number
  erzeugt_von: string
}

/** Was eine Freigabe in einem Modul abschließen kann (#1991). */
export interface AbschlussOption {
  art: 'score' | 'status'
  vorgabe: string
  objekt: string
  antworten: { wert: string; label: string }[]
  projekte: string[]
}

/** Was der Abschluss tatsächlich bewirkt hat (#1991). */
export interface AbschlussBericht {
  gesetzt: boolean
  grund?: string
  projekte?: string[]
  modul?: string
  projekt?: string
  objekt_id?: string
  antwort?: string
  vorher?: string
  ersetzt?: boolean
}

/** Eine von einem Menschen freigegebene Anforderung→Nachweis-Zuordnung (#1988). */
export interface EvidenceFreigabe {
  requirement_id: string
  claim: string
  citations: { doc_id: string; chunk: number }[]
  confidence: number
  rationale: string
  approved_by: string
  approved_at: number
  dokumente: string[]
}

export interface Produkt {
  id: number
  name: string
  beschreibung?: string
  produktklasse: string
  is_default: number | boolean
}

/**
 * Offene CRA-Release-Vorgänge eines Mandanten (#1749).
 *
 * Quer-Sicht für CRA as a Service. Die Zahlen kommen aus
 * `GET /firmen/releases-offen` — einer Antwort für alle Mandanten, damit die
 * Mandanten-Übersicht nicht je Zeile nachfragt. Serverseitig wird dafür kein
 * Gate gerechnet, nur Status und eingefrorene Ampel gezählt.
 */
export interface ReleasesOffen {
  gesamt: number
  offen: number
  in_pruefung: number
  rot: number
}

export interface DeletedFirma {
  name: string
  unternehmen: string
  deleted_at: string
}

export interface Constants {
  rb_frameworks: string[]
  gutachten_frameworks: string[]
  produktklassen: { key: string; label: string }[]
  // #1954: Die Sprachen kommen vom Server (`shared/sprache.py`), nicht als
  // zweite Liste im Frontend -- dieselbe Lehre wie `license_effective_modules`
  // in #1703/S9: Das Backend ist die einzige Quelle, das Frontend bekommt eine
  // fertige Entscheidung und baut die Regel nicht nach.
  sprachen?: { code: string; name: string }[]
  sprache_standard?: string
}

export const useFirmenStore = defineStore('firmen', () => {
  const firmen = ref<Firma[]>([])
  const selectedFirma = ref<Firma | null>(null)
  const deletedFirmen = ref<DeletedFirma[]>([])
  const produkte = ref<Produkt[]>([])
  const constants = ref<Constants | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ---- Firmen ----

  const fetchFirmen = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get('/firmen')
      // #1709: Der Endpoint liefert normalerweise eine Liste, bei gesetztem
      // `limit` aber `{ items, total }`. Beides tolerieren.
      const data = response.data
      firmen.value = Array.isArray(data) ? data : (data?.items ?? [])
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
    } finally {
      loading.value = false
    }
  }

  /**
   * #1749: Release-Kennzahlen aller Mandanten in einem Request.
   *
   * Bewusst kein Fehler-State: Die Spalte „Releases offen" ist eine Zusatz-
   * information in einer Liste, die ohne sie vollständig funktioniert. Ein
   * fehlgeschlagener Abruf darf die Mandanten-Übersicht nicht rot färben.
   */
  const releasesOffen = ref<Record<string, ReleasesOffen>>({})
  const releasesGeladen = ref(false)

  const fetchReleasesOffen = async (force = false) => {
    if (releasesGeladen.value && !force) return releasesOffen.value
    try {
      const response = await apiClient.get('/firmen/releases-offen')
      releasesOffen.value = response.data?.firmen ?? {}
    } catch {
      releasesOffen.value = {}
    } finally {
      releasesGeladen.value = true
    }
    return releasesOffen.value
  }

  const fetchFirma = async (name: string): Promise<Firma | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get(`/firmen/${encodeURIComponent(name)}`)
      return response.data
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
      return null
    } finally {
      loading.value = false
    }
  }

  const createFirma = async (data: Partial<Firma> & { name: string }): Promise<Firma | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.post('/firmen', data)
      const newFirma = response.data
      firmen.value.push(newFirma)
      return newFirma
    } catch (err: any) {
      error.value = fehlerText(err, 'anlegen')
      return null
    } finally {
      loading.value = false
    }
  }

  const updateFirma = async (name: string, data: Partial<Firma>): Promise<Firma | null> => {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.put(`/firmen/${encodeURIComponent(name)}`, data)
      const updated = response.data
      const idx = firmen.value.findIndex(k => k.name === name)
      if (idx >= 0) firmen.value[idx] = updated
      if (selectedFirma.value?.name === name) selectedFirma.value = updated
      return updated
    } catch (err: any) {
      error.value = fehlerText(err, 'aktualisieren')
      return null
    } finally {
      loading.value = false
    }
  }

  const deleteFirma = async (name: string): Promise<boolean> => {
    loading.value = true
    error.value = null
    try {
      await apiClient.delete(`/firmen/${encodeURIComponent(name)}`)
      firmen.value = firmen.value.filter(k => k.name !== name)
      if (selectedFirma.value?.name === name) selectedFirma.value = null
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'loeschen')
      return false
    } finally {
      loading.value = false
    }
  }

  const restoreFirma = async (name: string): Promise<boolean> => {
    try {
      const response = await apiClient.post(`/firmen/${encodeURIComponent(name)}/restore`)
      firmen.value.push(response.data)
      deletedFirmen.value = deletedFirmen.value.filter(k => k.name !== name)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'aktualisieren')
      return false
    }
  }

  const hardDeleteFirma = async (name: string): Promise<boolean> => {
    try {
      await apiClient.delete(`/firmen/${encodeURIComponent(name)}/permanent`)
      deletedFirmen.value = deletedFirmen.value.filter(k => k.name !== name)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'loeschen')
      return false
    }
  }

  const fetchDeletedFirmen = async () => {
    try {
      const response = await apiClient.get('/firmen/deleted')
      deletedFirmen.value = response.data
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
    }
  }

  // ---- Produkte ----

  const fetchProdukte = async (firmaName: string) => {
    try {
      const response = await apiClient.get(`/firmen/${encodeURIComponent(firmaName)}/produkte`)
      produkte.value = response.data
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
    }
  }

  const createProdukt = async (firmaName: string, data: Partial<Produkt>) => {
    try {
      await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/produkte`, data)
      await fetchProdukte(firmaName)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'anlegen')
      return false
    }
  }

  const updateProdukt = async (firmaName: string, id: number, data: Partial<Produkt>) => {
    try {
      await apiClient.put(`/firmen/${encodeURIComponent(firmaName)}/produkte/${id}`, data)
      await fetchProdukte(firmaName)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'aktualisieren')
      return false
    }
  }

  const setDefaultProdukt = async (firmaName: string, id: number) => {
    try {
      await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/produkte/${id}/default`)
      await fetchProdukte(firmaName)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'aktualisieren')
      return false
    }
  }

  const deleteProdukt = async (firmaName: string, id: number) => {
    try {
      await apiClient.delete(`/firmen/${encodeURIComponent(firmaName)}/produkte/${id}`)
      await fetchProdukte(firmaName)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'loeschen')
      return false
    }
  }

  // ---- Evidence ----

  const evidence = ref<any[]>([])

  const fetchEvidence = async (firmaName: string) => {
    try {
      const response = await apiClient.get(`/firmen/${encodeURIComponent(firmaName)}/evidence`)
      evidence.value = response.data
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
    }
  }

  const uploadEvidenceFile = async (firmaName: string, file: File, docType: string = '', tags: string[] = []) => {
    const formData = new FormData()
    formData.append('file', file)
    if (docType) formData.append('doc_type', docType)
    if (tags.length) formData.append('tags', tags.join(','))
    try {
      await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/evidence/file`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await fetchEvidence(firmaName)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'hochladen')
      return false
    }
  }

  const addEvidenceUrl = async (firmaName: string, url: string, maxPages: number = 5, docType: string = 'web', tags: string[] = []) => {
    try {
      await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/evidence/url`, {
        url, max_pages: maxPages, doc_type: docType, tags,
      })
      await fetchEvidence(firmaName)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'auswerten')
      return false
    }
  }

  const extractEvidence = async (firmaName: string, docId: string) => {
    try {
      const response = await apiClient.post(`/firmen/${encodeURIComponent(firmaName)}/evidence/${docId}/extract`)
      return response.data
    } catch (err: any) {
      error.value = fehlerText(err, 'auswerten')
      return null
    }
  }

  // ── Nachweise erschließen (#1861) ──────────────────────────────────────
  // Der Server prüft die Vorschläge nach (erfundene Anforderungs-IDs und
  // erfundene Fundstellen werden verworfen) und gibt die Gründe zurück. Hier
  // wird nichts gerechnet — die Regel steht an einer Stelle (#1703/S9).

  /**
   * Volltext + Abschnitte nachziehen. Kein KI-Lauf, kostet nichts.
   *
   * Eigene Zeitgrenze trotzdem (#1978): Die Textextraktion eines umfangreichen
   * PDF ist nicht in 30 s zu garantieren, und der Ausgang wäre derselbe wie
   * beim Erschließungslauf — der Server schreibt die Abschnitte, der Browser
   * hat schon aufgegeben.
   */
  const evidenceAbschnitte = async (firmaName: string, docId: string) => {
    try {
      const res = await apiClient.post(
        `/firmen/${encodeURIComponent(firmaName)}/evidence/${docId}/abschnitte`,
        undefined, { timeout: OBJEKT_LAUF_MS })
      return res.data
    } catch (err: any) {
      error.value = fehlerText(err, 'auswerten')
      return null
    }
  }

  /**
   * Volltext + Abschnitte für **alle** Dokumente der Firma (Bestand).
   *
   * Hier läuft die Extraktion in einer Schleife über jedes Dokument — bei einem
   * gewachsenen Nachweisbestand ist das der längste Lauf dieser Maske (#1978).
   */
  const evidenceAbschnitteAlle = async (firmaName: string) => {
    try {
      const res = await apiClient.post(
        `/firmen/${encodeURIComponent(firmaName)}/evidence/abschnitte`,
        undefined, { timeout: PROJEKT_LAUF_MS })
      return res.data as { dokumente: number; ohne_text: string[] }
    } catch (err: any) {
      error.value = fehlerText(err, 'auswerten')
      return null
    }
  }

  /** Der Prompt zum Kopieren — der Copy/Paste-Weg bleibt erhalten. */
  const erschliessungPrompt = async (firmaName: string, docId: string, modul: string) => {
    const res = await apiClient.get(
      `/firmen/${encodeURIComponent(firmaName)}/evidence/${docId}/erschliessen/prompt`,
      { params: { modul } })
    return res.data as { prompt: string; modul: string }
  }

  /**
   * Direktlauf über die KI. `confirmed` ist Pflicht (#1519).
   *
   * Eigene Zeitgrenze (#1978): Der Lauf geht in Scheiben über den Katalog —
   * gemessen 114 s für ein Dokument gegen die 257 WiBA-Prüffragen. Mit der
   * Vorgabe des `apiClient` (30 s) gab der Browser auf, während der Server
   * weiterarbeitete und schrieb; die Maske meldete „fehlgeschlagen" für einen
   * Lauf, dessen 31 Vorschläge in der Datenbank standen.
   */
  const erschliessen = async (firmaName: string, docId: string, modul: string) => {
    const res = await apiClient.post(
      `/firmen/${encodeURIComponent(firmaName)}/evidence/${docId}/erschliessen`,
      { modul, confirmed: true }, { timeout: KI_LAUF_MS })
    return res.data as { vorschlaege: number; verworfen: string[]; provider: string; laeufe: number }
  }

  /** Eine von Hand eingefügte Antwort übernehmen — gleiche Prüfung wie oben. */
  const erschliessungImport = async (firmaName: string, docId: string,
                                     modul: string, response: string) => {
    const res = await apiClient.post(
      `/firmen/${encodeURIComponent(firmaName)}/evidence/${docId}/erschliessen/import`,
      { modul, response })
    return res.data as { vorschlaege: number; verworfen: string[] }
  }

  /**
   * Die freigegebenen Zuordnungen der Firma (#1988).
   *
   * Es gab sie nirgends zu sehen: Eine Freigabe verschwand aus dem
   * Erschließungs-Dialog und erschien in der ganzen Anwendung nicht wieder.
   */
  const fetchFreigegebene = async (firmaName: string) => {
    try {
      const res = await apiClient.get(
        `/firmen/${encodeURIComponent(firmaName)}/evidence/freigegeben`)
      return res.data as { items: EvidenceFreigabe[]; anzahl: number }
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
      return null
    }
  }

  /** Eine Freigabe zurückziehen — der Gegenweg, den es nicht gab (#1988). */
  const freigabeZurueckziehen = async (firmaName: string,
                                       requirement_id: string, claim: string) => {
    try {
      await apiClient.post(
        `/firmen/${encodeURIComponent(firmaName)}/evidence/freigegeben/zurueckziehen`,
        { requirement_id, claim })
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'entfernen')
      return false
    }
  }

  const fetchVorschlaege = async (firmaName: string, docId?: string) => {
    const res = await apiClient.get(
      `/firmen/${encodeURIComponent(firmaName)}/evidence/vorschlaege`,
      { params: docId ? { doc_id: docId } : {} })
    return (res.data?.items || []) as EvidenceVorschlag[]
  }

  /** Erst hier wird aus einer Vermutung ein Beleg. */
  /**
   * Einen Vorschlag freigeben. Liefert `neu`: ob daraus eine Zeile wurde (#1988).
   *
   * Der Schlüssel der Freigabe ist (Anforderung, Aussage) — ein gleichlautender
   * Beleg **ersetzt** die frühere Freigabe samt Urheber und Zeitpunkt. Auf
   * Produktiv standen deshalb 103 Freigaben im Revisionspfad und 91 Zeilen in
   * der Tabelle, und jede Antwort war 200.
   */
  const vorschlagFreigeben = async (firmaName: string, id: string,
                                    antwort = '', projekt = '') => {
    const res = await apiClient.post(
      `/firmen/${encodeURIComponent(firmaName)}/evidence/vorschlaege/${id}/freigeben`,
      { antwort, ...(projekt ? { projekt } : {}) })
    return {
      neu: res.data?.neu !== false,
      antwort: res.data?.antwort as AbschlussBericht | undefined,
    }
  }

  /**
   * Was eine Freigabe je Modul abschließen kann (#1991).
   *
   * Die Liste stellt der **Server** — welche Antworten ein Modul kennt, welche
   * Projekte der Firma dafür in Frage kommen, was vorgeschlagen wird. Im
   * Frontend nachgebaut wäre das die zweite Wahrheit (#1703/S9).
   */
  const abschlussOptionen = async (firmaName: string) => {
    try {
      const res = await apiClient.get(
        `/firmen/${encodeURIComponent(firmaName)}/evidence/abschluss-optionen`)
      return res.data?.module as Record<string, AbschlussOption> | undefined
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
      return undefined
    }
  }

  const vorschlagVerwerfen = async (firmaName: string, id: string) => {
    await apiClient.delete(
      `/firmen/${encodeURIComponent(firmaName)}/evidence/vorschlaege/${id}`)
    return true
  }

  const deleteEvidence = async (firmaName: string, docId: string) => {
    try {
      await apiClient.delete(`/firmen/${encodeURIComponent(firmaName)}/evidence/${docId}`)
      evidence.value = evidence.value.filter(e => e.id !== docId)
      return true
    } catch (err: any) {
      error.value = fehlerText(err, 'loeschen')
      return false
    }
  }

  // ---- Konstanten ----

  const fetchConstants = async () => {
    if (constants.value) return constants.value
    try {
      const response = await apiClient.get('/firmen/constants')
      constants.value = response.data
      return response.data
    } catch (err: any) {
      error.value = fehlerText(err, 'laden')
      return null
    }
  }

  // ---- Impressum-Parser ----

  const parseImpressum = async (url: string, maxPages: number = 5) => {
    try {
      const response = await apiClient.post('/firmen/parse-impressum', { url, max_pages: maxPages })
      return response.data
    } catch (err: any) {
      error.value = fehlerText(err, 'auswerten')
      return null
    }
  }

  return {
    firmen,
    selectedFirma,
    deletedFirmen,
    produkte,
    evidence,
    constants,
    loading,
    error,
    releasesOffen,
    releasesGeladen,
    fetchReleasesOffen,
    fetchFirmen,
    fetchFirma,
    createFirma,
    updateFirma,
    deleteFirma,
    restoreFirma,
    hardDeleteFirma,
    fetchDeletedFirmen,
    fetchProdukte,
    createProdukt,
    updateProdukt,
    setDefaultProdukt,
    deleteProdukt,
    fetchEvidence,
    uploadEvidenceFile,
    addEvidenceUrl,
    extractEvidence,
    evidenceAbschnitte,
    evidenceAbschnitteAlle,
    erschliessungPrompt,
    erschliessen,
    erschliessungImport,
    fetchFreigegebene,
    freigabeZurueckziehen,
    abschlussOptionen,
    fetchVorschlaege,
    vorschlagFreigeben,
    vorschlagVerwerfen,
    deleteEvidence,
    fetchConstants,
    parseImpressum,
  }
})
