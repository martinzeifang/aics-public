<template>
  <div class="gov-panel">
    <div class="intro-banner">
      <strong>{{ $t('nis2.governancePanel.governanceNachweiseArtNIS2') }}</strong>
      <p class="hint">{{ $t('nis2.governancePanel.billigungsbeschlussDerRMMassnahmenMa') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>

    <template v-else>
      <div class="toolbar">
        <button class="btn-primary" @click="openNew">{{ $t('nis2.governancePanel.neuerNachweis') }}</button>
        <span v-if="store.loading" class="hint">{{ $t('common.loading') }}</span>
      </div>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>
      <div v-if="!store.nachweise.length && !store.loading" class="hint">{{ $t('nis2.governancePanel.nochKeineNachweise') }}</div>

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
          {{ $t('nis2.governancePanel.gremiumV0GegenstandV1', { v0: n.gremium || '—', v1: n.gegenstand || '—' }) }}
          <span v-if="n.rm_version"> {{ $t('nis2.governancePanel.rMVersionV0', { v0: n.rm_version }) }}</span>
          {{ $t('nis2.governancePanel.wiedervorlageV0', { v0: n.naechster_review || '—' }) }}
          <span v-if="n.review.status === 'overdue'" class="overdue"> {{ $t('nis2.governancePanel.uberfallig') }}</span>
        </div>

        <div v-if="n.typ === 'schulung'" class="teilnehmer">
          <strong>{{ $t('nis2.governancePanel.teilnehmer') }}</strong>
          <button class="btn-link" @click="openTeilnehmer(n)">{{ $t('nis2.governancePanel.teilnehmer2') }}</button>
          <table v-if="n.teilnehmer.length">
            <thead><tr><th>{{ $t('common.name') }}</th><th>{{ $t('common.rolle') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('nis2.governancePanel.quizScore') }}</th><th></th></tr></thead>
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
          <span v-else class="hint">{{ $t('nis2.governancePanel.keineTeilnehmer') }}</span>
        </div>
      </div>
    </template>

    <!-- Modal: Nachweis -->
    <div v-if="showForm" class="modal-backdrop" @click.self="showForm = false">
      <div class="modal">
        <h3>{{ form.id ? $t('nis2.governancePanel.nachweisBearbeiten') : $t('nis2.governancePanel.neuerNachweis2') }}</h3>
        <label>{{ $t('common.typ') }}
          <select v-model="form.typ">
            <option v-for="t in store.constants?.nachweis_typen || []" :key="t" :value="t">{{ typLabel(t) }}</option>
          </select>
        </label>
        <label>{{ $t('common.date') }} <input v-model="form.datum" type="date" /></label>
        <label>{{ $t('nis2.governancePanel.gremiumTeilnehmerkreis') }} <input v-model="form.gremium" /></label>
        <label>{{ $t('nis2.governancePanel.gegenstand') }} <input v-model="form.gegenstand" /></label>
        <label>{{ $t('nis2.governancePanel.rMMassnahmenVersion') }} <input v-model="form.rm_version" /></label>
        <label>{{ $t('nis2.governancePanel.dokumentURL') }} <input v-model="form.dokument_url" /></label>
        <label>{{ $t('nis2.governancePanel.nachsterReviewWiedervorlage') }} <input v-model="form.naechster_review" type="date" /></label>
        <label v-if="form.typ === 'schulung'">{{ $t('nis2.governancePanel.n16QuizReferenz') }} <input v-model="form.quiz_referenz" /></label>
        <label>{{ $t('common.notizen') }} <textarea v-model="form.notizen" rows="2" /></label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showForm = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="submit">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>

    <!-- Modal: Teilnehmer -->
    <div v-if="showTeilnehmer" class="modal-backdrop" @click.self="showTeilnehmer = false">
      <div class="modal">
        <h3>{{ $t('nis2.governancePanel.teilnehmerSchulung') }}</h3>
        <label>{{ $t('common.name') }} <input v-model="teilnehmerForm.name" /></label>
        <label>{{ $t('common.rolle') }} <input v-model="teilnehmerForm.rolle" /></label>
        <label>{{ $t('common.status') }}
          <select v-model="teilnehmerForm.status">
            <option v-for="s in store.constants?.teilnehmer_status || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>{{ $t('nis2.governancePanel.n16QuizScore') }} <input v-model="teilnehmerForm.quiz_score" /></label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showTeilnehmer = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="submitTeilnehmer">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useNis2GovernanceStore, type GovNachweis, type GovTeilnehmer } from '../../stores/nis2Governance'
// `t` ist in dieser Maske schon belegt (lokale Variable) — deshalb
// unter anderem Namen. Der Typprüfer (#1858) hat die Kollision
// gefunden; der Build blieb grün und hätte die lokale Variable
// aufgerufen.
import { t as uebersetze } from '../../i18n'

const props = defineProps<{ projektName: string | null }>()
const store = useNis2GovernanceStore()

const TYP_LABEL: Record<string, string> = {
  billigungsbeschluss: uebersetze('nis2.governancePanel.billigungsbeschluss'),
  management_review: uebersetze('nis2.governancePanel.managementReview'),
  schulung: uebersetze('nis2.governancePanel.schulung'),
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
  if (!props.projektName || !confirm(uebersetze('nis2.governancePanel.nachweisLoschen'))) return
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
  if (!props.projektName || !confirm(uebersetze('nis2.governancePanel.teilnehmerLoschen'))) return
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
