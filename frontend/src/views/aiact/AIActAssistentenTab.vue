<template>
  <div class="aiact-assistenten">
    <div class="intro">
      <h3>{{ $t('aiact.aIActAssistentenTab.aIActAssistenten') }}</h3>
      <p>
        {{ $t('aiact.aIActAssistentenTab.alleKIAssistentenUndWizardsFurDieAIA') }}
      </p>
      <p v-if="!store.selectedProjekt" class="hint">
        {{ $t('common.bitteZuerstEinAIActProjektAu') }}
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
      @open-in-register="emit('open-in-register')"
    />

    <!-- #1571: A3 — Risiken identifizieren (Art. 9) über die verknüpfte EU-AI-Act-Risikobewertung -->
    <div v-if="riskOpen" class="wizard-modal-overlay" @mousedown.self="riskOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('aiact.aIActAssistentenTab.a3RisikenIdentifizierenArt') }}</h3>
        <p class="hint">
          {{ $t('aiact.aIActAssistentenTab.dieRisikenDesKISystemsLiegenInEinerV') }}
        </p>
        <Hr01RiskLinkBox />
        <div class="row" style="justify-content: flex-end">
          <button class="btn-secondary" @click="riskOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- A7: Use-Case-Template anwenden -->
    <div v-if="useCaseOpen" class="wizard-modal-overlay" @mousedown.self="useCaseOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('aiact.aIActAssistentenTab.a7UseCaseTemplateAnwenden') }}</h3>
        <p class="hint">{{ $t('aiact.aIActAssistentenTab.setztDefaultsFurOversightModeReporti') }}</p>
        <div class="row">
          <select v-model="selectedUseCase">
            <option value="">{{ $t('aiact.aIActAssistentenTab.useCaseWahlen') }}</option>
            <option v-for="t in store.useCaseTemplates" :key="t.id" :value="t.id">
              {{ t.name }} ({{ t.tier }})
            </option>
          </select>
          <button class="btn-primary" :disabled="!selectedUseCase" @click="applyUseCase">{{ $t('aiact.aIActAssistentenTab.anwenden') }}</button>
        </div>
        <p v-if="useCaseApplied" class="ok-msg">{{ $t('common.template') }} <strong>{{ useCaseAppliedName }}</strong> {{ $t('aiact.aIActAssistentenTab.angewendet') }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="useCaseOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- A20: Model-Card-Importer -->
    <div v-if="modelCardOpen" class="wizard-modal-overlay" @mousedown.self="modelCardOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('aiact.aIActAssistentenTab.a20ModelCardImporter') }}</h3>
        <p class="hint">{{ $t('aiact.aIActAssistentenTab.systemDokuFelderWerdenAutomatischAus') }}</p>
        <div class="row" style="gap:8px;">
          <select v-model="modelCard.format">
            <option value="huggingface">{{ $t('aiact.aIActAssistentenTab.huggingFaceMarkdownYAML') }}</option>
            <option value="openai">{{ $t('aiact.aIActAssistentenTab.openAIJSON') }}</option>
            <option value="anthropic">{{ $t('aiact.aIActAssistentenTab.anthropicJSON') }}</option>
            <option value="generic">{{ $t('aiact.aIActAssistentenTab.genericMarkdown') }}</option>
          </select>
          <button class="btn-primary" :disabled="!modelCard.text.trim()" @click="runModelCardImport">{{ $t('aiact.aIActAssistentenTab.importieren') }}</button>
        </div>
        <textarea v-model="modelCard.text" rows="6" class="mono"
                  :placeholder="$t('aiact.aIActAssistentenTab.modelCardTextHierEinfugenZBHFREADMEM')"
                  style="width:100%; margin-top:8px;"></textarea>
        <pre v-if="modelCard.result" class="parsed-result">{{ JSON.stringify(modelCard.result, null, 2) }}</pre>
        <div class="modal-actions">
          <button class="btn-secondary" @click="modelCardOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- A21: OWASP-LLM-Top-10-Watch -->
    <div v-if="owaspWatchOpen" class="wizard-modal-overlay" @mousedown.self="owaspWatchOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('aiact.aIActAssistentenTab.a21OWASPLLMTopWatch') }}</h3>
        <p class="hint">{{ $t('aiact.aIActAssistentenTab.liveStatusProOWASPKategorieAufBasisD') }}</p>
        <button class="btn-primary" @click="refreshOwaspWatch">{{ $t('aiact.aIActAssistentenTab.statusAktualisieren') }}</button>
        <table v-if="owaspWatch" class="watch-table">
          <thead>
            <tr><th>ID</th><th>{{ $t('common.kategorie') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('common.hinweis') }}</th></tr>
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
          <button class="btn-secondary" @click="owaspWatchOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- A22: AI-Act-Chat -->
    <div v-if="chatOpen" class="wizard-modal-overlay" @mousedown.self="chatOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('aiact.aIActAssistentenTab.a22AIActChat') }}</h3>
        <p class="hint">{{ $t('aiact.aIActAssistentenTab.qAmpAMitVollemProjektKontextAntwortV') }}</p>
        <div class="row" style="gap:8px;">
          <input v-model="chatFrage" :placeholder="$t('aiact.aIActAssistentenTab.deineFrageZumAIAct')"
                 style="flex:1; padding:7px 10px; border:1px solid #ccc; border-radius:4px;" />
          <button class="btn-primary" :disabled="!chatFrage.trim()" @click="openChatWizard">{{ $t('aiact.aIActAssistentenTab.promptGenerieren') }}</button>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="chatOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- A23: EU-AI-Office-Reporting -->
    <div v-if="euOfficeOpen" class="wizard-modal-overlay" @mousedown.self="euOfficeOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('aiact.aIActAssistentenTab.a23EUAIOfficeReportingArt') }}</h3>
        <p class="hint">{{ $t('aiact.aIActAssistentenTab.vollstandigerMarkdownReportFurSignif') }}</p>
        <div class="form-grid">
          <input v-model="incident.incident_id" placeholder="Incident-ID (optional)" />
          <input v-model="incident.detected_at" :placeholder="$t('aiact.aIActAssistentenTab.eintrittYYYYMMDDHHMM')" />
          <select v-model="incident.severity">
            <option value="">{{ $t('aiact.aIActAssistentenTab.schweregrad') }}</option>
            <option value="moderat">moderat</option>
            <option value="hoch">{{ $t('aiact.aIActAssistentenTab.hoch') }}</option>
            <option value="kritisch">{{ $t('aiact.aIActAssistentenTab.kritischArtTage') }}</option>
          </select>
          <input v-model="incident.affected_subjects" :placeholder="$t('aiact.aIActAssistentenTab.betroffeneZBEndkunden')" />
          <textarea v-model="incident.summary" :placeholder="$t('aiact.aIActAssistentenTab.kurzbeschreibung')" rows="2" />
          <textarea v-model="incident.impact" :placeholder="$t('aiact.aIActAssistentenTab.auswirkung')" rows="2" />
          <textarea v-model="incident.immediate_actions" :placeholder="$t('common.sofortmassnahmen')" rows="2" />
        </div>
        <button class="btn-primary" :disabled="!incident.summary?.trim()" @click="openEuOfficeWizard">
          {{ $t('common.promptGenerieren') }}
        </button>
        <div class="modal-actions">
          <button class="btn-secondary" @click="euOfficeOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- A24: Pre-Market-Check -->
    <div v-if="preMarketOpen" class="wizard-modal-overlay" @mousedown.self="preMarketOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('aiact.aIActAssistentenTab.a24PreMarketCheck') }}</h3>
        <p class="hint">{{ $t('aiact.aIActAssistentenTab.pruftVorReleaseObAllePflichtBelegeDa') }}</p>
        <button class="btn-primary" @click="refreshPreMarket">{{ $t('aiact.aIActAssistentenTab.checkAusfuhren') }}</button>
        <div v-if="preMarket" :class="['pre-market-result', preMarket.release_ready ? 'pmr-ok' : 'pmr-fail']">
          <strong v-if="preMarket.release_ready">{{ $t('aiact.aIActAssistentenTab.releaseReadyAlleKritischenChecksBest') }}</strong>
          <strong v-else>{{ $t('aiact.aIActAssistentenTab.nICHTReleaseReadyV0KritischeLucken', { v0: preMarket.summary.critical_fail }) }}</strong>
          <small>Risk-Tier: {{ preMarket.tier }} · {{ preMarket.summary.passed }}/{{ preMarket.summary.total }} bestanden</small>
          <ul class="check-list">
            <li v-for="c in preMarket.checks" :key="c.key" :class="['check', c.ok ? 'ok' : 'fail', `sev-${c.severity}`]">
              <strong>{{ c.ok ? '✅' : '⛔' }} {{ c.label }}</strong>
              <small v-if="!c.ok">{{ c.hint }}</small>
            </li>
          </ul>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="preMarketOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- OWASP-LLM-Wizard (KI-Vorschläge) -->
    <div v-if="owaspWizardOpen" class="wizard-modal-overlay" @mousedown.self="owaspWizardOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('aiact.aIActAssistentenTab.oWASPLLMKIVorschlage') }}</h3>
        <p class="hint">{{ $t('aiact.aIActAssistentenTab.promptKopierenInChatGPTClaudeAntwort') }}</p>
        <PromptAustausch v-model="owaspWizardResponse" :prompt="owaspWizardPrompt"
                         prompt-titel="Prompt" antwort-titel="KI-Antwort (JSON)"
                         :nummeriert="false" :prompt-zeilen="6" :antwort-zeilen="6"
                         platzhalter='{"items": [{"id": "LLM01", "status": 4, "kommentar": "…"}]}' />
        <div v-if="owaspWizardMsg" class="ok-msg">{{ owaspWizardMsg }}</div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="owaspWizardOpen = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!owaspWizardResponse || owaspBusy" @click="applyOwaspWizard">{{ $t('common.uebernehmen') }}</button>
        </div>
      </div>
    </div>

    <!-- Prompt-basierter Wizard-Modal (Risk-Tier / EU-DOC / Transparenz / Spezial-Wizards / Chat / EU-Office) -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @mousedown.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <p v-if="isDocOnlyWizard" class="hint">
          {{ $t('aiact.aIActAssistentenTab.promptNachChatGPTKopierenAntwortMark') }}
        </p>
        <p v-else class="hint">{{ $t('aiact.aIActAssistentenTab.promptNachChatGPTKopierenJSONAntwort') }}</p>
        <PromptAustausch v-model="wizardModal.response" :prompt="wizardModal.prompt"
                         prompt-titel="Prompt" antwort-titel="ChatGPT-Antwort (JSON)"
                         :nummeriert="false" :prompt-zeilen="8" :antwort-zeilen="6"
                         :mit-antwort="!isDocOnlyWizard"
                         :platzhalter="$t('aiact.aIActAssistentenTab.jSONHierEinfugen')">
          <template #prompt-aktionen>
            <button class="btn-link" :disabled="wizardModal.running" @click="runWizardDirect">{{ $t('common.direktMitKIAusfuhren') }}</button>
          </template>
          <template #nach-prompt>
            <FehlerHinweis v-if="wizardModal.fehler" :text="wizardModal.fehler"
                           @close="wizardModal.fehler = ''" />
            <div v-if="wizardModal.running" class="ki-run">
              <!-- #1834/#1836/E6: eigene Hinweise auch hier. Die Engine
                   setzt sie serverseitig ein (shared/ki_engine). -->
              <PromptZusatzFeld v-model="zusatz" modul="aiact" :projekt="store.selectedProjekt" bereich="assistent" />
              <KiStreamView :url="`/api/ai/run-stream`" :confirm-egress="true" :body="{ prompt: wizardModal.prompt, prompt_zusatz: zusatz }"
                            @done="onWizardRunDone" @error="onWizardRunError" />
            </div>
          </template>
        </PromptAustausch>
        <template v-if="!isDocOnlyWizard">
          <div v-if="wizardModal.parsed" class="parsed-result">
            <strong v-if="wizardModal.parsed.applied" style="color: #2e7d32;">{{ $t('common.angewendetGespeichert') }}</strong>
            <strong v-else style="color: #e65100;">{{ $t('aiact.aIActAssistentenTab.geparsedVorschau') }}</strong>
            <pre>{{ JSON.stringify(wizardModal.parsed, null, 2) }}</pre>
          </div>
        </template>
        <!-- #1445–#1449: Doc-only-Wizards — Markdown-Ergebnis (Copy/Paste oder
             Direkt-mit-KI) hier ablegen und als Dokument speichern. -->
        <template v-else>
          <label>{{ $t('aiact.aIActAssistentenTab.ergebnisMarkdown') }}</label>
          <textarea v-model="wizardModal.response" rows="8" class="mono"
                    :placeholder="$t('aiact.aIActAssistentenTab.chatGPTAntwortMarkdownHierEinfugenOd')"></textarea>
        </template>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeWizard">{{ $t('common.close') }}</button>
          <button v-if="isDocOnlyWizard" class="btn-primary" :disabled="!docSaveText" @click="saveDocFromWizard">{{ $t('common.alsDokumentSpeichern') }}</button>
          <button v-if="!isDocOnlyWizard" class="btn-primary" :disabled="!wizardModal.response" @click="parseAndApply">{{ $t('common.parsenAnwenden') }}</button>
        </div>
      </div>
    </div>

    <!-- Simple Wizard-Modal (A4 Human-Oversight / A5 Post-Market-Monitoring) -->
    <div v-if="simpleWizard.open" class="wizard-modal-overlay" @mousedown.self="closeSimpleWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ simpleWizard.title }}</h3>
        <p class="hint">{{ $t('aiact.aIActAssistentenTab.promptNachChatGPTKopierenJSONAntwort2') }}</p>
        <PromptAustausch v-model="simpleWizard.response" :prompt="simpleWizard.prompt"
                         prompt-titel="Prompt" antwort-titel="ChatGPT-Antwort (JSON)"
                         :nummeriert="false" :prompt-zeilen="8" :antwort-zeilen="6"
                         :platzhalter="$t('aiact.aIActAssistentenTab.jSONHierEinfugen')" />
        <div v-if="simpleWizard.error" class="wizard-error">⚠ {{ simpleWizard.error }}</div>
        <div v-if="simpleWizard.result" class="parsed-result">
          <strong style="color: #2e7d32;">
            {{ $t('aiact.aIActAssistentenTab.ubernommen') }}<span v-if="simpleWizard.result.count != null"> ({{ simpleWizard.result.count }})</span>
          </strong>
          <pre>{{ JSON.stringify(simpleWizard.result, null, 2) }}</pre>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeSimpleWizard">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!simpleWizard.response || simpleWizard.busy"
                  @click="applySimpleWizard">{{ $t('common.uebernehmen') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import PromptZusatzFeld from '../../components/shared/PromptZusatzFeld.vue'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
import { useAiActStore } from '../../stores/aiact'
import AssistentenKachelGrid from '../../components/assistenten/AssistentenKachelGrid.vue'
import { parsedToMarkdown } from '../../utils/parsedToMarkdown'
import { buildWizardList, type WizardDescriptor } from '../../components/assistenten/registry'
import KiStreamView from '../../components/shared/KiStreamView.vue'
import PromptAustausch from '../../components/shared/PromptAustausch.vue'
import Hr01RiskLinkBox from './Hr01RiskLinkBox.vue'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'

// #1805: „Im Register öffnen" nach dem Speichern eines Dokuments wird nach oben
// durchgereicht. Ohne das war der Knopf im Speichern-Dialog ohne Wirkung — wie
// in DSGVO und WiBA, die denselben Zuhörer nicht hatten.
const emit = defineEmits<{ (e: 'open-in-register'): void }>()

// #1834: eigene Hinweise des Bearbeiters für diesen Lauf.
const zusatz = ref('')
const riskOpen = ref(false)  // #1571 A3-Kachel
// #1366: Assistenten-Prompt direkt über den Provider (lokal/Cloud) ausführen.
const runWizardDirect = () => { wizardModal.value.running = true }
const onWizardRunDone = (p: any) => { wizardModal.value.running = false; wizardModal.value.response = (p?.text || '').trim() }
const onWizardRunError = (msg: string) => {
  // #1839: `running = false` unmountet die KiStreamView — und damit die
  // Komponente, die die Meldung ANZEIGTE. Ein 409 „kein KI-Provider
  // verfügbar" verschwand dadurch spurlos: keine Meldung, keine Konsole,
  // ein leeres Antwortfeld. Der Text muss außerhalb des Streams liegen.
  wizardModal.value.running = false
  wizardModal.value.fehler = msg || uebersetze('common.derKILaufIstFehlgeschlagen')
}

const store = useAiActStore()

// #1445–#1449: Grid-Ref, um das Wizard-Ergebnis an den „Als Dokument speichern"-
// Dialog zu übergeben (der Dialog war zuvor leer → nicht speicherbar).
const grid = ref<InstanceType<typeof AssistentenKachelGrid> | null>(null)

// ── Tile-Registry ───────────────────────────────────────────────────────
const wizards: WizardDescriptor[] = buildWizardList([
  // Compliance / Klassifikation
  { id: 'risiken', title: uebersetze('aiact.aIActAssistentenTab.a3RisikenIdentifizierenArt'), kategorie: 'risiko', icon: '⚠️',
    description: uebersetze('aiact.aIActAssistentenTab.ermitteltDieRisikenDesKISystemsInDer') },
  { id: 'risk-tier', title: 'A6 — Risk-Tier-Klassifikator', kategorie: 'compliance', icon: '📌',
    description: uebersetze('aiact.aIActAssistentenTab.bestimmtAutomatischProhibitedHighRis') },
  { id: 'use-case', title: 'A7 — Use-Case-Template', kategorie: 'compliance', icon: '⚙️',
    description: uebersetze('aiact.aIActAssistentenTab.setztBranchenDefaultsFurOversightMod') },
  { id: 'eu-doc', title: uebersetze('aiact.aIActAssistentenTab.a8EUKonformitatserklarungAnnexV'), kategorie: 'dokumentation', icon: '📜',
    description: uebersetze('aiact.aIActAssistentenTab.fertigerMarkdownTextDerEUDOCNachAnne') },
  { id: 'transparency', title: 'A9 — Transparenz-Hinweise (Art. 50)', kategorie: 'dokumentation', icon: '👁️',
    description: uebersetze('aiact.aIActAssistentenTab.userFacingTexteFurChatbotDisclosureD') },

  // Pflicht-Doku-Wizards (A4 / A5)
  { id: 'ho', title: 'A4 — Human-Oversight-Wizard', kategorie: 'compliance', icon: '🧑‍✈️',
    description: uebersetze('aiact.aIActAssistentenTab.vorschlagFurOversightModusInterventi') },
  { id: 'pmm', title: 'A5 — Monitoring-Plan-Wizard', kategorie: 'compliance', icon: '📡',
    description: uebersetze('aiact.aIActAssistentenTab.vorschlagFurMonitoringPlanDriftDetec') },

  // Spezial-Wizards (#541-#545)
  { id: 'llm-card', title: 'A15 — LLM-System-Card-Generator', kategorie: 'dokumentation', icon: '🪪',
    description: 'System-Card im HuggingFace-Format (Modell, Trainingsdaten, Limitationen, Bias-Notes).' },
  { id: 'high-risk-doc', title: 'A16 — High-Risk-DOC + Annex-IV', kategorie: 'dokumentation', icon: '📑',
    description: uebersetze('aiact.aIActAssistentenTab.eUDOCFurHighRiskSystemeMitExpliziten') },
  { id: 'prompt-injection-tests', title: 'A17 — Prompt-Injection-Test-Plan', kategorie: 'compliance', icon: '🧪',
    description: uebersetze('aiact.aIActAssistentenTab.testSuiteMitOWASPLLMTopTestCasesInje') },
  { id: 'hitl-workflow', title: 'A18 — Human-in-the-Loop-Workflow', kategorie: 'compliance', icon: '🔁',
    description: uebersetze('aiact.aIActAssistentenTab.decisionPointsEskalationsPfadeSchwel') },
  { id: 'eu-db-registration', title: 'A19 — EU-Datenbank-Anmeldung (Art. 49)', kategorie: 'dokumentation', icon: '🗄️',
    description: uebersetze('aiact.aIActAssistentenTab.anmeldedatenFurDieEUDatenbankFurHigh') },

  // Erweiterungen (#546-#550)
  { id: 'model-card', title: 'A20 — Model-Card-Importer', kategorie: 'sonstiges', icon: '📥',
    description: uebersetze('aiact.aIActAssistentenTab.befulltSystemDokuFelderAutomatischAu') },
  { id: 'owasp-watch', title: 'A21 — OWASP-LLM-Top-10-Watch', kategorie: 'risiko', icon: '🔍',
    description: uebersetze('aiact.aIActAssistentenTab.liveStatusProOWASPKategorieMitigiert') },
  { id: 'chat', title: 'A22 — AI-Act-Chat', kategorie: 'sonstiges', icon: '💬',
    description: uebersetze('aiact.aIActAssistentenTab.qAMitVollemProjektKontextAntwortVerw') },
  { id: 'eu-office-report', title: 'A23 — EU-AI-Office-Reporting (Art. 73)', kategorie: 'compliance', icon: '🏛️',
    description: uebersetze('aiact.aIActAssistentenTab.markdownReportFurSignifikanteInciden') },
  { id: 'pre-market', title: 'A24 — Pre-Market-Check', kategorie: 'compliance', icon: '✅',
    description: uebersetze('aiact.aIActAssistentenTab.serverValidatorPruftVorReleaseObAlle') },

  // OWASP-LLM-Register-Wizards
  { id: 'owasp-autodetect', title: 'OWASP-LLM — Auto-Detect (Repo)', kategorie: 'risiko', icon: '🔭',
    description: uebersetze('aiact.aIActAssistentenTab.tokenAwareRepoScanMitLLMHeuristikenU') },
  { id: 'owasp-wizard', title: uebersetze('aiact.aIActAssistentenTab.oWASPLLMKIVorschlage'), kategorie: 'risiko', icon: '🛡️',
    description: uebersetze('aiact.aIActAssistentenTab.kIGestutzteStatusVorschlageJeOWASPLL') },

  // AI-Literacy (Art. 4, #1242)
  { id: 'literacy', title: uebersetze('aiact.aIActAssistentenTab.aILiteracyAusfullAssistentArt'), kategorie: 'compliance', icon: '🎓',
    description: uebersetze('aiact.aIActAssistentenTab.schlagtRollenbasiertSchulungsmassnah'),
    produces_document: { doc_type: 'ai_literacy_plan' } },

  // GPAI (Art. 53–55, #1244)
  { id: 'gpai', title: uebersetze('aiact.aIActAssistentenTab.gPAIKlassifikatorArt'), kategorie: 'compliance', icon: '🧠',
    description: uebersetze('aiact.aIActAssistentenTab.bestimmtGPAIEigenschaftSystemischesR') },
  { id: 'gpai-copyright', title: 'GPAI-Urheberrechts-/TDM-Policy (Art. 53(1)c)', kategorie: 'dokumentation', icon: '©️',
    description: uebersetze('aiact.aIActAssistentenTab.erzeugtEineVollstandigeUrheberrechts'),
    produces_document: { doc_type: 'gpai_copyright_policy' } },
  { id: 'gpai-training-summary', title: 'GPAI-Trainingsdaten-Zusammenfassung (Art. 53(1)d)', kategorie: 'dokumentation', icon: '🗂️',
    description: uebersetze('aiact.aIActAssistentenTab.erzeugtDieOffentlicheTrainingsdatenZ'),
    produces_document: { doc_type: 'gpai_training_summary' } },

  // Pflichtdokumente (#1245)
  { id: 'betriebsanleitung', title: uebersetze('aiact.aIActAssistentenTab.betriebsanleitungArt'), kategorie: 'dokumentation', icon: '📘',
    description: uebersetze('aiact.aIActAssistentenTab.instructionsForUseWizardVollstandige'),
    produces_document: { doc_type: 'betriebsanleitung' } },
  { id: 'fria-doc', title: uebersetze('aiact.aIActAssistentenTab.fRIABerichtArt'), kategorie: 'dokumentation', icon: '⚖️',
    description: uebersetze('aiact.aIActAssistentenTab.gefuhrterFRIABerichtGrundrechteFolge'),
    produces_document: { doc_type: 'fria' } },
])

function onOpen(id: string): void {
  switch (id) {
    case 'risiken': riskOpen.value = true; break
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
  'risk-tier': uebersetze('aiact.aIActAssistentenTab.aIActRiskTierKlassifikator'),
  'eu-doc': uebersetze('aiact.aIActAssistentenTab.eUKonformitatserklarungAnnexV'),
  'transparency': 'Transparenz-Hinweise (Art. 50)',
  'llm-card': 'LLM-System-Card-Generator (HuggingFace-Format)',
  'high-risk-doc': uebersetze('aiact.aIActAssistentenTab.eUDOCHighRiskAnnexIVVerweise'),
  'prompt-injection-tests': uebersetze('aiact.aIActAssistentenTab.promptInjectionTestPlanOWASPLLMTop'),
  'hitl-workflow': 'Human-in-the-Loop-Workflow (Art. 14)',
  'eu-db-registration': 'EU-Datenbank-Anmeldung (Art. 49)',
  'chat': uebersetze('aiact.aIActAssistentenTab.aIActChatQAMitProjektKontext'),
  'eu-office-report': 'EU-AI-Office-Reporting (Art. 73)',
  'betriebsanleitung': uebersetze('aiact.aIActAssistentenTab.betriebsanleitungInstructionsForUseA'),
  'fria-doc': uebersetze('aiact.aIActAssistentenTab.fRIABerichtGrundrechteFolgenabschatz'),
}
type WizardKind = 'risk-tier' | 'eu-doc' | 'transparency' | 'llm-card' | 'high-risk-doc' | 'prompt-injection-tests' | 'hitl-workflow' | 'eu-db-registration' | 'chat' | 'eu-office-report' | 'betriebsanleitung' | 'fria-doc'

// `customParse`: alternative Apply-Funktion für Wizards auf eigenen Blueprints
// (#1242 literacy, #1244 gpai). Liefert ein Objekt mit `applied`-Flag.
// Reine Markdown-Generatoren ohne Inline-Apply: Ergebnis nur via „Als Dokument speichern".
const DOC_ONLY_WIZARDS = new Set(['betriebsanleitung', 'fria-doc', 'gpai-copyright', 'gpai-training-summary'])
const isDocOnlyWizard = computed(() => DOC_ONLY_WIZARDS.has(wizardModal.value.kind))

const wizardModal = ref<any>({ open: false, fehler: '', kind: '', title: '', prompt: '', response: '', parsed: null, customParse: null })
const openWizard = async (kind: WizardKind) => {
  const prompt = await store.getWizardPrompt(kind)
  wizardModal.value = { open: true, kind, title: WIZARD_TITLES[kind], prompt, response: '', parsed: null, customParse: null }
}
const closeWizard = () => { wizardModal.value = { open: false, kind: '', title: '', prompt: '', response: '', parsed: null, customParse: null } }

// #1445–#1449: Doc-only-Ergebnis als Dokument speichern. Modal-`kind` == Kachel-id
// für die DOC_ONLY-Wizards; Text ist die Markdown-Antwort (Copy/Paste oder Direkt-KI).
const docSaveText = computed(
  () => parsedToMarkdown(wizardModal.value.parsed, wizardModal.value.response),
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
    open: true, kind: 'literacy', title: uebersetze('aiact.aIActAssistentenTab.aILiteracyAusfullAssistentArt'),
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
    open: true, kind: 'gpai', title: uebersetze('aiact.aIActAssistentenTab.gPAIKlassifikatorArt'),
    prompt, response: '', parsed: null,
    customParse: async (resp: string) => {
      try {
        const client = (await import('../../api/client')).default
        const res = await client.post(`/aiact-gpai/projekte/${proj}/wizard/parse`, { response: resp, apply: true })
        return { ...res.data, applied: true }
      } catch (e: any) {
        store.error = e?.response?.data?.error || uebersetze('common.uebernahmeFehlgeschlagen')
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
        || uebersetze('aiact.aIActAssistentenTab.ubernahmeFehlgeschlagenIstDieEingefu')
      return
    }
    if (kind === 'ho') await store.fetchHumanOversight()
    else if (kind === 'pmm') await store.fetchPmm()
    await store.fetchPflichtDokuStatus()
    simpleWizard.value.result = res
    setTimeout(closeSimpleWizard, 1400)
  } catch (e: any) {
    simpleWizard.value.error = e?.response?.data?.error || e?.message || uebersetze('aiact.aIActAssistentenTab.unerwarteterFehlerBeiDerUbernahme')
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
      alert(store.error || uebersetze('aiact.aIActAssistentenTab.autoDetectFehlgeschlagen'))
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
const applyOwaspWizard = async () => {
  owaspBusy.value = true
  owaspWizardMsg.value = ''
  try {
    const res = await store.owaspLlmWizardParse(owaspWizardResponse.value, true)
    if (res) {
      owaspWizardMsg.value = `KI-Vorschläge übernommen: ${res.count ?? 0} Items aktualisiert.`
      setTimeout(() => { owaspWizardOpen.value = false }, 1200)
    } else {
      owaspWizardMsg.value = store.error || uebersetze('common.uebernahmeFehlgeschlagen')
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
