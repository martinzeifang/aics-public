<template>
  <div class="modal-overlay" @click.self="onCancel">
    <div class="modal-content">
      <h3>♻️ Gelöschte Kunden</h3>
      <p class="hint">
        Soft-gelöschte Kunden können reaktiviert oder endgültig entfernt werden.
        Endgültige Löschung kann <strong>nicht rückgängig gemacht</strong> werden.
      </p>

      <div v-if="kunden.deletedKunden.length === 0" class="empty">
        Keine gelöschten Kunden gefunden.
      </div>

      <table v-else class="deleted-table">
        <thead>
          <tr>
            <th>Projektname</th>
            <th>Unternehmen</th>
            <th>Gelöscht am</th>
            <th>Aktion</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in kunden.deletedKunden" :key="d.name">
            <td>{{ d.name }}</td>
            <td>{{ d.unternehmen || '—' }}</td>
            <td>{{ formatDate(d.deleted_at) }}</td>
            <td class="action-cell">
              <button class="btn-small" @click="onRestore(d.name)" :disabled="busy">
                ♻️ Reaktivieren
              </button>
              <button class="btn-danger-small" @click="onHardDelete(d.name)" :disabled="busy">
                ❌ Endgültig
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="message" class="info-banner">{{ message }}</div>

      <div class="modal-actions">
        <button class="btn-secondary" @click="onCancel">Schließen</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useKundenStore } from '../../../stores/kunden'

const emit = defineEmits<{ cancel: [] }>()

const kunden = useKundenStore()
const busy = ref(false)
const message = ref('')

const formatDate = (s: string): string => {
  try {
    return new Date(s.includes('T') ? s : s.replace(' ', 'T') + 'Z').toLocaleString('de-DE')
  } catch {
    return s
  }
}

const onRestore = async (name: string) => {
  busy.value = true
  const ok = await kunden.restoreKunde(name)
  busy.value = false
  if (ok) {
    message.value = `${name} wurde reaktiviert.`
    setTimeout(() => (message.value = ''), 3000)
  }
}

const onHardDelete = async (name: string) => {
  if (!confirm(`Kunde "${name}" ENDGÜLTIG löschen? Diese Aktion ist NICHT umkehrbar.`)) return
  busy.value = true
  const ok = await kunden.hardDeleteKunde(name)
  busy.value = false
  if (ok) {
    message.value = `${name} wurde endgültig gelöscht.`
    setTimeout(() => (message.value = ''), 3000)
  }
}

const onCancel = () => emit('cancel')

onMounted(async () => {
  await kunden.fetchDeletedKunden()
})
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
  max-width: 700px;
  width: 90%;
  max-height: 85vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin: 0 0 8px;
  color: var(--color-primary);
}

.hint {
  margin: 0 0 16px;
  color: #888;
  font-size: 13px;
  line-height: 1.4;
}

.empty {
  padding: 32px;
  text-align: center;
  color: #888;
}

.deleted-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.deleted-table th {
  background: #f5f5f5;
  text-align: left;
  padding: 8px 10px;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}

.deleted-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
}

.action-cell {
  display: flex;
  gap: 6px;
}

.btn-small,
.btn-danger-small {
  padding: 4px 10px;
  border-radius: 3px;
  border: 1px solid var(--color-border);
  background: white;
  cursor: pointer;
  font-size: 12px;
}

.btn-small:disabled,
.btn-danger-small:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-danger-small {
  color: #d32f2f;
  border-color: #d32f2f;
}

.btn-danger-small:hover:not(:disabled) {
  background: #ffebee;
}

.info-banner {
  background: #e8f5e9;
  color: #2e7d32;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 12px 0;
  font-size: 13px;
  border: 1px solid #81c784;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
</style>
