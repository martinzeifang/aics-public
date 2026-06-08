/**
 * S9 (#1079) — Pinia-Store für das zentrale Risiko-Cockpit.
 *
 * Lädt die modulübergreifende, read-only Aggregation offener Risiken einer
 * Firma vom Backend (`GET /api/risk-cockpit/<firmen_id>`, siehe S8 / #1078).
 * Reine Anzeige — keine Mutation von rb_risiken/cra_vuln.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '../api/client'

export type RiskSource = 'rb' | 'cra'
export type RiskSeverity = 'critical' | 'high' | 'medium' | 'low' | 'unknown'

export interface RiskItem {
  source: RiskSource
  projekt: string
  titel: string
  severity: RiskSeverity
  status: string
  ref: string
  firmen_id: number
  id?: number
  cve_id?: string
  cvss_score?: number
  beschreibung?: string
  provenance_key?: string
}

export interface RiskCockpitSummary {
  total: number
  by_source: Record<string, number>
  by_severity: Record<string, number>
  projekte: string[]
}

export interface RiskCockpitResponse {
  firmen_id: number
  items: RiskItem[]
  summary: RiskCockpitSummary
}

export const useRiskCockpitStore = defineStore('riskCockpit', () => {
  const firmenId = ref<number | null>(null)
  const items = ref<RiskItem[]>([])
  const summary = ref<RiskCockpitSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchCockpit(id: number): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get<RiskCockpitResponse>(
        `/risk-cockpit/${encodeURIComponent(String(id))}`,
      )
      firmenId.value = res.data.firmen_id
      items.value = res.data.items || []
      summary.value = res.data.summary || null
    } catch (e: any) {
      error.value =
        e?.response?.data?.error || e?.message || 'Risiko-Cockpit konnte nicht geladen werden'
      items.value = []
      summary.value = null
    } finally {
      loading.value = false
    }
  }

  function reset(): void {
    firmenId.value = null
    items.value = []
    summary.value = null
    error.value = null
  }

  // Verfügbare Filterwerte (aus den geladenen Items abgeleitet).
  const projekte = computed<string[]>(() =>
    Array.from(new Set(items.value.map((i) => i.projekt).filter(Boolean))).sort(),
  )
  const statuses = computed<string[]>(() =>
    Array.from(new Set(items.value.map((i) => i.status).filter(Boolean))).sort(),
  )

  return {
    firmenId,
    items,
    summary,
    loading,
    error,
    projekte,
    statuses,
    fetchCockpit,
    reset,
  }
})
