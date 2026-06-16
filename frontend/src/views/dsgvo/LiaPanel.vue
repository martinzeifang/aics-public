<template>
  <div class="lia-panel">
    <div class="intro-banner">
      <strong>⚖️ LIA-Register (Art. 6(1)(f))</strong>
      <p class="hint">Geführter Drei-Stufen-Interessenabwägungstest je Verarbeitung:
        Zweck-/Legitimitäts-Test → Erforderlichkeit → Abwägung → Ergebnis.</p>
    </div>

    <div v-if="!projektName" class="hint">Bitte zuerst ein Projekt auswählen.</div>
    <template v-else>
      <button class="btn-primary" @click="openNew">➕ Neue Interessenabwägung</button>
      <p v-if="store.error" class="msg err">{{ store.error }}</p>

      <table v-if="store.items.length" class="grid">
        <thead>
          <tr><th>LIA-ID</th><th>Verarbeitung</th><th>VVT</th><th>Stufe</th><th>Ergebnis</th><th>Review</th><th>Aktionen</th></tr>
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
      <p v-else class="hint">— Keine Interessenabwägungen erfasst —</p>
    </template>

    <!-- Stepper-Editor -->
    <div v-if="editing" class="modal-backdrop" @click.self="editing = null">
      <div class="modal">
        <h3>{{ editing.id ? 'LIA bearbeiten' : 'Neue Interessenabwägung' }}</h3>
        <div class="stepper">
          <span v-for="(s, i) in STAGES" :key="s.key"
            :class="['step', { active: step === i, done: i < step }]" @click="step = i">
            {{ i + 1 }}. {{ s.label }}
          </span>
        </div>

        <div class="step-body">
          <template v-if="step === 0">
            <label>LIA-ID <input v-model="editing.lia_id" placeholder="LIA-VVT-001" /></label>
            <label>VVT-Referenz <input v-model="editing.vvt_ref" /></label>
            <label>Verarbeitung <input v-model="editing.verarbeitung" /></label>
            <label>Zweck <textarea v-model="editing.zweck" rows="2"></textarea></label>
            <label>Berechtigtes Interesse <textarea v-model="editing.berechtigtes_interesse" rows="2"></textarea></label>
            <label class="cb"><input type="checkbox" v-model="legitim" /> Interesse ist legitim</label>
          </template>
          <template v-else-if="step === 1">
            <label>Erforderlichkeit <textarea v-model="editing.erforderlichkeit" rows="2"></textarea></label>
            <label class="cb"><input type="checkbox" v-model="mildereGeprueft" /> Mildere Mittel geprüft</label>
            <label>Ergebnis mildere Mittel <textarea v-model="editing.mildere_mittel_ergebnis" rows="2"></textarea></label>
          </template>
          <template v-else-if="step === 2">
            <label>Interessen/Grundrechte der Betroffenen <textarea v-model="editing.interessen_betroffener" rows="2"></textarea></label>
            <label>Vernünftige Erwartung <textarea v-model="editing.vernuenftige_erwartung" rows="2"></textarea></label>
            <label>Garantien / Opt-out <textarea v-model="editing.garantien_optout" rows="2"></textarea></label>
          </template>
          <template v-else>
            <label>Ergebnis
              <select v-model="editing.ergebnis">
                <option value="offen">offen</option>
                <option value="ueberwiegt">Interesse überwiegt — tragfähig</option>
                <option value="ueberwiegt_nicht">Betroffene überwiegen — neue Rechtsgrundlage nötig</option>
              </select>
            </label>
            <label>Begründung <textarea v-model="editing.ergebnis_begruendung" rows="2"></textarea></label>
            <label>Reviewer <input v-model="editing.reviewer" /></label>
            <label>Review-Datum <input v-model="editing.review_datum" type="date" /></label>
            <label>Review-Zyklus (Monate) <input v-model.number="editing.review_zyklus_monate" type="number" min="0" /></label>
          </template>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" :disabled="step === 0" @click="step--">← Zurück</button>
          <button class="btn-secondary" :disabled="step === STAGES.length - 1" @click="step++">Weiter →</button>
          <button class="btn-primary" @click="save">💾 Speichern</button>
          <button class="btn-secondary" @click="editing = null">Abbrechen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useDsgvoLiaStore, type Lia } from '../../stores/dsgvoLia'

const props = defineProps<{ projektName: string | null }>()
const store = useDsgvoLiaStore()

const STAGES = [
  { key: 'zweck', label: 'Zweck-Test' },
  { key: 'erforderlichkeit', label: 'Erforderlichkeit' },
  { key: 'abwaegung', label: 'Abwägung' },
  { key: 'ergebnis', label: 'Ergebnis' },
]

const editing = ref<Partial<Lia> | null>(null)
const step = ref(0)
const legitim = ref(false)
const mildereGeprueft = ref(false)

const ergebnisLabel = (e: string) =>
  ({ ueberwiegt: 'überwiegt', ueberwiegt_nicht: 'überwiegt nicht', offen: 'offen' } as any)[e] || e

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
