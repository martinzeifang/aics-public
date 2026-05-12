<template>
  <div class="issues-view">
    <div class="header">
      <h2>🔗 Issue-Übersicht</h2>
      <p>Alle Issue-Verknüpfungen über alle Compliance-Module</p>
    </div>

    <!-- Statistiken -->
    <div v-if="stats" class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total || 0 }}</div>
        <div class="stat-label">Issues gesamt</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.by_state?.open || 0 }}</div>
        <div class="stat-label">Offen</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.by_state?.closed || 0 }}</div>
        <div class="stat-label">Geschlossen</div>
      </div>
      <div class="stat-card module-breakdown">
        <div class="stat-label">Pro Modul</div>
        <div class="modules-list">
          <div v-for="(count, module) in stats.by_module" :key="module" class="module-row">
            <span>{{ module }}</span>
            <span class="count-badge">{{ count }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <select v-model="filterModule" class="filter" @change="reload">
        <option value="">Alle Module</option>
        <option v-for="m in availableModules" :key="m" :value="m">{{ m }}</option>
      </select>
      <select v-model="filterState" class="filter" @change="reload">
        <option value="">Alle Status</option>
        <option value="open">Offen</option>
        <option value="closed">Geschlossen</option>
      </select>
      <input v-model="filterProjekt" placeholder="Projekt-Name…" class="filter-input" @change="reload" />
      <button class="btn-primary" @click="reload">Aktualisieren</button>
      <button class="btn-secondary" @click="onSyncAll" :disabled="syncing">
        {{ syncing ? '⏳ Sync läuft…' : '🔄 Alle GitHub-Issues syncen' }}
      </button>
      <span class="info">{{ issues.length }} Einträge</span>
    </div>

    <div v-if="error" class="alert alert-error">{{ error }}</div>
    <div v-if="syncResult" class="alert alert-success">
      Sync abgeschlossen: {{ syncResult.synced }} aktualisiert, {{ syncResult.errors?.length || 0 }} Fehler
    </div>

    <!-- Tabelle -->
    <div class="table-wrap">
      <table v-if="issues.length > 0">
        <thead>
          <tr>
            <th>Modul</th>
            <th>Projekt</th>
            <th>Objekt</th>
            <th>Provider</th>
            <th>Issue</th>
            <th>Titel</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in issues" :key="`${i.module}-${i.id}`">
            <td><span class="module-tag">{{ i.module }}</span></td>
            <td>{{ i.projekt_name }}</td>
            <td>
              <span class="kind-badge" :class="i.object_kind">{{ i.object_kind }}</span>
              <code>{{ i.object_id }}</code>
            </td>
            <td>{{ i.provider }}</td>
            <td>
              <a v-if="i.url" :href="i.url" target="_blank" class="issue-link">
                #{{ i.issue_number || i.issue_iid }}
              </a>
              <span v-else class="muted">—</span>
            </td>
            <td class="title-cell">{{ i.title || '—' }}</td>
            <td>
              <span :class="['status-pill', i.state || 'unknown']">
                {{ i.state || 'unbekannt' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="!loading" class="empty">Keine Issues gefunden.</div>
      <div v-else class="empty">Lädt…</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import apiClient from '../../api/client'

const issues = ref<any[]>([])
const stats = ref<any | null>(null)
const loading = ref(false)
const syncing = ref(false)
const error = ref('')
const syncResult = ref<any | null>(null)

const filterModule = ref('')
const filterState = ref('')
const filterProjekt = ref('')

const availableModules = computed(() => {
  if (stats.value?.by_module) return Object.keys(stats.value.by_module)
  return ['cra', 'nis2', 'aiact', 'dora', 'risikobewertung']
})

const reload = async () => {
  loading.value = true
  error.value = ''
  try {
    const params: any = {}
    if (filterModule.value) params.module = filterModule.value
    if (filterState.value) params.state = filterState.value
    if (filterProjekt.value) params.projekt = filterProjekt.value
    const [issuesRes, statsRes] = await Promise.all([
      apiClient.get('/issues/all', { params }),
      apiClient.get('/issues/stats'),
    ])
    issues.value = issuesRes.data.issues || []
    stats.value = statsRes.data
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Fehler beim Laden'
  } finally {
    loading.value = false
  }
}

const onSyncAll = async () => {
  if (!confirm('Alle GitHub-Issues über alle Module synchronisieren? Das kann dauern.')) return
  syncing.value = true
  error.value = ''
  syncResult.value = null
  try {
    const res = await apiClient.post('/issues/sync-all')
    syncResult.value = res.data
    await reload()
    setTimeout(() => { syncResult.value = null }, 5000)
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Sync fehlgeschlagen'
  } finally {
    syncing.value = false
  }
}

onMounted(() => reload())
</script>

<style scoped>
.issues-view { max-width: 1400px; }

.header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}
.header h2 { margin: 0; font-size: 22px; }
.header p { margin: 2px 0 0; color: #888; font-size: 13px; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr) 2fr;
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 16px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-primary);
}

.stat-label {
  font-size: 12px;
  color: #888;
  text-transform: uppercase;
  margin-top: 4px;
}

.module-breakdown .modules-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.module-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.count-badge {
  background: #e3f2fd;
  color: var(--color-primary);
  padding: 1px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.filter, .filter-input {
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
}

.filter-input { min-width: 160px; }

.btn-primary, .btn-secondary {
  padding: 6px 14px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.btn-primary { background: var(--color-primary); color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.info { color: #888; font-size: 12px; margin-left: auto; }

.alert {
  padding: 10px 14px;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 13px;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
}

.alert-success {
  background: #e8f5e9;
  color: #2e7d32;
  border: 1px solid #81c784;
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
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
}

.module-tag {
  background: var(--color-primary);
  color: white;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.kind-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  margin-right: 6px;
  text-transform: uppercase;
}

.kind-badge.requirement { background: #fff3e0; color: #e65100; }
.kind-badge.owasp { background: #e3f2fd; color: var(--color-primary); }
.kind-badge.risk { background: #f3e5f5; color: #6a1b9a; }

.issue-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 600;
}

.issue-link:hover { text-decoration: underline; }

.title-cell {
  max-width: 350px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.status-pill.open { background: #e3f2fd; color: var(--color-primary); }
.status-pill.closed { background: #e8f5e9; color: #2e7d32; }
.status-pill.unknown { background: #f5f5f5; color: #666; }

.muted { color: #888; }

.empty {
  padding: 40px;
  text-align: center;
  color: #888;
}
</style>
