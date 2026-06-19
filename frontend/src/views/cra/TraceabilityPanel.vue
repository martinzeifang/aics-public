<template>
  <div class="trace-panel">
    <div class="panel-header">
      <h3>🔗 Art. 13(1) / Annex VII — Traceability & Vollständigkeitsmatrix</h3>
      <p class="sub">Nachweis↔Anforderung-Verknüpfung · granulare Annex-VII-Content-Matrix
        mit belegt/fehlt-Ampel</p>
    </div>

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <!-- Nachweis erfassen + zuordnen -->
    <div class="form-card">
      <h4>Nachweis erfassen & zuordnen</h4>
      <div class="form-grid">
        <div class="form-row">
          <label>Bezeichnung</label>
          <input v-model="form.doc_name" placeholder="z.B. Pentest-Bericht 2026" />
        </div>
        <div class="form-row">
          <label>Dokument-Typ</label>
          <input v-model="form.doc_type" placeholder="z.B. testbericht, sbom, doc" />
        </div>
        <div class="form-row">
          <label>Anforderung-ID</label>
          <input v-model="form.anforderung_id" placeholder="z.B. ART13-01" />
        </div>
        <div class="form-row">
          <label>Annex-VII-Baustein</label>
          <select v-model="form.annex_baustein">
            <option value="">— optional —</option>
            <option v-for="b in bausteine" :key="b.key" :value="b.key">{{ b.label }}</option>
          </select>
        </div>
      </div>
      <button class="btn-primary" @click="create">Nachweis anlegen</button>
    </div>

    <!-- Annex-VII-Vollständigkeitsmatrix -->
    <div class="form-card" v-if="store.annex">
      <h4>Annex-VII-Vollständigkeitsmatrix</h4>
      <div class="quote">
        <span :class="['pill', store.annex.vollstaendig ? 'ok' : 'warn']">
          {{ store.annex.belegt_count }} / {{ store.annex.gesamt_count }} belegt
          ({{ store.annex.vollstaendigkeit_pct }} %)
        </span>
      </div>
      <table class="matrix">
        <thead><tr><th>Baustein</th><th>Nachweise</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="b in store.annex.bausteine" :key="b.key">
            <td>{{ b.label }}</td>
            <td>
              <span v-if="b.nachweis_count">{{ b.nachweise.map(n => n.doc_name).join(', ') }}</span>
              <span v-else class="muted">—</span>
            </td>
            <td><span :class="['pill', b.ampel === 'belegt' ? 'ok' : 'fehlt']">{{ b.ampel }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Per-Requirement Traceability -->
    <div class="form-card">
      <h4>Nachweis↔Anforderung ({{ belegtCount }} / {{ store.requirements.length }} belegt)</h4>
      <table class="matrix">
        <thead><tr><th>Anforderung</th><th>Titel</th><th>Nachweise</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="r in store.requirements" :key="r.anforderung_id">
            <td>{{ r.anforderung_id }}</td>
            <td class="titel">{{ r.titel }}</td>
            <td>{{ r.nachweis_count }}<span v-if="r.hat_bewertung" class="muted"> · Bewertung</span></td>
            <td><span :class="['pill', r.ampel === 'belegt' ? 'ok' : 'fehlt']">{{ r.ampel }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCraTraceabilityStore } from '../../stores/craTraceability'
import apiClient from '../../api/client'

const props = defineProps<{ projekt: string }>()
const store = useCraTraceabilityStore()

const bausteine = ref<{ key: string; label: string }[]>([])
const empty = () => ({ doc_name: '', doc_type: 'resource', anforderung_id: '', annex_baustein: '' })
const form = ref<any>(empty())

const belegtCount = computed(() =>
  store.requirements.filter(r => r.ampel === 'belegt').length)

async function create() {
  if (await store.createDokument(props.projekt, { ...form.value })) form.value = empty()
}

async function loadConstants() {
  try {
    const { data } = await apiClient.get('/cra-traceability/constants')
    bausteine.value = data.annex_vii_bausteine || []
  } catch { /* ignore */ }
}

async function load() {
  await store.fetchAll(props.projekt)
}
onMounted(async () => { await loadConstants(); await load() })
watch(() => props.projekt, load)
</script>

<style scoped>
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-card h4 { color: #1565c0; margin: 0 0 10px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; }
.matrix { width: 100%; border-collapse: collapse; font-size: 13px; }
.matrix th, .matrix td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e0e6ee; }
.matrix th { color: #455a64; }
.matrix .titel { color: #455a64; }
.pill { padding: 2px 8px; border-radius: 10px; font-size: 11px; }
.pill.ok { background: #e8f5e9; color: #2e7d32; }
.pill.warn { background: #fff3e0; color: #ef6c00; }
.pill.fehlt { background: #ffebee; color: #c62828; }
.quote { margin-bottom: 8px; }
.muted { color: #90a4ae; }
</style>
