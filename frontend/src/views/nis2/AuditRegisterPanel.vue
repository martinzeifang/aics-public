<template>
  <div class="audit-register">
    <div class="intro-banner">
      <strong>{{ $t('nis2.auditRegisterPanel.auditKonformitatsbewertungsRegisterA') }}</strong>
      <p class="hint">{{ $t('nis2.auditRegisterPanel.nachweisDerUmsetzungImJahresZyklusDu') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>

    <template v-else>
      <div class="toolbar">
        <button class="btn-primary" @click="openNew">{{ $t('nis2.auditRegisterPanel.neuesAudit') }}</button>
        <span v-if="store.loading" class="hint">{{ $t('common.loading') }}</span>
      </div>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>
      <div v-if="!store.audits.length && !store.loading" class="hint">{{ $t('nis2.auditRegisterPanel.nochKeineAuditsErfasst') }}</div>

      <div v-for="a in store.audits" :key="a.id" class="audit-card">
        <div class="audit-head">
          <span class="ampel" :class="'ampel-' + a.zyklus.ampel" :title="a.zyklus.status"></span>
          <span class="a-titel">{{ a.titel || $t('nis2.auditRegisterPanel.ohneTitel') }}</span>
          <span class="a-typ">{{ a.audit_typ }}</span>
          <span class="a-erg">{{ a.ergebnis }}</span>
          <span class="spacer"></span>
          <button class="btn-secondary" @click="openEdit(a)">✏️</button>
          <button class="btn-secondary" @click="store.exportAudit(projektName, a.id)">📄</button>
          <button class="btn-secondary danger" @click="remove(a)">🗑️</button>
        </div>
        <div class="a-meta">
          {{ $t('nis2.auditRegisterPanel.pruferV0DurchgefuhrtV1NachstesAuditV', { v0: a.pruefer || '—', v1: a.durchgefuehrt_am || '—', v2: a.naechster_audit_soll || '—' }) }}
          <span v-if="a.zyklus.status === 'overdue'" class="overdue"> {{ $t('nis2.auditRegisterPanel.uberfallig') }}</span>
        </div>

        <div class="findings">
          <strong>{{ $t('nis2.auditRegisterPanel.findingsCAPA') }}</strong>
          <button class="btn-link" @click="openFinding(a)">{{ $t('nis2.auditRegisterPanel.finding') }}</button>
          <!-- #2062 -->
          <div v-if="a.findings.length" class="tabelle-scroll">
          <table>
            <thead><tr><th>{{ $t('common.schwere') }}</th><th>{{ $t('common.description') }}</th><th>{{ $t('common.massnahme') }}</th><th>{{ $t('nis2.auditRegisterPanel.verantw') }}</th><th>{{ $t('common.frist') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('nis2.auditRegisterPanel.link') }}</th><th></th></tr></thead>
            <tbody>
              <tr v-for="f in a.findings" :key="f.id">
                <td><span class="schwere" :class="'schwere-' + f.schweregrad">{{ f.schweregrad }}</span></td>
                <td>{{ f.beschreibung }}</td>
                <td>{{ f.massnahme }}</td>
                <td>{{ f.verantwortlich }}</td>
                <td>{{ f.frist }}</td>
                <td>{{ f.status }}</td>
                <td>{{ f.objekt_typ ? f.objekt_typ + ' ' + f.objekt_ref : '—' }}</td>
                <td>
                  <button class="btn-link" @click="openFinding(a, f)">✏️</button>
                  <button class="btn-link" @click="removeFinding(a, f)">🗑️</button>
                </td>
              </tr>
            </tbody>
          </table>
          </div>
          <span v-else class="hint">{{ $t('nis2.auditRegisterPanel.keineFindings') }}</span>
        </div>
      </div>
    </template>

    <!-- Modal: Audit -->
    <div v-if="showAudit" class="modal-backdrop" @click.self="showAudit = false">
      <div class="modal">
        <h3>{{ auditForm.id ? $t('nis2.auditRegisterPanel.auditBearbeiten') : $t('nis2.auditRegisterPanel.neuesAudit2') }}</h3>
        <label>{{ $t('common.titel') }} <input v-model="auditForm.titel" /></label>
        <label>{{ $t('common.typ') }}
          <select v-model="auditForm.audit_typ">
            <option v-for="t in store.constants?.audit_typen || []" :key="t" :value="t">{{ t }}</option>
          </select>
        </label>
        <label>{{ $t('nis2.auditRegisterPanel.scope') }} <input v-model="auditForm.scope" /></label>
        <label>{{ $t('nis2.auditRegisterPanel.prufer') }} <input v-model="auditForm.pruefer" /></label>
        <label>{{ $t('nis2.auditRegisterPanel.durchgefuhrtAm') }} <input v-model="auditForm.durchgefuehrt_am" type="date" /></label>
        <label>{{ $t('nis2.auditRegisterPanel.nachstesAuditLeerJahre') }} <input v-model="auditForm.naechster_audit_soll" type="date" /></label>
        <label>{{ $t('nis2.auditRegisterPanel.zertifikatURL') }} <input v-model="auditForm.zertifikat_url" /></label>
        <label>{{ $t('nis2.auditRegisterPanel.zertifikatAblauf') }} <input v-model="auditForm.zertifikat_ablauf" type="date" /></label>
        <label>{{ $t('common.ergebnis') }}
          <select v-model="auditForm.ergebnis">
            <option v-for="e in store.constants?.audit_ergebnis || []" :key="e" :value="e">{{ e }}</option>
          </select>
        </label>
        <label>{{ $t('common.notizen') }} <textarea v-model="auditForm.notizen" rows="2" /></label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showAudit = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="submitAudit">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>

    <!-- Modal: Finding -->
    <div v-if="showFinding" class="modal-backdrop" @click.self="showFinding = false">
      <div class="modal">
        <h3>{{ $t('nis2.auditRegisterPanel.findingCAPA') }}</h3>
        <label>{{ $t('common.description') }} <textarea v-model="findingForm.beschreibung" rows="2" /></label>
        <label>{{ $t('common.schweregrad') }}
          <select v-model="findingForm.schweregrad">
            <option v-for="s in store.constants?.finding_schweregrade || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>{{ $t('common.massnahme') }} <textarea v-model="findingForm.massnahme" rows="2" /></label>
        <label>{{ $t('common.verantwortlich') }} <input v-model="findingForm.verantwortlich" /></label>
        <label>{{ $t('common.frist') }} <input v-model="findingForm.frist" type="date" /></label>
        <label>{{ $t('common.status') }}
          <select v-model="findingForm.status">
            <option v-for="s in store.constants?.finding_status || []" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>{{ $t('nis2.auditRegisterPanel.verknupfung') }}
          <select v-model="findingForm.objekt_typ">
            <option v-for="o in store.constants?.finding_objekt || []" :key="o" :value="o">{{ o || '(keine)' }}</option>
          </select>
        </label>
        <label v-if="findingForm.objekt_typ">{{ $t('nis2.auditRegisterPanel.referenzAnforderungsRisikoID') }}
          <input v-model="findingForm.objekt_ref" />
        </label>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showFinding = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="submitFinding">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useNis2AuditStore, type Audit, type AuditFinding } from '../../stores/nis2Audit'
import { t } from '../../i18n'

const props = defineProps<{ projektName: string | null }>()
const store = useNis2AuditStore()

const showAudit = ref(false)
const showFinding = ref(false)
const auditForm = ref<any>({})
const findingForm = ref<any>({})
const activeAudit = ref<Audit | null>(null)

const reload = async () => { if (props.projektName) await store.fetchAudits(props.projektName) }
onMounted(async () => { await store.fetchConstants(); await reload() })
watch(() => props.projektName, reload)

const openNew = () => {
  auditForm.value = {
    titel: '', audit_typ: 'intern', scope: '', pruefer: '', durchgefuehrt_am: '',
    naechster_audit_soll: '', zertifikat_url: '', zertifikat_ablauf: '',
    ergebnis: 'offen', notizen: '',
  }
  showAudit.value = true
}
const openEdit = (a: Audit) => { auditForm.value = { ...a }; showAudit.value = true }
const submitAudit = async () => {
  if (!props.projektName) return
  if (await store.saveAudit(props.projektName, auditForm.value)) {
    showAudit.value = false; await reload()
  }
}
const remove = async (a: Audit) => {
  if (!props.projektName || !confirm(`Audit "${a.titel}" löschen?`)) return
  if (await store.deleteAudit(props.projektName, a.id)) await reload()
}

const openFinding = (a: Audit, f?: AuditFinding) => {
  activeAudit.value = a
  findingForm.value = f ? { ...f } : {
    beschreibung: '', schweregrad: 'mittel', massnahme: '', verantwortlich: '',
    frist: '', status: 'offen', objekt_typ: '', objekt_ref: '',
  }
  showFinding.value = true
}
const submitFinding = async () => {
  if (!props.projektName || !activeAudit.value) return
  if (await store.saveFinding(props.projektName, activeAudit.value.id, findingForm.value)) {
    showFinding.value = false; await reload()
  }
}
const removeFinding = async (a: Audit, f: AuditFinding) => {
  if (!props.projektName || !confirm(t('nis2.auditRegisterPanel.findingLoschen'))) return
  if (await store.deleteFinding(props.projektName, a.id, f.id)) await reload()
}
</script>

<style scoped>
.audit-register { padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }
.intro-banner strong { color: #1565c0; }
.hint { color: #607d8b; font-size: 0.9em; }
.msg.err { color: #c62828; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.audit-card { border: 1px solid #cfd8dc; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; background: #fff; }
.audit-head { display: flex; align-items: center; gap: 10px; }
.a-titel { font-weight: 600; color: #1565c0; }
.a-typ, .a-erg { font-size: 0.8em; padding: 2px 8px; border-radius: 10px; background: #eceff1; }
.spacer { flex: 1; }
.a-meta { color: #607d8b; font-size: 0.85em; margin: 6px 0 10px; }
.overdue { color: #c62828; font-weight: 600; }
.findings { border-top: 1px dashed #cfd8dc; padding-top: 8px; }
.findings table { width: 100%; border-collapse: collapse; font-size: 0.85em; margin-top: 6px; }
.findings th, .findings td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #eceff1; }
.schwere { padding: 1px 6px; border-radius: 8px; background: #eceff1; }
.schwere-hoch { background: #ffe0b2; }
.schwere-kritisch { background: #ffcdd2; }
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
