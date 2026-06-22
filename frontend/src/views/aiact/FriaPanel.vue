<template>
  <div class="fria-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein AI-Act-Projekt auswählen.</p>

    <template v-else-if="rec">
      <div class="fria-toolbar">
        <div class="toolbar-info">
          <strong>⚖️ Art. 27 — Grundrechte-Folgenabschätzung (FRIA)</strong>
          <span class="muted">Status: {{ rec.status }} · Stufe: {{ rec.stage }}</span>
        </div>
      </div>

      <!-- Pflicht-Trigger -->
      <div class="trigger" :class="store.trigger?.required ? 'trig-on' : 'trig-off'" v-if="store.trigger">
        <strong v-if="store.trigger.required">🔴 FRIA-Pflicht ausgelöst</strong>
        <strong v-else>⚪ Keine FRIA-Pflicht erkannt</strong>
        <span class="muted">
          Risk-Tier: {{ store.trigger.risk_tier }} ·
          Betreiber: {{ store.trigger.betreiber_pflicht ? 'FRIA-pflichtig' : 'nicht pflichtig' }}
        </span>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>

      <!-- Stepper-Navigation -->
      <div class="stepper">
        <button v-for="(s, i) in steps" :key="s.key"
                :class="['step', { active: stageIdx === i, done: i < stageIdx }]"
                @click="goStep(i)">
          {{ i + 1 }}. {{ s.label }}
        </button>
      </div>

      <section class="card">
        <!-- 1. Betreiber -->
        <template v-if="curStep.key === 'betreiber'">
          <h4>Betreiber-Typ (Trigger)</h4>
          <label class="full">FRIA-pflichtiger Betreiber?
            <select v-model="rec.betreiber_typ" @change="onBetreiberChange">
              <option v-for="b in store.betreiberTypen" :key="b.code" :value="b.code">{{ b.label }}</option>
            </select>
          </label>
        </template>

        <!-- 2. Prozesse -->
        <template v-else-if="curStep.key === 'prozesse'">
          <h4>Nutzungsprozesse (Art. 27(1)a)</h4>
          <textarea v-model="rec.nutzungsprozesse" rows="3" placeholder="Wie wird das System eingesetzt?"></textarea>
          <h4>Zeitraum & Häufigkeit (Art. 27(1)b)</h4>
          <textarea v-model="rec.zeitraum_frequenz" rows="2"></textarea>
        </template>

        <!-- 3. Betroffene -->
        <template v-else-if="curStep.key === 'betroffene'">
          <h4>Betroffene Personengruppen (Art. 27(1)c)</h4>
          <textarea v-model="rec.betroffene_gruppen" rows="3"></textarea>
        </template>

        <!-- 4. Risiken -->
        <template v-else-if="curStep.key === 'risiken'">
          <h4>Spezifische Schadensrisiken (Art. 27(1)d)</h4>
          <div v-for="(r, i) in rec.schadensrisiken" :key="i" class="risk-row">
            <input v-model="rec.schadensrisiken[i]" />
            <button class="btn-small danger" @click="rec.schadensrisiken.splice(i, 1)">🗑️</button>
          </div>
          <button class="btn-secondary" @click="rec.schadensrisiken.push('')">➕ Risiko</button>
        </template>

        <!-- 5. Maßnahmen -->
        <template v-else-if="curStep.key === 'massnahmen'">
          <h4>Menschliche Aufsicht (Art. 27(1)e)</h4>
          <textarea v-model="rec.oversight_massnahmen" rows="2"></textarea>
          <h4>Maßnahmen bei Risikoeintritt (Art. 27(1)f)</h4>
          <textarea v-model="rec.massnahmen_bei_risiko" rows="2"></textarea>
          <h4>Governance</h4>
          <textarea v-model="rec.governance" rows="2"></textarea>
          <h4>Beschwerdemechanismus</h4>
          <textarea v-model="rec.beschwerdemechanismus" rows="2"></textarea>
        </template>

        <!-- 6. Mitteilung -->
        <template v-else-if="curStep.key === 'mitteilung'">
          <h4>Mitteilung an die Marktüberwachungsbehörde (Art. 27(3))</h4>
          <label class="full">Behörde<input v-model="rec.behoerde" /></label>
          <p class="muted" v-if="rec.mitteilung_behoerde_am">Gemeldet am: {{ rec.mitteilung_behoerde_am }}</p>
          <div class="row">
            <a class="btn-secondary" :href="exportUrl" target="_blank" rel="noopener">📄 Mitteilungs-Template</a>
            <button class="btn-primary" @click="report">📨 Status „an Behörde gemeldet"</button>
          </div>
        </template>

        <div class="row between nav">
          <button class="btn-secondary" :disabled="stageIdx === 0" @click="goStep(stageIdx - 1)">← Zurück</button>
          <button class="btn-primary" :disabled="busy" @click="saveStep">💾 Speichern</button>
          <button class="btn-secondary" :disabled="stageIdx === steps.length - 1" @click="next">Weiter →</button>
        </div>
      </section>

      <section class="card">
        <h4>🤖 KI-Assistent (Vorbefüllung)</h4>
        <div class="row">
          <button class="btn-secondary" @click="copyPrompt">📋 Prompt kopieren</button>
        </div>
        <textarea v-model="wizardResponse" rows="3" placeholder="KI-Antwort (JSON) hier einfügen…"></textarea>
        <button class="btn-primary" :disabled="!wizardResponse" @click="applyWizard">✨ Übernehmen</button>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { useAiactFriaStore, type FriaRecord } from '../../stores/aiactFria'

const aiact = useAiActStore()
const store = useAiactFriaStore()

const projekt = computed(() => aiact.selectedProjekt)
const rec = ref<FriaRecord | null>(null)
const busy = ref(false)
const message = ref('')
const wizardResponse = ref('')

const steps = [
  { key: 'betreiber', label: 'Betreiber' },
  { key: 'prozesse', label: 'Prozesse' },
  { key: 'betroffene', label: 'Betroffene' },
  { key: 'risiken', label: 'Risiken' },
  { key: 'massnahmen', label: 'Maßnahmen' },
  { key: 'mitteilung', label: 'Mitteilung' },
]

const stageIdx = computed(() => Math.max(0, steps.findIndex(s => s.key === (rec.value?.stage || 'betreiber'))))
const curStep = computed(() => steps[stageIdx.value])

const exportUrl = computed(() =>
  projekt.value
    ? `/api/aiact-fria/projekte/${encodeURIComponent(projekt.value)}/mitteilung/export`
    : '#')

function goStep(i: number) {
  if (!rec.value) return
  rec.value.stage = steps[Math.max(0, Math.min(steps.length - 1, i))].key
}
function next() { goStep(stageIdx.value + 1) }

async function onBetreiberChange() {
  if (!projekt.value || !rec.value) return
  const t = await store.checkTrigger(projekt.value, rec.value.betreiber_typ)
  if (t) store.trigger = t
}

async function load() {
  if (!projekt.value) return
  await store.loadConstants()
  await store.load(projekt.value)
  rec.value = store.record ? { ...store.record, schadensrisiken: [...(store.record.schadensrisiken || [])] } : null
}

async function saveStep() {
  if (!projekt.value || !rec.value) return
  busy.value = true
  try {
    await store.save(projekt.value, rec.value)
    rec.value = store.record ? { ...store.record, schadensrisiken: [...(store.record.schadensrisiken || [])] } : rec.value
    message.value = 'FRIA gespeichert.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally { busy.value = false }
}

async function report() {
  if (!projekt.value || !rec.value) return
  await store.report(projekt.value, rec.value.behoerde)
  await load()
  message.value = 'Als an Behörde gemeldet markiert.'
}

async function copyPrompt() {
  if (!projekt.value) return
  const p = await store.wizardPrompt(projekt.value)
  try { await navigator.clipboard.writeText(p) ; message.value = 'Prompt kopiert.' } catch { /* ignore */ }
}

async function applyWizard() {
  if (!projekt.value) return
  try {
    await store.wizardParse(projekt.value, wizardResponse.value)
    await load()
    wizardResponse.value = ''
    message.value = 'KI-Vorbefüllung übernommen.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Übernahme fehlgeschlagen.'
  }
}

watch(projekt, load, { immediate: true })
</script>

<style scoped>
.fria-panel { padding: 8px 0; }
.hint { color: #607d8b; padding: 16px; }
.fria-toolbar { background: #1565c0; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }
.toolbar-info strong { color: #fff; }
.toolbar-info .muted { color: #90caf9; margin-left: 12px; }
.trigger { padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; display: flex; gap: 12px; align-items: center; }
.trig-on { background: #ffebee; border: 1px solid #ef9a9a; }
.trig-off { background: #eceff1; border: 1px solid #cfd8dc; }
.status-msg { color: #1565c0; margin: 8px 0; }
.stepper { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.step { padding: 6px 12px; border: 1px solid #cfd8dc; border-radius: 16px; background: #fff; cursor: pointer; font-size: 0.85em; }
.step.active { background: #1565c0; color: #fff; border-color: #1565c0; }
.step.done { background: #e8f5e9; border-color: #a5d6a7; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.card h4 { margin: 12px 0 6px; color: #0d47a1; }
.card h4:first-child { margin-top: 0; }
label { display: flex; flex-direction: column; font-size: 0.85em; color: #455a64; gap: 3px; }
label.full { width: 100%; }
input, select, textarea { box-sizing: border-box; width: 100%; padding: 4px 6px; }
.row { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
.row.between { justify-content: space-between; }
.nav { margin-top: 16px; }
.risk-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.muted { color: #78909c; font-size: 0.85em; }
.danger { color: #c62828; }
</style>
