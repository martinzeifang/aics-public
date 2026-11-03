<!--
  ModalRahmen (#1849) — ein Gerüst für die KI- und Issue-Dialoge.

  WARUM DAS EIN BAUSTEIN IST UND KEINE STILREGEL
  Der Bestand kannte zwölf Klassennamen für dasselbe Gerüst (`modal-overlay`
  58×, `wizard-modal-overlay` 25×, `hub-overlay`, `cl-ai-overlay`,
  `wpm-overlay` …), und `Teleport` nutzten 5 von 17 KI-Overlays. Genau daraus
  entstand **#1535**: `MassAssessmentModal` stylte nur `.mass-modal`, nicht
  `.modal-overlay`. Vue-Styles sind `scoped`, ein globales Overlay-CSS gibt es
  nicht — das `<Teleport to="body">`-Overlay hatte also kein
  `position: fixed` und landete unsichtbar am Seitenende. Das Modal war da,
  nur nicht zu sehen.

  Dieser Defekt ist **nicht durch Sorgfalt vermeidbar**: Die Ursache (das
  fehlende Overlay-CSS) liegt in einer anderen Datei als der Fehler (der
  Knopf, der scheinbar nichts tut) — dieselbe Klasse wie #1731 und #1805.
  Solange jedes Modal sein Overlay selbst stylt, ist er reproduzierbar.

  VERSCHACHTELUNG
  Prompt-Modal über Bewertungs-Modal ist der Normalfall. Jede Ebene bekommt
  **eine** z-index-Stufe (`_offen` zählt mit), nicht drei Overlays auf 1000 —
  und **Escape schließt nur die oberste**. Ohne diese Einschränkung nähme ein
  Tastendruck dem Anwender beide Dialoge und damit seine Eingabe.

  Slots: `kopf` (Titelzeile, Vorgabe: `titel`), `inhalt`, `fuss`.
-->
<template>
  <Teleport to="body">
    <div
      class="mr-overlay"
      :style="{ zIndex: zIndex }"
      @mousedown.self="aufHintergrund"
    >
      <div
        ref="dialog"
        class="mr-dialog"
        :class="breiteKlasse"
        role="dialog"
        aria-modal="true"
        :aria-label="titel || 'Dialog'"
        tabindex="-1"
      >
        <div class="mr-kopf">
          <slot name="kopf">
            <h3>{{ titel }}</h3>
          </slot>
          <button class="mr-schliessen" type="button"
                  title="Schließen" aria-label="Schließen"
                  @click="schliessen">✕</button>
        </div>
        <div class="mr-inhalt">
          <slot name="inhalt"><slot /></slot>
        </div>
        <div v-if="$slots.fuss" class="mr-fuss">
          <slot name="fuss" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{
  /** Überschrift; dient zugleich als `aria-label`. */
  titel?: string
  /** Breite: `normal` (800px) | `breit` (1000px) | `schmal` (560px). */
  breite?: 'schmal' | 'normal' | 'breit'
  /** Klick auf den Hintergrund schließt. Aus, wo Eingaben verloren gingen. */
  hintergrundSchliesst?: boolean
}>(), {
  titel: '',
  breite: 'normal',
  hintergrundSchliesst: true,
})

const emit = defineEmits<{ close: [] }>()

// Wie viele Rahmen gerade offen sind — modulweit, damit jede Ebene ihre
// eigene z-index-Stufe und ihren eigenen Escape-Anspruch bekommt.
let _offen = 0

const ebene = ref(0)
const dialog = ref<HTMLElement | null>(null)
let vorherFokussiert: HTMLElement | null = null

const zIndex = computed(() => 1100 + ebene.value * 100)
const breiteKlasse = computed(() => `mr-${props.breite}`)

const schliessen = () => emit('close')

const aufHintergrund = () => {
  if (props.hintergrundSchliesst) schliessen()
}

const aufTaste = (e: KeyboardEvent) => {
  // Nur die oberste Ebene reagiert — sonst schließt ein Tastendruck den
  // ganzen Stapel und nimmt die Eingabe im darunterliegenden Dialog mit.
  if (e.key === 'Escape' && ebene.value === _offen) {
    e.stopPropagation()
    schliessen()
  }
}

onMounted(() => {
  _offen += 1
  ebene.value = _offen
  vorherFokussiert = (document.activeElement as HTMLElement) || null
  // Der Fokus muss in den Dialog, sonst tippt die Tastatur weiter in die
  // Maske dahinter und Escape erreicht uns gar nicht.
  dialog.value?.focus()
  document.addEventListener('keydown', aufTaste)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', aufTaste)
  _offen = Math.max(0, _offen - 1)
  try {
    vorherFokussiert?.focus()
  } catch { /* Element kann inzwischen weg sein */ }
})
</script>

<style scoped>
/* `position: fixed` steht hier und nirgends sonst — das war #1535. */
.mr-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  padding: 16px;
}

.mr-dialog {
  background: white; border-radius: 8px;
  display: flex; flex-direction: column;
  width: 90%; max-height: 90vh;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
  outline: none;
}

.mr-schmal { max-width: 560px; }
.mr-normal { max-width: 800px; }
.mr-breit { max-width: 1000px; }

.mr-kopf {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
}

.mr-kopf :deep(h3) {
  margin: 0; color: var(--color-primary); font-size: 16px;
}

.mr-schliessen {
  background: none; border: none; font-size: 22px; line-height: 1;
  color: #999; cursor: pointer; padding: 0 4px;
}

.mr-schliessen:hover { color: #333; }

.mr-inhalt { flex: 1; overflow-y: auto; padding: 16px 20px; }

.mr-fuss {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 20px; border-top: 1px solid var(--color-border);
}

@media (max-width: 640px) {
  .mr-dialog { width: 100%; max-height: 95vh; }
}
</style>
