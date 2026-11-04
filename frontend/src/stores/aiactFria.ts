import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

const BASE = '/aiact-fria'

export interface FriaRecord {
  projekt_name?: string
  betreiber_typ: string
  nutzungsprozesse: string
  zeitraum_frequenz: string
  betroffene_gruppen: string
  schadensrisiken: string[]
  oversight_massnahmen: string
  massnahmen_bei_risiko: string
  governance: string
  beschwerdemechanismus: string
  stage: string
  status: string
  mitteilung_behoerde_am: string
  behoerde: string
}

export interface FriaTrigger {
  required: boolean
  risk_tier: string
  is_high_risk: boolean
  betreiber_typ: string
  betreiber_pflicht: boolean
}

export interface BetreiberTyp { code: string; label: string }

export const useAiactFriaStore = defineStore('aiactFria', () => {
  const record = ref<FriaRecord | null>(null)
  const trigger = ref<FriaTrigger | null>(null)
  const betreiberTypen = ref<BetreiberTyp[]>([])
  const stages = ref<string[]>([])
  const loading = ref(false)
  const error = ref('')

  async function loadConstants() {
    try {
      const r = await apiClient.get(`${BASE}/constants`)
      betreiberTypen.value = r.data?.betreiber_typen || []
      stages.value = r.data?.stages || []
    } catch { /* ignore */ }
  }

  async function load(projekt: string) {
    loading.value = true
    error.value = ''
    try {
      const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/fria`)
      record.value = r.data?.record || null
      trigger.value = r.data?.trigger || null
    } catch (e: any) {
      error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
    } finally {
      loading.value = false
    }
  }

  async function save(projekt: string, rec: FriaRecord) {
    const r = await apiClient.put(`${BASE}/projekte/${encodeURIComponent(projekt)}/fria`, rec)
    record.value = r.data?.record || record.value
    trigger.value = r.data?.trigger || trigger.value
  }

  async function checkTrigger(projekt: string, betreiber_typ: string): Promise<FriaTrigger | null> {
    try {
      const r = await apiClient.get(
        `${BASE}/projekte/${encodeURIComponent(projekt)}/trigger`,
        { params: { betreiber_typ } },
      )
      return r.data || null
    } catch { return null }
  }

  async function report(projekt: string, behoerde: string) {
    const r = await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/mitteilung`, { behoerde })
    record.value = r.data?.record || record.value
  }

  async function wizardPrompt(projekt: string): Promise<string> {
    const r = await apiClient.get(`${BASE}/projekte/${encodeURIComponent(projekt)}/wizard/prompt`)
    return r.data?.prompt || ''
  }

  async function wizardParse(projekt: string, response: string) {
    const r = await apiClient.post(`${BASE}/projekte/${encodeURIComponent(projekt)}/wizard/parse`, { response, apply: true })
    record.value = r.data?.record || record.value
  }

  return {
    record, trigger, betreiberTypen, stages, loading, error,
    loadConstants, load, save, checkTrigger, report, wizardPrompt, wizardParse,
  }
})
