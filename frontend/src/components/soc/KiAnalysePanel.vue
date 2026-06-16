<template>
  <div class="ki-panel">
    <div class="ki-steps">
      <b>So funktioniert's:</b> 1. lokal mit Ollama analysieren <i>oder</i> 2. Prompt kopieren → in ChatGPT einfügen → JSON-Antwort hier einfügen und übernehmen.
    </div>

    <!-- Transparenz: was geht an die KI -->
    <details class="ki-transparency">
      <summary>🔍 Diese Daten werden an die KI übermittelt</summary>
      <p class="hint">Bei <b>Ollama</b> bleiben die Daten lokal im Haus. Beim Kopieren gehen sie an dein gewähltes KI-Tool.</p>
      <textarea readonly rows="8" class="mono">{{ prompt || 'Prompt wird geladen …' }}</textarea>
    </details>

    <div class="ki-actions">
      <button class="ai" :disabled="busy" @click="$emit('ollama')">🤖 Lokal mit Ollama analysieren</button>
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
import { ref } from 'vue'
import AnalysisCard from './AnalysisCard.vue'

const props = defineProps<{ prompt: string; result: any; busy?: boolean }>()
defineEmits<{ (e: 'ollama'): void; (e: 'paste', response: string): void }>()
const response = ref('')
const copied = ref(false)
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
