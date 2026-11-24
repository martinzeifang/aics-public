<template>
  <div class="modal-overlay" @mousedown.self="onCancel">
    <div class="modal-content">
      <h3>{{ $t('firmen.evidenceURLDialog.evidenceVonURLHinzufugen') }}</h3>

      <div class="form-row">
        <label>{{ $t('firmen.evidenceURLDialog.websiteURL') }}</label>
        <input v-model="form.url" placeholder="https://example.com" />
      </div>

      <div class="form-row">
        <label>{{ $t('firmen.evidenceURLDialog.maximaleSeitenZuCrawlen') }}</label>
        <input v-model.number="form.max_pages" type="number" min="1" max="50" />
      </div>

      <div class="form-row">
        <label>{{ $t('firmen.evidenceURLDialog.dokumenttyp') }}</label>
        <input v-model="form.doc_type" placeholder="z.B. richtlinie, datenschutz" />
      </div>

      <div class="form-row">
        <label>{{ $t('firmen.evidenceURLDialog.schlagworterKommasepariert') }}</label>
        <input v-model="form.tagsRaw" placeholder="z.B. impressum, kontakt" />
      </div>

      <FehlerHinweis :text="error" @close="error = ''" />
      <div v-if="loading" class="info">{{ $t('firmen.evidenceURLDialog.crawlLauftDiesKannEineWeileDauern') }}</div>

      <div class="modal-actions">
        <button class="btn-secondary" @click="onCancel" :disabled="loading">{{ $t('common.cancel') }}</button>
        <button class="btn-primary" @click="onSubmit" :disabled="loading">
          {{ loading ? $t('firmen.evidenceURLDialog.importiert') : $t('firmen.evidenceURLDialog.importieren') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import FehlerHinweis from '../../../components/shared/FehlerHinweis.vue'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../../i18n'

const emit = defineEmits<{
  submit: [data: { url: string; max_pages: number; doc_type: string; tags: string[] }]
  cancel: []
}>()

const form = ref({
  url: '',
  max_pages: 5,
  doc_type: 'web',
  tagsRaw: '',
})
const error = ref('')
const loading = ref(false)

const onSubmit = async () => {
  error.value = ''
  if (!form.value.url?.trim()) {
    error.value = uebersetze('firmen.evidenceURLDialog.uRLIstPflicht')
    return
  }
  loading.value = true
  const tags = form.value.tagsRaw.split(',').map(t => t.trim()).filter(Boolean)
  emit('submit', {
    url: form.value.url.trim(),
    max_pages: form.value.max_pages,
    doc_type: form.value.doc_type,
    tags,
  })
  loading.value = false
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
  max-width: 500px;
  width: 90%;
}

.modal-content h3 {
  margin: 0 0 20px;
  color: var(--color-primary);
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
