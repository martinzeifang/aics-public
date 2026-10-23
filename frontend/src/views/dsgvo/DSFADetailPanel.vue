<template>
  <div class="dsfa-detail">
    <div class="dsfa-head">
      <h3>DSFA „{{ dpia?.titel || dpia?.dpia_id }}" — Art. 35 DSGVO</h3>
      <button class="btn-link" @click="$emit('close')">✕ Schließen</button>
    </div>

    <!-- Schritt-/Fortschritts-Anzeige (DS7 #1107) -->
    <ol class="stepper">
      <li
        v-for="(s, i) in STEPS"
        :key="s.key"
        :class="{ active: s.key === activeStep, done: stepDone(s.key), clickable: true }"
        @click="goStep(s.key)"
      >
        <span class="step-no">{{ i + 1 }}</span>
        <span class="step-label">{{ s.label }}</span>
      </li>
    </ol>
    <div class="progress-bar"><div class="progress-fill" :style="{ width: progressPct + '%' }"></div></div>

    <p v-if="loading" class="muted">Lade DSFA …</p>

    <!-- 1) Schwellwertanalyse (DS5) — Art. 35 Abs. 1/3/4 -->
    <section v-show="activeStep === 'schwellwert'" class="block">
      <h4>1. Schwellwertanalyse (Art. 35 Abs. 1/3/4)</h4>
      <div class="help-box" v-if="kriterien?.hinweis">{{ kriterien.hinweis }}</div>

      <fieldset class="crit-group">
        <legend>Art. 35 Abs. 3 — Regelbeispiele (je einzeln DSFA-pflichtig)</legend>
        <label v-for="c in kriterien?.art35_3 || []" :key="c.id" class="crit">
          <input type="checkbox" :value="c.id" v-model="sw.art35_3" /> {{ c.label }}
        </label>
      </fieldset>

      <fieldset class="crit-group">
        <legend>EDSA/DSK-9-Kriterien (ab 2 erfüllt ⇒ DSFA i. d. R. erforderlich)</legend>
        <label v-for="c in kriterien?.edsa_9 || []" :key="c.id" class="crit">
          <input type="checkbox" :value="c.id" v-model="sw.edsa_9" /> {{ c.label }}
        </label>
      </fieldset>

      <fieldset class="crit-group">
        <legend>Listen der Aufsichtsbehörde (Art. 35 Abs. 4/5)</legend>
        <label class="crit"><input type="checkbox" v-model="sw.muss_liste" /> Steht auf der Positivliste (Muss-Liste, Abs. 4) — löst DSFA aus</label>
        <label class="crit"><input type="checkbox" v-model="sw.ausnahme_liste" /> Steht auf der Ausnahmeliste (Negativliste, Abs. 5) — schließt DSFA aus</label>
      </fieldset>

      <label class="field">
        <span>Dokumentierte Begründung</span>
        <textarea v-model="sw.begruendung" rows="3" placeholder="Begründung der Entscheidung (wird mit dokumentiert)"></textarea>
      </label>

      <div class="result" :class="swResultClass">
        <strong>Ergebnis:</strong>
        {{ swErforderlich ? 'DSFA erforderlich' : 'DSFA nicht erforderlich' }}
        <p class="muted" v-if="swBegruendungAuto">{{ swBegruendungAuto }}</p>
      </div>

      <div class="actions">
        <button class="btn-primary" :disabled="busy" @click="speichereSchwellwert">Schwellwert speichern</button>
      </div>
    </section>

    <!-- 2) Beschreibung der Verarbeitung (Art. 35 Abs. 7 lit. a) -->
    <section v-show="activeStep === 'beschreibung'" class="block">
      <h4>2. Systematische Beschreibung der Verarbeitung (Art. 35 Abs. 7 lit. a)</h4>
      <label class="field">
        <span>Beschreibung der Verarbeitungsvorgänge und -zwecke</span>
        <textarea v-model="local.beschreibung_verarbeitung" rows="6"></textarea>
      </label>
      <div class="actions"><button class="btn-primary" :disabled="busy" @click="speichereLokal">Speichern</button></div>
    </section>

    <!-- 3) Notwendigkeit / Verhältnismäßigkeit (Art. 35 Abs. 7 lit. b) -->
    <section v-show="activeStep === 'notwendigkeit'" class="block">
      <h4>3. Notwendigkeit &amp; Verhältnismäßigkeit (Art. 35 Abs. 7 lit. b)</h4>
      <div class="help-box">Bleibt lokal im DSGVO-Modul.</div>
      <label class="field">
        <span>Bewertung der Notwendigkeit und Verhältnismäßigkeit</span>
        <textarea v-model="local.notwendigkeit_grund" rows="5"></textarea>
      </label>
      <div class="actions"><button class="btn-primary" :disabled="busy" @click="speichereLokal">Speichern</button></div>
    </section>

    <!-- 4) Risiken (Art. 35 Abs. 7 lit. c) — READ-ONLY aus verknüpftem rb_projekt -->
    <section v-show="activeStep === 'risiko'" class="block">
      <div class="rb-head">
        <h4>4. Risiken für Rechte/Freiheiten (Art. 35 Abs. 7 lit. c)</h4>
        <a
          v-if="link?.rb_projekt_id"
          class="btn-primary jump"
          :href="`#/risikobewertung?projekt=${encodeURIComponent(link.rb_projekt_id)}`"
          :title="`Verknüpfte Risikobewertung „${link.rb_projekt_id}“ öffnen`"
        >↗ In Risikobewertung öffnen</a>
      </div>
      <div class="help-box">
        Read-only. Bearbeitung erfolgt in der verknüpften Risikobewertung
        <code v-if="link?.rb_projekt_id">{{ link.rb_projekt_id }}</code>
        (Framework {{ link?.framework || 'DSGVO-DSFA' }}).
      </div>

      <p v-if="!link?.rb_projekt_id" class="muted">Keine verknüpfte Risikobewertung gefunden.</p>
      <p v-else-if="!link.risiken?.length" class="muted">
        Noch keine Risiken erfasst. Über „In Risikobewertung öffnen" anlegen.
      </p>
      <table v-else>
        <thead>
          <tr>
            <th>Nr.</th>
            <th>c) Bedrohung für Rechte/Freiheiten</th>
            <th>Wahrsch.</th>
            <th>Schwere</th>
            <th>d) Abhilfemaßnahme</th>
            <th>Risiko</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in link.risiken" :key="r.id" :class="{ resolved: r.is_resolved }">
            <td>{{ r.nr }}</td>
            <td>{{ r.bedrohung_rechte_freiheiten || r.risk_name || '—' }}</td>
            <td>{{ r.eintrittswahrscheinlichkeit || '—' }}</td>
            <td>{{ r.schwere || '—' }}</td>
            <td>{{ r.massnahme || '—' }}</td>
            <td><span class="risk-pill">{{ r.risiko_label || '—' }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 5) Maßnahmen + Restrisiko (Art. 35 Abs. 7 lit. d) -->
    <section v-show="activeStep === 'massnahmen'" class="block">
      <h4>5. Abhilfemaßnahmen &amp; Restrisiko (Art. 35 Abs. 7 lit. d)</h4>
      <label class="field">
        <span>Zusammenfassung der Abhilfemaßnahmen</span>
        <textarea v-model="local.massnahmen" rows="4"></textarea>
      </label>
      <label class="field">
        <span>Verbleibendes Restrisiko</span>
        <select v-model="local.restrisiko">
          <option value="niedrig">niedrig</option>
          <option value="mittel">mittel</option>
          <option value="hoch">hoch</option>
        </select>
      </label>
      <div class="result" :class="local.restrisiko === 'hoch' ? 'erf' : 'nicht'">
        <strong v-if="local.restrisiko === 'hoch'">Restrisiko hoch ⇒ Konsultation der Aufsichtsbehörde nach Art. 36 erforderlich.</strong>
        <span v-else>Restrisiko vertretbar — keine Art.-36-Konsultation zwingend.</span>
      </div>
      <div class="actions"><button class="btn-primary" :disabled="busy" @click="speichereLokal">Speichern</button></div>
    </section>

    <!-- 6) Konsultation (Art. 36) -->
    <section v-show="activeStep === 'konsultation'" class="block">
      <h4>6. Konsultation der Aufsichtsbehörde (Art. 36)</h4>
      <div class="help-box">Bleibt lokal im DSGVO-Modul.</div>
      <div class="result" :class="art36Required ? 'erf' : 'nicht'">
        <strong>{{ art36Required ? 'Konsultation Art. 36 erforderlich (Restrisiko hoch).' : 'Konsultation Art. 36 derzeit nicht zwingend.' }}</strong>
      </div>
      <label class="field">
        <span>Konsultation Datenschutzbeauftragte/r (Art. 35 Abs. 2)</span>
        <textarea v-model="local.konsultation_dsb" rows="3"></textarea>
      </label>
      <label class="crit">
        <input type="checkbox" v-model="local.konsultation_aufsicht" />
        Aufsichtsbehörde wurde konsultiert (Art. 36)
      </label>
      <div class="actions"><button class="btn-primary" :disabled="busy" @click="speichereLokal">Speichern</button></div>
    </section>

    <!-- 7) Freigabe + Review (Art. 35 Abs. 11) -->
    <section v-show="activeStep === 'freigabe'" class="block">
      <h4>7. Freigabe &amp; Review (Art. 35 Abs. 11)</h4>
      <label class="field">
        <span>Freigabe durch (Verantwortlicher)</span>
        <input type="text" v-model="local.freigabe_durch" />
      </label>
      <label class="field">
        <span>Freigabe-Datum</span>
        <input type="date" v-model="local.freigabe_datum" />
      </label>
      <label class="field">
        <span>Nächstes Review (Art. 35 Abs. 11)</span>
        <input type="date" v-model="local.naechstes_review" />
      </label>
      <label class="field">
        <span>Status</span>
        <select v-model="local.status">
          <option value="in-bearbeitung">in Bearbeitung</option>
          <option value="abgeschlossen">abgeschlossen</option>
          <option value="freigegeben">freigegeben</option>
        </select>
      </label>
      <div class="actions"><button class="btn-primary" :disabled="busy" @click="speichereLokal">Speichern</button></div>
    </section>

    <!-- Navigation -->
    <div class="nav">
      <button class="btn-link" :disabled="stepIndex === 0" @click="prevStep">‹ Zurück</button>
      <span class="muted">Schritt {{ stepIndex + 1 }} / {{ STEPS.length }}</span>
      <button class="btn-primary" :disabled="stepIndex === STEPS.length - 1" @click="nextStep">Weiter ›</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, reactive } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'

const props = defineProps<{ dpia: any }>()
defineEmits<{ (e: 'close'): void }>()

const store = useDsgvoStore()
const link = ref<any | null>(null)
const kriterien = ref<any | null>(null)
const loading = ref(false)
const busy = ref(false)
const activeStep = ref('schwellwert')

const STEPS = [
  { key: 'schwellwert', label: 'Schwellwert' },
  { key: 'beschreibung', label: 'Beschreibung' },
  { key: 'notwendigkeit', label: 'Notwendigkeit' },
  { key: 'risiko', label: 'Risiko' },
  { key: 'massnahmen', label: 'Maßnahmen/Restrisiko' },
  { key: 'konsultation', label: 'Konsultation (Art. 36)' },
  { key: 'freigabe', label: 'Freigabe/Review' },
]

// Schwellwert-Formular (DS5)
const sw = reactive<any>({
  art35_3: [], edsa_9: [], muss_liste: false, ausnahme_liste: false, begruendung: '',
})
const swErgebnis = ref<any | null>(null)

// Lokale Art.-35-Felder (bleiben im dsgvo_dpia)
const local = reactive<any>({
  beschreibung_verarbeitung: '', notwendigkeit_grund: '', massnahmen: '',
  restrisiko: 'niedrig', konsultation_dsb: '', konsultation_aufsicht: false,
  freigabe_durch: '', freigabe_datum: '', naechstes_review: '', status: 'in-bearbeitung',
})

const stepIndex = computed(() => STEPS.findIndex(s => s.key === activeStep.value))
const progressPct = computed(() => Math.round(((stepIndex.value + 1) / STEPS.length) * 100))

const swErforderlich = computed(() =>
  !!(sw.art35_3.length || sw.muss_liste || sw.edsa_9.length >= 2) && !swExcluded.value)
const swExcluded = computed(() =>
  sw.ausnahme_liste && !sw.art35_3.length && !sw.muss_liste)
const swResultClass = computed(() => (swErforderlich.value ? 'erf' : 'nicht'))
const swBegruendungAuto = computed(() => swErgebnis.value?.begruendung_auto || '')

const art36Required = computed(() =>
  Number(link.value?.art36_required) === 1 || local.restrisiko === 'hoch')

const stepDone = (key: string) => {
  if (key === 'schwellwert') return !!swErgebnis.value?.ergebnis || !!link.value?.schwellwert?.ergebnis
  if (key === 'beschreibung') return !!local.beschreibung_verarbeitung
  if (key === 'notwendigkeit') return !!local.notwendigkeit_grund
  if (key === 'risiko') return !!(link.value?.risiken?.length)
  if (key === 'massnahmen') return !!local.massnahmen
  if (key === 'konsultation') return !!local.konsultation_dsb || !!local.konsultation_aufsicht
  if (key === 'freigabe') return !!local.freigabe_durch
  return false
}

const goStep = (key: string) => { activeStep.value = key }
const nextStep = () => { if (stepIndex.value < STEPS.length - 1) activeStep.value = STEPS[stepIndex.value + 1].key }
const prevStep = () => { if (stepIndex.value > 0) activeStep.value = STEPS[stepIndex.value - 1].key }

const hydrateLocal = () => {
  local.beschreibung_verarbeitung = link.value?.beschreibung_verarbeitung || props.dpia?.beschreibung_verarbeitung || ''
  local.notwendigkeit_grund = link.value?.notwendigkeit_grund || props.dpia?.notwendigkeit_grund || ''
  local.massnahmen = link.value?.massnahmen ?? props.dpia?.massnahmen ?? ''
  local.restrisiko = link.value?.restrisiko || props.dpia?.restrisiko || 'niedrig'
  local.konsultation_dsb = link.value?.konsultation_dsb ?? props.dpia?.konsultation_dsb ?? ''
  local.konsultation_aufsicht = Number(link.value?.konsultation_aufsicht ?? props.dpia?.konsultation_aufsicht) === 1
  local.freigabe_durch = link.value?.freigabe_durch ?? props.dpia?.freigabe_durch ?? ''
  local.freigabe_datum = link.value?.freigabe_datum || props.dpia?.freigabe_datum || ''
  local.naechstes_review = link.value?.naechstes_review || props.dpia?.naechstes_review || ''
  local.status = props.dpia?.status || 'in-bearbeitung'
  // Schwellwert-Formular aus persistiertem Ergebnis befüllen
  const s = link.value?.schwellwert || {}
  sw.art35_3 = Array.isArray(s.art35_3) ? [...s.art35_3] : []
  sw.edsa_9 = Array.isArray(s.edsa_9) ? [...s.edsa_9] : []
  sw.muss_liste = !!s.muss_liste
  sw.ausnahme_liste = !!s.ausnahme_liste
  sw.begruendung = s.begruendung || ''
  swErgebnis.value = s.ergebnis ? s : null
}

const load = async () => {
  if (!props.dpia?.id) return
  loading.value = true
  if (!kriterien.value) kriterien.value = await store.fetchSchwellwertKriterien()
  link.value = await store.fetchDsfaRiskLink(props.dpia.id)
  hydrateLocal()
  if (link.value?.stage) activeStep.value = link.value.stage
  loading.value = false
}

const speichereSchwellwert = async () => {
  if (!props.dpia?.id) return
  busy.value = true
  const res = await store.saveDsfaSchwellwert(props.dpia.id, {
    art35_3: sw.art35_3, edsa_9: sw.edsa_9,
    muss_liste: sw.muss_liste, ausnahme_liste: sw.ausnahme_liste,
    begruendung: sw.begruendung,
  })
  if (res?.schwellwert) {
    swErgebnis.value = res.schwellwert
    link.value = await store.fetchDsfaRiskLink(props.dpia.id)
  }
  busy.value = false
}

const speichereLokal = async () => {
  if (!props.dpia?.id) return
  busy.value = true
  // bestehende DSFA-Felder erhalten, lokale Werte überschreiben (Risiko c/d bleiben im RB-Projekt)
  await store.saveDpia({
    ...props.dpia,
    id: props.dpia.id,
    dpia_id: props.dpia.dpia_id,
    titel: props.dpia.titel,
    beschreibung_verarbeitung: local.beschreibung_verarbeitung,
    notwendigkeit_grund: local.notwendigkeit_grund,
    massnahmen: local.massnahmen,
    restrisiko: local.restrisiko,
    konsultation_dsb: local.konsultation_dsb,
    konsultation_aufsicht: local.konsultation_aufsicht,
    freigabe_durch: local.freigabe_durch,
    freigabe_datum: local.freigabe_datum,
    naechstes_review: local.naechstes_review,
    status: local.status,
    stage: activeStep.value,
  })
  await store.setDsfaStage(props.dpia.id, activeStep.value)
  link.value = await store.fetchDsfaRiskLink(props.dpia.id)
  busy.value = false
}

watch(() => props.dpia?.id, load)
onMounted(load)
</script>

<style scoped>
.dsfa-detail { border: 1px solid #cfd8dc; border-radius: 8px; padding: 16px; margin-top: 12px; background: #fafafa; }
.dsfa-head { display: flex; justify-content: space-between; align-items: center; }
.dsfa-head h3 { margin: 0; font-size: 1.05rem; color: #1565c0; }
.block { margin-top: 16px; }
.block h4 { margin: 0 0 8px; color: #37474f; }
.rb-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.help-box { background: #e3f2fd; border-left: 4px solid #1565c0; padding: 8px 12px; border-radius: 4px; margin: 8px 0; font-size: 0.88rem; }

/* Stepper */
.stepper { list-style: none; display: flex; flex-wrap: wrap; gap: 4px; padding: 0; margin: 12px 0 6px; }
.stepper li { display: flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 16px; background: #eceff1; font-size: 0.8rem; color: #607d8b; }
.stepper li.clickable { cursor: pointer; }
.stepper li.done { background: #c8e6c9; color: #2e7d32; }
.stepper li.active { background: #1565c0; color: #fff; }
.step-no { display: inline-flex; width: 18px; height: 18px; align-items: center; justify-content: center; border-radius: 50%; background: rgba(0,0,0,0.08); font-weight: 700; }
.stepper li.active .step-no { background: rgba(255,255,255,0.25); }
.progress-bar { height: 5px; background: #e0e0e0; border-radius: 3px; overflow: hidden; margin-bottom: 8px; }
.progress-fill { height: 100%; background: #1565c0; transition: width 0.2s; }

/* Forms */
.crit-group { border: 1px solid #e0e0e0; border-radius: 6px; padding: 10px 12px; margin: 10px 0; }
.crit-group legend { font-weight: 600; color: #455a64; font-size: 0.85rem; padding: 0 6px; }
.crit { display: block; margin: 5px 0; font-size: 0.88rem; }
.field { display: block; margin: 10px 0; }
.field > span { display: block; font-weight: 600; color: #455a64; font-size: 0.85rem; margin-bottom: 3px; }
.field textarea, .field input, .field select { width: 100%; box-sizing: border-box; padding: 6px 8px; border: 1px solid #cfd8dc; border-radius: 4px; font-family: inherit; }
.result { margin: 10px 0; padding: 8px 12px; border-radius: 4px; font-size: 0.9rem; }
.result.erf { background: #ffebee; border-left: 4px solid #b71c1c; }
.result.nicht { background: #e8f5e9; border-left: 4px solid #2e7d32; }
.actions { margin-top: 10px; }
.nav { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; padding-top: 10px; border-top: 1px solid #e0e0e0; }

table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.88rem; }
th, td { border: 1px solid #e0e0e0; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #eceff1; }
tr.resolved { opacity: 0.55; text-decoration: line-through; }
.risk-pill { display: inline-block; padding: 2px 8px; border-radius: 10px; background: #b71c1c; color: #fff; font-size: 0.78rem; }
.muted { color: #78909c; font-style: italic; }
.btn-primary { background: #1565c0; color: #fff; border: none; border-radius: 4px; padding: 6px 12px; cursor: pointer; text-decoration: none; font-size: 0.85rem; }
.btn-primary:disabled { opacity: 0.5; cursor: default; }
.btn-primary.jump:hover { background: #0d47a1; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; }
.btn-link:disabled { opacity: 0.4; cursor: default; }
code { background: #eceff1; padding: 1px 4px; border-radius: 3px; }
</style>
