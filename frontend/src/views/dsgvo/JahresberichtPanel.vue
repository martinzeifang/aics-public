<template>
  <div class="jb-panel">
    <p v-if="!projektName" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar -->
      <div class="jb-toolbar">
        <div class="toolbar-info">
          <strong>📅 DSGVO-Jahresbericht</strong>
          <span v-if="report" class="muted">{{ report.projekt?.unternehmen || report.projekt?.name }} · {{ jahr }}</span>
        </div>
        <div class="toolbar-actions">
          <label class="jahr-label">Jahr
            <select v-model.number="jahr" class="jahr-select">
              <option v-for="j in jahrOptionen" :key="j" :value="j">{{ j }}</option>
            </select>
          </label>
          <button class="btn-secondary" :disabled="busy !== ''" @click="onExport('docx')">
            {{ busy === 'docx' ? '⏳…' : '📝 DOCX' }}
          </button>
          <button class="btn-secondary" :disabled="busy !== ''" @click="onExport('pdf')">
            {{ busy === 'pdf' ? '⏳…' : '📄 PDF' }}
          </button>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>
      <p v-if="store.error" class="error-msg">{{ store.error }}</p>

      <p v-if="loading" class="hint">⏳ Lädt Jahresbericht…</p>

      <template v-if="report && !loading">
        <!-- Sign-off -->
        <div class="signoff-card" :class="report.signoff?.status">
          <div class="signoff-head">
            <span class="signoff-label">Status</span>
            <span class="signoff-pill" :style="signoffStyle(report.signoff?.status)">
              {{ signoffLabel(report.signoff?.status) }}
            </span>
          </div>
          <div class="signoff-actions">
            <button
              class="btn-approve"
              :disabled="busy !== '' || report.signoff?.status !== 'entwurf' || !canApprove"
              :title="canApprove ? '' : 'Berechtigung dsgvo:approve erforderlich'"
              @click="onFreigeben"
            >
              {{ busy === 'freigeben' ? '⏳…' : '✅ Freigeben (Geschäftsführung)' }}
            </button>
            <button
              class="btn-sign"
              :disabled="busy !== '' || report.signoff?.status !== 'freigegeben' || !canSign"
              :title="canSign ? '' : 'Berechtigung dsgvo:sign erforderlich'"
              @click="onSignieren"
            >
              {{ busy === 'signieren' ? '⏳…' : '🖋️ Signieren (DSB)' }}
            </button>
          </div>
          <div class="signoff-trail">
            <div v-if="report.signoff?.freigabe_von">
              ✅ Freigegeben von <strong>{{ report.signoff.freigabe_von }}</strong> am {{ formatDate(report.signoff.freigabe_am) }}
            </div>
            <div v-if="report.signoff?.signatur_von">
              🖋️ Signiert von <strong>{{ report.signoff.signatur_name || report.signoff.signatur_von }}</strong>
              am {{ formatDate(report.signoff.signatur_am) }}
            </div>
            <div v-if="report.signoff?.sha256" class="sha">SHA-256: <code>{{ report.signoff.sha256 }}</code></div>
          </div>
        </div>

        <!-- Summary-Karten -->
        <div class="summary-grid">
          <div class="card">
            <div class="card-num">{{ report.kontrollen_summary?.abgeschlossen ?? 0 }} / {{ report.kontrollen_summary?.gesamt ?? 0 }}</div>
            <div class="card-lbl">Kontrollen abgeschlossen</div>
            <div class="card-sub">{{ report.kontrollen_summary?.offen ?? 0 }} offen</div>
          </div>
          <div class="card">
            <div class="card-num">{{ report.tom?.pct ?? 0 }}%</div>
            <div class="card-lbl">TOM-Reifegrad</div>
            <div class="card-sub">{{ report.tom?.umgesetzt ?? 0 }} / {{ report.tom?.gesamt ?? 0 }} umgesetzt</div>
          </div>
          <div class="card">
            <div class="card-num">{{ report.meta?.anzahl_dsfa ?? 0 }}</div>
            <div class="card-lbl">DSFA</div>
          </div>
          <div class="card">
            <div class="card-num">{{ report.meta?.anzahl_datenpannen ?? 0 }}</div>
            <div class="card-lbl">Datenpannen</div>
          </div>
          <div class="card">
            <div class="card-num">{{ report.meta?.anzahl_betroffenenrechte ?? 0 }}</div>
            <div class="card-lbl">Betroffenenrechte</div>
          </div>
          <div class="card">
            <div class="card-num">{{ report.meta?.anzahl_risiken ?? 0 }}</div>
            <div class="card-lbl">Offene Risiken</div>
          </div>
        </div>

        <!-- Abschnitte -->
        <details class="section" open>
          <summary>🗓️ Kontrollen ({{ report.kontrollen?.length || 0 }})</summary>
          <ul class="sec-list" v-if="report.kontrollen?.length">
            <li v-for="(k, i) in report.kontrollen" :key="i">
              <strong>{{ k.titel || k.kontroll_id }}</strong>
              <span class="muted">— {{ k.bereich }} · {{ k.status }}</span>
            </li>
          </ul>
          <p v-else class="muted empty-line">Keine Kontrollen.</p>
        </details>

        <details class="section">
          <summary>📋 DSFA ({{ report.dsfa?.length || 0 }})</summary>
          <ul class="sec-list" v-if="report.dsfa?.length">
            <li v-for="(d, i) in report.dsfa" :key="i">
              <strong>{{ d.titel || d.name || ('DSFA #' + (d.id ?? i)) }}</strong>
              <span class="muted" v-if="d.status">— {{ d.status }}</span>
            </li>
          </ul>
          <p v-else class="muted empty-line">Keine DSFA.</p>
        </details>

        <details class="section">
          <summary>🚨 Datenpannen ({{ report.datenpannen?.length || 0 }})</summary>
          <ul class="sec-list" v-if="report.datenpannen?.length">
            <li v-for="(d, i) in report.datenpannen" :key="i">
              <strong>{{ d.titel || d.beschreibung || ('Vorfall #' + (d.id ?? i)) }}</strong>
              <span class="muted" v-if="d.datum">— {{ d.datum }}</span>
            </li>
          </ul>
          <p v-else class="muted empty-line">Keine Datenpannen.</p>
        </details>

        <details class="section">
          <summary>📨 Betroffenenrechte ({{ report.betroffenenrechte?.length || 0 }})</summary>
          <ul class="sec-list" v-if="report.betroffenenrechte?.length">
            <li v-for="(b, i) in report.betroffenenrechte" :key="i">
              <strong>{{ b.art || b.titel || ('Antrag #' + (b.id ?? i)) }}</strong>
              <span class="muted" v-if="b.status">— {{ b.status }}</span>
            </li>
          </ul>
          <p v-else class="muted empty-line">Keine Anträge.</p>
        </details>

        <details class="section">
          <summary>✍️ Einwilligungs-Widerrufe ({{ report.einwilligung_widerrufe?.length || 0 }})</summary>
          <ul class="sec-list" v-if="report.einwilligung_widerrufe?.length">
            <li v-for="(e, i) in report.einwilligung_widerrufe" :key="i">
              <strong>{{ e.zweck || e.titel || ('Widerruf #' + (e.id ?? i)) }}</strong>
              <span class="muted" v-if="e.datum">— {{ e.datum }}</span>
            </li>
          </ul>
          <p v-else class="muted empty-line">Keine Widerrufe.</p>
        </details>

        <details class="section">
          <summary>⚠️ Offene Risiken ({{ report.risiken?.length || 0 }})</summary>
          <ul class="sec-list" v-if="report.risiken?.length">
            <li v-for="(r, i) in report.risiken" :key="i">
              <span class="schwere-tag" :style="schwereStyle(r.schwere)">{{ r.schwere }}</span>
              <strong>{{ r.titel }}</strong>
              <span class="muted">— {{ r.quelle }}<span v-if="r.projekt"> · {{ r.projekt }}</span></span>
            </li>
          </ul>
          <p v-else class="muted empty-line">Keine offenen Risiken.</p>
        </details>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoKontrollenStore, type Jahresbericht } from '../../stores/dsgvoKontrollen'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{ projektName: string }>()
const store = useDsgvoKontrollenStore()
const auth = useAuthStore()

const projektName = computed(() => props.projektName)
const canApprove = computed(() => auth.hasPermission('dsgvo:approve'))
const canSign = computed(() => auth.hasPermission('dsgvo:sign'))

const currentYear = new Date().getFullYear()
const jahr = ref<number>(currentYear)
const jahrOptionen = computed(() => {
  const arr: number[] = []
  for (let y = currentYear + 1; y >= currentYear - 5; y--) arr.push(y)
  return arr
})

const report = ref<Jahresbericht | null>(null)
const loading = ref(false)
const busy = ref<'' | 'docx' | 'pdf' | 'freigeben' | 'signieren'>('')
const message = ref('')

const SIGNOFF_LABELS: Record<string, string> = {
  entwurf: 'Entwurf', freigegeben: 'Freigegeben', signiert: 'Signiert',
}
const SIGNOFF_COLORS: Record<string, { bg: string; fg: string }> = {
  entwurf: { bg: '#eceff1', fg: '#546e7a' },
  freigegeben: { bg: '#fff8e1', fg: '#e65100' },
  signiert: { bg: '#e8f5e9', fg: '#2e7d32' },
}
const signoffLabel = (s?: string) => SIGNOFF_LABELS[s || 'entwurf'] || 'Entwurf'
const signoffStyle = (s?: string) => {
  const c = SIGNOFF_COLORS[s || 'entwurf'] || SIGNOFF_COLORS.entwurf
  return { background: c.bg, color: c.fg }
}

const schwereStyle = (s?: string): Record<string, string> => {
  const v = (s || '').toLowerCase()
  if (v.includes('hoch') || v.includes('critical') || v.includes('kritisch')) return { background: '#ffebee', color: '#c62828' }
  if (v.includes('mittel') || v.includes('medium')) return { background: '#fff3e0', color: '#e65100' }
  return { background: '#e8f5e9', color: '#2e7d32' }
}

const formatDate = (s?: string | null): string => {
  if (!s) return '—'
  try { return new Date(s).toLocaleString('de-DE') } catch { return s }
}

const flash = (text: string) => {
  message.value = text
  setTimeout(() => { if (message.value === text) message.value = '' }, 4000)
}

async function load() {
  if (!projektName.value) return
  loading.value = true
  store.error = ''
  try {
    report.value = await store.fetchJahresbericht(projektName.value, jahr.value)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(projektName, load)
watch(jahr, load)

async function onExport(format: 'docx' | 'pdf') {
  busy.value = format
  try {
    const res = await store.exportJahresbericht(projektName.value, jahr.value, format)
    if (res.ok) flash(`${format.toUpperCase()} heruntergeladen.`)
  } finally { busy.value = '' }
}

async function onFreigeben() {
  busy.value = 'freigeben'
  try {
    const so = await store.freigebenJahresbericht(projektName.value, jahr.value)
    if (so && report.value) { report.value.signoff = so; flash('Bericht freigegeben.') }
  } finally { busy.value = '' }
}

async function onSignieren() {
  const name = prompt('Name der signierenden Person (DSB):', report.value?.projekt?.berater || '')
  if (name === null) return
  if (!name.trim()) { store.error = 'Name ist Pflicht.'; return }
  busy.value = 'signieren'
  try {
    const so = await store.signierenJahresbericht(projektName.value, jahr.value, name.trim())
    if (so && report.value) { report.value.signoff = so; flash('Bericht signiert.') }
  } finally { busy.value = '' }
}
</script>

<style scoped>
.jb-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.muted { color: #888; font-size: 12px; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.error-msg { background: #ffebee; color: #c62828; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }

.jb-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.jahr-label { font-size: 13px; color: #555; display: flex; align-items: center; gap: 6px; }
.jahr-select { padding: 6px 8px; border: 1px solid var(--color-border, #e0e0e0); border-radius: 4px; font-size: 13px; }

.signoff-card { background: white; border: 1px solid var(--color-border, #e0e0e0); border-left: 4px solid #546e7a; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px; }
.signoff-card.freigegeben { border-left-color: #e65100; }
.signoff-card.signiert { border-left-color: #2e7d32; }
.signoff-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.signoff-label { font-size: 12px; text-transform: uppercase; color: #888; font-weight: 600; }
.signoff-pill { padding: 3px 12px; border-radius: 12px; font-size: 12px; font-weight: 700; }
.signoff-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.signoff-trail { font-size: 12px; color: #555; display: flex; flex-direction: column; gap: 4px; }
.signoff-trail .sha { color: #888; word-break: break-all; }
.signoff-trail code { font-family: monospace; font-size: 11px; }

.summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-bottom: 18px; }
.card { background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px; padding: 14px 16px; text-align: center; }
.card-num { font-size: 26px; font-weight: 700; color: #1565c0; }
.card-lbl { font-size: 12px; color: #555; margin-top: 4px; }
.card-sub { font-size: 11px; color: #999; margin-top: 2px; }

.section { background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px; padding: 10px 16px; margin-bottom: 10px; }
.section summary { font-weight: 600; cursor: pointer; color: #1565c0; font-size: 14px; padding: 4px 0; }
.sec-list { list-style: none; margin: 8px 0 4px; padding: 0; }
.sec-list li { padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.empty-line { padding: 6px 0; }
.schwere-tag { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; }

.btn-secondary, .btn-approve, .btn-sign { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-approve { background: #2e7d32; color: white; }
.btn-sign { background: #1565c0; color: white; }
.btn-secondary:disabled, .btn-approve:disabled, .btn-sign:disabled { opacity: 0.55; cursor: not-allowed; }
</style>
