<template>
  <div class="bericht-panel">
    <div class="action-card">
      <h3>{{ $t('wiba.berichtPanel.wiBANachweisExportieren') }}</h3>
      <p>
        {{ $t('wiba.berichtPanel.erzeugtEinenVollstandigenWiBANachwei') }}
      </p>
      <div class="action-buttons">
        <DownloadButton
          :endpoint="reportEndpoint('docx')"
          :filename="`WiBA_${projektName || 'Bericht'}.docx`"
          variant="primary"
          :disabled="!projektName"
          :title="$t('wiba.berichtPanel.nachweisAlsWordDokumentHerunterladen')"
          @error="onError"
        >
          {{ $t('wiba.berichtPanel.nachweisAlsDOCX') }}
        </DownloadButton>
        <DownloadButton
          :endpoint="reportEndpoint('pdf')"
          :filename="`WiBA_${projektName || 'Bericht'}.pdf`"
          :disabled="!projektName"
          :title="$t('wiba.berichtPanel.nachweisAlsPDFHerunterladen')"
          @error="onError"
        >
          {{ $t('wiba.berichtPanel.nachweisAlsPDF') }}
        </DownloadButton>
        <span class="hint">{{ $t('wiba.berichtPanel.formatDOCXBearbeitbarOderPDFVersandA') }}</span>
      </div>
      <FehlerHinweis :text="errorMsg" @close="errorMsg = ''" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import DownloadButton from '../../components/shared/DownloadButton.vue'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'

const props = defineProps<{
  projektName: string
}>()

const errorMsg = ref('')

// DownloadButton ruft über apiClient (baseURL '/api'), daher OHNE /api-Präfix.
const reportEndpoint = (format: 'docx' | 'pdf'): string => {
  if (!props.projektName) return '#'
  return `/wiba/projekte/${encodeURIComponent(props.projektName)}/report?format=${format}`
}

const onError = (msg: string) => {
  errorMsg.value = msg
}
</script>

<style scoped>
.bericht-panel { padding: 8px 0; }
.action-card {
  background: white; padding: 24px; border-radius: 8px;
  border: 1px solid var(--color-border); max-width: 720px;
}
.action-card h3 { margin: 0 0 8px; }
.action-card p { color: #666; margin-bottom: 16px; line-height: 1.5; }
.action-buttons { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.action-buttons .hint { font-size: 12px; color: #888; }
.alert-error {
  margin-top: 12px; background: #ffebee; color: #c62828;
  padding: 10px; border-radius: 4px; border: 1px solid #ef5350;
}
</style>
