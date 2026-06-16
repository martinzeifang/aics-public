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

  return {
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
