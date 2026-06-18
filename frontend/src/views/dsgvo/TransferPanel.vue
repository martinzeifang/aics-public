<template>
  <div class="transfer-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar -->
      <div class="transfer-toolbar">
        <div class="toolbar-info">
          <strong>🌍 Drittlandtransfer-Register (Art. 44–49)</strong>
          <span class="muted">{{ transfers.length }} Transfer(s) · TIA: {{ tiaDone }} abgeschlossen</span>
        </div>
        <div class="toolbar-actions">
          <button class="btn-primary" @click="openCreate">➕ Transfer anlegen</button>
        </div>
      </div>

      <p v-if="store.error" class="status-msg err">{{ store.error }}</p>
      <p v-else-if="message" class="status-msg">{{ message }}</p>

      <p v-if="!transfers.length" class="hint">Noch keine Drittlandtransfers erfasst.</p>

      <!-- Grid -->
      <div class="transfer-grid">
        <div v-for="t in transfers" :key="t.transfer_id" class="transfer-card" @click="openEdit(t)">
          <div class="transfer-header">
            <span class="transfer-id">{{ t.transfer_id }}</span>
            <span class="status-pill" :style="{ background: tiaColor(t.tia_status) }">
              TIA: {{ tiaLabel(t.tia_status) }}
            </span>
          </div>
          <h4>{{ t.empfaenger || '(ohne Empfänger)' }}</h4>
          <p class="transfer-desc">🏳️ {{ t.drittland || '–' }} · {{ grundlageLabel(t.grundlage) }}</p>
          <div class="transfer-meta">
            <span v-if="t.vvt_ref">VVT: {{ t.vvt_ref }}</span>
            <span v-if="t.avv_ref">AVV: {{ t.avv_ref }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- Editor-Modal: Stammdaten + geführte TIA -->
    <div v-if="editing" class="modal-overlay" @mousedown.self="closeEditor">
      <div class="modal-content transfer-modal">
        <div class="modal-header">
          <h3>{{ isNew ? 'Neuer Transfer' : `Transfer ${form.transfer_id}` }}</h3>
          <button class="btn-close" @click="closeEditor">✕</button>
        </div>
        <div class="modal-body">
          <fieldset class="section">
            <legend>Übermittlung</legend>
            <div class="form-row">
              <label>Transfer-ID *</label>
              <input v-model="form.transfer_id" :disabled="!isNew" placeholder="z.B. T-001" />
            </div>
            <div class="form-row">
              <label>Empfänger</label>
              <input v-model="form.empfaenger" placeholder="z.B. Cloud-Anbieter Inc." />
            </div>
            <div class="form-row">
              <label>Drittland</label>
              <input v-model="form.drittland" placeholder="z.B. USA" />
            </div>
            <div class="form-row">
              <label>Grundlage (Art. 45–49)</label>
              <select v-model="form.grundlage">
                <option value="">– bitte wählen –</option>
                <option v-for="g in store.grundlagen" :key="g" :value="g">{{ grundlageLabel(g) }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>Garantie-Detail (z.B. SCC-Modul, BCR-Ref)</label>
              <textarea v-model="form.garantie_detail" rows="2"></textarea>
            </div>
            <div class="form-grid-2">
              <div class="form-row">
                <label>VVT-Referenz</label>
                <input v-model="form.vvt_ref" placeholder="Art. 30 Verzeichnis" />
              </div>
              <div class="form-row">
                <label>AVV-Referenz</label>
                <input v-model="form.avv_ref" placeholder="Art. 28 AVV" />
              </div>
            </div>
          </fieldset>

          <fieldset class="section tia-section">
            <legend>🔎 Geführte TIA (EDSA 01/2020)</legend>
            <div class="form-row">
              <label>1. Rechtslage im Drittland</label>
              <textarea v-model="form.tia_json.rechtslage" rows="3"
                        placeholder="Zugriffsbefugnisse von Behörden, Rechtsmittel für Betroffene …"></textarea>
            </div>
            <div class="form-row">
              <label>2. Zusatzgarantien (technisch/organisatorisch/vertraglich)</label>
              <textarea v-model="form.tia_json.zusatzgarantien" rows="3"
                        placeholder="Verschlüsselung, Pseudonymisierung, vertragliche Klauseln …"></textarea>
            </div>
            <div class="form-row">
              <label>3. Risikoabwägung</label>
              <textarea v-model="form.tia_json.risikoabwaegung" rows="3"
                        placeholder="Restrisiko nach Zusatzgarantien …"></textarea>
            </div>
            <div class="form-row">
              <label>4. Ergebnis</label>
              <textarea v-model="form.tia_json.ergebnis" rows="2"
                        placeholder="Transfer zulässig / unzulässig / zusätzliche Maßnahmen nötig"></textarea>
            </div>
            <div class="form-row">
              <label>TIA-Status</label>
              <select v-model="form.tia_status">
                <option v-for="s in store.tiaStatus" :key="s" :value="s">{{ tiaLabel(s) }}</option>
              </select>
            </div>
          </fieldset>
        </div>
        <div class="modal-footer">
          <button v-if="!isNew" class="btn-danger" @click="onDelete">🗑️ Löschen</button>
          <span class="spacer"></span>
          <button class="btn-secondary" @click="closeEditor">Abbrechen</button>
          <button class="btn-primary" :disabled="busy || !form.transfer_id.trim()" @click="onSave">
            {{ busy ? 'Speichere…' : 'Speichern' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import { useDsgvoTransferStore, type DsgvoTransfer } from '../../stores/dsgvoTransfer'

const dsgvo = useDsgvoStore()
const store = useDsgvoTransferStore()

const projekt = computed(() => dsgvo.selectedProjekt)
const transfers = computed(() => store.transfers)

const message = ref('')
const busy = ref(false)

const GRUNDLAGE_LABELS: Record<string, string> = {
  '': '–',
  angemessenheit45: 'Angemessenheitsbeschluss (Art. 45)',
  scc46: 'Standardvertragsklauseln (Art. 46)',
  bcr: 'Binding Corporate Rules (Art. 47)',
  ausnahme49: 'Ausnahme (Art. 49)',
}
const TIA_LABELS: Record<string, string> = {
  offen: 'Offen',
  in_arbeit: 'In Arbeit',
  abgeschlossen: 'Abgeschlossen',
}
const TIA_COLORS: Record<string, string> = {
  offen: '#9e9e9e',
  in_arbeit: '#f57f17',
  abgeschlossen: '#2e7d32',
}
const grundlageLabel = (g: string) => GRUNDLAGE_LABELS[g] ?? g
const tiaLabel = (s: string) => TIA_LABELS[s] ?? s
const tiaColor = (s: string) => TIA_COLORS[s] ?? '#9e9e9e'

const tiaDone = computed(
  () => transfers.value.filter((t) => t.tia_status === 'abgeschlossen').length,
)

function emptyForm(): DsgvoTransfer {
  return {
    projekt_name: projekt.value || '',
    transfer_id: '',
    empfaenger: '',
    drittland: '',
    grundlage: '',
    garantie_detail: '',
    tia_status: 'offen',
    tia_json: { rechtslage: '', zusatzgarantien: '', risikoabwaegung: '', ergebnis: '' },
    vvt_ref: '',
    avv_ref: '',
  }
}

const editing = ref(false)
const isNew = ref(false)
const form = ref<DsgvoTransfer>(emptyForm())

async function load() {
  if (!projekt.value) return
  await store.fetchConstants()
  await store.fetchTransfers(projekt.value)
}
onMounted(load)
watch(projekt, load)

function openCreate() {
  form.value = emptyForm()
  isNew.value = true
  editing.value = true
}

function openEdit(t: DsgvoTransfer) {
  form.value = {
    ...emptyForm(),
    ...t,
    tia_json: { ...emptyForm().tia_json, ...(t.tia_json || {}) },
  }
  isNew.value = false
  editing.value = true
}

function closeEditor() {
  editing.value = false
}

async function onSave() {
  if (!projekt.value) return
  busy.value = true
  try {
    const payload = {
      transfer_id: form.value.transfer_id.trim(),
      empfaenger: form.value.empfaenger,
      drittland: form.value.drittland,
      grundlage: form.value.grundlage,
      garantie_detail: form.value.garantie_detail,
      tia_status: form.value.tia_status,
      tia_json: form.value.tia_json,
      vvt_ref: form.value.vvt_ref,
      avv_ref: form.value.avv_ref,
    }
    const ok = isNew.value
      ? await store.createTransfer(projekt.value, payload)
      : await store.updateTransfer(projekt.value, payload.transfer_id, payload)
    if (ok) {
      message.value = `Transfer ${payload.transfer_id} gespeichert.`
      editing.value = false
    }
  } finally {
    busy.value = false
  }
}

async function onDelete() {
  if (!projekt.value) return
  if (!confirm(`Transfer ${form.value.transfer_id} löschen?`)) return
  busy.value = true
  try {
    const ok = await store.deleteTransfer(projekt.value, form.value.transfer_id)
    if (ok) {
      message.value = 'Transfer gelöscht.'
      editing.value = false
    }
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.transfer-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.status-msg.err { background: #ffebee; color: #c62828; }
.muted { color: #888; font-size: 12px; }

.transfer-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.transfer-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;
}
.transfer-card {
  background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px;
  padding: 14px; cursor: pointer; transition: all 0.15s;
}
.transfer-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-color: var(--color-primary, #1565c0); }
.transfer-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.transfer-id {
  background: #1565c0; color: white; padding: 3px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 700; font-family: monospace;
}
.transfer-card h4 { margin: 0 0 8px; font-size: 14px; }
.transfer-desc { margin: 0 0 8px; font-size: 12px; color: #555; line-height: 1.4; }
.transfer-meta { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; color: #666; flex-wrap: wrap; }
.status-pill { padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600; }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: white; border-radius: 8px;
  max-width: 720px; width: 95%; max-height: 90vh;
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
  display: flex; align-items: center; gap: 8px;
  padding: 12px 20px; border-top: 1px solid var(--color-border, #e0e0e0);
}
.spacer { flex: 1; }

.section {
  border: 1px solid var(--color-border, #e0e0e0); border-radius: 6px;
  padding: 10px 14px; margin-bottom: 14px;
}
.section legend {
  padding: 0 6px; font-weight: 600; font-size: 12px;
  color: var(--color-primary, #1565c0); text-transform: uppercase;
}
.tia-section { background: #f9f9f9; }

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-size: 13px; box-sizing: border-box;
}
.form-row textarea { resize: vertical; }
.form-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

.btn-primary, .btn-secondary, .btn-danger {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.btn-primary { background: var(--color-primary, #1565c0); color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-danger { background: #ffebee; color: #c62828; border: 1px solid #c62828; }
.btn-danger:hover { background: #c62828; color: white; }
</style>
