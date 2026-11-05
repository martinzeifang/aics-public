<!--
  Fließtext aus einem Sprachmodell darstellen (#1783).

  Die Modelle schreiben Markdown, auch wenn man sie nicht darum bittet:
  ``**teilweise erfüllt**``, Absätze, Spiegelstriche. Wurde dieser Text als
  ``{{ text }}`` mit ``white-space: pre-wrap`` gedruckt, stand die Auszeichnung
  wörtlich im Dokument — in der Wasserstandsmeldung las der Kunde
  „**teilweise erfüllt**" mit Sternchen, und aus „- Punkt" wurde keine Liste.

  Gerendert wird über ``markdownToHtml``, das zuerst escapet und am Ende durch
  DOMPurify geht: Der Text stammt aus einem Modell und kann aus Unterlagen des
  Kunden gespeist sein — er ist Daten, nicht Markup.
-->
<template>
  <div v-if="text" :class="['prosa', { eng }]" v-html="html"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import markdownToHtml from '../../utils/markdownToHtml'

const props = withDefaults(defineProps<{
  text?: string | null
  /** Weniger Abstand — für Tabellenzellen und Listeneinträge. */
  eng?: boolean
}>(), { text: '', eng: false })

const html = computed(() => markdownToHtml(props.text || ''))
</script>

<style scoped>
.prosa :deep(p) { margin: 0 0 .6em; }
.prosa :deep(p:last-child) { margin-bottom: 0; }
.prosa :deep(ul), .prosa :deep(ol) { margin: .3em 0 .6em; padding-left: 1.3em; }
.prosa :deep(li) { margin: .15em 0; }
.prosa :deep(h1), .prosa :deep(h2), .prosa :deep(h3),
.prosa :deep(h4), .prosa :deep(h5), .prosa :deep(h6) {
  font-size: 1em; font-weight: 600; margin: .6em 0 .3em;
}
.prosa :deep(code) {
  font-family: Consolas, monospace; font-size: .92em;
  background: rgba(0, 0, 0, .05); border-radius: 3px; padding: 0 3px;
}
.prosa :deep(a) { color: #1565c0; }
.prosa.eng :deep(p) { margin: 0 0 .3em; }
.prosa.eng :deep(ul), .prosa.eng :deep(ol) { margin: .2em 0; }
</style>
