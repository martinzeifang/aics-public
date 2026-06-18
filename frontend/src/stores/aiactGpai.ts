import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/aiact-gpai'

export interface GpaiKlassifizierung {
  projekt_name?: string
  ist_gpai: boolean
  training_flop: number
  systemisch_override: string
  copyright_tdm_policy: string
  trainingsdaten_summary: string
  notifikation_kommission_am: string
  schwellwert_erreicht_am: string
  kommentar: string
  flop_threshold?: number
  ueber_schwellenwert?: boolean
  systemisch?: boolean
  notifikation_deadline?: any
}

export interface GpaiCheck {
  id: string
  ref: string
  titel: string
  hinweis: string
  systemic_only: boolean
  status: number
  kommentar: string
  nachweis_ref: string
}

export interface GpaiIncident {
  id?: number
  titel: string
  beschreibung: string
  eingetreten_am: string
  gemeldet_ai_office_am: string
  status: string
}

export interface GpaiSummary {
  ist_gpai: boolean
  systemisch: boolean
  ueber_schwellenwert: boolean
  training_flop: number
  checks_gesamt: number
  checks_erfuellt: number
  notifikation_faellig: boolean
}

export const useAiactGpaiStore = defineStore('aiactGpai', () => {
  const klass = ref<GpaiKlassifizierung | null>(null)
  const checks = ref<GpaiCheck[]>([])
  const incidents = ref<GpaiIncident[]>([])
  const summary = ref<GpaiSummary | null>(null)
  const flopThreshold = ref(1e25)
  const incidentStatus = ref<string[]>([])
  const loading = ref(false)
  const error = ref('')

  async function loadRequirements() {
    try {
      const r = await apiClient.get(`${BASE}/requirements`)
      flopThreshold.value = r.data?.flop_threshold || 1e25
      incidentStatus.value = r.data?.incident_status || []
    } catch { /* ignore */ }
  }

  async function load(projekt: string) {
    loading.value = true
    error.value = ''
    try {
      const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/gpai`)
      klass.value = r.data?.klassifizierung || null
      checks.value = r.data?.checks || []
      incidents.value = r.data?.incidents || []
      summary.value = r.data?.summary || null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
    } finally {
      loading.value = false
    }
  }

  function _apply(r: any) {
    klass.value = r.data?.klassifizierung || klass.value
    if (r.data?.checks) checks.value = r.data.checks
    if (r.data?.incidents) incidents.value = r.data.incidents
    if (r.data?.summary) summary.value = r.data.summary
  }

  async function saveKlass(projekt: string, k: GpaiKlassifizierung) {
    _apply(await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/klassifizierung`, k))
  }

  async function saveCheck(projekt: string, c: GpaiCheck) {
    _apply(await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(projekt)}/checks/${c.id}`,
      { status: c.status, kommentar: c.kommentar, nachweis_ref: c.nachweis_ref }))
  }

  async function createIncident(projekt: string, i: GpaiIncident) {
    _apply(await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/incidents`, i))
  }

  async function deleteIncident(projekt: string, id: number) {
    _apply(await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/incidents/${id}`))
  }

  async function wizardPrompt(projekt: string): Promise<string> {
    const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/wizard/prompt`)
    return r.data?.prompt || ''
  }

  async function wizardParse(projekt: string, response: string) {
    _apply(await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/wizard/parse`, { response, apply: true }))
  }

  return {
    klass, checks, incidents, summary, flopThreshold, incidentStatus, loading, error,
    loadRequirements, load, saveKlass, saveCheck, createIncident, deleteIncident,
    wizardPrompt, wizardParse,
  }
})
