<template>
  <!-- #1612/#1615: Release-Assistent — Pre-Release-Check + Konformitätsnachweis je Version -->
  <div class="relcheck-panel">
    <div class="panel-header">
      <h3>🚦 Release-Check &amp; Konformitätsnachweis</h3>
      <p class="sub">Prüft vor dem Release, was noch fehlt, und erzeugt den kundenfähigen
        Konformitätsnachweis je Version.</p>
    </div>

    <div class="form-card">
      <div class="form-row ver-row">
        <label>Zielversion</label>
        <div class="ver-input">
          <input v-model="version" list="rc-versions" placeholder="z. B. v1.2.0" @change="load" />
          <datalist id="rc-versions">
            <option v-for="v in versions" :key="v" :value="v" />
          </datalist>
          <button class="btn-secondary" :disabled="busy" @click="load">Prüfen</button>
        </div>
        <p v-if="versions.length" class="hint-sub">{{ versions.length }} Version(en) aus {{ repo }} ({{ provider }})</p>
        <p v-else class="hint-sub muted">Keine Versionshistorie aus dem Repo abrufbar — Version manuell eingeben.</p>
      </div>
    </div>

    <p v-if="busy" class="muted">Prüft…</p>
    <div v-else-if="err" class="alert alert-error">{{ err }}</div>

    <template v-else-if="gate">
      <div class="form-card ampel-card" :class="gate.ampel">
        <div class="ampel-top">
          <span class="dot" />
          <strong>{{ ampelLabel(gate.ampel) }}</strong>
          <span class="pct">Reifegrad {{ gate.reifegrad_pct }} %</span>
        </div>
        <div class="counts">
          <span class="ok">erfüllt {{ gate.erfuellt }}</span>
          <span class="warn">begründet akzeptiert {{ gate.begruendet_akzeptiert }}</span>
          <span :class="gate.offen ? 'bad' : 'ok'">offen {{ gate.offen }}</span>
          <span class="muted">/ {{ gate.gesamt_anforderungen }} Anforderungen</span>
        </div>
        <div class="kpis">
          <span :class="gate.annex_vollstaendig ? 'ok' : 'bad'">Annex VII {{ gate.annex_vollstaendig ? '✓' : '✗' }}</span>
          <span :class="gate.doc_ausgestellt ? 'ok' : 'bad'">EU-Konformitätserklärung {{ gate.doc_ausgestellt ? '✓' : '✗' }}</span>
          <span :class="gate.offene_kritische_schwachstellen === 0 ? 'ok' : 'bad'">
            kritische Schwachstellen: {{ gate.offene_kritische_schwachstellen }}</span>
        </div>
      </div>

      <div class="form-card">
        <h4 v-if="gate.offene_punkte.length">Offene Punkte — hier pflegen</h4>
        <ul v-if="gate.offene_punkte.length" class="offen">
          <li v-for="(o, i) in gate.offene_punkte" :key="i">
            <span class="typ">{{ o.typ }}</span>
            <span class="txt">{{ o.titel }}<em v-if="o.hinweis"> — {{ o.hinweis }}</em></span>
            <button v-if="o.link" class="btn-link" @click="$emit('goto', o.link)">→ hier pflegen</button>
          </li>
        </ul>
        <p v-else class="hint-ok">✔ Keine offenen Punkte — das Release ist bereit.</p>
      </div>

      <div class="form-card">
        <div class="actions">
          <button class="btn-secondary" :disabled="busy" @click="download('pdf')">📄 Konformitätsnachweis (PDF)</button>
          <button class="btn-secondary" :disabled="busy" @click="download('docx')">📝 Nachweis (DOCX)</button>
          <button class="btn-primary" :disabled="busy || !version" @click="freigeben">✅ Freigeben &amp; archivieren</button>
        </div>
        <p v-if="msg" class="hint-sub">{{ msg }}</p>
      </div>

      <div v-if="archiv.length" class="form-card">
        <h4>Freigegebene Nachweise (unveränderlich)</h4>
        <ul class="archiv">
          <li v-for="a in archiv" :key="a.id">
            <strong>{{ a.version || '—' }}</strong>
            <span class="pill" :class="a.ampel">{{ ampelLabel(a.ampel) }}</span>
            <span class="muted sub">{{ (a.freigegeben_am || '').slice(0,10) }} · {{ a.freigegeben_von }} ·
              SHA-256 {{ (a.sha256 || '').slice(0,12) }}…</span>
            <button class="btn-link" @click="downloadArchiv(a.id)">herunterladen</button>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import apiClient from '../../api/client'

const props = defineProps<{ projekt: string }>()
defineEmits<{ (e: 'goto', tab: string): void }>()

const KONF = '/cra-konformitaet'
const version = ref('')
const versions = ref<string[]>([])
const repo = ref('')
const provider = ref('')
const gate = ref<any | null>(null)
const archiv = ref<any[]>([])
const busy = ref(false)
const err = ref('')
const msg = ref('')

const base = () => `${KONF}/projekte/${encodeURIComponent(props.projekt)}`
const ampelLabel = (a: string) => ({ gruen: 'KONFORM', bedingt: 'BEDINGT KONFORM', rot: 'NICHT KONFORM' } as any)[a] || a

async function loadVersions() {
  try {
    const d = (await apiClient.get(`${base()}/versions`)).data || {}
    versions.value = d.versions || []; repo.value = d.repo || ''; provider.value = d.provider || ''
    if (!version.value && versions.value.length) version.value = versions.value[0]
  } catch { /* optional */ }
}

async function load() {
  busy.value = true; err.value = ''; msg.value = ''
  try {
    gate.value = (await apiClient.get(`${base()}/release-check`, { params: { version: version.value || undefined } })).data
    archiv.value = (await apiClient.get(`${base()}/nachweis/archiv`)).data?.eintraege || []
  } catch (e: any) { err.value = e?.response?.data?.error || 'Release-Check fehlgeschlagen.' }
  finally { busy.value = false }
}

async function download(fmt: string) {
  try {
    const r = await apiClient.get(`${base()}/nachweis`, {
      params: { version: version.value || undefined, format: fmt }, responseType: 'blob' })
    const url = URL.createObjectURL(r.data as Blob)
    window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (e: any) { msg.value = e?.response?.data?.error || 'Download fehlgeschlagen.' }
}

async function freigeben() {
  if (!confirm(`Konformitätsnachweis für Version „${version.value}“ freigeben und unveränderlich archivieren?`)) return
  busy.value = true; msg.value = ''
  try {
    const r = await apiClient.post(`${base()}/nachweis/freigeben`, { version: version.value })
    msg.value = `Freigegeben & archiviert (SHA-256 ${String(r.data.sha256).slice(0, 12)}…).`
    await load()
  } catch (e: any) {
    const d = e?.response?.data
    if (e?.response?.status === 428 && d?.error === 'release_rot') {
      if (confirm('Release ist NICHT konform (offene Punkte). Trotzdem als bedingte Freigabe archivieren?')) {
        const r = await apiClient.post(`${base()}/nachweis/freigeben`, { version: version.value, confirm_rot: true })
        msg.value = `Bedingt freigegeben (SHA-256 ${String(r.data.sha256).slice(0, 12)}…).`
        await load()
      }
    } else { msg.value = d?.error || 'Freigabe fehlgeschlagen.' }
  } finally { busy.value = false }
}

async function downloadArchiv(id: number) {
  try {
    const r = await apiClient.get(`${base()}/nachweis/archiv/${id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(r.data as Blob)
    window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch { msg.value = 'Download fehlgeschlagen.' }
}

watch(() => props.projekt, async () => { await loadVersions(); await load() }, { immediate: true })
</script>

<style scoped>
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; margin: 0; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-row label { display: block; font-size: 12px; color: #455a64; margin-bottom: 4px; }
.ver-input { display: flex; gap: 8px; align-items: center; }
.ver-input input { padding: 6px 10px; border: 1px solid #cfd8e3; border-radius: 6px; min-width: 220px; }
.hint-sub { font-size: 12px; color: #607d8b; margin: 6px 0 0; }
.alert-error { background: #ffebee; color: #c62828; border: 1px solid #ffcdd2; border-radius: 6px; padding: 10px 12px; }

.ampel-card { display: flex; flex-direction: column; gap: 8px; border-left: 5px solid #9e9e9e; }
.ampel-card.gruen { border-left-color: #2e7d32; } .ampel-card.bedingt { border-left-color: #f57f17; }
.ampel-card.rot { border-left-color: #c62828; }
.ampel-top { display: flex; align-items: center; gap: 10px; }
.ampel-top strong { font-size: 15px; color: #1a237e; }
.ampel-top .pct { color: #607d8b; font-size: 13px; }
.ampel-card .dot { width: 13px; height: 13px; border-radius: 50%; background: #9e9e9e; }
.ampel-card.gruen .dot { background: #2e7d32; } .ampel-card.bedingt .dot { background: #f57f17; }
.ampel-card.rot .dot { background: #c62828; }
.counts, .kpis { display: flex; gap: 10px; flex-wrap: wrap; font-size: 12.5px; }
.counts span, .kpis span { padding: 2px 9px; border-radius: 10px; background: #eceff1; color: #455a64; }
.counts .ok, .kpis .ok { background: #e8f5e9; color: #2e7d32; }
.counts .warn { background: #fff8e1; color: #ef6c00; }
.counts .bad, .kpis .bad { background: #ffebee; color: #c62828; }

h4 { color: #1565c0; margin: 0 0 8px; font-size: 14px; }
ul.offen, ul.archiv { list-style: none; padding: 0; margin: 0; }
ul.offen li { display: flex; gap: 10px; align-items: baseline; padding: 6px 0; border-bottom: 1px solid #e6ecf3; }
ul.offen li:last-child { border-bottom: none; }
ul.offen .typ { font-size: 10.5px; color: #607d8b; min-width: 96px; text-transform: uppercase; letter-spacing: .4px; }
ul.offen .txt { flex: 1; }
ul.archiv li { display: flex; gap: 10px; align-items: baseline; padding: 5px 0; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 0; font-size: 13px; }
.pill { font-size: 11px; padding: 1px 8px; border-radius: 10px; background: #eceff1; color: #455a64; }
.pill.gruen { background: #e8f5e9; color: #2e7d32; } .pill.bedingt { background: #fff8e1; color: #ef6c00; }
.pill.rot { background: #ffebee; color: #c62828; }
.hint-ok { color: #2e7d32; margin: 0; } .muted { color: #90a4ae; } .sub { font-size: 12px; }
</style>
