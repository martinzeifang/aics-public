<template>
  <!-- #1569: Firmen-Ebene über den Produktprojekten (CRA/Risikobewertung) —
       analog AI-Act-Organisation (#1562). Das Risiko-Cockpit lebt nur hier. -->
  <div class="firma-overview">
    <div class="intro">
      <h3>🏢 {{ firma || $t('ansichten.firmaOverview.ohneFirma') }}</h3>
      <p class="muted">
        {{ modul === 'cra'
          ? $t('ansichten.firmaOverview.cRAPflichtenWerdenJeProduktGefuhrtHi')
          : $t('ansichten.firmaOverview.risikobewertungenWerdenJeProduktBzwA') }}
      </p>
    </div>

    <div class="tabs" role="tablist">
      <button :class="['tab', { active: tab === 'produkte' }]" @click="$emit('update:tab', 'produkte')">
        {{ $t('ansichten.firmaOverview.produkteV0', { v0: projekte.length }) }}
      </button>
      <button :class="['tab', { active: tab === 'cockpit' }]" @click="$emit('update:tab', 'cockpit')">
        {{ $t('ansichten.firmaOverview.risikoCockpit') }}<span v-if="openTotal"> ({{ openTotal }})</span>
      </button>
    </div>

    <div v-if="tab === 'produkte'" class="grid">
      <button v-for="r in rows" :key="r.name" class="card" @click="$emit('open', r.name)">
        <div class="card-head">📦 {{ r.produkt || r.name }}</div>
        <div v-if="r.produkt && r.produkt !== r.name" class="muted small name">{{ r.name }}</div>
        <div v-if="r.sub" class="sub">{{ r.sub }}</div>
        <template v-if="modul === 'cra'">
          <div v-if="r.loading" class="muted">{{ $t('common.loading') }}</div>
          <template v-else>
            <div class="pct" :style="{ color: color(r.pct) }">{{ r.pct }} %</div>
            <div class="bar"><span :style="{ width: r.pct + '%', background: color(r.pct) }" /></div>
            <div class="muted small">{{ $t('ansichten.firmaOverview.reifegrad') }}</div>
          </template>
        </template>
        <template v-else>
          <div class="count">{{ r.count }}</div>
          <div class="muted small">{{ r.count === 1 ? $t('ansichten.firmaOverview.risiko') : $t('ansichten.firmaOverview.risiken') }} erfasst</div>
        </template>
        <div class="risks">
          <span v-if="r.open" :class="['sev', r.worst]">{{ r.open }} offen · {{ SEV[r.worst] }}</span>
          <span v-else-if="!cockpitLoading" class="sev none">{{ $t('ansichten.firmaOverview.keineOffenenRisiken') }}</span>
        </div>
        <div class="open">{{ $t('common.offnen') }}</div>
      </button>
      <div v-if="!projekte.length" class="muted">{{ $t('ansichten.firmaOverview.keineProjekteFurDieseFirma') }}</div>
    </div>

    <div v-else class="cockpit">
      <div v-if="cockpitLoading" class="muted">{{ $t('ansichten.firmaOverview.ladeRisikoCockpit') }}</div>
      <RiskCockpit v-else-if="firmenId != null" :firmen-id="firmenId" />
      <div v-else class="hint">
        {{ $t('ansichten.firmaOverview.dieFirmaIstInDerFirmenverwaltungNich') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import apiClient from '../../api/client'
import RiskCockpit from './RiskCockpit.vue'

type Projekt = { name: string; produkt?: string; sub?: string; count?: number }

const props = defineProps<{
  modul: 'cra' | 'risikobewertung'
  firma: string
  projekte: Projekt[]
  tab: 'produkte' | 'cockpit'
}>()
defineEmits<{
  (e: 'open', name: string): void
  (e: 'update:tab', tab: 'produkte' | 'cockpit'): void
}>()

const SEV: Record<string, string> = {
  critical: 'kritisch', high: 'hoch', medium: 'mittel', low: 'gering', unknown: 'unbewertet',
}
const RANK = ['unknown', 'low', 'medium', 'high', 'critical']

type Row = Projekt & { loading: boolean; pct: number; open: number; worst: string; count: number }
const rows = ref<Row[]>([])
const firmenId = ref<number | null>(null)
const cockpitLoading = ref(false)
const items = ref<Array<{ projekt: string; severity: string }>>([])

const openTotal = computed(() => items.value.length)
const color = (p: number) => (p >= 75 ? '#2e7d32' : p >= 40 ? '#ef6c00' : '#c62828')

function applyRisks() {
  for (const r of rows.value) {
    const mine = items.value.filter(i => i.projekt === r.name)
    r.open = mine.length
    r.worst = mine.reduce((w, i) => (RANK.indexOf(i.severity) > RANK.indexOf(w) ? i.severity : w), 'unknown')
  }
}

async function loadCockpit() {
  firmenId.value = null
  items.value = []
  const first = props.projekte[0]?.name
  if (!first) return
  cockpitLoading.value = true
  try {
    // firmen_id über ein beliebiges Produktprojekt der Firma auflösen (S1-FK).
    const d = (await apiClient.get(
      `/risk-cockpit/by-projekt/${props.modul}/${encodeURIComponent(first)}`)).data || {}
    if (d.firmen_id != null && !d.unassigned) {
      firmenId.value = Number(d.firmen_id)
      items.value = Array.isArray(d.items) ? d.items : []
    }
  } catch { /* Cockpit optional */ }
  cockpitLoading.value = false
  applyRisks()
}

async function loadReifegrad() {
  if (props.modul !== 'cra') return
  await Promise.all(rows.value.map(async (r) => {
    try {
      const d = (await apiClient.get(`/cra/projekte/${encodeURIComponent(r.name)}/reifegrad`)).data || {}
      r.pct = Math.round(Number(d.gesamt?.prozent ?? d.gesamt_pct ?? 0))
    } catch { /* Reifegrad optional */ }
    r.loading = false
  }))
}

async function load() {
  rows.value = props.projekte.map(p => ({
    ...p, loading: props.modul === 'cra', pct: 0, open: 0, worst: 'unknown', count: p.count ?? 0,
  }))
  await Promise.all([loadReifegrad(), loadCockpit()])
}

watch(() => props.firma + '|' + props.projekte.map(p => p.name).join('|'), load, { immediate: true })
</script>

<style scoped>
.firma-overview { display: flex; flex-direction: column; gap: 16px; }
.intro h3 { margin: 0 0 6px; color: #1565c0; }
.muted { color: #666; font-size: 13px; }
.small { font-size: 12px; }
.name { margin-top: -4px; }
.tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--color-border); }
.tab {
  background: none; border: none; border-bottom: 2px solid transparent; padding: 8px 14px;
  font: inherit; font-size: 13px; cursor: pointer; color: #555;
}
.tab.active { border-bottom-color: #1565c0; color: #1565c0; font-weight: 600; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }
.card {
  text-align: left; background: white; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 14px; cursor: pointer; display: flex; flex-direction: column; gap: 6px; font: inherit;
}
.card:hover { border-color: #1565c0; box-shadow: 0 2px 8px rgba(21, 101, 192, .12); }
.card-head { font-weight: 600; color: #333; }
.sub { font-size: 11px; color: #1565c0; font-weight: 600; }
.pct, .count { font-size: 26px; font-weight: 700; }
.count { color: #333; }
.bar { height: 6px; background: #eee; border-radius: 3px; overflow: hidden; }
.bar span { display: block; height: 100%; }
.risks { margin-top: 2px; }
.sev { display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; }
.sev.critical { background: #ffebee; color: #b71c1c; }
.sev.high { background: #fff3e0; color: #e65100; }
.sev.medium { background: #fffde7; color: #f57f17; }
.sev.low { background: #e8f5e9; color: #2e7d32; }
.sev.unknown { background: #eceff1; color: #455a64; }
.sev.none { background: #f5f5f5; color: #777; font-weight: 500; }
.open { color: #1565c0; font-size: 12px; margin-top: 4px; }
.hint { background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px; padding: 12px; font-size: 13px; }
</style>
