import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

// Backend mountet den Blueprint unter '/api/nis2-incidents'. apiClient.baseURL
// ist '/api' -> Pfade hier ohne '/api'.
const BASE = '/nis2-incidents'

export interface IncidentMeldung {
  id: number
  incident_pk: number
  typ: string
  status: string
  ist_zeitpunkt: string
  text: string
  bsi_referenz: string
}

export interface DeadlineStage {
  key: string
  label: string
  due_at: string
  status: string
  ampel: 'grey' | 'green' | 'amber' | 'red'
  hours_left: number | null
  hours_overdue: number | null
  fulfilled: boolean
}

export interface IncidentDeadlines {
  stages: DeadlineStage[]
  overall_ampel: 'grey' | 'green' | 'amber' | 'red'
  any_overdue: boolean
  next_due: DeadlineStage | null
}

export interface Incident {
  id: number
  projekt_name: string
  incident_id: string
  titel: string
  kenntnis_zeitpunkt: string
  erheblich: number
  status: string
  schweregrad: string
  betroffene_assets: string
  root_cause: string
  grenzueberschreitend: number
  notizen: string
  meldungen: IncidentMeldung[]
  deadlines: IncidentDeadlines
  meldung_status: Record<string, string>
}

export interface IncidentConstants {
  incident_status: string[]
  meldung_status: string[]
  meldung_typen: string[]
  schweregrade: string[]
}

export const useNis2IncidentsStore = defineStore('nis2Incidents', () => {
  const constants = ref<IncidentConstants | null>(null)
  const incidents = ref<Incident[]>([])
  const loading = ref(false)
  const error = ref('')

  async function fetchConstants() {
    if (constants.value) return
    try {
      constants.value = (await apiClient.get(`${BASE}/constants`)).data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Konstanten konnten nicht geladen werden.'
    }
  }

  async function fetchIncidents(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/incidents`,
      )
      incidents.value = res.data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Vorfälle konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function saveIncident(
    projekt: string,
    data: Partial<Incident>,
  ): Promise<Incident | null> {
    error.value = ''
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/incidents`,
        data,
      )
      return res.data?.incident ?? null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Vorfall konnte nicht gespeichert werden.'
      return null
    }
  }

  async function deleteIncident(projekt: string, pk: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/incidents/${pk}`,
      )
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function saveMeldung(
    projekt: string,
    pk: number,
    data: Partial<IncidentMeldung>,
  ): Promise<Incident | null> {
    error.value = ''
    try {
      const res = await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/incidents/${pk}/meldungen`,
        data,
      )
      return res.data?.incident ?? null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Meldung konnte nicht gespeichert werden.'
      return null
    }
  }

  async function exportMeldung(
    projekt: string,
    pk: number,
    meldungId: number,
    incidentId: string,
    typ: string,
  ): Promise<boolean> {
    error.value = ''
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/incidents/${pk}/meldungen/${meldungId}/export`,
        { responseType: 'blob' },
      )
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `NIS2-Meldung_${incidentId}_${typ}.md`
      a.click()
      URL.revokeObjectURL(url)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Export fehlgeschlagen.'
      return false
    }
  }

  return {
    constants,
    incidents,
    loading,
    error,
    fetchConstants,
    fetchIncidents,
    saveIncident,
    deleteIncident,
    saveMeldung,
    exportMeldung,
  }
})
