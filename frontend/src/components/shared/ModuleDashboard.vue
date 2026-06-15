<template>
  <div class="module-dashboard">
    <!-- Gesamt-Reifegrad + Bereichs-/Kapitelkarten -->
    <div class="dashboard">
      <div class="gauge-card">
        <MaturityGauge
          :percent="Math.round(gesamt.percent ?? 0)"
          :ampel="gesamt.ampel"
          label="Gesamt-Reifegrad"
        />
        <div class="gauge-stats">
          <div v-for="(line, i) in gesamtStats" :key="i">{{ line }}</div>
        </div>
      </div>

      <div class="chapters-grid">
        <ChapterCard
          v-for="b in bereiche"
          :key="b.id"
          :id="b.id"
          :title="b.title"
          :percent="Math.round(b.percent ?? 0)"
          :bewertet="b.bewertet ?? 0"
          :gesamt="b.gesamt ?? 0"
          :ampel="b.ampel"
          @click="$emit('open-bereich', b.id)"
        />
        <div v-if="bereiche.length === 0" class="empty-card">
          Noch keine Bereichs-Daten — bitte zuerst bewerten.
        </div>
      </div>
    </div>

    <!-- Kacheln: offene Punkte / offene Fristen / Dokumente / Risiken -->
    <div class="kpi-grid">
      <!-- Offene Punkte (Score < Schwelle) -->
      <div class="kpi-card" :class="{ clickable: !!offenePunkte.length }"
           @click="offenePunkte.length && $emit('open-luecken')">
        <div class="kpi-head">
          <span class="kpi-icon">🚩</span>
          <span class="kpi-title">Offene Punkte</span>
        </div>
        <div class="kpi-value" :class="offenePunkte.length ? 'warn' : 'ok'">
          {{ offenePunkte.length }}
        </div>
        <div class="kpi-sub">Anforderungen mit Score &lt; {{ schwelle }}</div>
        <ul v-if="offenePunkte.length" class="kpi-list">
          <li v-for="l in offenePunkte.slice(0, 5)" :key="l.id"
              class="kpi-item" @click.stop="$emit('open-punkt', l.id)">
            <code>{{ l.id }}</code>
            <span class="kpi-item-text">{{ l.titel }}</span>
            <span class="kpi-item-meta">Score {{ l.bewertung }}</span>
          </li>
        </ul>
      </div>

      <!-- Offene Fristen -->
      <div class="kpi-card" :class="{ clickable: fristenTab }"
           @click="fristenTab && $emit('open-fristen')">
        <div class="kpi-head">
          <span class="kpi-icon">📅</span>
          <span class="kpi-title">Offene Fristen</span>
        </div>
        <div class="kpi-value" :class="fristenOffen ? 'warn' : 'ok'">
          {{ fristen.length ? fristenOffen : '–' }}
        </div>
        <div class="kpi-sub">
          <template v-if="fristen.length">{{ fristenUeberfaellig }} überfällig</template>
          <template v-else>Keine Fristen in diesem Modul</template>
        </div>
        <ul v-if="fristen.length" class="kpi-list">
          <li v-for="(f, i) in fristen.slice(0, 5)" :key="i"
              class="kpi-item" :class="{ overdue: f.overdue }"
              @click.stop="f.tab && $emit('open-fristen', f.tab)">
            <span class="kpi-item-text">{{ f.text }}</span>
            <span v-if="f.due" class="kpi-item-meta" :class="{ overdue: f.overdue }">
              {{ f.overdue ? 'überfällig' : 'fällig' }} {{ f.due }}
            </span>
          </li>
        </ul>
      </div>

      <!-- Dokumente-Status (Soll-Ist) -->
      <div class="kpi-card clickable" @click="$emit('open-dokumente')">
        <div class="kpi-head">
          <span class="kpi-icon">📄</span>
          <span class="kpi-title">Dokumente</span>
        </div>
        <div class="kpi-value" :class="dokFehlt ? 'warn' : 'ok'">
          {{ dokFertig }}<span class="kpi-of">/ {{ dokGesamt }}</span>
        </div>
        <div class="kpi-sub">erstellt/freigegeben · {{ dokFehlt }} ausstehend</div>
        <div v-if="dokGesamt" class="dok-bar">
          <div class="dok-bar-fill" :style="{ width: dokPct + '%' }"></div>
        </div>
        <div v-else class="kpi-sub muted">Kein Dokumenten-Katalog geladen</div>
      </div>

      <!-- Risiko-Kurzübersicht (read-only Verweis aufs Risiko-Cockpit) -->
      <div class="kpi-card clickable" @click="$emit('open-risiken')">
        <div class="kpi-head">
          <span class="kpi-icon">⚠️</span>
          <span class="kpi-title">Offene Risiken</span>
        </div>
        <div class="kpi-value" :class="risiko.gesamt ? 'warn' : 'ok'">
          {{ risikoLoading ? '…' : risiko.gesamt }}
        </div>
        <div class="kpi-sub">nach Schwere · zum Risiko-Cockpit →</div>
        <div v-if="risiko.gesamt" class="sev-row">
          <span v-if="risiko.kritisch" class="sev sev-kritisch">{{ risiko.kritisch }} kritisch</span>
          <span v-if="risiko.hoch" class="sev sev-hoch">{{ risiko.hoch }} hoch</span>
          <span v-if="risiko.mittel" class="sev sev-mittel">{{ risiko.mittel }} mittel</span>
          <span v-if="risiko.niedrig" class="sev sev-niedrig">{{ risiko.niedrig }} niedrig</span>
        </div>
        <div v-else-if="!risikoLoading" class="kpi-sub muted">
          {{ risiko.unassigned ? 'Keiner Firma zugeordnet' : 'Keine offenen Risiken' }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MaturityGauge from './MaturityGauge.vue'
import ChapterCard from './ChapterCard.vue'

/**
 * Einheitliches Dashboard für CRA/NIS2/AI-Act/DSGVO (#1250).
 * Komplett "dumm": jede View normalisiert ihre Modul-Daten auf diese Props,
 * damit Optik + Aufbau in allen vier Modulen identisch sind.
 */
export interface DashboardBereich {
  id: string
  title?: string
  percent: number
  bewertet?: number
  gesamt?: number
  ampel?: string
}
export interface DashboardLuecke {
  id: string
  titel: string
  bewertung: number
}
export interface DashboardFrist {
  text: string
  due?: string | null
  overdue?: boolean
  tab?: string
}
export interface DashboardRisiko {
  gesamt: number
  kritisch?: number
  hoch?: number
  mittel?: number
  niedrig?: number
  unassigned?: boolean
}

const props = withDefaults(defineProps<{
  gesamt: { percent: number; ampel?: string }
  gesamtStats?: string[]
  bereiche?: DashboardBereich[]
  offenePunkte?: DashboardLuecke[]
  schwelle?: number
  /** true, wenn das Modul einen Fristen-Bereich hat (sonst Kachel inaktiv). */
  fristenTab?: boolean
  fristen?: DashboardFrist[]
  /** Dokumente-Soll-Ist: erstellt/freigegeben vs. gesamt. */
  dokFertig?: number
  dokGesamt?: number
  risiko?: DashboardRisiko
  risikoLoading?: boolean
}>(), {
  gesamtStats: () => [],
  bereiche: () => [],
  offenePunkte: () => [],
  schwelle: 5,
  fristenTab: false,
  fristen: () => [],
  dokFertig: 0,
  dokGesamt: 0,
  risiko: () => ({ gesamt: 0 }),
  risikoLoading: false,
})

defineEmits<{
  'open-bereich': [id: string]
  'open-luecken': []
  'open-punkt': [id: string]
  'open-fristen': [tab?: string]
  'open-dokumente': []
  'open-risiken': []
}>()

const dokFehlt = computed(() => Math.max(0, (props.dokGesamt || 0) - (props.dokFertig || 0)))
const dokPct = computed(() =>
  props.dokGesamt ? Math.round(((props.dokFertig || 0) / props.dokGesamt) * 100) : 0)
const fristenOffen = computed(() => props.fristen.length)
const fristenUeberfaellig = computed(() => props.fristen.filter(f => f.overdue).length)
</script>

<style scoped>
.module-dashboard { display: flex; flex-direction: column; gap: 16px; }

.dashboard {
  display: grid; grid-template-columns: 280px 1fr; gap: 16px;
}
.gauge-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 16px;
  display: flex; flex-direction: column; align-items: center;
}
.gauge-stats { margin-top: 12px; text-align: center; font-size: 12px; color: #666; }
.gauge-stats div { margin-bottom: 4px; }

.chapters-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px;
  align-content: start;
}
.empty-card {
  grid-column: 1 / -1; background: white; border: 1px dashed var(--color-border);
  border-radius: 8px; padding: 24px; text-align: center; color: #888; font-size: 13px;
}

/* KPI-Kacheln */
.kpi-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px;
}
.kpi-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
}
.kpi-card.clickable { cursor: pointer; transition: box-shadow .15s, border-color .15s; }
.kpi-card.clickable:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); border-color: #1565c0; }

.kpi-head { display: flex; align-items: center; gap: 8px; }
.kpi-icon { font-size: 16px; }
.kpi-title { font-size: 13px; font-weight: 600; color: #263238; }
.kpi-value { font-size: 30px; font-weight: 700; line-height: 1; color: #263238; }
.kpi-value.warn { color: #c62828; }
.kpi-value.ok { color: #2e7d32; }
.kpi-of { font-size: 16px; font-weight: 500; color: #90a4ae; margin-left: 4px; }
.kpi-sub { font-size: 11px; color: #607d8b; }
.kpi-sub.muted { color: #b0bec5; font-style: italic; }

.kpi-list { list-style: none; margin: 6px 0 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.kpi-item {
  display: flex; align-items: center; gap: 6px; padding: 4px 6px;
  background: #fff8e1; border-radius: 4px; cursor: pointer; font-size: 11px;
}
.kpi-item:hover { background: #fff3c4; }
.kpi-item.overdue { background: #ffebee; }
.kpi-item code { background: white; padding: 1px 5px; border-radius: 3px; font-size: 10px; }
.kpi-item-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kpi-item-meta { font-size: 10px; color: #666; white-space: nowrap; }
.kpi-item-meta.overdue { color: #c62828; font-weight: 600; }

.dok-bar { height: 6px; background: #eceff1; border-radius: 3px; overflow: hidden; margin-top: 4px; }
.dok-bar-fill { height: 100%; background: #1565c0; transition: width .3s ease-out; }

.sev-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.sev { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; }
.sev-kritisch { background: #b71c1c; color: #fff; }
.sev-hoch { background: #ffebee; color: #c62828; }
.sev-mittel { background: #fff3e0; color: #e65100; }
.sev-niedrig { background: #e8f5e9; color: #2e7d32; }

@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; }
}
</style>
