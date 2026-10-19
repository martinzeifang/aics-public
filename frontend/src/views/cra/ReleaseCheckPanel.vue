<template>
  <!-- #1612/#1615: Release-Assistent — Pre-Release-Check + Konformitätsnachweis je Version -->
  <section class="release-check">
    <div class="head">
      <h3>🚦 Release-Check</h3>
      <div class="ver">
        <label>Version
          <input v-model="version" placeholder="z. B. v1.2.0" @keyup.enter="load" /></label>
        <button class="btn-secondary" :disabled="busy" @click="load">Prüfen</button>
      </div>
    </div>

    <p v-if="busy" class="muted">Prüft…</p>
    <p v-else-if="err" class="msg err">{{ err }}</p>

    <template v-else-if="gate">
      <div class="ampel" :class="gate.ampel">
        <span class="dot" />
        <strong>{{ ampelLabel(gate.ampel) }}</strong>
        <span class="sub">Reifegrad {{ gate.reifegrad_pct }} % ·
          erfüllt {{ gate.erfuellt }} · begründet {{ gate.begruendet_akzeptiert }} ·
          offen {{ gate.offen }} / {{ gate.gesamt_anforderungen }}</span>
      </div>

      <div class="kpis">
        <span :class="{ ok: gate.annex_vollstaendig }">Annex VII {{ gate.annex_vollstaendig ? '✓' : '✗' }}</span>
        <span :class="{ ok: gate.doc_ausgestellt }">EU-Konformitätserklärung {{ gate.doc_ausgestellt ? '✓' : '✗' }}</span>
        <span :class="{ ok: gate.offene_kritische_schwachstellen === 0 }">
          kritische Schwachstellen: {{ gate.offene_kritische_schwachstellen }}</span>
      </div>

      <h4 v-if="gate.offene_punkte.length">Offene Punkte — hier pflegen</h4>
      <ul v-if="gate.offene_punkte.length" class="offen">
        <li v-for="(o, i) in gate.offene_punkte" :key="i">
          <span class="typ">{{ o.typ }}</span>
          <span>{{ o.titel }}<em v-if="o.hinweis"> — {{ o.hinweis }}</em></span>
          <button v-if="o.link" class="btn-link" @click="$emit('goto', o.link)">→ hier pflegen</button>
        </li>
      </ul>
      <p v-else class="hint-ok">✔ Keine offenen Punkte — Release ist bereit.</p>

      <div class="actions">
        <button class="btn-secondary" :disabled="busy" @click="download('pdf')">📄 Konformitätsnachweis (PDF)</button>
        <button class="btn-secondary" :disabled="busy" @click="download('docx')">📝 Nachweis (DOCX)</button>
        <button class="btn-primary" :disabled="busy || !version" @click="freigeben">✅ Nachweis freigeben &amp; archivieren</button>
      </div>
      <p v-if="msg" class="msg">{{ msg }}</p>

      <h4 v-if="archiv.length">Freigegebene Nachweise (unveränderlich)</h4>
      <ul v-if="archiv.length" class="archiv">
        <li v-for="a in archiv" :key="a.id">
          <strong>{{ a.version || '—' }}</strong>
          <span class="lvl" :class="a.ampel">{{ ampelLabel(a.ampel) }}</span>
          <span class="muted small">{{ (a.freigegeben_am || '').slice(0,10) }} · {{ a.freigegeben_von }} · SHA-256 {{ (a.sha256||'').slice(0,12) }}…</span>
          <button class="btn-link" @click="downloadArchiv(a.id)">herunterladen</button>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import apiClient from '../../api/client'

const props = defineProps<{ projekt: string }>()
defineEmits<{ (e: 'goto', tab: string): void }>()

const KONF = '/cra-konformitaet'
const version = ref('')
const gate = ref<any | null>(null)
const archiv = ref<any[]>([])
const busy = ref(false)
const err = ref('')
const msg = ref('')

const base = () => `${KONF}/projekte/${encodeURIComponent(props.projekt)}`
const ampelLabel = (a: string) => ({ gruen: 'KONFORM', bedingt: 'BEDINGT KONFORM', rot: 'NICHT KONFORM' } as any)[a] || a

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
    msg.value = `Freigegeben & archiviert (SHA-256 ${String(r.data.sha256).slice(0,12)}…).`
    await load()
  } catch (e: any) {
    const d = e?.response?.data
    if (e?.response?.status === 428 && d?.error === 'release_rot') {
      if (confirm('Release ist NICHT konform (offene Punkte). Trotzdem als bedingte Freigabe archivieren?')) {
        const r = await apiClient.post(`${base()}/nachweis/freigeben`, { version: version.value, confirm_rot: true })
        msg.value = `Bedingt freigegeben (SHA-256 ${String(r.data.sha256).slice(0,12)}…).`
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

watch(() => props.projekt, load, { immediate: true })
</script>

<style scoped>
.release-check { padding: 4px 2px; }
.head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.head h3 { color: #1565c0; margin: 0; }
.ver { display: flex; gap: 8px; align-items: end; }
.ver input { padding: 4px 8px; }
.ampel { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 8px; margin: 12px 0;
  background: #f4f6fa; border: 1px solid #d9dee6; }
.ampel .dot { width: 14px; height: 14px; border-radius: 50%; background: #9e9e9e; }
.ampel.gruen .dot { background: #2e7d32; } .ampel.bedingt .dot { background: #f57f17; } .ampel.rot .dot { background: #c62828; }
.ampel .sub { color: #5c6878; font-size: 13px; }
.kpis { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 10px; font-size: 13px; }
.kpis span { padding: 2px 8px; border-radius: 10px; background: #ffebee; color: #c62828; }
.kpis span.ok { background: #e8f5e9; color: #2e7d32; }
h4 { color: #1565c0; margin: 14px 0 6px; }
ul.offen, ul.archiv { list-style: none; padding: 0; }
ul.offen li { display: flex; gap: 8px; align-items: baseline; padding: 4px 0; border-bottom: 1px solid #eef1f6; }
ul.offen .typ { font-size: 11px; color: #607d8b; min-width: 90px; text-transform: uppercase; }
ul.archiv li { display: flex; gap: 10px; align-items: baseline; padding: 4px 0; }
.lvl { font-size: 11px; padding: 1px 7px; border-radius: 8px; background: #eceff1; }
.lvl.gruen { background: #e8f5e9; color: #2e7d32; } .lvl.bedingt { background: #fff8e1; color: #ef6c00; }
.lvl.rot { background: #ffebee; color: #c62828; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; }
.hint-ok { color: #2e7d32; } .muted { color: #90a4ae; } .small { font-size: 12px; }
.msg { margin-top: 8px; } .msg.err { color: #c62828; }
</style>
