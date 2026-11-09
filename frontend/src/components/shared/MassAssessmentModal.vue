<template>
  <!-- #1528/#1573: EINE Massenbewertung über einen Sammel-Prompt für ALLE Module
       (CRA, NIS2, AI Act, DSGVO, WiBA, Risikobewertung) — modulspezifisch nur der Adapter. -->
  <Teleport to="body">
    <div class="modal-overlay" @mousedown.self="$emit('close')">
      <div class="modal-content mass-modal">
        <div class="modal-header">
          <h3>{{ $t('geteilt.massAssessmentModal.massenbewertungV0', { v0: stepLabel }) }}</h3>
          <button class="btn-close" @click="$emit('close')">✕</button>
        </div>

        <div class="modal-body">
          <!-- Schritt 1: Auswahl -->
          <div v-if="step === 1">
            <p class="hint">{{ $t('geteilt.massAssessmentModal.wahleDieV0DieIn', { v0: adapter.objekte }) }} <strong>{{ $t('geteilt.massAssessmentModal.einemSammelPrompt') }}</strong> {{ $t('geteilt.massAssessmentModal.bewertetWerdenSollen') }}</p>
            <div class="filter-row">
              <button class="btn-mini" @click="selectByFilter('reassess')">{{ $t('geteilt.massAssessmentModal.nurNeubewertungErforderlichV0', { v0: counts.reassess }) }}</button>
              <button class="btn-mini" @click="selectByFilter('open')">{{ $t('geteilt.massAssessmentModal.nurOffeneV0', { v0: counts.open }) }}</button>
              <button class="btn-mini" @click="selectByFilter('all')">{{ $t('geteilt.massAssessmentModal.alleV0', { v0: adapter.items.length }) }}</button>
              <button class="btn-mini" @click="selectByFilter('none')">{{ $t('common.keine') }}</button>
            </div>
            <div class="req-list">
              <label v-for="r in adapter.items" :key="String(r.id)" class="req-item">
                <input type="checkbox" :value="String(r.id)" v-model="selected" />
                <span class="req-id">{{ r.code }}</span>
                <span class="req-title">{{ r.label }}</span>
                <span class="req-score">{{ r.wert }}</span>
                <span v-if="r.reassess" class="req-badge">{{ $t('geteilt.massAssessmentModal.neuBewerten') }}</span>
              </label>
              <p v-if="!adapter.items.length" class="muted pad">{{ $t('geteilt.massAssessmentModal.keineV0Vorhanden', { v0: adapter.objekte }) }}</p>
            </div>
            <p class="muted">{{ $t('geteilt.massAssessmentModal.v0VonV1Ausgewahlt', { v0: selected.length, v1: adapter.items.length }) }}</p>
          </div>

          <!-- Schritt 2: Prompt + KI -->
          <div v-else-if="step === 2">
            <p class="hint">{{ $t('geteilt.massAssessmentModal.einSammelPromptFur') }} <strong>{{ promptInfo.count }}</strong> {{ $t('geteilt.massAssessmentModal.v0KopierenAmpInChatGPTClaudeEinfugen', { v0: adapter.objekte }) }}</p>
            <PromptAustausch v-model="response" :prompt="anzeigePrompt"
                             prompt-titel="Sammel-Prompt" :prompt-zeilen="9"
                             antwort-titel="Antwort (JSON-Array)" :antwort-zeilen="7"
                             :nummeriert="false"
                             :platzhalter="adapter.responsePlaceholder">
              <template #prompt-aktionen>
                <button class="btn-mini" @click="runDirect = true" :disabled="runDirect">{{ $t('common.direktMitKIAusfuhren') }}</button>
              </template>
              <!-- #1834: ein Hinweis für den ganzen Sammel-Lauf -->
              <template #vor-prompt>
                <PromptZusatzFeld v-model="zusatz" :modul="adapter.modul"
                                  :projekt="projektName" bereich="bewertung" :grenze="grenze"
                                  :beispiel="$t('geteilt.massAssessmentModal.zBSchwerpunktOTSicherheitBitteJeAnfo')" />
                <FehlerHinweis v-if="zusatzFehler" art="warnung" :text="zusatzFehler" />
              </template>
              <template #nach-prompt>
                <KiStreamView v-if="runDirect" :url="`/api/ai/run-stream`"
                              :body="{ prompt: anzeigePrompt, prompt_zusatz: zusatz }"
                              confirm-egress egress-modul="mass" pipeline
                              @done="onDirectDone" @error="(m: string) => { runDirect = false; error = m }" />
              </template>
            </PromptAustausch>
          </div>

          <!-- Schritt 3: Vorschau + Auswahl übernehmen -->
          <div v-else-if="step === 3">
            <p class="hint">{{ $t('geteilt.massAssessmentModal.v0BewertungenErkanntWahleAusWasUbern', { v0: preview.length }) }}</p>
            <div class="req-list">
              <label v-for="p in preview" :key="p.id" class="req-item">
                <input type="checkbox" :value="p.id" v-model="applySel" />
                <span class="req-id">{{ p.code }}</span>
                <span class="req-title">{{ p.label }}</span>
                <span class="req-score">→ {{ p.neu }}</span>
                <span class="req-komm">{{ (p.text || '').slice(0, 80) }}</span>
              </label>
            </div>
            <p v-if="unknown.length" class="muted">{{ $t('geteilt.massAssessmentModal.ignoriertNichtZugeordnetV0', { v0: unknown.join(', ') }) }}</p>
            <p class="muted">{{ $t('geteilt.massAssessmentModal.v0VonV1Ausgewahlt', { v0: applySel.length, v1: preview.length }) }}</p>
          </div>

          <FehlerHinweis :text="error" :art="hinweisArt" @close="error = ''" />
        </div>

        <div class="modal-footer">
          <button class="btn-secondary" @click="$emit('close')">{{ $t('common.cancel') }}</button>
          <button v-if="step > 1" class="btn-secondary" @click="back">{{ $t('common.zuruck') }}</button>
          <button v-if="step === 1" class="btn-primary" :disabled="!selected.length || busy" @click="genPrompt">
            {{ busy ? $t('geteilt.massAssessmentModal.erzeuge') : $t('geteilt.massAssessmentModal.sammelPromptErzeugen') }}
          </button>
          <button v-if="step === 2" class="btn-primary" :disabled="!response.trim() || busy" @click="doPreview">
            {{ busy ? $t('geteilt.massAssessmentModal.verarbeite') : $t('geteilt.massAssessmentModal.vorschauAnzeigen') }}
          </button>
          <button v-if="step === 3" class="btn-primary" :disabled="!applySel.length || busy" @click="doApply">
            {{ busy ? $t('geteilt.massAssessmentModal.ubernehme') : `✓ ${applySel.length} übernehmen` }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import KiStreamView from './KiStreamView.vue'
import PromptAustausch from './PromptAustausch.vue'
import PromptZusatzFeld from './PromptZusatzFeld.vue'
import { usePromptZusatz } from '../../composables/usePromptZusatz'
import type { MassAdapter, MassPreviewRow } from '../../utils/massAdapters'
import FehlerHinweis from './FehlerHinweis.vue'
import { t } from '../../i18n'

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
/** #2039: Ein Teilerfolg ist eine Warnung, kein Fehler. */
const hinweisArt = ref<'fehler' | 'warnung'>('fehler')
const promptInfo = ref<{ prompt: string; count: number }>({ prompt: '', count: 0 })
// #1834: Der angezeigte und kopierte Text ist Basis + Hinweis, serverseitig
// zusammengesetzt — nicht der Rohprompt.
const { zusatz, anzeigePrompt, fehler: zusatzFehler, grenze } =
  usePromptZusatz(() => promptInfo.value.prompt)
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
  } catch (e: any) { error.value = e?.response?.data?.error || t('geteilt.massAssessmentModal.promptErzeugungFehlgeschlagen') }
  finally { busy.value = false }
}
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
    if (!preview.value.length) { error.value = t('geteilt.massAssessmentModal.keineGultigenBewertungenErkannt'); return }
    step.value = 3
  } catch (e: any) { error.value = e?.response?.data?.error || t('geteilt.massAssessmentModal.antwortKonnteNichtVerarbeitetWerden') }
  finally { busy.value = false }
}

async function doApply() {
  busy.value = true; error.value = ''
  const chosen = preview.value.filter(p => applySel.value.includes(p.id))
  try {
    const { ok, total } = await props.adapter.apply(chosen)
    if (ok) emit('applied')
    if (ok < total) {
      // #2039: Das war ein **roter Fehlerkasten** mit „18/20 übernommen." —
      // die naheliegende Lesart ist „fehlgeschlagen, nichts gespeichert",
      // tatsächlich sind 18 Bewertungen geschrieben. `FehlerHinweis` kennt
      // seit #1781 die Art `warnung`, genau für diesen Fall; ohne Angabe gilt
      // „fehler". Und es war die einzige harte deutsche Zeichenkette der
      // Datei (#2042).
      hinweisArt.value = 'warnung'
      error.value = t('geteilt.massAssessmentModal.v0VonV1Uebernommen',
                      { v0: ok, v1: total, v2: total - ok })
      return
    }
    emit('close')
  } catch (e: any) {
    hinweisArt.value = 'fehler'
    error.value = e?.response?.data?.error || t('common.uebernahmeFehlgeschlagen')
  }
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
