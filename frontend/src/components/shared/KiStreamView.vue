<!--
  KiStreamView (Sprint #35, #1408) — geteilte Live-Ansicht der KI-Generierung für
  ALLE Module. Konsumiert einen POST-SSE-Endpoint (text/event-stream) und zeigt:
  Phase, live Token-für-Token-Ausgabe, Token-Zahl/Dauer/Tokens-pro-Sekunde.
  Wie beim lokalen LLM — funktioniert für on_prem (echtes Streaming) und cloud
  (Volltext als ein Chunk).

  Props:
    url      — absoluter API-Pfad inkl. /api (z. B. /api/cra/projekte/x/berichte/ki-summary/stream)
    body     — optionales JSON-Objekt (POST-Body)
    autostart— bei true sofort starten (Default true)
  Emits:
    done(payload)  — finales 'done'-Event (ok + Ergebnisfelder)
    error(message)
  Slot 'result' (scoped: { payload }) — eigene Ergebnis-Darstellung nach Abschluss.
-->
<template>
  <div class="kistream">
    <!-- #1519: Egress-Bestätigung VOR jeglicher Datenübermittlung an die KI -->
    <div v-if="showEgressGate" class="ks-egress-gate">
      <p class="ks-eg-title">
        {{ egressProvider === 'cloud' ? '☁️ Übermittlung an Cloud-KI' : '🖥️ Übermittlung an lokale KI' }}
      </p>
      <p class="ks-eg-text">
        Mit „Übermitteln &amp; ausführen" wird der angezeigte Prompt an
        <strong>{{ egressProvider === 'cloud' ? 'den externen Cloud-Provider' : 'die lokale KI (on-prem)' }}</strong>
        gesendet. Die Bestätigung wird revisionssicher protokolliert.
      </p>
      <button class="ks-eg-btn" @click="confirmEgressAndStart">✅ Übermitteln &amp; ausführen</button>
    </div>

    <template v-else>
    <!-- #1418/#1407: Phasen-Pipeline (RB-Optik) — einheitlich für alle Module -->
    <div v-if="pipeline" class="ks-pipeline">
      <div v-for="(s, i) in PIPELINE" :key="s.key"
           :class="['ks-step', { active: stepState(i) === 'active', done: stepState(i) === 'done' }]">
        <span class="ks-step-icon">{{ stepState(i) === 'done' ? '✓' : (stepState(i) === 'active' ? '⏳' : '○') }}</span>
        <span class="ks-step-label">{{ s.label }}</span>
      </div>
    </div>

    <div class="ks-status">
      <span class="ks-phase">{{ phaseLabel }}</span>
      <span v-if="tokens" class="ks-stat">{{ tokens }} Tokens</span>
      <span v-if="elapsedS" class="ks-stat">{{ elapsedS }}s</span>
      <span v-if="tPerS" class="ks-stat">{{ tPerS }} T/s</span>
      <span v-if="provider" class="ks-stat">{{ provider === 'cloud' ? '☁️ Cloud' : '🖥️ Lokal' }}</span>
      <!-- #1836/E1: Abbruch gab es an 2 von 49 Bedienstellen. Der
           AbortController lag hier schon, wurde aber nur beim Unmount
           gerufen — es fehlte der Knopf. Lange Läufe (Pentest-Extraktion in
           16k-Scheiben, Sammel-Bewertungen) waren damit nicht stoppbar. -->
      <button v-if="!done && !errorMsg" class="ks-stop" type="button"
              title="Lauf abbrechen" @click="stop">⏹ Abbrechen</button>
    </div>

    <pre v-if="text" class="ks-output" ref="outRef">{{ text }}</pre>
    <p v-else-if="!done" class="ks-wait">⏳ Warte auf die KI …</p>

    <p v-if="errorMsg" class="ks-error">⚠ {{ errorMsg }}</p>

    <div v-if="done && payload && payload.ok" class="ks-result">
      <slot name="result" :payload="payload" />
    </div>

    <!-- #1485/#1487 (Sprint #40): Provenienz — welche App-Nachweise stützen die Bewertung -->
    <div v-if="done && payload && payload.ok && payload.genutzte_nachweise && payload.genutzte_nachweise.length"
         class="ks-evidence">
      <div class="ks-ev-title">🔎 Genutzte Nachweise aus der Anwendung</div>
      <ul class="ks-ev-list">
        <li v-for="(n, i) in payload.genutzte_nachweise" :key="i">{{ n }}</li>
      </ul>
      <p v-if="provider === 'cloud'" class="ks-ev-cloud">
        ☁️ An Cloud-Provider übermittelt — als sensibel markierte Inhalte wurden vor dem
        Versand redigiert.
      </p>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { runSse } from '../../composables/useSseRun'
import apiClient from '../../api/client'

// #1519: confirmEgress → vor dem Senden MUSS die Datenübermittlung bestätigt werden
//        (kein Autostart); der bestätigte Egress wird serverseitig append-only auditiert.
// #1840: `egressVorbestaetigt` — der Aufrufer hat die Übermittlung schon
// sichtbar bestätigen lassen (DataPreviewWarning, die sagt WELCHE Daten
// hinausgehen). Dann zeigt diese Komponente **kein zweites** Tor, sendet aber
// weiterhin `confirmed: true`, damit der serverseitige Riegel greift und der
// Revisionseintrag entsteht. Zwei Tore für denselben Vorgang sind eines zu
// viel — und eine Zustimmung, die nichts auslöst, ist schlimmer als keine.
const props = withDefaults(defineProps<{ url: string; body?: any; autostart?: boolean; pipeline?: boolean; confirmEgress?: boolean; egressVorbestaetigt?: boolean; egressContext?: string; egressModul?: string }>(), {
  body: () => ({}), autostart: true, pipeline: false, confirmEgress: false,
  egressVorbestaetigt: false, egressContext: '', egressModul: 'ai',
})
const emit = defineEmits<{ (e: 'done', payload: any): void; (e: 'error', msg: string): void }>()

// #1519: Egress-Bestätigungs-Gate
const egressConfirmed = ref(false)
const egressProvider = ref<'on_prem' | 'cloud' | ''>('')
const showEgressGate = computed(() => props.confirmEgress && !props.egressVorbestaetigt
                                     && !egressConfirmed.value && !done.value)
async function loadEgressProvider() {
  try {
    const res = await apiClient.get('/ai/provider-status')
    egressProvider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { egressProvider.value = '' }
}
function confirmEgressAndStart() {
  egressConfirmed.value = true
  start()
}

const text = ref('')
const tokens = ref(0)
const elapsedS = ref(0)
const tPerS = ref(0)
const provider = ref('')
const phase = ref('')
const done = ref(false)
const errorMsg = ref('')
const payload = ref<any>(null)
const outRef = ref<HTMLElement | null>(null)
let abort: AbortController | null = null

const PHASE_LABEL: Record<string, string> = {
  connect: 'Verbinde mit KI …', streaming: 'Antwort kommt …', '': 'Starte …',
}
const phaseLabel = computed(() => done.value ? (payload.value?.ok ? '✓ Fertig' : '✗ Fehler')
  : (PHASE_LABEL[phase.value] || phase.value || 'Starte …'))

// #1418/#1407 — einheitliche Phasen-Pipeline. Mappt die Phase-Namen beider
// SSE-Quellen (shared/sse: connect/streaming · RB: prepare/connect/generate/
// streaming/parse/save) auf 5 sichtbare Schritte.
const PIPELINE = [
  { key: 'connect', label: 'Verbinden' },
  { key: 'generate', label: 'Modell laden' },
  { key: 'streaming', label: 'Generieren' },
  { key: 'parse', label: 'Parsen' },
  { key: 'save', label: 'Speichern' },
]
const PHASE_TO_STEP: Record<string, number> = {
  prepare: 0, connect: 0, generate: 1, streaming: 2, parse: 3, save: 4, done: 4,
}
const curStep = computed(() => PHASE_TO_STEP[phase.value] ?? -1)
function stepState(i: number): 'pending' | 'active' | 'done' {
  if (done.value && payload.value?.ok) return 'done'
  if (curStep.value > i) return 'done'
  if (curStep.value === i) return 'active'
  return 'pending'
}

async function start() {
  done.value = false; errorMsg.value = ''; text.value = ''; tokens.value = 0
  abort = new AbortController()
  // #1836/E2: `confirmed` reist mit, sobald eine sichtbare Zustimmung
  // vorliegt — eigenes Tor ODER vorbestätigt durch den Aufrufer. Nur so
  // greifen der serverseitige Riegel und der Revisionseintrag.
  const bestaetigt = props.confirmEgress || props.egressVorbestaetigt
  const sendBody = bestaetigt
    ? { ...(props.body || {}), confirmed: true, egress_context: props.egressContext, modul: props.egressModul }
    : (props.body || {})
  // #1573: geteilter SSE-Konsument (auch vom Auto-Massenlauf genutzt)
  const final = await runSse(props.url, sendBody, handle, abort.signal)
  if (!done.value && !final?.aborted) fail(final?.error || 'Stream ohne Ergebnis beendet.')
}

function handle(ev: string, data: any) {
  if (ev === 'phase') { phase.value = data.phase || ''; if (data.provider) provider.value = data.provider }
  else if (ev === 'chunk') { text.value += data.text || ''; phase.value = 'streaming'; scrollOut() }
  else if (ev === 'progress') {
    tokens.value = data.tokens || tokens.value
    elapsedS.value = data.elapsed_s || elapsedS.value
    tPerS.value = data.t_per_s || tPerS.value
  } else if (ev === 'done') {
    done.value = true; payload.value = data
    if (data.tokens) tokens.value = data.tokens
    if (data.elapsed_s) elapsedS.value = data.elapsed_s
    if (data.provider) provider.value = data.provider
    if (data.ok) emit('done', data)
    else { errorMsg.value = data.error || 'KI-Fehler'; emit('error', errorMsg.value) }
  }
}

function fail(msg: string) { done.value = true; errorMsg.value = msg; payload.value = { ok: false, error: msg }; emit('error', msg) }

/** #1836/E1: Lauf abbrechen. Der Stream endet, der bisherige Text bleibt stehen. */
function stop() {
  try { abort?.abort() } catch { /* ignore */ }
  done.value = true
  payload.value = { ok: false, aborted: true, text: text.value }
  phase.value = ''
  errorMsg.value = 'Abgebrochen — der bisherige Text bleibt stehen.'
}
async function scrollOut() { await nextTick(); if (outRef.value) outRef.value.scrollTop = outRef.value.scrollHeight }

defineExpose({ start })
onMounted(() => {
  // #1519: eigenes Tor → erst bestätigen. Hat der Aufrufer schon bestätigen
  // lassen (#1840), läuft es sofort: Eine zweite Rückfrage für denselben
  // Vorgang erzieht nur dazu, sie wegzuklicken.
  if (props.confirmEgress && !props.egressVorbestaetigt) { loadEgressProvider(); return }
  if (props.autostart) start()
})
onBeforeUnmount(() => { try { abort?.abort() } catch { /* ignore */ } })
</script>

<style scoped>
.kistream { display: flex; flex-direction: column; gap: 8px; }
.ks-egress-gate { padding: 12px 14px; background: #fff8e1; border: 1px solid #ffe082;
  border-radius: 8px; }
.ks-eg-title { margin: 0 0 6px; font-weight: 700; color: #6a4f00; }
.ks-eg-text { margin: 0 0 10px; font-size: 13px; color: #5d4037; }
.ks-eg-btn { background: #1565c0; color: #fff; border: none; border-radius: 6px;
  padding: 8px 14px; font-weight: 600; cursor: pointer; }
.ks-eg-btn:hover { background: #0d47a1; }
.ks-pipeline { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center;
  padding: 6px 2px; font-size: 12px; }
.ks-step { display: flex; align-items: center; gap: 4px; color: #b0bec5; }
.ks-step.active { color: #1565c0; font-weight: 600; }
.ks-step.done { color: #2e7d32; }
.ks-step-icon { font-size: 12px; }
.ks-status { display: flex; gap: 12px; align-items: center; font-size: 12px; color: #1565c0; flex-wrap: wrap; }
.ks-phase { font-weight: 600; }
.ks-stat { color: #607d8b; }
.ks-stop { margin-left: auto; background: #fff; color: #c62828; border: 1px solid #ef9a9a;
  border-radius: 6px; padding: 2px 10px; font-size: 12px; cursor: pointer; }
.ks-stop:hover { background: #ffebee; }
.ks-output { background: #263238; color: #eceff1; padding: 0.7rem; border-radius: 6px;
  font-family: Consolas, 'Courier New', monospace; font-size: 0.8rem; white-space: pre-wrap;
  word-break: break-word; max-height: 320px; overflow-y: auto; margin: 0; }
.ks-wait { color: #90a4ae; font-size: 13px; margin: 0; }
.ks-error { color: #c62828; font-size: 13px; margin: 0; }
.ks-result { margin-top: 6px; }
.ks-evidence { margin-top: 10px; padding: 8px 12px; background: #f5faff; border: 1px solid #cfe3f7; border-radius: 6px; }
.ks-ev-title { font-weight: 600; color: #1565c0; font-size: 13px; margin-bottom: 4px; }
.ks-ev-list { margin: 0; padding-left: 18px; font-size: 12px; color: #37474f; }
.ks-ev-cloud { margin: 6px 0 0; font-size: 11px; color: #78909c; }
</style>
