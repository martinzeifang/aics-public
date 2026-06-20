<template>
  <div class="alert-detail" v-if="alert">
    <div class="ad-head">
      <span class="sev-tag" :class="alert.severity">{{ sevDe(alert.severity) }}</span>
      <span class="ad-title">{{ alert.description }}</span>
      <span class="status-pill">{{ statusDe(alert.status) }}</span>
    </div>
    <div class="field-grid">
      <div><label>Regel-ID</label><span>{{ alert.rule_id }}</span></div>
      <div><label>Level</label><span>{{ alert.rule_level }}</span></div>
      <div><label>Agent / Asset</label><span>{{ alert.agent_name }} ({{ alert.agent_id }})</span></div>
      <div><label>Quell-IP</label><span>{{ alert.srcip || '—' }}</span></div>
      <div><label>Ort (location)</label><span>{{ alert.location || '—' }}</span></div>
      <div><label>Zeit</label><span>{{ alert.event_ts }}</span></div>
      <div class="full"><label>Regel-Gruppen</label>
        <span><span v-for="g in alert.groups || []" :key="g" class="chip">{{ g }}</span></span>
      </div>
      <div class="full" v-if="(mitreIds || []).length"><label>MITRE ATT&CK</label>
        <span>
          <a v-for="m in mitreIds" :key="m" class="chip mitre" :href="`https://attack.mitre.org/techniques/${m}/`" target="_blank">{{ m }}</a>
          <em v-if="mitreTactics.length"> · {{ mitreTactics.join(', ') }}</em>
        </span>
      </div>
    </div>
    <div class="rawlog-wrap">
      <label>Wazuh-Rohlog</label>
      <pre class="rawlog">{{ alert.full_log || '(kein full_log)' }}</pre>
    </div>
    <details v-if="hasRaw" class="raw-json">
      <summary>Vollständiges Wazuh-Event (JSON)</summary>
      <pre>{{ JSON.stringify(alert.raw_json, null, 2) }}</pre>
    </details>
    <div v-if="hasAnalysis" class="ad-analysis">
      <label>🤖 KI-Analyse</label>
      <AnalysisCard :analysis="alert.analysis_json" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AnalysisCard from './AnalysisCard.vue'
const props = defineProps<{ alert: any }>()
const mitreIds = computed(() => (props.alert?.mitre?.id) || [])
const mitreTactics = computed(() => (props.alert?.mitre?.tactic) || [])
const hasRaw = computed(() => props.alert?.raw_json && Object.keys(props.alert.raw_json).length > 0)
const hasAnalysis = computed(() => props.alert?.analysis_json && Object.keys(props.alert.analysis_json).length > 0)
const SEV: Record<string, string> = { critical: 'Kritisch', high: 'Hoch', medium: 'Mittel', low: 'Niedrig' }
const ST: Record<string, string> = { new: 'Neu', in_review: 'In Prüfung', false_positive: 'False Positive', confirmed: 'Bestätigt', suppressed: 'Unterdrückt' }
function sevDe(s: string) { return SEV[s] || s }
function statusDe(s: string) { return ST[s] || s }
</script>

<style scoped>
.alert-detail { font-size: 13px; }
.ad-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.ad-title { font-weight: 600; font-size: 15px; flex: 1; }
.sev-tag { padding: 2px 10px; border-radius: 10px; font-size: 12px; color: #fff; }
.sev-tag.critical { background: #b71c1c; } .sev-tag.high { background: #e65100; }
.sev-tag.medium { background: #f9a825; color: #333; } .sev-tag.low { background: #607d8b; }
.status-pill { background: #eceff1; border-radius: 10px; padding: 2px 10px; font-size: 12px; }
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; margin-bottom: 14px; }
.field-grid .full { grid-column: 1 / -1; }
.field-grid label { display: block; font-size: 11px; text-transform: uppercase; color: #90a4ae; letter-spacing: .3px; }
.field-grid span { font-size: 13px; color: #263238; }
.chip { display: inline-block; background: #eceff1; border-radius: 8px; padding: 1px 7px; margin: 0 4px 3px 0; font-size: 12px; }
.chip.mitre { background: #ede7f6; color: #4527a0; text-decoration: none; }
.rawlog-wrap label, .ad-analysis label { display: block; font-size: 11px; text-transform: uppercase; color: #90a4ae; margin-bottom: 4px; }
.rawlog { font-family: Consolas, monospace; font-size: 12px; background: #263238; color: #cfd8dc; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }
.raw-json { margin-top: 10px; }
.raw-json summary { cursor: pointer; color: #1565c0; font-size: 12px; }
.raw-json pre { font-family: Consolas, monospace; font-size: 11px; background: #f5f5f5; padding: 8px; border-radius: 4px; max-height: 280px; overflow: auto; }
.ad-analysis { margin-top: 14px; }
</style>
