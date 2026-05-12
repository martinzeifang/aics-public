<template>
  <div class="modal-overlay" @click.self="onCancel">
    <div class="modal-content">
      <h3>🌐 Aus Website-Impressum anlegen</h3>
      <p class="hint">
        Wir crawlen die Website (max. {{ form.max_pages }} Seiten) und versuchen, das Impressum
        zu finden. Erkannte Daten können dann direkt ins Formular übernommen werden.
      </p>

      <div class="form-row">
        <label>Website-URL *</label>
        <input v-model="form.url" placeholder="https://example.com" :disabled="loading" />
      </div>

      <div class="form-row">
        <label>Maximale Seiten zu crawlen</label>
        <input v-model.number="form.max_pages" type="number" min="1" max="50" :disabled="loading" />
      </div>

      <div v-if="loading" class="info">⏳ Analyse läuft… Dies kann eine Weile dauern.</div>
      <div v-if="error" class="alert alert-error">{{ error }}</div>

      <div v-if="result" class="impressum-preview">
        <h4>Erkannte Daten</h4>
        <table>
          <tbody>
            <tr v-if="result.unternehmen">
              <th>Unternehmen</th><td>{{ result.unternehmen }}</td>
            </tr>
            <tr v-if="result.rechtsform">
              <th>Rechtsform</th><td>{{ result.rechtsform }}</td>
            </tr>
            <tr v-if="result.strasse || result.plz || result.ort">
              <th>Adresse</th>
              <td>{{ [result.strasse, [result.plz, result.ort].filter(Boolean).join(' ')].filter(Boolean).join(', ') }}</td>
            </tr>
            <tr v-if="result.vertreter?.length">
              <th>Vertreter</th><td>{{ result.vertreter.join(', ') }}</td>
            </tr>
            <tr v-if="result.email">
              <th>E-Mail</th><td>{{ result.email }}</td>
            </tr>
            <tr v-if="result.telefon">
              <th>Telefon</th><td>{{ result.telefon }}</td>
            </tr>
            <tr v-if="result.ust_id">
              <th>USt-ID</th><td>{{ result.ust_id }}</td>
            </tr>
            <tr v-if="result.hrb">
              <th>HRB</th><td>{{ result.hrb }}</td>
            </tr>
            <tr>
              <th>Seiten gecrawlt</th><td>{{ result.pages_crawled }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="modal-actions">
        <button class="btn-secondary" @click="onCancel" :disabled="loading">Schließen</button>
        <button v-if="!result" class="btn-primary" @click="onAnalyze" :disabled="loading">
          {{ loading ? 'Lädt…' : 'Analyse starten' }}
        </button>
        <template v-else>
          <button class="btn-secondary" @click="result = null; error = ''">Erneut versuchen</button>
          <button class="btn-primary" @click="onApply">Formular befüllen</button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useKundenStore } from '../../../stores/kunden'

const emit = defineEmits<{
  apply: [data: any]
  cancel: []
}>()

const kunden = useKundenStore()

const form = ref({ url: '', max_pages: 5 })
const loading = ref(false)
const error = ref('')
const result = ref<any | null>(null)

const onAnalyze = async () => {
  if (!form.value.url?.trim()) {
    error.value = 'URL ist Pflicht.'
    return
  }
  if (!/^https?:\/\//.test(form.value.url)) {
    error.value = 'URL muss mit http:// oder https:// beginnen.'
    return
  }
  loading.value = true
  error.value = ''
  result.value = null
  const data = await kunden.parseImpressum(form.value.url, form.value.max_pages)
  loading.value = false
  if (data) {
    result.value = data
  } else {
    error.value = kunden.error || 'Keine Impressum-Daten gefunden.'
  }
}

const onApply = () => {
  emit('apply', result.value)
}

const onCancel = () => emit('cancel')
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.modal-content {
  background: white;
  border-radius: 8px;
  padding: 24px;
  max-width: 600px;
  width: 90%;
  max-height: 85vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin: 0 0 12px;
  color: var(--color-primary);
}

.hint {
  margin: 0 0 16px;
  color: #888;
  font-size: 13px;
  line-height: 1.4;
}

.form-row {
  margin-bottom: 14px;
}

.form-row label {
  display: block;
  margin-bottom: 4px;
  font-weight: 600;
  font-size: 13px;
}

.form-row input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
}

.form-row input:disabled {
  background: #f5f5f5;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 12px 0;
  font-size: 13px;
}

.info {
  background: #fff8e1;
  color: #e65100;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 12px 0;
  font-size: 13px;
}

.impressum-preview {
  background: #f9f9f9;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 12px 16px;
  margin: 16px 0;
}

.impressum-preview h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--color-primary);
}

.impressum-preview table {
  width: 100%;
  font-size: 13px;
}

.impressum-preview th {
  text-align: left;
  font-weight: 600;
  padding: 4px 8px 4px 0;
  white-space: nowrap;
  vertical-align: top;
  color: #555;
  width: 130px;
}

.impressum-preview td {
  padding: 4px 0;
  word-break: break-word;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.btn-primary,
.btn-secondary {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.6;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}
</style>
