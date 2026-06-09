<template>
  <div class="assistenten-panel">
    <div class="info-banner">
      <h3>🤖 WiBA-Assistenten</h3>
      <p>
        KI-gestützte Helfer je Thema: Lassen Sie sich für ein Thema einen
        <strong>Sammel-Prompt</strong> erzeugen, übergeben ihn an ChatGPT und
        fügen die JSON-Antwort hier ein — der Status der Prüffragen wird dann
        übernommen. Vorhandene <strong>Firmen-Nachweise</strong> fließen
        automatisch in den Prompt ein.
      </p>
      <p class="hint">
        1. Kachel wählen → 2. Prompt kopieren → 3. ChatGPT-Antwort (JSON)
        einfügen → 4. „Parsen + Anwenden".
      </p>
    </div>

    <AssistentenKachelGrid :wizards="wizards" @open="openWizard" />

    <!-- Prompt-Wizard-Dialog -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @mousedown.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <p class="hint">
          Kopiere den Prompt nach ChatGPT, füge die JSON-Antwort ein und wähle
          „Parsen + Anwenden". Die Prüffrage(n) dieses Themas werden aktualisiert.
        </p>

        <label>Optionen</label>
        <label class="check-row">
          <input type="checkbox" v-model="includeEvidence" />
          Firmen-Nachweise in den Prompt einbeziehen
        </label>

        <label>Prompt (zum Kopieren)</label>
        <textarea readonly :value="wizardModal.prompt" rows="8" class="mono"></textarea>
        <div class="prompt-actions">
          <button class="btn-link" @click="copyPrompt">📋 Kopieren</button>
          <span v-if="wizardModal.evidenceUsed?.length" class="evidence-note">
            📎 {{ wizardModal.evidenceUsed.length }} Nachweis(e) berücksichtigt
          </span>
        </div>

        <label>ChatGPT-Antwort (JSON)</label>
        <textarea v-model="wizardModal.response" rows="6" class="mono"
                  placeholder="Hier die ChatGPT-Antwort einfügen..."></textarea>

        <div v-if="wizardModal.parsed" class="parsed-result">
          <strong v-if="wizardModal.parsed.ok" style="color: #2e7d32;">✓ Verarbeitet</strong>
          <strong v-else style="color: #e65100;">Vorschau (nicht gespeichert)</strong>
          <pre>{{ JSON.stringify(wizardModal.parsed.parsed ?? wizardModal.parsed, null, 2) }}</pre>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeWizard">Schließen</button>
          <button class="btn-secondary" :disabled="!wizardModal.response" @click="parseOnly">Nur parsen</button>
          <button class="btn-primary" :disabled="!wizardModal.response" @click="parseAndApply">Parsen + Anwenden</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useWibaStore } from '../../stores/wiba'
import AssistentenKachelGrid from '../../components/assistenten/AssistentenKachelGrid.vue'
import { buildWizardList, type WizardDescriptor } from '../../components/assistenten/registry'

const store = useWibaStore()

const emit = defineEmits<{
  /** Signals the host that control data changed and should reload. */
  (e: 'applied'): void
}>()

// Eine Kachel je Thema — der „open"-Wert ist der erste control_id des Themas,
// über den wir den Sammel-Prompt erzeugen.
const wizards = computed<WizardDescriptor[]>(() => {
  const list: WizardDescriptor[] = store.themen.map((t) => {
    const firstControl = t.prueffragen[0]?.control_id || t.theme_key
    return {
      id: `thema:${firstControl}`,
      title: t.titel,
      description: `${t.prueffragen.length} Prüffragen · KI-Sammelauswertung mit Firmen-Nachweisen.`,
      kategorie: 'compliance',
      icon: '🛡️',
    }
  })
  return list.length ? buildWizardList(list) : []
})

const includeEvidence = ref(true)

const wizardModal = ref<any>({
  open: false,
  controlId: '',
  title: '',
  prompt: '',
  response: '',
  parsed: null,
  evidenceUsed: [],
})

const openWizard = async (id: string) => {
  const controlId = id.startsWith('thema:') ? id.slice('thema:'.length) : id
  const thema = store.themen.find((t) => t.prueffragen.some((q) => q.control_id === controlId))
  const res = await store.buildPrompt(controlId, includeEvidence.value)
  wizardModal.value = {
    open: true,
    controlId,
    title: thema?.titel || controlId,
    prompt: res?.prompt || '',
    response: '',
    parsed: null,
    evidenceUsed: res?.evidence_used || [],
  }
}

const closeWizard = () => {
  wizardModal.value = { open: false, controlId: '', title: '', prompt: '', response: '', parsed: null, evidenceUsed: [] }
}

const copyPrompt = () => navigator.clipboard?.writeText(wizardModal.value.prompt)

const parseOnly = async () => {
  wizardModal.value.parsed = await store.parseResponse(wizardModal.value.controlId, wizardModal.value.response, false)
}

const parseAndApply = async () => {
  const res = await store.parseResponse(wizardModal.value.controlId, wizardModal.value.response, true)
  wizardModal.value.parsed = res
  if (res?.ok) {
    emit('applied')
    setTimeout(() => closeWizard(), 1200)
  }
}
</script>

<style scoped>
.assistenten-panel { display: flex; flex-direction: column; gap: 16px; }

.info-banner { background: #f3e5f5; padding: 16px 20px; border-radius: 8px; border-left: 4px solid #7b1fa2; }
.info-banner h3 { margin: 0 0 8px; color: #4a148c; }
.info-banner p { margin: 0 0 6px; color: #444; line-height: 1.5; }
.info-banner .hint { color: #6a1b9a; font-size: 13px; margin-bottom: 0; }

.wizard-modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.wizard-modal {
  background: white; padding: 24px; border-radius: 10px;
  max-width: 800px; width: 90%; max-height: 90vh; overflow-y: auto;
}
.wizard-modal h3 { margin: 0 0 8px; color: #4a148c; }
.wizard-modal label { display: block; margin-top: 12px; font-weight: 600; font-size: 13px; }
.wizard-modal textarea {
  width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; resize: vertical;
}
.wizard-modal .mono { font-family: monospace; font-size: 12px; }
.check-row { display: flex; align-items: center; gap: 8px; font-weight: 400; cursor: pointer; }
.hint { color: #666; font-size: 13px; }

.prompt-actions { display: flex; align-items: center; gap: 16px; }
.evidence-note { font-size: 12px; color: #2e7d32; }

.parsed-result { background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 12px; }
.parsed-result pre { margin: 6px 0 0; white-space: pre-wrap; font-size: 12px; max-height: 240px; overflow-y: auto; }

.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover:not(:disabled) { background: #0d47a1; }
.btn-secondary { background: #eee; color: #333; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary:hover:not(:disabled) { background: #ddd; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 14px; color: #1565c0; padding: 4px 0; }
</style>
