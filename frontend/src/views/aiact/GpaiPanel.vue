<template>
  <div class="gpai-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein AI-Act-Projekt auswählen.</p>

    <template v-else-if="k">
      <div class="gpai-toolbar">
        <div class="toolbar-info">
          <strong>🧠 Art. 51-55 — GPAI-Modell (General-Purpose AI)</strong>
          <span class="muted" v-if="store.summary">
            {{ store.summary.ist_gpai ? 'GPAI' : 'kein GPAI' }} ·
            {{ store.summary.systemisch ? 'systemisches Risiko' : 'kein systemisches Risiko' }} ·
            {{ store.summary.checks_erfuellt }}/{{ store.summary.checks_gesamt }} Pflichten erfüllt
          </span>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>

      <!-- Klassifizierung -->
      <section class="card">
        <h4>Klassifizierung (Art. 51)</h4>
        <label class="check"><input type="checkbox" v-model="k.ist_gpai" /> Ist ein GPAI-Modell</label>
        <div class="grid">
          <label>Trainings-Rechenleistung (FLOP)
            <input type="number" step="any" v-model.number="k.training_flop" placeholder="z.B. 1e25" />
          </label>
          <label>Systemisch-Override
            <select v-model="k.systemisch_override">
              <option value="">automatisch (FLOP-Schwellenwert)</option>
              <option value="ja">systemisch (manuell)</option>
              <option value="nein">nicht systemisch (manuell)</option>
            </select>
          </label>
        </div>
        <div class="threshold" :class="k.systemisch ? 'thr-on' : 'thr-off'">
          Schwellenwert 10^25 FLOP {{ k.ueber_schwellenwert ? '⚠️ überschritten' : 'nicht überschritten' }}
          → {{ k.systemisch ? '🔴 systemisches Risiko (Art. 55 gilt)' : '⚪ kein systemisches Risiko' }}
        </div>

        <!-- 2-Wochen-Notifikationsfrist (Art. 52) -->
        <div class="deadline" v-if="k.systemisch && k.notifikation_deadline">
          <h5>⏱️ Kommissions-Notifikation (Art. 52 — 2 Wochen)</h5>
          <div class="grid">
            <label>Schwellenwert erreicht am<input type="date" v-model="k.schwellwert_erreicht_am" /></label>
            <label>Notifikation Kommission am<input type="date" v-model="k.notifikation_kommission_am" /></label>
          </div>
          <p class="ampel" :class="'a-' + (k.notifikation_deadline.overall_ampel || 'grey')">
            <template v-if="k.notifikation_deadline.next_due?.fulfilled">✅ notifiziert</template>
            <template v-else-if="k.notifikation_deadline.any_overdue">⚠️ Notifikationsfrist überschritten</template>
            <template v-else-if="k.notifikation_deadline.next_due">
              Fällig: {{ (k.notifikation_deadline.next_due.due_at || '').slice(0, 10) }}
            </template>
            <template v-else>Schwellenwert-/Kenntnisdatum erfassen</template>
          </p>
        </div>
      </section>

      <!-- Annex XI/XII Doku + Policy + Summary -->
      <section class="card">
        <h4>Dokumentation & Policies</h4>
        <label class="full">Urheberrechts-/TDM-Opt-out-Policy (Art. 53(1)c)
          <textarea v-model="k.copyright_tdm_policy" rows="2"></textarea>
        </label>
        <label class="full">Öffentliche Trainingsdaten-Zusammenfassung (Art. 53(1)d)
          <textarea v-model="k.trainingsdaten_summary" rows="2"></textarea>
        </label>
        <button class="btn-primary" :disabled="busy" @click="saveKlass">💾 Klassifizierung speichern</button>
      </section>

      <!-- Pflicht-Register -->
      <section class="card">
        <h4>GPAI-Pflicht-Register</h4>
        <table class="gpai-table">
          <thead>
            <tr><th>ID</th><th>Pflicht</th><th>Ref</th><th>Status</th><th>Kommentar</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="c in checks" :key="c.id" :class="{ 'sys-only': c.systemic_only }">
              <td>{{ c.id }}</td>
              <td>{{ c.titel }}<div class="hint-sm">{{ c.hinweis }}</div></td>
              <td>{{ c.ref }}</td>
              <td>
                <select v-model.number="c.status">
                  <option v-for="s in [0,1,2,3,4,5]" :key="s" :value="s">{{ s }}</option>
                </select>
              </td>
              <td><input v-model="c.kommentar" /></td>
              <td><button class="btn-small" :disabled="busy" @click="saveCheck(c)">💾</button></td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- AI-Office-Incident-Tracking (nur systemisch) -->
      <section class="card" v-if="k.systemisch">
        <div class="row between">
          <h4>AI-Office-Incident-Tracking (Art. 55(1)c)</h4>
          <button class="btn-secondary" @click="addIncident">➕ Incident</button>
        </div>
        <table class="gpai-table" v-if="incidentRows.length">
          <thead>
            <tr><th>Titel</th><th>Eingetreten</th><th>Gemeldet AI-Office</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(inc, i) in incidentRows" :key="inc.id ?? ('new-' + i)">
              <td><input v-model="inc.titel" /></td>
              <td><input type="date" v-model="inc.eingetreten_am" /></td>
              <td><input type="date" v-model="inc.gemeldet_ai_office_am" /></td>
              <td>
                <select v-model="inc.status">
                  <option v-for="s in incStatus" :key="s" :value="s">{{ s }}</option>
                </select>
              </td>
              <td>
                <button class="btn-small" v-if="!inc.id" @click="saveIncident(inc)">💾</button>
                <button class="btn-small danger" v-else @click="removeIncident(inc)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">Noch keine AI-Office-Incidents erfasst.</p>
      </section>

      <!-- KI-Wizard -->
      <section class="card">
        <h4>🤖 KI-Assistent</h4>
        <div class="row"><button class="btn-secondary" @click="copyPrompt">📋 Prompt kopieren</button></div>
        <textarea v-model="wizardResponse" rows="3" placeholder="KI-Antwort (JSON)…"></textarea>
        <button class="btn-primary" :disabled="!wizardResponse" @click="applyWizard">✨ Übernehmen</button>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { useAiactGpaiStore, type GpaiKlassifizierung, type GpaiCheck, type GpaiIncident } from '../../stores/aiactGpai'

const aiact = useAiActStore()
const store = useAiactGpaiStore()

const projekt = computed(() => aiact.selectedProjekt)
const k = ref<GpaiKlassifizierung | null>(null)
const checks = ref<GpaiCheck[]>([])
const incidentRows = ref<GpaiIncident[]>([])
const busy = ref(false)
const message = ref('')
const wizardResponse = ref('')

const incStatus = computed(() => store.incidentStatus.length ? store.incidentStatus
  : ['offen', 'gemeldet', 'abgeschlossen'])

async function load() {
  if (!projekt.value) return
  await store.loadRequirements()
  await store.load(projekt.value)
  k.value = store.klass ? { ...store.klass } : null
  checks.value = store.checks.map(c => ({ ...c }))
  incidentRows.value = store.incidents.map(i => ({ ...i }))
}

async function saveKlass() {
  if (!projekt.value || !k.value) return
  busy.value = true
  try {
    await store.saveKlass(projekt.value, k.value)
    k.value = store.klass ? { ...store.klass } : k.value
    checks.value = store.checks.map(c => ({ ...c }))
    message.value = 'Klassifizierung gespeichert.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally { busy.value = false }
}

async function saveCheck(c: GpaiCheck) {
  if (!projekt.value) return
  busy.value = true
  try {
    await store.saveCheck(projekt.value, c)
    checks.value = store.checks.map(x => ({ ...x }))
    message.value = 'Pflicht gespeichert.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally { busy.value = false }
}

function addIncident() {
  incidentRows.value.push({ titel: '', beschreibung: '', eingetreten_am: '', gemeldet_ai_office_am: '', status: 'offen' })
}
async function saveIncident(inc: GpaiIncident) {
  if (!projekt.value) return
  await store.createIncident(projekt.value, inc)
  incidentRows.value = store.incidents.map(i => ({ ...i }))
}
async function removeIncident(inc: GpaiIncident) {
  if (!projekt.value || !inc.id) return
  if (!confirm('Incident löschen?')) return
  await store.deleteIncident(projekt.value, inc.id)
  incidentRows.value = store.incidents.map(i => ({ ...i }))
}

async function copyPrompt() {
  if (!projekt.value) return
  const p = await store.wizardPrompt(projekt.value)
  try { await navigator.clipboard.writeText(p); message.value = 'Prompt kopiert.' } catch { /* ignore */ }
}
async function applyWizard() {
  if (!projekt.value) return
  try {
    await store.wizardParse(projekt.value, wizardResponse.value)
    k.value = store.klass ? { ...store.klass } : k.value
    checks.value = store.checks.map(c => ({ ...c }))
    wizardResponse.value = ''
    message.value = 'KI-Vorbefüllung übernommen.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Übernahme fehlgeschlagen.'
  }
}

watch(projekt, load, { immediate: true })
</script>

<style scoped>
.gpai-panel { padding: 8px 0; }
.hint { color: #607d8b; padding: 16px; }
.gpai-toolbar { background: #1565c0; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }
.toolbar-info strong { color: #fff; }
.toolbar-info .muted { color: #90caf9; margin-left: 12px; }
.status-msg { color: #1565c0; margin: 8px 0; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.card h4 { margin: 0 0 8px; color: #0d47a1; }
.card h5 { margin: 8px 0 4px; color: #455a64; }
label { display: flex; flex-direction: column; font-size: 0.85em; color: #455a64; gap: 3px; }
label.full { width: 100%; margin-bottom: 8px; }
label.check { flex-direction: row; align-items: center; gap: 8px; margin: 6px 0; }
.grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 8px 0; }
input, select, textarea { box-sizing: border-box; width: 100%; padding: 4px 6px; }
.threshold { padding: 8px 12px; border-radius: 6px; margin: 8px 0; font-size: 0.9em; }
.thr-on { background: #ffebee; }
.thr-off { background: #eceff1; }
.deadline { background: #fafafa; border: 1px solid #eee; border-radius: 6px; padding: 8px 12px; margin-top: 8px; }
.ampel { font-weight: 600; padding: 4px 0; }
.a-red { color: #c62828; }
.a-amber { color: #f9a825; }
.a-green { color: #2e7d32; }
.a-grey { color: #78909c; }
.gpai-table { width: 100%; border-collapse: collapse; font-size: 0.88em; }
.gpai-table th, .gpai-table td { padding: 6px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; }
.gpai-table th { background: #e3f2fd; color: #0d47a1; }
.sys-only { background: #fff8e1; }
.hint-sm { color: #90a4ae; font-size: 0.85em; }
.row { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
.row.between { justify-content: space-between; }
.muted { color: #78909c; font-size: 0.85em; }
.danger { color: #c62828; }
</style>
