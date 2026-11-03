import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiClient from '../api/client'

export interface UnassignedProjekt {
  projekt: string
  unternehmen: string
}

// dbfile (z.B. 'cra.sqlite') → Liste unzugeordneter Projekte
export type UnassignedMap = Record<string, UnassignedProjekt[]>

export interface FirmaOption {
  id: number
  name: string
}

// Ergebnis des Backfill-Laufs je Modul, vom Backend frei strukturiert geliefert.
export interface BackfillModuleResult {
  matched?: number
  unmatched?: number
  [key: string]: any
}
export type BackfillResults = Record<string, BackfillModuleResult>

export const useFirmenLinkStore = defineStore('firmenLink', () => {
  const unassigned = ref<UnassignedMap>({})
  const firmen = ref<FirmaOption[]>([])
  const backfillResults = ref<BackfillResults | null>(null)
  const loading = ref(false)
  const backfilling = ref(false)
  const error = ref<string | null>(null)

  const fetchUnassigned = async () => {
    loading.value = true
    error.value = null
    try {
      const res = await apiClient.get('/admin/firmen-link/unassigned')
      unassigned.value = res.data?.unassigned || {}
      return unassigned.value
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der unzugeordneten Projekte'
      unassigned.value = {}
      return {}
    } finally {
      loading.value = false
    }
  }

  const fetchFirmen = async () => {
    error.value = null
    try {
      const res = await apiClient.get('/firmen')
      firmen.value = (res.data || []).map((f: any) => ({ id: f.id, name: f.name }))
      return firmen.value
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Laden der Firmen'
      firmen.value = []
      return []
    }
  }

  const runBackfill = async () => {
    backfilling.value = true
    error.value = null
    try {
      const res = await apiClient.post('/admin/firmen-link/backfill')
      backfillResults.value = res.data?.results || {}
      // Nach dem Backfill verbleiben i.d.R. weniger unzugeordnete Projekte.
      await fetchUnassigned()
      return backfillResults.value
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Ausführen des Backfills'
      return null
    } finally {
      backfilling.value = false
    }
  }

  const assign = async (module: string, projekt: string, firmenId: number) => {
    error.value = null
    try {
      await apiClient.post('/admin/firmen-link/assign', {
        module,
        projekt,
        firmen_id: firmenId,
      })
      // Zugeordnetes Projekt lokal aus der Liste entfernen (optimistisch).
      const list = unassigned.value[module]
      if (list) {
        unassigned.value[module] = list.filter((p) => p.projekt !== projekt)
        if (unassigned.value[module].length === 0) {
          delete unassigned.value[module]
        }
      }
      return true
    } catch (err: any) {
      error.value = err?.response?.data?.error || 'Fehler beim Zuordnen'
      return false
    }
  }

  return {
    unassigned,
    firmen,
    backfillResults,
    loading,
    backfilling,
    error,
    fetchUnassigned,
    fetchFirmen,
    runBackfill,
    assign,
  }
})
