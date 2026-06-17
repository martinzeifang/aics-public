<template>
  <div class="einw-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar -->
      <div class="einw-toolbar">
        <div class="toolbar-info">
          <strong>📝 Einwilligungs-Register (Art. 7 DSGVO)</strong>
          <span class="muted">
            {{ aktivCount }} aktiv · {{ widerrufenCount }} widerrufen · {{ items.length }} gesamt
          </span>
        </div>
        <div class="toolbar-actions">
          <button class="btn-secondary" :disabled="busy" @click="openCreate">
            ➕ Einwilligung erfassen
          </button>
          <button class="btn-secondary" :disabled="busy" @click="importOpen = true">
            📥 CSV-Import
          </button>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>
      <p v-if="store.error" class="error-msg">{{ store.error }}</p>

      <!-- Grid -->
      <p v-if="!items.length && !store.loading" class="hint">
        Noch keine Einwilligungen erfasst.
      </p>
      <div class="einw-grid">
        <div v-for="e in items" :key="e.id" class="einw-card" @click="openEdit(e)">
          <div class="einw-header">
            <span class="einw-id">{{ e.einwilligung_id }}</span>
            <span class="status-pill" :style="{ background: statusColor(e.status) }">
              {{ statusLabel(e.status) }}
            </span>
          </div>
          <h4>{{ e.zweck || '(ohne Zweck)' }}</h4>
          <p class="einw-meta">
            <span>📅 {{ e.zeitpunkt || '—' }}</span>
            <span>📡 {{ e.kanal || '—' }}</span>
            <span>🏷️ v{{ e.text_version }}</span>
          </p>
          <p v-if="e.widerruf_zeitpunkt" class="einw-widerruf">
            ⛔ Widerruf: {{ e.widerruf_zeitpunkt }}
          </p>
        </div>
      </div>
    </template>

    <!-- Editor-Modal -->
    <div v-if="editing" class="modal-overlay" @mousedown.self="editing = null">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ isNew ? 'Einwilligung erfassen' : `Einwilligung ${form.einwilligung_id}` }}</h3>
          <button class="btn-close" @click="editing = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Einwilligungs-ID *</label>
            <input v-model="form.einwilligung_id" :disabled="!isNew" placeholder="z.B. EW-2026-001" />
          </div>
          <div class="form-row">
            <label>Zweck</label>
            <input v-model="form.zweck" placeholder="z.B. Newsletter-Versand" />
          </div>
          <div class="form-row">
            <label>Text-Version</label>
            <input v-model="form.text_version" placeholder="1" />
          </div>
          <div class="form-row">
            <label>Einwilligungstext (Nachweis Art. 7 Abs. 1)</label>
            <textarea v-model="form.einwilligung_text" rows="3"></textarea>
          </div>
          <div class="form-row">
            <label>Zeitpunkt der Erteilung</label>
            <input v-model="form.zeitpunkt" placeholder="2026-06-01T10:00" />
          </div>
          <div class="form-row">
            <label>Kanal</label>
            <input v-model="form.kanal" placeholder="z.B. Web-Formular, Double-Opt-In" />
          </div>
          <div class="form-row">
            <label>Betroffener / Quelle</label>
            <input v-model="form.betroffener_quelle" placeholder="z.B. Kunden-ID 4711" />
          </div>
          <div class="form-row" v-if="!isNew">
            <label>Status</label>
            <select v-model="form.status">
              <option value="aktiv">aktiv</option>
              <option value="widerrufen">widerrufen</option>
              <option value="abgelaufen">abgelaufen</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button
            v-if="!isNew && form.status !== 'widerrufen'"
            class="btn-warn"
            :disabled="busy"
            @click="onWiderruf"
          >
            ⛔ Widerruf erfassen (Art. 7 Abs. 3)
          </button>
          <button
            v-if="!isNew"
            class="btn-danger"
            :disabled="busy"
            @click="onDelete"
          >
            🗑️ Löschen
          </button>
          <button class="btn-secondary" @click="editing = null">Abbrechen</button>
          <button class="btn-primary" :disabled="busy" @click="onSave">Speichern</button>
        </div>
      </div>
    </div>

    <!-- CSV-Import-Modal -->
    <div v-if="importOpen" class="modal-overlay" @mousedown.self="importOpen = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>📥 CSV-Import</h3>
          <button class="btn-close" @click="importOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">
            CSV mit Kopfzeile. Spalten: <code>einwilligung_id, zweck, text_version,
            einwilligung_text, zeitpunkt, kanal, betroffener_quelle, status</code>
          </p>
          <textarea
            v-model="csvText"
            rows="8"
            placeholder="einwilligung_id,zweck,zeitpunkt,kanal,status&#10;EW-001,Newsletter,2026-06-01,Web,aktiv"
          ></textarea>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="importOpen = false">Abbrechen</button>
          <button class="btn-primary" :disabled="busy || !csvText.trim()" @click="onImport">
            Importieren
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import { useDsgvoEinwilligungStore, type DsgvoEinwilligung } from '../../stores/dsgvoEinwilligung'

const dsgvoStore = useDsgvoStore()
const store = useDsgvoEinwilligungStore()

const projekt = computed(() => dsgvoStore.selectedProjekt)
const items = computed(() => store.items)

const busy = ref(false)
const message = ref('')

const aktivCount = computed(() => items.value.filter((e) => e.status === 'aktiv').length)
const widerrufenCount = computed(() => items.value.filter((e) => e.status === 'widerrufen').length)

const STATUS_COLORS: Record<string, string> = {
  aktiv: '#2e7d32',
  widerrufen: '#c62828',
  abgelaufen: '#e65100',
}
function statusColor(s: string): string { return STATUS_COLORS[s] || '#9e9e9e' }
function statusLabel(s: string): string { return s || 'unbekannt' }

async function load() {
  if (!projekt.value) return
  await store.fetchEinwilligungen(projekt.value)
}
onMounted(load)
watch(projekt, load)

// ── Editor ──────────────────────────────────────────────────────────────
const editing = ref<DsgvoEinwilligung | null>(null)
const isNew = ref(false)
const emptyForm = (): Partial<DsgvoEinwilligung> => ({
  einwilligung_id: '',
  zweck: '',
  text_version: '1',
  einwilligung_text: '',
  zeitpunkt: '',
  kanal: '',
  betroffener_quelle: '',
  status: 'aktiv',
})
const form = ref<Partial<DsgvoEinwilligung>>(emptyForm())

function openCreate() {
  isNew.value = true
  form.value = emptyForm()
  editing.value = {} as DsgvoEinwilligung
}

function openEdit(e: DsgvoEinwilligung) {
  isNew.value = false
  form.value = { ...e }
  editing.value = e
}

async function onSave() {
  if (!projekt.value) return
  const eid = (form.value.einwilligung_id || '').trim()
  if (!eid) { message.value = 'Einwilligungs-ID ist Pflicht.'; return }
  busy.value = true
  try {
    const ok = isNew.value
      ? await store.createEinwilligung(projekt.value, form.value)
      : await store.updateEinwilligung(projekt.value, eid, form.value)
    if (ok) { message.value = 'Gespeichert.'; editing.value = null }
  } finally { busy.value = false }
}

async function onWiderruf() {
  if (!projekt.value || !form.value.einwilligung_id) return
  if (!confirm('Widerruf der Einwilligung erfassen (Art. 7 Abs. 3)?')) return
  busy.value = true
  try {
    const ok = await store.widerrufEinwilligung(projekt.value, form.value.einwilligung_id)
    if (ok) { message.value = 'Widerruf erfasst.'; editing.value = null }
  } finally { busy.value = false }
}

async function onDelete() {
  if (!projekt.value || !form.value.einwilligung_id) return
  if (!confirm('Einwilligungs-Datensatz löschen?')) return
  busy.value = true
  try {
    const ok = await store.deleteEinwilligung(projekt.value, form.value.einwilligung_id)
    if (ok) { message.value = 'Gelöscht.'; editing.value = null }
  } finally { busy.value = false }
}

// ── CSV-Import ──────────────────────────────────────────────────────────
const importOpen = ref(false)
const csvText = ref('')

async function onImport() {
  if (!projekt.value) return
  busy.value = true
  try {
    const res = await store.importCsv(projekt.value, csvText.value)
    if (res) {
      message.value = `Import: ${res.imported} übernommen, ${res.skipped} übersprungen.`
      importOpen.value = false
      csvText.value = ''
    }
  } finally { busy.value = false }
}
</script>

<style scoped>
.einw-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.error-msg { background: #ffebee; color: #c62828; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.muted { color: #888; font-size: 12px; }

.einw-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.einw-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;
}
.einw-card {
  background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px;
  padding: 14px; cursor: pointer; transition: all 0.15s;
}
.einw-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-color: var(--color-primary, #1565c0); }
.einw-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
}
.einw-id {
  background: #1565c0; color: white;
  padding: 3px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 700; font-family: monospace;
}
.einw-card h4 { margin: 0 0 8px; font-size: 14px; }
.einw-meta {
  display: flex; justify-content: space-between; gap: 8px;
  font-size: 11px; color: #666; flex-wrap: wrap; margin: 0 0 4px;
}
.einw-widerruf { margin: 4px 0 0; font-size: 11px; color: #c62828; font-weight: 600; }
.status-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
}

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: white; border-radius: 8px;
  max-width: 640px; width: 95%; max-height: 90vh;
  display: flex; flex-direction: column;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid var(--color-border, #e0e0e0);
}
.modal-header h3 { margin: 0; color: var(--color-primary, #1565c0); font-size: 16px; }
.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap;
  padding: 12px 20px; border-top: 1px solid var(--color-border, #e0e0e0);
}

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row textarea, .form-row select {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-size: 13px; box-sizing: border-box;
}
.form-row input:disabled { background: #f5f5f5; color: #888; }

code { background: #f5f5f5; padding: 1px 4px; border-radius: 3px; font-size: 11px; }

.btn-primary, .btn-secondary, .btn-warn, .btn-danger {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.btn-primary { background: var(--color-primary, #1565c0); color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-warn { background: #e65100; color: white; }
.btn-warn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-danger { background: #c62828; color: white; }
.btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
