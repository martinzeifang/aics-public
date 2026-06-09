<template>
  <div class="audit-view">
    <div class="header">
      <h2>Audit-Log</h2>
      <p>Übersicht aller protokollierten System-Ereignisse</p>
    </div>

    <div class="toolbar">
      <input v-model="filters.module" placeholder="Modul filtern…" class="filter" @change="reload" />
      <select v-model="filters.outcome" class="filter" @change="reload">
        <option value="">Alle Ergebnisse</option>
        <option value="success">success</option>
        <option value="fail">fail</option>
        <option value="start">start</option>
      </select>
      <input v-model="filters.since" type="date" class="filter" @change="reload" />
      <button class="btn-primary" @click="reload">Aktualisieren</button>
      <a :href="csvUrl" download class="btn-secondary">CSV-Export</a>
      <span class="info">{{ admin.auditTotal }} Einträge</span>
    </div>

    <div v-if="admin.error" class="alert alert-error">{{ admin.error }}</div>

    <div class="table-wrap">
      <table v-if="admin.auditEvents.length > 0">
        <thead>
          <tr>
            <th v-for="c in columns" :key="c">{{ c }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(ev, i) in admin.auditEvents" :key="i" :class="['row', rowClass(ev)]">
            <td v-for="c in columns" :key="c" class="cell">
              <code v-if="isJson(ev[c])" class="json-cell">{{ ev[c] }}</code>
              <span v-else>{{ ev[c] ?? '' }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!admin.loading" class="empty">Keine Audit-Events gefunden.</div>
      <div v-else class="loading">Lädt…</div>
    </div>

    <div class="pagination" v-if="admin.auditTotal > pageSize">
      <button @click="prevPage" :disabled="page === 0">&laquo; Zurück</button>
      <span>Seite {{ page + 1 }} von {{ Math.ceil(admin.auditTotal / pageSize) }}</span>
      <button @click="nextPage" :disabled="(page + 1) * pageSize >= admin.auditTotal">Weiter &raquo;</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminStore } from '../../stores/admin'

const admin = useAdminStore()
const filters = ref({ module: '', outcome: '', since: '' })
const page = ref(0)
const pageSize = 100

const columns = computed(() => {
  const first = admin.auditEvents[0]
  if (!first) return []
  return Object.keys(first)
})

const queryParams = computed(() => {
  const p: any = { limit: pageSize, offset: page.value * pageSize }
  if (filters.value.module) p.module = filters.value.module
  if (filters.value.outcome) p.outcome = filters.value.outcome
  if (filters.value.since) p.since = filters.value.since
  return p
})

const csvUrl = computed(() => admin.auditCsvUrl(queryParams.value))

const reload = async () => {
  page.value = 0
  await admin.fetchAuditEvents(queryParams.value)
}

const nextPage = async () => {
  page.value++
  await admin.fetchAuditEvents(queryParams.value)
}

const prevPage = async () => {
  if (page.value > 0) {
    page.value--
    await admin.fetchAuditEvents(queryParams.value)
  }
}

const isJson = (v: any): boolean => {
  if (typeof v !== 'string') return false
  return v.startsWith('{') || v.startsWith('[')
}

const rowClass = (ev: any): string => {
  if (ev.outcome === 'fail') return 'fail'
  if (ev.outcome === 'success') return 'success'
  return ''
}

onMounted(() => reload())
</script>

<style scoped>
.audit-view {
  max-width: 1400px;
}

.header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.header h2 {
  margin: 0;
  font-size: 22px;
  color: var(--color-text-primary);
}

.header p {
  margin: 2px 0 0;
  color: #888;
  font-size: 13px;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.filter {
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
}

.btn-primary,
.btn-secondary {
  padding: 6px 14px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  text-decoration: none;
  display: inline-block;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}

.info {
  color: #888;
  font-size: 12px;
  margin-left: auto;
}

.table-wrap {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th {
  background: #f5f5f5;
  text-align: left;
  padding: 8px;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 1;
}

td {
  padding: 6px 8px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: top;
  white-space: nowrap;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row.fail {
  background: #ffebee;
}

.row.success {
  background: #f1f8e9;
}

.json-cell {
  font-family: monospace;
  font-size: 11px;
  color: #555;
  white-space: pre-wrap;
  max-width: 400px;
  overflow: hidden;
  display: inline-block;
}

.empty,
.loading {
  padding: 40px;
  text-align: center;
  color: #888;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
  padding: 10px;
  border-radius: 4px;
  margin-bottom: 12px;
}

.pagination {
  display: flex;
  gap: 12px;
  justify-content: center;
  align-items: center;
  margin-top: 16px;
  font-size: 13px;
}

.pagination button {
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
