<script setup lang="ts">
/**
 * S9 (#1079) — Wiederverwendbares Risiko-Cockpit.
 *
 * Zeigt modulübergreifend (Risikobewertung + CRA) alle offenen Risiken einer
 * Firma in einer filterbaren Tabelle. Read-only Anzeige. Wird in Wave 2 in die
 * Modul-Views eingebettet — hier bewusst nur als eigenständige Komponente.
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRiskCockpitStore, type RiskItem, type RiskSeverity } from '../../stores/riskCockpit'

const props = defineProps<{
  /** Firmen-ID, deren Risiken aggregiert werden sollen. */
  firmenId: number
}>()

const store = useRiskCockpitStore()

// Filterzustand (clientseitig).
const fSource = ref<'' | 'rb' | 'cra'>('')
const fSeverity = ref<'' | RiskSeverity>('')
const fStatus = ref<string>('')
const fProjekt = ref<string>('')

const SEVERITY_LABELS: Record<RiskSeverity, string> = {
  critical: 'Kritisch',
  high: 'Hoch',
  medium: 'Mittel',
  low: 'Gering',
  unknown: 'Unbekannt',
}

const SOURCE_LABELS: Record<string, string> = {
  rb: 'Risikobewertung',
  cra: 'CRA',
}

const filtered = computed<RiskItem[]>(() =>
  store.items.filter((i) => {
    if (fSource.value && i.source !== fSource.value) return false
    if (fSeverity.value && i.severity !== fSeverity.value) return false
    if (fStatus.value && i.status !== fStatus.value) return false
    if (fProjekt.value && i.projekt !== fProjekt.value) return false
    return true
  }),
)

function resetFilters(): void {
  fSource.value = ''
  fSeverity.value = ''
  fStatus.value = ''
  fProjekt.value = ''
}

async function reload(): Promise<void> {
  if (props.firmenId != null) {
    await store.fetchCockpit(props.firmenId)
  }
}

onMounted(reload)
watch(() => props.firmenId, reload)
</script>

<template>
  <div class="risk-cockpit">
    <div class="header">
      <h2>Risiko-Cockpit</h2>
      <button class="reload-btn" :disabled="store.loading" @click="reload">
        {{ store.loading ? 'Lädt…' : 'Aktualisieren' }}
      </button>
    </div>

    <p v-if="store.error" class="error">{{ store.error }}</p>

    <div v-if="store.summary" class="summary">
      <span class="pill total">Gesamt: {{ store.summary.total }}</span>
      <span class="pill sev-critical">Kritisch: {{ store.summary.by_severity.critical || 0 }}</span>
      <span class="pill sev-high">Hoch: {{ store.summary.by_severity.high || 0 }}</span>
      <span class="pill sev-medium">Mittel: {{ store.summary.by_severity.medium || 0 }}</span>
      <span class="pill sev-low">Gering: {{ store.summary.by_severity.low || 0 }}</span>
      <span class="pill src">RB: {{ store.summary.by_source.rb || 0 }}</span>
      <span class="pill src">CRA: {{ store.summary.by_source.cra || 0 }}</span>
    </div>

    <div class="filters">
      <label>
        Quelle
        <select v-model="fSource">
          <option value="">Alle</option>
          <option value="rb">Risikobewertung</option>
          <option value="cra">CRA</option>
        </select>
      </label>
      <label>
        Schwere
        <select v-model="fSeverity">
          <option value="">Alle</option>
          <option value="critical">Kritisch</option>
          <option value="high">Hoch</option>
          <option value="medium">Mittel</option>
          <option value="low">Gering</option>
          <option value="unknown">Unbekannt</option>
        </select>
      </label>
      <label>
        Status
        <select v-model="fStatus">
          <option value="">Alle</option>
          <option v-for="s in store.statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label>
        Projekt
        <select v-model="fProjekt">
          <option value="">Alle</option>
          <option v-for="p in store.projekte" :key="p" :value="p">{{ p }}</option>
        </select>
      </label>
      <button class="reset-btn" @click="resetFilters">Filter zurücksetzen</button>
    </div>

    <table class="risk-table">
      <thead>
        <tr>
          <th>Quelle</th>
          <th>Schwere</th>
          <th>Projekt</th>
          <th>Titel</th>
          <th>Status</th>
          <th>Referenz</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in filtered" :key="item.ref + ':' + item.projekt">
          <td>
            <span class="badge" :class="'src-' + item.source">
              {{ SOURCE_LABELS[item.source] || item.source }}
            </span>
          </td>
          <td>
            <span class="badge" :class="'sev-' + item.severity">
              {{ SEVERITY_LABELS[item.severity] || item.severity }}
            </span>
          </td>
          <td>{{ item.projekt }}</td>
          <td :title="item.beschreibung || ''">{{ item.titel }}</td>
          <td>{{ item.status }}</td>
          <td class="ref">{{ item.ref }}</td>
        </tr>
        <tr v-if="!store.loading && filtered.length === 0">
          <td colspan="6" class="empty">Keine offenen Risiken gefunden.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.risk-cockpit {
  font-family: 'Segoe UI', system-ui, sans-serif;
  color: #1a1a1a;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.header h2 {
  margin: 0;
  color: #1565c0;
  font-size: 1.25rem;
}
.reload-btn,
.reset-btn {
  background: #1565c0;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.85rem;
}
.reload-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.reset-btn {
  background: #607d8b;
}
.error {
  color: #c62828;
  background: #ffebee;
  padding: 8px 12px;
  border-radius: 4px;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.pill {
  border-radius: 12px;
  padding: 3px 10px;
  font-size: 0.8rem;
  background: #eceff1;
  color: #37474f;
}
.pill.total {
  background: #1565c0;
  color: #fff;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: flex-end;
  margin-bottom: 12px;
}
.filters label {
  display: flex;
  flex-direction: column;
  font-size: 0.8rem;
  color: #455a64;
  gap: 3px;
}
.filters select {
  padding: 5px 8px;
  border: 1px solid #cfd8dc;
  border-radius: 4px;
  min-width: 130px;
}
.risk-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.risk-table th,
.risk-table td {
  text-align: left;
  padding: 7px 10px;
  border-bottom: 1px solid #eceff1;
}
.risk-table th {
  background: #f5f7fa;
  color: #1565c0;
  font-weight: 600;
}
.risk-table .ref {
  font-family: 'Consolas', monospace;
  color: #546e7a;
}
.empty {
  text-align: center;
  color: #90a4ae;
  padding: 18px;
}
.badge {
  display: inline-block;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge.src-rb {
  background: #e3f2fd;
  color: #1565c0;
}
.badge.src-cra {
  background: #ede7f6;
  color: #5e35b1;
}
.badge.sev-critical,
.pill.sev-critical {
  background: #b71c1c;
  color: #fff;
}
.badge.sev-high,
.pill.sev-high {
  background: #ef6c00;
  color: #fff;
}
.badge.sev-medium,
.pill.sev-medium {
  background: #f9a825;
  color: #1a1a1a;
}
.badge.sev-low,
.pill.sev-low {
  background: #2e7d32;
  color: #fff;
}
.badge.sev-unknown {
  background: #b0bec5;
  color: #1a1a1a;
}
</style>
