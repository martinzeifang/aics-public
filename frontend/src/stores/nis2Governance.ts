import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/nis2-governance'

export interface GovTeilnehmer {
  id: number
  nachweis_id: number
  name: string
  rolle: string
  status: string
  quiz_score: string
}

export interface GovReview {
  ampel: 'grey' | 'green' | 'amber' | 'red'
  status: string
  due_at: string
  days_left?: number
}

export interface GovNachweis {
  id: number
  projekt_name: string
  typ: string
  datum: string
  gremium: string
  gegenstand: string
  rm_version: string
  dokument_url: string
  naechster_review: string
  quiz_referenz: string
  notizen: string
  teilnehmer: GovTeilnehmer[]
  review: GovReview
}

export interface GovConstants {
  nachweis_typen: string[]
  teilnehmer_status: string[]
}

export const useNis2GovernanceStore = defineStore('nis2Governance', () => {
  const constants = ref<GovConstants | null>(null)
  const nachweise = ref<GovNachweis[]>([])
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

  async function fetchNachweise(projekt: string) {
    if (!projekt) return
    loading.value = true
    error.value = ''
    try {
      nachweise.value =
        (await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/nachweise`)).data || []
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Nachweise konnten nicht geladen werden.'
    } finally {
      loading.value = false
    }
  }

  async function saveNachweis(projekt: string, data: Partial<GovNachweis>): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/nachweise`, data)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
      return false
    }
  }

  async function deleteNachweis(projekt: string, pk: number): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(`${BASE}/projekte/${encodeURIComponent(projekt)}/nachweise/${pk}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
      return false
    }
  }

  async function saveTeilnehmer(
    projekt: string, nachweisId: number, data: Partial<GovTeilnehmer>,
  ): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.post(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/nachweise/${nachweisId}/teilnehmer`, data)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Teilnehmer speichern fehlgeschlagen.'
      return false
    }
  }

  async function deleteTeilnehmer(
    projekt: string, nachweisId: number, teilnehmerId: number,
  ): Promise<boolean> {
    error.value = ''
    try {
      await apiClient.delete(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/nachweise/${nachweisId}/teilnehmer/${teilnehmerId}`)
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Teilnehmer löschen fehlgeschlagen.'
      return false
    }
  }

  return {
    constants, nachweise, loading, error,
    fetchConstants, fetchNachweise, saveNachweis, deleteNachweis,
    saveTeilnehmer, deleteTeilnehmer,
  }
})
