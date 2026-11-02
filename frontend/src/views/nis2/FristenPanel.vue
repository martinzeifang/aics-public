<template>
  <div class="fristen-panel">
    <div class="intro-banner">
      <strong>📅 Fristen &amp; Wiedervorlagen (Art. 21(2)f / 27(4) NIS2)</strong>
      <p class="hint">Aktives Monitoring aller Kontrollzyklen: Risiko-Reviews (N2),
        Lieferanten-Reviews (N4), BCP-Tests (N5), Maßnahmen-Zieltermine, Audit-Zyklus
        und jährliche BSI-Bestätigung — mit Überfälligkeits-Ampel, sortiert nach Fälligkeit.</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>

    <template v-else>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>
      <span v-if="store.loading" class="hint">Lädt…</span>

      <div v-if="store.result" class="summary">
        <span class="pill red">{{ store.result.counts.ueberfaellig }} überfällig</span>
        <span class="pill amber">{{ store.result.counts.faellig }} bald fällig</span>
        <span class="pill green">{{ store.result.counts.on_track }} im Plan</span>
        <span class="pill grey">{{ store.result.counts.grey }} ohne Datum</span>
        <button class="btn-secondary" @click="reload">🔄 Aktualisieren</button>
      </div>

      <table v-if="store.result && store.result.items.length" class="fristen-table">
        <thead>
          <tr><th></th><th>Bereich</th><th>Referenz</th><th>Titel</th><th>Fällig am</th><th>Status</th><th>Restzeit</th><th>Quelle</th></tr>
        </thead>
        <tbody>
          <tr v-for="(it, idx) in store.result.items" :key="idx">
            <td><span class="ampel" :class="'ampel-' + it.ampel"></span></td>
            <td>{{ it.bereich }}</td>
            <td>{{ it.ref }}</td>
            <td>{{ it.titel }}</td>
            <td>{{ fmtDate(it.due_at) }}</td>
            <td>{{ statusLabel(it.status) }}</td>
            <td>{{ restzeit(it) }}</td>
            <td class="quelle">{{ it.quelle_feld }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="store.result && !store.loading" class="hint">
        Keine terminierten Wiedervorlagen erfasst.
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useNis2FristenStore, type FristItem } from '../../stores/nis2Fristen'

const props = defineProps<{ projektName: string | null }>()
const store = useNis2FristenStore()

const reload = async () => { if (props.projektName) await store.fetchFristen(props.projektName) }
onMounted(reload)
watch(() => props.projektName, reload)

const fmtDate = (s: string) => (s ? new Date(s).toLocaleDateString('de-DE') : '—')
const statusLabel = (s: string) => {
  if (s === 'ueberfaellig') return 'überfällig'
  if (s === 'faellig') return 'bald fällig'
  if (s === 'on_track') return 'im Plan'
  return '—'
}
const restzeit = (it: FristItem) => {
  if (it.days_left == null) return '—'
  return it.days_left < 0 ? `−${Math.abs(Math.round(it.days_left))} Tage` : `${Math.round(it.days_left)} Tage`
}
</script>

<style scoped>
.fristen-panel { padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }
.intro-banner strong { color: #1565c0; }
.hint { color: #607d8b; font-size: 0.9em; }
.msg.err { color: #c62828; }
.summary { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.pill { font-size: 0.85em; padding: 4px 10px; border-radius: 12px; color: #fff; }
.pill.red { background: #e53935; }
.pill.amber { background: #fb8c00; }
.pill.green { background: #43a047; }
.pill.grey { background: #bdbdbd; }
.fristen-table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
.fristen-table th, .fristen-table td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eceff1; }
.quelle { color: #90a4ae; font-family: Consolas, monospace; font-size: 0.85em; }
.ampel { width: 12px; height: 12px; border-radius: 50%; display: inline-block; background: #bdbdbd; }
.ampel-green { background: #43a047; }
.ampel-amber { background: #fb8c00; }
.ampel-red { background: #e53935; }
.ampel-grey { background: #bdbdbd; }
.btn-secondary { background: #eceff1; border: 1px solid #cfd8dc; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
</style>
