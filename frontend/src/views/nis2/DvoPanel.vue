<template>
  <div class="dvo-panel">
    <div class="intro-banner">
      <strong>📜 DVO (EU) 2024/2690 — Sektorspezifische Mindestanforderungen</strong>
      <p class="hint">Sektor-aktiviertes Anforderungsset (13 Abschnitte) für digitale
        Infrastrukturen/Dienste als bewertbare Controls plus Erheblichkeits-Schwellenwert-Katalog
        je Diensttyp für die Vorfall-Triage.</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>

    <template v-else>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <div v-if="store.status" class="status-card">
        <div>
          <strong>Sektor:</strong> {{ store.status.sektor || '— (kein Klassifikator-Sektor)' }}
          <span class="badge" :class="store.status.relevant ? 'ok' : 'neutral'">
            {{ store.status.relevant ? 'DVO-relevant' : 'nicht sektor-relevant' }}
          </span>
          <span class="badge" :class="store.status.aktiv ? 'active' : 'neutral'">
            {{ store.status.aktiv ? `aktiv (${store.status.anzahl_controls} Controls)` : 'inaktiv' }}
          </span>
        </div>
        <div class="actions">
          <button v-if="!store.status.aktiv" class="btn-primary" @click="store.activate(projektName)">
            DVO-2690-Set aktivieren
          </button>
          <button v-else class="btn-secondary danger" @click="store.deactivate(projektName)">
            Set deaktivieren
          </button>
        </div>
      </div>

      <div v-if="store.status?.controls?.length" class="controls">
        <strong>Aktivierte Controls</strong>
        <table>
          <thead><tr><th>Ref</th><th>Titel</th><th>Beschreibung</th></tr></thead>
          <tbody>
            <tr v-for="c in store.status.controls" :key="c.id">
              <td>{{ c.ref }}</td><td>{{ c.titel }}</td><td>{{ c.beschreibung }}</td>
            </tr>
          </tbody>
        </table>
        <p class="hint">Bewertung erfolgt im Tab „Anforderungen" (Kapitel DVO2690).</p>
      </div>

      <div class="schwellen">
        <strong>Erheblichkeits-Schwellenwerte (Vorfall-Triage)</strong>
        <div v-for="s in store.schwellenwerte" :key="s.diensttyp" class="schwelle-card">
          <div class="dt">{{ s.diensttyp }}</div>
          <ul><li v-for="(k, i) in s.kriterien" :key="i">{{ k }}</li></ul>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useNis2DvoStore } from '../../stores/nis2Dvo'

const props = defineProps<{ projektName: string | null }>()
const store = useNis2DvoStore()

const reload = async () => { if (props.projektName) await store.fetchStatus(props.projektName) }
onMounted(async () => { await store.fetchSchwellenwerte(); await reload() })
watch(() => props.projektName, reload)
</script>

<style scoped>
.dvo-panel { padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }
.intro-banner strong { color: #1565c0; }
.hint { color: #607d8b; font-size: 0.9em; }
.msg.err { color: #c62828; }
.status-card { display: flex; justify-content: space-between; align-items: center; gap: 16px; border: 1px solid #cfd8dc; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; background: #fff; flex-wrap: wrap; }
.badge { font-size: 0.8em; padding: 3px 10px; border-radius: 12px; margin-left: 8px; }
.badge.ok { background: #c8e6c9; color: #2e7d32; }
.badge.active { background: #bbdefb; color: #1565c0; }
.badge.neutral { background: #eceff1; color: #607d8b; }
.controls, .schwellen { margin-top: 16px; }
.controls table { width: 100%; border-collapse: collapse; font-size: 0.85em; margin-top: 6px; }
.controls th, .controls td { text-align: left; padding: 5px 8px; border-bottom: 1px solid #eceff1; }
.schwelle-card { border: 1px solid #eceff1; border-radius: 6px; padding: 8px 12px; margin: 8px 0; }
.dt { font-weight: 600; color: #1565c0; }
.schwelle-card ul { margin: 6px 0 0; padding-left: 20px; font-size: 0.9em; }
.btn-primary { background: #1565c0; color: #fff; border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer; }
.btn-secondary { background: #eceff1; border: 1px solid #cfd8dc; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
.btn-secondary.danger { color: #c62828; }
</style>
