<template>
  <div class="owasp-llm-panel">
    <p v-if="!projekt" class="hint">Bitte zuerst ein AI-Act-Projekt auswählen.</p>

    <template v-else>
      <!-- Toolbar (Pendant zu CRA Repo-Scan/Align-Controls) -->
      <div class="owasp-toolbar">
        <div class="toolbar-info">
          <strong>🛡️ OWASP-LLM-Top-10-Register</strong>
          <span class="muted">{{ evaluated }} / {{ items.length }} bewertet · ø {{ avg.toFixed(1) }} / 5</span>
        </div>
        <div class="toolbar-actions">
          <button class="btn-secondary" :disabled="busy !== ''" @click="detectOpen = true">
            🔍 Repo-Auto-Detect
          </button>
          <button class="btn-secondary" :disabled="busy !== ''" @click="openWizard">
            {{ busy === 'wizard' ? '⏳ Lädt…' : '🤖 KI-Wizard' }}
          </button>
          <!-- Eigener Objektbestand (OWASP-LLM-Kontrollen), deshalb bleibt der
               Knopf in diesem Register — die Beschriftung kommt aus dem
               Katalog, damit sie nicht wieder auseinanderläuft (#1851). -->
          <button class="btn-secondary" :disabled="busy !== '' || !items.length"
                  :title="PROJEKT_AKTIONEN.massenAuto.titel" @click="autoMassOpen = true">
            {{ PROJEKT_AKTIONEN.massenAuto.text }}
          </button>
        </div>
      </div>

      <p v-if="message" class="status-msg">{{ message }}</p>

      <!-- OWASP-Grid (deckungsgleich mit CRA OWASP-SbD) -->
      <div class="owasp-grid">
        <div v-for="c in items" :key="c.id" class="owasp-card"
             @click="editingOwasp = c">
          <div class="owasp-header">
            <span class="owasp-id">{{ c.id }}</span>
            <span class="score-pill" :style="{ background: scoreColor(c.status) }">{{ c.status }}/5</span>
          </div>
          <h4>{{ c.title }}<NeubewertungBadge :text="c.kommentar" /></h4>
          <p class="owasp-desc">{{ truncate(c.hint, 150) }}</p>
          <div class="owasp-meta">
            <span class="evidence-count">📎 {{ (c.evidence || []).length }} Evidence</span>
            <span v-if="c.maps_to?.length" class="cra-articles">
              AI-Act: {{ c.maps_to.slice(0, 2).join(', ') }}{{ c.maps_to.length > 2 ? '…' : '' }}
            </span>
          </div>
        </div>
      </div>
    </template>

    <!-- OWASP-Editor (custom inline, mirror CRA editingOwasp modal) -->
    <div v-if="editingOwasp" class="modal-overlay" @mousedown.self="editingOwasp = null">
      <div class="modal-content owasp-edit-modal">
        <div class="modal-header">
          <h3>{{ editingOwasp.id }}: {{ editingOwasp.title }}</h3>
          <button class="btn-close" @click="editingOwasp = null">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">{{ editingOwasp.hint }}</p>
          <div class="cra-mapping" v-if="editingOwasp.maps_to?.length">
            <strong>AI-Act-Mapping:</strong> {{ editingOwasp.maps_to.join(' · ') }}
          </div>
          <div class="evidence-hint" v-if="editingOwasp.ref">
            <strong>Referenz:</strong>
            <a :href="safeUrl(editingOwasp.ref)" target="_blank" rel="noopener">{{ editingOwasp.ref }}</a>
          </div>

          <!-- #1765: Herkunfts-/Prüfhinweis zur KI-Bewertung. Dieses Panel läuft
               nicht über RequirementActions, braucht den Hinweis aber genauso —
               die Bewertung landet im Bericht. -->
          <KiHerkunftBadge
            v-if="projekt && editingOwasp.id"
            modul="aiact"
            :projekt="projekt"
            art="owasp_llm"
            :objekt-id="String(editingOwasp.id)"
          />

          <!-- #1564: Risiko für Nichterfüllung → verknüpfte Risikobewertung -->
          <RequirementRiskLinks
            v-if="projekt"
            api-base="/aiact"
            :projekt-name="projekt"
            object-kind="owasp_llm"
            :object-id="String(editingOwasp.id)"
            :titel="editingOwasp.title || ''"
            :score="owaspForm.status"
            :kommentar="owaspForm.kommentar || ''"
          />

          <div class="form-row">
            <label>Status (0-5)</label>
            <input v-model.number="owaspForm.status" type="range" min="0" max="5" />
            <span class="score-display" :style="{ background: scoreColor(owaspForm.status) }">
              {{ owaspForm.status }} – {{ statusLabel(owaspForm.status) }}
            </span>
          </div>
          <div class="form-row">
            <label>Kommentar</label>
            <textarea v-model="owaspForm.kommentar" rows="3"></textarea>
          </div>
          <div class="form-row">
            <label>Evidence (URLs/Pfade, kommagetrennt)</label>
            <textarea v-model="owaspForm.evidenceText" rows="3"
                      placeholder="https://github.com/.../security_utils.py"></textarea>
          </div>

          <!-- #1848: der geteilte KI-Baustein. Vorher stand hier ein Eigenbau mit
               genau einem Knopf — ohne Daten-Vorschau, also ohne wirksame
               Egress-Bestätigung (#1840), und ohne die Markierung
               „⚠️ Neubewertung erforderlich" im Abschnittstitel. -->
          <KiBewertungsBlock
            :adapter="kiAdapter"
            :projekt-name="projekt || ''"
            :objekt="editingOwasp"
            :objekt-id="String(editingOwasp.id)"
            :objekt-titel="`${editingOwasp.id}: ${editingOwasp.title}`"
            :issues="editingOwasp.issues || []"
            :freitext="owaspForm.kommentar"
            :mit-herkunft-badge="false"
            @gespeichert="onKiErgebnis"
            @fehler="(m: string) => (message = m)"
          />

          <!-- #1847: der geteilte Issue-Baustein. Neu dabei: „Bestehendes
               verknüpfen" (fehlte hier ganz) und ein Repo-/Titel-/Body-Formular
               beim Anlegen statt eines Direktaufrufs ohne Rückfrage. -->
          <IssueVerknuepfung
            :api-base="'/aiact'"
            :projekt-name="projekt || ''"
            objekt-pfad="owasp-llm"
            :objekt-id="String(editingOwasp.id)"
            :objekt-titel="String(editingOwasp.id)"
            text-ziel="den Kommentar"
            :vorgeladen="editingOwasp.issues || []"
            @geaendert="onIssueAenderung"
            @uebernommen="onUebernahme"
          />
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="editingOwasp = null">Abbrechen</button>
          <button class="btn-primary" @click="onSaveOwasp">Speichern</button>
        </div>
      </div>
    </div>

    <!-- Repo-Auto-Detect-Dialog (mirror CRA Repo-Scan modal) -->
    <div v-if="detectOpen" class="modal-overlay" @mousedown.self="detectOpen = false">
      <div class="modal-content scan-modal">
        <div class="modal-header">
          <h3>🔍 Repo-Auto-Detect</h3>
          <button class="btn-close" @click="detectOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">Scannt das Repository token-aware auf Sicherheits-Artefakte und hebt
            den Status der LLM-Top-10-Items an, wenn ein konkretes Repo-Artefakt zitierbar ist.</p>
          <div class="form-row">
            <label>Repository (owner/name oder URL)</label>
            <input v-model="detectInput.repo" placeholder="owner/repo (leer = aus Projekt-Meta)" />
          </div>
          <div class="form-row">
            <label>Branch</label>
            <input v-model="detectInput.branch" placeholder="main" />
          </div>
          <div v-if="busy === 'detect'" class="info">⏳ Auto-Detect läuft… (kann dauern)</div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="detectOpen = false">Schließen</button>
          <button class="btn-primary" :disabled="busy === 'detect'" @click="runDetect">
            {{ busy === 'detect' ? 'Lädt…' : 'Auto-Detect starten' }}
          </button>
        </div>
      </div>
    </div>

    <!-- KI-Wizard-Dialog -->
    <div v-if="wizardOpen" class="modal-overlay nested" @mousedown.self="wizardOpen = false">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>🤖 KI-Wizard – OWASP-LLM-Top-10</h3>
          <button class="btn-close" @click="wizardOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">Prompt kopieren, in ChatGPT einfügen, die JSON-Antwort unten einfügen
            und übernehmen.</p>
          <label class="wizard-label">Prompt</label>
          <pre class="prompt-text">{{ wizardPrompt }}</pre>
          <div class="wizard-prompt-actions">
            <button class="btn-small" @click="copyPrompt">📋 Prompt kopieren</button>
            <button class="btn-small" :disabled="wizardRunning || !wizardPrompt"
                    @click="runWizardDirect">⚡ Direkt mit KI ausführen</button>
          </div>
          <!-- #1453: Prompt direkt über den Provider (lokal/Cloud) ausführen statt Copy/Paste.
               Spiegelt das #1366-Muster (CRA AssistentenPanel) — Ergebnis füllt das
               bestehende JSON-Antwortfeld, danach greift die vorhandene Parse-Logik. -->
          <div v-if="wizardRunning" class="ki-run">
            <!-- #1834/#1836/E6: eigene Hinweise auch hier. Die Engine
                 setzt sie serverseitig ein (shared/ki_engine). -->
            <PromptZusatzFeld v-model="zusatz" modul="aiact" :projekt="projekt" bereich="bewertung" />
            <KiStreamView :url="`/api/ai/run-stream`" :confirm-egress="true" :body="{ prompt: wizardPrompt, prompt_zusatz: zusatz }"
                          pipeline
                          @done="onWizardRunDone" @error="onWizardRunError" />
          </div>
          <label class="wizard-label">Antwort (JSON)</label>
          <textarea v-model="wizardResponse" rows="6"
                    placeholder='{"items": [{"id": "LLM01", "status": 3, "kommentar": "…"}]}'></textarea>
          <div v-if="wizardMsg" class="preview">{{ wizardMsg }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="wizardOpen = false">Schließen</button>
          <button class="btn-primary" :disabled="busy === 'wizard' || !wizardResponse.trim()"
                  @click="applyWizard">
            {{ busy === 'wizard' ? 'Übernehme…' : 'Übernehmen' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Import-Modal, Neubewertungs-Modal und Auto-Bewertungs-Dialog stecken
         seit #1847/#1848 in den geteilten Bausteinen im Editor oben. -->
    <AutoMassBewertungModal v-if="autoMassOpen && projekt" :projekt-name="projekt" :adapter="massAdapter"
      @close="autoMassOpen = false" @done="load" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import PromptZusatzFeld from '../../components/shared/PromptZusatzFeld.vue'
import NeubewertungBadge from '../../components/shared/NeubewertungBadge.vue'
import { safeUrl } from '../../utils/safeUrl'  // #1175: Schema-Allowlist für Links
import { useAiActStore } from '../../stores/aiact'
import KiStreamView from '../../components/shared/KiStreamView.vue'
import AutoMassBewertungModal from '../../components/shared/AutoMassBewertungModal.vue'
import { owaspAutoAdapter } from '../../utils/massAdapters'
import RequirementRiskLinks from '../../components/shared/RequirementRiskLinks.vue'
import KiHerkunftBadge from '../../components/shared/KiHerkunftBadge.vue'  // #1765
// #1847/#1848: KI-Bewertung und Issue-Verknüpfung kommen aus den geteilten
// Bausteinen — vorher ~65 Zeilen Eigenbau in dieser Datei.
import IssueVerknuepfung from '../../components/shared/IssueVerknuepfung.vue'
import KiBewertungsBlock from '../../components/shared/KiBewertungsBlock.vue'
import { owaspLlmKiAdapter } from '../../utils/kiBewertung'
import { PROJEKT_AKTIONEN } from '../../utils/aktionen'

const store = useAiActStore()
const projekt = computed(() => store.selectedProjekt)
const items = computed(() => store.owaspLlmItems)

// #1834: eigene Hinweise des Bearbeiters für diesen Lauf.
const zusatz = ref('')
const busy = ref<'' | 'detect' | 'wizard'>('')
const message = ref('')

// #1848: Wertetyp, Endpunkte und — ausdrücklich — welche Einstiege es gibt.
// Für OWASP-LLM ist `prompt` **aus**: Der Wizard ist hier registerweit
// (`…/owasp-llm/wizard/prompt`), einen Prompt je Kontrolle gibt es nicht. Ein
// Knopf ohne Route wäre ein Defekt (#1846), ein Schalter ist eine Aussage.
const kiAdapter = computed(() => owaspLlmKiAdapter(projekt.value || ''))

const STATUS_LABELS = ['Nicht bewertet', 'Nicht vorhanden', 'In Planung', 'Teilweise', 'Weitgehend', 'Vollständig']
function statusLabel(n: number): string { return STATUS_LABELS[n] || String(n) }

// Identische Farb-/Truncate-Helfer wie CRA OWASP-SbD
const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']
const scoreColor = (s: number) => SCORE_COLORS[s] || '#9e9e9e'
const truncate = (s: string, n: number): string => (s && s.length > n) ? s.substring(0, n) + '…' : s

const evaluated = computed(() => items.value.filter((c: any) => (c.status || 0) > 0).length)
const avg = computed(() => {
  const ev = items.value.filter((c: any) => (c.status || 0) > 0)
  if (ev.length === 0) return 0
  return ev.reduce((sum: number, c: any) => sum + (c.status || 0), 0) / ev.length
})

async function load() {
  if (!projekt.value) return
  await store.fetchOwaspLlmRegister()
}
onMounted(load)
watch(projekt, load)

// ── Editor-Modal ────────────────────────────────────────────────────────
const editingOwasp = ref<any | null>(null)
const owaspForm = ref({ status: 0, kommentar: '', evidenceText: '' })

watch(editingOwasp, (c) => {
  if (!c) return
  const evArr = Array.isArray(c.evidence)
    ? c.evidence.map((e: any) => typeof e === 'string' ? e : (e?.url || e?.path || ''))
    : []
  owaspForm.value = {
    status: Number(c.status ?? 0),
    kommentar: c.kommentar ?? '',
    evidenceText: evArr.filter(Boolean).join(', '),
  }
})

async function onSaveOwasp() {
  if (!editingOwasp.value) return
  // saveOwaspLlmStatus persistiert Status + Kommentar; Evidence wird via Backend
  // beim Status-Upsert beibehalten (manuelle Evidence wird über Kommentar/Status
  // gepflegt — die Auto-Detect-/Wizard-Pfade setzen die strukturierte Evidence).
  const ok = await store.saveOwaspLlmStatus(
    editingOwasp.value.id,
    owaspForm.value.status,
    owaspForm.value.kommentar,
  )
  if (ok) {
    message.value = `${editingOwasp.value.id} gespeichert.`
    editingOwasp.value = null
  } else {
    message.value = store.error || 'Speichern fehlgeschlagen.'
  }
}

// #1573: automatische Massenbewertung über den Register-Adapter.
const autoMassOpen = ref(false)
const massAdapter = computed(() => owaspAutoAdapter('/aiact', 'owasp-llm', projekt.value || '',
  items.value.map((c: any) => ({ id: c.id, title: c.title, score: c.status, kommentar: c.kommentar }))))

/**
 * Nach einem KI-Lauf: Register neu laden und das Editor-Objekt neu binden.
 * Das Formular muss mitkommen — die KI hat Status und Kommentar
 * **serverseitig** geschrieben, und ein Formular, das noch den alten Stand
 * zeigt, überschreibt ihn beim nächsten „Speichern".
 */
async function onKiErgebnis() {
  await load()
  if (editingOwasp.value) refreshEditing(editingOwasp.value.id)
}

/** Der Abgleich kann „⚠️ Neubewertung erforderlich" geschrieben haben (#1850). */
const onIssueAenderung = () => onKiErgebnis()

const onUebernahme = (ergebnis: any) => {
  if (ergebnis?.kommentar !== undefined) owaspForm.value.kommentar = ergebnis.kommentar
  message.value = 'Issue-Inhalt übernommen (Status unverändert).'
  return onKiErgebnis()
}

// Editor-Objekt nach Store-Reload neu binden (issues/evidence aktualisieren)
function refreshEditing(id: string) {
  const fresh = items.value.find((c: any) => c.id === id)
  if (fresh && editingOwasp.value) editingOwasp.value = fresh
}

// ── Repo-Auto-Detect ────────────────────────────────────────────────────
const detectOpen = ref(false)
const detectInput = ref({ repo: '', branch: 'main' })

async function runDetect() {
  busy.value = 'detect'
  try {
    const res = await store.autodetectOwaspLlm(
      detectInput.value.repo || undefined,
      detectInput.value.branch || undefined,
    )
    message.value = res
      ? `Auto-Detect abgeschlossen: ${res.detected ?? res.updated ?? 0} Items erkannt.`
      : (store.error || 'Auto-Detect fehlgeschlagen.')
    if (res) detectOpen.value = false
  } finally { busy.value = '' }
}

// ── KI-Wizard ───────────────────────────────────────────────────────────
const wizardOpen = ref(false)
const wizardPrompt = ref('')
const wizardResponse = ref('')
const wizardMsg = ref('')
const wizardRunning = ref(false)  // #1453: Live-KI-Lauf aktiv?

async function openWizard() {
  busy.value = 'wizard'
  try {
    wizardPrompt.value = await store.owaspLlmWizardPrompt()
    wizardResponse.value = ''
    wizardMsg.value = ''
    wizardRunning.value = false
    wizardOpen.value = true
  } finally { busy.value = '' }
}

function copyPrompt() {
  navigator.clipboard?.writeText(wizardPrompt.value)
  wizardMsg.value = 'Prompt kopiert.'
}

// #1453: Prompt direkt über /api/ai/run-stream ausführen (SSE via KiStreamView).
// Muster aus CRA AssistentenPanel (#1366): das fertige KI-Ergebnis landet im
// JSON-Antwortfeld, danach übernimmt die bestehende applyWizard-Parse-Logik.
function runWizardDirect() {
  wizardMsg.value = ''
  wizardRunning.value = true
}

function onWizardRunDone(p: any) {
  wizardRunning.value = false
  wizardResponse.value = (p?.text || '').trim()
  wizardMsg.value = 'KI-Antwort erhalten — prüfen und „Übernehmen".'
}

// 409 = kein Provider verfügbar (kein stiller Fallback) → Fehler sichtbar machen.
function onWizardRunError(msg: string) {
  wizardRunning.value = false
  wizardMsg.value = msg || 'KI-Ausführung fehlgeschlagen.'
}

async function applyWizard() {
  busy.value = 'wizard'
  try {
    const res = await store.owaspLlmWizardParse(wizardResponse.value, true)
    if (res) {
      wizardMsg.value = `Übernommen: ${res.applied ?? res.count ?? 0} Items.`
      message.value = 'KI-Vorschläge übernommen.'
      wizardOpen.value = false
    } else {
      wizardMsg.value = store.error || 'Übernehmen fehlgeschlagen.'
    }
  } finally { busy.value = '' }
}
</script>

<style scoped>
.owasp-llm-panel { padding: 4px 0; }
.hint { color: #607d8b; padding: 16px 0; }
.status-msg { background: #e8f5e9; color: #2e7d32; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; margin: 0 0 12px; }
.muted { color: #888; font-size: 12px; }

/* Toolbar (Pendant zu CRA Repo-Scan/Align-Controls) */
.owasp-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 14px;
}
.toolbar-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.toolbar-info strong { color: #1565c0; font-size: 15px; }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }

/* OWASP-Grid (1:1 aus CRAView.vue) */
.owasp-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;
}
.owasp-card {
  background: white; border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px;
  padding: 14px; cursor: pointer; transition: all 0.15s;
}
.owasp-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-color: var(--color-primary, #1565c0); }
.owasp-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
}
.owasp-id {
  background: #1565c0; color: white;
  padding: 3px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 700; font-family: monospace;
}
.owasp-card h4 { margin: 0 0 8px; font-size: 14px; }
.owasp-desc { margin: 0 0 8px; font-size: 12px; color: #555; line-height: 1.4; }
.owasp-meta {
  display: flex; justify-content: space-between; gap: 8px;
  font-size: 11px; color: #666; flex-wrap: wrap;
}
.score-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
}

/* Modal (1:1 aus CRAView.vue) */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-overlay.nested { z-index: 1100; }
.modal-content {
  background: white; border-radius: 8px;
  max-width: 700px; width: 95%; max-height: 90vh;
  display: flex; flex-direction: column;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid var(--color-border, #e0e0e0);
}
.modal-header h3 { margin: 0; color: var(--color-primary, #1565c0); font-size: 16px; }
.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 20px; border-top: 1px solid var(--color-border, #e0e0e0);
}

.cra-mapping, .evidence-hint {
  background: #f9f9f9; padding: 8px 12px; border-radius: 4px;
  margin-bottom: 12px; font-size: 12px;
}
.evidence-hint a { color: #1565c0; word-break: break-all; }

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input[type="range"] { width: 70%; vertical-align: middle; }
.form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-size: 13px;
}
.score-display {
  display: inline-block; padding: 4px 12px; border-radius: 4px;
  color: white; font-weight: 600; min-width: 40px; text-align: center; margin-left: 8px;
}

.issues-section legend {
  padding: 0 6px; font-weight: 600; font-size: 12px;
  color: var(--color-primary, #1565c0); text-transform: uppercase;
}
.issue-state.open { background: #e3f2fd; color: #1565c0; }
.issue-link:hover { text-decoration: underline; color: var(--color-primary, #1565c0); }
.btn-llm:hover:not(:disabled) { background: #1565c0; color: white; }
.btn-tiny:hover:not(:disabled) { background: #ffebee; color: #c62828; border-color: #c62828; }

/* Wizard / Scan-Dialog */
.scan-modal, .prompt-modal { max-width: 800px; }
.wizard-label { display: block; font-weight: 600; font-size: 13px; margin: 12px 0 4px; }
.prompt-text {
  background: #f5f5f5; padding: 12px; border-radius: 4px; font-size: 12px; line-height: 1.5;
  white-space: pre-wrap; max-height: 40vh; overflow-y: auto; font-family: monospace; border: 1px solid #ddd;
}
.prompt-modal textarea {
  width: 100%; padding: 8px; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px; font-family: monospace; font-size: 12px; resize: vertical; margin-bottom: 4px;
}
.preview {
  background: #e8f5e9; padding: 10px 14px; border-radius: 4px; margin-top: 12px;
  font-size: 13px; border: 1px solid #81c784;
}
/* #1453: Aktionszeile unter dem Prompt + Live-KI-Lauf */
.wizard-prompt-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.ki-run {
  margin: 10px 0; padding: 10px 12px;
  background: #f5f9ff; border: 1px solid #b3d4f5; border-radius: 6px;
}
.info {
  background: #fff8e1; color: #e65100; padding: 8px 12px;
  border-radius: 4px; font-size: 13px; border: 1px solid #ffd54f; margin: 12px 0;
}

.btn-primary, .btn-secondary, .btn-small {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
  text-decoration: none; display: inline-block;
}
.btn-primary { background: var(--color-primary, #1565c0); color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-small {
  padding: 5px 10px; background: white;
  border: 1px solid var(--color-border, #e0e0e0); font-size: 12px;
}
</style>
