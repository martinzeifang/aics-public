<template>
  <div class="br-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar -->
      <div class="br-toolbar">
        <div class="toolbar-info">
          <strong>📨 Betroffenenrechte-Register (Art. 15-22 DSGVO)</strong>
          <span class="muted">
            {{ antraege.length }} Anträge · {{ overdueCount }} überfällig · {{ offenCount }} offen
          </span>
        </div>
        <div class="toolbar-actions">
          <button class="btn-secondary" :disabled="busy" @click="openCreate">
            ➕ Neuer Antrag
          </button>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>
      <p v-if="store.error" class="error-msg">{{ store.error }}</p>

      <!-- Tabelle -->
      <table v-if="antraege.length" class="br-table">
        <thead>
          <tr>
            <th>Antrag-ID</th>
            <th>Typ</th>
            <th>Eingang</th>
            <th>Frist</th>
            <th>Status</th>
            <th>Ident.</th>
            <th>Art. 19</th>
            <th>Bearbeiter</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in antraege" :key="a.id" :class="{ overdue: a.overdue }">
            <td>{{ a.antrag_id || '—' }}</td>
            <td>{{ typLabel(a.typ) }}</td>
            <td>{{ a.eingang_datum }}</td>
            <td>
              {{ a.frist_datum || '—' }}
              <span v-if="a.overdue" class="badge badge-overdue">Überfällig</span>
              <span v-else-if="a.days_left !== null && a.days_left <= 7 && !isDone(a)"
                    class="badge badge-soon">{{ a.days_left }} T</span>
              <span v-if="a.verlaengert" class="badge badge-ext">+2 M</span>
            </td>
            <td>
              <span class="status-pill" :style="{ background: statusColor(a.status) }">
                {{ statusLabel(a.status) }}
              </span>
            </td>
            <td class="center">{{ a.identitaet_geprueft ? '✔' : '—' }}</td>
            <td class="center">
              <span v-if="!isArt19(a.typ)" class="muted">—</span>
              <span v-else class="badge" :class="art19BadgeClass(a.empfaenger_status)">
                {{ art19Label(a.empfaenger_status) }}
              </span>
            </td>
            <td>{{ a.bearbeiter || '—' }}</td>
            <td class="center">
              <button class="btn-tiny" title="Bearbeiten" @click="openEdit(a)">✏️</button>
              <button class="btn-tiny btn-del" title="Löschen" @click="onDelete(a)">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="hint">Noch keine Anträge erfasst.</p>
    </template>

    <!-- Editor-Modal -->
    <div v-if="editing" class="modal-overlay" @mousedown.self="editing = null">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ form.id ? 'Antrag bearbeiten' : 'Neuer Antrag' }}</h3>
          <button class="btn-close" @click="editing = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Antrag-ID / Aktenzeichen</label>
            <input v-model="form.antrag_id" placeholder="z. B. BR-2026-001" />
          </div>
          <div class="form-row">
            <label>Typ (Art. 15-22)</label>
            <select v-model="form.typ">
              <option v-for="t in store.typen" :key="t" :value="t">{{ typLabel(t) }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>Eingangsdatum</label>
            <input v-model="form.eingang_datum" type="date" />
          </div>
          <div class="form-row checkbox-row">
            <label><input type="checkbox" v-model="form.verlaengert" /> Frist verlängert (+2 Monate)</label>
          </div>
          <div class="form-row checkbox-row">
            <label><input type="checkbox" v-model="form.identitaet_geprueft" /> Identität geprüft</label>
          </div>
          <div class="form-row">
            <label>Status</label>
            <select v-model="form.status">
              <option v-for="s in store.statusOptions" :key="s" :value="s">{{ statusLabel(s) }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>Bearbeiter</label>
            <input v-model="form.bearbeiter" />
          </div>
          <div class="form-row">
            <label>Ergebnis</label>
            <textarea v-model="form.ergebnis" rows="2"></textarea>
          </div>
          <div class="form-row">
            <label>Notizen</label>
            <textarea v-model="form.notizen" rows="2"></textarea>
          </div>

          <!-- #1218 (Art. 19): Empfänger-Benachrichtigung bei Berichtigung/Löschung/Einschränkung -->
          <fieldset v-if="isArt19(form.typ)" class="art19-box">
            <legend>Art. 19 — Mitteilung an Empfänger</legend>
            <p class="art19-hint">Pflicht-Nachweis vor Abschluss: Wurden alle
              Empfänger, denen Daten offengelegt wurden, über die
              Berichtigung/Löschung/Einschränkung unterrichtet?</p>
            <div class="form-row">
              <label>Status</label>
              <select v-model="form.empfaenger_status">
                <option value="offen">offen</option>
                <option value="benachrichtigt">Empfänger benachrichtigt</option>
                <option value="entfaellt">entfällt (keine Empfänger)</option>
              </select>
            </div>
            <div v-if="form.empfaenger_status === 'benachrichtigt'" class="form-row">
              <label>Benachrichtigte Empfänger</label>
              <textarea v-model="form.empfaenger_liste" rows="2"
                        placeholder="z. B. Hosting-Dienstleister, CRM-Anbieter …"></textarea>
            </div>
            <div v-if="form.empfaenger_status === 'benachrichtigt'" class="form-row">
              <label>Mitteilung erfolgt am</label>
              <input v-model="form.empfaenger_datum" type="date" />
            </div>
            <p v-if="art19Blocked" class="art19-warn">
              ⚠ Abschluss erst möglich, wenn die Empfänger-Benachrichtigung
              dokumentiert oder als „entfällt" markiert ist.
            </p>
          </fieldset>

          <p v-if="fristPreview" class="frist-preview">
            Berechnete Frist: <strong>{{ fristPreview }}</strong>
          </p>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="editing = null">Abbrechen</button>
          <button class="btn-primary"
                  :disabled="busy || !form.typ || !form.eingang_datum || art19Blocked"
                  @click="onSave">
            {{ busy ? 'Speichert…' : 'Speichern' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import { useDsgvoBetroffenenrechteStore, type BetroffenenrechtAntrag } from '../../stores/dsgvoBetroffenenrechte'

const dsgvo = useDsgvoStore()
const store = useDsgvoBetroffenenrechteStore()

const projekt = computed(() => dsgvo.selectedProjekt)
const antraege = computed(() => store.antraege)

const busy = ref(false)
const message = ref('')

const TYP_LABELS: Record<string, string> = {
  auskunft15: 'Auskunft (Art. 15)',
  berichtigung16: 'Berichtigung (Art. 16)',
  loeschung17: 'Löschung (Art. 17)',
  einschraenkung18: 'Einschränkung (Art. 18)',
  portabilitaet20: 'Datenübertragbarkeit (Art. 20)',
  widerspruch21: 'Widerspruch (Art. 21)',
  profiling22: 'Automatisierte Entscheidung (Art. 22)',
}
function typLabel(t: string): string { return TYP_LABELS[t] || t }

const STATUS_LABELS: Record<string, string> = {
  eingegangen: 'Eingegangen',
  in_bearbeitung: 'In Bearbeitung',
  wartet_identitaet: 'Wartet (Identität)',
  abgeschlossen: 'Abgeschlossen',
  abgelehnt: 'Abgelehnt',
}
function statusLabel(s: string): string { return STATUS_LABELS[s] || s }

const STATUS_COLORS: Record<string, string> = {
  eingegangen: '#1565c0',
  in_bearbeitung: '#f57f17',
  wartet_identitaet: '#e65100',
  abgeschlossen: '#2e7d32',
  abgelehnt: '#9e9e9e',
}
function statusColor(s: string): string { return STATUS_COLORS[s] || '#9e9e9e' }

function isDone(a: BetroffenenrechtAntrag): boolean {
  return a.status === 'abgeschlossen' || a.status === 'abgelehnt'
}

// #1218 (Art. 19): Typen mit Empfänger-Benachrichtigungspflicht.
const ART19_FALLBACK = ['berichtigung16', 'loeschung17', 'einschraenkung18']
function isArt19(typ: string): boolean {
  const list = store.art19Typen.length ? store.art19Typen : ART19_FALLBACK
  return list.includes(typ)
}
const ART19_LABELS: Record<string, string> = {
  offen: 'offen', benachrichtigt: 'benachrichtigt', entfaellt: 'entfällt',
}
function art19Label(s: string): string { return ART19_LABELS[s] || s || 'offen' }
function art19BadgeClass(s: string): string {
  return s === 'benachrichtigt' ? 'badge-done'
    : s === 'entfaellt' ? 'badge-ext' : 'badge-soon'
}

const overdueCount = computed(() => antraege.value.filter(a => a.overdue).length)
const offenCount = computed(() => antraege.value.filter(a => !isDone(a)).length)

async function load() {
  if (!projekt.value) return
  await store.fetchConstants()
  await store.fetchAntraege(projekt.value)
}
onMounted(load)
watch(projekt, load)

// ── Editor ──────────────────────────────────────────────────────────────
const editing = ref<BetroffenenrechtAntrag | null | 'new'>(null)
const form = reactive({
  id: 0,
  antrag_id: '',
  typ: 'auskunft15',
  eingang_datum: '',
  verlaengert: false,
  identitaet_geprueft: false,
  status: 'eingegangen',
  bearbeiter: '',
  ergebnis: '',
  notizen: '',
  empfaenger_status: 'offen',
  empfaenger_liste: '',
  empfaenger_datum: '',
})

// #1218 (Art. 19): Abschluss eines Art.-19-Antrags erst, wenn die Empfänger-
// Benachrichtigung dokumentiert ('benachrichtigt') oder als 'entfällt' markiert ist.
const art19Blocked = computed(() =>
  form.status === 'abgeschlossen' && isArt19(form.typ)
  && (form.empfaenger_status || 'offen') === 'offen')

function addMonths(iso: string, months: number): string {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return ''
  const dt = new Date(Date.UTC(y, m - 1 + months, 1))
  const lastDay = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth() + 1, 0)).getUTCDate()
  dt.setUTCDate(Math.min(d, lastDay))
  return dt.toISOString().slice(0, 10)
}

const fristPreview = computed(() => addMonths(form.eingang_datum, 1 + (form.verlaengert ? 2 : 0)))

function openCreate() {
  Object.assign(form, {
    id: 0, antrag_id: '', typ: store.typen[0] || 'auskunft15', eingang_datum: '',
    verlaengert: false, identitaet_geprueft: false, status: 'eingegangen',
    bearbeiter: '', ergebnis: '', notizen: '',
    empfaenger_status: 'offen', empfaenger_liste: '', empfaenger_datum: '',
  })
  editing.value = 'new'
}

function openEdit(a: BetroffenenrechtAntrag) {
  Object.assign(form, {
    id: a.id,
    antrag_id: a.antrag_id,
    typ: a.typ,
    eingang_datum: a.eingang_datum,
    verlaengert: !!a.verlaengert,
    identitaet_geprueft: !!a.identitaet_geprueft,
    status: a.status,
    bearbeiter: a.bearbeiter,
    ergebnis: a.ergebnis,
    notizen: a.notizen,
    empfaenger_status: a.empfaenger_status || 'offen',
    empfaenger_liste: a.empfaenger_liste || '',
    empfaenger_datum: a.empfaenger_datum || '',
  })
  editing.value = a
}

async function onSave() {
  if (!projekt.value) return
  busy.value = true
  try {
    const payload = {
      antrag_id: form.antrag_id,
      typ: form.typ,
      eingang_datum: form.eingang_datum,
      verlaengert: form.verlaengert ? 1 : 0,
      identitaet_geprueft: form.identitaet_geprueft ? 1 : 0,
      status: form.status,
      bearbeiter: form.bearbeiter,
      ergebnis: form.ergebnis,
      notizen: form.notizen,
      empfaenger_status: form.empfaenger_status,
      empfaenger_liste: form.empfaenger_liste,
      empfaenger_datum: form.empfaenger_datum,
    }
    const res = form.id
      ? await store.updateAntrag(projekt.value, form.id, payload)
      : await store.createAntrag(projekt.value, payload)
    if (res) {
      message.value = form.id ? 'Antrag gespeichert.' : 'Antrag angelegt.'
      editing.value = null
    }
  } finally {
    busy.value = false
  }
}

async function onDelete(a: BetroffenenrechtAntrag) {
  if (!confirm(`Antrag ${a.antrag_id || a.id} löschen?`)) return
  busy.value = true
  try {
    const ok = await store.deleteAntrag(projekt.value, a.id)
    if (ok) message.value = 'Antrag gelöscht.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.br-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.error-msg { background: #ffebee; color: #c62828; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.muted { color: #888; font-size: 12px; }

.br-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.br-table {
  width: 100%; border-collapse: collapse; font-size: 13px; background: white;
  border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px; overflow: hidden;
}
.br-table th {
  text-align: left; padding: 10px 12px; background: #f5f7fa;
  color: #1565c0; font-size: 12px; border-bottom: 1px solid #e0e0e0;
}
.br-table td { padding: 9px 12px; border-bottom: 1px solid #f0f0f0; }
.br-table tr.overdue td { background: #fff5f5; }
.br-table td.center { text-align: center; }

.status-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
  display: inline-block; white-space: nowrap;
}
.badge {
  display: inline-block; padding: 1px 6px; border-radius: 3px;
  font-size: 10px; font-weight: 600; margin-left: 6px;
}
.badge-overdue { background: #c62828; color: white; }
.badge-soon { background: #f57f17; color: white; }
.badge-ext { background: #e0e0e0; color: #555; }
.badge-done { background: #2e7d32; color: white; }

.art19-box { border: 1px solid #90caf9; border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; }
.art19-box legend { color: #1565c0; font-weight: 600; font-size: 13px; padding: 0 6px; }
.art19-hint { color: #607d8b; font-size: 12px; margin: 0 0 10px; }
.art19-warn { background: #fff8e1; color: #f57f17; padding: 6px 10px; border-radius: 4px; font-size: 12px; margin: 6px 0 0; }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: white; border-radius: 8px; max-width: 560px; width: 95%;
  max-height: 90vh; display: flex; flex-direction: column;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid var(--color-border, #e0e0e0);
}
.modal-header h3 { margin: 0; color: var(--color-primary, #1565c0); font-size: 16px; }
.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 20px; border-top: 1px solid var(--color-border, #e0e0e0);
}

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row.checkbox-row label { font-weight: 400; display: flex; align-items: center; gap: 8px; }
.form-row input[type="text"], .form-row input[type="date"], .form-row input:not([type]),
.form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-size: 13px; box-sizing: border-box;
}
.frist-preview {
  background: #e3f2fd; color: #1565c0; padding: 8px 12px;
  border-radius: 4px; font-size: 12px; margin-top: 8px;
}

.btn-tiny {
  background: none; border: 1px solid #ddd; padding: 3px 7px;
  border-radius: 3px; cursor: pointer; font-size: 12px; margin: 0 2px;
}
.btn-tiny:hover { background: #f0f0f0; }
.btn-tiny.btn-del:hover { background: #ffebee; border-color: #c62828; }

.btn-primary, .btn-secondary {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.btn-primary { background: var(--color-primary, #1565c0); color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
