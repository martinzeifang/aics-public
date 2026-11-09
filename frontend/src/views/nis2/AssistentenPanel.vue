<template>
  <div class="assistenten-panel">
    <div class="info-banner">
      <h3>{{ $t('nis2.assistentenPanel.nIS2Assistenten') }}</h3>
      <p>{{ $t('nis2.assistentenPanel.alleKIUndCopyPasteHelferDesNIS2Modul') }}</p>
    </div>

    <AssistentenKachelGrid
      ref="grid"
      :wizards="wizards"
      grouped
      :modul="'nis2'"
      :projekt="store.selectedProjekt"
      @open="openTile"
      @open-in-register="(id: number) => emit('open-in-register', id)"
    />

    <!-- N1 Asset-Inventar-Wizard (Copy-Paste) -->
    <!-- (kein eigenes Modal nötig — öffnet direkt das Prompt-Wizard-Modal) -->

    <!-- N7 Sektor-Template-Auswahl -->
    <div v-if="sektorModalOpen" class="wizard-modal-overlay" @mousedown.self="sektorModalOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.assistentenPanel.n7SektorTemplateAnwenden') }}</h3>
        <p class="hint">{{ $t('nis2.assistentenPanel.setztSektorSpezifischeDefaultsInEine') }}</p>
        <div class="row">
          <select v-model="selectedSektor">
            <option value="">{{ $t('nis2.assistentenPanel.sektorWahlen') }}</option>
            <option v-for="t in store.sektorTemplates" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
          <button class="btn-primary" :disabled="!selectedSektor" @click="applySektor">{{ $t('nis2.assistentenPanel.anwenden') }}</button>
        </div>
        <p v-if="sektorApplied" class="hint">{{ $t('common.template') }} <strong>{{ sektorAppliedName }}</strong> {{ $t('nis2.assistentenPanel.angewendetDefaultsSindInN3N5Aktiv') }}</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="sektorModalOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- N8 Incident-Notification — Meta-Eingabe -->
    <div v-if="incidentModalOpen" class="wizard-modal-overlay" @mousedown.self="incidentModalOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.assistentenPanel.n8IncidentNotificationGenerator') }}</h3>
        <p class="hint">{{ $t('nis2.assistentenPanel.erzeugtDieDreiPflichtigenCSIRTMeldun') }}</p>
        <div class="form-grid">
          <input v-model="incidentMeta.description" :placeholder="$t('nis2.assistentenPanel.incidentKurzBeschreibenZBRansomwareA')" />
          <select v-model="incidentMeta.severity">
            <option value="niedrig">{{ $t('common.niedrig') }}</option><option value="mittel">{{ $t('common.mittel') }}</option>
            <option value="hoch">{{ $t('common.hoch') }}</option><option value="kritisch">{{ $t('common.kritisch') }}</option>
          </select>
          <input v-model="incidentMeta.affected_services" :placeholder="$t('nis2.assistentenPanel.betroffeneServices')" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="incidentModalOpen = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!incidentMeta.description"
                  @click="startIncidentNotification">{{ $t('common.promptGenerieren') }}</button>
        </div>
      </div>
    </div>

    <!-- N9 Supply-Chain-Assessment — Vendor-Auswahl -->
    <div v-if="supplyChainModalOpen" class="wizard-modal-overlay" @mousedown.self="supplyChainModalOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.assistentenPanel.n9SupplyChainAssessment') }}</h3>
        <p class="hint">{{ $t('nis2.assistentenPanel.generiertFurEinenEinzelnenVendorEinK') }}
          <strong>{{ $t('nis2.assistentenPanel.n4SupplyChainSecurity') }}</strong> {{ $t('nis2.assistentenPanel.pflichtDokuAngelegt') }}</p>
        <div v-if="store.vendors.length === 0" class="info-no-vendor">
          {{ $t('nis2.assistentenPanel.nochKeineVendorenAngelegtDerWizardBr') }}
        </div>
        <div v-else class="row">
          <select v-model="assessmentVendorId">
            <option value="">{{ $t('nis2.assistentenPanel.vendorWahlen') }}</option>
            <option v-for="v in store.vendors" :key="v.id" :value="v.id">{{ v.vendor_name }} ({{ v.leistung || '—' }})</option>
          </select>
          <button class="btn-primary" :disabled="!assessmentVendorId" @click="startSupplyChain">{{ $t('common.promptGenerieren') }}</button>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="supplyChainModalOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- N14 24h-Erstmeldung -->
    <div v-if="incident24ModalOpen" class="wizard-modal-overlay" @mousedown.self="incident24ModalOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.assistentenPanel.n14HErstmeldungArtAbsLitA') }}</h3>
        <p class="hint">{{ $t('nis2.assistentenPanel.kurzmeldungImBSIPortalFormatBlossDie') }}</p>
        <div class="form-grid">
          <input v-model="phaseD.incident24.incident_id" :placeholder="$t('nis2.assistentenPanel.incidentIDOderLeerGenerieren')" />
          <input v-model="phaseD.incident24.detected_at" :placeholder="$t('nis2.assistentenPanel.eintrittYYYYMMDDHHMM')" />
          <textarea v-model="phaseD.incident24.summary" :placeholder="$t('nis2.assistentenPanel.kurzbeschreibung')" rows="2" />
          <input v-model="phaseD.incident24.suspected_cause" :placeholder="$t('nis2.assistentenPanel.vermuteteUrsache')" />
          <select v-model="phaseD.incident24.malicious_suspected">
            <option value="unklar">{{ $t('nis2.assistentenPanel.bosartigUnklar') }}</option>
            <option value="ja">{{ $t('nis2.assistentenPanel.bosartigJa') }}</option>
            <option value="nein">{{ $t('nis2.assistentenPanel.bosartigNein') }}</option>
          </select>
          <select v-model="phaseD.incident24.cross_border">
            <option value="unklar">{{ $t('nis2.assistentenPanel.grenzuberschrUnklar') }}</option>
            <option value="ja">{{ $t('nis2.assistentenPanel.grenzuberschrJa') }}</option>
            <option value="nein">{{ $t('nis2.assistentenPanel.grenzuberschrNein') }}</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="incident24ModalOpen = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!phaseD.incident24.summary?.trim()"
                  @click="startPhaseDWizard('incident-24h', phaseD.incident24, () => incident24ModalOpen = false)">{{ $t('common.promptGenerieren') }}</button>
        </div>
      </div>
    </div>

    <!-- N15 72h-Aktualisierung -->
    <div v-if="incident72ModalOpen" class="wizard-modal-overlay" @mousedown.self="incident72ModalOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.assistentenPanel.n15HAktualisierungArtAbsLitB') }}</h3>
        <p class="hint">{{ $t('nis2.assistentenPanel.folgemeldungMitErsteinschatzungSchwe') }}</p>
        <div class="form-grid">
          <input v-model="phaseD.incident72.incident_id" :placeholder="$t('nis2.assistentenPanel.incidentIDGleicheWieH')" />
          <input v-model="phaseD.incident72.first_notified_at" :placeholder="$t('nis2.assistentenPanel.hMeldungAm')" />
          <select v-model="phaseD.incident72.severity">
            <option value="">{{ $t('nis2.assistentenPanel.schweregrad') }}</option>
            <option value="niedrig">{{ $t('dsgvo.dSFADetailPanel.niedrig') }}</option>
            <option value="mittel">{{ $t('dsgvo.dSFADetailPanel.mittel') }}</option>
            <option value="hoch">{{ $t('aiact.aIActAssistentenTab.hoch') }}</option>
            <option value="kritisch">kritisch</option>
          </select>
          <input v-model="phaseD.incident72.affected_services" :placeholder="$t('nis2.assistentenPanel.betroffeneServices')" />
          <textarea v-model="phaseD.incident72.impact_preliminary" :placeholder="$t('nis2.assistentenPanel.auswirkungVorlaufig')" rows="2" />
          <textarea v-model="phaseD.incident72.immediate_actions" :placeholder="$t('common.sofortmassnahmen')" rows="2" />
          <textarea v-model="phaseD.incident72.iocs" :placeholder="$t('nis2.assistentenPanel.bekannteIoCsZBIPsHashes')" rows="2" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="incident72ModalOpen = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!phaseD.incident72.incident_id?.trim()"
                  @click="startPhaseDWizard('incident-72h', phaseD.incident72, () => incident72ModalOpen = false)">{{ $t('common.promptGenerieren') }}</button>
        </div>
      </div>
    </div>

    <!-- N15 1-Monats-Abschlussmeldung -->
    <div v-if="incidentFinalModalOpen" class="wizard-modal-overlay" @mousedown.self="incidentFinalModalOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.assistentenPanel.n15MonatsAbschlussmeldungArtAbsLitC') }}</h3>
        <p class="hint">{{ $t('nis2.assistentenPanel.vollstandigerFinalReportVorfallBesch') }}</p>
        <div class="form-grid">
          <input v-model="phaseD.incidentFinal.incident_id" :placeholder="$t('nis2.assistentenPanel.incidentID')" />
          <input v-model="phaseD.incidentFinal.detected_at" :placeholder="$t('nis2.assistentenPanel.eintritt')" />
          <input v-model="phaseD.incidentFinal.resolved_at" :placeholder="$t('nis2.assistentenPanel.behebungAm')" />
          <select v-model="phaseD.incidentFinal.severity">
            <option value="">{{ $t('nis2.assistentenPanel.endgSchweregrad') }}</option>
            <option value="niedrig">{{ $t('dsgvo.dSFADetailPanel.niedrig') }}</option>
            <option value="mittel">{{ $t('dsgvo.dSFADetailPanel.mittel') }}</option>
            <option value="hoch">{{ $t('aiact.aIActAssistentenTab.hoch') }}</option>
            <option value="kritisch">kritisch</option>
          </select>
          <textarea v-model="phaseD.incidentFinal.root_cause" placeholder="Root-Cause / Bedrohungsart" rows="2" />
          <textarea v-model="phaseD.incidentFinal.mitigations" :placeholder="$t('nis2.assistentenPanel.umgesetzteMassnahmen')" rows="2" />
          <textarea v-model="phaseD.incidentFinal.lessons_learned" :placeholder="$t('nis2.assistentenPanel.lessonsLearned')" rows="2" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="incidentFinalModalOpen = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!phaseD.incidentFinal.incident_id?.trim()"
                  @click="startPhaseDWizard('incident-final', phaseD.incidentFinal, () => incidentFinalModalOpen = false)">{{ $t('common.promptGenerieren') }}</button>
        </div>
      </div>
    </div>

    <!-- N16 Cyberhygiene-Quiz -->
    <div v-if="quizModalOpen" class="wizard-modal-overlay" @mousedown.self="quizModalOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.assistentenPanel.n16CyberhygieneQuizFurMitarbeiter') }}</h3>
        <p class="hint">{{ $t('nis2.assistentenPanel.fragenQuizMCTrueFalseFurAwarenessTes') }}</p>
        <div class="row">
          <select v-model="phaseD.quiz.niveau">
            <option value="leicht">{{ $t('nis2.assistentenPanel.niveauLeicht') }}</option>
            <option value="mittel">{{ $t('nis2.assistentenPanel.niveauMittel') }}</option>
            <option value="hoch">{{ $t('nis2.assistentenPanel.niveauHoch') }}</option>
          </select>
          <button class="btn-primary" @click="startPhaseDWizard('cyberhygiene-quiz', phaseD.quiz, () => quizModalOpen = false)">{{ $t('nis2.assistentenPanel.quizErzeugen') }}</button>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="quizModalOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- N17 Vendor-Tiering -->
    <div v-if="tieringModalOpen" class="wizard-modal-overlay" @mousedown.self="tieringModalOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.assistentenPanel.n17LieferantenRisikoBewertungTiering') }}</h3>
        <p class="hint">{{ $t('nis2.assistentenPanel.klassifizierungKritischWichtigNormal') }} <strong>{{ $t('nis2.assistentenPanel.n4SupplyChainSecurity') }}</strong> {{ $t('nis2.assistentenPanel.pflichtDokuAngelegt') }}</p>
        <div v-if="store.vendors.length === 0" class="info-no-vendor">
          {{ $t('nis2.assistentenPanel.nochKeineVendorenInN4BitteZuerstEine') }}
        </div>
        <div v-else class="row">
          <select v-model="phaseD.tieringVendorId">
            <option value="">{{ $t('nis2.assistentenPanel.vendorWahlen') }}</option>
            <option v-for="v in store.vendors" :key="v.id" :value="v.id">
              {{ v.vendor_name }} ({{ v.leistung || '—' }})
            </option>
          </select>
          <button class="btn-primary" :disabled="!phaseD.tieringVendorId" @click="startTiering">{{ $t('nis2.assistentenPanel.tiering') }}</button>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="tieringModalOpen = false">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- Prompt-Wizard-Modal (Copy-Paste-JSON) -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @mousedown.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <p v-if="isDocOnlyWizard" class="hint">{{ $t('nis2.assistentenPanel.promptNachChatGPTKopierenJSONAntwort') }}</p>
        <p v-else class="hint">{{ $t('nis2.assistentenPanel.promptNachChatGPTKopierenJSONAntwort2') }}</p>
        <PromptAustausch v-model="wizardModal.response" :prompt="wizardModal.prompt"
                         prompt-titel="Prompt (zum Kopieren)"
                         antwort-titel="ChatGPT-Antwort (JSON)" :nummeriert="false"
                         :platzhalter="'JSON hier einfügen...'">
          <template #prompt-aktionen>
            <button class="btn-link" :disabled="wizardModal.running" @click="runWizardDirect">{{ $t('common.direktMitKIAusfuhren') }}</button>
          </template>
          <template #nach-prompt>
        <FehlerHinweis v-if="wizardModal.fehler" :text="wizardModal.fehler"
                       @close="wizardModal.fehler = ''" />
        <div v-if="wizardModal.running" class="ki-run">
          <!-- #1834/#1836/E6: eigene Hinweise auch hier. Die Engine
               setzt sie serverseitig ein (shared/ki_engine). -->
          <PromptZusatzFeld v-model="zusatz" modul="nis2" :projekt="store.selectedProjekt" bereich="assistent" />
          <KiStreamView :url="`/api/ai/run-stream`" :confirm-egress="true" :body="{ prompt: wizardModal.prompt, prompt_zusatz: zusatz }"
                        @done="onWizardRunDone" @error="onWizardRunError" />
        </div>
          </template>
        </PromptAustausch>
        <div v-if="wizardModal.parsed" class="parsed-result">
          <strong v-if="wizardModal.parsed.applied" style="color: #2e7d32;">{{ $t('common.angewendetGespeichert') }}</strong>
          <strong v-else style="color: #e65100;">{{ $t('nis2.assistentenPanel.geparsedNurVorschauNichtGespeichert') }}</strong>
          <!-- #1445–#1449: Markdown zum Übernehmen als Dokument -->
          <template v-if="isDocOnlyWizard && wizardModal.parsed.markdown">
            <label>{{ $t('nis2.assistentenPanel.markdownFurDasPflichtdokument') }}</label>
            <textarea readonly :value="wizardModal.parsed.markdown" rows="8" class="mono"></textarea>
          </template>
          <pre>{{ JSON.stringify(wizardModal.parsed, null, 2) }}</pre>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeWizard">{{ $t('common.cancel') }}</button>
          <button class="btn-secondary" :disabled="!wizardModal.response" @click="parseOnly">{{ $t('common.nurParsen') }}</button>
          <button v-if="isDocOnlyWizard" class="btn-primary" :disabled="!docSaveText" @click="saveDocFromWizard">{{ $t('common.alsDokumentSpeichern') }}</button>
          <button v-if="!isDocOnlyWizard" class="btn-primary" :disabled="!wizardModal.response" @click="parseAndApply">{{ $t('common.parsenAnwenden') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import PromptZusatzFeld from '../../components/shared/PromptZusatzFeld.vue'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
import { useNis2Store } from '../../stores/nis2'
import AssistentenKachelGrid from '../../components/assistenten/AssistentenKachelGrid.vue'
import { parsedToMarkdown } from '../../utils/parsedToMarkdown'
import { buildWizardList, type WizardDescriptor } from '../../components/assistenten/registry'
import KiStreamView from '../../components/shared/KiStreamView.vue'
import PromptAustausch from '../../components/shared/PromptAustausch.vue'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'
// #1366: Assistenten-Prompt direkt über den Provider (lokal/Cloud) ausführen.
const runWizardDirect = () => { wizardModal.value.running = true }
const onWizardRunDone = async (p: any) => {
  wizardModal.value.running = false
  wizardModal.value.response = (p?.text || '').trim()
  // #1902: Ohne das Parsen bleibt `wizardModal.parsed` null — der ganze
  // Ergebnisblock hängt daran, und der Anwender müsste nach einem Direktlauf
  // zusätzlich „Nur parsen" drücken. Beide Wege müssen im selben Zustand
  // enden. Geparst, nicht angewendet: Speichern bleibt sein Klick (#1773).
  if (!wizardModal.value.response) return
  try { await parseOnly() } catch { /* der Fehler steht im Store */ }
}
const onWizardRunError = (msg: string) => {
  // #1839: `running = false` unmountet die KiStreamView — und damit die
  // Komponente, die die Meldung ANZEIGTE. Ein 409 „kein KI-Provider
  // verfügbar" verschwand dadurch spurlos: keine Meldung, keine Konsole,
  // ein leeres Antwortfeld. Der Text muss außerhalb des Streams liegen.
  wizardModal.value.running = false
  wizardModal.value.fehler = msg || uebersetze('common.derKILaufIstFehlgeschlagen')
}

const store = useNis2Store()

// #1445–#1449: Grid-Ref, um das Wizard-Ergebnis an den „Als Dokument speichern"-
// Dialog zu übergeben (der Dialog war zuvor leer → nicht speicherbar).
// #1834: eigene Hinweise des Bearbeiters für diesen Lauf.
const zusatz = ref('')
const grid = ref<InstanceType<typeof AssistentenKachelGrid> | null>(null)

const emit = defineEmits<{
  /** Signals the host that pflicht-doku data changed and should reload. */
  (e: 'applied'): void
  /** #1240/#1235: Sprung ins Dokumente-Register (gerade gespeichertes Dokument). */
  (e: 'open-in-register', id: number): void
}>()

// ── Tile-Registry (#1095) ───────────────────────────────────────────────────
const wizards: WizardDescriptor[] = buildWizardList([
  {
    id: 'nis2-asset-wizard',
    title: 'N1 — Asset-Inventar-Wizard',
    description: uebersetze('nis2.assistentenPanel.copyPasteAssistentDerEinVollstandige'),
    kategorie: 'dokumentation',
    icon: '🤖',
  },
  {
    id: 'nis2-klassifikator',
    title: 'N6 — Entity-Klassifikator',
    description: uebersetze('nis2.assistentenPanel.bestimmtEssentialImportantOutOfScope'),
    kategorie: 'compliance',
    icon: '📝',
  },
  {
    id: 'nis2-sektor-template',
    title: 'N7 — Sektor-Template',
    description: uebersetze('nis2.assistentenPanel.setztSektorSpezifischeDefaultsFurCSI'),
    kategorie: 'compliance',
    icon: '⚡',
  },
  {
    id: 'nis2-incident-notification',
    title: 'N8 — Incident-Notification',
    description: uebersetze('nis2.assistentenPanel.erzeugtDieDreiPflichtigenCSIRTMeldun'),
    kategorie: 'compliance',
    icon: '🚨',
  },
  {
    id: 'nis2-supply-chain',
    title: 'N9 — Supply-Chain-Assessment',
    description: uebersetze('nis2.assistentenPanel.kategorienBewertungsrasterProVendorI'),
    kategorie: 'risiko',
    icon: '🔗',
  },
  {
    id: 'nis2-incident-24h',
    title: 'N14 — 24h-Erstmeldung',
    description: uebersetze('nis2.assistentenPanel.kurzmeldungImBSIPortalFormatArtAbsLi'),
    kategorie: 'compliance',
    icon: '⏱️',
  },
  {
    id: 'nis2-incident-72h',
    title: 'N15 — 72h-Aktualisierung',
    description: uebersetze('nis2.assistentenPanel.folgemeldungMitErsteinschatzungSchwe'),
    kategorie: 'compliance',
    icon: '📨',
  },
  {
    id: 'nis2-incident-final',
    title: 'N15 — 1-Monats-Abschlussmeldung',
    description: uebersetze('nis2.assistentenPanel.vollstandigerFinalReportMitRootCause'),
    kategorie: 'compliance',
    icon: '📑',
  },
  {
    id: 'nis2-cyberhygiene-quiz',
    title: 'N16 — Cyberhygiene-Quiz',
    description: uebersetze('nis2.assistentenPanel.fragenAwarenessQuizFurMitarbeitendeP'),
    kategorie: 'dokumentation',
    icon: '🎓',
  },
  {
    id: 'nis2-vendor-tiering',
    title: 'N17 — Vendor-Tiering',
    description: uebersetze('nis2.assistentenPanel.klassifiziertLieferantenKritischWich'),
    kategorie: 'risiko',
    icon: '🏷️',
  },
  // ── #1240: Pflichtdokument-Generatoren (Art. 21(2)) ───────────────────────
  // Ergebnis → editier-/freigabe-/exportierbares managed_doc (#1235).
  {
    id: 'nis2-is-leitlinie',
    title: uebersetze('nis2.assistentenPanel.iSLeitlinieRisikoanalyse'),
    description: uebersetze('nis2.assistentenPanel.erzeugtEineInformationssicherheitsLe'),
    kategorie: 'dokumentation',
    icon: '📘',
    produces_document: { doc_type: 'is_leitlinie' },
  },
  {
    id: 'nis2-incident-handling-konzept',
    title: uebersetze('nis2.assistentenPanel.incidentHandlingKonzept'),
    description: uebersetze('nis2.assistentenPanel.erzeugtEinKonzeptZurVorfallsbehandlu'),
    kategorie: 'dokumentation',
    icon: '🛠️',
    produces_document: { doc_type: 'incident_handling_konzept' },
  },
  {
    id: 'nis2-bcm-dr-plan',
    title: 'BCM-/DR-Plan',
    description: uebersetze('nis2.assistentenPanel.erzeugtEinenBusinessContinuityDisast'),
    kategorie: 'dokumentation',
    icon: '🔁',
    produces_document: { doc_type: 'bcm_dr_plan' },
  },
  {
    id: 'nis2-lieferketten-richtlinie',
    title: uebersetze('nis2.assistentenPanel.lieferkettenSicherheitsrichtlinie'),
    description: uebersetze('nis2.assistentenPanel.erzeugtEineLieferkettenSicherheitsri'),
    kategorie: 'dokumentation',
    icon: '🔗',
    produces_document: { doc_type: 'lieferketten_richtlinie' },
  },
  {
    id: 'nis2-krypto-richtlinie',
    title: uebersetze('nis2.assistentenPanel.kryptoVerschlusselungsrichtlinie'),
    description: uebersetze('nis2.assistentenPanel.erzeugtEineKryptoVerschlusselungsric'),
    kategorie: 'dokumentation',
    icon: '🔐',
    produces_document: { doc_type: 'krypto_richtlinie' },
  },
  {
    id: 'nis2-zugriffskontroll-policy',
    title: 'Zugriffskontroll-/Asset-Policy',
    description: uebersetze('nis2.assistentenPanel.erzeugtEineZugriffskontrollUndAssetM'),
    kategorie: 'dokumentation',
    icon: '🗝️',
    produces_document: { doc_type: 'zugriffskontroll_policy' },
  },
])

// ── Daten laden (Vendoren für N9/N17, Sektor-Templates für N7) ───────────────
const reloadData = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchVendors(),
    store.fetchSektorTemplates(),
    store.fetchIncidentResponse(),
    store.fetchBcp(),
  ])
}
onMounted(reloadData)
watch(() => store.selectedProjekt, reloadData)

// ── Modal-State je Wizard ────────────────────────────────────────────────────
const sektorModalOpen = ref(false)
const incidentModalOpen = ref(false)
const supplyChainModalOpen = ref(false)
const incident24ModalOpen = ref(false)
const incident72ModalOpen = ref(false)
const incidentFinalModalOpen = ref(false)
const quizModalOpen = ref(false)
const tieringModalOpen = ref(false)

// #1240: Doc-only-Generatoren — id (Kachel) → Backend-Wizard-Kind.
const DOC_WIZARD_KIND: Record<string, DocWizardKind> = {
  'nis2-is-leitlinie': 'is-leitlinie',
  'nis2-incident-handling-konzept': 'incident-handling-konzept',
  'nis2-bcm-dr-plan': 'bcm-dr-plan',
  'nis2-lieferketten-richtlinie': 'lieferketten-richtlinie',
  'nis2-krypto-richtlinie': 'krypto-richtlinie',
  'nis2-zugriffskontroll-policy': 'zugriffskontroll-policy',
}

// Tile-Dispatch: id → Wizard öffnen (in DIESEM Panel, kein Routing).
const openTile = (id: string) => {
  if (id in DOC_WIZARD_KIND) { openWizard(DOC_WIZARD_KIND[id]); return }
  switch (id) {
    case 'nis2-asset-wizard': openAssetWizard(); break
    case 'nis2-klassifikator': openWizard('klassifikator'); break
    case 'nis2-sektor-template': selectedSektor.value = ''; sektorApplied.value = false; sektorModalOpen.value = true; break
    case 'nis2-incident-notification': incidentModalOpen.value = true; break
    case 'nis2-supply-chain': assessmentVendorId.value = ''; supplyChainModalOpen.value = true; break
    case 'nis2-incident-24h': incident24ModalOpen.value = true; break
    case 'nis2-incident-72h': incident72ModalOpen.value = true; break
    case 'nis2-incident-final': incidentFinalModalOpen.value = true; break
    case 'nis2-cyberhygiene-quiz': quizModalOpen.value = true; break
    case 'nis2-vendor-tiering': phaseD.value.tieringVendorId = ''; tieringModalOpen.value = true; break
  }
}

// ── Prompt-Wizard-Modal (Copy-Paste-JSON) ────────────────────────────────────
const wizardModal = ref<any>({ open: false, fehler: '', kind: '', title: '', prompt: '', response: '', parsed: null, extra: {} })

// #1240: Diese Wizards persistieren NICHT direkt — ihr Ergebnis wird per
// „📄 Als Dokument speichern" zum managed_doc. Im Modal nur „Nur parsen".
type DocWizardKind =
  | 'is-leitlinie' | 'incident-handling-konzept' | 'bcm-dr-plan'
  | 'lieferketten-richtlinie' | 'krypto-richtlinie' | 'zugriffskontroll-policy'
const DOC_ONLY_WIZARDS: ReadonlySet<string> = new Set<DocWizardKind>([
  'is-leitlinie', 'incident-handling-konzept', 'bcm-dr-plan',
  'lieferketten-richtlinie', 'krypto-richtlinie', 'zugriffskontroll-policy',
])
const isDocOnlyWizard = computed(() => DOC_ONLY_WIZARDS.has(wizardModal.value.kind))

const WIZARD_TITLES: Record<string, string> = {
  'klassifikator': 'NIS2-Entity-Klassifikator',
  'incident-notification': uebersetze('nis2.assistentenPanel.incidentNotificationGenerator'),
  'supply-chain': uebersetze('nis2.assistentenPanel.supplyChainAssessment'),
  'incident-24h': '24h-Erstmeldung (Art. 23 Abs. 4 lit. a)',
  'incident-72h': '72h-Aktualisierung (Art. 23 Abs. 4 lit. b)',
  'incident-final': '1-Monats-Abschlussmeldung (Art. 23 Abs. 4 lit. d)',
  'cyberhygiene-quiz': uebersetze('nis2.assistentenPanel.cyberhygieneQuiz'),
  'vendor-tiering': 'Vendor-Tiering (kritisch/wichtig/normal)',
  'is-leitlinie': uebersetze('nis2.assistentenPanel.iSLeitlinieRisikoanalyseArtA'),
  'incident-handling-konzept': 'Incident-Handling-Konzept (Art. 21(2)b)',
  'bcm-dr-plan': uebersetze('nis2.assistentenPanel.bCMDRPlanArtC'),
  'lieferketten-richtlinie': 'Lieferketten-Sicherheitsrichtlinie (Art. 21(2)d)',
  'krypto-richtlinie': uebersetze('nis2.assistentenPanel.kryptoVerschlusselungsrichtlinieArtH'),
  'zugriffskontroll-policy': 'Zugriffskontroll-/Asset-Policy (Art. 21(2)i/j)',
}

type WizardKind = 'klassifikator' | 'incident-notification' | 'supply-chain' | 'incident-24h' | 'incident-72h' | 'incident-final' | 'cyberhygiene-quiz' | 'vendor-tiering' | DocWizardKind

const openWizard = async (kind: WizardKind, extra: any = {}) => {
  const prompt = await store.getWizardPrompt(kind, extra)
  wizardModal.value = { open: true, kind, title: WIZARD_TITLES[kind], prompt, response: '', parsed: null, extra }
}

const closeWizard = () => { wizardModal.value = { open: false, kind: '', title: '', prompt: '', response: '', parsed: null, extra: {} } }


// #1240: Doc-only-Wizards — nur Vorschau parsen (keine Persistenz).
const parseOnly = async () => {
  wizardModal.value.parsed = await store.parseWizardResponse(
    wizardModal.value.kind, wizardModal.value.response, wizardModal.value.extra, false)
}

// #1445–#1449: Doc-only-Ergebnis (geparster Markdown bzw. Roh-Antwort) als Dokument
// speichern. Modal-`kind` ist die Kurzform → zurück auf die Kachel-id mappen.
const KIND_TO_TILE_ID: Record<string, string> = Object.fromEntries(
  Object.entries(DOC_WIZARD_KIND).map(([tileId, kind]) => [kind, tileId]),
)
const docSaveText = computed(
  () => parsedToMarkdown(wizardModal.value.parsed, wizardModal.value.response),
)
const saveDocFromWizard = () => {
  const text = docSaveText.value
  const tileId = KIND_TO_TILE_ID[wizardModal.value.kind]
  if (!text || !tileId) return
  grid.value?.openSaveDialogFor(tileId, text)
  closeWizard()
}

const parseAndApply = async () => {
  const { kind, response, extra } = wizardModal.value
  if (kind === 'asset-inventory') {
    // #1072: eigener Parse-Pfad (mehrere Assets auf einmal)
    wizardModal.value.parsed = await store.parseAssetWizardResponse(response, true)
  } else {
    wizardModal.value.parsed = await store.parseWizardResponse(kind, response, extra, true)
  }
  await reloadData()
  if (wizardModal.value.parsed?.applied) {
    emit('applied')
    setTimeout(closeWizard, 1200)
  }
}

// ── N1 Asset-Inventar-Wizard (Copy-Paste) ────────────────────────────────────
const openAssetWizard = async () => {
  const prompt = await store.getAssetWizardPrompt()
  wizardModal.value = { open: true, kind: 'asset-inventory', title: 'N1 Asset-Inventar-Wizard',
    prompt, response: '', parsed: null, extra: {} }
}

// ── N7 Sektor-Template ───────────────────────────────────────────────────────
const selectedSektor = ref('')
const sektorApplied = ref(false)
const sektorAppliedName = ref('')

const applySektor = async () => {
  if (!selectedSektor.value) return
  const tpl = store.sektorTemplates.find((t: any) => t.id === selectedSektor.value)
  if (await store.applySektorTemplate(selectedSektor.value)) {
    sektorApplied.value = true
    sektorAppliedName.value = tpl?.name || selectedSektor.value
    await reloadData()
    emit('applied')
    setTimeout(() => { sektorApplied.value = false }, 6000)
  }
}

// ── N8 Incident-Notification ─────────────────────────────────────────────────
const incidentMeta = ref({ description: '', severity: 'mittel', affected_services: '' })

const startIncidentNotification = async () => {
  if (!incidentMeta.value.description) return
  incidentModalOpen.value = false
  await openWizard('incident-notification', incidentMeta.value)
}

// ── N9 Supply-Chain-Assessment ───────────────────────────────────────────────
const assessmentVendorId = ref<number | ''>('')

const startSupplyChain = async () => {
  if (!assessmentVendorId.value) return
  const v = store.vendors.find((x: any) => x.id === assessmentVendorId.value)
  if (!v) return
  supplyChainModalOpen.value = false
  const prompt = await store.getWizardPrompt('supply-chain', v)
  wizardModal.value = {
    open: true, kind: 'supply-chain', title: WIZARD_TITLES['supply-chain'],
    prompt, response: '', parsed: null, extra: { vendor_id: assessmentVendorId.value },
  }
}

// ── Phase D — Incident-/Awareness-Wizards (#513-#516) ────────────────────────
const phaseD = ref<any>({
  incident24: { incident_id: '', detected_at: '', summary: '', suspected_cause: '',
                malicious_suspected: 'unklar', cross_border: 'unklar' },
  incident72: { incident_id: '', first_notified_at: '', current_status: 'in Analyse',
                impact_preliminary: '', severity: 'mittel', affected_services: '',
                immediate_actions: '', iocs: '' },
  incidentFinal: { incident_id: '', detected_at: '', resolved_at: '', severity: 'mittel',
                   root_cause: '', mitigations: '', lessons_learned: '' },
  quiz: { niveau: 'mittel', themen: null },
  tieringVendorId: '',
})

const startPhaseDWizard = async (
  kind: 'incident-24h' | 'incident-72h' | 'incident-final' | 'cyberhygiene-quiz',
  body: any,
  closeOwn: () => void,
) => {
  closeOwn()
  await openWizard(kind, body)
}

// ── N17 Vendor-Tiering ───────────────────────────────────────────────────────
const startTiering = async () => {
  if (!phaseD.value.tieringVendorId) return
  const v = store.vendors.find((x: any) => x.id === Number(phaseD.value.tieringVendorId))
  if (!v) return
  tieringModalOpen.value = false
  const body: any = {
    vendor_name: v.vendor_name,
    leistung: v.leistung,
    kritikalitaet: v.kritikalitaet,
    zertifikate: v.zertifikate || [],
  }
  const prompt = await store.getWizardPrompt('vendor-tiering', body)
  wizardModal.value = {
    open: true, kind: 'vendor-tiering', title: WIZARD_TITLES['vendor-tiering'],
    prompt, response: '', parsed: null, extra: { vendor_id: v.id },
  }
}
</script>

<style scoped>
.assistenten-panel { display: flex; flex-direction: column; gap: 16px; }

.info-banner { background: #ede7f6; padding: 16px 20px; border-radius: 8px; border-left: 4px solid #7b1fa2; }
.info-banner h3 { margin: 0 0 8px; color: #4a148c; }
.info-banner p { margin: 0; color: #444; line-height: 1.5; }

.row { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.row select { flex: 1; padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; margin: 8px 0; }
.form-grid input, .form-grid select, .form-grid textarea {
  padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit;
}
.form-grid textarea { grid-column: 1 / -1; }

.info-no-vendor {
  background: #fff3e0; border-left: 4px solid #ff9800; padding: 10px 14px;
  border-radius: 4px; font-size: 13px; margin: 8px 0;
}

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
.wizard-modal textarea, .wizard-modal select { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.wizard-modal .row select { width: auto; }
.wizard-modal .mono { font-family: monospace; font-size: 12px; }
.hint { color: #666; font-size: 13px; margin-top: 6px; }

.parsed-result { background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 12px; }
.parsed-result pre { margin: 6px 0 0; white-space: pre-wrap; font-size: 12px; }

.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #0d47a1; }
.btn-secondary { background: #eee; color: #333; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary:hover { background: #ddd; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 14px; color: #1565c0; padding: 4px 0; }
</style>
