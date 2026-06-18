<template>
  <div class="firma-selector">
    <!-- Anzeige-Modus -->
    <div v-if="!editing" class="firma-display">
      <span class="firma-label">Firma:</span>
      <span class="firma-value" :class="{ empty: !modelValue }">
        {{ modelValue || '— ohne Firma —' }}
      </span>
      <button class="btn-edit" type="button" @click="onStartEdit" :title="t.changeCustomer">
        ✎
      </button>
    </div>

    <!-- Edit-Modus -->
    <div v-else class="firma-edit">
      <select v-model="draft" :disabled="saving">
        <option value="">— ohne Firma —</option>
        <option v-for="k in firmenStore.firmen" :key="k.name" :value="k.name">
          {{ k.name }}<span v-if="k.company"> ({{ k.company }})</span>
        </option>
      </select>
      <button class="btn-save" type="button" @click="onSave" :disabled="saving || draft === modelValue">
        {{ saving ? '…' : '✓ Speichern' }}
      </button>
      <button class="btn-cancel" type="button" @click="onCancel" :disabled="saving">
        Abbrechen
      </button>
    </div>

    <div v-if="message" class="firma-msg" :class="{ error: isError }">
      {{ message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useFirmenStore } from '../../stores/firmen'

// Issue #436: Generischer Inline-Editor fuer das Firmen-Feld eines
// Modul-Projekts. Sendet beim Speichern ein 'save'-Event mit dem
// neuen Wert und ueberlaesst das eigentliche PUT dem Caller.

const props = defineProps<{
  modelValue: string                     // aktueller Firmen-Name (unternehmen/organisation)
  saving?: boolean                       // Caller setzt true, waehrend PUT laeuft
  successText?: string                   // optionale Erfolgs-Meldung
  errorText?: string                     // optionale Fehler-Meldung
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  save: [value: string]
}>()

const firmenStore = useFirmenStore()
const editing = ref(false)
const draft = ref(props.modelValue || '')

const t = {
  changeCustomer: 'Firmen zuordnen / ändern',
}

const message = ref('')
const isError = ref(false)

watch(() => props.successText, (v) => {
  if (v) { message.value = v; isError.value = false; editing.value = false }
})
watch(() => props.errorText, (v) => {
  if (v) { message.value = v; isError.value = true }
})
watch(() => props.modelValue, (v) => {
  draft.value = v || ''
})

const onStartEdit = () => {
  draft.value = props.modelValue || ''
  message.value = ''
  if (firmenStore.firmen.length === 0) firmenStore.fetchFirmen()
  editing.value = true
}

const onSave = () => {
  emit('update:modelValue', draft.value)
  emit('save', draft.value)
}

const onCancel = () => {
  draft.value = props.modelValue || ''
  editing.value = false
  message.value = ''
}
</script>

<style scoped>
.firma-selector {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.firma-display, .firma-edit {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.firma-label {
  color: var(--color-text-secondary, #666);
  font-weight: 500;
}

.firma-value {
  font-weight: 600;
  color: var(--color-text-primary, #1a1a1a);
}

.firma-value.empty {
  color: var(--color-text-secondary, #999);
  font-style: italic;
  font-weight: 400;
}

.btn-edit {
  background: transparent;
  border: 1px solid var(--color-border, #d4d8e0);
  color: var(--color-text-secondary, #666);
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
  font-size: 13px;
}

.btn-edit:hover {
  background: var(--color-surface-alt, #f3f5f9);
  color: var(--color-primary, #1565c0);
  border-color: var(--color-primary, #1565c0);
}

.firma-edit select {
  padding: 4px 8px;
  border: 1px solid var(--color-border, #d4d8e0);
  border-radius: 4px;
  font-size: 13px;
  min-width: 220px;
  background: white;
}

.btn-save, .btn-cancel {
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid;
}

.btn-save {
  background: var(--color-primary, #1565c0);
  color: white;
  border-color: var(--color-primary, #1565c0);
}
.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-cancel {
  background: white;
  color: var(--color-text-secondary, #666);
  border-color: var(--color-border, #d4d8e0);
}

.firma-msg {
  font-size: 11px;
  color: #2e7d32;
}
.firma-msg.error {
  color: #c62828;
}
</style>
