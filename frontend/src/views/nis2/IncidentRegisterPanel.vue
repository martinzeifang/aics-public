<template>
  <div class="incident-register">
    <div class="intro-banner">
      <strong>{{ $t('nis2.incidentRegisterPanel.vorfallRegisterArtNIS2') }}</strong>
      <p class="hint">{{ $t('nis2.incidentRegisterPanel.erheblicheSicherheitsvorfalleMitDemG') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>

    <template v-else>
      <div class="toolbar">
        <button class="btn-primary" @click="openNew">{{ $t('nis2.incidentRegisterPanel.neuerVorfall') }}</button>
        <span v-if="store.loading" class="hint">{{ $t('common.loading') }}</span>
      </div>

      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <div v-if="store.incidents.length === 0 && !store.loading" class="hint">
        {{ $t('nis2.incidentRegisterPanel.nochKeineVorfalleErfasst') }}
      </div>

      <div v-for="inc in store.incidents" :key="inc.id" class="incident-card">
        <div class="incident-head">
          <span class="ampel" :class="'ampel-' + inc.deadlines.overall_ampel" :title="inc.deadlines.overall_ampel"></span>
          <span class="inc-id">{{ inc.incident_id }}</span>
          <span class="inc-titel">{{ inc.titel }}</span>
          <span class="inc-schwere" :class="'schwere-' + inc.schweregrad">{{ inc.schweregrad }}</span>
          <span class="inc-status">{{ inc.status }}</span>
          <span class="spacer"></span>
          <button class="btn-secondary" @click="openEdit(inc)">{{ $t('nis2.incidentRegisterPanel.bearbeiten') }}</button>
          <button class="btn-secondary danger" @click="remove(inc)">🗑️</button>
        </div>
        <div class="inc-meta">
          {{ $t('nis2.incidentRegisterPanel.kenntnisV0', { v0: inc.kenntnis_zeitpunkt || '—' }) }}
          <span v-if="inc.grenzueberschreitend"> {{ $t('nis2.incidentRegisterPanel.grenzuberschreitend') }}</span>
          <span v-if="inc.betroffene_assets"> {{ $t('nis2.incidentRegisterPanel.assetsV0', { v0: inc.betroffene_assets }) }}</span>
        </div>

        <table class="stufen">
          <thead>
            <tr><th>{{ $t('common.stufe') }}</th><th>{{ $t('common.frist') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('nis2.incidentRegisterPanel.restzeit') }}</th><th>{{ $t('nis2.incidentRegisterPanel.aktion') }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="st in inc.deadlines.stages" :key="st.key">
              <td>{{ st.label }}</td>
              <td>{{ fmtDate(st.due_at) }}</td>
              <td>
                <span class="ampel small" :class="'ampel-' + st.ampel"></span>
                {{ statusLabel(st) }}
              </td>
              <td>{{ restzeit(st) }}</td>
              <td>
                <button class="btn-link" @click="openMeldung(inc, stageTyp(st.key))">
                  {{ hasMeldung(inc, stageTyp(st.key)) ? $t('nis2.incidentRegisterPanel.meldungAnzeigen') : $t('nis2.incidentRegisterPanel.meldungErfassen') }}
                </button>
                <button
                  v-if="meldungOf(inc, stageTyp(st.key))"
                  class="btn-link"
                  @click="doExport(inc, stageTyp(st.key))"
                >{{ $t('nis2.incidentRegisterPanel.export') }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Modal: Vorfall -->
    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <div class="modal">
        <h3>{{ form.id ? $t('nis2.incidentRegisterPanel.vorfallBearbeiten') : $t('nis2.incidentRegisterPanel.neuerVorfall2') }}</h3>
        <label>{{ $t('nis2.incidentRegisterPanel.vorfallID') }}
          <input v-model="form.incident_id" :disabled="!!form.id" placeholder="NIS2-INC-2026-001" />
        </label>
        <label>{{ $t('common.titel') }} <input v-model="form.titel" /></label>
        <label>{{ $t('nis2.incidentRegisterPanel.kenntniserlangungZeitpunkt') }}
          <input v-model="form.kenntnis_zeitpunkt" type="datetime-local" />
        </label>
        <label>{{ $t('common.schweregrad') }}
          <select v-model="form.schweregrad">
            <option v-for="s in store.constants?.schweregrade || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>{{ $t('common.status') }}
          <select v-model="form.status">
            <option v-for="s in store.constants?.incident_status || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>{{ $t('nis2.incidentRegisterPanel.betroffeneAssets') }} <input v-model="form.betroffene_assets" /></label>
        <label>{{ $t('nis2.incidentRegisterPanel.grundursacheRootCause') }} <textarea v-model="form.root_cause" rows="2" /></label>
        <label class="cb"><input type="checkbox" v-model="form.grenzueberschreitend" /> {{ $t('nis2.incidentRegisterPanel.grenzuberschreitend2') }}</label>
        <label class="cb"><input type="checkbox" v-model="form.erheblich" /> {{ $t('nis2.incidentRegisterPanel.erheblichMeldepflichtig') }}</label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showForm = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="submitForm">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>

    <!-- Modal: Meldung -->
    <div v-if="showMeldung" class="modal-backdrop" @click.self="showMeldung = false">
      <div class="modal">
        <h3>{{ $t('nis2.incidentRegisterPanel.meldeStufeV0', { v0: meldungForm.typ }) }}</h3>
        <label>{{ $t('common.status') }}
          <select v-model="meldungForm.status">
            <option v-for="s in store.constants?.meldung_status || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>{{ $t('nis2.incidentRegisterPanel.ubermitteltAm') }} <input v-model="meldungForm.ist_zeitpunkt" type="datetime-local" /></label>
        <label>{{ $t('nis2.incidentRegisterPanel.bSIReferenz') }} <input v-model="meldungForm.bsi_referenz" /></label>
        <label>{{ $t('nis2.incidentRegisterPanel.meldetext') }} <textarea v-model="meldungForm.text" rows="6" /></label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showMeldung = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="submitMeldung">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useNis2IncidentsStore, type Incident, type DeadlineStage } from '../../stores/nis2Incidents'
import { t } from '../../i18n'

const props = defineProps<{ projektName: string | null }>()
const store = useNis2IncidentsStore()

const TYP_BY_KEY: Record<string, string> = {
  fruehwarnung: '24h', meldung: '72h', abschlussbericht: '1M',
}

const showForm = ref(false)
const showMeldung = ref(false)
const form = ref<any>({})
const meldungForm = ref<any>({})
const activeInc = ref<Incident | null>(null)

const reload = async () => {
  if (props.projektName) await store.fetchIncidents(props.projektName)
}

onMounted(async () => {
  await store.fetchConstants()
  await reload()
})
watch(() => props.projektName, reload)

const stageTyp = (key: string) => TYP_BY_KEY[key] || key
const meldungOf = (inc: Incident, typ: string) =>
  inc.meldungen.find((m) => m.typ === typ) || null
const hasMeldung = (inc: Incident, typ: string) => !!meldungOf(inc, typ)

const fmtDate = (s: string) => (s ? new Date(s).toLocaleString('de-DE') : '—')
const statusLabel = (st: DeadlineStage) => {
  if (st.fulfilled) return t('nis2.incidentRegisterPanel.ubermittelt')
  if (st.status === 'overdue') return t('common.uberfallig')
  if (st.status === 'due_soon') return t('nis2.incidentRegisterPanel.baldFallig')
  if (st.status === 'no_base') return '—'
  return 'offen'
}
const restzeit = (st: DeadlineStage) => {
  if (st.fulfilled) return '✓'
  if (st.hours_overdue != null) return `−${Math.round(st.hours_overdue)} h`
  if (st.hours_left != null) return `${Math.round(st.hours_left)} h`
  return '—'
}

const openNew = () => {
  form.value = {
    incident_id: '', titel: '', kenntnis_zeitpunkt: '', schweregrad: 'mittel',
    status: 'offen', betroffene_assets: '', root_cause: '',
    grenzueberschreitend: false, erheblich: true,
  }
  showForm.value = true
}
const openEdit = (inc: Incident) => {
  form.value = {
    id: inc.id, incident_id: inc.incident_id, titel: inc.titel,
    kenntnis_zeitpunkt: inc.kenntnis_zeitpunkt, schweregrad: inc.schweregrad,
    status: inc.status, betroffene_assets: inc.betroffene_assets,
    root_cause: inc.root_cause, grenzueberschreitend: !!inc.grenzueberschreitend,
    erheblich: !!inc.erheblich,
  }
  showForm.value = true
}
const submitForm = async () => {
  if (!props.projektName || !form.value.incident_id) return
  const ok = await store.saveIncident(props.projektName, form.value)
  if (ok) { showForm.value = false; await reload() }
}
const remove = async (inc: Incident) => {
  if (!props.projektName) return
  if (!confirm(`Vorfall ${inc.incident_id} löschen?`)) return
  if (await store.deleteIncident(props.projektName, inc.id)) await reload()
}

const openMeldung = (inc: Incident, typ: string) => {
  activeInc.value = inc
  const m = meldungOf(inc, typ)
  meldungForm.value = {
    typ, status: m?.status || 'offen', ist_zeitpunkt: m?.ist_zeitpunkt || '',
    bsi_referenz: m?.bsi_referenz || '', text: m?.text || '',
  }
  showMeldung.value = true
}
const submitMeldung = async () => {
  if (!props.projektName || !activeInc.value) return
  const ok = await store.saveMeldung(props.projektName, activeInc.value.id, meldungForm.value)
  if (ok) { showMeldung.value = false; await reload() }
}
const doExport = async (inc: Incident, typ: string) => {
  if (!props.projektName) return
  const m = meldungOf(inc, typ)
  if (!m) return
  await store.exportMeldung(props.projektName, inc.id, m.id, inc.incident_id, typ)
}
</script>

<style scoped>
.incident-register { padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }
.intro-banner strong { color: #1565c0; }
.hint { color: #607d8b; font-size: 0.9em; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.incident-card { border: 1px solid #cfd8dc; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; background: #fff; }
.incident-head { display: flex; align-items: center; gap: 10px; }
.inc-id { font-family: Consolas, monospace; font-weight: 600; color: #1565c0; }
.inc-titel { font-weight: 600; }
.inc-schwere { font-size: 0.8em; padding: 2px 8px; border-radius: 10px; background: #eceff1; }
.schwere-hoch { background: #ffe0b2; }
.schwere-kritisch { background: #ffcdd2; }
.inc-status { font-size: 0.85em; color: #607d8b; }
.spacer { flex: 1; }
.inc-meta { color: #607d8b; font-size: 0.85em; margin: 6px 0 10px; }
.stufen { width: 100%; border-collapse: collapse; font-size: 0.9em; }
.stufen th, .stufen td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eceff1; }
.ampel { width: 12px; height: 12px; border-radius: 50%; display: inline-block; background: #bdbdbd; }
.ampel.small { width: 10px; height: 10px; }
.ampel-green { background: #43a047; }
.ampel-amber { background: #fb8c00; }
.ampel-red { background: #e53935; }
.ampel-grey { background: #bdbdbd; }
.btn-primary { background: #1565c0; color: #fff; border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer; }
.btn-secondary { background: #eceff1; border: 1px solid #cfd8dc; padding: 6px 12px; border-radius: 6px; cursor: pointer; }
.btn-secondary.danger { color: #c62828; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 0 6px; }
.msg.err { color: #c62828; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 8px; padding: 20px 24px; width: 520px; max-width: 92vw; max-height: 88vh; overflow: auto; }
.modal h3 { color: #1565c0; margin-top: 0; }
.modal label { display: block; margin: 10px 0; font-size: 0.9em; }
.modal label.cb { display: flex; gap: 8px; align-items: center; }
.modal input, .modal select, .modal textarea { width: 100%; padding: 6px 8px; border: 1px solid #cfd8dc; border-radius: 4px; margin-top: 4px; box-sizing: border-box; }
.modal label.cb input { width: auto; margin-top: 0; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
</style>
