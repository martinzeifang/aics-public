<!--
  Fehlermeldung, die sich schließen lässt (#1781).

  Bis v8.0.4 wurden Fehler als `<div class="alert alert-error">{{ error }}</div>`
  gezeigt: 90 Stellen in 46 Dateien, davon 11 mit einem Klick-zum-Schließen, das
  niemand sehen konnte — die Meldung stand, bis die nächste Aktion sie zufällig
  überschrieb. In einer Oberfläche, in der man danach weiterarbeitet, ist eine
  Meldung ohne Ausgang ein Fehler in der Darstellung des Fehlers.

  Die Komponente schließt sich **selbst**, auch wenn der Aufrufer kein
  ``@close`` reicht: Sonst hätte jede der 46 Dateien eine eigene Zuweisung
  gebraucht, und genau solche Sweeps lassen einzelne Stellen zurück. Wer die
  Meldung im eigenen Zustand löschen will, hört auf ``close``.

  Erscheint ein **neuer** Text, wird wieder angezeigt — sonst bliebe eine einmal
  weggeklickte Stelle für den Rest der Sitzung stumm. Bei gleichem Text nach dem
  Schließen hilft, dass die Aufrufer ihren Fehler vor jeder Aktion zurücksetzen;
  wer ``@close`` reicht, bekommt das ohnehin richtig.
-->
<template>
  <div v-if="sichtbar && text" :class="['fh', art]" role="alert" aria-live="polite">
    <span class="fh-icon" aria-hidden="true">{{ symbol }}</span>
    <div class="fh-text">
      <slot>{{ text }}</slot>
    </div>
    <button type="button" class="fh-close" :aria-label="schliessenText"
            :title="schliessenText" @click="schliessen">✕</button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  /** Der Meldungstext. Leer = nichts wird gezeigt. */
  text?: string | null
  /** Art der Meldung — die Farbe folgt ihr, nicht der Dekoration. */
  art?: 'fehler' | 'warnung' | 'hinweis' | 'erfolg'
}>(), { text: '', art: 'fehler' })

const emit = defineEmits<{ (e: 'close'): void }>()

const sichtbar = ref(true)
const symbol = computed(() => ({
  warnung: '⚠️', hinweis: 'ℹ️', erfolg: '✅', fehler: '⛔',
}[props.art] || '⛔'))
const schliessenText = computed(() => (
  props.art === 'fehler' ? 'Fehlermeldung schließen' : 'Meldung schließen'
))
// Dieselbe Leiste trägt in einigen Masken auch die Erfolgsmeldung („Vorgang
// freigegeben"). Sie dort als eigenes Element zu belassen hätte bedeutet, dass
// ausgerechnet die halbe Hälfte wieder nicht schließbar ist.

watch(() => props.text, (neu, alt) => {
  if (neu && neu !== alt) sichtbar.value = true
})

function schliessen() {
  sichtbar.value = false
  emit('close')
}
</script>

<style scoped>
.fh {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.45;
  margin: 8px 0;
  border: 1px solid;
}
.fh-icon { flex: 0 0 auto; font-size: 14px; line-height: 1.3; }
.fh-text { flex: 1; min-width: 0; overflow-wrap: anywhere; }

.fh.fehler { background: #ffebee; border-color: #ef9a9a; color: #c62828; }
.fh.warnung { background: #fff8e1; border-color: #ffe082; color: #6d4c41; }
.fh.hinweis { background: #e3f2fd; border-color: #90caf9; color: #1565c0; }
.fh.erfolg { background: #e8f5e9; border-color: #a5d6a7; color: #2e7d32; }

.fh-close {
  flex: 0 0 auto;
  background: none;
  border: none;
  color: inherit;
  opacity: .65;
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 4px;
}
.fh-close:hover { opacity: 1; background: rgba(0, 0, 0, .07); }
.fh-close:focus-visible { outline: 2px solid currentColor; outline-offset: 1px; }
</style>
