import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

// Backend mountet das Blueprint unter url_prefix '/api/dsgvo-tom'.
// apiClient.baseURL ist '/api' -> Pfade hier ohne führendes '/api'.
const BASE = '/dsgvo-tom'

export interface TomMassnahme {
  id?: number
  projekt_name?: string
  ziel: string
  massnahme_key: string
  titel: string
  beschreibung: string
  status: number
  soll: number
  verantwortlich: string
  wirksamkeit_datum: string
  wirksamkeit_ergebnis: string
  vvt_ref: string
  // #1575: WiBA-Verknüpfung
  umsetzung?: string
  umsetzung_quelle?: string
  status_quelle?: string | null
  status_quelle_effektiv?: 'wiba' | 'manuell'
  wiba_verknuepft?: number
  created_at?: string
  updated_at?: string
}

export interface TomGruppe {
  ziel: string
  massnahmen: TomMassnahme[]
}

export interface KiVorschlag {
  ziel: string
  empfehlung: string
  prioritaet: string
}

// #1575: Ableitung je TOM aus den BSI-WiBA-Antworten der Firma
export interface WibaFrage { control_id: string; nr?: number; theme_key: string; frage: string; status: string; notiz: string }
export interface WibaTomItem {
  fragen: WibaFrage[]
  counts: Record<'ja' | 'nein' | 'offen' | 'nicht_relevant', number>
  in_scope: number
  status_abgeleitet: number | null
}
export interface WibaAbleitung {
  wiba_projekt: string | null
  explizit: boolean
  katalog_geladen: boolean
  kandidaten: { name: string; unternehmen: string }[]
  items: Record<string, WibaTomItem>
}

export const useDsgvoTomStore = defineStore('dsgvoTom', () => {
  const projektName = ref<string>('')
  const items = ref<TomMassnahme[]>([])
  const gruppen = ref<TomGruppe[]>([])
  const ziele = ref<string[]>([])
  const loading = ref(false)
  const error = ref('')

  const gesamt = computed(() => items.value.length)
  const bewertet = computed(() => items.value.filter((m) => (m.status || 0) > 0).length)
  const avg = computed(() => {
    const ev = items.value.filter((m) => (m.status || 0) > 0)
    if (!ev.length) return 0
    return ev.reduce((s, m) => s + (m.status || 0), 0) / ev.length
  })

  async function fetchZiele() {
    try {
      const res = await apiClient.get(`${BASE}/ziele`)
      ziele.value = res.data.ziele || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Ziele konnten nicht geladen werden.'
    }
  }

  async function fetchMassnahmen(projekt: string) {
    if (!projekt) return
    projektName.value = projekt
    loading.value = true
    error.value = ''
    try {
      const res = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/massnahmen`)
      items.value = res.data.items || []
      gruppen.value = res.data.gruppen || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Maßnahmen konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function seed(force = false): Promise<number | null> {
    if (!projektName.value) return null
    error.value = ''
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projektName.value)}/seed`,
        { force },
      )
      await fetchMassnahmen(projektName.value)
      return res.data.inserted ?? 0
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Seed fehlgeschlagen.'
      return null
    }
  }

  async function saveMassnahme(data: Partial<TomMassnahme>): Promise<boolean> {
    if (!projektName.value) return false
    error.value = ''
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projektName.value)}/massnahmen`,
        data,
      )
      await fetchMassnahmen(projektName.value)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function deleteMassnahme(massnahmeKey: string): Promise<boolean> {
    if (!projektName.value) return false
    error.value = ''
    try {
      await apiClient.delete(
        `${BASE}/projekte/${encodeURIComponent(projektName.value)}/massnahmen/${encodeURIComponent(massnahmeKey)}`,
      )
      await fetchMassnahmen(projektName.value)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function saveWirksamkeit(
    massnahmeKey: string,
    payload: { datum: string; ergebnis: string; status?: number },
  ): Promise<boolean> {
    if (!projektName.value) return false
    error.value = ''
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projektName.value)}/massnahmen/${encodeURIComponent(massnahmeKey)}/wirksamkeit`,
        payload,
      )
      await fetchMassnahmen(projektName.value)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Wirksamkeitsprüfung fehlgeschlagen.'
      return false
    }
  }

  async function fetchKiVorschlag(): Promise<KiVorschlag[]> {
    if (!projektName.value) return []
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projektName.value)}/ki-vorschlag`,
      )
      return res.data.vorschlaege || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'KI-Vorschlag fehlgeschlagen.'
      return []
    }
  }

  // ── #1575 WiBA-Verknüpfung ───────────────────────────────────────────
  const wiba = ref<WibaAbleitung | null>(null)
  const pj = () => `${BASE}/projekte/${encodeURIComponent(projektName.value)}`

  async function fetchWiba() {
    if (!projektName.value) return
    try { wiba.value = (await apiClient.get(`${pj()}/wiba`)).data }
    catch { wiba.value = null }
  }
  async function syncWiba(): Promise<{ updated: any[]; wiba_projekt: string } | null> {
    error.value = ''
    try {
      const res = await apiClient.post(`${pj()}/wiba/sync`, {})
      await Promise.all([fetchMassnahmen(projektName.value), fetchWiba()])
      return res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'WiBA-Abgleich fehlgeschlagen.'
      return null
    }
  }
  async function setWibaLink(wibaProjekt: string) {
    error.value = ''
    try {
      await apiClient.put(`${pj()}/wiba-link`, { wiba_projekt: wibaProjekt })
      await fetchWiba()
    } catch (e: any) { error.value = e?.response?.data?.error || 'Verknüpfung fehlgeschlagen.' }
  }
  async function setStatusQuelle(key: string, quelle: 'wiba' | 'manuell'): Promise<TomMassnahme | null> {
    error.value = ''
    try {
      const res = await apiClient.put(`${pj()}/massnahmen/${encodeURIComponent(key)}/status-quelle`, { quelle })
      await fetchMassnahmen(projektName.value)
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Umschalten fehlgeschlagen.'; return null }
  }
  async function fetchFormulierung(key: string): Promise<{ entwurf: string; prompt: string; fragen: number } | null> {
    try { return (await apiClient.get(`${pj()}/massnahmen/${encodeURIComponent(key)}/formulierung`)).data }
    catch (e: any) { error.value = e?.response?.data?.error || 'Formulierung fehlgeschlagen.'; return null }
  }
  async function saveUmsetzung(key: string, payload: { umsetzung?: string; raw?: string; quelle?: string }):
      Promise<(TomMassnahme & { luecken?: string[] }) | null> {
    error.value = ''
    try {
      const res = await apiClient.post(`${pj()}/massnahmen/${encodeURIComponent(key)}/umsetzung`, payload)
      await fetchMassnahmen(projektName.value)
      return res.data
    } catch (e: any) { error.value = e?.response?.data?.error || 'Speichern der Umsetzung fehlgeschlagen.'; return null }
  }

  return {
    wiba, fetchWiba, syncWiba, setWibaLink, setStatusQuelle, fetchFormulierung, saveUmsetzung,
    projektName,
    items,
    gruppen,
    ziele,
    loading,
    error,
    gesamt,
    bewertet,
    avg,
    fetchZiele,
    fetchMassnahmen,
    seed,
    saveMassnahme,
    deleteMassnahme,
    saveWirksamkeit,
    fetchKiVorschlag,
  }
})
