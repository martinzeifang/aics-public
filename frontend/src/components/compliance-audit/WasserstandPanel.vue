<template>
  <div class="wasserstand">
    <div class="intro">
      <h3>📊 Wasserstandsmeldung</h3>
      <p>
        Der Compliance-Stand wird <strong>aus den Antworten berechnet</strong>, nicht
        von der KI vergeben — bei gleichen Antworten kommt immer dieselbe Stufe heraus.
        Die KI formuliert nur den Text für den Kunden.
      </p>
    </div>

    <div v-if="fehler" class="alert alert-error" @click="fehler = ''">{{ fehler }}</div>

    <!-- Berechneter Stand -->
    <div v-if="status" class="stand-card" :class="'stufe-' + status.stufe">
      <div class="stand-kopf">
        <div class="ampel">{{ ampel(status.stufe) }}</div>
        <div>
          <div class="stufe-label">{{ status.label }}</div>
          <div class="stufe-bedeutung">{{ status.bedeutung }}</div>
        </div>
        <div class="quote">
          <strong>{{ status.quote_prozent ?? '–' }} %</strong>
          <span>Erfüllungsquote</span>
        </div>
      </div>

      <div class="kennzahlen">
        <span>{{ status.fragen.gesamt }} Fragen</span>
        <span class="k-ok">{{ status.fragen.erfuellt }} erfüllt</span>
        <span class="k-teil">{{ status.fragen.teilweise }} teilweise</span>
        <span class="k-nein">{{ status.fragen.nicht_erfuellt }} nicht erfüllt</span>
        <span class="k-offen">{{ status.fragen.offen }} offen</span>
        <span class="k-na">{{ status.fragen.nicht_anwendbar }} n. a.</span>
      </div>

      <p v-if="status.fragen.offen > 0" class="hinweis">
        ⚠️ {{ status.fragen.offen }} Fragen sind noch offen. Sie zählen in der Quote als
        <em>nicht nachgewiesen</em> — die Abdeckung liegt bei
        {{ status.abdeckung_prozent ?? '–' }} %. Nur die bewerteten Fragen ergäben
        {{ status.quote_bewertet_prozent ?? '–' }} %.
      </p>

      <table v-if="status.frameworks?.length" class="fw-tabelle">
        <thead>
          <tr><th>Framework</th><th>Stufe</th><th>Quote</th><th>offen</th></tr>
        </thead>
        <tbody>
          <tr v-for="fw in status.frameworks" :key="fw.framework">
            <td>{{ fw.framework }}</td>
            <td><span :class="'pille stufe-' + fw.stufe">{{ fw.label }}</span></td>
            <td>{{ fw.quote_prozent ?? '–' }} %</td>
            <td>{{ fw.fragen.offen }} / {{ fw.fragen.anwendbar }}</td>
          </tr>
        </tbody>
      </table>

      <div class="aktionen">
        <button class="btn-secondary" :disabled="laedt" @click="ladeStatus">↻ Neu berechnen</button>
        <button class="btn-secondary" :disabled="laedt" @click="backfill"
                title="Erfüllung aus der alten Freitext-Bewertung ableiten (Projekte vor v7.4.0)">
          ⤵ Alte Bewertungen übernehmen
        </button>
        <button class="btn-primary" :disabled="laedt || !hatFragen" @click="starteKi">
          🤖 Meldung mit KI erstellen
        </button>
        <button class="btn-secondary" :disabled="laedt || !hatFragen" @click="holePrompt">
          📋 Prompt kopieren
        </button>
      </div>
    </div>

    <div v-else-if="laedt" class="lade">Stand wird berechnet …</div>

    <!-- KI-Lauf -->
    <KiStreamView
      v-if="kiAktiv"
      :url="`/compliance-audit/${encodeURIComponent(projekt)}/wasserstand/stream`"
      :body="{}"
      :autostart="false"
      confirm-egress
      egress-modul="compliance_audit"
      egress-context="Wasserstandsmeldung (Fragen, Bewertungen und Lücken des Audits)"
      @done="onKiFertig"
      @error="(m: string) => { fehler = m; kiAktiv = false }"
    />

    <!-- Copy/Paste-Weg -->
    <div v-if="prompt" class="prompt-box">
      <div class="prompt-kopf">
        <strong>Prompt</strong>
        <button class="btn-mini" @click="kopieren(prompt)">Kopieren</button>
        <button class="btn-mini" @click="prompt = ''">Schließen</button>
      </div>
      <textarea readonly rows="10" :value="prompt"></textarea>
      <label>Antwort der KI hier einfügen:</label>
      <textarea v-model="antwort" rows="6" placeholder='{ "kundenmitteilung": … }'></textarea>
      <button class="btn-primary" :disabled="!antwort.trim() || laedt" @click="importiere">
        Übernehmen
      </button>
    </div>

    <!-- Ergebnis -->
    <div v-if="meldung" class="meldung-card">
      <h4>Mitteilung an den Kunden</h4>
      <p class="kundentext">{{ meldung.kundenmitteilung }}</p>

      <div v-for="fw in meldung.je_framework || []" :key="fw.framework" class="fw-block">
        <h5>{{ fw.framework }}</h5>
        <p>{{ fw.einschaetzung }}</p>
        <div v-if="fw.hauptluecken?.length">
          <strong>Hauptlücken</strong>
          <ul><li v-for="(l, i) in fw.hauptluecken" :key="i">{{ l }}</li></ul>
        </div>
        <div v-if="fw.naechste_schritte?.length">
          <strong>Nächste Schritte</strong>
          <ul><li v-for="(l, i) in fw.naechste_schritte" :key="i">{{ l }}</li></ul>
        </div>
      </div>

      <div v-if="meldung.top_massnahmen?.length" class="massnahmen">
        <h5>Empfohlene Maßnahmen</h5>
        <table>
          <thead><tr><th>Maßnahme</th><th>Priorität</th><th>Aufwand</th><th>Begründung</th></tr></thead>
          <tbody>
            <tr v-for="(m, i) in meldung.top_massnahmen" :key="i">
              <td>{{ m.massnahme }}</td>
              <td><span :class="'prio prio-' + m.prioritaet">{{ m.prioritaet }}</span></td>
              <td>{{ m.aufwand }}</td>
              <td>{{ m.begruendung }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-if="meldung.fazit" class="fazit"><strong>Fazit:</strong> {{ meldung.fazit }}</p>
    </div>

    <!-- Verlauf -->
    <div v-if="verlauf.length" class="verlauf">
      <h4>Verlauf</h4>
      <table>
        <thead><tr><th>Datum</th><th>Stufe</th><th>Quote</th><th>Quelle</th><th></th></tr></thead>
        <tbody>
          <tr v-for="w in verlauf" :key="w.id">
            <td>{{ (w.created_at || '').slice(0, 16).replace('T', ' ') }}</td>
            <td><span :class="'pille stufe-' + w.stufe">{{ w.stufe }}</span></td>
            <td>{{ w.quote_prozent ?? '–' }} %</td>
            <td>{{ w.provider || '–' }}</td>
            <td><button class="btn-mini" @click="oeffne(w.id)">anzeigen</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import apiClient from '../../api/client'
import KiStreamView from '../shared/KiStreamView.vue'

const props = defineProps<{ projekt: string }>()

const status = ref<any>(null)
const meldung = ref<any>(null)
const verlauf = ref<any[]>([])
const prompt = ref('')
const antwort = ref('')
const fehler = ref('')
const laedt = ref(false)
const kiAktiv = ref(false)

const hatFragen = computed(() => (status.value?.fragen?.gesamt || 0) > 0)

const AMPELN: Record<string, string> = {
  vollstaendig: '🟢', weitgehend: '🟡', teilweise: '🟠', nicht: '🔴', unbewertet: '⚪',
}
function ampel(stufe: string) { return AMPELN[stufe] || '⚪' }

async function ladeStatus() {
  if (!props.projekt) return
  laedt.value = true
  try {
    const r = await apiClient.get(`/compliance-audit/${encodeURIComponent(props.projekt)}/status`)
    status.value = r.data
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Stand konnte nicht berechnet werden'
  } finally { laedt.value = false }
}

async function ladeVerlauf() {
  if (!props.projekt) return
  try {
    const r = await apiClient.get(`/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand`)
    verlauf.value = Array.isArray(r.data) ? r.data : []
  } catch { verlauf.value = [] }
}

async function backfill() {
  laedt.value = true
  try {
    const r = await apiClient.post(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/erfuellung/backfill`, {})
    status.value = r.data.status
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Übernahme fehlgeschlagen'
  } finally { laedt.value = false }
}

async function holePrompt() {
  laedt.value = true
  try {
    const r = await apiClient.post(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand/prompt`, {})
    prompt.value = r.data.prompt
    status.value = r.data.status
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Prompt konnte nicht erzeugt werden'
  } finally { laedt.value = false }
}

async function importiere() {
  laedt.value = true
  try {
    const r = await apiClient.post(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand/import`,
      { response: antwort.value })
    meldung.value = r.data.ki
    status.value = r.data.status
    antwort.value = ''
    prompt.value = ''
    await ladeVerlauf()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Antwort konnte nicht übernommen werden'
  } finally { laedt.value = false }
}

function starteKi() { kiAktiv.value = true; meldung.value = null }

async function onKiFertig(payload: any) {
  kiAktiv.value = false
  if (payload?.error) { fehler.value = payload.error; return }
  if (payload?.ki) meldung.value = payload.ki
  if (payload?.status) status.value = payload.status
  await ladeVerlauf()
}

async function oeffne(id: number) {
  try {
    const r = await apiClient.get(
      `/compliance-audit/${encodeURIComponent(props.projekt)}/wasserstand/${id}`)
    meldung.value = r.data.ki
    status.value = r.data.status
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Meldung konnte nicht geladen werden'
  }
}

function kopieren(text: string) {
  navigator.clipboard?.writeText(text).catch(() => {})
}

onMounted(() => { ladeStatus(); ladeVerlauf() })
watch(() => props.projekt, () => {
  status.value = null; meldung.value = null; prompt.value = ''
  ladeStatus(); ladeVerlauf()
})
</script>

<style scoped>
.wasserstand { display: flex; flex-direction: column; gap: 1.25rem; }
.intro h3 { margin: 0 0 .25rem; }
.intro p { margin: 0; color: #546e7a; font-size: .9rem; }

.stand-card { border: 1px solid #cfd8dc; border-left-width: 6px; border-radius: 8px; padding: 1rem; background: #fff; }
.stand-card.stufe-vollstaendig { border-left-color: #2e7d32; }
.stand-card.stufe-weitgehend  { border-left-color: #f9a825; }
.stand-card.stufe-teilweise   { border-left-color: #ef6c00; }
.stand-card.stufe-nicht       { border-left-color: #c62828; }
.stand-card.stufe-unbewertet  { border-left-color: #90a4ae; }

.stand-kopf { display: flex; align-items: center; gap: 1rem; }
.ampel { font-size: 2.25rem; line-height: 1; }
.stufe-label { font-size: 1.15rem; font-weight: 600; }
.stufe-bedeutung { color: #546e7a; font-size: .88rem; }
.quote { margin-left: auto; text-align: right; }
.quote strong { display: block; font-size: 1.6rem; }
.quote span { font-size: .75rem; color: #78909c; }

.kennzahlen { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .85rem; font-size: .82rem; }
.kennzahlen span { background: #eceff1; border-radius: 12px; padding: .15rem .6rem; }
.k-ok { background: #e8f5e9 !important; } .k-teil { background: #fff8e1 !important; }
.k-nein { background: #ffebee !important; } .k-offen { background: #e3f2fd !important; }
.k-na { background: #f5f5f5 !important; color: #78909c; }

.hinweis { margin: .75rem 0 0; font-size: .85rem; background: #fff8e1; border-radius: 6px; padding: .5rem .75rem; }

.fw-tabelle, .verlauf table, .massnahmen table { width: 100%; border-collapse: collapse; margin-top: .85rem; font-size: .86rem; }
.fw-tabelle th, .fw-tabelle td, .verlauf th, .verlauf td, .massnahmen th, .massnahmen td {
  text-align: left; padding: .4rem .5rem; border-bottom: 1px solid #eceff1;
}
.pille { border-radius: 10px; padding: .1rem .5rem; font-size: .78rem; background: #eceff1; }
.pille.stufe-vollstaendig { background: #e8f5e9; color: #2e7d32; }
.pille.stufe-weitgehend { background: #fff8e1; color: #f57f17; }
.pille.stufe-teilweise { background: #fff3e0; color: #ef6c00; }
.pille.stufe-nicht { background: #ffebee; color: #c62828; }

.aktionen { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; }

.prompt-box, .meldung-card, .verlauf { border: 1px solid #cfd8dc; border-radius: 8px; padding: 1rem; background: #fff; }
.prompt-kopf { display: flex; align-items: center; gap: .5rem; margin-bottom: .5rem; }
.prompt-box textarea { width: 100%; font-family: Consolas, monospace; font-size: .8rem; }
.prompt-box label { display: block; margin: .6rem 0 .25rem; font-size: .85rem; font-weight: 600; }

.kundentext { background: #f1f8e9; border-radius: 6px; padding: .75rem; white-space: pre-wrap; }
.fw-block { margin-top: 1rem; border-top: 1px solid #eceff1; padding-top: .75rem; }
.fw-block h5 { margin: 0 0 .35rem; }
.prio { border-radius: 10px; padding: .1rem .5rem; font-size: .78rem; }
.prio-hoch { background: #ffebee; color: #c62828; }
.prio-mittel { background: #fff8e1; color: #f57f17; }
.prio-niedrig { background: #e8f5e9; color: #2e7d32; }
.fazit { margin-top: 1rem; }
.lade { color: #78909c; }
.btn-mini { font-size: .78rem; padding: .15rem .5rem; }
</style>
