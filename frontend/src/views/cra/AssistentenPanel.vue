<template>
  <div class="assistenten-panel">
    <div class="info-banner">
      <h3>{{ $t('cra.assistentenPanel.cRAAssistenten') }}</h3>
      <p>{{ $t('cra.assistentenPanel.alleKIGestutztenHelferDesCRAModulsAn') }}</p>
    </div>

    <AssistentenKachelGrid
      ref="grid"
      :wizards="wizards"
      grouped
      :modul="'cra'"
      :projekt="store.selectedProjekt"
      @open="openWizard"
      @open-in-register="(id: number) => emit('open-in-register', id)"
    />

    <!-- Branchen-Template-Wizard (C7) -->
    <div v-if="brancheWizardOpen" class="wizard-modal-overlay" @mousedown.self="brancheWizardOpen = false">
      <div class="wizard-modal">
        <h3>{{ $t('cra.assistentenPanel.branchenTemplateAnwenden') }}</h3>
        <p class="hint">{{ $t('cra.assistentenPanel.setztSinnvolleDefaultsFurPSIRTSLAsSu') }}</p>

        <label>{{ $t('cra.assistentenPanel.branche') }}</label>
        <select v-model="selectedBranche">
          <option value="">{{ $t('cra.assistentenPanel.brancheWahlen') }}</option>
          <option v-for="t in store.branchenTemplates" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>

        <div v-if="brancheApplied" class="branche-applied">
          {{ $t('common.template') }} <strong>{{ brancheAppliedName }}</strong> {{ $t('cra.assistentenPanel.angewendetFolgendeDefaultsWurdenGese') }}
          <ul>
            <li v-for="(v, k) in brancheAppliedDefaults" :key="k"><strong>{{ k }}</strong>: {{ v }}</li>
          </ul>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" @click="brancheWizardOpen = false">{{ $t('common.close') }}</button>
          <button class="btn-primary" :disabled="!selectedBranche" @click="applyBranche">{{ $t('cra.assistentenPanel.anwenden') }}</button>
        </div>
      </div>
    </div>

    <!-- Prompt-Wizard-Dialog (C6 / C8 / C9) -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @mousedown.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <p v-if="nichtBereit" class="hint">{{ $t('cra.assistentenPanel.erstDieAkteDannDerEntwurf') }}</p>
        <p v-else-if="isDocOnlyWizard" class="hint">{{ $t('cra.assistentenPanel.kopiereDenPromptNachChatGPTAntwortAl') }}</p>
        <p v-else class="hint">{{ $t('cra.assistentenPanel.kopiereDenPromptNachChatGPTAntwortAl2') }}</p>

        <!-- #1874: Vollständigkeit nach Anhang V VOR dem Prompt. Damit ist
             sichtbar, ob ein lückenloses Dokument überhaupt entstehen kann —
             statt die Lücken der KI als „[zu ergänzen]" zu überlassen.
             Gerechnet wird nichts neu: dieselbe Quelle, gegen die
             `ausstellen()` seit #1814 prüft. -->
        <!-- #1901: Der Lauf startet nicht, solange die Akte ihn nicht trägt.
             Was die KI nur benennen, aber nicht beheben könnte, soll sie nicht
             für einen Lauf vorlesen — das kam aus dem Betrieb als Entwurf mit
             drei Bemerkungen zurück. -->
        <div v-if="nichtBereit" class="nicht-bereit">
          <strong>{{ $t('cra.assistentenPanel.derAssistentLauftHierNochNicht') }}</strong>
          <p>{{ nichtBereit.error }}</p>
          <ul v-if="nichtBereit.befunde?.length">
            <li v-for="(b, i) in nichtBereit.befunde" :key="'b' + i">
              <span class="nr">Nr. {{ b.nr }}</span> {{ b.text }}
              <span v-if="b.hinweis" class="hint-sub">{{ b.hinweis }}</span>
            </li>
          </ul>
          <ul v-if="nichtBereit.fehlend?.length">
            <li v-for="(f, i) in nichtBereit.fehlend" :key="'f' + i">
              <span class="nr">Nr. {{ f.nr }}</span> {{ f.bezeichnung }} fehlt
            </li>
          </ul>
        </div>
        <div v-else-if="wizardModal.kind === 'eu-doc' && vollst" class="anhang-v-check"
             :class="vollst.vollstaendig ? 'ok' : 'luecken'">
          <strong v-if="vollst.vollstaendig">{{ $t('cra.assistentenPanel.allePflichtangabenNachAnhangVSindErf') }}</strong>
          <template v-else>
            <strong>{{ $t('cra.assistentenPanel.v0PflichtangabeNNachAnhangVFehlen', { v0: vollst.fehlend.length }) }}</strong>
            <p class="hint-sub">{{ $t('cra.assistentenPanel.wasHierFehltKannAuchDieKINichtErfind') }}</p>
          </template>
          <ul>
            <li v-for="a in vollst.angaben" :key="a.nr + a.bezeichnung"
                :class="{ fehlt: !a.erfasst }">
              <span class="nr">Nr. {{ a.nr }}</span>
              {{ a.bezeichnung }}
              <span v-if="a.erfasst" class="ja">{{ $t('cra.assistentenPanel.erfasst') }}</span>
              <span v-else class="nein">fehlt: {{ a.leere_felder.join(', ') }}</span>
            </li>
          </ul>
        </div>
        <PromptAustausch v-if="!nichtBereit"
                         v-model="wizardModal.response" :prompt="wizardModal.prompt"
                         prompt-titel="Prompt (zum Kopieren)"
                         antwort-titel="ChatGPT-Antwort (JSON)" :nummeriert="false"
                         :platzhalter="'Hier die ChatGPT-Antwort einfügen...'">
          <template #prompt-aktionen>
            <button class="btn-link" :disabled="wizardModal.running" @click="runWizardDirect">{{ $t('common.direktMitKIAusfuhren') }}</button>
          </template>
          <template #nach-prompt>
        <!-- #1366: Direkt über den Provider (lokal/Cloud) ausführen statt Copy/Paste -->
        <FehlerHinweis v-if="wizardModal.fehler" :text="wizardModal.fehler"
                       @close="wizardModal.fehler = ''" />
        <div v-if="wizardModal.running" class="ki-run">
          <!-- #1834/#1836/E6: eigene Hinweise auch hier. Die Engine
               setzt sie serverseitig ein (shared/ki_engine). -->
          <PromptZusatzFeld v-model="zusatz" modul="cra" :projekt="store.selectedProjekt" bereich="assistent" />
          <KiStreamView :url="`/api/ai/run-stream`" :confirm-egress="true" :body="{ prompt: wizardModal.prompt, prompt_zusatz: zusatz }"
                        @done="onWizardRunDone" @error="onWizardRunError" />
        </div>

          </template>
        </PromptAustausch>

        <div v-if="wizardModal.parsed" class="parsed-result">
          <strong v-if="wizardModal.parsed.applied" style="color: #2e7d32;">{{ $t('common.angewendetGespeichert') }}</strong>
          <strong v-else style="color: #e65100;">{{ $t('cra.assistentenPanel.geparsedNurVorschauNichtGespeichert') }}</strong>
          <!-- #1249: Markdown zum Übernehmen in DoC / technische Doku -->
          <template v-if="wizardModal.parsed.markdown">
            <label>{{ $t('cra.assistentenPanel.markdownFurKonformitatserklarungTech') }}</label>
            <textarea readonly :value="wizardModal.parsed.markdown" rows="8" class="mono"></textarea>
            <button class="btn-link" @click="copyMarkdown">
              {{ markdownKopiert ? $t('cra.assistentenPanel.kopiert') : $t('cra.assistentenPanel.markdownKopieren') }}</button>
            <p class="hint">{{ $t('cra.assistentenPanel.anschliessendUberDieKachelAlsDokumen') }}</p>
          </template>
          <pre>{{ JSON.stringify(wizardModal.parsed, null, 2) }}</pre>
        </div>

        <div v-if="nichtBereit" class="modal-actions">
          <button class="btn-primary" @click="closeWizard">{{ $t('cra.assistentenPanel.verstandenZurAkte') }}</button>
        </div>
        <div v-else class="modal-actions">
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
import { ref, computed, onMounted } from 'vue'
import { kopiere } from '../../utils/zwischenablage'
import PromptZusatzFeld from '../../components/shared/PromptZusatzFeld.vue'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
import { useCraStore } from '../../stores/cra'
import AssistentenKachelGrid from '../../components/assistenten/AssistentenKachelGrid.vue'
import { parsedToMarkdown } from '../../utils/parsedToMarkdown'
import KiStreamView from '../../components/shared/KiStreamView.vue'
import PromptAustausch from '../../components/shared/PromptAustausch.vue'

// #1445–#1449: Grid-Ref, um das Wizard-Ergebnis an den „Als Dokument speichern"-
// Dialog zu übergeben (der Dialog war zuvor leer → nicht speicherbar).
// #1834: eigene Hinweise des Bearbeiters für diesen Lauf.
const zusatz = ref('')
const grid = ref<InstanceType<typeof AssistentenKachelGrid> | null>(null)

// #1366: Assistenten-Prompt direkt über den Provider (lokal/Cloud) ausführen.
const runWizardDirect = () => { wizardModal.value.running = true }
const onWizardRunDone = async (p: any) => {
  wizardModal.value.running = false
  wizardModal.value.response = (p?.text || '').trim()
  // #1902: Der Direktlauf legte die Antwort nur ins Feld und parste nicht.
  // Damit blieb `parsed` null, der Markdown-Kasten erschien nie, und
  // „📄 Als Dokument speichern" bekam über `parsedToMarkdown` nur den
  // Rückfall auf den Rohtext. Beobachtet bei der Konformitätserklärung und
  // der SBOM-Doku. Zwei Wege zur selben Handlung müssen im selben Zustand
  // enden — beim Einfügen tut genau das der Klick auf „Nur parsen".
  //
  // **Geparst, nicht angewendet:** Speichern ist eine Entscheidung des
  // Anwenders, und ein Direktlauf ist keine Zustimmung dazu (die Linie aus
  // #1773). „Anwenden" bleibt sein Klick.
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
import { buildWizardList, type WizardDescriptor } from '../../components/assistenten/registry'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'

const store = useCraStore()

const emit = defineEmits<{
  /** Signals the host that pflicht-doku data changed and should reload. */
  (e: 'applied'): void
  /** #1235: Bubble the Register-Sprung up to the CRA view (Tab-Wechsel + Editor). */
  (e: 'open-in-register', id: number): void
}>()

// ── Tile-Registry (S11 / #1081) ─────────────────────────────────────────────
const wizards: WizardDescriptor[] = buildWizardList([
  {
    id: 'klassifikator',
    title: 'C6 — CRA-Klassifikator',
    description: uebersetze('cra.assistentenPanel.bestimmtAutomatischDieProduktklasseD'),
    kategorie: 'compliance',
    icon: '📌',
  },
  {
    id: 'branche',
    title: 'C7 — Branchen-Template',
    description: uebersetze('cra.assistentenPanel.setztBranchenublicheDefaultsFurPSIRT'),
    kategorie: 'compliance',
    icon: '🏭',
  },
  {
    id: 'vuln-policy',
    title: 'C8 — Vulnerability-Disclosure-Policy',
    description: uebersetze('cra.assistentenPanel.generiertEinenVollstandigenPolicyTex'),
    kategorie: 'dokumentation',
    icon: '📝',
    // #1235: Ergebnis als editier-/exportierbares managed_doc speicherbar.
    produces_document: { doc_type: 'vuln_disclosure_policy' },
  },
  {
    id: 'update-policy',
    title: 'C9 — Security-Update-Policy',
    description: uebersetze('cra.assistentenPanel.generiertEineUpdatePolicyMitKadenzOu'),
    kategorie: 'dokumentation',
    icon: '🔄',
    // #1235: Ergebnis als editier-/exportierbares managed_doc speicherbar.
    produces_document: { doc_type: 'update_policy' },
  },
  {
    id: 'eu-doc',
    title: uebersetze('cra.assistentenPanel.eUKonformitatserklarungAnnexV'),
    description: uebersetze('cra.assistentenPanel.erzeugtKIGestutztEinenAnnexVKonforme'),
    kategorie: 'dokumentation',
    icon: '📜',
    // #1237: Ergebnis als editier-/freigabe-/exportierbares managed_doc speicherbar.
    produces_document: { doc_type: 'konformitaetserklaerung' },
  },
  {
    id: 'sbom-doc',
    title: uebersetze('cra.assistentenPanel.sBOMBegleitdokument'),
    description: uebersetze('cra.assistentenPanel.erzeugtKIGestutztEinSBOMBegleitdokum'),
    kategorie: 'dokumentation',
    icon: '📦',
    // #1239: Ergebnis als editier-/freigabe-/exportierbares managed_doc speicherbar.
    produces_document: { doc_type: 'sbom_begleitdoc' },
  },
  {
    id: 'version-changes',
    title: uebersetze('cra.assistentenPanel.wesentlicheAnderungenJeVersion'),
    description: uebersetze('cra.assistentenPanel.fasstDieAusGitHubGitLabImportiertenV'),
    kategorie: 'dokumentation',
    icon: '📈',
    // #1249: Ergebnis als editier-/exportierbarer Änderungs-Abschnitt der Annex-VII-Doku.
    produces_document: { doc_type: 'technische_doku_annex_vii' },
  },
])

onMounted(() => store.fetchBranchenTemplates())

const openWizard = (id: string) => {
  if (id === 'branche') {
    selectedBranche.value = ''
    brancheApplied.value = false
    brancheWizardOpen.value = true
    return
  }
  openPromptWizard(id as PromptWizardKind)
}

// ── Branchen-Template (C7) ──────────────────────────────────────────────────
const brancheWizardOpen = ref(false)
const selectedBranche = ref('')
const brancheApplied = ref(false)
const brancheAppliedName = ref('')
const brancheAppliedDefaults = ref<Record<string, any>>({})

const applyBranche = async () => {
  if (!selectedBranche.value) return
  const tpl = store.branchenTemplates.find((t: any) => t.id === selectedBranche.value)
  const ok = await store.applyBranchenTemplate(selectedBranche.value)
  if (ok) {
    brancheApplied.value = true
    brancheAppliedName.value = tpl?.name || selectedBranche.value
    brancheAppliedDefaults.value = tpl?.pflicht_doku_defaults || {}
    emit('applied')
  }
}

// ── Prompt-Wizards (C6 / C8 / C9 / EU-DoC / SBOM-Doc) ────────────────────────
type PromptWizardKind =
  | 'klassifikator' | 'vuln-policy' | 'update-policy' | 'eu-doc' | 'sbom-doc' | 'version-changes'

const wizardTitles: Record<PromptWizardKind, string> = {
  'klassifikator': uebersetze('cra.assistentenPanel.cRAKlassifikator'),
  'vuln-policy': uebersetze('cra.assistentenPanel.vulnerabilityDisclosurePolicy'),
  'update-policy': uebersetze('cra.assistentenPanel.securityUpdatePolicy'),
  'eu-doc': uebersetze('cra.assistentenPanel.eUKonformitatserklarungAnnexV'),
  'sbom-doc': uebersetze('cra.assistentenPanel.sBOMBegleitdokument'),
  'version-changes': uebersetze('cra.assistentenPanel.wesentlicheAnderungenJeVersion'),
}

// #1237/#1239/#1249: Diese Wizards persistieren NICHT direkt — ihr Ergebnis wird
// per „📄 Als Dokument speichern" zum managed_doc. Im Modal nur „Nur parsen".
// #1664: C8/C9 erzeugen ein versioniertes Dokument (managed_doc), konsistent zu EU-DoC/
// SBOM-Doc — vorher schrieben sie nur in Legacy-PSIRT/Support-Period (unsichtbar).
const DOC_ONLY_WIZARDS: ReadonlySet<string> = new Set(
  ['eu-doc', 'sbom-doc', 'version-changes', 'vuln-policy', 'update-policy'])

const wizardModal = ref<any>({ open: false, fehler: '', kind: '', title: '', prompt: '', response: '', parsed: null })

const isDocOnlyWizard = computed(() => DOC_ONLY_WIZARDS.has(wizardModal.value.kind))

const vollst = ref<any>(null)

const openPromptWizard = async (kind: PromptWizardKind) => {
  // #1874: Nur für die Erklärung — und fehlerfrei still, wenn der Endpunkt
  // (noch) nichts liefert: Eine Vollständigkeitsanzeige darf nie der Grund
  // sein, dass der Assistent nicht aufgeht.
  vollst.value = null
  if (kind === 'eu-doc') {
    try { vollst.value = await store.docVollstaendigkeit() } catch { vollst.value = null }
  }
  // #1901: Trägt die Akte den Lauf nicht, wird der Prompt gar nicht geholt.
  // Das Urteil fällt der Server (`bereit`) — dieselbe Funktion, mit der
  // `wizards/eu-doc/prompt` einen Lauf abweist; hier nachgebaut wäre es die
  // zweite Wahrheit (#1703/S9). Der Grund kommt mit und wird gezeigt, statt
  // dass das Modell ihn für Geld vorliest.
  if (vollst.value && vollst.value.bereit === false) {
    wizardModal.value = { open: true, kind, title: wizardTitles[kind],
                          prompt: '', response: '', parsed: null }
    return
  }
  const prompt = await store.getWizardPrompt(kind)
  wizardModal.value = { open: true, kind, title: wizardTitles[kind], prompt, response: '', parsed: null }
}

/** #1901: Der Lauf ist gesperrt — mit dem Grund, den der Server nennt. */
const nichtBereit = computed(() =>
  wizardModal.value.kind === 'eu-doc' && vollst.value?.bereit === false
    ? vollst.value.sperre : null)

const closeWizard = () => { wizardModal.value = { open: false, kind: '', title: '', prompt: '', response: '', parsed: null } }

const markdownKopiert = ref(false)
const copyMarkdown = async () => {
  markdownKopiert.value = await kopiere(wizardModal.value.parsed?.markdown || '')
  if (markdownKopiert.value) setTimeout(() => (markdownKopiert.value = false), 2000)
}

const parseOnly = async () => {
  wizardModal.value.parsed = await store.parseWizardResponse(wizardModal.value.kind, wizardModal.value.response, false)
}

// #1445–#1449: Für DOC_ONLY-Wizards ist die Kachel-id == Modal-kind. Den geparsten
// Markdown (oder ersatzweise die Roh-Antwort) an den Grid-Save-Dialog übergeben.
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
  const kind = wizardModal.value.kind
  wizardModal.value.parsed = await store.parseWizardResponse(kind, wizardModal.value.response, true)
  // Projekt-Daten neu laden (Klassifikator schreibt in projekt.produktklasse + meta)
  await store.fetchProjekte()
  if (wizardModal.value.parsed?.applied) {
    emit('applied')
    setTimeout(() => { closeWizard() }, 1200)
  }
}
</script>

<style scoped>
.assistenten-panel { display: flex; flex-direction: column; gap: 16px; }

.info-banner { background: #f3e5f5; padding: 16px 20px; border-radius: 8px; border-left: 4px solid #7b1fa2; }
.info-banner h3 { margin: 0 0 8px; color: #4a148c; }
.info-banner p { margin: 0; color: #444; line-height: 1.5; }

.wizard-modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.wizard-modal {
  background: white; padding: 24px; border-radius: 10px; max-width: 800px; width: 90%; max-height: 90vh; overflow-y: auto;
}
.wizard-modal h3 { margin: 0 0 8px; color: #4a148c; }
.wizard-modal label { display: block; margin-top: 12px; font-weight: 600; font-size: 13px; }
.wizard-modal textarea, .wizard-modal select {
  width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit;
}
.wizard-modal .mono { font-family: monospace; font-size: 12px; }
.hint { color: #666; font-size: 13px; margin-top: 8px; }

.parsed-result { background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 12px; }
.parsed-result pre { margin: 6px 0 0; white-space: pre-wrap; font-size: 12px; }

.branche-applied {
  background: #e8f5e9; border-left: 4px solid #4caf50; padding: 10px 14px;
  border-radius: 4px; margin-top: 10px; font-size: 13px;
}
.branche-applied ul { margin: 6px 0 0 18px; padding: 0; }

.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #0d47a1; }
.btn-secondary { background: #eee; color: #333; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary:hover { background: #ddd; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 14px; color: #1565c0; padding: 4px 0; }

/* #1874: Anhang-V-Vollständigkeit vor dem Prompt. Bewusst nüchtern — die
   Aussage ist „kann das Dokument vollständig werden?", keine Dekoration. */
.nicht-bereit { border: 1px solid #ef9a9a; background: #fff5f5; border-radius: 6px;
  padding: 10px 12px; margin: 8px 0; }
.nicht-bereit strong { color: #c62828; font-size: 13px; }
.nicht-bereit p { margin: 4px 0 6px; font-size: 12px; color: #455a64; }
.nicht-bereit ul { margin: 0 0 0 18px; font-size: 12px; color: #455a64; }
.nicht-bereit .nr { background: #c62828; color: #fff; border-radius: 8px;
  padding: 0 6px; font-size: 10px; margin-right: 4px; }
.nicht-bereit .hint-sub { display: block; color: #607d8b; font-size: 11px; }
.anhang-v-check {
  border: 1px solid #d4dae3;
  border-left: 4px solid #2e7d32;
  border-radius: 0 6px 6px 0;
  padding: .75rem .9rem;
  margin: 0 0 1rem;
  background: #f6f8fb;
  font-size: .92rem;
}
.anhang-v-check.luecken { border-left-color: #e65100; }
.anhang-v-check ul { list-style: none; padding: 0; margin: .6rem 0 0; }
.anhang-v-check li { padding: .15rem 0; color: #4d5a6a; }
.anhang-v-check li.fehlt { color: #b34700; font-weight: 500; }
.anhang-v-check .nr {
  display: inline-block; min-width: 3.4rem;
  font-weight: 600; color: #0b4ea2;
}
.anhang-v-check .ja { color: #2e7d32; margin-left: .4rem; }
.anhang-v-check .nein { color: #b34700; margin-left: .4rem; }
.anhang-v-check .hint-sub { margin: .3rem 0 0; color: #566075; font-size: .88rem; }
</style>
