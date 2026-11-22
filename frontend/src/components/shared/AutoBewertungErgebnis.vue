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
      <h4>{{ $t('geteilt.autoBewertungErgebnis.woraufDuSchauenSolltest') }}</h4>
      <ul>
        <li v-for="h in hinweise" :key="h.art" :class="'g' + h.gewicht">{{ h.text }}</li>
      </ul>
      <p v-if="abweichung" class="abe-abw">
        {{ $t('geteilt.autoBewertungErgebnis.zweiLaufeZweiErgebnisse') }} <strong>{{ abweichung }}</strong>
      </p>
    </div>
    <div class="abe-block">
      <h4>{{ $t('geteilt.autoBewertungErgebnis.begrundungDerKI') }}</h4>
      <!--
        #2040: Hier stand `{{ … }}` mit `white-space: pre-wrap` — Absätze
        blieben, Markdown nicht. Der Anwender las `**teilweise erfüllt**` mit
        Sternchen und `- Punkt` statt einer Liste. Das ist die gemeinsame
        Ergebnisanzeige der automatischen KI-Bewertung **aller sechs Module**
        (#1573), also die häufigste Stelle, an der Modellprosa erscheint — und
        `ProsaText` wurde in #1783 genau dafür gebaut („Überall, wo Modelltext
        angezeigt wird, gehört diese Komponente hin").
      -->
      <ProsaText v-if="r.begruendung" :text="r.begruendung" />
      <p v-else class="abe-text">{{ $t('geteilt.autoBewertungErgebnis.keineBegrundungGeliefert') }}</p>
    </div>
    <div v-if="r.massnahmen.length" class="abe-block">
      <h4>{{ $t('common.empfohleneMassnahmen') }}</h4>
      <ul class="abe-list">
        <li v-for="(m, i) in r.massnahmen" :key="i"><ProsaText :text="m" eng /></li>
      </ul>
    </div>
    <div v-if="r.normbezug" class="abe-block">
      <h4>{{ $t('geteilt.autoBewertungErgebnis.normbezug') }}</h4>
      <ProsaText :text="r.normbezug" />
    </div>
    <p class="abe-disclaimer">{{ $t('geteilt.autoBewertungErgebnis.kIGeneriert') }}<span v-if="r.provider"> ({{ r.provider === 'cloud' ? $t('geteilt.autoBewertungErgebnis.cloud') : $t('geteilt.autoBewertungErgebnis.lokal') }})</span>
      {{ $t('geteilt.autoBewertungErgebnis.fachlichZuPrufenDasErgebnisWurdeGesp') }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { normalizeAutoResult } from '../../utils/autoBewertung'
import { t } from '../../i18n'
import ProsaText from './ProsaText.vue'

const props = withDefaults(defineProps<{ payload: any; wertLabel?: string }>(), { wertLabel: t('common.bewertung') })
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
