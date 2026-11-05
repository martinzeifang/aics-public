import { ref } from 'vue'
import apiClient from '../api/client'
import { useDocumentsStore } from '../stores/documents'
import type { DashboardRisiko } from '../components/shared/ModuleDashboard.vue'

/**
 * Geteilte Daten-Loader für das einheitliche Dashboard (#1250):
 * - Dokumente-Soll-Ist aus dem `shared/documents`-Katalog (erstellt/freigegeben vs. ausstehend)
 * - Risiko-Kurzübersicht (read-only) aus dem firmenweiten Risiko-Cockpit, projekt-aufgelöst.
 *
 * Module-übergreifend identisch genutzt von CRA/NIS2/AI-Act/DSGVO.
 */
export function useModuleDashboard(modul: string) {
  const docsStore = useDocumentsStore()

  const dokFertig = ref(0)
  const dokGesamt = ref(0)
  const risiko = ref<DashboardRisiko>({ gesamt: 0 })
  const risikoLoading = ref(false)

  /** Soll-Ist aus dem Pflichtdokumenten-Katalog. „fertig" = erstellt/freigegeben/final. */
  async function loadDokumente(projekt: string | null) {
    dokFertig.value = 0
    dokGesamt.value = 0
    if (!projekt) return
    const cat = await docsStore.fetchCatalog(modul, projekt)
    if (!cat) return
    const pflicht = cat.katalog.filter(s => s.pflicht !== false)
    dokGesamt.value = pflicht.length
    dokFertig.value = pflicht.filter(s => s.vorhanden && s.status !== 'fehlt').length
  }

  /** Offene Risiken nach Schwere — read-only aus dem Risiko-Cockpit (projekt → Firma). */
  async function loadRisiko(projekt: string | null) {
    risiko.value = { gesamt: 0 }
    if (!projekt) return
    risikoLoading.value = true
    try {
      const res = await apiClient.get(
        `/risk-cockpit/by-projekt/${modul}/${encodeURIComponent(projekt)}`,
      )
      const d = res.data || {}
      if (d.unassigned) {
        risiko.value = { gesamt: 0, unassigned: true }
        return
      }
      const sev = d.summary?.by_severity || {}
      risiko.value = {
        gesamt: d.summary?.total ?? 0,
        kritisch: sev.critical ?? 0,
        hoch: sev.high ?? 0,
        mittel: sev.medium ?? 0,
        niedrig: (sev.low ?? 0) + (sev.unknown ?? 0),
      }
    } catch {
      risiko.value = { gesamt: 0 }
    } finally {
      risikoLoading.value = false
    }
  }

  async function loadAll(projekt: string | null) {
    await Promise.all([loadDokumente(projekt), loadRisiko(projekt)])
  }

  return { dokFertig, dokGesamt, risiko, risikoLoading, loadDokumente, loadRisiko, loadAll }
}
