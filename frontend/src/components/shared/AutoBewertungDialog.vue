<template>
  <!-- #1573: EIN Dialog für die automatische KI-Bewertung eines Objekts in ALLEN Modulen
       (Anforderung, OWASP-Kontrolle, OWASP-LLM, Risiko, WiBA-Prüffrage):
       1. Datenübermittlung bestätigen → 2. Live-Stream → 3. einheitliches Ergebnis. -->
  <Teleport to="body">
    <div class="modal-overlay" @mousedown.self="onClose">
      <div class="modal-content abd">
        <div class="modal-header">
          <h3>🤖 Automatische KI-Bewertung<span v-if="title"> — {{ title }}</span></h3>
          <button class="btn-close" @click="onClose">✕</button>
        </div>
        <div class="modal-body">
          <template v-if="step === 'confirm'">
            <!-- #1834: Der Hinweis gehört VOR die Bestätigung — er ist Teil
                 dessen, was übermittelt wird, und muss vorher feststehen. -->
            <PromptZusatzFeld v-model="zusatz" :modul="hinweisModul"
                              :projekt="hinweisProjekt" bereich="bewertung"
                              beispiel="z. B. Fertigungsbetrieb, IT ausgelagert — bitte die Auslagerung berücksichtigen." />
            <DataPreviewWarning :fields="previewFields" :sensitive="sensitive" :provider="provider"
                                @confirm="step = 'run'" />
            <OutputDestinationHint :destination="destination" :impact="impact" />
          </template>
          <!-- #1836/E2: Die Daten-Vorschau oben IST die Zustimmung. Sie wird
               jetzt mitgesendet (`confirmed`), damit der serverseitige
               Riegel greift und ein Revisionseintrag entsteht — vorher
               war sie eine Anzeige ohne Wirkung (#1840). Kein zweites
               Tor: für denselben Vorgang eines zu viel. -->
          <KiStreamView v-else :url="streamUrl" :body="sendBody" :pipeline="true"
                        :confirm-egress="true" :egress-vorbestaetigt="true"
                        :egress-context="title" :egress-modul="egressModul"
                        @done="onDone" @error="(m: string) => { errorMsg = m }">
            <template #result="{ payload }">
              <AutoBewertungErgebnis :payload="payload" :wert-label="wertLabel" />
            </template>
          </KiStreamView>
        </div>
        <div class="modal-footer">
          <button v-if="step === 'confirm'" class="btn-secondary" @click="onClose">Abbrechen</button>
          <button v-else-if="!result && !errorMsg" class="btn-secondary" @click="onClose">⏹ Abbrechen</button>
          <button v-else class="btn-primary" @click="onClose">{{ result ? '✓ Fertig' : 'Schließen' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '../../api/client'
import PromptZusatzFeld from './PromptZusatzFeld.vue'
import DataPreviewWarning from './DataPreviewWarning.vue'
import OutputDestinationHint from './OutputDestinationHint.vue'
import KiStreamView from './KiStreamView.vue'
import AutoBewertungErgebnis from './AutoBewertungErgebnis.vue'

const props = withDefaults(defineProps<{
  /** z. B. „CRA-IMPL-01: Sichere Standardkonfiguration" */
  title?: string
  /** absoluter SSE-Pfad inkl. /api */
  streamUrl: string
  body?: any
  previewFields: { label: string; value: any }[]
  sensitive?: string[]
  /** Beschriftung des Hauptwerts (Bewertung | Risiko | Antwort) */
  wertLabel?: string
  destination?: string
  impact?: string
  /** Modul für den Revisionseintrag der Übermittlung (#1836/E2). */
  egressModul?: string
  /** #1835: Modul und Projekt für die gespeicherten Hinweise. */
  hinweisModul?: string
  hinweisProjekt?: string
}>(), {
  egressModul: 'ai',
  hinweisModul: '', hinweisProjekt: '',
  title: '', body: () => ({}), sensitive: () => [], wertLabel: 'Bewertung',
  destination: 'Die KI bewertet direkt; das Ergebnis wird gespeichert.',
  impact: 'Überschreibt die aktuelle Bewertung.',
})
const emit = defineEmits<{ close: []; done: [payload: any] }>()

const step = ref<'confirm' | 'run'>('confirm')
const provider = ref<'on_prem' | 'cloud'>('on_prem')
// #1834: eigene Hinweise reisen im Body des Streams; der Server setzt sie ein
// (shared/sse.stream_ai_sse) und vermerkt sie im Revisionspfad.
const zusatz = ref('')
const sendBody = computed(() => ({ ...(props.body || {}), prompt_zusatz: zusatz.value }))
const result = ref<any>(null)
const errorMsg = ref('')

onMounted(async () => {
  try {
    const res = await apiClient.get('/ai/provider-status')
    provider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Default on_prem */ }
})

function onDone(payload: any) { result.value = payload }

// Schließen: laufender Stream wird durch das Unmount der KiStreamView abgebrochen;
// bei Erfolg lädt der Aufrufer über `done` neu.
function onClose() {
  if (result.value) emit('done', result.value)
  emit('close')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1200; padding: 1rem;
}
.modal-content { background: #fff; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.25); }
.abd { width: min(760px, 96vw); max-height: 90vh; display: flex; flex-direction: column; }
.modal-header {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 0.9rem 1.2rem; border-bottom: 1px solid #e0e0e0;
}
.modal-header h3 { margin: 0; font-size: 1.05rem; color: #1565c0; }
.btn-close { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: #757575; }
.modal-body { padding: 1rem 1.2rem; overflow-y: auto; display: flex; flex-direction: column; gap: 0.8rem; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 0.8rem 1.2rem; border-top: 1px solid #e0e0e0; }
</style>
