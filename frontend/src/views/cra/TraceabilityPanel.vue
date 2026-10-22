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
              <template v-if="b.nachweis_count">
                <div v-for="n in b.nachweise" :key="(n.id ?? '') + '|' + n.doc_name" class="nachweis">
                  <span class="quelle" :title="n.doc_type">{{ quelleBadge(n) }}</span>
                  <a v-if="oeffenbar(n)" href="#" @click.prevent="oeffneNachweis(n)">{{ n.doc_name }}</a>
                  <span v-else>{{ n.doc_name }}</span>
                  <span v-if="n.herkunft === 'auto'" class="auto-tag" title="automatisch aus der Anwendung erkannt">auto</span>
                </div>
              </template>
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

// #1603: Nachweise einzeln sichtbar + öffenbar machen (Quelle erkennbar, mehrere je Baustein).
function quelleBadge(n: any): string {
  if (n.quelle) return n.quelle            // #1606: Auto-Beleg bringt seine Quelle mit
  const t = String(n.doc_type || '').toLowerCase()
  if (t === 'pentest') return '🛡️ Pentest'
  if (String(n.doc_path || '').startsWith('http')) return '🔗 Link'
  if (t.includes('sbom')) return '📦 SBOM'
  return '📄 Doku'
}
function oeffenbar(n: any): boolean {
  const p = String(n.doc_path || '')
  if (p.startsWith('http')) return true                 // #1606 Deep-Link/externer Link
  return !!n.id && p.startsWith('evidence:')             // #1603 Evidence-Download
}
async function oeffneNachweis(n: any) {
  const p = String(n.doc_path || '')
  if (p.startsWith('http')) { window.open(p, '_blank', 'noopener'); return }
  try {
    const r = await apiClient.get(
      `/cra-traceability/projekte/${encodeURIComponent(props.projekt)}/dokumente/${n.id}/download`,
      { responseType: 'blob' })
    const url = URL.createObjectURL(r.data as Blob)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch { /* Fehler still — Nachweis evtl. interner Verweis */ }
}

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
.nachweis { display: flex; align-items: baseline; gap: 6px; margin: 2px 0; }
.nachweis .quelle { font-size: 11px; color: #546e7a; white-space: nowrap; }
.nachweis a { color: #1565c0; cursor: pointer; }
.nachweis .auto-tag { font-size: 9px; background: #eef5ff; color: #2b6cb0; border: 1px solid #cfe0f5;
  border-radius: 8px; padding: 0 5px; text-transform: uppercase; letter-spacing: .4px; }
</style>
