<!--
  „Aus den Quellen füllen" — die Leiste über einem Formular (#1893).

  Ein Knopf, nicht achtzehn. Der Zähler sagt, wie viele leere Felder eine
  Quelle haben; ist er null, ist der Knopf gesperrt statt wirkungslos
  (#1805: kein sichtbarer Knopf ohne Wirkung).

  Der Hinweis daneben ist keine Dekoration: Er sagt, dass gefüllte Felder
  stehen bleiben. Ohne ihn klickt niemand, der etwas eingetippt hat.
-->
<template>
  <div class="quellen-leiste">
    <button class="btn-secondary" :disabled="!anzahl" @click="emit('alle')">
      ⚙ Aus den Quellen füllen
      <span v-if="anzahl" class="zaehler">{{ anzahl }}</span>
    </button>
    <!-- Der Assistenten-Knopf kommt als Slot und nicht als Event: Nicht jede
         Maske hat einen, und ein Event, für das niemand zuhört, ist der Befund
         aus #1805. So trägt jede Maske ihren eigenen Knopf — oder keinen. -->
    <slot name="eigene" />
    <span class="hint small">
      Füllt nur leere Felder. Was gefüllt ist, bleibt stehen — ersetzen ist ein
      eigener Klick am Feld.
    </span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  /** Zahl der leeren Felder mit Quelle. */
  anzahl: number
}>()
const emit = defineEmits<{ (e: 'alle'): void }>()
</script>

<style scoped>
.quellen-leiste { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0 4px; }
.zaehler { background: #1565c0; color: #fff; border-radius: 9px; padding: 0 6px; font-size: 11px; margin-left: 4px; }
.hint { color: #607d8b; font-size: 12px; }
.small { font-size: 11px; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
