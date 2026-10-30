<!--
  Befunde eines Formulars — vor dem Abschluss, nicht danach (#1885/#1893).

  Die Reihenfolge ist die Wirkung: blockierend zuerst. Ein Hinweis, der über
  einem blockierenden Befund steht, verdeckt den Grund, warum der Knopf
  gesperrt ist.

  Die Liste steht **über** dem Formular und nicht am Seitenende: Sie nennt
  Feld und Behebung, und der Anwender soll sie lesen, bevor er tippt.
-->
<template>
  <div v-if="sortiert.length" class="befunde">
    <h5>{{ titel }}</h5>
    <ul>
      <li v-for="(b, i) in sortiert" :key="i" :class="b.wirkung">
        <strong>{{ wirkungLabel(b.wirkung) }}</strong>
        <span v-if="b.nr"> · Nr. {{ b.nr }}</span>: {{ b.text }}
        <span v-if="b.hinweis" class="small"> — {{ b.hinweis }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { wirkungLabel, type Befund } from '../../composables/useFormularVorschlag'

const props = withDefaults(defineProps<{
  befunde?: Befund[]
  titel?: string
}>(), { titel: 'Vor dem Abschluss zu klären' })

const RANG: Record<string, number> = { blockiert: 0, bestaetigung: 1, hinweis: 2 }
const sortiert = computed(() =>
  [...(props.befunde || [])].sort(
    (a, b) => (RANG[a.wirkung] ?? 9) - (RANG[b.wirkung] ?? 9)))
</script>

<style scoped>
.befunde { border: 1px solid #ef9a9a; background: #fff5f5; border-radius: 6px; padding: 8px 10px; margin: 8px 0; }
.befunde h5 { margin: 0 0 4px; color: #c62828; font-size: 13px; }
.befunde ul { margin: 0 0 0 18px; font-size: 12px; }
.befunde li.blockiert { color: #c62828; font-weight: 600; }
.befunde li.bestaetigung { color: #ef6c00; }
.befunde li.hinweis { color: #455a64; }
.befunde .small { font-weight: 400; color: #607d8b; }
</style>
