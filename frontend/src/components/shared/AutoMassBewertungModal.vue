<template>
  <!-- #1573: EINE automatische Massenbewertung für ALLE Module (CRA, NIS2, AI Act, DSGVO,
       WiBA, Risikobewertung): Auswahl → Datenübermittlung bestätigen → Lauf.
       Je Objekt ein eigener Stream (gleicher Endpunkt wie die Einzelbewertung) — kein
       langer Sammel-Request, daher kein Browser-Timeout; Fortschritt + Abbruch. -->
  <Teleport to="body">
    <div class="modal-overlay" @mousedown.self="onClose">
      <div class="modal-content amb">
        <div class="modal-header">
          <h3>{{ PROJEKT_AKTIONEN.massenAuto.text }} — {{ stepLabel }}</h3>
          <button class="btn-close" @click="onClose">✕</button>
        </div>

        <div class="modal-body">
          <!-- 1. Auswahl -->
          <template v-if="step === 1">
            <p class="hint">Wähle die {{ objekte }}, die die KI nacheinander <strong>automatisch bewerten</strong>
              soll. Jede Bewertung wird sofort gespeichert.</p>
            <div class="filter-row">
              <button class="btn-mini" @click="selectBy('reassess')">⚠️ Nur „Neubewertung erforderlich" ({{ counts.reassess }})</button>
              <button class="btn-mini" @click="selectBy('open')">Nur offene ({{ counts.open }})</button>
              <button class="btn-mini" @click="selectBy('all')">Alle ({{ items.length }})</button>
              <button class="btn-mini" @click="selectBy('none')">Keine</button>
            </div>
            <div class="item-list">
              <label v-for="it in items" :key="String(it.id)" class="item">
                <input type="checkbox" :value="String(it.id)" v-model="selected" />
                <span class="item-code">{{ it.code }}</span>
                <span class="item-label">{{ it.label }}</span>
                <span class="item-wert">{{ it.wert }}</span>
                <span v-if="it.reassess" class="badge">⚠️ neu bewerten</span>
              </label>
              <p v-if="!items.length" class="muted pad">Keine {{ objekte }} vorhanden.</p>
            </div>
            <p class="muted">{{ selected.length }} von {{ items.length }} ausgewählt</p>
          </template>

          <!-- 2. Bestätigung der Datenübermittlung -->
          <template v-else-if="step === 2">
            <!-- #1834: EIN Hinweis für den ganzen Lauf — er steht vor der
                 Bestätigung, weil er Teil dessen ist, was übermittelt wird. -->
            <PromptZusatzFeld v-model="zusatz" :modul="adapter.modul"
                              :projekt="projektName" bereich="bewertung"
                              beispiel="z. B. Fertigungsbetrieb, IT ausgelagert — bitte knapp begründen." />
            <!-- #1863: Zwei Läufe je Eintrag, und die Abweichung ist das
                 Signal. Kein Mehrheitsentscheid — bei Uneinigkeit entscheidet
                 ein Mensch, er bekommt nur den Grund hinzusehen. Abschaltbar,
                 weil der Preis die **Laufzeit** ist: on-prem ist sie die
                 eigentliche Grenze, nicht das Geld. -->
            <label class="kontroll-opt">
              <input type="checkbox" v-model="mitKontrolle" />
              <span>
                <strong>Jeden Eintrag zweimal bewerten</strong> und bei
                abweichendem Ergebnis markieren.
                <em>Verdoppelt die Laufzeit.</em>
              </span>
            </label>
            <DataPreviewWarning :fields="previewFields" :provider="provider" @confirm="startRun" />
            <OutputDestinationHint
              :destination="`Die KI bewertet ${selected.length} ${objekte} nacheinander; jedes Ergebnis wird sofort gespeichert.`"
              impact="Überschreibt die bisherigen Bewertungen der ausgewählten Einträge." />
          </template>

          <!-- 3. Lauf -->
          <template v-else>
            <div class="progress">
              <div class="progress-bar"><span :style="{ width: pct + '%' }" /></div>
              <span class="progress-text">
                {{ running ? `⏳ Bewerte ${current + 1} von ${rows.length}` : (aborted ? '⏹ Abgebrochen' : '✓ Fertig') }}
                · {{ okCount }} bewertet<span v-if="errCount">, {{ errCount }} Fehler</span>
                <span v-if="providerUsed"> · {{ providerUsed === 'cloud' ? '☁️ Cloud' : '🖥️ Lokal' }}</span>
              </span>
            </div>
            <!-- #1863: die Arbeitsliste. Nicht „fertig", sondern „das hier
                 braucht dich" — sonst ist die Prüfarbeit dieselbe wie vorher,
                 nur in anderer Reihenfolge. -->
            <div v-if="!running && pruefenCount" class="arbeitsliste">
              <span class="al-text">
                ⚠️ <strong>{{ pruefenCount }} von {{ rows.length }}</strong>
                brauchen deinen Blick.
              </span>
              <button class="btn-mini" @click="nurPruefen = !nurPruefen">
                {{ nurPruefen ? 'Alle zeigen' : 'Nur diese zeigen' }}
              </button>
            </div>
            <p v-else-if="!running && rows.length && !errCount" class="muted">
              Kein Eintrag ist auffällig — geprüft werden muss trotzdem, die
              Entwürfe sind unbestätigt.
            </p>
            <table class="run-table">
              <thead><tr><th></th><th>ID</th><th>{{ objekt }}</th><th>{{ wertLabel }}</th><th>Hinweis</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in sichtbareRows" :key="String(r.id)"
                    :class="[r.state, { auffaellig: istAuffaellig(r) }]"
                    @click="r.result && (detail = rows.indexOf(r))">
                  <td class="st">{{ ICON[r.state] }}</td>
                  <td class="code">{{ r.code }}</td>
                  <td>{{ r.label }}</td>
                  <td :class="['wert', r.result?.ton]">
                    {{ r.result?.wert || '—' }}
                    <em v-if="r.abweichung" class="abw" :title="`Zwei Läufe: ${r.abweichung}`">
                      ⇄ {{ r.abweichung }}
                    </em>
                  </td>
                  <td class="note">
                    <template v-if="r.error">{{ r.error }}</template>
                    <template v-else-if="r.hinweise?.length">
                      <span v-for="h in r.hinweise" :key="h.art"
                            :class="['hinw', 'g' + h.gewicht]" :title="h.text">
                        {{ h.text }}
                      </span>
                    </template>
                    <template v-else-if="r.result">Details ›</template>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="detail !== null && rows[detail]?.payload" class="detail">
              <div class="detail-head">
                <strong>{{ rows[detail].code }} — {{ rows[detail].label }}</strong>
                <button class="btn-mini" @click="detail = null">✕</button>
              </div>
              <AutoBewertungErgebnis :payload="rows[detail].payload" :wert-label="wertLabel" />
            </div>
          </template>
          <FehlerHinweis :text="error" @close="error = ''" />
        </div>

        <div class="modal-footer">
          <template v-if="step === 1">
            <button class="btn-secondary" @click="onClose">Abbrechen</button>
            <button class="btn-primary" :disabled="!selected.length" @click="step = 2">Weiter →</button>
          </template>
          <template v-else-if="step === 2">
            <button class="btn-secondary" @click="step = 1">← Zurück</button>
          </template>
          <template v-else>
            <button v-if="running" class="btn-secondary" @click="abortRun">⏹ Abbrechen</button>
            <button v-else class="btn-primary" @click="onClose">✓ Fertig</button>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { PROJEKT_AKTIONEN } from '../../utils/aktionen'
import apiClient from '../../api/client'
import PromptZusatzFeld from './PromptZusatzFeld.vue'
import DataPreviewWarning from './DataPreviewWarning.vue'
import OutputDestinationHint from './OutputDestinationHint.vue'
import AutoBewertungErgebnis from './AutoBewertungErgebnis.vue'
import { runSse } from '../../composables/useSseRun'
import { normalizeAutoResult, type AutoResult, type AutoMassItem } from '../../utils/autoBewertung'
import type { MassAdapter } from '../../utils/massAdapters'
import FehlerHinweis from './FehlerHinweis.vue'

const props = defineProps<{
  projektName: string
  /** Modul-Adapter (utils/massAdapters): Objekte, Bezeichnungen, Stream-URL */
  adapter: MassAdapter
}>()
const emit = defineEmits<{ close: []; done: [] }>()

/** #1862: ein Grund, bei diesem Entwurf genauer hinzusehen (shared/ki_pruefhinweise). */
interface Pruefhinweis { art: string; text: string; gewicht: number }

type Row = AutoMassItem & {
  state: 'wait' | 'run' | 'ok' | 'err' | 'skip'
  result?: AutoResult
  payload?: any
  error?: string
  /** #1862 — vom Server gerechnet, nicht hier abgeleitet. */
  hinweise?: Pruefhinweis[]
  /** #1863 — „4/5 vs. 2/5", leer wenn die Läufe einig waren. */
  abweichung?: string
}
const ICON: Record<Row['state'], string> = { wait: '○', run: '⏳', ok: '✓', err: '✗', skip: '–' }

const step = ref(1)
// #1834: reist im Body jedes Einzel-Streams; stream_ai_sse setzt ihn ein.
const zusatz = ref('')
const selected = ref<string[]>([])
const provider = ref<'on_prem' | 'cloud'>('on_prem')
const providerUsed = ref('')
const rows = ref<Row[]>([])
const running = ref(false)
const aborted = ref(false)
const current = ref(0)
const detail = ref<number | null>(null)
const error = ref('')
// #1863: Vorgabe an. Wer on-prem 257 Prüffragen durchlaufen lässt, kann sie
// abwählen — die Laufzeit ist dort die Grenze, nicht das Geld.
const mitKontrolle = ref(true)
const nurPruefen = ref(false)
let ctrl: AbortController | null = null

const stepLabel = computed(() => ['', 'Auswahl', 'Bestätigung', 'Bewertung'][step.value])
const items = computed(() => props.adapter.items)
const objekt = computed(() => props.adapter.objekt)
const objekte = computed(() => props.adapter.objekte)
const wertLabel = computed(() => props.adapter.wertLabel)
const counts = computed(() => ({
  reassess: items.value.filter(i => i.reassess).length,
  open: items.value.filter(i => i.open).length,
}))
const okCount = computed(() => rows.value.filter(r => r.state === 'ok').length)
const errCount = computed(() => rows.value.filter(r => r.state === 'err').length)
const pct = computed(() => rows.value.length
  ? Math.round(100 * rows.value.filter(r => r.state === 'ok' || r.state === 'err').length / rows.value.length) : 0)
/**
 * Auffällig = es gibt einen Prüfhinweis mit Gewicht ≥ 2 (#1862) oder ein Fehler.
 *
 * Gewicht 1 (beiläufig, z. B. „Anbieter konnte force_json nicht umsetzen")
 * macht eine Zeile **nicht** auffällig: Eine Arbeitsliste, auf der alles steht,
 * ist keine.
 */
function istAuffaellig(r: Row): boolean {
  if (r.state === 'err') return true
  return (r.hinweise || []).some(h => h.gewicht >= 2)
}
const pruefenCount = computed(() => rows.value.filter(istAuffaellig).length)
const sichtbareRows = computed(() =>
  nurPruefen.value ? rows.value.filter(istAuffaellig) : rows.value)

const previewFields = computed(() => [
  { label: 'Projekt', value: props.projektName },
  { label: 'Umfang', value: `${selected.value.length} ${selected.value.length === 1 ? objekt.value : objekte.value}` },
  { label: 'Inhalt je Eintrag', value: 'Stammdaten, bisherige Bewertung und vorhandene Nachweise aus der Anwendung' },
])

function selectBy(kind: string) {
  const ids = (f: (i: AutoMassItem) => boolean) => items.value.filter(f).map(i => String(i.id))
  if (kind === 'all') selected.value = ids(() => true)
  else if (kind === 'none') selected.value = []
  else if (kind === 'open') selected.value = ids(i => i.open)
  else if (kind === 'reassess') selected.value = ids(i => !!i.reassess)
}

onMounted(async () => {
  selectBy(counts.value.reassess ? 'reassess' : 'open')
  try {
    const res = await apiClient.get('/ai/provider-status')
    provider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Default on_prem */ }
})

async function startRun() {
  const sel = new Set(selected.value)
  rows.value = items.value.filter(i => sel.has(String(i.id))).map(i => ({ ...i, state: 'wait' as const }))
  step.value = 3; running.value = true; aborted.value = false; error.value = ''
  for (let i = 0; i < rows.value.length; i++) {
    if (aborted.value) { rows.value[i].state = 'skip'; continue }
    current.value = i
    const r = rows.value[i]
    r.state = 'run'
    ctrl = new AbortController()
    // #1836/E2: Die Daten-Vorschau in Schritt 2 ist die Zustimmung; sie
    // reist jetzt mit, damit der serverseitige Riegel greift und der Lauf im
    // Revisionspfad erscheint (vorher: Anzeige ohne Wirkung, #1840).
    const payload = await runSse(props.adapter.streamUrl(r.id),
                                 { prompt_zusatz: zusatz.value, confirmed: true,
                                   // #1863: der Schalter reist mit; gelesen wird
                                   // er serverseitig an einer Stelle
                                   // (ki_mehrlauf.kontrolle_gewuenscht).
                                   kontrolle: mitKontrolle.value,
                                   egress_context: `massenlauf:${objekte.value}` },
                                 (ev, data) => {
      if (data?.provider) providerUsed.value = data.provider
    }, ctrl.signal)
    if (payload?.aborted) { r.state = 'skip'; continue }
    if (payload?.ok) {
      r.state = 'ok'; r.payload = payload; r.result = normalizeAutoResult(payload)
      r.hinweise = Array.isArray(payload.pruefhinweise) ? payload.pruefhinweise : []
      r.abweichung = String(payload.abweichung || '')
    } else { r.state = 'err'; r.error = payload?.error || 'KI-Fehler' }
  }
  running.value = false
}

function abortRun() { aborted.value = true; try { ctrl?.abort() } catch { /* ignore */ } }

function onClose() {
  if (running.value) abortRun()
  if (okCount.value) emit('done')
  emit('close')
}
onBeforeUnmount(() => { if (running.value) abortRun() })
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1100; padding: 1rem;
}
.modal-content { background: #fff; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.25); }
.amb { width: min(920px, 96vw); max-height: 90vh; display: flex; flex-direction: column; }
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.9rem 1.2rem; border-bottom: 1px solid #e0e0e0;
}
.modal-header h3 { margin: 0; font-size: 1.05rem; color: #1565c0; }
.btn-close { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: #757575; }
.modal-body { padding: 1rem 1.2rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.7rem; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 0.8rem 1.2rem; border-top: 1px solid #e0e0e0; }
.hint { color: #546e7a; font-size: 13px; margin: 0; }
.filter-row { display: flex; flex-wrap: wrap; gap: 8px; }
.btn-mini { padding: 4px 10px; font-size: 12px; border: 1px solid #b0bec5; border-radius: 6px; background: #fff; cursor: pointer; }
.btn-mini:hover { background: #eceff1; }
.item-list { border: 1px solid #e0e0e0; border-radius: 6px; max-height: 46vh; overflow-y: auto; }
.item { display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-bottom: 1px solid #f0f0f0; cursor: pointer; font-size: 13px; }
.item:hover { background: #f5faff; }
.item-code, .code { font-family: monospace; font-weight: 600; color: #1565c0; min-width: 90px; }
.item-label { flex: 1; }
.item-wert { font-weight: 600; color: #455a64; white-space: nowrap; }
.badge { background: #fff3e0; color: #b26a00; border-radius: 8px; padding: 1px 7px; font-size: 11px; font-weight: 600; }
.muted { color: #90a4ae; font-size: 12px; margin: 0; }
.pad { padding: 10px; }
.progress { display: flex; flex-direction: column; gap: 6px; }
.progress-bar { height: 8px; background: #eceff1; border-radius: 4px; overflow: hidden; }
.progress-bar span { display: block; height: 100%; background: #1565c0; transition: width .3s; }
.progress-text { font-size: 13px; color: #37474f; }
.run-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.run-table th { text-align: left; font-size: 12px; color: #546e7a; border-bottom: 1px solid #e0e0e0; padding: 4px 6px; }
.run-table td { padding: 5px 6px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
.run-table tr.ok { cursor: pointer; }
.run-table tr.ok:hover { background: #f5faff; }
.run-table tr.run { background: #e3f2fd; }
.run-table tr.err .note { color: #c62828; }
.run-table tr.skip { color: #90a4ae; }
.st { width: 18px; text-align: center; }
.wert { font-weight: 600; white-space: nowrap; }
.wert.gut { color: #2e7d32; } .wert.mittel { color: #ef6c00; } .wert.schlecht { color: #c62828; }
.note { font-size: 12px; color: #78909c; }
.kontroll-opt { display: flex; gap: 8px; align-items: flex-start; font-size: 13px;
  color: #37474f; background: #f5faff; border: 1px solid #cfe3f7; border-radius: 6px; padding: 8px 10px; }
.kontroll-opt em { color: #78909c; font-style: normal; }
.arbeitsliste { display: flex; align-items: center; gap: 10px; background: #fff8e1;
  border: 1px solid #ffe082; border-radius: 6px; padding: 7px 10px; font-size: 13px; }
.al-text { flex: 1; color: #8d6e00; }
.run-table tr.auffaellig { background: #fffdf5; }
.run-table tr.auffaellig:hover { background: #fff8e1; }
.hinw { display: block; font-size: 12px; line-height: 1.35; }
.hinw.g3 { color: #c62828; font-weight: 600; }
.hinw.g2 { color: #ef6c00; }
.hinw.g1 { color: #90a4ae; }
.abw { font-style: normal; font-size: 11px; color: #c62828; display: block; font-weight: 600; }
.detail { border: 1px solid #cfe3f7; border-radius: 8px; padding: 10px 12px; background: #fafcff; }
.detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
</style>
