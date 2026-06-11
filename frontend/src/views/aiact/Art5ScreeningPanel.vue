<template>
  <div class="art5-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein AI-Act-Projekt auswählen.</p>

    <template v-else>
      <div class="art5-toolbar">
        <div class="toolbar-info">
          <strong>🚫 Art. 5 — Verbots-Screening</strong>
          <span class="muted" v-if="art5.summary">
            {{ art5.summary.gesamt - art5.summary.offen }} / {{ art5.summary.gesamt }} geprüft
          </span>
        </div>
        <div class="toolbar-actions">
          <button class="btn-secondary" :disabled="busy !== ''" @click="openWizard">
            {{ busy === 'wizard' ? '⏳ Lädt…' : '🤖 KI-Vorbewertung' }}
          </button>
          <DownloadButton v-if="projekt" :endpoint="exportEndpoint" filename="art5_screening.md"
            class="btn-secondary">📄 Negativprüfung exportieren</DownloadButton>
        </div>
      </div>

      <!-- Gate-Hinweis -->
      <div v-if="art5.summary?.has_prohibited" class="gate-banner gate-prohibited">
        ⛔ Verbotene Praktik erkannt ({{ (art5.summary.treffer || []).join(', ') }}) —
        Risiko-Klasse wurde automatisch auf <strong>prohibited</strong> gesetzt.
      </div>
      <div v-else-if="art5.summary && !art5.summary.complete" class="gate-banner gate-open">
        ⚠️ Negativprüfung unvollständig: {{ art5.summary.offen }} Tatbestand/-stände noch offen.
        Erst bei vollständiger Prüfung darf das Risk-Tier bestätigt werden.
      </div>
      <div v-else-if="art5.summary" class="gate-banner gate-ok">
        ✅ Keine verbotene Praktik festgestellt — Negativprüfung vollständig dokumentiert.
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>

      <table class="art5-table">
        <thead>
          <tr>
            <th>Tatbestand</th>
            <th>Betroffen</th>
            <th>Begründung</th>
            <th>Geprüft von / am</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in art5.items" :key="t.code" :class="rowClass(t)">
            <td>
              <strong>{{ t.code }}) {{ t.kurz }}</strong>
              <div class="muted ref">{{ t.ref }}</div>
              <div class="muted desc">{{ t.beschreibung }}</div>
            </td>
            <td>
              <select v-model="t.betroffen">
                <option v-for="b in betroffenOptions" :key="b" :value="b">{{ labelBetroffen(b) }}</option>
              </select>
            </td>
            <td>
              <textarea v-model="t.begruendung" rows="2" placeholder="Negativ-/Positivprüfung dokumentieren…"></textarea>
            </td>
            <td class="muted">
              {{ t.geprueft_von || '—' }}<br>{{ t.geprueft_am || '—' }}
            </td>
            <td>
              <button class="btn-small" :disabled="busy !== ''" @click="save(t)">💾</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Wizard-Dialog -->
      <div v-if="wizardOpen" class="modal-overlay" @click.self="wizardOpen = false">
        <div class="modal">
          <h3>🤖 KI-Vorbewertung (Art. 5)</h3>
          <p class="muted">Prompt in ChatGPT einfügen, Antwort (JSON) hier einfügen.</p>
          <label>Prompt</label>
          <textarea class="code" rows="6" readonly :value="wizardPromptText"></textarea>
          <button class="btn-small" @click="copyPrompt">📋 Prompt kopieren</button>
          <label>Antwort (JSON)</label>
          <textarea class="code" rows="6" v-model="wizardResponse" placeholder='{"items":[...]}'></textarea>
          <div class="modal-actions">
            <button class="btn-secondary" @click="wizardOpen = false">Schließen</button>
            <button class="btn-primary" :disabled="busy !== ''" @click="applyWizard">Übernehmen</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import { useAiactArt5Store, type Art5Befund } from '../../stores/aiactArt5'
import DownloadButton from '../../components/shared/DownloadButton.vue'

const store = useAiActStore()
const art5 = useAiactArt5Store()

const projekt = computed(() => store.selectedProjekt)
const busy = ref('')
const message = ref('')
const wizardOpen = ref(false)
const wizardPromptText = ref('')
const wizardResponse = ref('')

const betroffenOptions = computed(() => art5.betroffenWerte.length ? art5.betroffenWerte
  : ['offen', 'ja', 'nein', 'nicht_relevant'])

const exportEndpoint = computed(() => projekt.value
  ? `/aiact-art5/projekte/${encodeURIComponent(projekt.value)}/export` : '')

function labelBetroffen(b: string): string {
  return ({ offen: 'Offen', ja: 'Ja (betroffen)', nein: 'Nein', nicht_relevant: 'Nicht relevant' } as Record<string, string>)[b] || b
}

function rowClass(t: Art5Befund): string {
  if (t.betroffen === 'ja') return 'row-prohibited'
  if (t.betroffen === 'offen') return 'row-open'
  return ''
}

async function load() {
  if (!projekt.value) return
  await art5.loadCatalog()
  await art5.load(projekt.value)
}

async function save(t: Art5Befund) {
  if (!projekt.value) return
  busy.value = 'save'
  message.value = ''
  try {
    await art5.saveBefund(projekt.value, t.code, {
      betroffen: t.betroffen, begruendung: t.begruendung,
    })
    message.value = 'Befund gespeichert.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally { busy.value = '' }
}

async function openWizard() {
  if (!projekt.value) return
  busy.value = 'wizard'
  try {
    wizardPromptText.value = await art5.wizardPrompt(projekt.value)
    wizardResponse.value = ''
    wizardOpen.value = true
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Wizard-Prompt fehlgeschlagen.'
  } finally { busy.value = '' }
}

function copyPrompt() {
  navigator.clipboard?.writeText(wizardPromptText.value)
}

async function applyWizard() {
  if (!projekt.value || !wizardResponse.value.trim()) return
  busy.value = 'wizard-apply'
  try {
    await art5.wizardParse(projekt.value, wizardResponse.value, true)
    wizardOpen.value = false
    message.value = 'KI-Vorbewertung übernommen.'
  } catch (e: any) {
    message.value = e?.response?.data?.error || 'Übernahme fehlgeschlagen.'
  } finally { busy.value = '' }
}

watch(projekt, load, { immediate: true })
</script>

<style scoped>
.art5-panel { padding: 8px 0; }
.hint { color: #607d8b; padding: 16px; }
.art5-toolbar { display: flex; justify-content: space-between; align-items: center;
  background: #1565c0; color: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; }
.toolbar-info strong { color: #fff; }
.toolbar-info .muted { color: #90caf9; margin-left: 12px; }
.toolbar-actions { display: flex; gap: 8px; }
.gate-banner { padding: 12px 16px; border-radius: 8px; margin-bottom: 12px; font-size: 0.95em; }
.gate-prohibited { background: #ffebee; color: #b71c1c; border: 1px solid #ef9a9a; }
.gate-open { background: #fff8e1; color: #8d6e00; border: 1px solid #ffe082; }
.gate-ok { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
.status-msg { color: #1565c0; margin: 8px 0; }
.art5-table { width: 100%; border-collapse: collapse; }
.art5-table th, .art5-table td { text-align: left; padding: 8px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }
.art5-table th { background: #e3f2fd; color: #0d47a1; }
.row-prohibited { background: #fff5f5; }
.row-open { background: #fffdf5; }
.muted { color: #78909c; font-size: 0.85em; }
.ref { font-weight: 600; }
.desc { margin-top: 2px; }
.art5-table textarea, .art5-table select { width: 100%; box-sizing: border-box; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; padding: 20px; border-radius: 8px; width: 640px; max-width: 92vw; max-height: 88vh; overflow: auto; }
.modal label { display: block; margin: 10px 0 4px; font-weight: 600; }
.modal textarea.code { width: 100%; box-sizing: border-box; font-family: Consolas, monospace; font-size: 0.85em; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
</style>
