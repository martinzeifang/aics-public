<!--
  QuellenKnopf — „aus den Quellen füllen" an einem einzelnen Feld (#1900).

  Meldung aus dem Betrieb: „Der Knopf ist viel zu groß und passt nicht so
  richtig in das Design."

  WARUM ER ZU GROSS WAR
  Er trug seinen Text mit („⚙ füllen" bzw. „⚙ ersetzen") — bei 18 Feldern 18
  Textknöpfe in den Beschriftungszeilen. Schlimmer als die Größe war die
  **wechselnde Breite**: Sobald der Anwender etwas eintippte, wurde aus
  „⚙ füllen" ein „⚙ ersetzen", die Beschriftungszeile wurde länger und das
  Layout sprang beim Schreiben. Jetzt ist es ein Symbolknopf mit **fester**
  Größe; die Handlung steht im Tooltip und in `aria-label`, wo sie auch für
  Screenreader ankommt (vorher stand dort gar nichts Eigenes).

  „ERSETZEN" BLEIBT UNTERSCHEIDBAR
  Ein gefülltes Feld wird nie ohne ausdrücklichen Klick überschrieben
  (#1769/#1773) — also muss sichtbar sein, dass dieser Klick etwas ersetzt.
  Das macht jetzt die Farbe (orange statt blau) und der Tooltip, nicht die
  Breite. Die Information geht nicht verloren, sie wandert nur dorthin, wo sie
  das Layout nicht verschiebt.

  EINE KOMPONENTE, ZWEI FORMULARE
  Den Knopf gab es zweimal — in `cra/` und in `aiact/KonformitaetserklaerungForm.vue`,
  mit identischem CSS und identischem Verhalten. Zusammengeführt ist genau das,
  was dasselbe ist: der Knopf. Die Zeilenstruktur der beiden Formulare bleibt
  bei ihnen, denn sie ist wirklich verschieden (CRA baut die ganze Zeile, der
  AI Act nur den Knopf). Eine Komponente, die beides vereinheitlichen wollte,
  hätte zwei Layouts in einen Baustein gepresst.
-->
<template>
  <span class="quellen-knopf">
    <button
      type="button"
      class="knopf"
      :class="{ ersetzt: gefuellt }"
      :title="titel"
      :aria-label="titel"
      @click="emit('fuellen')"
    >⚙</button>
    <span v-if="quelle" class="quelle">{{ quelle }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** Woher der Wert kommt — erscheint neben dem Knopf und im Tooltip. */
  quelle: string
  /** Trägt das Feld schon einen Wert? Dann ersetzt der Klick ihn. */
  gefuellt?: boolean
}>()

const emit = defineEmits<{ (e: 'fuellen'): void }>()

const titel = computed(() =>
  props.gefuellt
    ? `Eingabe ersetzen — aus den Quellen: ${props.quelle}`
    : `Aus den Quellen füllen: ${props.quelle}`,
)
</script>

<style scoped>
.quellen-knopf { display: inline-flex; align-items: center; gap: 4px; }

/* Feste Größe: Der Knopf darf seine Breite nicht ändern, wenn aus „füllen"
   ein „ersetzen" wird — sonst springt die Zeile beim Tippen. */
.knopf {
  width: 18px; height: 18px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid #cfd8dc; border-radius: 4px; background: #fff;
  font-size: 11px; line-height: 1; color: #607d8b; cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background 0.12s;
}
/* Hover fehlte ganz — ein Knopf ohne Rückmeldung sieht aus wie ein Symbol. */
.knopf:hover { border-color: #1565c0; color: #1565c0; background: #f5f9ff; }
.knopf:focus-visible { outline: 2px solid #1565c0; outline-offset: 1px; }

/* Ersetzen ist die eingreifendere Handlung und wird dadurch kenntlich —
   nicht durch mehr Text. */
.knopf.ersetzt { color: #ef6c00; border-color: #ffcc80; }
.knopf.ersetzt:hover { border-color: #ef6c00; color: #e65100; background: #fff8f0; }

.quelle { color: #90a4ae; font-size: 10px; }
</style>
