<template>
  <div class="backup-view">
    <div class="header">
      <h2>Backup-Verwaltung</h2>
      <p>Erstellt, listet und stellt Backups aller Modul-Datenbanken wieder her</p>
    </div>

    <div class="actions">
      <button class="btn-primary" @click="onCreate" :disabled="creating">
        {{ creating ? 'Erstelle Backup…' : '+ Neues Backup erstellen' }}
      </button>
      <input ref="fileInput" type="file" accept=".zip" style="display:none"
             @change="onFileChosen" />
      <button class="btn-secondary" @click="(fileInput as any)?.click()" :disabled="uploading">
        {{ uploading ? 'Lade hoch…' : '⬆️ Backup hochladen' }}
      </button>
      <span v-if="lastResult" class="info-banner">{{ lastResult }}</span>
    </div>

    <div v-if="admin.error" class="alert alert-error">{{ admin.error }}</div>

    <div class="backup-table">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Erstellt am</th>
            <th>Größe</th>
            <th>Aktionen</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in admin.backups" :key="b.id">
            <td><code>{{ b.id }}</code></td>
            <td>{{ formatDate(b.created_at) }}</td>
            <td>{{ formatSize(b.size_bytes) }}</td>
            <td class="action-cell">
              <button class="btn-warn" @click="onRestore(b.id)" :disabled="restoring === b.id">
                {{ restoring === b.id ? 'Stelle wieder her…' : 'Wiederherstellen' }}
              </button>
              <button class="btn-danger" @click="onDelete(b.id)">Löschen</button>
            </td>
          </tr>
          <tr v-if="!admin.loading && admin.backups.length === 0">
            <td colspan="4" class="empty">Keine Backups vorhanden.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Restore-Confirm -->
    <div v-if="confirmRestore" class="modal-overlay" @click.self="confirmRestore = null">
      <div class="modal-content">
        <h3>⚠️ Backup wirklich wiederherstellen?</h3>
        <p>
          Backup <code>{{ confirmRestore }}</code> wird wiederhergestellt. Vor dem Restore wird ein
          Sicherheits-Backup der aktuellen Daten erstellt.
        </p>
        <p><strong>Alle aktuellen Daten werden überschrieben.</strong></p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="confirmRestore = null">Abbrechen</button>
          <button class="btn-danger" @click="executeRestore">Bestätigen und wiederherstellen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAdminStore } from '../../stores/admin'

const admin = useAdminStore()
const creating = ref(false)
const uploading = ref(false)
const restoring = ref<string | null>(null)
const confirmRestore = ref<string | null>(null)
const lastResult = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const onFileChosen = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.zip')) {
    admin.error = 'Nur .zip-Dateien erlaubt.'
    input.value = ''
    return
  }
  uploading.value = true
  lastResult.value = ''
  admin.error = null
  const result = await admin.uploadBackup(file)
  uploading.value = false
  input.value = ''
  if (result) {
    lastResult.value = `Backup hochgeladen: ${result.id} (${formatSize(result.size_bytes)})`
    setTimeout(() => (lastResult.value = ''), 5000)
  }
}

const formatDate = (iso: string): string => {
  try {
    return new Date(iso).toLocaleString('de-DE')
  } catch {
    return iso
  }
}

const formatSize = (b: number): string => {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`
  return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

const onCreate = async () => {
  creating.value = true
  lastResult.value = ''
  const result = await admin.createBackup()
  creating.value = false
  if (result) {
    lastResult.value = `Backup ${result.id} erstellt (${formatSize(result.size_bytes)})`
    setTimeout(() => (lastResult.value = ''), 5000)
  }
}

const onDelete = async (id: string) => {
  if (!confirm(`Backup ${id} wirklich löschen?`)) return
  await admin.deleteBackup(id)
}

const onRestore = (id: string) => {
  confirmRestore.value = id
}

const executeRestore = async () => {
  if (!confirmRestore.value) return
  restoring.value = confirmRestore.value
  const id = confirmRestore.value
  confirmRestore.value = null
  const ok = await admin.restoreBackup(id)
  restoring.value = null
  if (ok) {
    lastResult.value = `Backup ${id} wiederhergestellt. Bitte App neu laden.`
  }
}

onMounted(() => admin.fetchBackups())
</script>

<style scoped>
.backup-view {
  max-width: 1100px;
}

.header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.header h2 {
  margin: 0;
  font-size: 22px;
}

.header p {
  margin: 2px 0 0;
  color: #888;
  font-size: 13px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.info-banner {
  background: #e8f5e9;
  color: #2e7d32;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 13px;
  border: 1px solid #81c784;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 12px;
}

.backup-table {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th {
  background: #f5f5f5;
  text-align: left;
  padding: 10px;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}

td {
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
}

.action-cell {
  display: flex;
  gap: 8px;
}

.empty {
  padding: 40px !important;
  text-align: center;
  color: #888;
}

.btn-primary,
.btn-warn,
.btn-danger,
.btn-secondary {
  padding: 6px 14px;
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
  opacity: 0.5;
}

.btn-warn {
  background: #ff9800;
  color: white;
}

.btn-warn:hover:not(:disabled) {
  background: #f57c00;
}

.btn-danger {
  background: #d32f2f;
  color: white;
}

.btn-danger:hover {
  background: #b71c1c;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  padding: 24px;
  max-width: 500px;
  width: 90%;
}

.modal-content h3 {
  margin: 0 0 16px;
  color: #d32f2f;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}
</style>
