import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/aiact-incidents'

export interface IncidentDeadlineStage {
  key: string
  label: string
  due_at: string
  status: string
  ampel: string
  hours_left: number | null
  hours_overdue: number | null
  fulfilled: boolean
}

export interface Incident {
  id?: number
  titel: string
  beschreibung: string
  eintritts_datum: string
  kenntnis_datum: string
  schweregrad: string
  status: string
  behoerde: string
  erstbericht_am: string
  vollbericht_am: string
  abgeschlossen_am: string
  einreichungsnachweis: string
  capa_ref: string
  report_text?: string
  schweregrad_label?: string
  frist_tage?: number
  due_date?: string
  ampel?: string
  overdue?: boolean
  deadlines?: { stages: IncidentDeadlineStage[]; overall_ampel: string; any_overdue: boolean; next_due: IncidentDeadlineStage | null }
}

export interface IncidentSummary {
  gesamt: number
  offen: number
  ueberfaellig: number
  abgeschlossen: number
}

export interface SchweregradOption {
  code: string
  label: string
  frist_tage: number
  stage_key: string
}

export const useAiactIncidentsStore = defineStore('aiactIncidents', () => {
  const items = ref<Incident[]>([])
  const summary = ref<IncidentSummary | null>(null)
  const schweregrade = ref<SchweregradOption[]>([])
  const statusWerte = ref<string[]>([])
  const loading = ref(false)
  const error = ref('')

  async function loadConstants() {
    try {
      const r = await apiClient.get(`${BASE}/constants`)
      schweregrade.value = r.data?.schweregrade || []
      statusWerte.value = r.data?.status || []
    } catch { /* ignore */ }
  }

  async function load(projekt: string) {
    loading.value = true
    error.value = ''
    try {
      const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/incidents`)
      items.value = r.data?.items || []
      summary.value = r.data?.summary || null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
    } finally {
      loading.value = false
    }
  }

  async function create(projekt: string, i: Incident) {
    await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/incidents`, i)
    await load(projekt)
  }

  async function update(projekt: string, id: number, i: Incident) {
    await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/incidents/${id}`, i)
    await load(projekt)
  }

  async function remove(projekt: string, id: number) {
    await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/incidents/${id}`)
    await load(projekt)
  }

  return {
    items, summary, schweregrade, statusWerte, loading, error,
    loadConstants, load, create, update, remove,
  }
})
