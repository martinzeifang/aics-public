<template>
  <div class="cockpit-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <div class="cockpit-toolbar">
        <div class="toolbar-info">
          <strong>📊 DSMS-Cockpit — Rechenschaftspflicht (Art. 5 Abs. 2 DSGVO)</strong>
        </div>
        <button class="btn-tiny" :disabled="store.loading" @click="load">
          {{ store.loading ? 'Lädt…' : '↻ Aktualisieren' }}
        </button>
      </div>

      <p v-if="store.error" class="error-msg">{{ store.error }}</p>

      <template v-if="cockpit">
        <!-- Gesamt-Reifegrad -->
        <section class="gesamt-card">
          <div class="gesamt-ring" :style="{ '--pct': cockpit.gesamt_reifegrad }">
            <span class="gesamt-value">{{ cockpit.gesamt_reifegrad }}%</span>
          </div>
          <div class="gesamt-text">
            <h4>Gesamt-Reifegrad des Datenschutz-Managements</h4>
            <p>Durchschnitt über alle {{ cockpit.areas.length }} DSGVO-Bereiche.</p>
          </div>
        </section>

        <!-- Reifegrad-Kacheln -->
        <div class="kachel-grid">
          <button
            v-for="a in cockpit.areas"
            :key="a.key"
            class="kachel"
            :class="`status-${a.status}`"
            :title="`Bereich öffnen: ${a.label}`"
            @click="openArea(a)"
          >
            <div class="kachel-head">
              <span class="kachel-label">{{ a.label }}</span>
              <span class="kachel-dot" :class="`dot-${a.status}`"></span>
            </div>
            <div class="kachel-bar">
              <div class="kachel-bar-fill" :class="`fill-${a.status}`"
                   :style="{ width: a.reifegrad_pct + '%' }"></div>
            </div>
            <div class="kachel-foot">
              <span class="kachel-pct">{{ a.reifegrad_pct }}%</span>
              <span class="kachel-meta">
                <span v-if="a.offen">{{ a.offen }} offen</span>
                <span v-if="a.faellig" class="faellig">{{ a.faellig }} fällig</span>
              </span>
            </div>
          </button>
        </div>

        <!-- Offene Aufgaben / Fristen -->
        <section class="aufgaben-card">
          <h4>Offene Aufgaben &amp; Fristen ({{ cockpit.offene_aufgaben.length }})</h4>
          <p v-if="!cockpit.offene_aufgaben.length" class="empty">
            Keine offenen Aufgaben — alle Bereiche sind aktuell.
          </p>
          <ul v-else class="aufgaben-list">
            <li
              v-for="(t, i) in cockpit.offene_aufgaben"
              :key="i"
              :class="{ overdue: t.overdue }"
            >
              <button class="aufgabe-link" :title="`Bereich öffnen: ${t.area_label}`"
                      @click="openTab(t.tab)">
                <span class="aufgabe-area">{{ t.area_label }}</span>
                <span class="aufgabe-text">{{ t.text }}</span>
                <span v-if="t.due" class="aufgabe-due" :class="{ overdue: t.overdue }">
                  {{ t.overdue ? 'überfällig seit' : 'fällig' }} {{ t.due }}
                </span>
              </button>
            </li>
          </ul>
        </section>
      </template>

      <p v-else-if="!store.loading" class="hint">Keine Cockpit-Daten verfügbar.</p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import { useDsgvoCockpitStore, type CockpitArea } from '../../stores/dsgvoCockpit'

const emit = defineEmits<{ (e: 'open-tab', tabId: string): void }>()

const dsgvo = useDsgvoStore()
const store = useDsgvoCockpitStore()

const projekt = computed(() => dsgvo.selectedProjekt)
const cockpit = computed(() => store.cockpit)

async function load() {
  if (!projekt.value) return
  await store.fetchCockpit(projekt.value)
}
onMounted(load)
watch(projekt, load)

function openTab(tabId: string) {
  if (tabId) emit('open-tab', tabId)
}
function openArea(a: CockpitArea) {
  openTab(a.tab)
}
</script>

<style scoped>
.cockpit-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.empty { color: #607d8b; font-size: 0.85rem; margin: 8px 0 0; }
.error-msg { background: #ffebee; color: #c62828; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }

.cockpit-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.toolbar-info strong { color: #1565c0; font-size: 15px; }

.btn-tiny {
  background: none; border: 1px solid #ddd; padding: 4px 10px;
  border-radius: 3px; cursor: pointer; font-size: 12px;
}
.btn-tiny:hover { background: #f0f0f0; }
.btn-tiny:disabled { opacity: 0.6; cursor: not-allowed; }

/* Gesamt-Reifegrad */
.gesamt-card {
  display: flex; align-items: center; gap: 20px;
  background: white; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 8px; padding: 16px 20px; margin-bottom: 16px;
}
.gesamt-ring {
  width: 96px; height: 96px; border-radius: 50%; flex: none;
  display: flex; align-items: center; justify-content: center;
  background: conic-gradient(#1565c0 calc(var(--pct) * 1%), #e3eaf2 0);
}
.gesamt-value {
  width: 72px; height: 72px; border-radius: 50%; background: white;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 18px; color: #1565c0;
}
.gesamt-text h4 { margin: 0 0 4px; color: #1565c0; font-size: 15px; }
.gesamt-text p { margin: 0; color: #607d8b; font-size: 13px; }

/* Kacheln */
.kachel-grid {
  display: grid; gap: 12px; margin-bottom: 16px;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}
.kachel {
  text-align: left; cursor: pointer; background: white;
  border: 1px solid var(--color-border, #e0e0e0); border-left-width: 4px;
  border-radius: 8px; padding: 12px 14px; transition: box-shadow .15s;
}
.kachel:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.kachel.status-gruen { border-left-color: #2e7d32; }
.kachel.status-gelb  { border-left-color: #f57f17; }
.kachel.status-rot   { border-left-color: #c62828; }
.kachel.status-leer  { border-left-color: #9e9e9e; }

.kachel-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.kachel-label { font-weight: 600; font-size: 13px; color: #263238; }
.kachel-dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
.dot-gruen { background: #2e7d32; }
.dot-gelb  { background: #f57f17; }
.dot-rot   { background: #c62828; }
.dot-leer  { background: #9e9e9e; }

.kachel-bar { height: 6px; background: #eceff1; border-radius: 3px; overflow: hidden; }
.kachel-bar-fill { height: 100%; }
.fill-gruen { background: #2e7d32; }
.fill-gelb  { background: #f57f17; }
.fill-rot   { background: #c62828; }
.fill-leer  { background: #9e9e9e; }

.kachel-foot { display: flex; align-items: baseline; justify-content: space-between; margin-top: 8px; }
.kachel-pct { font-weight: 700; font-size: 16px; color: #263238; }
.kachel-meta { font-size: 11px; color: #607d8b; display: flex; gap: 8px; }
.kachel-meta .faellig { color: #c62828; font-weight: 600; }

/* Aufgaben */
.aufgaben-card {
  background: white; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 8px; padding: 16px 18px;
}
.aufgaben-card h4 { margin: 0 0 12px; color: #1565c0; font-size: 14px; }
.aufgaben-list { list-style: none; margin: 0; padding: 0; }
.aufgaben-list li { border-bottom: 1px solid #f0f0f0; }
.aufgaben-list li:last-child { border-bottom: none; }

.aufgabe-link {
  width: 100%; text-align: left; background: none; border: none; cursor: pointer;
  display: flex; align-items: center; gap: 10px; padding: 8px 4px; font-size: 13px;
}
.aufgabe-link:hover { background: #f5f8fc; }
.aufgabe-area {
  flex: none; font-size: 11px; font-weight: 600; color: #1565c0;
  background: #e3f2fd; padding: 2px 8px; border-radius: 3px; white-space: nowrap;
}
.aufgabe-text { flex: 1; color: #37474f; }
.aufgabe-due { flex: none; font-size: 11px; color: #607d8b; white-space: nowrap; }
.aufgabe-due.overdue { color: #c62828; font-weight: 600; }
.aufgaben-list li.overdue .aufgabe-text { color: #c62828; }
</style>
