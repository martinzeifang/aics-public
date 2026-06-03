<template>
  <div class="db-view">
    <div class="header">
      <h2>DB-Viewer</h2>
      <p>Read-only Inspektor für alle Modul-Datenbanken</p>
    </div>

    <div class="layout">
      <!-- DB-Liste -->
      <aside class="db-list">
        <h3>Datenbanken</h3>
        <div
          v-for="db in admin.dbList"
          :key="db.key"
          @click="selectDb(db.key)"
          :class="['db-item', { active: selectedDb === db.key }]"
        >
          <div class="db-name">{{ db.key }}</div>
          <div class="db-size">{{ formatSize(db.size_bytes) }}</div>
        </div>
      </aside>

      <!-- Tabellen + Daten -->
      <main class="db-main">
        <div v-if="!selectedDb" class="placeholder">
          ← Datenbank wählen
        </div>

        <template v-else>
          <div class="tab-row">
            <button
              v-for="t in admin.dbTables"
              :key="t"
              @click="selectTable(t)"
              :class="['tab-btn', { active: selectedTable === t }]"
            >
              {{ t }}
            </button>
          </div>

          <div v-if="selectedTable" class="data-area">
            <div class="data-toolbar">
              <input v-model="searchQuery" placeholder="Suche…" class="search" @keyup.enter="reload" />
              <button class="btn-primary" @click="reload">Suchen</button>
              <span class="info">{{ admin.dbTotal }} Zeilen</span>
            </div>

            <div class="table-wrap" v-if="admin.dbRows.length > 0">
              <table>
                <thead>
                  <tr>
                    <th v-for="c in admin.dbColumns" :key="c">{{ c }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in admin.dbRows" :key="i">
                    <td v-for="c in admin.dbColumns" :key="c">
                      <span class="cell-content">{{ formatValue(row[c]) }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else-if="!admin.loading" class="empty">Keine Daten in dieser Tabelle.</div>
            <div v-else class="loading">Lädt…</div>

            <div class="pagination" v-if="admin.dbTotal > pageSize">
              <button @click="prevPage" :disabled="page === 0">&laquo;</button>
              <span>{{ page + 1 }} / {{ Math.ceil(admin.dbTotal / pageSize) }}</span>
              <button @click="nextPage" :disabled="(page + 1) * pageSize >= admin.dbTotal">&raquo;</button>
            </div>
          </div>

          <div v-else class="placeholder">↑ Tabelle wählen</div>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAdminStore } from '../../stores/admin'

const admin = useAdminStore()
const selectedDb = ref<string | null>(null)
const selectedTable = ref<string | null>(null)
const searchQuery = ref('')
const page = ref(0)
const pageSize = 100

const formatSize = (b: number): string => {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

const formatValue = (v: any): string => {
  if (v === null) return '∅'
  if (typeof v === 'string' && v.length > 100) return v.substring(0, 100) + '…'
  return String(v)
}

const selectDb = async (key: string) => {
  selectedDb.value = key
  selectedTable.value = null
  await admin.fetchDbTables(key)
}

const selectTable = async (table: string) => {
  selectedTable.value = table
  page.value = 0
  searchQuery.value = ''
  await reload()
}

const reload = async () => {
  if (!selectedDb.value || !selectedTable.value) return
  await admin.fetchDbRows(selectedDb.value, selectedTable.value, {
    q: searchQuery.value,
    limit: pageSize,
    offset: page.value * pageSize,
  })
}

const nextPage = async () => {
  page.value++
  await reload()
}

const prevPage = async () => {
  if (page.value > 0) {
    page.value--
    await reload()
  }
}

onMounted(() => admin.fetchDbList())
</script>

<style scoped>
.db-view {
  max-width: 1500px;
  height: calc(100vh - 180px);
  display: flex;
  flex-direction: column;
}

.header {
  margin-bottom: 12px;
  padding-bottom: 8px;
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

.layout {
  display: flex;
  gap: 12px;
  flex: 1;
  overflow: hidden;
}

.db-list {
  width: 200px;
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 12px;
  overflow-y: auto;
}

.db-list h3 {
  margin: 0 0 8px;
  font-size: 12px;
  text-transform: uppercase;
  color: #666;
}

.db-item {
  padding: 8px 10px;
  cursor: pointer;
  border-radius: 4px;
  border-left: 3px solid transparent;
}

.db-item:hover {
  background: #f5f5f5;
}

.db-item.active {
  background: #e3f2fd;
  border-left-color: var(--color-primary);
}

.db-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.db-size {
  font-size: 11px;
  color: #999;
}

.db-main {
  flex: 1;
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tab-row {
  display: flex;
  gap: 2px;
  padding: 8px;
  background: #f5f5f5;
  border-bottom: 1px solid var(--color-border);
  overflow-x: auto;
}

.tab-btn {
  background: white;
  border: 1px solid var(--color-border);
  padding: 5px 10px;
  font-size: 12px;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
}

.tab-btn.active {
  background: var(--color-primary);
  color: white;
}

.data-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.data-toolbar {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
}

.search {
  padding: 5px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
  width: 200px;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: 5px 12px;
  border-radius: 4px;
  cursor: pointer;
}

.info {
  margin-left: auto;
  color: #888;
  font-size: 12px;
}

.table-wrap {
  flex: 1;
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
  padding: 6px 10px;
  font-weight: 600;
  position: sticky;
  top: 0;
  border-bottom: 1px solid var(--color-border);
}

td {
  padding: 5px 10px;
  border-bottom: 1px solid #f0f0f0;
  white-space: nowrap;
}

.cell-content {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
}

.placeholder,
.empty,
.loading {
  padding: 40px;
  text-align: center;
  color: #888;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pagination {
  display: flex;
  gap: 8px;
  justify-content: center;
  align-items: center;
  padding: 8px;
  border-top: 1px solid var(--color-border);
}

.pagination button {
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
}
</style>
