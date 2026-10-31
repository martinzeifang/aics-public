<!--
  Prompt hinaus, Antwort herein — ein Baustein für alle Masken (#1867).

  Der Copy/Paste-Weg ist der Vorgabeweg der Suite. Trotzdem sah er in 19 Masken
  verschieden aus: drei hatten gar keinen Kopier-Knopf („🔎 Akte prüfen lassen",
  „🔍 Nachweise erschließen", DSGVO-Zweckänderung), die übrigen kopierten jede
  für sich — mit „✓ Kopiert", mit `alert()`, mit verschlucktem Fehler und
  einmal ganz ohne Rückmeldung. **Einfügen** konnte keine einzige:
  `navigator.clipboard.readText` kam im ganzen Baum 0× vor.

  WARUM EIN BAUSTEIN UND NICHT NUR EIN HELFER
  Ein Helfer (`utils/zwischenablage.ts`) macht die Mechanik gleich, nicht die
  Bedienung. Sichtbar ist aber Letzteres: wo der Knopf steht, wie er heißt, was
  er nach dem Klick sagt. Genau das war in jeder Maske anders — die
  Spiegel-Liste aus #1731/#1735 in ihrer leisen Form, denn nichts schlägt fehl.

  DER EINFÜGE-KNOPF SAGT, WENN ER NICHT KANN
  `readText()` braucht in Firefox eine Bestätigung und fehlt in unsicheren
  Kontexten. Der Knopf bleibt dann nicht stumm, sondern setzt den Fokus ins
  Antwortfeld und nennt `Strg+V`. Ein Knopf, der nichts tut und nichts sagt,
  ist schlechter als keiner (#1805/#1830).
-->
<template>
  <div class="pa">
    <!-- 1. Prompt -->
    <div class="pa-kopf">
      <h4 class="pa-titel">
        <span v-if="nummeriert" class="pa-nr">1.</span>{{ promptTitel }}
      </h4>
      <div class="pa-aktionen">
        <slot name="prompt-aktionen" />
        <button type="button" class="pa-btn" :disabled="!prompt || busy"
                :title="prompt ? 'Prompt in die Zwischenablage legen'
                               : 'Es liegt noch kein Prompt vor'"
                @click="aufKopieren">
          {{ kopiert ? '✓ Kopiert' : '📋 Kopieren' }}
        </button>
      </div>
    </div>

    <slot name="vor-prompt" />

    <p v-if="schemaHinweis" class="pa-hinweis">{{ schemaHinweis }}</p>

    <textarea class="pa-feld pa-prompt" readonly :rows="promptZeilen"
              :value="prompt" :placeholder="promptPlatzhalter" />
    <p v-if="kopierFehler" class="pa-fehler">⚠ {{ kopierFehler }}</p>

    <slot name="nach-prompt" />

    <!-- 2. Antwort -->
    <template v-if="mitAntwort">
    <div class="pa-kopf">
      <h4 class="pa-titel">
        <span v-if="nummeriert" class="pa-nr">2.</span>{{ antwortTitel }}
      </h4>
      <div class="pa-aktionen">
        <slot name="antwort-aktionen" />
        <button type="button" class="pa-btn" :disabled="busy"
                title="Antwort aus der Zwischenablage in das Feld einfügen"
                @click="aufEinfuegen">
          📥 Einfügen
        </button>
      </div>
    </div>

    <textarea ref="antwortFeld" class="pa-feld" :rows="antwortZeilen"
              :placeholder="platzhalter" :disabled="busy"
              :value="modelValue"
              @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)" />
    <p v-if="einfuegeFehler" class="pa-fehler">⚠ {{ einfuegeFehler }}</p>
    </template>

    <!-- Der Übernehmen-Knopf ist ein **Slot** und kein Event.
         Als Emit hätte ihn jede Maske ohne eigenen Knopf in die
         Ausnahmeliste von `test_knopf_ohne_wirkung_1805` eintragen müssen
         (WizardPromptModal und die drei Assistenten haben ihren eigenen
         Fuß) — eine Ausnahmeliste, die mit jeder neuen Maske wächst, wird
         zum Teppich. So entsteht der Knopf nur, wo ihn jemand zeichnet. -->
    <div v-if="$slots.fuss" class="pa-fuss">
      <slot name="fuss" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { EINFUEGE_HINWEIS, einfuegen, kopiere } from '../../utils/zwischenablage'

const props = withDefaults(defineProps<{
  /** Der Prompt. Leer = der Kopier-Knopf ist gesperrt und sagt warum. */
  prompt: string
  /** Die eingefügte Antwort (v-model). */
  modelValue: string
  busy?: boolean
  promptTitel?: string
  antwortTitel?: string
  /** „1."/„2." davorstellen — aus, wo die Maske schon eigene Schritte zählt. */
  nummeriert?: boolean
  promptZeilen?: number
  antwortZeilen?: number
  platzhalter?: string
  promptPlatzhalter?: string
  schemaHinweis?: string
  /**
   * Das Antwortfeld zeichnen. Aus, wo es nichts einzufügen gibt — ein
   * Dokumenten-Assistent liefert Prosa in ein Dokument, keine JSON-Antwort in
   * ein Feld. Ein leeres Antwortfeld mit Einfüge-Knopf wäre dort ein Angebot,
   * das ins Nichts führt (#1805/#1830).
   */
  mitAntwort?: boolean
}>(), {
  busy: false,
  promptTitel: 'Prompt für die KI',
  antwortTitel: 'KI-Antwort einfügen',
  nummeriert: true,
  promptZeilen: 8,
  antwortZeilen: 6,
  platzhalter: 'Antwort der KI hier einfügen …',
  promptPlatzhalter: '',
  schemaHinweis: '',
  mitAntwort: true,
})

const emit = defineEmits<{
  'update:modelValue': [wert: string]
}>()

const kopiert = ref(false)
const kopierFehler = ref('')
const einfuegeFehler = ref('')
const antwortFeld = ref<HTMLTextAreaElement | null>(null)

async function aufKopieren() {
  kopierFehler.value = ''
  // Der Rückgabewert wird ausgewertet — ein verworfenes `false` war genau der
  // stille Fehlschlag, den dieser Baustein beseitigt.
  if (await kopiere(props.prompt)) {
    kopiert.value = true
    setTimeout(() => (kopiert.value = false), 2000)
  } else {
    kopierFehler.value = 'Der Prompt ließ sich nicht in die Zwischenablage '
      + 'legen. Bitte im Feld markieren und mit Strg+C kopieren.'
  }
}

async function aufEinfuegen() {
  einfuegeFehler.value = ''
  const erg = await einfuegen()
  if (erg.fehler) {
    einfuegeFehler.value = EINFUEGE_HINWEIS[erg.fehler]
    // Den Fokus setzen, damit Strg+V sofort wirkt: Der Hinweis allein wäre
    // eine Bedienanleitung, und die ist keine Funktion.
    antwortFeld.value?.focus()
    return
  }
  emit('update:modelValue', erg.text)
}
</script>

<style scoped>
.pa { display: flex; flex-direction: column; gap: 6px; }
.pa-kopf { display: flex; align-items: center; justify-content: space-between;
  gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.pa-titel { margin: 0; font-size: 13px; font-weight: 600; color: #37474f; }
.pa-nr { color: #90a4ae; margin-right: 5px; }
.pa-aktionen { display: flex; gap: 6px; flex-wrap: wrap; }
.pa-btn { padding: 3px 10px; font-size: 12px; border: 1px solid #b0bec5;
  border-radius: 6px; background: #fff; cursor: pointer; white-space: nowrap; }
.pa-btn:hover:not(:disabled) { background: #eceff1; }
.pa-btn:disabled { opacity: .55; cursor: not-allowed; }
.pa-primaer { border-color: #1565c0; background: #1565c0; color: #fff; }
.pa-primaer:hover:not(:disabled) { background: #0d47a1; }
.pa-feld { width: 100%; box-sizing: border-box; font-family: monospace;
  font-size: 12px; border: 1px solid #cfd8dc; border-radius: 6px; padding: 6px;
  resize: vertical; }
.pa-prompt { background: #fafafa; color: #37474f; }
.pa-hinweis { margin: 0; font-size: 12px; color: #546e7a; }
.pa-fehler { margin: 0; font-size: 12px; color: #c62828; }
.pa-fuss { display: flex; justify-content: flex-end; margin-top: 2px; }
</style>
