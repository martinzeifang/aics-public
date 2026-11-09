<template>
  <div class="jc-panel">
    <div class="intro-banner">
      <strong>{{ $t('dsgvo.jointControllerPanel.jointControllerRegisterArt') }}</strong>
      <p class="hint">{{ $t('dsgvo.jointControllerPanel.gemeinsamVerantwortlicheVerteilungDe') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>
    <template v-else>
      <button class="btn-primary" @click="openNew">{{ $t('dsgvo.jointControllerPanel.neueKonstellation') }}</button>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <!-- #2062 -->
      <div v-if="store.items.length" class="tabelle-scroll">
      <table class="grid">
        <thead>
          <tr><th>ID</th><th>{{ $t('dsgvo.jointControllerPanel.partner') }}</th><th>{{ $t('dsgvo.jointControllerPanel.verarbeitung') }}</th><th>{{ $t('dsgvo.jointControllerPanel.anlaufstelle') }}</th>
            <th>{{ $t('dsgvo.jointControllerPanel.vereinbarung') }}</th><th>{{ $t('dsgvo.jointControllerPanel.zusammenfassung') }}</th><th>{{ $t('dsgvo.jointControllerPanel.review') }}</th><th>{{ $t('common.actions') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="j in store.items" :key="j.id">
            <td>{{ j.jc_id }}</td>
            <td>{{ j.partner }}</td>
            <td>{{ j.verarbeitung }}</td>
            <td>{{ anlaufstelleLabel(j.anlaufstelle_betroffene) }}</td>
            <td><span class="pill" :class="j.vereinbarung_vorhanden ? 'pill-ok' : 'pill-warn'">
              {{ j.vereinbarung_vorhanden ? 'vorhanden' : 'fehlt' }}</span></td>
            <td><span class="pill" :class="'pill-zs-' + j.zusammenfassung_status">
              {{ zsLabel(j.zusammenfassung_status) }}</span></td>
            <td>{{ j.naechstes_review || '—' }}</td>
            <td class="actions">
              <button class="btn-secondary" @click="openEdit(j)">✏️</button>
              <button class="btn-secondary" @click="store.exportItem(projektName!, j.id, 'docx')">📝</button>
              <button class="btn-secondary" @click="store.exportItem(projektName!, j.id, 'pdf')">📄</button>
              <button class="btn-danger-mini" @click="del(j)">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
      </div>
      <p v-else class="hint">{{ $t('dsgvo.jointControllerPanel.keineGemeinsamenVerantwortlichkeiten') }}</p>
    </template>

    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? $t('dsgvo.jointControllerPanel.konstellationBearbeiten') : $t('dsgvo.jointControllerPanel.neueKonstellation2') }}</h3>

        <h4>{{ $t('dsgvo.jointControllerPanel.eckdaten') }}</h4>
        <label>{{ $t('dsgvo.jointControllerPanel.konstellationsID') }} <input v-model="editing.jc_id" placeholder="JC-001" /></label>
        <label>{{ $t('dsgvo.jointControllerPanel.partner') }} <input v-model="editing.partner" /></label>
        <label>{{ $t('dsgvo.jointControllerPanel.partnerKontakt') }} <input v-model="editing.partner_kontakt" /></label>
        <label>{{ $t('common.vVTReferenz') }} <input v-model="editing.vvt_ref" /></label>
        <label>{{ $t('dsgvo.jointControllerPanel.betroffeneVerarbeitung') }} <input v-model="editing.verarbeitung" /></label>
        <label>{{ $t('dsgvo.jointControllerPanel.zweckMittel') }} <textarea v-model="editing.zweck_mittel" rows="2"></textarea></label>

        <h4>{{ $t('dsgvo.jointControllerPanel.verteilungDerPflichtenArtAbs') }}</h4>
        <label>{{ $t('dsgvo.jointControllerPanel.anlaufstelleFurBetroffenenrechte') }}
          <select v-model="editing.anlaufstelle_betroffene">
            <option value="offen">{{ $t('cra.pflichtDokuPanel.offen') }}</option>
            <option value="wir">{{ $t('dsgvo.jointControllerPanel.wirEigeneStelle') }}</option>
            <option value="partner">{{ $t('dsgvo.jointControllerPanel.partner') }}</option>
            <option value="beide">{{ $t('dsgvo.jointControllerPanel.beideGemeinsam') }}</option>
          </select>
        </label>
        <label>{{ $t('dsgvo.jointControllerPanel.informationspflichtenArt') }} <textarea v-model="editing.pflicht_information" rows="2"></textarea></label>
        <label>{{ $t('dsgvo.jointControllerPanel.technischeOrganisatorischeMassnahmen') }} <textarea v-model="editing.pflicht_tom" rows="2"></textarea></label>
        <label>{{ $t('dsgvo.jointControllerPanel.meldungVonDatenpannen') }} <textarea v-model="editing.pflicht_meldung" rows="2"></textarea></label>

        <h4>{{ $t('dsgvo.jointControllerPanel.vereinbarungArtAbs') }}</h4>
        <label class="cb"><input type="checkbox" v-model="vereinbarung" /> {{ $t('dsgvo.jointControllerPanel.vereinbarungVorhanden') }}</label>
        <label>{{ $t('dsgvo.jointControllerPanel.fundstelleURL') }} <input v-model="editing.vereinbarung_url" /></label>
        <label>{{ $t('common.date') }} <input v-model="editing.vereinbarung_datum" type="date" /></label>

        <h4>{{ $t('dsgvo.jointControllerPanel.zusammenfassungFurBetroffeneArtAbs') }}</h4>
        <label>{{ $t('common.status') }}
          <select v-model="editing.zusammenfassung_status">
            <option value="offen">{{ $t('cra.pflichtDokuPanel.offen') }}</option>
            <option value="entwurf">{{ $t('dsgvo.jointControllerPanel.entwurf') }}</option>
            <option value="veroeffentlicht">{{ $t('dsgvo.jointControllerPanel.veroffentlicht') }}</option>
          </select>
        </label>
        <label>{{ $t('dsgvo.jointControllerPanel.fundstelleURL') }} <input v-model="editing.zusammenfassung_url" /></label>
        <label>{{ $t('dsgvo.jointControllerPanel.wesentlichesDerVereinbarung') }} <textarea v-model="editing.zusammenfassung_text" rows="3"></textarea></label>

        <h4>{{ $t('dsgvo.jointControllerPanel.review') }}</h4>
        <label>{{ $t('common.reviewer') }} <input v-model="editing.reviewer" /></label>
        <label>{{ $t('common.reviewDatum') }} <input v-model="editing.review_datum" type="date" /></label>
        <label>{{ $t('dsgvo.jointControllerPanel.reviewZyklusMonate') }} <input v-model.number="editing.review_zyklus_monate" type="number" min="0" /></label>
        <label>{{ $t('common.notizen') }} <textarea v-model="editing.notizen" rows="2"></textarea></label>

        <div class="modal-actions">
          <button class="btn-primary" @click="save">{{ $t('common.saveIcon') }}</button>
          <button class="btn-secondary" @click="editing = null">{{ $t('common.cancel') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useDsgvoJointControllerStore, type JointController } from '../../stores/dsgvoJointController'
import { t } from '../../i18n'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoJointControllerStore()

const editing = ref<Partial<JointController> | null>(null)
const vereinbarung = ref(false)

const anlaufstelleLabel = (a: string) =>
  ({ wir: t('dsgvo.jointControllerPanel.wir'), partner: t('dsgvo.jointControllerPanel.partner'), beide: t('dsgvo.jointControllerPanel.beide'), offen: 'offen' } as any)[a] || a
const zsLabel = (s: string) =>
  ({ veroeffentlicht: t('dsgvo.jointControllerPanel.veroffentlicht'), entwurf: t('common.entwurf'), offen: 'offen' } as any)[s] || s

const load = () => { if (props.projektName) store.fetchItems(props.projektName) }

const openNew = () => {
  vereinbarung.value = false
  editing.value = {
    jc_id: '', partner: '', partner_kontakt: '', vvt_ref: '', verarbeitung: '',
    zweck_mittel: '', anlaufstelle_betroffene: 'offen', pflicht_information: '',
    pflicht_tom: '', pflicht_meldung: '', vereinbarung_url: '', vereinbarung_datum: '',
    zusammenfassung_status: 'offen', zusammenfassung_text: '', zusammenfassung_url: '',
    reviewer: '', review_datum: '', review_zyklus_monate: 12, notizen: '',
  }
}

const openEdit = (j: JointController) => {
  vereinbarung.value = !!j.vereinbarung_vorhanden
  editing.value = { ...j }
}

const save = async () => {
  if (!props.projektName || !editing.value) return
  const payload = { ...editing.value, vereinbarung_vorhanden: vereinbarung.value ? 1 : 0 }
  if (await store.save(props.projektName, payload)) editing.value = null
}

const del = async (j: JointController) => {
  if (!props.projektName) return
  if (confirm(`Konstellation ${j.jc_id} löschen?`)) await store.remove(props.projektName, j.id)
}

onMounted(() => { store.fetchConstants(); load() })
watch(() => props.projektName, load)
</script>

<style scoped>
.jc-panel { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 8px; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin: 4px 0 0; }
.hint { color: #666; font-size: 13px; }
.grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.grid th, .grid td { border: 1px solid var(--color-border, #ddd); padding: 6px 8px; text-align: left; }
.grid th { background: #1565c0; color: white; }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.pill { padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.pill-ok { background: #e8f5e9; color: #2e7d32; }
.pill-warn { background: #ffebee; color: #c62828; }
.pill-zs-veroeffentlicht { background: #e8f5e9; color: #2e7d32; }
.pill-zs-entwurf { background: #fff8e1; color: #f57f17; }
.pill-zs-offen { background: #eceff1; color: #607d8b; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; align-self: flex-start; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-danger-mini { background: #ffcdd2; color: #b71c1c; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.msg { font-size: 13px; }
.msg.err { color: #c62828; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; border-radius: 8px; padding: 20px 24px; width: min(640px, 94vw); max-height: 90vh; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.modal h3 { color: #1565c0; margin: 0 0 8px; }
.modal h4 { color: #1565c0; margin: 12px 0 0; font-size: 14px; }
.modal label { display: flex; flex-direction: column; font-size: 13px; gap: 2px; }
.modal label.cb { flex-direction: row; align-items: center; gap: 6px; }
.modal input, .modal select, .modal textarea { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.modal-actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
</style>
