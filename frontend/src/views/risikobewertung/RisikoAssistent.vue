<template>
  <div v-if="open" class="modal-overlay" @click.self="close">
    <div class="modal-content modal-wide">
      <div class="modal-header">
        <h3>🤖 Risiken-Assistent</h3>
        <button class="btn-close" @click="close">✕</button>
      </div>

      <!-- Step-Indikator -->
      <div class="steps">
        <div v-for="(s, i) in steps" :key="i"
             :class="['step', { active: step === i, done: step > i }]">
          <span class="step-num">{{ i + 1 }}</span> {{ s }}
        </div>
      </div>

      <div class="modal-body">
        <!-- Schritt 1: Kontext -->
        <div v-if="step === 0">
          <p class="hint">Beschreibe System und Bereich, der untersucht werden soll.</p>
          <div class="form-row">
            <label>Anwendung / System *</label>
            <input v-model="form.anwendung" placeholder="z.B. Web-Shop, Mobile-App, IoT-Gateway" />
          </div>
          <div class="form-row">
            <label>Risikobereich</label>
            <input v-model="form.risikobereich" placeholder="z.B. Login + Checkout, Geräte-Onboarding, OTA-Updates" />
          </div>
        </div>

        <!-- Schritt 2: Schutzziele -->
        <div v-if="step === 1">
          <p class="hint">Welche Schutzziele sollen abgeprüft werden?</p>
          <div class="ziele-grid">
            <label v-for="z in schutzziele" :key="z.key"
                   :class="['ziel-card', { active: form.schutzziele.includes(z.key) }]"
                   :style="{ borderColor: z.farbe }">
              <input type="checkbox" :value="z.key"
                     :checked="form.schutzziele.includes(z.key)"
                     @change="toggleZiel(z.key, $event)" />
              <div class="ziel-key" :style="{ color: z.farbe }">{{ z.key }}</div>
              <div class="ziel-name">{{ z.de }}</div>
              <div class="ziel-en">{{ z.en }}</div>
            </label>
          </div>
        </div>

        <!-- Schritt 3: Beschreibung -->
        <div v-if="step === 2">
          <p class="hint">Detaillierte System-/Architektur-Beschreibung (Optional, verbessert die Vorschläge).</p>
          <div class="form-row">
            <label>Beschreibung</label>
            <textarea v-model="form.beschreibung" rows="10"
                      placeholder="Tech-Stack, Schnittstellen, Speicherorte, Drittparteien…"></textarea>
          </div>
          <div class="form-row">
            <label>Anzahl Risiken</label>
            <input type="number" v-model.number="form.n_risiken" min="3" max="30" />
          </div>
        </div>

        <!-- Schritt 4: Generierung (Prompt) -->
        <div v-if="step === 3">
          <p class="hint">
            Kopiere den Prompt unten in ChatGPT (oder ein anderes LLM) und füge die JSON-Antwort
            in das untere Feld ein.
          </p>
          <button class="btn-mini" @click="copyToClipboard(generatedPrompt)" :disabled="!generatedPrompt">
            📋 Prompt kopieren
          </button>
          <textarea readonly :value="generatedPrompt" rows="12" class="prompt-textarea"></textarea>

          <hr style="margin: 12px 0;" />
          <label>ChatGPT-Antwort (JSON-Array)</label>
          <textarea v-model="rawResponse" rows="8" class="prompt-textarea"
                    placeholder='[{"risk_name":"...","beschreibung":"..."}]'></textarea>
          <span v-if="parseMsg" class="hint" :class="{ err: parseErr }">{{ parseMsg }}</span>
        </div>

        <!-- Schritt 5: Vorschau -->
        <div v-if="step === 4">
          <p class="hint">{{ discoveredRisks.length }} Vorschläge — wähle aus, was übernommen werden soll:</p>
          <div class="risk-list">
            <label v-for="(r, i) in discoveredRisks" :key="i" class="risk-item">
              <input type="checkbox" v-model="selected[i]" />
              <div class="risk-content">
                <strong>{{ r.risk_name }}</strong>
                <p>{{ r.beschreibung }}</p>
              </div>
            </label>
          </div>
          <div class="select-actions">
            <button class="btn-mini" @click="selectAll(true)">Alle</button>
            <button class="btn-mini" @click="selectAll(false)">Keine</button>
            <span class="muted">{{ selectedCount }} von {{ discoveredRisks.length }} ausgewählt</span>
          </div>
          <span v-if="applyMsg" class="hint" :class="{ err: applyErr, ok: !applyErr }">{{ applyMsg }}</span>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn-secondary" @click="close">Abbrechen</button>
        <button v-if="step > 0" class="btn-secondary" @click="step--">← Zurück</button>
        <button v-if="step < 3" class="btn-primary" @click="next" :disabled="!canNext">
          Weiter →
        </button>
        <button v-if="step === 3" class="btn-primary" @click="onParseResponse"
                :disabled="!rawResponse || busy">
          {{ busy ? 'Verarbeite…' : 'Vorschläge anzeigen →' }}
        </button>
        <button v-if="step === 4" class="btn-primary" @click="onApply"
                :disabled="selectedCount === 0 || busy">
          {{ busy ? 'Importiere…' : `✓ ${selectedCount} Risiken übernehmen` }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import apiClient from '../../api/client'

const props = defineProps<{ open: boolean; projektName: string | null }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'applied', count: number): void }>()

const close = () => emit('close')

const steps = ['Kontext', 'Schutzziele', 'Beschreibung', 'Generierung', 'Vorschau']
const step = ref(0)

const form = reactive({
  anwendung: '',
  risikobereich: '',
  schutzziele: [] as string[],
  beschreibung: '',
  n_risiken: 10,
})

const schutzziele = ref<any[]>([])
const generatedPrompt = ref('')
const rawResponse = ref('')
const parseMsg = ref('')
const parseErr = ref(false)
const discoveredRisks = ref<{ risk_name: string; beschreibung: string }[]>([])
const selected = ref<boolean[]>([])
const applyMsg = ref('')
const applyErr = ref(false)
const busy = ref(false)

const canNext = computed(() => {
  if (step.value === 0) return !!form.anwendung
  if (step.value === 1) return form.schutzziele.length > 0
  return true
})

const selectedCount = computed(() => selected.value.filter(Boolean).length)

const reset = () => {
  step.value = 0
  form.anwendung = ''
  form.risikobereich = ''
  form.schutzziele = []
  form.beschreibung = ''
  form.n_risiken = 10
  generatedPrompt.value = ''
  rawResponse.value = ''
  parseMsg.value = ''
  discoveredRisks.value = []
  selected.value = []
  applyMsg.value = ''
}

watch(() => props.open, async (o) => {
  if (o) {
    reset()
    if (schutzziele.value.length === 0) {
      try {
        const res = await apiClient.get('/risikobewertung/assistent/schutzziele')
        schutzziele.value = res.data
      } catch { schutzziele.value = [] }
    }
  }
})

const toggleZiel = (key: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  if (checked && !form.schutzziele.includes(key)) form.schutzziele.push(key)
  else if (!checked) form.schutzziele = form.schutzziele.filter(k => k !== key)
}

const copyToClipboard = async (text: string) => {
  try { await navigator.clipboard.writeText(text); parseMsg.value = '✓ In Zwischenablage kopiert.'; parseErr.value = false; setTimeout(() => parseMsg.value = '', 2000) }
  catch { parseMsg.value = 'Konnte nicht kopieren — manuell markieren.'; parseErr.value = true }
}

const next = async () => {
  // Wechsel zu Schritt 4: Prompt erzeugen
  if (step.value === 2) {
    if (!props.projektName) return
    busy.value = true
    try {
      const res = await apiClient.post(
        `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/discovery-prompt`,
        {
          anwendung: form.anwendung,
          risikobereich: form.risikobereich,
          schutzziele: form.schutzziele,
          beschreibung: form.beschreibung,
          n_risiken: form.n_risiken,
        },
      )
      generatedPrompt.value = res.data.prompt
      step.value++
    } catch (e: any) {
      parseErr.value = true
      parseMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
    } finally {
      busy.value = false
    }
    return
  }
  step.value++
}

const onParseResponse = async () => {
  if (!props.projektName || !rawResponse.value) return
  busy.value = true
  parseMsg.value = ''
  try {
    const res = await apiClient.post(
      `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/discovery-import`,
      { raw: rawResponse.value },
    )
    discoveredRisks.value = res.data.risks || []
    selected.value = discoveredRisks.value.map(() => true)
    step.value = 4
  } catch (e: any) {
    parseErr.value = true
    parseMsg.value = e?.response?.data?.error || e.message
  } finally {
    busy.value = false
  }
}

const selectAll = (val: boolean) => {
  selected.value = discoveredRisks.value.map(() => val)
}

const onApply = async () => {
  if (!props.projektName) return
  const picked = discoveredRisks.value.filter((_, i) => selected.value[i])
  if (picked.length === 0) return
  busy.value = true
  applyMsg.value = ''
  try {
    const res = await apiClient.post(
      `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/discovery-apply`,
      { risks: picked },
    )
    applyErr.value = false
    applyMsg.value = `✓ ${res.data.imported} Risiken angelegt.`
    emit('applied', res.data.imported)
    setTimeout(close, 1200)
  } catch (e: any) {
    applyErr.value = true
    applyMsg.value = e?.response?.data?.error || e.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: var(--color-surface); border-radius: 8px; max-width: 1000px; width: 90%; max-height: 92vh; display: flex; flex-direction: column; }
.modal-header { background: var(--color-primary); color: #fff; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }
.modal-header h3 { margin: 0; font-size: 16px; }
.btn-close { background: none; border: none; color: #fff; font-size: 22px; cursor: pointer; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer { padding: 12px 20px; border-top: 1px solid var(--color-border); display: flex; gap: 8px; justify-content: flex-end; }

.steps { display: flex; gap: 4px; padding: 12px 20px; background: var(--color-background); border-bottom: 1px solid var(--color-border); }
.step { display: flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 4px; font-size: 12px; color: var(--color-text-secondary); }
.step.active { background: var(--color-primary); color: #fff; }
.step.done { color: var(--color-success); }
.step-num { display: inline-block; width: 22px; height: 22px; line-height: 22px; text-align: center; border-radius: 50%; background: rgba(0,0,0,0.1); font-weight: 600; }
.step.active .step-num { background: rgba(255,255,255,0.2); }

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: var(--color-surface); color: var(--color-text-primary);
}

.ziele-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.ziel-card {
  border: 2px solid; border-radius: 8px; padding: 14px;
  background: var(--color-surface); cursor: pointer; opacity: 0.55;
  transition: all 150ms;
}
.ziel-card.active { opacity: 1; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.ziel-card input { display: none; }
.ziel-key { font-size: 28px; font-weight: 700; line-height: 1; }
.ziel-name { font-size: 14px; font-weight: 600; margin-top: 4px; }
.ziel-en { font-size: 11px; color: var(--color-text-secondary); }

.prompt-textarea {
  width: 100%; font-family: monospace; font-size: 12px; padding: 10px;
  border: 1px solid var(--color-border); border-radius: 4px;
  background: var(--color-background); color: var(--color-text-primary); margin-top: 6px;
}

.btn-mini {
  background: var(--color-background); border: 1px solid var(--color-border);
  padding: 4px 10px; border-radius: 3px; cursor: pointer; font-size: 11px;
  margin-right: 4px;
}

.risk-list { display: flex; flex-direction: column; gap: 6px; }
.risk-item {
  display: flex; gap: 10px; padding: 10px 12px;
  background: var(--color-background); border-radius: 4px;
  border-left: 3px solid var(--color-primary); cursor: pointer;
}
.risk-item input { margin-top: 4px; }
.risk-content { flex: 1; }
.risk-content strong { display: block; font-size: 14px; }
.risk-content p { margin: 4px 0 0; color: var(--color-text-secondary); font-size: 13px; }
.select-actions { display: flex; align-items: center; gap: 8px; padding-top: 8px; border-top: 1px solid var(--color-border); margin-top: 12px; }
.muted { color: var(--color-text-secondary); font-size: 12px; }

.hint { font-size: 12px; color: var(--color-text-secondary); }
.hint.err { color: var(--color-error); }
.hint.ok { color: var(--color-success); }

.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: var(--color-background); color: var(--color-primary); border: 1px solid var(--color-border); padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-secondary:hover { background: var(--color-border); }
</style>
