<template>
  <div class="loeschkonzept-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar -->
      <div class="lk-toolbar">
        <div class="toolbar-info">
          <strong>🗑️ Löschkonzept (Art. 17 DSGVO · DIN 66398)</strong>
          <span class="muted">
            {{ store.regeln.length }} Regeln · {{ kategorien.length }} Datenkategorien ·
            {{ store.faellig.length }} fällig
          </span>
        </div>
        <div class="toolbar-actions">
          <button class="btn-secondary" :disabled="store.loading" @click="reload">
            🔄 Aktualisieren
          </button>
          <button class="btn-primary" @click="openCreate">＋ Neue Löschregel</button>
        </div>
      </div>

      <p v-if="store.error" class="status-msg error">{{ store.error }}</p>
      <p v-else-if="message" class="status-msg">{{ message }}</p>

      <!-- Fällige Löschungen -->
      <div v-if="store.faellig.length" class="faellig-box">
        <strong>⏰ Fällige Löschungen ({{ store.faellig.length }})</strong>
        <ul>
          <li v-for="f in store.faellig" :key="'f' + f.id">
            <code>{{ f.regel_id }}</code> — {{ f.datenkategorie || '—' }}
            <span class="trigger">Trigger: {{ f.loesch_trigger }}</span>
            <button class="btn-tiny" title="Als erledigt markieren"
                    @click="markErledigt(f.id)">✓</button>
          </li>
        </ul>
      </div>

      <p v-if="!store.regeln.length && !store.loading" class="hint">
        Noch keine Löschregeln erfasst.
      </p>

      <!-- Regeln gruppiert nach Datenkategorie -->
      <div v-for="kat in kategorien" :key="kat" class="kat-group">
        <h4 class="kat-title">{{ kat || '(ohne Datenkategorie)' }}</h4>
        <div class="lk-grid">
          <div v-for="r in regelnByKat(kat)" :key="r.id" class="lk-card" @click="openEdit(r)">
            <div class="lk-header">
              <span class="lk-id">{{ r.regel_id }}</span>
              <span class="status-pill" :style="{ background: statusColor(r.status) }">
                {{ r.status }}
              </span>
            </div>
            <div class="lk-row"><b>Aufbewahrungsfrist:</b> {{ r.aufbewahrungsfrist || '—' }}</div>
            <div class="lk-row">
              <b>Rechtsgrundlage:</b>
              <span class="rg-pill">{{ r.rechtsgrundlage_frist }}</span>
            </div>
            <div class="lk-row"><b>Löschklasse (DIN 66398):</b> {{ r.loeschklasse || '—' }}</div>
            <div class="lk-row"><b>Trigger:</b> {{ r.loesch_trigger || '—' }}</div>
            <div class="lk-meta">
              <span v-if="r.verantwortlich">👤 {{ r.verantwortlich }}</span>
              <span v-if="r.vvt_ref">📋 VVT: {{ r.vvt_ref }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Editor / Create modal -->
    <div v-if="editing" class="modal-overlay" @mousedown.self="editing = null">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ form.id ? 'Löschregel bearbeiten' : 'Neue Löschregel' }}</h3>
          <button class="btn-close" @click="editing = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Regel-ID *</label>
            <input v-model="form.regel_id" :disabled="!!form.id" placeholder="z. B. LK-001" />
          </div>
          <div class="form-row">
            <label>Datenkategorie</label>
            <input v-model="form.datenkategorie" placeholder="z. B. Bewerberdaten" />
          </div>
          <div class="form-row">
            <label>Aufbewahrungsfrist</label>
            <input v-model="form.aufbewahrungsfrist" placeholder="z. B. 6 Monate / 10 Jahre" />
          </div>
          <div class="form-row">
            <label>Rechtsgrundlage der Frist</label>
            <select v-model="form.rechtsgrundlage_frist">
              <option value="gesetzlich">gesetzlich</option>
              <option value="zweckbindung">zweckbindung</option>
            </select>
          </div>
          <div class="form-row">
            <label>Löschklasse (DIN 66398)</label>
            <input v-model="form.loeschklasse" placeholder="z. B. LK 2" />
          </div>
          <div class="form-row">
            <label>Lösch-Trigger</label>
            <input v-model="form.loesch_trigger" placeholder="z. B. Ende des Beschäftigungsverhältnisses" />
          </div>
          <div class="form-row">
            <label>Verantwortlich</label>
            <input v-model="form.verantwortlich" placeholder="z. B. HR-Abteilung" />
          </div>
          <div class="form-row">
            <label>Status</label>
            <select v-model="form.status">
              <option value="offen">offen</option>
              <option value="aktiv">aktiv</option>
              <option value="erledigt">erledigt</option>
              <option value="deaktiviert">deaktiviert</option>
            </select>
          </div>
          <div class="form-row">
            <label>VVT-Referenz</label>
            <input v-model="form.vvt_ref" placeholder="z. B. VVT-12" />
          </div>
        </div>
        <div class="modal-footer">
          <button v-if="form.id" class="btn-danger" @click="onDelete">Löschen</button>
          <span class="spacer"></span>
          <button class="btn-secondary" @click="editing = null">Abbrechen</button>
          <button class="btn-primary" :disabled="!form.regel_id.trim()" @click="onSave">Speichern</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import { useDsgvoLoeschkonzeptStore, type LoeschRegel } from '../../stores/dsgvoLoeschkonzept'

const dsgvo = useDsgvoStore()
const store = useDsgvoLoeschkonzeptStore()
const projekt = computed(() => dsgvo.selectedProjekt)

const message = ref('')

const STATUS_COLORS: Record<string, string> = {
  offen: '#9e9e9e',
  aktiv: '#1565c0',
  erledigt: '#2e7d32',
  deaktiviert: '#c62828',
}
const statusColor = (s: string) => STATUS_COLORS[s] || '#9e9e9e'

const kategorien = computed(() => {
  const set = new Set<string>()
  for (const r of store.regeln) set.add(r.datenkategorie || '')
  return Array.from(set).sort((a, b) => a.localeCompare(b))
})
const regelnByKat = (kat: string) =>
  store.regeln.filter((r) => (r.datenkategorie || '') === kat)

async function reload() {
  if (!projekt.value) return
  await store.fetchRegeln(projekt.value)
  await store.fetchFaellig(projekt.value)
}
onMounted(reload)
watch(projekt, reload)

// ── Editor ──────────────────────────────────────────────────────────────
const editing = ref<LoeschRegel | 'new' | null>(null)
const emptyForm = (): any => ({
  id: 0,
  regel_id: '',
  datenkategorie: '',
  aufbewahrungsfrist: '',
  rechtsgrundlage_frist: 'gesetzlich',
  loeschklasse: '',
  loesch_trigger: '',
  verantwortlich: '',
  status: 'offen',
  vvt_ref: '',
})
const form = ref(emptyForm())

function openCreate() {
  form.value = emptyForm()
  editing.value = 'new'
}
function openEdit(r: LoeschRegel) {
  form.value = { ...r }
  editing.value = r
}

async function onSave() {
  if (!projekt.value) return
  const payload = { ...form.value }
  let ok = false
  if (form.value.id) {
    ok = await store.updateRegel(projekt.value, form.value.id, payload)
  } else {
    ok = await store.createRegel(projekt.value, payload)
  }
  if (ok) {
    message.value = 'Gespeichert.'
    editing.value = null
  }
}

async function onDelete() {
  if (!projekt.value || !form.value.id) return
  if (!confirm('Löschregel wirklich entfernen?')) return
  const ok = await store.deleteRegel(projekt.value, form.value.id)
  if (ok) {
    message.value = 'Gelöscht.'
    editing.value = null
  }
}

async function markErledigt(pk: number) {
  if (!projekt.value) return
  const ok = await store.setStatus(projekt.value, pk, 'erledigt')
  if (ok) message.value = 'Als erledigt markiert.'
}
</script>

<style scoped>
.loeschkonzept-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.status-msg.error { background: #ffebee; color: #c62828; }
.muted { color: #888; font-size: 12px; }

.lk-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.faellig-box {
  background: #fff8e1; border: 1px solid #ffd54f; border-radius: 6px;
  padding: 10px 14px; margin-bottom: 16px; font-size: 13px;
}
.faellig-box strong { color: #e65100; }
.faellig-box ul { margin: 8px 0 0; padding-left: 18px; }
.faellig-box li { margin-bottom: 4px; }
.faellig-box code { background: #fff; padding: 1px 6px; border-radius: 3px; }
.trigger { color: #888; margin-left: 6px; }

.kat-group { margin-bottom: 18px; }
.kat-title {
  margin: 0 0 8px; font-size: 14px; color: #1565c0;
  border-bottom: 2px solid #e3f2fd; padding-bottom: 4px;
}
.lk-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;
}
.lk-card {
  background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px;
  padding: 14px; cursor: pointer; transition: all 0.15s;
}
.lk-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-color: var(--color-primary, #1565c0); }
.lk-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
}
.lk-id {
  background: #1565c0; color: white; padding: 3px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 700; font-family: monospace;
}
.lk-row { font-size: 12px; color: #555; margin-bottom: 4px; line-height: 1.4; }
.lk-row b { color: #333; }
.rg-pill {
  display: inline-block; background: #e3f2fd; color: #1565c0;
  padding: 1px 8px; border-radius: 3px; font-size: 11px; font-weight: 600;
}
.lk-meta {
  display: flex; justify-content: space-between; gap: 8px;
  font-size: 11px; color: #666; flex-wrap: wrap; margin-top: 6px;
}
.status-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
}

/* Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: white; border-radius: 8px;
  max-width: 600px; width: 95%; max-height: 90vh;
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

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row select {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-size: 13px;
}

.btn-primary, .btn-secondary, .btn-danger {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.btn-primary { background: var(--color-primary, #1565c0); color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-danger { background: #c62828; color: white; }
.btn-tiny {
  background: none; border: 1px solid #ddd; width: 22px; height: 22px;
  border-radius: 3px; cursor: pointer; color: #2e7d32; font-size: 12px; margin-left: 6px;
}
.btn-tiny:hover { background: #e8f5e9; border-color: #2e7d32; }
</style>
