<template>
  <div class="soc-sidebar">
    <div class="sidebar-header"><h2>SOC-Lage</h2></div>
    <div class="kpi-mini">
      <div><b>{{ store.kpis.alerts_new ?? '–' }}</b><span>neue Alarme</span></div>
      <div><b>{{ store.kpis.incidents_open ?? '–' }}</b><span>offene Incidents</span></div>
    </div>
    <div class="sidebar-header"><h2>Offene Incidents</h2></div>
    <div class="sidebar-list">
      <div v-for="i in openIncidents" :key="i.id" class="sidebar-item" @click="store.getIncident(i.id)">
        <div class="inc-title">#{{ i.id }} {{ i.titel }}</div>
        <div class="inc-meta"><span class="pill" :class="i.severity">{{ i.severity }}</span> {{ i.status }}</div>
      </div>
      <div v-if="!openIncidents.length" class="sidebar-empty">Keine offenen Incidents.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSocStore } from '../../stores/soc'

const store = useSocStore()
const OPEN = ['new', 'in_review', 'confirmed', 'contained', 'eradicated', 'reopened']
const openIncidents = computed(() => (store.incidents as any[]).filter(i => OPEN.includes(i.status)))

onMounted(async () => {
  try { await store.fetchKpis(); await store.fetchIncidents() } catch { /* ignore */ }
})
</script>

<style scoped>
.soc-sidebar { display: flex; flex-direction: column; height: 100%; }
.sidebar-header { padding: 14px 16px; border-bottom: 1px solid #e0e0e0; }
.sidebar-header h2 { font-size: 15px; margin: 0; color: #1565c0; }
.kpi-mini { display: flex; gap: 8px; padding: 12px 16px; }
.kpi-mini div { flex: 1; text-align: center; background: #f5f5f5; border-radius: 6px; padding: 8px; }
.kpi-mini b { display: block; font-size: 20px; color: #1565c0; }
.kpi-mini span { font-size: 11px; color: #777; }
.sidebar-list { overflow-y: auto; flex: 1; }
.sidebar-item { padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
.sidebar-item:hover { background: #e3f2fd; }
.inc-title { font-size: 13px; font-weight: 500; }
.inc-meta { font-size: 11px; color: #777; margin-top: 2px; }
.pill { padding: 1px 6px; border-radius: 8px; color: #fff; font-size: 10px; text-transform: uppercase; }
.pill.critical { background: #b71c1c; } .pill.high { background: #e65100; }
.pill.medium { background: #f9a825; color:#333; } .pill.low { background: #607d8b; }
.sidebar-empty { padding: 16px; color: #999; font-size: 13px; }
</style>
