<!--
  ReportCenterPanel (Sprint #35, #1381) — einheitliches Berichts-Center für alle
  Module (Vorbild SOC, #1350). Gleiche Optik/UX überall:
  - optionaler Zeitraum-Picker (Presets 30/90 Tage · Quartal · Jahr · Custom)
  - Berichtstyp-Karten mit 📝 Word / 📄 PDF je Typ
  - Historie erzeugter Berichte (Download)

  Backend-Vertrag (über :mod:`shared.reports.api`):
    GET  {apiBase}/berichte                       → { reports:[{key,titel,norm,beschreibung}], runs:[…], zeitraum:bool }
    GET  {apiBase}/berichte/<typ>?format&von&bis  → Datei (Ad-hoc-Download)
    POST {apiBase}/berichte/<typ>/generate        → { ok, id, dateiname }  (speichert + protokolliert)
    GET  {apiBase}/berichte/runs/<id>/download    → Datei (aus Historie)

  Props:
    apiBase   — z. B. '/cra/projekte/<p>' (projektbezogen) oder '/soc' (global)
    title     — Überschrift (Default 'Berichts-Center')
-->
<template>
  <div class="report-center">
    <div class="rc-head">
      <h3>📑 {{ title }}</h3>
      <button v-if="kiSummary" class="rc-summary-btn" @click="openSummary">
        🧭 KI-Management-Zusammenfassung
      </button>
      <button class="rc-refresh" :disabled="loading" @click="load">↻ Aktualisieren</button>
    </div>
    <p v-if="error" class="rc-error">{{ error }}</p>

    <!-- #1393: KI-Management-Zusammenfassung (mit Datenübermittlungs-Bestätigung #1380) -->
    <div v-if="summary.open" class="rc-modal-overlay" @mousedown.self="summary.open = false">
      <div class="rc-modal">
        <div class="rc-modal-head">
          <h4>🧭 KI-Management-Zusammenfassung</h4>
          <button class="rc-modal-close" @click="summary.open = false">✕</button>
        </div>
        <div class="rc-modal-body">
          <DataPreviewWarning
            v-if="!summary.confirmed"
            :fields="[{ label: 'Projekt', value: projektHint }, { label: 'Daten', value: 'Reifegrad-Kennzahlen + offene Punkte' }]"
            :provider="aiProvider"
            @confirm="summary.confirmed = true"
          />
          <template v-else>
            <KiStreamView :url="`/api${apiBase}/berichte/ki-summary/stream`" :body="{}" />
            <p class="llm-note">🤖 KI-generiert — fachlich zu prüfen.</p>
          </template>
        </div>
      </div>
    </div>

    <!-- Zeitraum -->
    <div v-if="zeitraum" class="rc-zeitraum">
      <label>Zeitraum
        <select v-model="preset" @change="applyPreset">
          <option value="30">Letzte 30 Tage</option>
          <option value="90">Letzte 90 Tage</option>
          <option value="quartal">Letztes Quartal</option>
          <option value="jahr">Letztes Jahr</option>
          <option value="custom">Benutzerdefiniert</option>
        </select>
      </label>
      <label>Von <input type="date" v-model="von" @change="preset = 'custom'" /></label>
      <label>Bis <input type="date" v-model="bis" @change="preset = 'custom'" /></label>
    </div>

    <!-- Berichtstypen -->
    <div v-if="reports.length" class="rc-cards">
      <div v-for="r in reports" :key="r.key" class="rc-card">
        <div class="rc-card-title">{{ r.titel }}</div>
        <div v-if="r.norm" class="rc-card-norm">{{ r.norm }}</div>
        <p v-if="r.beschreibung" class="rc-card-desc">{{ r.beschreibung }}</p>
        <div class="rc-card-actions">
          <button class="primary" :disabled="busy === r.key + ':docx'" @click="download(r.key, 'docx')">
            {{ busy === r.key + ':docx' ? '⏳ …' : '📝 Word' }}
          </button>
          <button :disabled="busy === r.key + ':pdf'" @click="download(r.key, 'pdf')">
            {{ busy === r.key + ':pdf' ? '⏳ …' : '📄 PDF' }}
          </button>
          <button class="rc-save" :disabled="busy === r.key + ':gen'" title="Erzeugen + in der Historie ablegen"
                  @click="generate(r.key)">
            {{ busy === r.key + ':gen' ? '⏳ …' : '💾 Ablegen' }}
          </button>
        </div>
      </div>
    </div>
    <p v-else-if="!loading" class="rc-empty">Keine Berichtstypen verfügbar.</p>

    <!-- Historie -->
    <div class="rc-history">
      <h4>📂 Erzeugte Berichte <span class="rc-count">({{ runs.length }})</span></h4>
      <table v-if="runs.length" class="rc-table">
        <thead><tr><th>Datum</th><th>Typ</th><th>Zeitraum</th><th>Format</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="run in runs" :key="run.id">
            <td>{{ (run.created_at || '').slice(0, 16) }}</td>
            <td>{{ titelFor(run.typ) }}</td>
            <td>{{ run.von }}<template v-if="run.bis"> – {{ run.bis }}</template></td>
            <td>{{ (run.format || '').toUpperCase() }}</td>
            <td><span :class="['rc-status', run.status]">{{ run.status === 'failed' ? 'Fehler' : 'OK' }}</span></td>
            <td>
              <button v-if="run.status !== 'failed' && run.dateiname" class="rc-dl"
                      @click="downloadRun(run.id, run.dateiname)">⬇️</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="rc-empty">Noch keine Berichte abgelegt. „💾 Ablegen" erzeugt einen Bericht und speichert ihn hier.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '../../api/client'
import DataPreviewWarning from './DataPreviewWarning.vue'
import KiStreamView from './KiStreamView.vue'

interface ReportType { key: string; titel: string; norm?: string; beschreibung?: string }
interface ReportRun {
  id: number; typ: string; von?: string; bis?: string; format?: string
  status?: string; dateiname?: string; created_at?: string
}

const props = withDefaults(defineProps<{ apiBase: string; title?: string }>(), {
  title: 'Berichts-Center',
})

const loading = ref(false)
const error = ref('')
const busy = ref('')
const reports = ref<ReportType[]>([])
const runs = ref<ReportRun[]>([])
const zeitraum = ref(false)

const preset = ref('90')
const von = ref('')
const bis = ref('')

// #1393: KI-Management-Zusammenfassung
const kiSummary = ref(false)
const aiProvider = ref<'on_prem' | 'cloud'>('on_prem')
const summary = ref<{ open: boolean; confirmed: boolean }>({ open: false, confirmed: false })
const projektHint = computed(() => props.apiBase.split('/projekte/')[1] || '—')

function _isoDay(d: Date) { return d.toISOString().slice(0, 10) }

function applyPreset() {
  if (preset.value === 'custom') return
  const today = new Date()
  if (preset.value === '30' || preset.value === '90') {
    const from = new Date(); from.setDate(today.getDate() - parseInt(preset.value, 10))
    von.value = _isoDay(from); bis.value = _isoDay(today)
  } else if (preset.value === 'quartal') {
    const q = Math.floor(today.getMonth() / 3)
    const prevQ = q === 0 ? 3 : q - 1
    const year = q === 0 ? today.getFullYear() - 1 : today.getFullYear()
    von.value = _isoDay(new Date(year, prevQ * 3, 1))
    bis.value = _isoDay(new Date(year, prevQ * 3 + 3, 0))
  } else if (preset.value === 'jahr') {
    const y = today.getFullYear() - 1
    von.value = `${y}-01-01`; bis.value = `${y}-12-31`
  }
}

function titelFor(typ: string) { return reports.value.find(r => r.key === typ)?.titel || typ }

function _zeitraumQuery(): string {
  if (!zeitraum.value || !von.value || !bis.value) return ''
  return `&von=${von.value}&bis=${bis.value}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await apiClient.get(`${props.apiBase}/berichte`)
    reports.value = res.data?.reports || []
    runs.value = res.data?.runs || []
    zeitraum.value = !!res.data?.zeitraum
    kiSummary.value = !!res.data?.ki_summary
    if (zeitraum.value && !von.value) applyPreset()
    if (kiSummary.value) {
      try {
        const p = await apiClient.get('/ai/provider-status')
        aiProvider.value = p.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
      } catch { /* default on_prem */ }
    }
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Berichts-Center konnte nicht geladen werden'
  } finally {
    loading.value = false
  }
}

// Bei Blob-Antworten steckt eine Fehlermeldung als JSON IM Blob — auslesen,
// damit der Nutzer die echte Ursache sieht (z. B. „PDF-Konverter nicht verfügbar").
async function _blobError(e: any, fallback: string): Promise<string> {
  const d = e?.response?.data
  try {
    if (d instanceof Blob) {
      const txt = await d.text()
      try { return JSON.parse(txt)?.error || fallback } catch { return txt?.slice(0, 200) || fallback }
    }
  } catch { /* ignore */ }
  return e?.response?.data?.error || fallback
}

async function _blobDownload(url: string, fallbackName: string) {
  const res = await apiClient.get(url, { responseType: 'blob' })
  const cd = res.headers?.['content-disposition'] || ''
  const m = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(cd)
  const name = m ? decodeURIComponent(m[1]) : fallbackName
  const blobUrl = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = blobUrl; a.download = name; document.body.appendChild(a); a.click()
  a.remove(); URL.revokeObjectURL(blobUrl)
}

async function download(typ: string, fmt: 'docx' | 'pdf') {
  busy.value = `${typ}:${fmt}`
  error.value = ''
  try {
    await _blobDownload(`${props.apiBase}/berichte/${encodeURIComponent(typ)}?format=${fmt}${_zeitraumQuery()}`,
      `${typ}.${fmt}`)
  } catch (e: any) {
    error.value = await _blobError(e, 'Download fehlgeschlagen')
  } finally {
    busy.value = ''
  }
}

async function generate(typ: string) {
  busy.value = `${typ}:gen`
  error.value = ''
  try {
    const body: any = { format: 'docx' }
    if (zeitraum.value) { body.von = von.value; body.bis = bis.value }
    await apiClient.post(`${props.apiBase}/berichte/${encodeURIComponent(typ)}/generate`, body)
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Bericht konnte nicht abgelegt werden'
  } finally {
    busy.value = ''
  }
}

async function downloadRun(id: number, name: string) {
  try {
    await _blobDownload(`${props.apiBase}/berichte/runs/${id}/download`, name)
  } catch (e: any) {
    error.value = await _blobError(e, 'Download fehlgeschlagen')
  }
}

function openSummary() {
  summary.value = { open: true, confirmed: false }
}

onMounted(load)
</script>

<style scoped>
.report-center { max-width: 1000px; }
.rc-head { display: flex; align-items: center; gap: 12px; }
.rc-head h3 { margin: 0; flex: 1; }
.rc-refresh { background: #eceff1; border: 1px solid #cfd8dc; border-radius: 6px; padding: 5px 12px; cursor: pointer; }
.rc-error { background: #ffebee; border: 1px solid #ef9a9a; color: #c62828; padding: 8px 12px; border-radius: 6px; }

.rc-zeitraum { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-end;
  background: #e3f2fd; border-radius: 8px; padding: 10px 14px; margin: 12px 0; }
.rc-zeitraum label { display: flex; flex-direction: column; font-size: 12px; color: #1565c0; gap: 3px; }
.rc-zeitraum select, .rc-zeitraum input { padding: 5px 8px; border: 1px solid #b3d4f5; border-radius: 6px; }

.rc-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; margin: 12px 0; }
.rc-card { border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px; padding: 12px 14px; background: #fff;
  display: flex; flex-direction: column; }
.rc-card-title { font-weight: 600; color: #0d47a1; }
.rc-card-norm { font-size: 11px; color: #78909c; margin-top: 2px; }
.rc-card-desc { font-size: 12.5px; color: #455a64; margin: 6px 0 10px; flex: 1; line-height: 1.4; }
.rc-card-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.rc-card-actions button { padding: 6px 12px; border-radius: 6px; border: 1px solid #cfd8dc; background: #fff; cursor: pointer; font-size: 13px; }
.rc-card-actions button.primary { background: var(--color-primary, #1565c0); color: #fff; border-color: var(--color-primary, #1565c0); }
.rc-card-actions button.rc-save { margin-left: auto; }
.rc-card-actions button:disabled { opacity: 0.5; cursor: not-allowed; }

.rc-history { margin-top: 18px; }
.rc-history h4 { margin: 0 0 8px; }
.rc-count { color: #90a4ae; font-weight: 400; }
.rc-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.rc-table th, .rc-table td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #eee; }
.rc-table th { color: #607d8b; font-weight: 600; }
.rc-status.failed { color: #c62828; }
.rc-status.finished { color: #2e7d32; }
.rc-dl { background: none; border: none; cursor: pointer; font-size: 15px; }
.rc-empty { color: #90a4ae; font-size: 13px; }

/* #1393: KI-Management-Zusammenfassung */
.rc-summary-btn { background: #e3f2fd; border: 1px solid #b3d4f5; color: #1565c0;
  border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 13px; }
.rc-summary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.rc-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1100; padding: 1rem; }
.rc-modal { background: #fff; border-radius: 10px; width: min(640px, 100%); max-height: 88vh;
  overflow-y: auto; box-shadow: 0 10px 40px rgba(0,0,0,0.25); }
.rc-modal-head { display: flex; align-items: center; justify-content: space-between;
  padding: 0.8rem 1.1rem; border-bottom: 1px solid #e0e0e0; }
.rc-modal-head h4 { margin: 0; color: #1565c0; }
.rc-modal-close { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: #757575; }
.rc-modal-body { padding: 1rem 1.1rem; display: flex; flex-direction: column; gap: 0.7rem; }
.rc-summary-text { white-space: pre-wrap; line-height: 1.55; color: #263238; margin: 0; }
.llm-note { font-size: 0.8rem; color: #e65100; margin: 0; }
</style>
