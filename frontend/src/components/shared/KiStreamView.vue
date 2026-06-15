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
    </div>

    <pre v-if="text" class="ks-output" ref="outRef">{{ text }}</pre>
    <p v-else-if="!done" class="ks-wait">⏳ Warte auf die KI …</p>

    <p v-if="errorMsg" class="ks-error">⚠ {{ errorMsg }}</p>

    <div v-if="done && payload && payload.ok" class="ks-result">
      <slot name="result" :payload="payload" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = withDefaults(defineProps<{ url: string; body?: any; autostart?: boolean; pipeline?: boolean }>(), {
  body: () => ({}), autostart: true, pipeline: false,
})
const emit = defineEmits<{ (e: 'done', payload: any): void; (e: 'error', msg: string): void }>()

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
  const token = sessionStorage.getItem('auth_token') || ''
  if (!token) { fail('Kein Auth-Token — bitte neu einloggen.'); return }
  abort = new AbortController()
  let resp: Response
  try {
    resp = await fetch(props.url, {
      method: 'POST', signal: abort.signal,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json',
                 Accept: 'text/event-stream' },
      body: JSON.stringify(props.body || {}),
    })
  } catch (e: any) { fail(`Netzwerk-Fehler: ${e?.message || e}`); return }
  if (!resp.ok || !resp.body) {
    let d = ''
    try { d = (await resp.text()).slice(0, 300) } catch { /* ignore */ }
    fail(`HTTP ${resp.status}${d ? ' — ' + d : ''}`); return
  }
  const reader = resp.body.getReader()
  const dec = new TextDecoder('utf-8')
  let buf = ''
  while (true) {
    const { value, done: rdone } = await reader.read()
    if (rdone) break
    buf += dec.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const raw = buf.slice(0, idx); buf = buf.slice(idx + 2)
      let ev = '', dataStr = ''
      for (const ln of raw.split('\n')) {
        if (ln.startsWith('event: ')) ev = ln.slice(7)
        else if (ln.startsWith('data: ')) dataStr += ln.slice(6)
      }
      if (!ev) continue
      let data: any = {}
      try { data = JSON.parse(dataStr) } catch { /* ignore */ }
      handle(ev, data)
    }
  }
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
async function scrollOut() { await nextTick(); if (outRef.value) outRef.value.scrollTop = outRef.value.scrollHeight }

defineExpose({ start })
onMounted(() => { if (props.autostart) start() })
onBeforeUnmount(() => { try { abort?.abort() } catch { /* ignore */ } })
</script>

<style scoped>
.kistream { display: flex; flex-direction: column; gap: 8px; }
.ks-pipeline { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center;
  padding: 6px 2px; font-size: 12px; }
.ks-step { display: flex; align-items: center; gap: 4px; color: #b0bec5; }
.ks-step.active { color: #1565c0; font-weight: 600; }
.ks-step.done { color: #2e7d32; }
.ks-step-icon { font-size: 12px; }
.ks-status { display: flex; gap: 12px; align-items: center; font-size: 12px; color: #1565c0; flex-wrap: wrap; }
.ks-phase { font-weight: 600; }
.ks-stat { color: #607d8b; }
.ks-output { background: #263238; color: #eceff1; padding: 0.7rem; border-radius: 6px;
  font-family: Consolas, 'Courier New', monospace; font-size: 0.8rem; white-space: pre-wrap;
  word-break: break-word; max-height: 320px; overflow-y: auto; margin: 0; }
.ks-wait { color: #90a4ae; font-size: 13px; margin: 0; }
.ks-error { color: #c62828; font-size: 13px; margin: 0; }
.ks-result { margin-top: 6px; }
</style>
