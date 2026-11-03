<template>
  <div class="dpw" :class="{ 'dpw-cloud': provider === 'cloud' }">
    <div class="dpw-head">
      <span class="dpw-icon" aria-hidden="true">{{ provider === 'cloud' ? '☁️' : '🔍' }}</span>
      <strong>Diese Daten werden an die KI übermittelt</strong>
    </div>

    <p v-if="provider === 'cloud'" class="dpw-egress-warn">
      ⚠️ Cloud-Modus: Diese Daten verlassen dein Netzwerk.
    </p>

    <ul class="dpw-list">
      <li
        v-for="(field, idx) in fields"
        :key="idx"
        class="dpw-row"
        :class="{ 'dpw-sensitive': isSensitive(field.label) }"
      >
        <span class="dpw-label">
          <span v-if="isSensitive(field.label)" class="dpw-flag" title="Sensibles Feld">⚠️</span>
          {{ field.label }}
        </span>
        <span class="dpw-value">{{ formatValue(field.value) }}</span>
      </li>
    </ul>

    <template v-if="!confirmed">
      <label class="dpw-confirm">
        <input type="checkbox" v-model="acknowledged" />
        <span>Ich habe geprüft, welche Daten übermittelt werden.</span>
      </label>

      <div class="dpw-actions">
        <button class="dpw-btn" type="button" :disabled="!acknowledged" @click="onConfirm">
          Bestätigen
        </button>
      </div>
    </template>

    <p v-else class="dpw-confirmed">✓ Übermittlung bestätigt — du kannst den Prompt jetzt nutzen.</p>
  </div>
</template>

<script setup lang="ts">
/**
 * DataPreviewWarning — zeigt vor dem KI-Aufruf, welche Daten übermittelt
 * werden (#868). Hebt sensible Felder hervor und verlangt eine explizite
 * Bestätigung. Im Cloud-Modus zusätzlich ein Egress-Warnhinweis (#877).
 *
 * Props:
 *   - fields:    { label, value }[] — die in den Prompt einfließenden Daten.
 *   - sensitive: string[] — Labels, die als sensibel hervorgehoben werden.
 *   - provider:  'on_prem' | 'cloud' — steuert den Egress-Hinweis.
 *
 * Emits:
 *   - confirm:  Nutzer hat die Übermittlung bestätigt.
 *
 * Teil von #865.
 */
import { ref, computed } from 'vue'

interface PreviewField {
  label: string
  value: unknown
}

const props = withDefaults(
  defineProps<{
    fields?: PreviewField[]
    sensitive?: string[]
    provider?: 'on_prem' | 'cloud'
  }>(),
  { fields: () => [], sensitive: () => [], provider: 'on_prem' },
)

const emit = defineEmits<{ (e: 'confirm'): void }>()

const acknowledged = ref(false)
const confirmed = ref(false)

const sensitiveSet = computed(
  () => new Set((props.sensitive || []).map((s) => String(s).toLowerCase())),
)

function isSensitive(label: string) {
  return sensitiveSet.value.has(String(label || '').toLowerCase())
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch (e) {
      return String(value)
    }
  }
  return String(value)
}

function onConfirm() {
  if (!acknowledged.value) return
  confirmed.value = true
  emit('confirm')
}
</script>

<style scoped>
.dpw {
  border: 1px solid #cfd8dc;
  border-radius: 8px;
  padding: 0.8rem 1rem;
  background: #f5f7fa;
  font-size: 0.85rem;
}

.dpw-cloud {
  border-color: #ffcc80;
  background: #fff8e1;
}

.dpw-head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
  color: #37474f;
}

.dpw-icon {
  font-size: 1rem;
}

.dpw-egress-warn {
  margin: 0 0 0.6rem;
  color: #e65100;
  font-weight: 600;
}

.dpw-list {
  list-style: none;
  margin: 0 0 0.7rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.dpw-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.25rem 0.4rem;
  border-radius: 4px;
}

.dpw-sensitive {
  background: #ffebee;
}

.dpw-label {
  color: #455a64;
  font-weight: 500;
}

.dpw-flag {
  margin-right: 0.2rem;
}

.dpw-value {
  color: #263238;
  text-align: right;
  word-break: break-word;
  max-width: 60%;
}

.dpw-confirm {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.6rem;
  color: #37474f;
  cursor: pointer;
}

.dpw-actions {
  display: flex;
  justify-content: flex-end;
}

.dpw-btn {
  padding: 0.4rem 0.9rem;
  border-radius: 6px;
  border: none;
  background: var(--color-primary, #1565c0);
  color: #fff;
  cursor: pointer;
  font-size: 0.82rem;
}

.dpw-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.dpw-confirmed {
  margin: 0.2rem 0 0;
  color: #2e7d32;
  font-weight: 600;
  font-size: 0.85rem;
}
</style>
