<template>
  <div class="kontrollen-panel">
    <p v-if="!projektName" class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar -->
      <div class="kp-toolbar">
        <div class="toolbar-info">
          <strong>🗓️ Jährlicher Kontrollplan</strong>
          <span class="muted">{{ store.kontrollen.length }} Kontrolle(n) · {{ jahr }}</span>
        </div>
        <div class="toolbar-actions">
          <label class="jahr-label">Jahr
            <select v-model.number="jahr" class="jahr-select">
              <option v-for="j in jahrOptionen" :key="j" :value="j">{{ j }}</option>
            </select>
          </label>
          <button class="btn-secondary" :disabled="busy !== ''" @click="onSeed">
            {{ busy === 'seed' ? '⏳ Lädt…' : '📋 Standard-Kontrollen anlegen' }}
          </button>
          <button class="btn-secondary" :disabled="busy !== ''" @click="openNew">➕ Kontrolle</button>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>
      <p v-if="store.error" class="error-msg">{{ store.error }}</p>

      <p v-if="!store.loading && store.kontrollen.length === 0" class="hint">
        Noch keine Kontrollen für {{ jahr }}. Über „Standard-Kontrollen anlegen" den Jahresplan erzeugen.
      </p>

      <!-- Tabelle -->
      <div v-if="store.kontrollen.length" class="kp-list">
        <table>
          <thead>
            <tr>
              <th>Bereich</th>
              <th>Titel</th>
              <th class="c-status">Status</th>
              <th>Verantwortlich</th>
              <th class="c-anh">📎</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="k in store.kontrollen" :key="k.id" class="kp-row" @click="openDetail(k)">
              <td><span class="bereich-tag">{{ k.bereich }}</span></td>
              <td class="title-cell">{{ k.titel }}<br /><span class="kid">{{ k.kontroll_id }}</span></td>
              <td class="c-status">
                <span class="status-pill" :style="statusStyle(k.status)">{{ statusLabel(k.status) }}</span>
              </td>
              <td>{{ k.verantwortlich || '—' }}</td>
              <td class="c-anh">
                <span v-if="anhaengeCount(k)">📎 {{ anhaengeCount(k) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Detail-Modal -->
    <div v-if="detail" class="modal-overlay" @mousedown.self="closeDetail">
      <div class="modal-content detail-modal">
        <div class="modal-header">
          <h3>{{ form.titel || 'Neue Kontrolle' }}
            <span v-if="!isNew" class="status-pill modal-status" :style="statusStyle(form.status)">
              {{ statusLabel(form.status) }}
            </span>
          </h3>
          <button class="btn-close" @click="closeDetail">✕</button>
        </div>
        <div class="modal-body">
          <p v-if="locked" class="lock-note">
            🔒 Stammdaten gesperrt (Status: {{ statusLabel(form.status) }}). Bearbeitung nur im Status „geplant".
          </p>

          <!-- Stammdaten -->
          <fieldset class="section" :disabled="locked">
            <legend>Stammdaten</legend>
            <div class="form-grid">
              <div class="form-cell">
                <label>Kontroll-ID<span class="req">*</span></label>
                <input v-model="form.kontroll_id" :disabled="!isNew" placeholder="z. B. K-01" />
              </div>
              <div class="form-cell">
                <label>Bereich</label>
                <select v-model="form.bereich">
                  <option v-for="b in bereiche" :key="b" :value="b">{{ b }}</option>
                </select>
              </div>
              <div class="form-cell full">
                <label>Titel<span class="req">*</span></label>
                <input v-model="form.titel" />
              </div>
              <div class="form-cell">
                <label>Frequenz</label>
                <select v-model="form.frequenz">
                  <option v-for="f in frequenzen" :key="f" :value="f">{{ f }}</option>
                </select>
              </div>
              <div class="form-cell">
                <label>Verantwortlich</label>
                <input v-model="form.verantwortlich" />
              </div>
              <div class="form-cell">
                <label>Geplant am</label>
                <input v-model="form.geplant_am" type="date" />
              </div>
              <div class="form-cell">
                <label>Bezug / Referenz</label>
                <input v-model="form.bezug_ref" placeholder="z. B. TOM-7, VVT-3" />
              </div>
            </div>
          </fieldset>

          <div v-if="!isNew" class="freigabe-row">
            <button
              v-if="form.status === 'geplant'"
              class="btn-approve"
              :disabled="busy !== '' || !canApprove"
              :title="canApprove ? '' : 'Berechtigung dsgvo:approve erforderlich'"
              @click="onFreigeben"
            >
              {{ busy === 'freigeben' ? '⏳…' : '✅ Freigeben' }}
            </button>
            <span v-if="form.freigabe_von" class="freigabe-info">
              Freigegeben von {{ form.freigabe_von }} am {{ formatDate(form.freigabe_am) }}
            </span>
          </div>

          <!-- Durchführungs-Doku -->
          <fieldset v-if="!isNew" class="section">
            <legend>🔬 Durchführung dokumentieren</legend>
            <div class="form-grid">
              <div class="form-cell">
                <label>Durchgeführt am</label>
                <input v-model="dokuForm.durchgefuehrt_am" type="date" />
              </div>
              <div class="form-cell">
                <label>Durchgeführt von</label>
                <input v-model="dokuForm.durchgefuehrt_von" />
              </div>
              <div class="form-cell full">
                <label>Ergebnis</label>
                <textarea v-model="dokuForm.ergebnis" rows="3"
                          placeholder="Feststellungen, Ergebnis, Folgemaßnahmen…"></textarea>
              </div>
              <div class="form-cell full check-cell">
                <label class="check-row">
                  <input type="checkbox" v-model="dokuForm.abschliessen" />
                  Kontrolle abschließen (Status → abgeschlossen)
                </label>
              </div>
            </div>
            <button class="btn-secondary" :disabled="busy !== ''" @click="onDokumentieren">
              {{ busy === 'doku' ? '⏳…' : '💾 Durchführung speichern' }}
            </button>
          </fieldset>

          <!-- Anhänge -->
          <fieldset v-if="!isNew" class="section">
            <legend>📎 Anhänge ({{ anhaenge.length }})</legend>
            <div class="anh-upload">
              <input ref="fileInput" type="file" @change="onFilePicked" />
              <button class="btn-secondary mini" :disabled="busy !== '' || !pickedFile" @click="onUpload">
                {{ busy === 'upload' ? '⏳…' : '⬆️ Hochladen' }}
              </button>
            </div>
            <ul v-if="anhaenge.length" class="anh-list">
              <li v-for="a in anhaenge" :key="a.id">
                <span class="anh-name">{{ a.filename }}</span>
                <span class="anh-meta">{{ formatSize(a.size) }} · {{ formatDate(a.uploaded_at) }}</span>
                <button class="btn-tiny" title="Herunterladen" @click="onDownloadAnhang(a)">⬇️</button>
                <button class="btn-tiny del" title="Löschen" @click="onDeleteAnhang(a)">🗑️</button>
              </li>
            </ul>
            <p v-else class="muted">Keine Anhänge.</p>
          </fieldset>
        </div>
        <div class="modal-footer">
          <button v-if="!isNew" class="btn-danger" :disabled="busy !== ''" @click="onDelete">Löschen</button>
          <span style="flex:1"></span>
          <button class="btn-secondary" @click="closeDetail">{{ isNew ? 'Abbrechen' : 'Schließen' }}</button>
          <button v-if="isNew || !locked" class="btn-primary" :disabled="busy !== ''" @click="onSaveStamm">
            {{ busy === 'save' ? '⏳…' : 'Speichern' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoKontrollenStore, type Kontrolle, type KontrolleAnhang } from '../../stores/dsgvoKontrollen'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{ projektName: string }>()
const store = useDsgvoKontrollenStore()
const auth = useAuthStore()

const projektName = computed(() => props.projektName)
const canApprove = computed(() => auth.hasPermission('dsgvo:approve'))

const currentYear = new Date().getFullYear()
const jahr = ref<number>(currentYear)
const jahrOptionen = computed(() => {
  const arr: number[] = []
  for (let y = currentYear + 1; y >= currentYear - 5; y--) arr.push(y)
  return arr
})

const busy = ref<'' | 'seed' | 'save' | 'freigeben' | 'doku' | 'upload' | 'delete'>('')
const message = ref('')

const bereiche = computed(() => store.constants?.bereiche || [])
const frequenzen = computed(() => store.constants?.frequenz || ['jaehrlich'])

const STATUS_LABELS: Record<string, string> = {
  geplant: 'Geplant',
  freigegeben: 'Freigegeben',
  in_durchfuehrung: 'In Durchführung',
  abgeschlossen: 'Abgeschlossen',
}
const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  geplant: { bg: '#e3f2fd', fg: '#1565c0' },
  freigegeben: { bg: '#fff8e1', fg: '#e65100' },
  in_durchfuehrung: { bg: '#f3e5f5', fg: '#6a1b9a' },
  abgeschlossen: { bg: '#e8f5e9', fg: '#2e7d32' },
}
const statusLabel = (s: string) => STATUS_LABELS[s] || s || '—'
const statusStyle = (s: string) => {
  const c = STATUS_COLORS[s] || { bg: '#eee', fg: '#555' }
  return { background: c.bg, color: c.fg }
}

const anhaengeCount = (k: Kontrolle): number =>
  typeof k.anhaenge === 'number' ? k.anhaenge : (k.anhaenge?.length || 0)

const formatDate = (s?: string | null): string => {
  if (!s) return '—'
  try { return new Date(s).toLocaleDateString('de-DE') } catch { return s }
}
const formatSize = (n: number): string => {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  if (!projektName.value) return
  await store.fetchConstants()
  await store.fetchKontrollen(projektName.value, jahr.value)
}
onMounted(load)
watch(projektName, load)
watch(jahr, () => { if (projektName.value) store.fetchKontrollen(projektName.value, jahr.value) })

// ── Detail / Form ─────────────────────────────────────────────────────────
const detail = ref<Kontrolle | null>(null)
const isNew = ref(false)
const anhaenge = ref<KontrolleAnhang[]>([])

const emptyForm = (): Partial<Kontrolle> => ({
  kontroll_id: '',
  titel: '',
  bereich: bereiche.value[0] || '',
  jahr: jahr.value,
  frequenz: frequenzen.value[0] || 'jaehrlich',
  verantwortlich: '',
  geplant_am: '',
  bezug_ref: '',
  status: 'geplant',
  freigabe_von: '',
  freigabe_am: '',
})
const form = ref<Partial<Kontrolle>>(emptyForm())
const dokuForm = ref({ durchgefuehrt_am: '', durchgefuehrt_von: '', ergebnis: '', abschliessen: false })

const locked = computed(() => !isNew.value && form.value.status !== 'geplant')

function applyKontrolle(k: Kontrolle) {
  form.value = { ...k }
  dokuForm.value = {
    durchgefuehrt_am: k.durchgefuehrt_am || '',
    durchgefuehrt_von: k.durchgefuehrt_von || '',
    ergebnis: k.ergebnis || '',
    abschliessen: false,
  }
}

async function openDetail(k: Kontrolle) {
  isNew.value = false
  detail.value = k
  applyKontrolle(k)
  anhaenge.value = []
  pickedFile.value = null
  // Vollständige Kontrolle inkl. Anhänge nachladen.
  const full = await store.fetchKontrolle(k.id)
  if (full) {
    applyKontrolle(full)
    anhaenge.value = Array.isArray(full.anhaenge) ? full.anhaenge : []
  }
}

function openNew() {
  isNew.value = true
  form.value = emptyForm()
  anhaenge.value = []
  detail.value = { id: 0 } as Kontrolle
}

function closeDetail() {
  detail.value = null
  isNew.value = false
}

async function refreshDetail(pk: number) {
  await store.fetchKontrollen(projektName.value, jahr.value)
  const full = await store.fetchKontrolle(pk)
  if (full) {
    applyKontrolle(full)
    anhaenge.value = Array.isArray(full.anhaenge) ? full.anhaenge : []
  }
}

const flash = (text: string) => {
  message.value = text
  setTimeout(() => { if (message.value === text) message.value = '' }, 4000)
}

async function onSaveStamm() {
  if (!form.value.kontroll_id?.trim() || !form.value.titel?.trim()) {
    store.error = 'Kontroll-ID und Titel sind Pflicht.'
    return
  }
  busy.value = 'save'
  try {
    if (isNew.value) {
      const res = await store.createKontrolle(projektName.value, { ...form.value, jahr: jahr.value })
      if (res.ok) {
        flash('Kontrolle angelegt.')
        closeDetail()
        await store.fetchKontrollen(projektName.value, jahr.value)
      }
    } else {
      // Stammdaten-Update nur im Status „geplant" → erneut anlegen (Upsert per kontroll_id).
      const res = await store.createKontrolle(projektName.value, { ...form.value, jahr: jahr.value })
      if (res.ok) {
        flash('Gespeichert.')
        await store.fetchKontrollen(projektName.value, jahr.value)
      }
    }
  } finally { busy.value = '' }
}

async function onFreigeben() {
  if (!detail.value || !detail.value.id) return
  busy.value = 'freigeben'
  try {
    const k = await store.freigebenKontrolle(detail.value.id)
    if (k) { applyKontrolle(k); flash('Freigegeben.'); await store.fetchKontrollen(projektName.value, jahr.value) }
  } finally { busy.value = '' }
}

async function onDokumentieren() {
  if (!detail.value || !detail.value.id) return
  busy.value = 'doku'
  try {
    const k = await store.dokumentierenKontrolle(detail.value.id, { ...dokuForm.value })
    if (k) { applyKontrolle(k); flash('Durchführung gespeichert.'); await store.fetchKontrollen(projektName.value, jahr.value) }
  } finally { busy.value = '' }
}

async function onDelete() {
  if (!detail.value || !detail.value.id) return
  if (!confirm(`Kontrolle „${form.value.titel}" löschen?`)) return
  busy.value = 'delete'
  try {
    const ok = await store.deleteKontrolle(detail.value.id)
    if (ok) { flash('Gelöscht.'); closeDetail(); await store.fetchKontrollen(projektName.value, jahr.value) }
  } finally { busy.value = '' }
}

async function onSeed() {
  busy.value = 'seed'
  try {
    const n = await store.seedKontrollen(projektName.value, jahr.value)
    if (n !== null) {
      flash(`Standard-Kontrollen: ${n} angelegt.`)
      await store.fetchKontrollen(projektName.value, jahr.value)
    }
  } finally { busy.value = '' }
}

// ── Anhänge ─────────────────────────────────────────────────────────────
const fileInput = ref<HTMLInputElement | null>(null)
const pickedFile = ref<File | null>(null)

function onFilePicked(e: Event) {
  const files = (e.target as HTMLInputElement).files
  pickedFile.value = files && files.length ? files[0] : null
}

async function onUpload() {
  if (!detail.value || !detail.value.id || !pickedFile.value) return
  busy.value = 'upload'
  try {
    const ok = await store.uploadAnhang(detail.value.id, pickedFile.value)
    if (ok) {
      pickedFile.value = null
      if (fileInput.value) fileInput.value.value = ''
      anhaenge.value = await store.fetchAnhaenge(detail.value.id)
      flash('Anhang hochgeladen.')
    }
  } finally { busy.value = '' }
}

async function onDownloadAnhang(a: KontrolleAnhang) {
  await store.downloadAnhang(a.id, a.filename)
}

async function onDeleteAnhang(a: KontrolleAnhang) {
  const reason = prompt(`Anhang „${a.filename}" löschen — Begründung (min. 5 Zeichen):`, '')
  if (reason === null) return
  if (reason.trim().length < 5) { store.error = 'Begründung muss mindestens 5 Zeichen enthalten.'; return }
  const ok = await store.deleteAnhang(a.id, reason.trim())
  if (ok && detail.value?.id) {
    anhaenge.value = await store.fetchAnhaenge(detail.value.id)
    flash('Anhang gelöscht.')
  }
}
</script>

<style scoped>
.kontrollen-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.muted { color: #888; font-size: 12px; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.error-msg { background: #ffebee; color: #c62828; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }

.kp-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.jahr-label { font-size: 13px; color: #555; display: flex; align-items: center; gap: 6px; }
.jahr-select { padding: 6px 8px; border: 1px solid var(--color-border, #e0e0e0); border-radius: 4px; font-size: 13px; }

.kp-list { background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px; overflow: hidden; }
.kp-list table { width: 100%; border-collapse: collapse; font-size: 13px; }
.kp-list th { background: #f5f7fa; text-align: left; padding: 8px 12px; font-size: 11px; text-transform: uppercase; color: #888; border-bottom: 2px solid #e0e0e0; }
.kp-list td { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
.kp-row { cursor: pointer; }
.kp-row:hover { background: #f3f8ff; }
.title-cell { color: #222; }
.kid { font-size: 11px; color: #999; font-family: monospace; }
.bereich-tag { background: #e3f2fd; color: #1565c0; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.c-status { width: 150px; }
.c-anh { width: 70px; color: #666; }
.status-pill { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; }
.modal-status { margin-left: 8px; vertical-align: middle; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; border-radius: 8px; max-width: 720px; width: 95%; max-height: 90vh; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--color-border, #e0e0e0); }
.modal-header h3 { margin: 0; color: #1565c0; font-size: 16px; }
.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.modal-footer { display: flex; align-items: center; gap: 8px; padding: 12px 20px; border-top: 1px solid var(--color-border, #e0e0e0); }

.lock-note { background: #fff8e1; color: #e65100; border: 1px solid #ffe082; border-radius: 4px; padding: 8px 12px; font-size: 13px; margin: 0 0 12px; }

.section { border: 1px solid var(--color-border, #e0e0e0); border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; }
.section[disabled] { opacity: 0.65; }
.section legend { padding: 0 6px; font-weight: 600; font-size: 12px; color: #1565c0; text-transform: uppercase; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.form-cell { display: flex; flex-direction: column; gap: 4px; }
.form-cell.full { grid-column: 1 / -1; }
.form-cell.check-cell { padding-top: 4px; }
.form-cell label { font-size: 13px; font-weight: 600; color: #444; }
.form-cell label .req { color: #c62828; }
.form-cell input, .form-cell select, .form-cell textarea {
  padding: 7px 10px; border: 1px solid var(--color-border, #e0e0e0); border-radius: 4px; font-size: 13px; font: inherit;
}
.check-row { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500; cursor: pointer; }

.freigabe-row { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.freigabe-info { font-size: 12px; color: #2e7d32; }

.anh-upload { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.anh-list { list-style: none; margin: 0; padding: 0; }
.anh-list li { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.anh-name { flex: 1; color: #222; word-break: break-all; }
.anh-meta { font-size: 11px; color: #999; white-space: nowrap; }

.btn-primary, .btn-secondary, .btn-danger, .btn-approve { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-primary { background: #1565c0; color: white; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary.mini { padding: 6px 12px; font-size: 12px; }
.btn-danger { background: #c62828; color: white; }
.btn-approve { background: #2e7d32; color: white; }
.btn-primary:disabled, .btn-secondary:disabled, .btn-danger:disabled, .btn-approve:disabled { opacity: 0.55; cursor: not-allowed; }
.btn-tiny { background: none; border: 1px solid #ddd; padding: 2px 6px; border-radius: 3px; cursor: pointer; font-size: 13px; }
.btn-tiny.del:hover { background: #ffebee; }
</style>
