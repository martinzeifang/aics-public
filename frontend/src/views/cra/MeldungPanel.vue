<template>
  <div class="meldung-panel">
    <div class="panel-header">
      <h3>🚨 Art. 14 — Melde-Workflow</h3>
      <p class="sub">Aktiv ausgenutzte Schwachstellen + schwerwiegende Vorfälle ·
        Frühwarnung 24h → Meldung 72h → Abschluss 14d/1M (ENISA SRP)</p>
    </div>

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <button class="btn-primary" @click="showForm = !showForm">+ Neue Meldung</button>

    <div v-if="showForm" class="form-card">
      <div class="form-row">
        <label>Typ</label>
        <select v-model="form.typ">
          <option value="vuln_exploited">Aktiv ausgenutzte Schwachstelle (Abschluss 14d)</option>
          <option value="serious_incident">Schwerwiegender Vorfall (Abschluss 1 Monat)</option>
        </select>
      </div>
      <div class="form-row">
        <label>Titel</label>
        <input v-model="form.titel" placeholder="Kurzbeschreibung" />
      </div>
      <div class="form-row">
        <label>Erkannt am</label>
        <input v-model="form.erkannt_am" type="datetime-local" />
      </div>
      <div class="form-row">
        <label>Betroffene Mitgliedstaaten</label>
        <input v-model="form.betroffene_ms" placeholder="z.B. DE, FR" />
      </div>
      <button class="btn-primary" @click="create">Speichern</button>
      <button class="btn-secondary" @click="showForm = false">Abbrechen</button>
    </div>

    <table v-if="store.meldungen.length" class="meldung-table">
      <thead>
        <tr>
          <th>Titel</th><th>Typ</th><th>Status</th><th>Fristen-Ampel</th><th>Aktionen</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in store.meldungen" :key="m.id">
          <td>{{ m.titel }}</td>
          <td>{{ m.typ === 'serious_incident' ? 'Vorfall' : 'Schwachstelle' }}</td>
          <td>{{ statusLabel(m.status) }}</td>
          <td>
            <span v-for="s in m.deadlines?.stages || []" :key="s.key"
                  class="ampel" :class="'ampel-' + s.ampel" :title="ampelTitle(s)">
              {{ s.label }}
            </span>
          </td>
          <td>
            <select :value="m.status" @change="onStufe(m, $event)">
              <option v-for="s in store.status" :key="s" :value="s">{{ statusLabel(s) }}</option>
            </select>
            <a class="btn-link" :href="safeUrl(store.exportUrl(projekt, m.id))" target="_blank">SRP-Export</a>
            <button class="btn-link" @click="openAdvisory(m)">Advisory</button>
            <button class="btn-link danger" @click="store.deleteMeldung(projekt, m.id)">🗑</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">Noch keine Meldungen erfasst.</p>

    <div v-if="advisoryFor" class="form-card advisory">
      <h4>Nutzer-Advisory (Art. 14(8)) — {{ advisoryFor.titel }}</h4>
      <div class="form-row">
        <label>Empfohlene Maßnahmen</label>
        <textarea v-model="advisoryForm.empfohlene_massnahmen"></textarea>
      </div>
      <div class="form-row">
        <label>Schweregrad</label>
        <input v-model="advisoryForm.schweregrad" />
      </div>
      <div class="form-row">
        <label>Veröffentlichungskanal</label>
        <input v-model="advisoryForm.veroeffentlichungskanal" />
      </div>
      <button class="btn-primary" @click="saveAdvisory">Speichern</button>
      <button class="btn-secondary" @click="advisoryFor = null">Schließen</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useCraMeldungStore, type Meldung, type MeldungDeadlineStage } from '../../stores/craMeldung'
import { safeUrl } from '../../utils/safeUrl'

const props = defineProps<{ projekt: string }>()
const store = useCraMeldungStore()

const showForm = ref(false)
const form = ref({ typ: 'vuln_exploited', titel: '', erkannt_am: '', betroffene_ms: '' })
const advisoryFor = ref<Meldung | null>(null)
const advisoryForm = ref<Record<string, any>>({})

function statusLabel(s: string) {
  return ({
    erkannt: 'Erkannt', early_warning_24h: 'Frühwarnung (24h)',
    notification_72h: 'Meldung (72h)', final_report: 'Abschlussbericht',
  } as Record<string, string>)[s] || s
}

function ampelTitle(s: MeldungDeadlineStage) {
  if (s.overdue) return `${s.label}: überfällig`
  return `${s.label}: fällig ${s.due_at} (${Math.round(s.hours_left)}h)`
}

async function create() {
  await store.createMeldung(props.projekt, { ...form.value })
  showForm.value = false
  form.value = { typ: 'vuln_exploited', titel: '', erkannt_am: '', betroffene_ms: '' }
}

async function onStufe(m: Meldung, ev: Event) {
  const val = (ev.target as HTMLSelectElement).value
  if (val !== m.status) await store.setStufe(props.projekt, m.id, val)
}

function openAdvisory(m: Meldung) {
  advisoryFor.value = m
  advisoryForm.value = { ...(m.advisory || {}) }
}

async function saveAdvisory() {
  if (!advisoryFor.value) return
  await store.saveAdvisory(props.projekt, advisoryFor.value.id, advisoryForm.value)
  advisoryFor.value = null
}

function load() {
  if (props.projekt) store.fetchMeldungen(props.projekt)
}

onMounted(() => { store.fetchConstants(); load() })
watch(() => props.projekt, load)
</script>

<style scoped>
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; }
.meldung-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; }
.meldung-table th, .meldung-table td { border-bottom: 1px solid #e0e0e0; padding: 6px 8px; text-align: left; }
.ampel { display: inline-block; padding: 1px 6px; margin: 1px; border-radius: 4px; font-size: 11px; color: #fff; }
.ampel-gruen { background: #2e7d32; }
.ampel-gelb { background: #f9a825; color: #000; }
.ampel-rot { background: #e53935; }
.ampel-overdue { background: #b71c1c; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 0 4px; }
.btn-link.danger { color: #c62828; }
.empty { color: #90a4ae; font-style: italic; }
</style>
