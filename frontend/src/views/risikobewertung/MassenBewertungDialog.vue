<template>
  <div class="modal-overlay" @mousedown.self="onCancel">
    <div class="modal-content">
      <div class="modal-header">
        <h3>🤖 Massen-Bewertung</h3>
        <button class="btn-close" @click="onCancel">✕</button>
      </div>

      <div class="modal-body">
        <p class="hint">
          Mehrere Risiken auf einmal bewerten — entweder automatisch über den
          konfigurierten KI-Provider oder manuell via Prompt-/JSON-Copy.
        </p>

        <div class="mode-tabs">
          <button :class="['mode-tab', { active: mode === 'ollama' }]" @click="mode = 'ollama'">
            ⚡ Automatisch (KI-API)
          </button>
          <button :class="['mode-tab', { active: mode === 'chatgpt' }]" @click="mode = 'chatgpt'">
            📝 Manuell (Prompt/JSON)
          </button>
        </div>

        <!-- Automatisch (Ollama oder Cloud) -->
        <div v-if="mode === 'ollama'" class="tab-content">
          <div class="info-banner">
            ℹ️ Nutzt den in den Einstellungen konfigurierten Provider (Ollama-Daemon
            oder Cloud-API). Prüfbar unter „Einstellungen → KI-Provider → 🔬 Diagnose".
          </div>
          <p>Diese Aktion bewertet alle <strong>{{ openCount }} offenen</strong> Risiken automatisch.</p>
          <button class="btn-primary" @click="runOllama" :disabled="busy">
            {{ busy ? '⏳ Läuft… (kann dauern)' : 'Bewertung starten' }}
          </button>

          <div v-if="ollamaResults.length > 0" class="results">
            <h4>Ergebnisse</h4>
            <table>
              <thead>
                <tr><th>ID</th><th>Status</th><th>Score</th><th>Level</th><th>Fehler</th></tr>
              </thead>
              <tbody>
                <tr v-for="(r, i) in ollamaResults" :key="i" :class="{ failed: !r.ok }">
                  <td>{{ r.risk_id }}</td>
                  <td>{{ r.ok ? '✓' : '✗' }}</td>
                  <td>{{ r.risikowert ?? '—' }}</td>
                  <td>{{ r.risiko_label || '—' }}</td>
                  <td class="error-cell">{{ r.error || '' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ChatGPT-JSON-Modus -->
        <div v-if="mode === 'chatgpt'" class="tab-content">
          <div class="info-banner">
            ℹ️ Workflow: Prompts kopieren → in ChatGPT einfügen → JSON-Antwort kopieren → hier einfügen → Übernehmen.
          </div>

          <div class="step">
            <h4>Schritt 1: Prompts generieren</h4>
            <p>Erzeugt Prompts für alle <strong>{{ openCount }}</strong> offenen Risiken.</p>
            <button class="btn-secondary" @click="generatePrompts" :disabled="busy">
              Prompts generieren
            </button>
          </div>

          <div v-if="prompts.length > 0" class="step">
            <h4>Schritt 2: Antworten einfügen</h4>
            <p>{{ prompts.length }} Prompts generiert. Pro Risiko Prompt kopieren, Antwort einfügen.</p>
            <div v-for="p in prompts" :key="p.risk_id" class="prompt-block">
              <div class="prompt-header">
                <strong>#{{ p.risk_id }}: {{ p.risk_name }}</strong>
                <button class="btn-small" @click="copyPrompt(p.prompt)">📋 Prompt kopieren</button>
              </div>
              <details>
                <summary>Prompt anzeigen</summary>
                <pre class="prompt-text">{{ p.prompt }}</pre>
              </details>
              <textarea
                v-model="responses[p.risk_id]"
                rows="4"
                placeholder='JSON-Antwort hier einfügen, z.B. {"felder": {...}, "bewertung": "..."}'
              ></textarea>
            </div>
          </div>

          <div v-if="prompts.length > 0" class="step">
            <h4>Schritt 3: Übernehmen</h4>
            <button class="btn-primary" @click="applyResponses" :disabled="busy || filledResponseCount === 0">
              {{ busy ? 'Wendet an…' : `${filledResponseCount} Antworten übernehmen` }}
            </button>
            <div v-if="applyResults" class="apply-result">
              <strong>{{ applyResults.applied_count }} übernommen.</strong>
              <span v-if="applyResults.errors.length > 0">{{ applyResults.errors.length }} Fehler.</span>
            </div>
          </div>
        </div>

        <div v-if="error" class="alert alert-error">{{ error }}</div>
      </div>

      <div class="modal-footer">
        <button class="btn-secondary" @click="onCancel">Schließen</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRisikobewertungStore } from '../../stores/risikobewertung'
import apiClient from '../../api/client'

const props = defineProps<{ projektName: string }>()
const emit = defineEmits<{ cancel: []; refresh: [] }>()

const rb = useRisikobewertungStore()

const mode = ref<'ollama' | 'chatgpt'>('ollama')
const busy = ref(false)
const error = ref('')

const ollamaResults = ref<any[]>([])
const prompts = ref<any[]>([])
const responses = ref<Record<number, string>>({})
const applyResults = ref<any | null>(null)

const openCount = computed(() => rb.risiken.filter(r => !r.is_resolved).length)
const filledResponseCount = computed(() =>
  Object.values(responses.value).filter(v => (v || '').trim()).length
)

const runOllama = async () => {
  busy.value = true
  error.value = ''
  ollamaResults.value = []
  try {
    const res = await apiClient.post(
      `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/mass-ollama`,
      { only_open: true },
    )
    ollamaResults.value = res.data.results || []
    emit('refresh')
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Fehler bei Ollama-Bewertung'
  } finally {
    busy.value = false
  }
}

const generatePrompts = async () => {
  busy.value = true
  error.value = ''
  prompts.value = []
  responses.value = {}
  try {
    const res = await apiClient.post(
      `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/mass-prompt`,
      { only_open: true },
    )
    prompts.value = res.data.prompts || []
    for (const p of prompts.value) {
      responses.value[p.risk_id] = ''
    }
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Fehler beim Generieren'
  } finally {
    busy.value = false
  }
}

const copyPrompt = async (prompt: string) => {
  try {
    await navigator.clipboard.writeText(prompt)
  } catch {
    // Fallback: Selection
  }
}

const applyResponses = async () => {
  busy.value = true
  error.value = ''
  applyResults.value = null
  const payload = {
    responses: Object.entries(responses.value)
      .filter(([_, v]) => (v || '').trim())
      .map(([risk_id, raw]) => ({ risk_id: Number(risk_id), raw })),
  }
  try {
    const res = await apiClient.post(
      `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/mass-apply`,
      payload,
    )
    applyResults.value = res.data
    emit('refresh')
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Fehler beim Übernehmen'
  } finally {
    busy.value = false
  }
}

const onCancel = () => emit('cancel')
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1100;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 800px;
  width: 95%;
  max-height: 90vh;
  display: flex; flex-direction: column;
}

.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h3 { margin: 0; color: var(--color-primary); }

.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }

.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }

.modal-footer {
  display: flex; justify-content: flex-end;
  padding: 12px 20px;
  border-top: 1px solid var(--color-border);
}

.hint { color: #888; font-size: 13px; margin-bottom: 16px; }

.mode-tabs {
  display: flex; gap: 2px;
  margin-bottom: 16px;
  border-bottom: 2px solid var(--color-border);
}

.mode-tab {
  background: none;
  border: none;
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  color: #666;
}

.mode-tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-content {
  display: flex; flex-direction: column;
  gap: 12px;
}

.info-banner {
  background: #e3f2fd;
  color: #0d47a1;
  padding: 10px 14px;
  border-radius: 4px;
  font-size: 13px;
  border: 1px solid #90caf9;
}

.step {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 12px 16px;
}

.step h4 { margin: 0 0 8px; font-size: 14px; }
.step p { color: #666; font-size: 13px; margin: 0 0 12px; }

.prompt-block {
  background: #f9f9f9;
  border-radius: 4px;
  padding: 8px;
  margin: 8px 0;
}

.prompt-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 6px;
}

.prompt-text {
  background: white;
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
}

.prompt-block textarea {
  width: 100%;
  margin-top: 8px;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
}

.results {
  margin-top: 16px;
}

.results table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.results th, .results td {
  padding: 5px 10px;
  text-align: left;
  border-bottom: 1px solid #f0f0f0;
}

.results tr.failed { background: #ffebee; }
.error-cell { color: #c62828; font-size: 11px; max-width: 200px; }

.apply-result {
  background: #e8f5e9;
  color: #2e7d32;
  padding: 8px;
  border-radius: 4px;
  margin-top: 8px;
  font-size: 13px;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  padding: 10px;
  border-radius: 4px;
  margin-top: 12px;
  border: 1px solid #ef5350;
}

.btn-primary, .btn-secondary, .btn-small {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-primary { background: var(--color-primary); color: white; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-small { padding: 4px 10px; font-size: 12px; background: white; border: 1px solid var(--color-border); }
</style>
