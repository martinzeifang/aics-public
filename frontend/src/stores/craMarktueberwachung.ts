import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Blueprint unter '/api/cra-marktueberwachung'; apiClient.baseURL = '/api'.
const BASE = '/cra-marktueberwachung'

export interface MarktaufsichtUnterlage {
  titel: string
  ref: string
  uebergeben_am: string
}

/** Fristenlauf einer Behördenfrist (cra/fristenuhr.py). `verstrichen` sagt nur,
 *  dass das Datum vorbei ist — ob das ein Versäumnis ist, sagt `frist_versaeumt`
 *  (nur bei noch laufendem Vorgang). */
export interface Fristenstand {
  datum: string | null
  tage_verbleibend: number | null
  ampel: 'gruen' | 'gelb' | 'rot' | 'verstrichen' | 'unbekannt'
  verstrichen: boolean
}

export interface Marktaufsichtsvorgang {
  id: number
  projekt_name: string
  vorgangsart: string
  behoerde_name: string
  behoerde_land: string
  aktenzeichen: string
  eingang_am: string | null
  frist_am: string | null
  gegenstand: string
  verlangen: string
  betroffene_versionen: string
  status: string
  beantwortet_am: string | null
  unterlagen: MarktaufsichtUnterlage[]
  ergebnis: string
  notizen: string
  audit_trail: Array<{ event: string; ts: string; [k: string]: any }>
  frist: Fristenstand
  frist_versaeumt: boolean
}

export const useCraMarktueberwachungStore = defineStore('craMarktueberwachung', () => {
  const vorgaenge = ref<Marktaufsichtsvorgang[]>([])
  const uebersicht = ref<any>({ gesamt: 0, laufend: 0, versaeumt: 0 })
  const vorgangsarten = ref<string[]>([])
  const status = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const _pj = (projekt: string, suffix = '') =>
    `${BASE}/projekte/${encodeURIComponent(projekt)}/vorgaenge${suffix}`

  async function fetchConstants() {
    try {
      const { data } = await apiClient.get(`${BASE}/constants`)
      vorgangsarten.value = data.vorgangsarten || []
      status.value = data.status || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden'
    }
  }

  async function fetchVorgaenge(projekt: string) {
    loading.value = true
    error.value = null
    try {
      const { data } = await apiClient.get(_pj(projekt))
      vorgaenge.value = data || []
      const u = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/uebersicht`)
      uebersicht.value = u.data || {}
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Vorgänge konnten nicht geladen werden'
    } finally {
      loading.value = false
    }
  }

  async function createVorgang(projekt: string, payload: Partial<Marktaufsichtsvorgang>) {
    error.value = null
    try {
      const { data } = await apiClient.post(_pj(projekt), payload)
      await fetchVorgaenge(projekt)
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Anlegen fehlgeschlagen'
      return null
    }
  }

  async function setStatus(projekt: string, id: number, neu: string) {
    error.value = null
    try {
      await apiClient.post(_pj(projekt, `/${id}/status`), { status: neu })
      await fetchVorgaenge(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Statuswechsel fehlgeschlagen'
      return false
    }
  }

  async function addUnterlage(projekt: string, id: number, titel: string, ref_ = '') {
    error.value = null
    try {
      await apiClient.post(_pj(projekt, `/${id}/unterlagen`), { titel, ref: ref_ })
      await fetchVorgaenge(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Unterlage konnte nicht erfasst werden'
      return false
    }
  }

  async function deleteVorgang(projekt: string, id: number) {
    error.value = null
    try {
      await apiClient.delete(_pj(projekt, `/${id}`))
      await fetchVorgaenge(projekt)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen'
      return false
    }
  }

  return {
    vorgaenge, uebersicht, vorgangsarten, status, loading, error,
    fetchConstants, fetchVorgaenge, createVorgang, setStatus, addUnterlage,
    deleteVorgang,
  }
})
