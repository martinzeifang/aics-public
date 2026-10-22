<template>
  <div class="inc-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein AI-Act-Projekt auswählen.</p>

    <template v-else>
      <div class="inc-toolbar">
        <div class="toolbar-info">
          <strong>🚨 Art. 73 — Serious-Incident-Register & Fristenuhr</strong>
          <span class="muted" v-if="store.summary">
            {{ store.summary.gesamt }} Vorfälle · {{ store.summary.offen }} offen ·
            <span :class="store.summary.ueberfaellig ? 'overdue-text' : ''">
              {{ store.summary.ueberfaellig }} überfällig
            </span>
          </span>
        </div>
        <button class="btn-secondary" @click="addRow">➕ Vorfall melden</button>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>
      <p class="muted">
        Meldefristen nach Art. 73: 2 Tage (weit verbreitet/KRITIS), 10 Tage (Todesfall),
        15 Tage (Regelfrist). Basis der Fristenuhr ist der Kenntnis-Zeitpunkt.
      </p>

      <section v-if="!rows.length" class="card">
        <p class="muted">Noch keine schwerwiegenden Vorfälle erfasst.</p>
      </section>

      <section v-for="(n, i) in rows" :key="n.id ?? ('new-' + i)" class="card"
               :class="ampelClass(n.ampel)">
        <div class="row between">
          <h4>
            <span class="ampel-dot" :class="ampelClass(n.ampel)"></span>
            {{ n.titel || 'Neuer Vorfall' }}
          </h4>
          <span class="pill" :class="'st-' + n.status">{{ n.status }}</span>
        </div>

        <div class="grid">
          <label>Titel<input v-model="n.titel" /></label>
          <label>Schweregrad
            <select v-model="n.schweregrad">
              <option v-for="s in store.schweregrade" :key="s.code" :value="s.code">
                {{ s.label }} ({{ s.frist_tage }} T.)
              </option>
            </select>
          </label>
          <label>Status
            <select v-model="n.status">
              <option v-for="s in statusWerte" :key="s" :value="s">{{ s }}</option>
            </select>
          </label>
          <label>Eintritts-Datum<input type="date" v-model="n.eintritts_datum" /></label>
          <label>Kenntnis-Datum<input type="date" v-model="n.kenntnis_datum" /></label>
          <label>Behörde<input v-model="n.behoerde" placeholder="Marktüberwachungsbehörde" /></label>
          <label>Erstbericht am<input type="date" v-model="n.erstbericht_am" /></label>
          <label>Vollbericht am<input type="date" v-model="n.vollbericht_am" /></label>
          <label>Abgeschlossen am<input type="date" v-model="n.abgeschlossen_am" /></label>
          <label>Einreichungsnachweis<input v-model="n.einreichungsnachweis" placeholder="Aktenzeichen/Beleg" /></label>
          <label>CAPA-Verweis<input v-model="n.capa_ref" /></label>
        </div>
        <label class="full">Beschreibung
          <textarea v-model="n.beschreibung" rows="2"></textarea>
        </label>

        <!-- Fristenuhr / Ampel / Countdown -->
        <div class="deadlines" v-if="n.deadlines">
          <h5>⏱️ Fristenuhr</h5>
          <div class="stage" v-for="st in n.deadlines.stages" :key="st.key">
            <span class="ampel-dot" :class="ampelClass(st.ampel)"></span>
            <span class="stage-label">{{ st.label }}</span>
            <span class="stage-due">
              <template v-if="st.status === 'no_base'">— (Kenntnis-Datum fehlt)</template>
              <template v-else-if="st.fulfilled">✅ gemeldet</template>
              <template v-else-if="st.status === 'overdue'" class="overdue-text">
                ⚠️ überfällig seit {{ fmtHours(st.hours_overdue) }}
              </template>
              <template v-else>noch {{ fmtHours(st.hours_left) }} (fällig {{ fmtDate(st.due_at) }})</template>
            </span>
          </div>
        </div>

        <label class="full" v-if="n.report_text">A23-Reporttext (gebunden)
          <textarea v-model="n.report_text" rows="3" readonly></textarea>
        </label>

        <div class="row">
          <button class="btn-primary" :disabled="busy !== ''" @click="save(n)">💾 Speichern</button>
          <button class="btn-small danger" v-if="n.id" :disabled="busy !== ''" @click="remove(n)">🗑️ Löschen</button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { useAiactIncidentsStore, type Incident } from '../../stores/aiactIncidents'

const aiact = useAiActStore()
const store = useAiactIncidentsStore()

const projekt = computed(() => aiact.selectedProjekt)
const busy = ref('')
const message = ref('')
const rows = ref<Incident[]>([])

const statusWerte = computed(() => store.statusWerte.length ? store.statusWerte
  : ['offen', 'erstbericht', 'vollbericht', 'abgeschlossen'])

function emptyRow(): Incident {
  return reactive({
    titel: '', beschreibung: '', eintritts_datum: '', kenntnis_datum: '',
    schweregrad: 'standard', status: 'offen', behoerde: '', erstbericht_am: '',
    vollbericht_am: '', abgeschlossen_am: '', einreichungsnachweis: '', capa_ref: '',
  })
}

function ampelClass(a?: string): string {
  return ({ red: 'ampel-red', amber: 'ampel-amber', green: 'ampel-green', grey: 'ampel-grey' } as Record<string, string>)[a || ''] || 'ampel-grey'
}

function fmtHours(h?: number | null): string {
  if (h == null) return '—'
  if (h >= 24) return `${Math.floor(h / 24)} T ${Math.round(h % 24)} h`
  return `${Math.round(h)} h`
}
function fmtDate(d?: string): string {
  if (!d) return '—'
  return d.slice(0, 10)
}

async function load() {
  if (!projekt.value) return
  await store.loadConstants()
  await store.load(projekt.value)
  rows.value = store.items.map(n => reactive({ ...n }))
}

function addRow() { rows.value.unshift(emptyRow()) }

async function save(n: Incident) {
  if (!projekt.value) return
  busy.value = 'save'
  try {
    if (n.id) await store.update(projekt.value, n.id, n)
    else await store.create(projekt.value, n)
    rows.value = store.items.map(x => reactive({ ...x }))
    message.value = 'Vorfall gespeichert.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally { busy.value = '' }
}

async function remove(n: Incident) {
  if (!projekt.value || !n.id) return
  if (!confirm('Vorfall löschen?')) return
  busy.value = 'del'
  try {
    await store.remove(projekt.value, n.id)
    rows.value = store.items.map(x => reactive({ ...x }))
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
  } finally { busy.value = '' }
}

watch(projekt, load, { immediate: true })
</script>

<style scoped>
.inc-panel { padding: 8px 0; }
.hint { color: #607d8b; padding: 16px; }
.inc-toolbar { background: #1565c0; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
.toolbar-info strong { color: #fff; }
.toolbar-info .muted { color: #90caf9; margin-left: 12px; }
.overdue-text { color: #ffcdd2; font-weight: 600; }
.status-msg { color: #1565c0; margin: 8px 0; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #cfd8dc; }
.card.ampel-red { border-left-color: #c62828; }
.card.ampel-amber { border-left-color: #f9a825; }
.card.ampel-green { border-left-color: #2e7d32; }
.card h4 { margin: 0 0 8px; color: #0d47a1; }
.card h5 { margin: 8px 0 4px; color: #455a64; }
.row { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
.row.between { justify-content: space-between; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 8px 0; }
label { display: flex; flex-direction: column; font-size: 0.82em; color: #455a64; gap: 3px; }
label.full { grid-column: 1 / -1; }
input, select, textarea { box-sizing: border-box; width: 100%; padding: 4px 6px; }
.muted { color: #78909c; font-size: 0.85em; }
.pill { padding: 2px 8px; border-radius: 10px; font-size: 0.8em; background: #eceff1; }
.st-offen { background: #fff3e0; }
.st-erstbericht { background: #e3f2fd; }
.st-vollbericht { background: #e8eaf6; }
.st-abgeschlossen { background: #e8f5e9; }
.deadlines { background: #fafafa; border: 1px solid #eee; border-radius: 6px; padding: 8px 12px; margin: 8px 0; }
.stage { display: flex; gap: 8px; align-items: center; font-size: 0.85em; padding: 2px 0; }
.stage-label { flex: 0 0 280px; }
.ampel-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; background: #b0bec5; }
.ampel-dot.ampel-red { background: #c62828; }
.ampel-dot.ampel-amber { background: #f9a825; }
.ampel-dot.ampel-green { background: #2e7d32; }
.ampel-dot.ampel-grey { background: #b0bec5; }
.btn-small.danger { color: #c62828; }
</style>
