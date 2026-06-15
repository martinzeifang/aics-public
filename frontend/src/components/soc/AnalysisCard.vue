<template>
  <div class="analysis-card">
    <div v-if="a._parse_error" class="parse-err">
      KI-Antwort war kein gültiges JSON — Rohtext:
      <pre>{{ a._raw }}</pre>
    </div>
    <template v-else>
      <div v-if="a.zusammenfassung" class="row summary">{{ a.zusammenfassung }}</div>
      <div class="badges">
        <span v-if="schwere" class="badge" :class="schwere">Schwere: {{ sevDe(schwere) }}</span>
        <span v-if="a.prioritaet" class="badge prio">Priorität {{ a.prioritaet }}</span>
        <span v-if="a.false_positive_wahrscheinlichkeit" class="badge fp">FP-Wahrscheinlichkeit: {{ fpDe(a.false_positive_wahrscheinlichkeit) }}</span>
        <span v-if="a.empfohlene_aktion" class="badge act">{{ aktionDe(a.empfohlene_aktion) }}</span>
        <span v-if="a.ist_echter_vorfall !== undefined" class="badge" :class="a.ist_echter_vorfall ? 'critical' : 'low'">{{ a.ist_echter_vorfall ? 'Echter Vorfall' : 'Kein Vorfall' }}</span>
        <span v-if="a.personenbezug_moeglich" class="badge pers">Personenbezug möglich</span>
      </div>
      <div v-if="a.angriffsmuster" class="row"><b>Angriffsmuster:</b> {{ a.angriffsmuster }}</div>
      <div v-if="a.begruendung" class="row"><b>Begründung:</b> {{ a.begruendung }}</div>
      <div v-if="(a.mitre||[]).length" class="row"><b>MITRE:</b>
        <span v-for="m in a.mitre" :key="m" class="chip">{{ m }}</span>
      </div>
      <div v-if="(a.meldepflicht_pruefen||[]).length" class="row"><b>Meldepflicht prüfen:</b>
        <span v-for="m in a.meldepflicht_pruefen" :key="m" class="chip warn">{{ String(m).toUpperCase() }}</span>
      </div>
      <div v-if="(a.empfohlene_eindaemmung||[]).length" class="row"><b>Empfohlene Eindämmung:</b>
        <ul><li v-for="(s,i) in a.empfohlene_eindaemmung" :key="i">{{ s }}</li></ul>
      </div>
      <div v-if="(a.naechste_schritte||[]).length" class="row"><b>Nächste Schritte:</b>
        <ul><li v-for="(s,i) in a.naechste_schritte" :key="i">{{ s }}</li></ul>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ analysis: any }>()
const a = computed(() => props.analysis || {})
const schwere = computed(() => a.value.severity || a.value.schwere || '')
const SEV: Record<string, string> = { critical: 'Kritisch', high: 'Hoch', medium: 'Mittel', low: 'Niedrig' }
const FP: Record<string, string> = { low: 'gering', medium: 'mittel', high: 'hoch' }
const ACT: Record<string, string> = { investigate: 'Untersuchen', monitor: 'Beobachten', contain: 'Eindämmen', 'false-positive': 'False Positive', patch: 'Patchen' }
function sevDe(s: string) { return SEV[s] || s }
function fpDe(s: string) { return FP[s] || s }
function aktionDe(s: string) { return ACT[s] || s }
</script>

<style scoped>
.analysis-card { background: #e8f5e9; border: 1px solid #c8e6c9; border-radius: 6px; padding: 12px; font-size: 13px; color: #1b3a1f; }
.row { margin: 6px 0; }
.summary { font-weight: 600; font-size: 14px; }
.badges { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: #c8e6c9; color: #1b5e20; }
.badge.critical { background: #b71c1c; color: #fff; } .badge.high { background: #e65100; color: #fff; }
.badge.medium { background: #f9a825; color: #333; } .badge.low { background: #607d8b; color: #fff; }
.badge.prio { background: #1565c0; color: #fff; } .badge.fp { background: #8d6e63; color: #fff; }
.badge.act { background: #6a1b9a; color: #fff; } .badge.pers { background: #ad1457; color: #fff; }
.chip { display: inline-block; background: #fff; border: 1px solid #90a4ae; border-radius: 8px; padding: 1px 7px; margin: 0 4px 2px 0; font-size: 12px; }
.chip.warn { border-color: #e65100; color: #e65100; }
.parse-err { color: #b71c1c; }
.parse-err pre { white-space: pre-wrap; background: #fff; padding: 8px; border-radius: 4px; }
ul { margin: 4px 0 0 18px; }
</style>
