<template>
  <div class="sub-panel">
    <div class="intro-banner">
      <strong>{{ $t('dsgvo.subprozessorenPanel.subprozessorenArt') }}</strong>
      <p class="hint">{{ $t('dsgvo.subprozessorenPanel.weitereAuftragsverarbeiterNurMitVorh') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>
    <template v-else>
      <div class="toolbar">
        <button class="btn-secondary" @click="store.exportBericht(projektName!, 'docx')">{{ $t('dsgvo.subprozessorenPanel.aVVBerichtWord') }}</button>
        <button class="btn-secondary" @click="store.exportBericht(projektName!, 'pdf')">{{ $t('common.pDF2') }}</button>
      </div>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>
      <p v-if="!store.avv.length && !store.loading" class="hint">
        {{ $t('dsgvo.subprozessorenPanel.keineAuftragsverarbeiterErfasstBitte') }}</p>

      <div v-for="a in store.avv" :key="a.id" class="avv-card">
        <div class="avv-head">
          <strong>{{ a.auftragsverarbeiter }}</strong>
          <span class="muted">{{ a.leistung }}</span>
          <span v-if="a.review_faellig" class="pill pill-rot">⚠ {{ a.sub_ausstehend }} ungenehmigt</span>
          <span v-else-if="a.sub_gesamt" class="pill pill-gruen">{{ $t('dsgvo.subprozessorenPanel.alleGenehmigt') }}</span>
          <button class="btn-secondary" @click="toggle(a.id)">
            {{ $t('dsgvo.subprozessorenPanel.v0SubprozessorenV1', { v0: open === a.id ? '▲' : '▼', v1: a.sub_gesamt }) }}
          </button>
        </div>

        <div v-if="open === a.id" class="sub-body">
          <table v-if="(store.subs[a.id] || []).length" class="grid">
            <thead>
              <tr><th>{{ $t('common.name') }}</th><th>{{ $t('common.leistung') }}</th><th>{{ $t('dsgvo.subprozessorenPanel.drittlandGarantie') }}</th>
                <th>{{ $t('dsgvo.subprozessorenPanel.genehmigung') }}</th><th>back-to-back</th><th>{{ $t('common.actions') }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="s in store.subs[a.id]" :key="s.id">
                <td>{{ s.name }}</td>
                <td>{{ s.leistung }}</td>
                <td>{{ s.drittland ? $t('dsgvo.subprozessorenPanel.drittland') : '' }}{{ s.drittland_garantie || '—' }}</td>
                <td>
                  <span class="pill" :class="'pill-' + s.genehmigung_status">{{ s.genehmigung_status }}</span>
                  <span v-if="s.genehmigung_datum" class="muted"> {{ s.genehmigung_datum }}</span>
                </td>
                <td>{{ s.pflichten_backtoback ? '✓' : '✗' }}</td>
                <td class="actions">
                  <button class="btn-mini" @click="approve(a.id, s.id, 'genehmigt')">✓</button>
                  <button class="btn-mini" @click="approve(a.id, s.id, 'abgelehnt')">✗</button>
                  <button class="btn-secondary" @click="openEdit(a.id, s)">✏️</button>
                  <button class="btn-danger-mini" @click="del(a.id, s.id)">🗑️</button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="hint">{{ $t('dsgvo.subprozessorenPanel.keineSubprozessoren') }}</p>
          <button class="btn-primary" @click="openNew(a.id)">{{ $t('dsgvo.subprozessorenPanel.subprozessor') }}</button>
        </div>
      </div>
    </template>

    <!-- Editor -->
    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? $t('dsgvo.subprozessorenPanel.subprozessorBearbeiten') : $t('dsgvo.subprozessorenPanel.neuerSubprozessor') }}</h3>
        <label>{{ $t('common.name') }} <input v-model="editing.name" /></label>
        <label>{{ $t('common.leistung') }} <input v-model="editing.leistung" /></label>
        <label class="cb"><input type="checkbox" v-model="drittland" /> {{ $t('common.drittland') }}</label>
        <label>{{ $t('dsgvo.subprozessorenPanel.drittlandGarantie') }}
          <select v-model="editing.drittland_garantie">
            <option value="">—</option>
            <option value="SCC">{{ $t('dsgvo.subprozessorenPanel.sCC') }}</option>
            <option value="Adäquanzbeschluss">{{ $t('dsgvo.subprozessorenPanel.adaquanzbeschluss') }}</option>
            <option value="BCR">{{ $t('dsgvo.subprozessorenPanel.bCR') }}</option>
          </select>
        </label>
        <label>{{ $t('dsgvo.subprozessorenPanel.genehmigungsStatus') }}
          <select v-model="editing.genehmigung_status">
            <option value="ausstehend">ausstehend</option>
            <option value="genehmigt">genehmigt</option>
            <option value="abgelehnt">{{ $t('dsgvo.subprozessorenPanel.abgelehnt') }}</option>
          </select>
        </label>
        <label>{{ $t('dsgvo.subprozessorenPanel.genehmigungsdatum') }} <input v-model="editing.genehmigung_datum" type="date" /></label>
        <label class="cb"><input type="checkbox" v-model="subAvv" /> {{ $t('dsgvo.subprozessorenPanel.subAVVVorhanden') }}</label>
        <label>{{ $t('dsgvo.subprozessorenPanel.subAVVURL') }} <input v-model="editing.sub_avv_url" /></label>
        <label class="cb"><input type="checkbox" v-model="backToBack" /> {{ $t('dsgvo.subprozessorenPanel.identischePflichtenBackToBackWeiterg') }}</label>
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
import { useDsgvoSubprozessorenStore, type Subprozessor } from '../../stores/dsgvoSubprozessoren'
import { t } from '../../i18n'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoSubprozessorenStore()

const open = ref<number | null>(null)
const editing = ref<(Partial<Subprozessor> & { _avvPk?: number }) | null>(null)
const drittland = ref(false)
const subAvv = ref(false)
const backToBack = ref(false)

const load = () => { if (props.projektName) store.fetchAvv(props.projektName) }

const toggle = (avvPk: number) => {
  if (open.value === avvPk) { open.value = null; return }
  open.value = avvPk
  if (props.projektName) store.fetchSubs(props.projektName, avvPk)
}

const openNew = (avvPk: number) => {
  drittland.value = false; subAvv.value = false; backToBack.value = false
  editing.value = {
    _avvPk: avvPk, name: '', leistung: '', drittland_garantie: '',
    genehmigung_status: 'ausstehend', genehmigung_datum: '', sub_avv_url: '',
  }
}

const openEdit = (avvPk: number, s: Subprozessor) => {
  drittland.value = !!s.drittland; subAvv.value = !!s.sub_avv_vorhanden
  backToBack.value = !!s.pflichten_backtoback
  editing.value = { ...s, _avvPk: avvPk }
}

const save = async () => {
  if (!props.projektName || !editing.value) return
  const avvPk = editing.value._avvPk!
  const payload = {
    name: editing.value.name, leistung: editing.value.leistung,
    drittland: drittland.value ? 1 : 0, drittland_garantie: editing.value.drittland_garantie,
    genehmigung_status: editing.value.genehmigung_status,
    genehmigung_datum: editing.value.genehmigung_datum,
    sub_avv_vorhanden: subAvv.value ? 1 : 0, sub_avv_url: editing.value.sub_avv_url,
    pflichten_backtoback: backToBack.value ? 1 : 0,
  }
  const ok = editing.value.id
    ? await store.updateSub(props.projektName, avvPk, editing.value.id, payload)
    : await store.createSub(props.projektName, avvPk, payload)
  if (ok) editing.value = null
}

const approve = async (avvPk: number, pk: number, status: string) => {
  if (!props.projektName) return
  await store.setGenehmigung(props.projektName, avvPk, pk, status, new Date().toISOString().slice(0, 10))
}

const del = async (avvPk: number, pk: number) => {
  if (!props.projektName) return
  if (confirm(t('dsgvo.subprozessorenPanel.subprozessorLoschen'))) await store.deleteSub(props.projektName, avvPk, pk)
}

onMounted(load)
watch(() => props.projektName, load)
</script>

<style scoped>
.sub-panel { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 8px; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin: 4px 0 0; }
.hint { color: #666; font-size: 13px; }
.muted { color: #888; font-size: 12px; }
.toolbar { display: flex; gap: 8px; }
.avv-card { border: 1px solid var(--color-border, #ddd); border-radius: 8px; padding: 10px 14px; background: white; }
.avv-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sub-body { margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }
.grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.grid th, .grid td { border: 1px solid var(--color-border, #ddd); padding: 6px 8px; text-align: left; }
.grid th { background: #1565c0; color: white; }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.pill { padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.pill-gruen, .pill-genehmigt { background: #e8f5e9; color: #2e7d32; }
.pill-rot, .pill-abgelehnt { background: #ffebee; color: #c62828; }
.pill-ausstehend { background: #fff8e1; color: #f57f17; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 7px 12px; border-radius: 4px; cursor: pointer; align-self: flex-start; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-mini { background: #c8e6c9; color: #2e7d32; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-danger-mini { background: #ffcdd2; color: #b71c1c; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.msg { font-size: 13px; }
.msg.err { color: #c62828; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; border-radius: 8px; padding: 20px 24px; width: min(540px, 92vw); max-height: 88vh; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.modal h3 { color: #1565c0; margin: 0 0 8px; }
.modal label { display: flex; flex-direction: column; font-size: 13px; gap: 2px; }
.modal label.cb { flex-direction: row; align-items: center; gap: 6px; }
.modal input, .modal select { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.modal-actions { display: flex; gap: 8px; margin-top: 12px; }
</style>
