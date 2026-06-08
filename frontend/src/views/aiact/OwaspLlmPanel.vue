<template>
  <div class="owasp-llm-panel">
    <div class="panel-header">
      <div>
        <h3>🛡️ OWASP-LLM-Top-10-Register</h3>
        <p>
          Status-Verwaltung (0–5) je LLM-Top-10-Risiko · token-aware Repo-Auto-Detect ·
          KI-Vorschläge · Issue-Tracking. Mapping auf AI-Act Art. 9 / Art. 15.
        </p>
      </div>
      <div class="header-actions">
        <span class="assistent-hint">
          🔍 Auto-Detect (Repo) &amp; 🤖 KI-Vorschläge: <strong>Zum Assistenten →</strong>
          Reiter „🤖 Assistenten".
        </span>
      </div>
    </div>

    <p v-if="!projekt" class="hint">Bitte zuerst ein AI-Act-Projekt auswählen.</p>

    <div v-else class="table-wrap">
      <p v-if="message" class="status-msg">{{ message }}</p>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Risiko</th>
            <th>Status</th>
            <th>AI-Act-Mapping</th>
            <th>Kommentar</th>
            <th>Issues</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in items" :key="it.id">
            <td class="mono">{{ it.id }}</td>
            <td>
              <a :href="it.ref" target="_blank" rel="noopener">{{ it.title }}</a>
              <div class="item-hint">{{ it.hint }}</div>
            </td>
            <td>
              <select :value="it.status" @change="onStatusChange(it, $event)"
                      :class="['status-pill', `s${it.status}`]">
                <option v-for="n in [0,1,2,3,4,5]" :key="n" :value="n">
                  {{ n }} – {{ statusLabel(n) }}
                </option>
              </select>
            </td>
            <td class="mono small">
              <span v-for="m in it.maps_to" :key="m" class="map-chip">{{ m }}</span>
              <span v-if="!it.maps_to.length">—</span>
            </td>
            <td>
              <input class="kommentar-input" :value="it.kommentar"
                     placeholder="Notiz…"
                     @change="onKommentarChange(it, $event)" />
            </td>
            <td>
              <div v-if="it.issues && it.issues.length" class="issue-cell">
                <a v-for="li in it.issues" :key="li.id" :href="li.url" target="_blank"
                   rel="noopener" :class="['issue-pill', li.state || 'open']"
                   :title="li.title">
                  #{{ li.issue_number || li.issue_iid }} {{ li.state || 'open' }}
                </a>
                <button class="btn-mini" :disabled="busy" @click="sync(it)" title="Status synchronisieren">🔄</button>
              </div>
              <span v-else class="muted">–</span>
            </td>
            <td>
              <button class="btn-mini" :disabled="busy" @click="createIssue(it)"
                      title="GitHub/GitLab-Issue anlegen">🐙 Issue</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'

const store = useAiActStore()
const projekt = computed(() => store.selectedProjekt)
const items = computed(() => store.owaspLlmItems)

const busy = ref<'' | 'detect' | 'wizard' | 'issue' | 'sync'>('')
const message = ref('')

const STATUS_LABELS = ['Nicht bewertet', 'Nicht vorhanden', 'In Planung', 'Teilweise', 'Weitgehend', 'Vollständig']
function statusLabel(n: number): string { return STATUS_LABELS[n] || String(n) }

async function load() {
  if (!projekt.value) return
  await store.fetchOwaspLlmRegister()
}

onMounted(load)
watch(projekt, load)

async function onStatusChange(it: any, ev: Event) {
  const status = parseInt((ev.target as HTMLSelectElement).value, 10)
  await store.saveOwaspLlmStatus(it.id, status, it.kommentar || '')
}

async function onKommentarChange(it: any, ev: Event) {
  const kommentar = (ev.target as HTMLInputElement).value
  await store.saveOwaspLlmStatus(it.id, it.status, kommentar)
}

async function createIssue(it: any) {
  busy.value = 'issue'
  try {
    const res = await store.createOwaspLlmIssue(it.id)
    message.value = res ? `Issue angelegt: ${res.url}` : (store.error || 'Issue-Anlage fehlgeschlagen.')
  } finally { busy.value = '' }
}

async function sync(it: any) {
  busy.value = 'sync'
  try {
    const res = await store.syncOwaspLlmIssues(it.id)
    message.value = res ? `Issues synchronisiert: ${res.synced ?? 0}.` : (store.error || 'Sync fehlgeschlagen.')
  } finally { busy.value = '' }
}
</script>

<style scoped>
.owasp-llm-panel { padding: 4px 0; }
.panel-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.panel-header h3 { margin: 0 0 4px; color: #1565c0; }
.panel-header p { margin: 0; color: #607d8b; font-size: 0.85rem; max-width: 640px; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.assistent-hint { color: #6a1b9a; font-size: 0.82rem; max-width: 280px; }
.assistent-hint strong { color: #4a148c; }
.hint { color: #607d8b; padding: 16px 0; }
.table-wrap { margin-top: 14px; overflow-x: auto; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eceff1; vertical-align: top; }
th { color: #455a64; font-weight: 600; background: #f5f7fa; }
.mono { font-family: Consolas, monospace; }
.small { font-size: 0.78rem; }
.item-hint { color: #90a4ae; font-size: 0.75rem; margin-top: 2px; }
.map-chip { display: inline-block; background: #e3f2fd; color: #1565c0; border-radius: 3px; padding: 1px 5px; margin: 0 3px 3px 0; }
.status-pill { border: 1px solid #cfd8dc; border-radius: 4px; padding: 3px 6px; font-size: 0.8rem; }
.status-pill.s0 { background: #f5f5f5; }
.status-pill.s1 { background: #ffcdd2; }
.status-pill.s2 { background: #ffe0b2; }
.status-pill.s3 { background: #fff9c4; }
.status-pill.s4 { background: #c8e6c9; }
.status-pill.s5 { background: #a5d6a7; }
.kommentar-input { width: 100%; min-width: 150px; border: 1px solid #cfd8dc; border-radius: 4px; padding: 4px 6px; font-size: 0.8rem; }
.issue-cell { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.issue-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 0.72rem; text-decoration: none; background: #eceff1; color: #37474f; }
.issue-pill.closed { background: #c8e6c9; color: #2e7d32; }
.muted { color: #b0bec5; }
.btn-mini { border: none; background: #455a64; color: #fff; border-radius: 4px; padding: 3px 7px; font-size: 0.75rem; cursor: pointer; }
.btn-mini:disabled { opacity: 0.5; cursor: default; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; padding: 20px; border-radius: 8px; width: 640px; max-width: 92vw; max-height: 90vh; overflow-y: auto; }
.modal h4 { margin: 0 0 6px; color: #1565c0; }
.modal label { display: block; font-size: 0.8rem; color: #455a64; margin: 10px 0 4px; font-weight: 600; }
.modal textarea.code { width: 100%; font-family: Consolas, monospace; font-size: 0.8rem; border: 1px solid #cfd8dc; border-radius: 4px; padding: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
</style>
