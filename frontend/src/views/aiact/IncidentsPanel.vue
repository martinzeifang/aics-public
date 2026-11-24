<template>
  <div class="inc-panel">
    <p v-if="!projekt" class="hint">{{ $t('common.bitteZuerstEinAIActProjektAu') }}</p>

    <template v-else>
      <div class="inc-toolbar">
        <div class="toolbar-info">
          <strong>{{ $t('aiact.incidentsPanel.artSeriousIncidentRegisterFristenuhr') }}</strong>
          <span class="muted" v-if="store.summary">
            {{ $t('aiact.incidentsPanel.v0VorfalleV1Offen', { v0: store.summary.gesamt, v1: store.summary.offen }) }}
            <span :class="store.summary.ueberfaellig ? 'overdue-text' : ''">
              {{ $t('aiact.incidentsPanel.v0Uberfallig', { v0: store.summary.ueberfaellig }) }}
            </span>
          </span>
        </div>
        <button class="btn-secondary" @click="addRow">{{ $t('aiact.incidentsPanel.vorfallMelden') }}</button>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>
      <p class="muted">
        {{ $t('aiact.incidentsPanel.meldefristenNachArtTageWeitVerbreite') }}
      </p>

      <section v-if="!rows.length" class="card">
        <p class="muted">{{ $t('aiact.incidentsPanel.nochKeineSchwerwiegendenVorfalleErfa') }}</p>
      </section>

      <section v-for="(n, i) in rows" :key="n.id ?? ('new-' + i)" class="card"
               :class="ampelClass(n.ampel)">
        <div class="row between">
          <h4>
            <span class="ampel-dot" :class="ampelClass(n.ampel)"></span>
            {{ n.titel || $t('aiact.incidentsPanel.neuerVorfall') }}
          </h4>
          <span class="pill" :class="'st-' + n.status">{{ n.status }}</span>
        </div>

        <div class="grid">
          <label>{{ $t('common.titel') }}<input v-model="n.titel" /></label>
          <label>{{ $t('common.schweregrad') }}
            <select v-model="n.schweregrad">
              <option v-for="s in store.schweregrade" :key="s.code" :value="s.code">
                {{ s.label }} ({{ s.frist_tage }} T.)
              </option>
            </select>
          </label>
          <label>{{ $t('common.status') }}
            <select v-model="n.status">
              <option v-for="s in statusWerte" :key="s" :value="s">{{ s }}</option>
            </select>
          </label>
          <label>{{ $t('aiact.incidentsPanel.eintrittsDatum') }}<input type="date" v-model="n.eintritts_datum" /></label>
          <label>{{ $t('aiact.incidentsPanel.kenntnisDatum') }}<input type="date" v-model="n.kenntnis_datum" /></label>
          <label>{{ $t('common.behorde') }}<input v-model="n.behoerde" :placeholder="$t('aiact.incidentsPanel.marktuberwachungsbehorde')" /></label>
          <label>{{ $t('aiact.incidentsPanel.erstberichtAm') }}<input type="date" v-model="n.erstbericht_am" /></label>
          <label>{{ $t('aiact.incidentsPanel.vollberichtAm') }}<input type="date" v-model="n.vollbericht_am" /></label>
          <label>{{ $t('aiact.incidentsPanel.abgeschlossenAm') }}<input type="date" v-model="n.abgeschlossen_am" /></label>
          <label>{{ $t('aiact.incidentsPanel.einreichungsnachweis') }}<input v-model="n.einreichungsnachweis" placeholder="Aktenzeichen/Beleg" /></label>
          <label>{{ $t('aiact.incidentsPanel.cAPAVerweis') }}<input v-model="n.capa_ref" /></label>
        </div>
        <label class="full">{{ $t('common.description') }}
          <textarea v-model="n.beschreibung" rows="2"></textarea>
        </label>

        <!-- Fristenuhr / Ampel / Countdown -->
        <div class="deadlines" v-if="n.deadlines">
          <h5>{{ $t('aiact.incidentsPanel.fristenuhr') }}</h5>
          <div class="stage" v-for="st in n.deadlines.stages" :key="st.key">
            <span class="ampel-dot" :class="ampelClass(st.ampel)"></span>
            <span class="stage-label">{{ st.label }}</span>
            <span class="stage-due">
              <template v-if="st.status === 'no_base'">{{ $t('aiact.incidentsPanel.kenntnisDatumFehlt') }}</template>
              <template v-else-if="st.fulfilled">{{ $t('aiact.incidentsPanel.gemeldet') }}</template>
              <template v-else-if="st.status === 'overdue'" class="overdue-text">
                {{ $t('aiact.incidentsPanel.uberfalligSeitV0', { v0: fmtHours(st.hours_overdue) }) }}
              </template>
              <template v-else>{{ $t('aiact.incidentsPanel.nochV0FalligV1', { v0: fmtHours(st.hours_left), v1: fmtDate(st.due_at) }) }}</template>
            </span>
          </div>
        </div>

        <label class="full" v-if="n.report_text">{{ $t('aiact.incidentsPanel.a23ReporttextGebunden') }}
          <textarea v-model="n.report_text" rows="3" readonly></textarea>
        </label>

        <div class="row">
          <button class="btn-primary" :disabled="busy !== ''" @click="save(n)">{{ $t('common.saveIcon') }}</button>
          <button class="btn-small danger" v-if="n.id" :disabled="busy !== ''" @click="remove(n)">{{ $t('common.loschen') }}</button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { useAiactIncidentsStore, type Incident } from '../../stores/aiactIncidents'
import { t } from '../../i18n'

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
    message.value = t('aiact.incidentsPanel.vorfallGespeichert')
  } catch (e: any) {
    message.value = e?.response?.data?.error || t('common.speichernFehlgeschlagen')
  } finally { busy.value = '' }
}

async function remove(n: Incident) {
  if (!projekt.value || !n.id) return
  if (!confirm(t('aiact.incidentsPanel.vorfallLoschen'))) return
  busy.value = 'del'
  try {
    await store.remove(projekt.value, n.id)
    rows.value = store.items.map(x => reactive({ ...x }))
  } catch (e: any) {
    message.value = e?.response?.data?.error || t('common.loeschenFehlgeschlagen')
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
