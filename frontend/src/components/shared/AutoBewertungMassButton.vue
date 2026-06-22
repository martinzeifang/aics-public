<template>
  <span class="auto-mass">
    <button
      class="btn-small auto-mass-btn"
      :disabled="busy"
      :title="'Alle offenen Anforderungen (Score 0) automatisch per LLM bewerten'"
      @click="onRun"
    >
      {{ busy ? '⏳ Bewerte…' : '🤖 Alle offenen automatisch bewerten' }}
    </button>
    <span v-if="result" class="auto-mass-result" :class="{ err: result.hasError }">{{ result.text }}</span>

    <!-- #1380: Bestätigung der Datenübermittlung vor der Massen-KI-Bewertung -->
    <Teleport to="body">
      <div v-if="confirmOpen" class="modal-overlay nested" @mousedown.self="confirmOpen = false">
        <div class="modal-content prompt-modal">
          <div class="modal-header">
            <h3>🤖 Automatische KI-Massen-Bewertung</h3>
            <button class="btn-close" @click="confirmOpen = false">✕</button>
          </div>
          <div class="modal-body">
            <DataPreviewWarning
              :fields="previewFields"
              :provider="aiProvider"
              @confirm="doRun"
            />
            <OutputDestinationHint
              destination="Die KI bewertet alle offenen Anforderungen direkt; Score, Kommentar und Maßnahme werden übernommen."
              impact="Überschreibt die bisherigen (leeren) Bewertungen der offenen Anforderungen."
            />
          </div>
        </div>
      </div>
    </Teleport>
  </span>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import apiClient from '../../api/client'
import DataPreviewWarning from './DataPreviewWarning.vue'
import OutputDestinationHint from './OutputDestinationHint.vue'

const props = defineProps<{
  /** API-Base, z.B. /nis2 | /aiact | /dsgvo */
  apiBase: string
  /** Projekt-Name */
  projektName: string
}>()

const emit = defineEmits<{
  /** Nach Abschluss — Parent lädt Anforderungen/Bewertungen neu */
  done: []
  error: [message: string]
}>()

const busy = ref(false)
const result = ref<{ text: string; hasError: boolean } | null>(null)
const confirmOpen = ref(false)
// #867/#877: aktiver Provider für die Egress-Transparenz
const aiProvider = ref<'on_prem' | 'cloud'>('on_prem')

const previewFields = computed(() => [
  { label: 'Projekt', value: props.projektName },
  { label: 'Umfang', value: 'Alle offenen Anforderungen (Score 0)' },
])

onMounted(async () => {
  try {
    const res = await apiClient.get('/ai/provider-status')
    aiProvider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Default on_prem */ }
})

// Klick öffnet zuerst die Datenübermittlungs-Bestätigung (#1380).
const onRun = () => {
  if (!props.projektName || busy.value) return
  result.value = null
  confirmOpen.value = true
}

const doRun = async () => {
  confirmOpen.value = false
  if (!props.projektName || busy.value) return
  busy.value = true
  result.value = null
  try {
    const res = await apiClient.post(
      `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/anforderungen/auto-bewertung-mass`,
    )
    const d = res.data || {}
    const fehler = Array.isArray(d.fehler) ? d.fehler : []
    result.value = {
      text: `${d.bewertet ?? 0}/${d.gesamt ?? 0} bewertet${fehler.length ? `, ${fehler.length} Fehler` : ''}`,
      hasError: fehler.length > 0,
    }
    emit('done')
  } catch (e: any) {
    const msg = e?.response?.data?.error || 'Automatische Massen-Bewertung fehlgeschlagen'
    result.value = { text: msg, hasError: true }
    emit('error', msg)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.auto-mass { display: inline-flex; align-items: center; gap: 8px; }
.auto-mass-btn {
  background: white;
  border: 1px solid #b3d4f5;
  color: #1565c0;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.auto-mass-btn:hover:not(:disabled) { background: #1565c0; color: white; }
.auto-mass-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.auto-mass-result { font-size: 12px; color: #2e7d32; }
.auto-mass-result.err { color: #c62828; }

/* Modal (gespiegelt von den geteilten Modal-Styles) */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1100; padding: 1rem;
}
.modal-content {
  background: #fff; border-radius: 10px; width: min(640px, 100%);
  max-height: 90vh; overflow-y: auto; box-shadow: 0 10px 40px rgba(0,0,0,0.25);
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.9rem 1.2rem; border-bottom: 1px solid #e0e0e0;
}
.modal-header h3 { margin: 0; font-size: 1.05rem; color: #1565c0; }
.btn-close { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: #757575; }
.modal-body { padding: 1rem 1.2rem 1.2rem; display: flex; flex-direction: column; gap: 0.8rem; }
</style>
