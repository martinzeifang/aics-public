<template>
  <!-- #1573: einheitliche Ergebnis-Darstellung der automatischen KI-Bewertung (alle Module) -->
  <div class="abe">
    <div class="abe-score">
      <span class="abe-label">{{ wertLabel }}</span>
      <span :class="['abe-value', r.ton]">{{ r.wert }}</span>
    </div>
    <!-- #1862: zuerst der Grund hinzusehen, dann der Entwurf. Die Hinweise
         rechnet der Server (shared/ki_pruefhinweise) — hier wird nichts
         abgeleitet, sonst gäbe es die Regel zweimal. Sie sagen ausdrücklich
         nicht, ob der Entwurf falsch ist, nur woran man zweifeln sollte. -->
    <div v-if="hinweise.length" class="abe-hinweise">
      <h4>Worauf du schauen solltest</h4>
      <ul>
        <li v-for="h in hinweise" :key="h.art" :class="'g' + h.gewicht">{{ h.text }}</li>
      </ul>
      <p v-if="abweichung" class="abe-abw">
        Zwei Läufe, zwei Ergebnisse: <strong>{{ abweichung }}</strong>
      </p>
    </div>
    <div class="abe-block">
      <h4>Begründung der KI</h4>
      <p class="abe-text">{{ r.begruendung || '— keine Begründung geliefert —' }}</p>
    </div>
    <div v-if="r.massnahmen.length" class="abe-block">
      <h4>Empfohlene Maßnahmen</h4>
      <ul class="abe-list"><li v-for="(m, i) in r.massnahmen" :key="i">{{ m }}</li></ul>
    </div>
    <div v-if="r.normbezug" class="abe-block">
      <h4>Normbezug</h4>
      <p class="abe-text">{{ r.normbezug }}</p>
    </div>
    <p class="abe-disclaimer">🤖 KI-generiert<span v-if="r.provider"> ({{ r.provider === 'cloud' ? 'Cloud' : 'Lokal' }})</span>
      — fachlich zu prüfen. Das Ergebnis wurde gespeichert.</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { normalizeAutoResult } from '../../utils/autoBewertung'

const props = withDefaults(defineProps<{ payload: any; wertLabel?: string }>(), { wertLabel: 'Bewertung' })
const r = computed(() => normalizeAutoResult(props.payload))

/** #1862: vom Server gerechnet (`pruefhinweise`); fehlt das Feld, gibt es nichts. */
const hinweise = computed<{ art: string; text: string; gewicht: number }[]>(() => {
  const hs = props.payload?.pruefhinweise
  return Array.isArray(hs) ? hs : []
})
/** #1863: „4/5 vs. 2/5" — leer, wenn die Läufe einig waren oder nur einer lief. */
const abweichung = computed(() => String(props.payload?.abweichung || ''))
</script>

<style scoped>
.abe { display: flex; flex-direction: column; gap: 10px; }
.abe-score { display: flex; align-items: baseline; gap: 10px; padding: 10px 12px;
  background: #f5faff; border: 1px solid #cfe3f7; border-radius: 8px; }
.abe-label { font-size: 12px; color: #546e7a; text-transform: uppercase; letter-spacing: .03em; }
.abe-value { font-size: 22px; font-weight: 700; }
.abe-value.gut { color: #2e7d32; }
.abe-value.mittel { color: #ef6c00; }
.abe-value.schlecht { color: #c62828; }
.abe-value.neutral { color: #455a64; }
.abe-block h4 { margin: 0 0 4px; font-size: 13px; color: #1565c0; }
.abe-text { margin: 0; font-size: 13px; white-space: pre-wrap; color: #37474f; }
.abe-list { margin: 0; padding-left: 18px; font-size: 13px; color: #37474f; }
.abe-disclaimer { margin: 0; font-size: 12px; color: #78909c; font-style: italic; }
.abe-hinweise { background: #fff8e1; border: 1px solid #ffe082; border-radius: 8px; padding: 8px 12px; }
.abe-hinweise h4 { margin: 0 0 4px; font-size: 13px; color: #8d6e00; }
.abe-hinweise ul { margin: 0; padding-left: 18px; font-size: 13px; }
.abe-hinweise li.g3 { color: #c62828; font-weight: 600; }
.abe-hinweise li.g2 { color: #ef6c00; }
.abe-hinweise li.g1 { color: #78909c; }
.abe-abw { margin: 6px 0 0; font-size: 12px; color: #c62828; }
</style>
