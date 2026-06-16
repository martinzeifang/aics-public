<template>
  <div class="aiact-assistenten">
    <div class="intro">
      <h3>🤖 AI-Act-Assistenten</h3>
      <p>
        Alle KI-Assistenten und Wizards für die AI-Act-Compliance an einem Ort —
        Risk-Tier-Klassifikation, Use-Case-Templates, EU-DOC/Transparenz,
        Spezial-Wizards (LLM-Card, High-Risk-DOC, Prompt-Injection-Tests …),
        Erweiterungen (Model-Card-Import, OWASP-Watch, Chat, Pre-Market-Check) sowie
        die Wizards für Human-Oversight, Post-Market-Monitoring und das
        OWASP-LLM-Register. Die Pflicht-Doku-Felder selbst bleiben im Reiter
        „📋 Dokumentation".
      </p>
      <p v-if="!store.selectedProjekt" class="hint">
        Bitte zuerst ein AI-Act-Projekt auswählen.
      </p>
    </div>

    <AssistentenKachelGrid
      v-if="store.selectedProjekt"
      ref="grid"
      :wizards="wizards"
      grouped
      :modul="'aiact'"
      :projekt="store.selectedProjekt"
      @open="onOpen"
    />

    <!-- A7: Use-Case-Template anwenden -->
    <div v-if="useCaseOpen" class="wizard-modal-overlay" @mousedown.self="useCaseOpen = false">
      <div class="wizard-modal">
        <h3>⚙️ A7 — Use-Case-Template anwenden</h3>
        <p class="hint">Setzt Defaults für Oversight-Mode + Reporting-SLA passend zum Use-Case.</p>
        <div class="row">
          <select v-model="selectedUseCase">
            <option value="">— Use-Case wählen —</option>
            <option v-for="t in store.useCaseTemplates" :key="t.id" :value="t.id">
              {{ t.name }} ({{ t.tier }})
            </option>
          </select>
          <button class="btn-primary" :disabled="!selectedUseCase" @click="applyUseCase">⚡ Anwenden</button>
        </div>
        <p v-if="useCaseApplied" class="ok-msg">✅ Template <strong>{{ useCaseAppliedName }}</strong> angewendet.</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="useCaseOpen = false">Schließen</button>
        </div>
      </div>
    </div>

    <!-- A20: Model-Card-Importer -->
    <div v-if="modelCardOpen" class="wizard-modal-overlay" @mousedown.self="modelCardOpen = false">
      <div class="wizard-modal">
        <h3>📥 A20 — Model-Card-Importer</h3>
        <p class="hint">System-Doku-Felder werden automatisch aus einer Model-Card (HuggingFace,
          OpenAI, Anthropic) befüllt — ohne ChatGPT-Roundtrip.</p>
        <div class="row" style="gap:8px;">
          <select v-model="modelCard.format">
            <option value="huggingface">HuggingFace (Markdown + YAML)</option>
            <option value="openai">OpenAI (JSON)</option>
            <option value="anthropic">Anthropic (JSON)</option>
            <option value="generic">Generic Markdown</option>
          </select>
          <button class="btn-primary" :disabled="!modelCard.text.trim()" @click="runModelCardImport">📥 Importieren</button>
        </div>
        <textarea v-model="modelCard.text" rows="6" class="mono"
                  placeholder="Model-Card-Text hier einfügen (z.B. HF README.md mit YAML-Frontmatter)..."
                  style="width:100%; margin-top:8px;"></textarea>
        <pre v-if="modelCard.result" class="parsed-result">{{ JSON.stringify(modelCard.result, null, 2) }}</pre>
        <div class="modal-actions">
          <button class="btn-secondary" @click="modelCardOpen = false">Schließen</button>
        </div>
      </div>
    </div>

    <!-- A21: OWASP-LLM-Top-10-Watch -->
    <div v-if="owaspWatchOpen" class="wizard-modal-overlay" @mousedown.self="owaspWatchOpen = false">
      <div class="wizard-modal">
        <h3>🔍 A21 — OWASP-LLM-Top-10-Watch</h3>
        <p class="hint">Live-Status pro OWASP-Kategorie auf Basis der Pflicht-Doku-Felder.</p>
        <button class="btn-primary" @click="refreshOwaspWatch">🔍 Status aktualisieren</button>
        <table v-if="owaspWatch" class="watch-table">
          <thead>
            <tr><th>ID</th><th>Kategorie</th><th>Status</th><th>Hinweis</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in owaspWatch.rows" :key="r.owasp_id">
              <td>{{ r.owasp_id }}</td>
              <td>{{ r.title }}</td>
              <td><span :class="`watch-badge watch-${r.status.replace('.','')}`">{{ r.status }}</span></td>
              <td>{{ r.hint }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="owaspWatch" class="hint">
          ✅ {{ owaspWatch.summary.mitigiert }} mitigiert ·
          ⚠️ {{ owaspWatch.summary.offen }} offen ·
          ⊘ {{ owaspWatch.summary['n.a.'] }} n.a.
        </p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="owaspWatchOpen = false">Schließen</button>
        </div>
      </div>
    </div>

    <!-- A22: AI-Act-Chat -->
    <div v-if="chatOpen" class="wizard-modal-overlay" @mousedown.self="chatOpen = false">
      <div class="wizard-modal">
        <h3>💬 A22 — AI-Act-Chat</h3>
        <p class="hint">Q&amp;A mit vollem Projekt-Kontext. Antwort verweist auf konkrete Artikel/Annex.</p>
        <div class="row" style="gap:8px;">
          <input v-model="chatFrage" placeholder="Deine Frage zum AI-Act..."
                 style="flex:1; padding:7px 10px; border:1px solid #ccc; border-radius:4px;" />
          <button class="btn-primary" :disabled="!chatFrage.trim()" @click="openChatWizard">💬 Prompt generieren</button>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="chatOpen = false">Schließen</button>
        </div>
      </div>
    </div>

    <!-- A23: EU-AI-Office-Reporting -->
    <div v-if="euOfficeOpen" class="wizard-modal-overlay" @mousedown.self="euOfficeOpen = false">
      <div class="wizard-modal">
        <h3>🏛️ A23 — EU-AI-Office-Reporting (Art. 73)</h3>
        <p class="hint">Vollständiger Markdown-Report für signifikante Incidents bei High-Risk-Systemen.</p>
        <div class="form-grid">
          <input v-model="incident.incident_id" placeholder="Incident-ID (optional)" />
          <input v-model="incident.detected_at" placeholder="Eintritt (YYYY-MM-DD HH:MM)" />
          <select v-model="incident.severity">
            <option value="">— Schweregrad —</option>
            <option value="moderat">moderat</option>
            <option value="hoch">hoch</option>
            <option value="kritisch">kritisch (Art. 73(3) — 2 Tage)</option>
          </select>
          <input v-model="incident.affected_subjects" placeholder="Betroffene (z.B. ~200 Endkunden)" />
          <textarea v-model="incident.summary" placeholder="Kurzbeschreibung *" rows="2" />
          <textarea v-model="incident.impact" placeholder="Auswirkung" rows="2" />
          <textarea v-model="incident.immediate_actions" placeholder="Sofortmaßnahmen" rows="2" />
        </div>
        <button class="btn-primary" :disabled="!incident.summary?.trim()" @click="openEuOfficeWizard">
          📝 Prompt generieren
        </button>
        <div class="modal-actions">
          <button class="btn-secondary" @click="euOfficeOpen = false">Schließen</button>
        </div>
      </div>
    </div>

    <!-- A24: Pre-Market-Check -->
    <div v-if="preMarketOpen" class="wizard-modal-overlay" @mousedown.self="preMarketOpen = false">
      <div class="wizard-modal">
        <h3>✅ A24 — Pre-Market-Check</h3>
        <p class="hint">Prüft vor Release, ob alle Pflicht-Belege da sind.</p>
        <button class="btn-primary" @click="refreshPreMarket">✅ Check ausführen</button>
        <div v-if="preMarket" :class="['pre-market-result', preMarket.release_ready ? 'pmr-ok' : 'pmr-fail']">
          <strong v-if="preMarket.release_ready">✅ Release-Ready — alle kritischen Checks bestanden</strong>
          <strong v-else>⛔ NICHT release-ready — {{ preMarket.summary.critical_fail }} kritische Lücken</strong>
          <small>Risk-Tier: {{ preMarket.tier }} · {{ preMarket.summary.passed }}/{{ preMarket.summary.total }} bestanden</small>
          <ul class="check-list">
            <li v-for="c in preMarket.checks" :key="c.key" :class="['check', c.ok ? 'ok' : 'fail', `sev-${c.severity}`]">
              <strong>{{ c.ok ? '✅' : '⛔' }} {{ c.label }}</strong>
              <small v-if="!c.ok">{{ c.hint }}</small>
            </li>
          </ul>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="preMarketOpen = false">Schließen</button>
        </div>
      </div>
    </div>

    <!-- OWASP-LLM-Wizard (KI-Vorschläge) -->
    <div v-if="owaspWizardOpen" class="wizard-modal-overlay" @mousedown.self="owaspWizardOpen = false">
      <div class="wizard-modal">
        <h3>🤖 OWASP-LLM — KI-Vorschläge</h3>
        <p class="hint">1. Prompt kopieren → in ChatGPT/Claude. 2. Antwort hier einfügen → „Übernehmen".
          Die Skala-Werte (0–5) werden im OWASP-LLM-Register gespeichert.</p>
        <label>Prompt</label>
        <textarea readonly :value="owaspWizardPrompt" rows="6" class="mono"></textarea>
        <button class="btn-link" @click="copyOwaspPrompt">📋 Kopieren</button>
        <label>KI-Antwort (JSON)</label>
        <textarea v-model="owaspWizardResponse" rows="6" class="mono"
                  placeholder='{"items": [{"id": "LLM01", "status": 4, "kommentar": "…"}]}'></textarea>
        <div v-if="owaspWizardMsg" class="ok-msg">{{ owaspWizardMsg }}</div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="owaspWizardOpen = false">Abbrechen</button>
          <button class="btn-primary" :disabled="!owaspWizardResponse || owaspBusy" @click="applyOwaspWizard">Übernehmen</button>
        </div>
      </div>
    </div>

    <!-- Prompt-basierter Wizard-Modal (Risk-Tier / EU-DOC / Transparenz / Spezial-Wizards / Chat / EU-Office) -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @mousedown.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <p v-if="isDocOnlyWizard" class="hint">
          1. Prompt nach ChatGPT kopieren. 2. Antwort (Markdown) zurückkopieren.
          3. Auf der Kachel „📄 Als Dokument speichern" einfügen → editier-/exportierbares Dokument.
        </p>
        <p v-else class="hint">1. Prompt nach ChatGPT kopieren. 2. JSON-Antwort hier einfügen. 3. „Parsen + Anwenden".</p>
        <label>Prompt</label>
        <textarea readonly :value="wizardModal.prompt" rows="8" class="mono"></textarea>
        <div style="display:flex; gap:10px; align-items:center;">
          <button class="btn-link" @click="copyPrompt">📋 Kopieren</button>
          <button class="btn-link" :disabled="wizardModal.running" @click="runWizardDirect">⚡ Direkt mit KI ausführen</button>
        </div>
        <div v-if="wizardModal.running" class="ki-run">
          <KiStreamView :url="`/api/ai/run-stream`" :body="{ prompt: wizardModal.prompt }"
                        @done="onWizardRunDone" @error="onWizardRunError" />
        </div>
        <template v-if="!isDocOnlyWizard">
          <label>ChatGPT-Antwort (JSON)</label>
          <textarea v-model="wizardModal.response" rows="6" class="mono" placeholder="JSON hier einfügen..."></textarea>
          <div v-if="wizardModal.parsed" class="parsed-result">
            <strong v-if="wizardModal.parsed.applied" style="color: #2e7d32;">✓ Angewendet + gespeichert</strong>
            <strong v-else style="color: #e65100;">Geparsed (Vorschau)</strong>
            <pre>{{ JSON.stringify(wizardModal.parsed, null, 2) }}</pre>
          </div>
        </template>
        <!-- #1445–#1449: Doc-only-Wizards — Markdown-Ergebnis (Copy/Paste oder
             Direkt-mit-KI) hier ablegen und als Dokument speichern. -->
        <template v-else>
          <label>Ergebnis (Markdown)</label>
          <textarea v-model="wizardModal.response" rows="8" class="mono"
                    placeholder="ChatGPT-Antwort (Markdown) hier einfügen — oder ⚡ Direkt mit KI ausführen nutzen..."></textarea>
        </template>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeWizard">Schließen</button>
          <button v-if="isDocOnlyWizard" class="btn-primary" :disabled="!docSaveText" @click="saveDocFromWizard">📄 Als Dokument speichern</button>
          <button v-if="!isDocOnlyWizard" class="btn-primary" :disabled="!wizardModal.response" @click="parseAndApply">Parsen + Anwenden</button>
        </div>
      </div>
    </div>

    <!-- Simple Wizard-Modal (A4 Human-Oversight / A5 Post-Market-Monitoring) -->
    <div v-if="simpleWizard.open" class="wizard-modal-overlay" @mousedown.self="closeSimpleWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ simpleWizard.title }}</h3>
        <p class="hint">1. Prompt nach ChatGPT kopieren. 2. JSON-Antwort hier einfügen. 3. „Übernehmen".</p>
        <label>Prompt</label>
        <textarea readonly :value="simpleWizard.prompt" rows="8" class="mono"></textarea>
        <button class="btn-link" @click="copySimplePrompt">📋 Kopieren</button>
        <label>ChatGPT-Antwort (JSON)</label>
        <textarea v-model="simpleWizard.response" rows="6" class="mono" placeholder="JSON hier einfügen..."></textarea>
        <div v-if="simpleWizard.error" class="wizard-error">⚠ {{ simpleWizard.error }}</div>
        <div v-if="simpleWizard.result" class="parsed-result">
          <strong style="color: #2e7d32;">
            ✓ Übernommen<span v-if="simpleWizard.result.count != null"> ({{ simpleWizard.result.count }})</span>
          </strong>
          <pre>{{ JSON.stringify(simpleWizard.result, null, 2) }}</pre>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeSimpleWizard">Abbrechen</button>
          <button class="btn-primary" :disabled="!simpleWizard.response || simpleWizard.busy"
                  @click="applySimpleWizard">Übernehmen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import AssistentenKachelGrid from '../../components/assistenten/AssistentenKachelGrid.vue'
import { buildWizardList, type WizardDescriptor } from '../../components/assistenten/registry'
import KiStreamView from '../../components/shared/KiStreamView.vue'
// #1366: Assistenten-Prompt direkt über den Provider (lokal/Cloud) ausführen.
const runWizardDirect = () => { wizardModal.value.running = true }
const onWizardRunDone = (p: any) => { wizardModal.value.running = false; wizardModal.value.response = (p?.text || '').trim() }
const onWizardRunError = () => { wizardModal.value.running = false }

const store = useAiActStore()

// #1445–#1449: Grid-Ref, um das Wizard-Ergebnis an den „Als Dokument speichern"-
// Dialog zu übergeben (der Dialog war zuvor leer → nicht speicherbar).
const grid = ref<InstanceType<typeof AssistentenKachelGrid> | null>(null)

// ── Tile-Registry ───────────────────────────────────────────────────────
const wizards: WizardDescriptor[] = buildWizardList([
  // Compliance / Klassifikation
  { id: 'risk-tier', title: 'A6 — Risk-Tier-Klassifikator', kategorie: 'compliance', icon: '📌',
    description: 'Bestimmt automatisch prohibited / high-risk / limited / minimal. Schreibt in meta_json.aiact.risk_tier.' },
  { id: 'use-case', title: 'A7 — Use-Case-Template', kategorie: 'compliance', icon: '⚙️',
    description: 'Setzt branchen-Defaults für Oversight-Mode + Reporting-SLA in einem Klick.' },
  { id: 'eu-doc', title: 'A8 — EU-Konformitätserklärung (Annex V)', kategorie: 'dokumentation', icon: '📜',
    description: 'Fertiger Markdown-Text der EU-DOC nach Annex V — wird an die System-Doku angehängt.' },
  { id: 'transparency', title: 'A9 — Transparenz-Hinweise (Art. 50)', kategorie: 'dokumentation', icon: '👁️',
    description: 'User-Facing-Texte für Chatbot-Disclosure / Deepfake-Markierung / Emotion-Recognition-Hinweis.' },

  // Pflicht-Doku-Wizards (A4 / A5)
  { id: 'ho', title: 'A4 — Human-Oversight-Wizard', kategorie: 'compliance', icon: '🧑‍✈️',
    description: 'Vorschlag für Oversight-Modus + Intervention-Mechanismen (Art. 14).' },
  { id: 'pmm', title: 'A5 — Monitoring-Plan-Wizard', kategorie: 'compliance', icon: '📡',
    description: 'Vorschlag für Monitoring-Plan, Drift-Detection und Incident-SLA (Art. 72-73).' },

  // Spezial-Wizards (#541-#545)
  { id: 'llm-card', title: 'A15 — LLM-System-Card-Generator', kategorie: 'dokumentation', icon: '🪪',
    description: 'System-Card im HuggingFace-Format (Modell, Trainingsdaten, Limitationen, Bias-Notes).' },
  { id: 'high-risk-doc', title: 'A16 — High-Risk-DOC + Annex-IV', kategorie: 'dokumentation', icon: '📑',
    description: 'EU-DOC für High-Risk-Systeme mit expliziten Verweisen auf Annex-IV-Belege.' },
  { id: 'prompt-injection-tests', title: 'A17 — Prompt-Injection-Test-Plan', kategorie: 'compliance', icon: '🧪',
    description: 'Test-Suite mit OWASP-LLM-Top-10-Test-Cases (Injection, Jailbreak, Disclosure).' },
  { id: 'hitl-workflow', title: 'A18 — Human-in-the-Loop-Workflow', kategorie: 'compliance', icon: '🔁',
    description: 'Decision-Points + Eskalations-Pfade + Schwellen für menschliche Freigabe (Art. 14).' },
  { id: 'eu-db-registration', title: 'A19 — EU-Datenbank-Anmeldung (Art. 49)', kategorie: 'dokumentation', icon: '🗄️',
    description: 'Anmeldedaten für die EU-Datenbank für High-Risk-Systeme inkl. Deadlines.' },

  // Erweiterungen (#546-#550)
  { id: 'model-card', title: 'A20 — Model-Card-Importer', kategorie: 'sonstiges', icon: '📥',
    description: 'Befüllt System-Doku-Felder automatisch aus HuggingFace/OpenAI/Anthropic-Model-Cards.' },
  { id: 'owasp-watch', title: 'A21 — OWASP-LLM-Top-10-Watch', kategorie: 'risiko', icon: '🔍',
    description: 'Live-Status pro OWASP-Kategorie (mitigiert / offen / n.a.) aus den Pflicht-Doku-Feldern.' },
  { id: 'chat', title: 'A22 — AI-Act-Chat', kategorie: 'sonstiges', icon: '💬',
    description: 'Q&A mit vollem Projekt-Kontext. Antwort verweist auf konkrete Artikel/Annex.' },
  { id: 'eu-office-report', title: 'A23 — EU-AI-Office-Reporting (Art. 73)', kategorie: 'compliance', icon: '🏛️',
    description: 'Markdown-Report für signifikante Incidents bei High-Risk-Systemen inkl. Meldefrist.' },
  { id: 'pre-market', title: 'A24 — Pre-Market-Check', kategorie: 'compliance', icon: '✅',
    description: 'Server-Validator: prüft vor Release, ob alle Pflicht-Belege vorhanden sind.' },

  // OWASP-LLM-Register-Wizards
  { id: 'owasp-autodetect', title: 'OWASP-LLM — Auto-Detect (Repo)', kategorie: 'risiko', icon: '🔭',
    description: 'Token-aware Repo-Scan mit 10 LLM-Heuristiken; überträgt Treffer ins OWASP-LLM-Register.' },
  { id: 'owasp-wizard', title: 'OWASP-LLM — KI-Vorschläge', kategorie: 'risiko', icon: '🛡️',
    description: 'KI-gestützte Status-Vorschläge (0–5) je OWASP-LLM-Top-10-Risiko fürs Register.' },

  // AI-Literacy (Art. 4, #1242)
  { id: 'literacy', title: 'AI-Literacy-Ausfüll-Assistent (Art. 4)', kategorie: 'compliance', icon: '🎓',
    description: 'Schlägt rollenbasiert Schulungsmaßnahmen vor (Entwickler/Fachanwender/Management/Betroffene); übernimmt sie ins AI-Literacy-Register und liefert einen exportierbaren AI-Literacy-Plan.',
    produces_document: { doc_type: 'ai_literacy_plan' } },

  // GPAI (Art. 53–55, #1244)
  { id: 'gpai', title: 'GPAI-Klassifikator (Art. 51–55)', kategorie: 'compliance', icon: '🧠',
    description: 'Bestimmt GPAI-Eigenschaft, systemisches Risiko (FLOP-Schwelle) und Pflichten-Status (Annex XI/XII); schreibt ins GPAI-Pflicht-Register.' },
  { id: 'gpai-copyright', title: 'GPAI-Urheberrechts-/TDM-Policy (Art. 53(1)c)', kategorie: 'dokumentation', icon: '©️',
    description: 'Erzeugt eine vollständige Urheberrechts-/TDM-Opt-out-Policy für das GPAI-Modell.',
    produces_document: { doc_type: 'gpai_copyright_policy' } },
  { id: 'gpai-training-summary', title: 'GPAI-Trainingsdaten-Zusammenfassung (Art. 53(1)d)', kategorie: 'dokumentation', icon: '🗂️',
    description: 'Erzeugt die öffentliche Trainingsdaten-Zusammenfassung nach AI-Office-Template.',
    produces_document: { doc_type: 'gpai_training_summary' } },

  // Pflichtdokumente (#1245)
  { id: 'betriebsanleitung', title: 'Betriebsanleitung (Art. 13)', kategorie: 'dokumentation', icon: '📘',
    description: 'Instructions-for-Use-Wizard: vollständige Betriebsanleitung für Betreiber (Art. 13(3)).',
    produces_document: { doc_type: 'betriebsanleitung' } },
  { id: 'fria-doc', title: 'FRIA-Bericht (Art. 27)', kategorie: 'dokumentation', icon: '⚖️',
    description: 'Geführter FRIA-Bericht (Grundrechte-Folgenabschätzung) mit Art-27-Pflichtpunkten.',
    produces_document: { doc_type: 'fria' } },
])

function onOpen(id: string): void {
  switch (id) {
    case 'use-case': selectedUseCase.value = ''; useCaseApplied.value = false; useCaseOpen.value = true; break
    case 'ho': openSimpleWizard('ho'); break
    case 'pmm': openSimpleWizard('pmm'); break
    case 'model-card': modelCard.value = { format: 'huggingface', text: '', result: null }; modelCardOpen.value = true; break
    case 'owasp-watch': owaspWatch.value = null; owaspWatchOpen.value = true; break
    case 'chat': chatFrage.value = ''; chatOpen.value = true; break
    case 'eu-office-report':
      incident.value = { incident_id: '', detected_at: '', severity: '', affected_subjects: '', summary: '', impact: '', immediate_actions: '' }
      euOfficeOpen.value = true
      break
    case 'pre-market': preMarket.value = null; preMarketOpen.value = true; break
    case 'owasp-autodetect': runOwaspAutodetect(); break
    case 'owasp-wizard': openOwaspWizard(); break
    // #1242 AI-Literacy-Ausfüll-Assistent (eigener Blueprint, apply ins Register).
    case 'literacy': openLiteracyWizard(); break
    // #1244 GPAI-Klassifikator (eigener Blueprint, apply ins GPAI-Register).
    case 'gpai': openGpaiWizard(); break
    // #1244 GPAI-Dokument-Prompts (Copy/Paste → „Als Dokument speichern").
    case 'gpai-copyright': openGpaiDocWizard('copyright-policy', 'GPAI-Urheberrechts-/TDM-Policy (Art. 53(1)c)'); break
    case 'gpai-training-summary': openGpaiDocWizard('training-summary', 'GPAI-Trainingsdaten-Zusammenfassung (Art. 53(1)d)'); break
    // #1245 Dokument-Wizards (Prompt → „Als Dokument speichern").
    case 'betriebsanleitung':
    case 'fria-doc':
    case 'high-risk-doc':
    default: openWizard(id as WizardKind)
  }
}

const reloadAll = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchSystemDoku(), store.fetchDataGovernance(),
    store.fetchHumanOversight(), store.fetchPmm(), store.fetchPflichtDokuStatus(),
  ])
}

onMounted(async () => {
  await store.fetchUseCaseTemplates()
})
watch(() => store.selectedProjekt, async () => {
  await store.fetchUseCaseTemplates()
})

// ── A7 Use-Case-Template ────────────────────────────────────────────────
const useCaseOpen = ref(false)
const selectedUseCase = ref('')
const useCaseApplied = ref(false)
const useCaseAppliedName = ref('')
const applyUseCase = async () => {
  if (!selectedUseCase.value) return
  const tpl = store.useCaseTemplates.find((t: any) => t.id === selectedUseCase.value)
  if (await store.applyUseCaseTemplate(selectedUseCase.value)) {
    useCaseApplied.value = true
    useCaseAppliedName.value = tpl?.name || selectedUseCase.value
    await reloadAll()
    await store.fetchProjekte()
  }
}

// ── Prompt-basierte Wizards ─────────────────────────────────────────────
const WIZARD_TITLES: Record<string, string> = {
  'risk-tier': 'AI-Act Risk-Tier-Klassifikator',
  'eu-doc': 'EU-Konformitätserklärung (Annex V)',
  'transparency': 'Transparenz-Hinweise (Art. 50)',
  'llm-card': 'LLM-System-Card-Generator (HuggingFace-Format)',
  'high-risk-doc': 'EU-DOC High-Risk + Annex-IV-Verweise',
  'prompt-injection-tests': 'Prompt-Injection-Test-Plan (OWASP LLM Top 10)',
  'hitl-workflow': 'Human-in-the-Loop-Workflow (Art. 14)',
  'eu-db-registration': 'EU-Datenbank-Anmeldung (Art. 49)',
  'chat': 'AI-Act-Chat (Q&A mit Projekt-Kontext)',
  'eu-office-report': 'EU-AI-Office-Reporting (Art. 73)',
  'betriebsanleitung': 'Betriebsanleitung / Instructions for Use (Art. 13)',
  'fria-doc': 'FRIA-Bericht — Grundrechte-Folgenabschätzung (Art. 27)',
}
type WizardKind = 'risk-tier' | 'eu-doc' | 'transparency' | 'llm-card' | 'high-risk-doc' | 'prompt-injection-tests' | 'hitl-workflow' | 'eu-db-registration' | 'chat' | 'eu-office-report' | 'betriebsanleitung' | 'fria-doc'

// `customParse`: alternative Apply-Funktion für Wizards auf eigenen Blueprints
// (#1242 literacy, #1244 gpai). Liefert ein Objekt mit `applied`-Flag.
// Reine Markdown-Generatoren ohne Inline-Apply: Ergebnis nur via „Als Dokument speichern".
const DOC_ONLY_WIZARDS = new Set(['betriebsanleitung', 'fria-doc', 'gpai-copyright', 'gpai-training-summary'])
const isDocOnlyWizard = computed(() => DOC_ONLY_WIZARDS.has(wizardModal.value.kind))

const wizardModal = ref<any>({ open: false, kind: '', title: '', prompt: '', response: '', parsed: null, customParse: null })
const openWizard = async (kind: WizardKind) => {
  const prompt = await store.getWizardPrompt(kind)
  wizardModal.value = { open: true, kind, title: WIZARD_TITLES[kind], prompt, response: '', parsed: null, customParse: null }
}
const closeWizard = () => { wizardModal.value = { open: false, kind: '', title: '', prompt: '', response: '', parsed: null, customParse: null } }
const copyPrompt = () => navigator.clipboard?.writeText(wizardModal.value.prompt)

// #1445–#1449: Doc-only-Ergebnis als Dokument speichern. Modal-`kind` == Kachel-id
// für die DOC_ONLY-Wizards; Text ist die Markdown-Antwort (Copy/Paste oder Direkt-KI).
const docSaveText = computed(
  () => (wizardModal.value.parsed?.markdown || wizardModal.value.response || '').trim(),
)
const saveDocFromWizard = () => {
  const text = docSaveText.value
  if (!text) return
  grid.value?.openSaveDialogFor(wizardModal.value.kind, text)
  closeWizard()
}
const parseAndApply = async () => {
  const { kind, response, customParse } = wizardModal.value
  if (typeof customParse === 'function') {
    wizardModal.value.parsed = await customParse(response)
  } else {
    wizardModal.value.parsed = await store.parseWizardResponse(kind, response, true)
  }
  await store.fetchProjekte()
  await reloadAll()
  if (wizardModal.value.parsed?.applied) {
    setTimeout(closeWizard, 1200)
  }
}

// ── #1242 AI-Literacy-Ausfüll-Assistent ─────────────────────────────────────
const openLiteracyWizard = async () => {
  const prompt = await store.getLiteracyWizardPrompt()
  wizardModal.value = {
    open: true, kind: 'literacy', title: 'AI-Literacy-Ausfüll-Assistent (Art. 4)',
    prompt, response: '', parsed: null,
    customParse: async (resp: string) => {
      const res = await store.parseLiteracyWizard(resp, true)
      return res ? { ...res, applied: !!res.applied } : null
    },
  }
}

// ── #1244 GPAI-Klassifikator (eigener Blueprint /aiact-gpai) ─────────────────
const openGpaiWizard = async () => {
  if (!store.selectedProjekt) return
  const proj = encodeURIComponent(store.selectedProjekt)
  let prompt = ''
  try { prompt = (await (await import('../../api/client')).default.get(`/aiact-gpai/projekte/${proj}/wizard/prompt`)).data?.prompt || '' }
  catch { prompt = '' }
  wizardModal.value = {
    open: true, kind: 'gpai', title: 'GPAI-Klassifikator (Art. 51–55)',
    prompt, response: '', parsed: null,
    customParse: async (resp: string) => {
      try {
        const client = (await import('../../api/client')).default
        const res = await client.post(`/aiact-gpai/projekte/${proj}/wizard/parse`, { response: resp, apply: true })
        return { ...res.data, applied: true }
      } catch (e: any) {
        store.error = e?.response?.data?.error || 'Übernahme fehlgeschlagen.'
        return null
      }
    },
  }
}

// ── #1244 GPAI-Dokument-Prompts (Copy/Paste → „Als Dokument speichern") ──────
const openGpaiDocWizard = async (kind: 'copyright-policy' | 'training-summary', title: string) => {
  const prompt = await store.getGpaiDocPrompt(kind)
  // #1445–#1449: `modalKind` muss der Kachel-id entsprechen, damit `isDocOnlyWizard`
  // greift und „📄 Als Dokument speichern" den richtigen Wizard-Descriptor findet.
  const modalKind = kind === 'copyright-policy' ? 'gpai-copyright' : 'gpai-training-summary'
  // Kein customParse: das Ergebnis wird über „📄 Als Dokument speichern" abgelegt.
  wizardModal.value = { open: true, kind: modalKind, title, prompt, response: '', parsed: null, customParse: null }
}

// ── A20 Model-Card-Importer ─────────────────────────────────────────────
const modelCardOpen = ref(false)
const modelCard = ref<any>({ format: 'huggingface', text: '', result: null })
const runModelCardImport = async () => {
  modelCard.value.result = await store.importModelCard(modelCard.value.text, modelCard.value.format, true)
  await reloadAll()
}

// ── A21 OWASP-LLM-Watch ─────────────────────────────────────────────────
const owaspWatchOpen = ref(false)
const owaspWatch = ref<any>(null)
const refreshOwaspWatch = async () => {
  owaspWatch.value = await store.fetchOwaspLlmWatch()
}

// ── A22 Chat ────────────────────────────────────────────────────────────
const chatOpen = ref(false)
const chatFrage = ref('')
const openChatWizard = async () => {
  const prompt = await store.getChatPrompt(chatFrage.value.trim())
  chatOpen.value = false
  wizardModal.value = { open: true, kind: 'chat', title: WIZARD_TITLES['chat'], prompt, response: '', parsed: null }
}

// ── A23 EU-AI-Office-Reporting ──────────────────────────────────────────
const euOfficeOpen = ref(false)
const incident = ref<any>({ incident_id: '', detected_at: '', severity: '', affected_subjects: '',
                            summary: '', impact: '', immediate_actions: '' })
const openEuOfficeWizard = async () => {
  const prompt = await store.getEuOfficeReportPrompt(incident.value)
  euOfficeOpen.value = false
  wizardModal.value = { open: true, kind: 'eu-office-report', title: WIZARD_TITLES['eu-office-report'], prompt, response: '', parsed: null }
}

// ── A24 Pre-Market-Check ────────────────────────────────────────────────
const preMarketOpen = ref(false)
const preMarket = ref<any>(null)
const refreshPreMarket = async () => {
  preMarket.value = await store.fetchPreMarketCheck()
}

// ── Simple Wizards (A4 Human-Oversight / A5 Post-Market-Monitoring) ──────
type SimpleWizardKind = 'ho' | 'pmm'
const SIMPLE_WIZARD_TITLES: Record<SimpleWizardKind, string> = {
  ho: 'Human-Oversight-Wizard (Art. 14)',
  pmm: 'Post-Market-Monitoring-Wizard (Art. 72-73)',
}
const simpleWizard = ref<any>({ open: false, kind: '', title: '', prompt: '', response: '', busy: false, result: null, error: '' })
const openSimpleWizard = async (kind: SimpleWizardKind) => {
  simpleWizard.value = { open: true, kind, title: SIMPLE_WIZARD_TITLES[kind], prompt: '', response: '', busy: true, result: null, error: '' }
  let prompt = ''
  if (kind === 'ho') prompt = await store.hoWizardPrompt()
  else if (kind === 'pmm') prompt = await store.pmmWizardPrompt()
  simpleWizard.value.prompt = prompt
  simpleWizard.value.busy = false
}
const closeSimpleWizard = () => {
  simpleWizard.value = { open: false, kind: '', title: '', prompt: '', response: '', busy: false, result: null, error: '' }
}
const copySimplePrompt = () => navigator.clipboard?.writeText(simpleWizard.value.prompt)
const applySimpleWizard = async () => {
  const { kind, response } = simpleWizard.value
  if (!response) return
  simpleWizard.value.busy = true
  simpleWizard.value.error = ''
  simpleWizard.value.result = null
  store.error = ''
  try {
    let res: any = null
    if (kind === 'ho') {
      res = await store.hoWizardApply(response)
    } else if (kind === 'pmm') {
      res = await store.pmmWizardApply(response)
    }
    const ok = !!(res && (res.ok || (Array.isArray(res.applied) && res.applied.length) || res.created))
    if (!ok) {
      simpleWizard.value.error = store.error
        || 'Übernahme fehlgeschlagen — ist die eingefügte Antwort gültiges JSON aus der KI-Antwort?'
      return
    }
    if (kind === 'ho') await store.fetchHumanOversight()
    else if (kind === 'pmm') await store.fetchPmm()
    await store.fetchPflichtDokuStatus()
    simpleWizard.value.result = res
    setTimeout(closeSimpleWizard, 1400)
  } catch (e: any) {
    simpleWizard.value.error = e?.response?.data?.error || e?.message || 'Unerwarteter Fehler bei der Übernahme'
  } finally {
    simpleWizard.value.busy = false
  }
}

// ── OWASP-LLM-Register-Wizards ──────────────────────────────────────────
const owaspBusy = ref(false)
const owaspWizardOpen = ref(false)
const owaspWizardPrompt = ref('')
const owaspWizardResponse = ref('')
const owaspWizardMsg = ref('')

const runOwaspAutodetect = async () => {
  if (!store.selectedProjekt) return
  owaspBusy.value = true
  store.error = ''
  try {
    const res = await store.autodetectOwaspLlm()
    if (res) {
      alert(`OWASP-LLM Auto-Detect: ${res.summary?.matched ?? 0}/${res.summary?.total ?? 10} Treffer, ${res.applied ?? 0} ins Register übernommen.`)
    } else {
      alert(store.error || 'Auto-Detect fehlgeschlagen.')
    }
  } finally { owaspBusy.value = false }
}

const openOwaspWizard = async () => {
  if (!store.selectedProjekt) return
  owaspBusy.value = true
  owaspWizardMsg.value = ''
  try {
    owaspWizardPrompt.value = await store.owaspLlmWizardPrompt()
    owaspWizardResponse.value = ''
    owaspWizardOpen.value = true
  } finally { owaspBusy.value = false }
}
const copyOwaspPrompt = () => navigator.clipboard?.writeText(owaspWizardPrompt.value)
const applyOwaspWizard = async () => {
  owaspBusy.value = true
  owaspWizardMsg.value = ''
  try {
    const res = await store.owaspLlmWizardParse(owaspWizardResponse.value, true)
    if (res) {
      owaspWizardMsg.value = `KI-Vorschläge übernommen: ${res.count ?? 0} Items aktualisiert.`
      setTimeout(() => { owaspWizardOpen.value = false }, 1200)
    } else {
      owaspWizardMsg.value = store.error || 'Übernahme fehlgeschlagen.'
    }
  } finally { owaspBusy.value = false }
}
</script>

<style scoped>
.aiact-assistenten { display: flex; flex-direction: column; gap: 16px; padding: 16px 0; }
.intro { background: #f3e5f5; border-left: 4px solid #7b1fa2; border-radius: 8px; padding: 14px 18px; }
.intro h3 { margin: 0 0 6px; color: #4a148c; }
.intro p { margin: 0 0 6px; color: #444; font-size: 13px; line-height: 1.5; }
.intro .hint { color: #7b1fa2; font-weight: 600; }
.hint { color: #666; font-size: 13px; margin-top: 6px; }
.ok-msg { color: #2e7d32; font-size: 13px; margin-top: 8px; }
.row { display: flex; gap: 8px; align-items: center; }
.row select { flex: 1; padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin: 8px 0; }
.form-grid input, .form-grid select, .form-grid textarea {
  padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit;
}
.form-grid textarea { grid-column: 1 / -1; }

.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #0d47a1; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #eee; color: #333; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 14px; color: #1565c0; }

.watch-table { width: 100%; margin-top: 8px; font-size: 13px; border-collapse: collapse; }
.watch-table th, .watch-table td { padding: 5px 8px; text-align: left; border-bottom: 1px solid #eee; }
.watch-table th { background: #f5f5f5; font-weight: 600; }
.watch-badge { padding: 2px 8px; border-radius: 10px; font-weight: 600; font-size: 11px; text-transform: uppercase; }
.watch-mitigiert { background: #c8e6c9; color: #1b5e20; }
.watch-offen { background: #ffe0b2; color: #bf360c; }
.watch-na { background: #eceff1; color: #455a64; }

.pre-market-result { padding: 12px 16px; border-radius: 6px; margin-top: 12px; border-left: 4px solid; }
.pmr-ok { background: #e8f5e9; border-color: #2e7d32; }
.pmr-fail { background: #ffebee; border-color: #c62828; }
.pre-market-result strong { display: block; margin-bottom: 4px; }
.pre-market-result small { display: block; color: #555; margin-bottom: 8px; }
.check-list { list-style: none; padding: 0; margin: 8px 0 0; }
.check { padding: 6px 8px; border-radius: 4px; margin-bottom: 4px; background: white; }
.check.fail.sev-critical { border-left: 3px solid #c62828; background: #ffebee; }
.check.fail.sev-high { border-left: 3px solid #ef6c00; background: #fff3e0; }
.check.ok { border-left: 3px solid #2e7d32; }
.check small { display: block; color: #666; font-size: 12px; margin-top: 2px; }

.wizard-modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.wizard-modal {
  background: white; padding: 24px; border-radius: 10px;
  max-width: 800px; width: 90%; max-height: 90vh; overflow-y: auto;
}
.wizard-modal h3 { margin: 0 0 8px; color: #4a148c; }
.wizard-modal label { display: block; margin-top: 12px; font-weight: 600; font-size: 13px; }
.wizard-modal textarea, .wizard-modal input { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.wizard-modal .mono { font-family: monospace; font-size: 12px; }
.parsed-result { background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 12px; }
.parsed-result pre { margin: 6px 0 0; white-space: pre-wrap; font-size: 12px; }
.wizard-error { background: #fdecea; color: #b71c1c; border: 1px solid #f5c6cb; padding: 10px 12px; border-radius: 4px; margin-top: 12px; font-size: 13px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
</style>
