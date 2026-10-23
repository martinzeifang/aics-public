<template>
  <div class="ki-panel">
    <div class="ki-steps">
      <b>So funktioniert's:</b> 1. direkt mit der KI ausführen ({{ providerLabel }}) <i>oder</i> 2. Prompt kopieren → in ein KI-Tool einfügen → JSON-Antwort hier einfügen und übernehmen.
    </div>

    <!-- Transparenz: was geht an die KI -->
    <details class="ki-transparency">
      <summary>🔍 Diese Daten werden an die KI übermittelt</summary>
      <p class="hint">
        <template v-if="provider === 'cloud'">⚠️ <b>Cloud-Provider</b> aktiv — die Daten verlassen bei der direkten Ausführung das Haus (mit Redaction + Audit).</template>
        <template v-else-if="provider === 'on_prem'"><b>Lokaler Provider</b> aktiv — die Daten bleiben bei der direkten Ausführung im Haus.</template>
        <template v-else>Der genutzte KI-Provider richtet sich nach der KI-Einstellung (lokal oder Cloud).</template>
        Beim Kopieren gehen die Daten an dein gewähltes KI-Tool.
      </p>
      <textarea readonly rows="8" class="mono">{{ prompt || 'Prompt wird geladen …' }}</textarea>
    </details>

    <div class="ki-actions">
      <button class="ai" :disabled="busy || provider === 'none'" @click="$emit('ollama')"
              :title="provider === 'none' ? 'Kein KI-Provider konfiguriert (Admin → KI-Einstellungen)' : 'Über den konfigurierten Provider ausführen'">
        ⚡ Direkt mit KI ausführen <span v-if="provider !== 'none'">({{ providerBadge }})</span>
      </button>
      <button :disabled="!prompt" @click="copy">📋 Prompt kopieren</button>
      <span v-if="copied" class="copied">✓ in die Zwischenablage kopiert</span>
    </div>

    <div class="ki-paste">
      <label>KI-Antwort (JSON) einfügen</label>
      <textarea v-model="response" rows="4" class="mono" placeholder="Antwort des KI-Tools (JSON) hier einfügen …"></textarea>
      <button class="btn-primary" :disabled="!response" @click="$emit('paste', response)">Antwort übernehmen</button>
    </div>

    <div v-if="result" class="ki-result">
      <label>Ergebnis</label>
      <AnalysisCard :analysis="result" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import AnalysisCard from './AnalysisCard.vue'
import { useAiProviderStore } from '../../stores/aiProvider'

const props = defineProps<{ prompt: string; result: any; busy?: boolean }>()
defineEmits<{ (e: 'ollama'): void; (e: 'paste', response: string): void }>()
const response = ref('')
const copied = ref(false)

// #1470: KI-Analyse läuft über den konfigurierten Provider (lokal ODER Cloud, #1342) —
// nicht mehr „nur Ollama lokal". Badge/Texte spiegeln den aktiven Provider.
const aiProvider = useAiProviderStore()
const provider = computed(() => aiProvider.status?.provider ?? 'none')
const providerBadge = computed(() => provider.value === 'cloud' ? '☁️ Cloud' : provider.value === 'on_prem' ? '🖥️ Lokal' : '—')
const providerLabel = computed(() =>
  provider.value === 'cloud' ? 'Cloud' : provider.value === 'on_prem' ? 'lokal' : 'lokal oder Cloud — je nach KI-Einstellung')
onMounted(() => { if (!aiProvider.loaded) aiProvider.loadStatus() })
async function copy() {
  try {
    await navigator.clipboard.writeText(props.prompt)
    copied.value = true
    setTimeout(() => (copied.value = false), 2500)
  } catch {
    copied.value = false
  }
}
</script>

<style scoped>
.ki-panel { border: 1px solid #e1e6ec; border-radius: 8px; padding: 12px; background: #fbfdff; }
.ki-steps { font-size: 13px; color: #555; margin-bottom: 10px; }
.ki-transparency { margin-bottom: 10px; }
.ki-transparency summary { cursor: pointer; color: #6a1b9a; font-weight: 600; font-size: 13px; }
.ki-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0; }
.copied { color: #1b5e20; font-size: 13px; }
.ki-paste { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.ki-paste label, .ki-result label { font-size: 12px; text-transform: uppercase; color: #90a4ae; }
.mono { width: 100%; font-family: Consolas, monospace; font-size: 12px; padding: 8px; border: 1px solid #cfd8dc; border-radius: 4px; }
.ki-result { margin-top: 12px; }
button { background: #fff; border: 1px solid #1565c0; color: #1565c0; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 13px; }
button:hover { background: #e3f2fd; } button:disabled { opacity: .5; cursor: default; }
button.ai { border-color: #6a1b9a; color: #6a1b9a; } button.btn-primary { background: #1565c0; color: #fff; }
</style>
