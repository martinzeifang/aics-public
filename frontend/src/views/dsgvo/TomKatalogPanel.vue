<template>
  <div class="tom-panel">
    <p v-if="!projektName" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar -->
      <div class="tom-toolbar">
        <div class="toolbar-info">
          <strong>🛡️ TOM-Katalog (SDM-Gewährleistungsziele · Art. 32)</strong>
          <span class="muted">{{ store.bewertet }} / {{ store.gesamt }} bewertet · ø {{ store.avg.toFixed(1) }} / 5</span>
        </div>
        <div class="toolbar-actions">
          <button class="btn-secondary" :disabled="busy !== ''" @click="onSeed">
            {{ busy === 'seed' ? '⏳ Lädt…' : '📋 Standard-Katalog seeden' }}
          </button>
          <button class="btn-secondary" :disabled="busy !== ''" @click="openKi">
            {{ busy === 'ki' ? '⏳ Lädt…' : '🤖 KI-Vorschlag' }}
          </button>
          <button class="btn-secondary" :disabled="busy !== ''" @click="openNew">➕ Maßnahme</button>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>
      <p v-if="store.error" class="error-msg">{{ store.error }}</p>

      <p v-if="!store.loading && store.gesamt === 0" class="hint">
        Noch keine Maßnahmen. Über „Standard-Katalog seeden" die SDM-Maßnahmen anlegen.
      </p>

      <!-- Katalog gruppiert nach Ziel -->
      <div v-for="g in store.gruppen" :key="g.ziel" class="ziel-group">
        <template v-if="g.massnahmen.length">
          <h3 class="ziel-head">{{ g.ziel }} <span class="ziel-count">({{ g.massnahmen.length }})</span></h3>
          <div class="tom-grid">
            <div v-for="m in g.massnahmen" :key="m.massnahme_key" class="tom-card" @click="openEdit(m)">
              <div class="tom-cardhead">
                <span class="tom-key">{{ m.massnahme_key }}</span>
                <span class="score-pill" :style="{ background: scoreColor(m.status) }">{{ m.status }}/5</span>
              </div>
              <h4>{{ m.titel || m.massnahme_key }}</h4>
              <p class="tom-desc">{{ truncate(m.beschreibung, 130) }}</p>
              <div class="tom-meta">
                <span>Soll {{ m.soll }}</span>
                <span v-if="m.verantwortlich">👤 {{ m.verantwortlich }}</span>
                <span v-if="m.wirksamkeit_datum" class="wirk-ok">✔ {{ m.wirksamkeit_datum }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </template>

    <!-- Editor-Modal -->
    <div v-if="editing" class="modal-overlay" @mousedown.self="editing = null">
      <div class="modal-content edit-modal">
        <div class="modal-header">
          <h3>{{ form.massnahme_key || 'Neue Maßnahme' }}</h3>
          <button class="btn-close" @click="editing = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Gewährleistungsziel</label>
            <select v-model="form.ziel">
              <option v-for="z in ziele" :key="z" :value="z">{{ z }}</option>
            </select>
          </div>
          <div class="form-row" v-if="isNew">
            <label>Maßnahmen-Key</label>
            <input v-model="form.massnahme_key" placeholder="z. B. VT-10" />
          </div>
          <div class="form-row">
            <label>Titel</label>
            <input v-model="form.titel" />
          </div>
          <div class="form-row">
            <label>Beschreibung</label>
            <textarea v-model="form.beschreibung" rows="3"></textarea>
          </div>
          <div class="form-row">
            <label>Status (Ist, 0-5)</label>
            <input v-model.number="form.status" type="range" min="0" max="5" />
            <span class="score-display" :style="{ background: scoreColor(form.status) }">
              {{ form.status }} – {{ statusLabel(form.status) }}
            </span>
          </div>
          <div class="form-row">
            <label>Soll (0-5)</label>
            <input v-model.number="form.soll" type="number" min="0" max="5" />
          </div>
          <div class="form-row">
            <label>Verantwortlich</label>
            <input v-model="form.verantwortlich" />
          </div>
          <div class="form-row">
            <label>VVT-Referenz</label>
            <input v-model="form.vvt_ref" placeholder="z. B. VVT-7" />
          </div>

          <fieldset class="wirk-section">
            <legend>🔬 Wirksamkeitsprüfung</legend>
            <div class="form-row">
              <label>Datum der Prüfung</label>
              <input v-model="form.wirksamkeit_datum" type="date" />
            </div>
            <div class="form-row">
              <label>Ergebnis</label>
              <textarea v-model="form.wirksamkeit_ergebnis" rows="2"
                        placeholder="z. B. wirksam / teilweise wirksam / Mangel …"></textarea>
            </div>
          </fieldset>
        </div>
        <div class="modal-footer">
          <button v-if="!isNew" class="btn-danger" :disabled="busy !== ''" @click="onDelete">Löschen</button>
          <span style="flex:1"></span>
          <button class="btn-secondary" @click="editing = null">Abbrechen</button>
          <button class="btn-primary" :disabled="busy !== ''" @click="onSave">Speichern</button>
        </div>
      </div>
    </div>

    <!-- KI-Vorschlag-Modal (Stub) -->
    <div v-if="kiOpen" class="modal-overlay" @mousedown.self="kiOpen = false">
      <div class="modal-content ki-modal">
        <div class="modal-header">
          <h3>🤖 KI-Vorschlag (Stub)</h3>
          <button class="btn-close" @click="kiOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">Heuristische Empfehlungen je Gewährleistungsziel. Echte KI-Anbindung folgt (#1104).</p>
          <p v-if="!kiItems.length" class="muted">Keine Empfehlungen.</p>
          <div v-for="(v, i) in kiItems" :key="i" class="ki-row">
            <span class="ki-prio" :class="v.prioritaet">{{ v.prioritaet }}</span>
            <div>
              <strong>{{ v.ziel }}</strong>
              <p class="ki-text">{{ v.empfehlung }}</p>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="kiOpen = false">Schließen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoTomStore, type TomMassnahme, type KiVorschlag } from '../../stores/dsgvoTom'

const props = defineProps<{ projektName: string }>()
const store = useDsgvoTomStore()

const projektName = computed(() => props.projektName)
const ziele = computed(() => store.ziele)

const busy = ref<'' | 'seed' | 'ki' | 'save' | 'delete'>('')
const message = ref('')

const STATUS_LABELS = ['Nicht bewertet', 'Nicht vorhanden', 'In Planung', 'Teilweise', 'Weitgehend', 'Vollständig']
function statusLabel(n: number): string { return STATUS_LABELS[n] || String(n) }

const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']
const scoreColor = (s: number) => SCORE_COLORS[s] || '#9e9e9e'
const truncate = (s: string, n: number): string => (s && s.length > n) ? s.substring(0, n) + '…' : s

async function load() {
  if (!projektName.value) return
  await store.fetchZiele()
  await store.fetchMassnahmen(projektName.value)
}
onMounted(load)
watch(projektName, load)

// ── Editor ──────────────────────────────────────────────────────────────
const editing = ref<TomMassnahme | null>(null)
const isNew = ref(false)
const emptyForm = (): TomMassnahme => ({
  ziel: store.ziele[0] || 'Datenminimierung',
  massnahme_key: '',
  titel: '',
  beschreibung: '',
  status: 0,
  soll: 5,
  verantwortlich: '',
  wirksamkeit_datum: '',
  wirksamkeit_ergebnis: '',
  vvt_ref: '',
})
const form = ref<TomMassnahme>(emptyForm())

function openEdit(m: TomMassnahme) {
  isNew.value = false
  form.value = { ...m }
  editing.value = m
}

function openNew() {
  isNew.value = true
  form.value = emptyForm()
  editing.value = form.value
}

async function onSave() {
  if (isNew.value && !form.value.massnahme_key.trim()) {
    message.value = 'Maßnahmen-Key ist Pflicht.'
    return
  }
  busy.value = 'save'
  try {
    const ok = await store.saveMassnahme({ ...form.value })
    if (ok) {
      message.value = `${form.value.massnahme_key} gespeichert.`
      editing.value = null
    }
  } finally { busy.value = '' }
}

async function onDelete() {
  if (!confirm(`Maßnahme ${form.value.massnahme_key} löschen?`)) return
  busy.value = 'delete'
  try {
    const ok = await store.deleteMassnahme(form.value.massnahme_key)
    if (ok) {
      message.value = `${form.value.massnahme_key} gelöscht.`
      editing.value = null
    }
  } finally { busy.value = '' }
}

// ── Seed ────────────────────────────────────────────────────────────────
async function onSeed() {
  busy.value = 'seed'
  try {
    const n = await store.seed(false)
    if (n !== null) message.value = `Standard-Katalog: ${n} Maßnahme(n) ergänzt.`
  } finally { busy.value = '' }
}

// ── KI-Vorschlag ────────────────────────────────────────────────────────
const kiOpen = ref(false)
const kiItems = ref<KiVorschlag[]>([])

async function openKi() {
  busy.value = 'ki'
  try {
    kiItems.value = await store.fetchKiVorschlag()
    kiOpen.value = true
  } finally { busy.value = '' }
}
</script>

<style scoped>
.tom-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.error-msg { background: #ffebee; color: #c62828; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.muted { color: #888; font-size: 12px; }

.tom-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.ziel-group { margin-bottom: 18px; }
.ziel-head { color: #1565c0; font-size: 14px; margin: 0 0 8px; border-bottom: 2px solid #e3f2fd; padding-bottom: 4px; }
.ziel-count { color: #999; font-weight: 400; font-size: 12px; }

.tom-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px;
}
.tom-card {
  background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px;
  padding: 14px; cursor: pointer; transition: all 0.15s;
}
.tom-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-color: var(--color-primary, #1565c0); }
.tom-cardhead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.tom-key {
  background: #1565c0; color: white; padding: 3px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 700; font-family: monospace;
}
.tom-card h4 { margin: 0 0 8px; font-size: 14px; }
.tom-desc { margin: 0 0 8px; font-size: 12px; color: #555; line-height: 1.4; }
.tom-meta { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; color: #666; flex-wrap: wrap; }
.wirk-ok { color: #2e7d32; }
.score-pill { padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600; }

/* Modal */
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
  display: flex; align-items: center; gap: 8px;
  padding: 12px 20px; border-top: 1px solid var(--color-border, #e0e0e0);
}

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input[type="range"] { width: 70%; vertical-align: middle; }
.form-row input:not([type="range"]), .form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-size: 13px;
}
.score-display {
  display: inline-block; padding: 4px 12px; border-radius: 4px;
  color: white; font-weight: 600; min-width: 40px; text-align: center; margin-left: 8px;
}

.wirk-section {
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 6px; padding: 10px 14px; margin-top: 16px; background: #f9f9f9;
}
.wirk-section legend {
  padding: 0 6px; font-weight: 600; font-size: 12px;
  color: var(--color-primary, #1565c0); text-transform: uppercase;
}

.ki-row { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid #eee; }
.ki-prio {
  padding: 2px 8px; border-radius: 3px; font-size: 10px; font-weight: 600;
  text-transform: uppercase; flex-shrink: 0; margin-top: 2px;
}
.ki-prio.hoch { background: #ffebee; color: #c62828; }
.ki-prio.mittel { background: #fff8e1; color: #e65100; }
.ki-text { margin: 4px 0 0; font-size: 12px; color: #555; }

.btn-primary, .btn-secondary, .btn-danger {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.btn-primary { background: var(--color-primary, #1565c0); color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-danger { background: #c62828; color: white; }
.btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
