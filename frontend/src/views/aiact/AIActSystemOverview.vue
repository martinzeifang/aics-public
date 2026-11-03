<template>
  <!-- #1562: Organisation mit KI-Systemen — Übersicht statt System-Dashboard -->
  <div class="sys-overview">
    <div class="intro">
      <h3>🏢 Organisation {{ firma }}</h3>
      <p class="muted">
        Systembezogene Pflichten (Risikoklasse, Art. 5, Art. 9–15, FRIA, Konformität, Vorfälle,
        OWASP-LLM) werden <strong>je KI-System</strong> geführt. In der Organisation liegen die
        firmenweiten Bereiche: AI-Literacy (Art. 4), Dokumente und Berichte.
      </p>
    </div>

    <div class="grid">
      <button v-for="s in rows" :key="s.name" class="card" @click="$emit('open', s.name)">
        <div class="card-head">🤖 {{ s.produkt || s.name }}</div>
        <div v-if="s.loading" class="muted">Lädt…</div>
        <template v-else>
          <div class="pct" :style="{ color: color(s.pct) }">{{ s.pct }} %</div>
          <div class="bar"><span :style="{ width: s.pct + '%', background: color(s.pct) }" /></div>
          <div class="muted small">{{ s.bewertet }} / {{ s.gesamt }} Anforderungen bewertet</div>
        </template>
        <div class="open">Öffnen →</div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import apiClient from '../../api/client'

const props = defineProps<{ firma: string; systeme: Array<{ name: string; produkt: string }> }>()
defineEmits<{ (e: 'open', name: string): void }>()

type Row = { name: string; produkt: string; loading: boolean; pct: number; bewertet: number; gesamt: number }
const rows = ref<Row[]>([])

const color = (p: number) => (p >= 75 ? '#2e7d32' : p >= 40 ? '#ef6c00' : '#c62828')

async function load() {
  rows.value = props.systeme.map(s => ({ ...s, loading: true, pct: 0, bewertet: 0, gesamt: 0 }))
  await Promise.all(rows.value.map(async (r) => {
    try {
      const d = (await apiClient.get(`/aiact/projekte/${encodeURIComponent(r.name)}/reifegrad`)).data || {}
      r.pct = Math.round(Number(d.gesamt_pct ?? 0))
      r.bewertet = Number(d.bewertete_count ?? 0)
      r.gesamt = Number(d.gesamt_count ?? 0)
    } catch { /* Reifegrad optional */ }
    r.loading = false
  }))
}

watch(() => props.systeme.map(s => s.name).join('|'), load, { immediate: true })
</script>

<style scoped>
.sys-overview { display: flex; flex-direction: column; gap: 16px; }
.intro h3 { margin: 0 0 6px; color: #1565c0; }
.muted { color: #666; font-size: 13px; }
.small { font-size: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.card {
  text-align: left; background: white; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 14px; cursor: pointer; display: flex; flex-direction: column; gap: 6px; font: inherit;
}
.card:hover { border-color: #1565c0; box-shadow: 0 2px 8px rgba(21, 101, 192, .12); }
.card-head { font-weight: 600; color: #333; }
.pct { font-size: 26px; font-weight: 700; }
.bar { height: 6px; background: #eee; border-radius: 3px; overflow: hidden; }
.bar span { display: block; height: 100%; }
.open { color: #1565c0; font-size: 12px; margin-top: 4px; }
</style>
