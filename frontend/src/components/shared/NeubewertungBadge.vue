<template>
  <span v-if="sichtbar" class="nb-badge" :title="titel">⚠️ Neubewertung</span>
</template>

<script setup lang="ts">
/**
 * „Neubewertung erforderlich" in Listen und Kacheln (#1850).
 *
 * Die Markierung stand bisher nur im geöffneten Editor. Wer sie dort sieht,
 * hat das Objekt schon aufgeschlagen — gesucht wird sie aber in der Liste:
 * „Was hat sich getan, seit ich zuletzt hingesehen habe?" Deshalb dieselbe
 * Markierung an der Zeile, mit dem Anlass im Tooltip.
 *
 * Die Komponente ist absichtlich dumm: Sie liest nur Text. Ob der Marker
 * vom Issue-Abgleich oder von einem Pentest-Befund stammt (#1584), steht im
 * Text und nicht in einer Prop.
 */
import { computed } from 'vue'
import { hatNeubewertung, neubewertungTitel } from '../../utils/neubewertung'

const props = defineProps<{
  /** Der Freitext des Objekts (Kommentar, Notiz, Bemerkung, Triage). */
  text?: unknown
  /** Weiterer Text, der die Markierung tragen kann. */
  text2?: unknown
}>()

const sichtbar = computed(() => hatNeubewertung(props.text, props.text2))
const titel = computed(() => neubewertungTitel(props.text, props.text2))
</script>

<style scoped>
.nb-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 10px;
  /* Gleiche Farben wie der Badge im Editor (RequirementActions) — es ist
     dieselbe Aussage und soll nicht nach zwei verschiedenen aussehen. */
  background: #fff3e0;
  color: #b26a00;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: help;
}
</style>
