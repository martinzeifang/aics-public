<template>
  <div class="wpm-overlay" @mousedown.self="onClose" role="dialog" aria-modal="true" :aria-label="title">
    <div class="wpm-modal">
      <header class="wpm-header">
        <h2 class="wpm-title">🤖 {{ title }}</h2>
        <button class="wpm-close" type="button" aria-label="Schließen" @click="onClose">✕</button>
      </header>

      <!-- KI-Kennzeichnung / Disclaimer (#870) -->
      <p class="wpm-disclaimer">🤖 KI-generiert — fachlich zu prüfen.</p>

      <!-- Slot für Transparenz-Bausteine: DataPreviewWarning (#868) etc. -->
      <div v-if="$slots.before" class="wpm-slot">
        <slot name="before" />
      </div>

      <!-- (a)+(b) Prompt hinaus, Antwort herein — der geteilte Baustein (#1867).
           Vorher stand das Kopieren hier als eigene Fassung mit „✓ Kopiert",
           und ein Einfügen gab es nicht. Beides liegt jetzt in
           `PromptAustausch`, und die sechs Aufrufer dieses Modals erben es. -->
      <section class="wpm-section">
        <PromptAustausch v-model="rawText" :prompt="anzeigePrompt" :busy="busy"
                         :prompt-zeilen="10" :antwort-zeilen="8"
                         :schema-hinweis="schemaHint"
                         platzhalter="Antwort der KI hier einfügen (JSON)…">
          <template #prompt-aktionen>
            <button class="wpm-btn wpm-run" type="button"
                    :disabled="busy || running || !prompt || egressVorbestaetigt === false"
                    :title="egressVorbestaetigt === false
                      ? 'Bitte zuerst die Datenübermittlung oben bestätigen'
                      : 'Direkt über den konfigurierten Provider (lokal oder Cloud) ausführen'"
                    @click="runDirect">
              ⚡ Direkt mit KI ausführen
            </button>
          </template>

          <!-- #1834: eigene Gedanken ergänzen. Steht ÜBER dem Prompt, damit die
               Wirkung sichtbar ist: Was hier steht, erscheint unten im Text. -->
          <template #vor-prompt>
            <PromptZusatzFeld v-model="zusatz" :disabled="busy || running" :grenze="grenze"
                              :beispiel="zusatzBeispiel"
                              :modul="hinweisModul" :projekt="hinweisProjekt"
                              :bereich="hinweisBereich" />
            <p v-if="zusatzFehler" class="wpm-runerr">⚠ {{ zusatzFehler }}</p>
          </template>

          <!-- #1366: Live-Ausführung über die API (lokal/Cloud) statt Copy/Paste -->
          <template #nach-prompt>
            <div v-if="running" class="wpm-run-box">
              <KiStreamView :url="`/api/ai/run-stream`" :confirm-egress="true"
                            :egress-vorbestaetigt="egressVorbestaetigt === true"
                            :body="{ prompt: anzeigePrompt, prompt_zusatz: zusatz, force_json: forceJson }"
                            @done="onRunDone" @error="onRunError" />
            </div>
            <p v-if="runError" class="wpm-runerr">⚠ {{ runError }}</p>
          </template>
        </PromptAustausch>
      </section>

      <!-- Slot für Ziel-Hinweis: OutputDestinationHint (#869) etc. -->
      <div v-if="$slots.after" class="wpm-slot">
        <slot name="after" />
      </div>

      <!-- (c) Buttons -->
      <footer class="wpm-footer">
        <button class="wpm-btn wpm-cancel" type="button" :disabled="busy" @click="onClose">
          Abbrechen
        </button>
        <button
          class="wpm-btn wpm-apply"
          type="button"
          :disabled="busy || !rawText.trim()"
          @click="onApply"
        >
          {{ busy ? 'Übernehme…' : 'Übernehmen' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * WizardPromptModal — wiederverwendbares Copy-Paste-KI-Modal (#866).
 *
 * Ersetzt perspektivisch die modul-eigenen Inline-Modals (RequirementActions.vue
 * u. a.). Diese Komponente wird zunächst nur bereitgestellt und in einer
 * späteren Phase in die Modul-Views eingebunden.
 *
 * Props:
 *   - title:       Überschrift des Wizards.
 *   - prompt:      Anzuzeigender Prompt-Text (zum Kopieren).
 *   - schemaHint:  Optionaler Hinweis auf das erwartete JSON-Schema.
 *   - busy:        Lade-/Verarbeitungszustand (deaktiviert Eingaben).
 *
 * Slots:
 *   - before:  Transparenz vor dem Absenden (z. B. DataPreviewWarning, #868).
 *   - after:   Ziel-/Wirkungshinweis (z. B. OutputDestinationHint, #869).
 *
 * Emits:
 *   - apply(rawText):  Nutzer übernimmt die eingefügte KI-Antwort.
 *   - close:           Modal schließen/abbrechen.
 *
 * Teil von #865.
 */
import { ref } from 'vue'
import { usePromptZusatz } from '../../composables/usePromptZusatz'
import KiStreamView from './KiStreamView.vue'
import PromptAustausch from './PromptAustausch.vue'
import PromptZusatzFeld from './PromptZusatzFeld.vue'

const props = withDefaults(
  defineProps<{
    title: string
    prompt?: string
    schemaHint?: string
    busy?: boolean
    forceJson?: boolean
    /** #1834: Beispieltext für das Hinweis-Feld, passend zur Maske. */
    zusatzBeispiel?: string
    /**
     * #1840 — hat der Aufrufer die Datenübermittlung schon bestätigen lassen?
     *
     *   `null`  (Vorgabe)  kein eigenes Tor des Aufrufers → die KiStreamView
     *                      fragt selbst (Verhalten bis v8.1.1).
     *   `false`            Tor vorhanden, noch nicht bestätigt → „⚡ Direkt
     *                      mit KI" ist gesperrt.
     *   `true`             bestätigt → kein zweites Tor, `confirmed` reist mit.
     *
     * Vorher setzten drei Aufrufer ein `confirmed`-Feld, das **niemand las**:
     * Der Haken gab nichts frei und sperrte nichts, und daneben lag ein
     * zweites, wirksames Tor mit anderem Wortlaut.
     */
    egressVorbestaetigt?: boolean | null
    /**
     * #1835 — Modul und Projekt für die **gespeicherten** Hinweise. Nur wo der
     * Aufrufer beides kennt; sonst bleibt das Feld rein ad hoc.
     */
    hinweisModul?: string
    hinweisProjekt?: string
    hinweisBereich?: string
  }>(),
  { prompt: '', schemaHint: '', busy: false, forceJson: false, zusatzBeispiel: '',
    egressVorbestaetigt: null, hinweisModul: '', hinweisProjekt: '',
    hinweisBereich: '' },
)

const emit = defineEmits<{
  (e: 'apply', rawText: string): void
  (e: 'close'): void
}>()

const rawText = ref('')
const running = ref(false)
const runError = ref('')

// #1834: eigene Hinweise — zusammengesetzt wird serverseitig, damit im Fenster
// steht, was wirklich gesendet wird (siehe usePromptZusatz).
const { zusatz, anzeigePrompt, fehler: zusatzFehler, grenze } =
  usePromptZusatz(() => props.prompt)

function runDirect() {
  runError.value = ''
  running.value = true  // KiStreamView startet (autostart) und sendet den oben gezeigten Prompt
}
function onRunDone(payload: any) {
  running.value = false
  rawText.value = (payload?.text || '').trim()  // Antwort ins Feld → bestehende Übernehmen-Logik
}
function onRunError(msg: string) {
  running.value = false
  runError.value = msg
}

function onApply() {
  const text = rawText.value.trim()
  if (!text) return
  emit('apply', text)
}

function onClose() {
  emit('close')
}
</script>

<style scoped>
.wpm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.wpm-modal {
  background: var(--color-surface, #fff);
  color: var(--color-text-primary, #1a1a1a);
  border-radius: 10px;
  width: min(760px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
  padding: 1.25rem 1.5rem 1.5rem;
}

.wpm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wpm-title {
  font-size: 1.15rem;
  margin: 0;
  color: var(--color-primary, #0d47a1);
}

.wpm-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: #757575;
}

.wpm-disclaimer {
  margin: 0.5rem 0 1rem;
  padding: 0.4rem 0.7rem;
  background: #fff8e1;
  border: 1px solid #ffe082;
  border-radius: 6px;
  color: #e65100;
  font-size: 0.85rem;
}

.wpm-slot {
  margin-bottom: 1rem;
}

.wpm-section {
  margin-bottom: 1.1rem;
}






.wpm-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.5rem;
}

.wpm-btn {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 0.85rem;
}

.wpm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}


.wpm-cancel {
  background: #fff;
  color: #616161;
  border-color: #cfd8dc;
}

.wpm-apply {
  background: var(--color-primary, #1565c0);
  color: #fff;
}

.wpm-run {
  background: #1565c0;
  color: #fff;
  border-color: #1565c0;
}
.wpm-run-box {
  margin-top: 0.7rem;
  padding: 0.7rem;
  background: #f5f9ff;
  border: 1px solid #bbdefb;
  border-radius: 6px;
}
.wpm-runerr {
  margin: 0.5rem 0 0;
  color: #c62828;
  font-size: 0.85rem;
}
</style>
