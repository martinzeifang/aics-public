import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Blueprint unter '/api/cra-meldung'; apiClient.baseURL = '/api'.
const BASE = '/cra-meldung'

export interface MeldungDeadlineStage {
  key: string
  label: string
  // null, solange der Fristbeginn nicht bestimmt ist (#1760).
  due_at: string | null
  hours_left: number | null
  ampel: 'gruen' | 'gelb' | 'rot' | 'overdue' | 'unbestimmt' | 'erfuellt' | 'erfuellt_verspaetet'
  overdue: boolean
  unbestimmt?: boolean
  hinweis?: string
  erfuellt_am?: string | null
  verspaetet?: boolean
}

export interface MeldungAbschlussfrist {
  anker_feld: string
  anker_label: string
  fundstelle: string
  dauer: string
  anker_am: string | null
  beginn: string | null
  bestimmt: boolean
  faellig_am?: string
}

export interface MeldungDeadlines {
  stages: MeldungDeadlineStage[]
  next_due: string | null
  any_overdue: boolean
  abschlussfrist?: MeldungAbschlussfrist
}

/** Empfänger einer Stufe: CSIRT-Koordinator + ENISA (Art. 14). */
export interface MeldungKanal {
  mitgliedstaat?: string
  stelle?: string
  referenz?: string
  gemeldet_am?: string
  eingang_bestaetigt_am?: string
  bemerkung?: string
}

export type MeldungEmpfaenger = Record<string, Record<string, MeldungKanal>>

export interface MeldungLuecke {
  bereich: string
  label: string
  text: string
  schwere: 'pflicht' | 'offen'
}

export interface MeldungNachweis {
  vollstaendig: boolean
  belegt: boolean
  /**
   * Wurde überhaupt schon eine Stufe abgegeben? (#1760)
   *
   * `nachweis_status` in `cra/meldung_db.py` liefert das Feld; hier fehlte
   * es, obwohl `MeldungPanel` genau darauf den Unterschied zwischen
   * „vollständig belegt" und „noch nichts gemeldet" stützt (#1858).
   */
  gemeldet: boolean
  luecken: MeldungLuecke[]
  pflicht_offen: number
  offen: number
}

export interface Meldung {
  id: number
  projekt_name: string
  vuln_id: number | null
  typ: string
  titel: string
  status: string
  erkannt_am: string
  betroffene_ms: string
  vermutete_ursache: string
  mitigation: string
  beschreibung: string
  early_warning_gemeldet_am: string | null
  notification_gemeldet_am: string | null
  final_report_gemeldet_am: string | null
  massnahme_verfuegbar_ab: string | null
  advisory: Record<string, any>
  empfaenger: MeldungEmpfaenger
  deadlines: MeldungDeadlines | null
  nachweis: MeldungNachweis | null
}

export const useCraMeldungStore = defineStore('craMeldung', () => {
  const meldungen = ref<Meldung[]>([])
  const typen = ref<string[]>([])
  const status = ref<string[]>([])
  const stufen = ref<string[]>([])
  const mitgliedstaaten = ref<Record<string, string>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** 400-Antwort mit Feldliste lesbar machen (#1760). */
  function meldeFehler(e: any, fallback: string) {
    const d = e?.response?.data || {}
    const felder: string[] = d.fehlende_felder || []
    error.value = felder.length
      ? `${d.error || fallback} — fehlt: ${felder.join(', ')}`
      : (d.error || fallback)
    return false
  }

  async function fetchConstants() {
    try {
      const { data } = await apiClient.get(`${BASE}/constants`)
      typen.value = data.typen || []
      status.value = data.status || []
      stufen.value = data.stufen || []
      mitgliedstaaten.value = data.mitgliedstaaten || {}
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden'
    }
  }

  async function fetchMeldungen(projekt: string) {
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen`)
      meldungen.value = data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Meldungen konnten nicht geladen werden'
    } finally {
      loading.value = false
    }
  }

  async function createMeldung(projekt: string, payload: Partial<Meldung>) {
    const { data } = await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen`, payload)
    await fetchMeldungen(projekt)
    return data
  }

  /** Stufe als gemeldet verbuchen. Ohne Adressat + Referenz lehnt der Server ab. */
  async function setStufe(projekt: string, id: number, newStatus: string,
                          empfaenger?: Record<string, MeldungKanal>) {
    error.value = null
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}/stufe`,
        { status: newStatus, empfaenger })
    } catch (e: any) {
      return meldeFehler(e, 'Stufe konnte nicht gesetzt werden')
    }
    await fetchMeldungen(projekt)
    return true
  }

  /** Empfänger/Referenzen einer Stufe erfassen oder ergänzen. */
  async function saveEmpfaenger(projekt: string, id: number, stufe: string,
                                daten: Record<string, MeldungKanal>) {
    error.value = null
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}/empfaenger`,
        { stufe, ...daten })
    } catch (e: any) {
      return meldeFehler(e, 'Empfänger konnten nicht gespeichert werden')
    }
    await fetchMeldungen(projekt)
    return true
  }

  async function updateMeldung(projekt: string, id: number, payload: Record<string, any>) {
    error.value = null
    try {
      await apiClient.put(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}`, payload)
    } catch (e: any) {
      return meldeFehler(e, 'Meldung konnte nicht gespeichert werden')
    }
    await fetchMeldungen(projekt)
    return true
  }

  async function saveAdvisory(projekt: string, id: number, advisory: Record<string, any>) {
    error.value = null
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}/nutzer-advisory`,
        advisory)
    } catch (e: any) {
      return meldeFehler(e, 'Nutzerunterrichtung konnte nicht gespeichert werden')
    }
    await fetchMeldungen(projekt)
    return true
  }

  async function deleteMeldung(projekt: string, id: number) {
    await apiClient.delete(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}`)
    await fetchMeldungen(projekt)
  }

  function exportUrl(projekt: string, id: number) {
    return `/api${BASE}/projekte/${encodeURIComponent(projekt)}/meldungen/${id}/export?format=json`
  }

  return {
    meldungen, typen, status, stufen, mitgliedstaaten, loading, error,
    fetchConstants, fetchMeldungen, createMeldung, setStufe, saveEmpfaenger,
    updateMeldung, saveAdvisory, deleteMeldung, exportUrl,
  }
})
