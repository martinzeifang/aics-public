<template>
  <div class="modal-overlay" @mousedown.self="onCancel">
    <div class="modal-content">
      <h3>{{ produkt?.id ? $t('firmen.produktDialog.produktBearbeiten') : $t('firmen.produktDialog.neuesProdukt') }}</h3>

      <div class="form-row">
        <label>{{ $t('firmen.produktDialog.produktname') }}</label>
        <input v-model="form.name" :placeholder="$t('firmen.produktDialog.zBMeinProdukt')" />
      </div>

      <div class="form-row">
        <label>{{ $t('common.description') }}</label>
        <textarea v-model="form.beschreibung" rows="3" :placeholder="$t('firmen.produktDialog.optionalerBeschreibungstext')"></textarea>
      </div>

      <div class="form-row">
        <label>{{ $t('firmen.produktDialog.produktklasseCRA') }}</label>
        <select v-model="form.produktklasse">
          <option v-for="pk in produktklassen" :key="pk.key" :value="pk.key">
            {{ pk.label }}
          </option>
        </select>
      </div>

      <div class="form-row">
        <label class="checkbox-label">
          <input type="checkbox" v-model="form.is_default" />
          {{ $t('firmen.produktDialog.alsStandardProduktFurDieseFirmaSetze') }}
        </label>
      </div>

      <FehlerHinweis :text="error" @close="error = ''" />

      <div class="modal-actions">
        <button class="btn-secondary" @click="onCancel">{{ $t('common.cancel') }}</button>
        <button class="btn-primary" @click="onSave" :disabled="saving">
          {{ saving ? $t('firmen.produktDialog.speichert') : $t('firmen.produktDialog.speichern') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Produkt } from '../../../stores/firmen'
import FehlerHinweis from '../../../components/shared/FehlerHinweis.vue'
import { t } from '../../../i18n'

const props = defineProps<{
  produkt: Produkt | null
  produktklassen: { key: string; label: string }[]
}>()

const emit = defineEmits<{
  save: [data: Partial<Produkt>]
  cancel: []
}>()

const form = ref<Partial<Produkt>>({
  name: '',
  beschreibung: '',
  produktklasse: 'default',
  is_default: false,
})
const error = ref('')
const saving = ref(false)

watch(() => props.produkt, (p) => {
  form.value = p
    ? { ...p, is_default: !!p.is_default }
    : { name: '', beschreibung: '', produktklasse: 'default', is_default: false }
  error.value = ''
}, { immediate: true })

const onSave = async () => {
  if (!form.value.name?.trim()) {
    error.value = t('firmen.produktDialog.produktnameIstPflicht')
    return
  }
  saving.value = true
  emit('save', form.value)
  saving.value = false
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

.form-row input,
.form-row select,
.form-row textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  cursor: pointer;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
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

.btn-primary:disabled {
  opacity: 0.6;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}
</style>
