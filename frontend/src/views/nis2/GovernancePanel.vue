<template>
  <div class="gov-panel">
    <div class="intro-banner">
      <strong>🏛️ Governance-Nachweise (Art. 20 NIS2)</strong>
      <p class="hint">Billigungsbeschluss der RM-Maßnahmen, Management-Review-Protokolle und
        Schulungsnachweise der Leitungsorgane (mit Teilnehmerliste + N16-Quiz-Verknüpfung).
        Wiedervorlage-Ampel; Aufnahme in den Readiness-Report.</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>

    <template v-else>
      <div class="toolbar">
        <button class="btn-primary" @click="openNew">+ Neuer Nachweis</button>
        <span v-if="store.loading" class="hint">Lädt…</span>
      </div>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>
      <div v-if="!store.nachweise.length && !store.loading" class="hint">Noch keine Nachweise.</div>

      <div v-for="n in store.nachweise" :key="n.id" class="gov-card">
        <div class="gov-head">
          <span class="ampel" :class="'ampel-' + n.review.ampel" :title="n.review.status"></span>
          <span class="g-typ">{{ typLabel(n.typ) }}</span>
          <span class="g-datum">{{ n.datum || '—' }}</span>
          <span class="spacer"></span>
          <button class="btn-secondary" @click="openEdit(n)">✏️</button>
          <button class="btn-secondary danger" @click="remove(n)">🗑️</button>
        </div>
        <div class="g-meta">
          Gremium: {{ n.gremium || '—' }} · Gegenstand: {{ n.gegenstand || '—' }}
          <span v-if="n.rm_version"> · RM-Version: {{ n.rm_version }}</span>
          · Wiedervorlage: {{ n.naechster_review || '—' }}
          <span v-if="n.review.status === 'overdue'" class="overdue"> · überfällig!</span>
        </div>

        <div v-if="n.typ === 'schulung'" class="teilnehmer">
          <strong>Teilnehmer</strong>
          <button class="btn-link" @click="openTeilnehmer(n)">+ Teilnehmer</button>
          <table v-if="n.teilnehmer.length">
            <thead><tr><th>Name</th><th>Rolle</th><th>Status</th><th>Quiz-Score</th><th></th></tr></thead>
            <tbody>
              <tr v-for="t in n.teilnehmer" :key="t.id">
                <td>{{ t.name }}</td>
                <td>{{ t.rolle }}</td>
                <td>{{ t.status }}</td>
                <td>{{ t.quiz_score || '—' }}</td>
                <td>
                  <button class="btn-link" @click="openTeilnehmer(n, t)">✏️</button>
                  <button class="btn-link" @click="removeTeilnehmer(n, t)">🗑️</button>
                </td>
              </tr>
            </tbody>
          </table>
          <span v-else class="hint">Keine Teilnehmer.</span>
        </div>
      </div>
    </template>

    <!-- Modal: Nachweis -->
    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <div class="modal">
        <h3>{{ form.id ? 'Nachweis bearbeiten' : 'Neuer Nachweis' }}</h3>
        <label>Typ
          <select v-model="form.typ">
            <option v-for="t in store.constants?.nachweis_typen || []" :key="t" :value="t">{{ typLabel(t) }}</option>
          </select>
        </label>
        <label>Datum <input v-model="form.datum" type="date" /></label>
        <label>Gremium / Teilnehmerkreis <input v-model="form.gremium" /></label>
        <label>Gegenstand <input v-model="form.gegenstand" /></label>
        <label>RM-Maßnahmen-Version <input v-model="form.rm_version" /></label>
        <label>Dokument-URL <input v-model="form.dokument_url" /></label>
        <label>Nächster Review (Wiedervorlage) <input v-model="form.naechster_review" type="date" /></label>
        <label v-if="form.typ === 'schulung'">N16-Quiz-Referenz <input v-model="form.quiz_referenz" /></label>
        <label>Notizen <textarea v-model="form.notizen" rows="2" /></label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showForm = false">Abbrechen</button>
          <button class="btn-primary" @click="submit">Speichern</button>
        </div>
      </div>
    </div>

    <!-- Modal: Teilnehmer -->
    <div v-if="showTeilnehmer" class="modal-backdrop" @click.self="showTeilnehmer = false">
      <div class="modal">
        <h3>Teilnehmer (Schulung)</h3>
        <label>Name <input v-model="teilnehmerForm.name" /></label>
        <label>Rolle <input v-model="teilnehmerForm.rolle" /></label>
        <label>Status
          <select v-model="teilnehmerForm.status">
            <option v-for="s in store.constants?.teilnehmer_status || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>N16-Quiz-Score <input v-model="teilnehmerForm.quiz_score" /></label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showTeilnehmer = false">Abbrechen</button>
          <button class="btn-primary" @click="submitTeilnehmer">Speichern</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useNis2GovernanceStore, type GovNachweis, type GovTeilnehmer } from '../../stores/nis2Governance'

const props = defineProps<{ projektName: string | null }>()
const store = useNis2GovernanceStore()

const TYP_LABEL: Record<string, string> = {
  billigungsbeschluss: 'Billigungsbeschluss',
  management_review: 'Management-Review',
  schulung: 'Schulung',
}
const typLabel = (t: string) => TYP_LABEL[t] || t

const showForm = ref(false)
const showTeilnehmer = ref(false)
const form = ref<any>({})
const teilnehmerForm = ref<any>({})
const activeNachweis = ref<GovNachweis | null>(null)

const reload = async () => { if (props.projektName) await store.fetchNachweise(props.projektName) }
onMounted(async () => { await store.fetchConstants(); await reload() })
watch(() => props.projektName, reload)

const openNew = () => {
  form.value = {
    typ: 'billigungsbeschluss', datum: '', gremium: '', gegenstand: '',
    rm_version: '', dokument_url: '', naechster_review: '', quiz_referenz: '', notizen: '',
  }
  showForm.value = true
}
const openEdit = (n: GovNachweis) => { form.value = { ...n }; showForm.value = true }
const submit = async () => {
  if (!props.projektName) return
  if (await store.saveNachweis(props.projektName, form.value)) {
    showForm.value = false; await reload()
  }
}
const remove = async (n: GovNachweis) => {
  if (!props.projektName || !confirm('Nachweis löschen?')) return
  if (await store.deleteNachweis(props.projektName, n.id)) await reload()
}

const openTeilnehmer = (n: GovNachweis, t?: GovTeilnehmer) => {
  activeNachweis.value = n
  teilnehmerForm.value = t ? { ...t } : { name: '', rolle: '', status: 'offen', quiz_score: '' }
  showTeilnehmer.value = true
}
const submitTeilnehmer = async () => {
  if (!props.projektName || !activeNachweis.value) return
  if (await store.saveTeilnehmer(props.projektName, activeNachweis.value.id, teilnehmerForm.value)) {
    showTeilnehmer.value = false; await reload()
  }
}
const removeTeilnehmer = async (n: GovNachweis, t: GovTeilnehmer) => {
  if (!props.projektName || !confirm('Teilnehmer löschen?')) return
  if (await store.deleteTeilnehmer(props.projektName, n.id, t.id)) await reload()
}
</script>

<style scoped>
.gov-panel { padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }
.intro-banner strong { color: #1565c0; }
.hint { color: #607d8b; font-size: 0.9em; }
.msg.err { color: #c62828; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.gov-card { border: 1px solid #cfd8dc; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; background: #fff; }
.gov-head { display: flex; align-items: center; gap: 10px; }
.g-typ { font-weight: 600; color: #1565c0; }
.g-datum { font-size: 0.85em; color: #607d8b; }
.spacer { flex: 1; }
.g-meta { color: #607d8b; font-size: 0.85em; margin: 6px 0 10px; }
.overdue { color: #c62828; font-weight: 600; }
.teilnehmer { border-top: 1px dashed #cfd8dc; padding-top: 8px; }
.teilnehmer table { width: 100%; border-collapse: collapse; font-size: 0.85em; margin-top: 6px; }
.teilnehmer th, .teilnehmer td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #eceff1; }
.ampel { width: 12px; height: 12px; border-radius: 50%; display: inline-block; background: #bdbdbd; }
.ampel-green { background: #43a047; }
.ampel-amber { background: #fb8c00; }
.ampel-red { background: #e53935; }
.ampel-grey { background: #bdbdbd; }
.btn-primary { background: #1565c0; color: #fff; border: none; padding: 7px 14px; border-radius: 6px; cursor: pointer; }
.btn-secondary { background: #eceff1; border: 1px solid #cfd8dc; padding: 6px 10px; border-radius: 6px; cursor: pointer; }
.btn-secondary.danger { color: #c62828; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 0 6px; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 8px; padding: 20px 24px; width: 520px; max-width: 92vw; max-height: 88vh; overflow: auto; }
.modal h3 { color: #1565c0; margin-top: 0; }
.modal label { display: block; margin: 10px 0; font-size: 0.9em; }
.modal input, .modal select, .modal textarea { width: 100%; padding: 6px 8px; border: 1px solid #cfd8dc; border-radius: 4px; margin-top: 4px; box-sizing: border-box; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
</style>
