import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export interface CockpitArea {
  key: string
  label: string
  tab: string
  reifegrad_pct: number
  status: string
  offen: number
  faellig: number
}

export interface CockpitAufgabe {
  area: string
  area_label: string
  tab: string
  text: string
  due: string
  overdue: boolean
}

export interface Cockpit {
  projekt: string
  areas: CockpitArea[]
  offene_aufgaben: CockpitAufgabe[]
  gesamt_reifegrad: number
}

const BASE = '/dsgvo-cockpit'

export const useDsgvoCockpitStore = defineStore('dsgvoCockpit', () => {
  const cockpit = ref<Cockpit | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchCockpit(projektName: string) {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projektName)}/dsms-cockpit`,
      )
      cockpit.value = res.data
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'DSMS-Cockpit konnte nicht geladen werden.'
      cockpit.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    cockpit,
    loading,
    error,
    fetchCockpit,
  }
})
