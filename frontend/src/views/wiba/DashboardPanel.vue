<template>
  <div class="wiba-dashboard">
    <!-- Gesamt-Reifegrad -->
    <div class="dash-grid">
      <div class="gauge-card">
        <div class="gauge-big" :style="{ color: pctColor(gesamtPct) }">{{ gesamtPct }}%</div>
        <div class="gauge-label">Gesamt-Reifegrad</div>
        <div class="gauge-bar">
          <div class="gauge-fill" :style="{ width: gesamtPct + '%', background: pctColor(gesamtPct) }"></div>
        </div>
        <div class="gauge-stats">
          <span>{{ bewertet }} / {{ inScope }} Prüffragen bewertet</span>
        </div>
      </div>

      <div class="counters">
        <div class="counter ja">
          <span class="num">{{ totals.ja }}</span>
          <span class="lbl">✅ Ja</span>
        </div>
        <div class="counter nein">
          <span class="num">{{ totals.nein }}</span>
          <span class="lbl">❌ Nein</span>
        </div>
        <div class="counter offen">
          <span class="num">{{ totals.offen }}</span>
          <span class="lbl">⏳ Offen</span>
        </div>
        <div class="counter nr">
          <span class="num">{{ totals.nicht_relevant }}</span>
          <span class="lbl">➖ Nicht relevant</span>
        </div>
      </div>
    </div>

    <!-- Pro-Thema-Balken -->
    <div class="themen-card">
      <h3>📊 Reifegrad je Thema</h3>
      <div v-if="themenList.length === 0" class="empty">Noch keine Themen geladen.</div>
      <div v-else class="thema-rows">
        <div v-for="t in themenList" :key="t.key" class="thema-row">
          <div class="thema-name" :title="t.titel">{{ t.titel }}</div>
          <div class="thema-bar">
            <div class="thema-fill" :style="{ width: t.pct + '%', background: pctColor(t.pct) }"></div>
          </div>
          <div class="thema-pct">{{ t.pct }}%</div>
          <div class="thema-meta">{{ t.ja + t.nein + t.nicht_relevant }}/{{ t.total }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useWibaStore } from '../../stores/wiba'

const store = useWibaStore()

const gesamtPct = computed(() => Math.round(store.reifegrad?.gesamt_pct ?? 0))
const bewertet = computed(() => store.reifegrad?.bewertet ?? 0)
const inScope = computed(() => store.reifegrad?.in_scope ?? 0)

const themenList = computed(() => {
  const t = store.reifegrad?.themen || {}
  return Object.entries(t).map(([key, v]: [string, any]) => ({
    key,
    titel: v.titel || key,
    total: v.total ?? 0,
    ja: v.ja ?? 0,
    nein: v.nein ?? 0,
    offen: v.offen ?? 0,
    nicht_relevant: v.nicht_relevant ?? 0,
    pct: Math.round(v.pct ?? 0),
  }))
})

const totals = computed(() => {
  const acc = { ja: 0, nein: 0, offen: 0, nicht_relevant: 0 }
  for (const t of themenList.value) {
    acc.ja += t.ja
    acc.nein += t.nein
    acc.offen += t.offen
    acc.nicht_relevant += t.nicht_relevant
  }
  return acc
})

const pctColor = (p: number): string => {
  if (p >= 80) return '#2e7d32'
  if (p >= 50) return '#f57f17'
  if (p > 0) return '#e65100'
  return '#9e9e9e'
}
</script>

<style scoped>
.wiba-dashboard { display: flex; flex-direction: column; gap: 16px; }

.dash-grid { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }

.gauge-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 24px; display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.gauge-big { font-size: 56px; font-weight: 800; line-height: 1; }
.gauge-label { font-size: 14px; color: #555; font-weight: 600; }
.gauge-bar {
  width: 100%; height: 10px; background: #eee; border-radius: 6px; overflow: hidden; margin-top: 4px;
}
.gauge-fill { height: 100%; border-radius: 6px; transition: width 0.3s; }
.gauge-stats { font-size: 12px; color: #888; margin-top: 4px; }

.counters {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;
}
.counter {
  background: white; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 18px; display: flex; flex-direction: column; gap: 4px; align-items: flex-start;
}
.counter .num { font-size: 30px; font-weight: 700; }
.counter .lbl { font-size: 13px; color: #555; }
.counter.ja { border-left: 4px solid #2e7d32; }
.counter.nein { border-left: 4px solid #c62828; }
.counter.offen { border-left: 4px solid #f57f17; }
.counter.nr { border-left: 4px solid #9e9e9e; }

.themen-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 16px 20px;
}
.themen-card h3 { margin: 0 0 12px; font-size: 16px; }
.empty { padding: 24px; text-align: center; color: #888; }

.thema-rows { display: flex; flex-direction: column; gap: 8px; }
.thema-row {
  display: grid; grid-template-columns: 240px 1fr 48px 64px; align-items: center; gap: 12px;
}
.thema-name {
  font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.thema-bar { height: 12px; background: #eee; border-radius: 6px; overflow: hidden; }
.thema-fill { height: 100%; border-radius: 6px; transition: width 0.3s; }
.thema-pct { font-size: 13px; font-weight: 700; text-align: right; }
.thema-meta { font-size: 11px; color: #888; text-align: right; }

@media (max-width: 768px) {
  .dash-grid { grid-template-columns: 1fr; }
  .thema-row { grid-template-columns: 1fr 60px; }
  .thema-bar, .thema-meta { display: none; }
}
</style>
