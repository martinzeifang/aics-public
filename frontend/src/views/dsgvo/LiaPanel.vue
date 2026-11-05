<template>
  <div class="lia-panel">
    <div class="intro-banner">
      <strong>{{ $t('dsgvo.liaPanel.lIARegisterArtF') }}</strong>
      <p class="hint">{{ $t('dsgvo.liaPanel.gefuhrterDreiStufenInteressenabwagun') }}</p>
    </div>

    <div v-if="!projektName" class="hint">{{ $t('common.projektWaehlen') }}</div>
    <template v-else>
      <button class="btn-primary" @click="openNew">{{ $t('dsgvo.liaPanel.neueInteressenabwagung') }}</button>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <table v-if="store.items.length" class="grid">
        <thead>
          <tr><th>{{ $t('dsgvo.liaPanel.lIAID') }}</th><th>{{ $t('dsgvo.liaPanel.verarbeitung') }}</th><th>{{ $t('dsgvo.liaPanel.vVT') }}</th><th>{{ $t('common.stufe') }}</th><th>{{ $t('common.ergebnis') }}</th><th>{{ $t('dsgvo.liaPanel.review') }}</th><th>{{ $t('common.actions') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="l in store.items" :key="l.id">
            <td>{{ l.lia_id }}</td>
            <td>{{ l.verarbeitung }}</td>
            <td>{{ l.vvt_ref }}</td>
            <td><span class="stage">{{ l.stage }}</span></td>
            <td><span class="pill" :class="'pill-' + l.ergebnis">{{ ergebnisLabel(l.ergebnis) }}</span></td>
            <td>{{ l.naechstes_review || '—' }}</td>
            <td class="actions">
              <button class="btn-secondary" @click="openEdit(l)">✏️</button>
              <button class="btn-secondary" @click="store.exportLia(projektName!, l.id, 'docx')">📝</button>
              <button class="btn-secondary" @click="store.exportLia(projektName!, l.id, 'pdf')">📄</button>
              <button class="btn-danger-mini" @click="del(l)">🗑️</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="hint">{{ $t('dsgvo.liaPanel.keineInteressenabwagungenErfasst') }}</p>
    </template>

    <!-- Stepper-Editor -->
    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? $t('dsgvo.liaPanel.lIABearbeiten') : $t('dsgvo.liaPanel.neueInteressenabwagung2') }}</h3>
        <div class="stepper">
          <span v-for="(s, i) in STAGES" :key="s.key"
            :class="['step', { active: step === i, done: i < step }]" @click="step = i">
            {{ i + 1 }}. {{ s.label }}
          </span>
        </div>

        <div class="step-body">
          <template v-if="step === 0">
            <label>{{ $t('dsgvo.liaPanel.lIAID') }} <input v-model="editing.lia_id" placeholder="LIA-VVT-001" /></label>
            <label>{{ $t('common.vVTReferenz') }} <input v-model="editing.vvt_ref" /></label>
            <label>{{ $t('dsgvo.liaPanel.verarbeitung') }} <input v-model="editing.verarbeitung" /></label>
            <label>{{ $t('common.zweck') }} <textarea v-model="editing.zweck" rows="2"></textarea></label>
            <label>{{ $t('dsgvo.liaPanel.berechtigtesInteresse') }} <textarea v-model="editing.berechtigtes_interesse" rows="2"></textarea></label>
            <label class="cb"><input type="checkbox" v-model="legitim" /> {{ $t('dsgvo.liaPanel.interesseIstLegitim') }}</label>
          </template>
          <template v-else-if="step === 1">
            <label>{{ $t('dsgvo.liaPanel.erforderlichkeit') }} <textarea v-model="editing.erforderlichkeit" rows="2"></textarea></label>
            <label class="cb"><input type="checkbox" v-model="mildereGeprueft" /> {{ $t('dsgvo.liaPanel.mildereMittelGepruft') }}</label>
            <label>{{ $t('dsgvo.liaPanel.ergebnisMildereMittel') }} <textarea v-model="editing.mildere_mittel_ergebnis" rows="2"></textarea></label>
          </template>
          <template v-else-if="step === 2">
            <label>{{ $t('dsgvo.liaPanel.interessenGrundrechteDerBetroffenen') }} <textarea v-model="editing.interessen_betroffener" rows="2"></textarea></label>
            <label>{{ $t('dsgvo.liaPanel.vernunftigeErwartung') }} <textarea v-model="editing.vernuenftige_erwartung" rows="2"></textarea></label>
            <label>{{ $t('dsgvo.liaPanel.garantienOptOut') }} <textarea v-model="editing.garantien_optout" rows="2"></textarea></label>
          </template>
          <template v-else>
            <label>{{ $t('common.ergebnis') }}
              <select v-model="editing.ergebnis">
                <option value="offen">{{ $t('cra.pflichtDokuPanel.offen') }}</option>
                <option value="ueberwiegt">{{ $t('dsgvo.liaPanel.interesseUberwiegtTragfahig') }}</option>
                <option value="ueberwiegt_nicht">{{ $t('dsgvo.liaPanel.betroffeneUberwiegenNeueRechtsgrundl') }}</option>
              </select>
            </label>
            <label>{{ $t('common.begruendung') }} <textarea v-model="editing.ergebnis_begruendung" rows="2"></textarea></label>
            <label>{{ $t('common.reviewer') }} <input v-model="editing.reviewer" /></label>
            <label>{{ $t('common.reviewDatum') }} <input v-model="editing.review_datum" type="date" /></label>
            <label>{{ $t('dsgvo.liaPanel.reviewZyklusMonate') }} <input v-model.number="editing.review_zyklus_monate" type="number" min="0" /></label>
          </template>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" :disabled="step === 0" @click="step--">{{ $t('common.zuruck') }}</button>
          <button class="btn-secondary" :disabled="step === STAGES.length - 1" @click="step++">{{ $t('common.weiter') }}</button>
          <button class="btn-primary" @click="save">{{ $t('common.saveIcon') }}</button>
          <button class="btn-secondary" @click="editing = null">{{ $t('common.cancel') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useDsgvoLiaStore, type Lia } from '../../stores/dsgvoLia'
import { t } from '../../i18n'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoLiaStore()

const STAGES = [
  { key: 'zweck', label: t('dsgvo.liaPanel.zweckTest') },
  { key: 'erforderlichkeit', label: t('dsgvo.liaPanel.erforderlichkeit') },
  { key: 'abwaegung', label: t('dsgvo.liaPanel.abwagung') },
  { key: 'ergebnis', label: t('common.ergebnis') },
]

const editing = ref<Partial<Lia> | null>(null)
const step = ref(0)
const legitim = ref(false)
const mildereGeprueft = ref(false)

const ergebnisLabel = (e: string) =>
  ({ ueberwiegt: t('dsgvo.liaPanel.uberwiegt'), ueberwiegt_nicht: t('dsgvo.liaPanel.uberwiegtNicht'), offen: 'offen' } as any)[e] || e

const load = () => { if (props.projektName) store.fetchLia(props.projektName) }

const openNew = () => {
  step.value = 0
  legitim.value = false
  mildereGeprueft.value = false
  editing.value = {
    lia_id: '', vvt_ref: '', verarbeitung: '', zweck: '', berechtigtes_interesse: '',
    erforderlichkeit: '', mildere_mittel_ergebnis: '', interessen_betroffener: '',
    vernuenftige_erwartung: '', garantien_optout: '', ergebnis: 'offen',
    ergebnis_begruendung: '', reviewer: '', review_datum: '', review_zyklus_monate: 12,
  }
}

const openEdit = (l: Lia) => {
  step.value = STAGES.findIndex((s) => s.key === l.stage)
  if (step.value < 0) step.value = 0
  legitim.value = !!l.legitim
  mildereGeprueft.value = !!l.mildere_mittel_geprueft
  editing.value = { ...l }
}

const save = async () => {
  if (!props.projektName || !editing.value) return
  const payload = {
    ...editing.value,
    stage: STAGES[step.value].key,
    legitim: legitim.value ? 1 : 0,
    mildere_mittel_geprueft: mildereGeprueft.value ? 1 : 0,
  }
  if (await store.saveLia(props.projektName, payload)) editing.value = null
}

const del = async (l: Lia) => {
  if (!props.projektName) return
  if (confirm(`LIA ${l.lia_id} löschen?`)) await store.deleteLia(props.projektName, l.id)
}

onMounted(() => { store.fetchConstants(); load() })
watch(() => props.projektName, load)
</script>

<style scoped>
.lia-panel { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
.intro-banner { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 8px; }
.intro-banner .hint { color: #1565c0; font-size: 13px; margin: 4px 0 0; }
.hint { color: #666; font-size: 13px; }
.grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.grid th, .grid td { border: 1px solid var(--color-border, #ddd); padding: 6px 8px; text-align: left; }
.grid th { background: #1565c0; color: white; }
.actions { display: flex; gap: 4px; flex-wrap: wrap; }
.stage { font-size: 12px; color: #607d8b; }
.pill { padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.pill-ueberwiegt { background: #e8f5e9; color: #2e7d32; }
.pill-ueberwiegt_nicht { background: #ffebee; color: #c62828; }
.pill-offen { background: #eceff1; color: #607d8b; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; align-self: flex-start; }
.btn-secondary { background: #e0e0e0; color: #333; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger-mini { background: #ffcdd2; color: #b71c1c; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
.msg { font-size: 13px; }
.msg.err { color: #c62828; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; border-radius: 8px; padding: 20px 24px; width: min(620px, 94vw); max-height: 90vh; overflow-y: auto; }
.modal h3 { color: #1565c0; margin: 0 0 12px; }
.stepper { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.step { font-size: 12px; padding: 4px 10px; border-radius: 12px; background: #eceff1; cursor: pointer; }
.step.active { background: #1565c0; color: white; }
.step.done { background: #c8e6c9; color: #2e7d32; }
.step-body { display: flex; flex-direction: column; gap: 8px; }
.modal label { display: flex; flex-direction: column; font-size: 13px; gap: 2px; }
.modal label.cb { flex-direction: row; align-items: center; gap: 6px; }
.modal input, .modal select, .modal textarea { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.modal-actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
</style>
