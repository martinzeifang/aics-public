<template>
  <!-- #1528/#1573: EINE Massenbewertung über einen Sammel-Prompt für ALLE Module
       (CRA, NIS2, AI Act, DSGVO, WiBA, Risikobewertung) — modulspezifisch nur der Adapter. -->
  <Teleport to="body">
    <div class="modal-overlay" @mousedown.self="$emit('close')">
      <div class="modal-content mass-modal">
        <div class="modal-header">
          <h3>🧮 Massenbewertung — {{ stepLabel }}</h3>
          <button class="btn-close" @click="$emit('close')">✕</button>
        </div>

        <div class="modal-body">
          <!-- Schritt 1: Auswahl -->
          <div v-if="step === 1">
            <p class="hint">Wähle die {{ adapter.objekte }}, die in <strong>einem Sammel-Prompt</strong> bewertet werden sollen.</p>
            <div class="filter-row">
              <button class="btn-mini" @click="selectByFilter('reassess')">⚠️ Nur „Neubewertung erforderlich" ({{ counts.reassess }})</button>
              <button class="btn-mini" @click="selectByFilter('open')">Nur offene ({{ counts.open }})</button>
              <button class="btn-mini" @click="selectByFilter('all')">Alle ({{ adapter.items.length }})</button>
              <button class="btn-mini" @click="selectByFilter('none')">Keine</button>
            </div>
            <div class="req-list">
              <label v-for="r in adapter.items" :key="String(r.id)" class="req-item">
                <input type="checkbox" :value="String(r.id)" v-model="selected" />
                <span class="req-id">{{ r.code }}</span>
                <span class="req-title">{{ r.label }}</span>
                <span class="req-score">{{ r.wert }}</span>
                <span v-if="r.reassess" class="req-badge">⚠️ neu bewerten</span>
              </label>
              <p v-if="!adapter.items.length" class="muted pad">Keine {{ adapter.objekte }} vorhanden.</p>
            </div>
            <p class="muted">{{ selected.length }} von {{ adapter.items.length }} ausgewählt</p>
          </div>

          <!-- Schritt 2: Prompt + KI -->
          <div v-else-if="step === 2">
            <p class="hint">Ein Sammel-Prompt für <strong>{{ promptInfo.count }}</strong> {{ adapter.objekte }}.
              Kopieren &amp; in ChatGPT/Claude einfügen — oder direkt ausführen. Die JSON-Array-Antwort unten einfügen.</p>
            <div class="prompt-actions">
              <button class="btn-mini" @click="copyPrompt">📋 Prompt kopieren</button>
              <button class="btn-mini" @click="runDirect = true" :disabled="runDirect">⚡ Direkt mit KI ausführen</button>
            </div>
            <pre class="prompt-text">{{ promptInfo.prompt }}</pre>
            <KiStreamView v-if="runDirect" :url="`/api/ai/run-stream`" :body="{ prompt: promptInfo.prompt }"
                          confirm-egress egress-modul="mass" pipeline
                          @done="onDirectDone" @error="(m: string) => { runDirect = false; error = m }" />
            <label class="lbl">Antwort (JSON-Array)</label>
            <textarea v-model="response" rows="7" :placeholder="adapter.responsePlaceholder"></textarea>
          </div>

          <!-- Schritt 3: Vorschau + Auswahl übernehmen -->
          <div v-else-if="step === 3">
            <p class="hint">{{ preview.length }} Bewertungen erkannt — wähle aus, was übernommen werden soll:</p>
            <div class="req-list">
              <label v-for="p in preview" :key="p.id" class="req-item">
                <input type="checkbox" :value="p.id" v-model="applySel" />
                <span class="req-id">{{ p.code }}</span>
                <span class="req-title">{{ p.label }}</span>
                <span class="req-score">→ {{ p.neu }}</span>
                <span class="req-komm">{{ (p.text || '').slice(0, 80) }}</span>
              </label>
            </div>
            <p v-if="unknown.length" class="muted">Ignoriert (nicht zugeordnet): {{ unknown.join(', ') }}</p>
            <p class="muted">{{ applySel.length }} von {{ preview.length }} ausgewählt</p>
          </div>

          <FehlerHinweis :text="error" @close="error = ''" />
        </div>

        <div class="modal-footer">
          <button class="btn-secondary" @click="$emit('close')">Abbrechen</button>
          <button v-if="step > 1" class="btn-secondary" @click="back">← Zurück</button>
          <button v-if="step === 1" class="btn-primary" :disabled="!selected.length || busy" @click="genPrompt">
            {{ busy ? 'Erzeuge…' : 'Sammel-Prompt erzeugen →' }}
          </button>
          <button v-if="step === 2" class="btn-primary" :disabled="!response.trim() || busy" @click="doPreview">
            {{ busy ? 'Verarbeite…' : 'Vorschau anzeigen →' }}
          </button>
          <button v-if="step === 3" class="btn-primary" :disabled="!applySel.length || busy" @click="doApply">
            {{ busy ? 'Übernehme…' : `✓ ${applySel.length} übernehmen` }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import KiStreamView from './KiStreamView.vue'
import type { MassAdapter, MassPreviewRow } from '../../utils/massAdapters'
import FehlerHinweis from './FehlerHinweis.vue'

const props = defineProps<{
  projektName: string
  /** Modul-Adapter (utils/massAdapters): Objekte + Endpunkte */
  adapter: MassAdapter
}>()
const emit = defineEmits<{ close: []; applied: [] }>()

const step = ref(1)
const selected = ref<string[]>([])
const busy = ref(false)
const error = ref('')
const promptInfo = ref<{ prompt: string; count: number }>({ prompt: '', count: 0 })
const response = ref('')
const runDirect = ref(false)
const preview = ref<MassPreviewRow[]>([])
const applySel = ref<string[]>([])
const unknown = ref<(string | number)[]>([])

const stepLabel = computed(() => ['', 'Auswahl', 'Sammel-Prompt', 'Vorschau'][step.value])
const counts = computed(() => ({
  reassess: props.adapter.items.filter(r => r.reassess).length,
  open: props.adapter.items.filter(r => r.open).length,
}))

function selectByFilter(kind: string) {
  const ids = (f: (r: any) => boolean) => props.adapter.items.filter(f).map(r => String(r.id))
  if (kind === 'all') selected.value = ids(() => true)
  else if (kind === 'none') selected.value = []
  else if (kind === 'open') selected.value = ids(r => r.open)
  else if (kind === 'reassess') selected.value = ids(r => !!r.reassess)
}
onMounted(() => selectByFilter(counts.value.reassess ? 'reassess' : 'open'))

async function genPrompt() {
  busy.value = true; error.value = ''
  try {
    promptInfo.value = await props.adapter.prompt(selected.value)
    response.value = ''; runDirect.value = false
    step.value = 2
  } catch (e: any) { error.value = e?.response?.data?.error || 'Prompt-Erzeugung fehlgeschlagen.' }
  finally { busy.value = false }
}
function copyPrompt() { navigator.clipboard?.writeText(promptInfo.value.prompt) }
function onDirectDone(payload: any) {
  runDirect.value = false
  response.value = payload?.text || payload?.result || ''
}

async function doPreview() {
  busy.value = true; error.value = ''
  try {
    const res = await props.adapter.preview(response.value)
    preview.value = res.rows
    unknown.value = res.unknown
    applySel.value = preview.value.map(p => p.id)
    if (!preview.value.length) { error.value = 'Keine gültigen Bewertungen erkannt.'; return }
    step.value = 3
  } catch (e: any) { error.value = e?.response?.data?.error || 'Antwort konnte nicht verarbeitet werden.' }
  finally { busy.value = false }
}

async function doApply() {
  busy.value = true; error.value = ''
  const chosen = preview.value.filter(p => applySel.value.includes(p.id))
  try {
    const { ok, total } = await props.adapter.apply(chosen)
    if (ok) emit('applied')
    if (ok < total) { error.value = `${ok}/${total} übernommen.`; return }
    emit('close')
  } catch (e: any) { error.value = e?.response?.data?.error || 'Übernahme fehlgeschlagen.' }
  finally { busy.value = false }
}

function back() { step.value = Math.max(1, step.value - 1) }
</script>

<style scoped>
/* #1535: Modal-Overlay/-Content-Basis. Fehlte bisher — .modal-overlay/.modal-content
   sind pro Komponente scoped (kein globales CSS), sodass der Teleport-Overlay ohne
   position:fixed/z-index unsichtbar am Seitenende landete („Knopf ohne Wirkung"). */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1100; padding: 1rem;
}
.modal-content {
  background: #fff; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.25); overflow: hidden;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.9rem 1.2rem; border-bottom: 1px solid #e0e0e0;
}
.modal-header h3 { margin: 0; font-size: 1.05rem; color: #1565c0; }
.btn-close { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: #757575; }
.modal-body { padding: 1rem 1.2rem 1.2rem; overflow-y: auto; }
.mass-modal { width: min(900px, 96vw); max-height: 90vh; display: flex; flex-direction: column; }
.modal-body { overflow-y: auto; }
.hint { color: #546e7a; font-size: 13px; margin: 0 0 10px; }
.filter-row, .prompt-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.btn-mini { padding: 4px 10px; font-size: 12px; border: 1px solid #b0bec5; border-radius: 6px;
  background: #fff; cursor: pointer; }
.btn-mini:hover { background: #eceff1; }
.req-list { border: 1px solid #e0e0e0; border-radius: 6px; max-height: 46vh; overflow-y: auto; }
.req-item { display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-bottom: 1px solid #f0f0f0;
  cursor: pointer; font-size: 13px; }
.req-item:hover { background: #f5faff; }
.req-id { font-family: monospace; font-weight: 600; color: #1565c0; min-width: 90px; }
.req-title { flex: 1; }
.req-score { font-weight: 600; }
.req-score.low { color: #c62828; }
.req-komm { color: #78909c; font-size: 12px; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.req-badge { background: #fff3e0; color: #b26a00; border-radius: 8px; padding: 1px 7px; font-size: 11px; font-weight: 600; }
.prompt-text { background: #263238; color: #eceff1; padding: 10px; border-radius: 6px; font-family: Consolas, monospace;
  font-size: 12px; white-space: pre-wrap; max-height: 30vh; overflow-y: auto; }
.lbl { display: block; margin: 8px 0 4px; font-weight: 600; font-size: 13px; }
textarea { width: 100%; box-sizing: border-box; font-family: Consolas, monospace; font-size: 12px; }
.muted { color: #90a4ae; font-size: 12px; }
.pad { padding: 10px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 0.8rem 1.2rem; border-top: 1px solid #e0e0e0; }
</style>
