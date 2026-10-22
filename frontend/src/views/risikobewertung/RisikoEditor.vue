<template>
  <div class="modal-overlay" @mousedown.self="onCancel">
    <div class="modal-content">
      <div class="modal-header">
        <h3>{{ risiko?.id ? `Risiko #${risiko.nr || ''} bearbeiten` : 'Neues Risiko' }}</h3>
        <button class="btn-close" @click="onCancel">✕</button>
      </div>

      <div class="modal-body">
        <div class="form-row">
          <label>Risiko-Name *</label>
          <input v-model="form.risk_name" placeholder="z.B. Unbefugter Zugriff auf Admin-Konten" />
        </div>

        <div class="form-row">
          <label>Beschreibung</label>
          <textarea v-model="form.beschreibung" rows="3"
                    placeholder="Welche Bedrohung, welcher Asset, welcher mögliche Schaden?"></textarea>
        </div>

        <div class="form-row" v-if="!fixedFramework">
          <label>Framework</label>
          <select v-model="form.framework" @change="onFrameworkChanged">
            <option v-for="fw in store.frameworks" :key="fw.id" :value="fw.id">
              {{ fw.label }}
            </option>
          </select>
          <small v-if="frameworkInfo" class="hint-text">
            <details>
              <summary>Framework-Details</summary>
              <pre>{{ frameworkInfo.description }}</pre>
            </details>
          </small>
        </div>

        <!-- Dynamische Framework-Felder, gruppiert -->
        <fieldset v-for="(fields, gruppe) in groupedFields" :key="String(gruppe)" class="framework-fields">
          <legend>{{ gruppe || 'Bewertung' }}</legend>
          <div v-for="f in fields" :key="f.key" class="form-row">
            <label>{{ f.label }}</label>
            <select v-if="f.typ === 'combo' || f.typ === 'select'" v-model="form.felder[f.key]" @change="recalc">
              <option value="">— bitte wählen —</option>
              <option v-for="opt in (f.optionen || [])" :key="opt" :value="opt">{{ opt }}</option>
            </select>
            <input v-else-if="f.typ === 'number'" v-model.number="form.felder[f.key]" type="number" @input="recalc" />
            <input v-else v-model="form.felder[f.key]" @input="recalc" />
          </div>
        </fieldset>

        <!-- Live-Score-Anzeige -->
        <div v-if="liveScore" class="score-preview" :style="{ borderLeftColor: liveScore.farbe }">
          <div class="score-row">
            <span class="score-label">Risikowert</span>
            <span class="score-value">{{ liveScore.risikowert ?? '—' }}</span>
          </div>
          <div class="score-row">
            <span class="score-label">Risiko-Level</span>
            <span class="score-badge" :style="{ background: liveScore.farbe, color: 'white' }">
              {{ liveScore.risiko_label }}
            </span>
          </div>
          <details v-if="liveScore.detail_text">
            <summary>Berechnungs-Details</summary>
            <pre>{{ liveScore.detail_text }}</pre>
          </details>
        </div>

        <div class="form-row">
          <label>Bemerkungen / Bewertungs-Text</label>
          <textarea v-model="form.bewertung_text" rows="10" class="bewertung-textarea"
                    placeholder="Notizen zur Bewertung, Kontext, Quellen, Issue-Feedback…"></textarea>
          <!-- #1765: Herkunfts-/Prüfhinweis am Bewertungs-Text, nicht im Dokument. -->
          <KiHerkunftBadge
            v-if="risiko?.id && projektName"
            modul="risikobewertung"
            :projekt="projektName"
            art="risk"
            :objekt-id="risiko.id"
          />
        </div>

        <!-- Resolved-Status (nur beim Bearbeiten) — kompakt -->
        <div v-if="risiko?.id" class="resolved-row">
          <label class="resolved-toggle">
            <input type="checkbox" v-model="form.is_resolved" />
            <span>✓ Risiko gelöst</span>
          </label>
          <input v-if="form.is_resolved"
                 v-model="form.resolved_reason"
                 class="resolved-reason"
                 placeholder="Begründung / wie mitigiert?" />
        </div>

        <!-- #1674: Formale Risikobehandlung inkl. CRA-konformer Akzeptanz -->
        <fieldset v-if="risiko?.id" class="akz-section">
          <legend>⚖️ Risikobehandlung (CRA-Nachweis)</legend>
          <div class="akz-row">
            <label class="akz-field akz-behandlung">Behandlung
              <select v-model="akzForm.behandlung">
                <option value="offen">offen</option>
                <option value="reduziert">reduziert / behoben</option>
                <option value="akzeptiert">akzeptiert (Restrisiko)</option>
                <option value="vermieden">vermieden</option>
                <option value="uebertragen">übertragen</option>
              </select>
            </label>
            <span v-if="risiko.behandlung === 'akzeptiert'" class="akz-badge"
                  :title="risiko.akzeptanz_grund">✓ akzeptiert ({{ risiko.akzeptanz_kategorie }})</span>
          </div>
          <div v-if="akzForm.behandlung === 'akzeptiert'" class="akz-grid">
            <label class="akz-field akz-span">Begründungskategorie
              <select v-model="akzForm.kategorie">
                <option value="nicht_anwendbar">nicht anwendbar (risikobasiert)</option>
                <option value="restrisiko">Restrisiko nach Maßnahmen</option>
                <option value="kompensierend">kompensierende Maßnahme</option>
              </select>
            </label>
            <label class="akz-field akz-span">Begründung
              <textarea v-model="akzForm.grund" rows="2" placeholder="Warum ist das Restrisiko vertretbar?"></textarea>
            </label>
            <label class="akz-field">Akzeptiert von
              <input v-model="akzForm.von" placeholder="Rolle/Person" />
            </label>
            <label class="akz-field">Rechtsgrundlage
              <input v-model="akzForm.rechtsgrundlage" placeholder="z. B. CRA Annex I …" />
            </label>
          </div>
          <div class="akz-actions">
            <button class="btn-secondary" :disabled="akzBusy || (akzForm.behandlung === 'akzeptiert' && !akzForm.grund.trim())"
                    @click="onBehandlung">{{ akzBusy ? '⏳ …' : 'Behandlung speichern' }}</button>
          </div>
        </fieldset>

        <!-- LLM-Aktionen (nur bei existierendem Risiko) -->
        <fieldset v-if="risiko?.id" class="llm-section">
          <legend>🤖 KI-Bewertung</legend>
          <div class="llm-buttons">
            <button class="btn-secondary" @click="onShowWizard" :disabled="!!busy">
              {{ busy === 'prompt' ? '⏳ Lade Prompt…' : '🤖 KI-Bewertung (Prompt → Antwort)' }}
            </button>
            <button class="btn-secondary" @click="onOllama" :disabled="!!busy"
                    title="Direkter API-Call an den konfigurierten KI-Provider (kein Copy/Paste)">
              🤖 Automatische Bewertung
            </button>
          </div>
          <div class="llm-buttons">
            <button class="btn-secondary" @click="onShowImportIssue" :disabled="!!busy">
              📥 Issue-Inhalt importieren
            </button>
            <button class="btn-secondary" @click="onShowReAssessment" :disabled="!!busy">
              🔄 Neubewertung mit Issue-Feedback
            </button>
          </div>
          <p class="llm-hint">
            <strong>Manuelle Bewertung</strong>: Prompt erstellen → in ChatGPT/Claude einfügen → JSON-Antwort hier einfügen.<br />
            <strong>Automatische Bewertung</strong>: direkter API-Call an den in den Einstellungen konfigurierten Provider (Ollama lokal oder Cloud).<br />
            <strong>Neubewertung</strong>: Issue-Text einfügen → Re-Assessment-Prompt für manuelle Bewertung.
          </p>
        </fieldset>

        <!-- #1685: Bestehende Issues an das Risiko verknüpfen (mehrere möglich) -->
        <fieldset v-if="risiko?.id" class="issuelink-section">
          <legend>🔗 Verknüpfte Issues</legend>
          <p class="il-hint">Bestehende GitHub-/GitLab-Issues per URL mit diesem Risiko verknüpfen. Mehrere möglich.</p>
          <ul v-if="linkedIssues.length" class="il-list">
            <li v-for="it in linkedIssues" :key="it.id" class="il-item">
              <a :href="it.url" target="_blank" rel="noopener" class="il-link">
                <span v-if="it.issue_number" class="il-num">#{{ it.issue_number }}</span>
                {{ it.title || it.url }}
              </a>
              <span v-if="it.state" :class="['il-state', it.state === 'closed' ? 'closed' : 'open']">{{ it.state }}</span>
              <button class="il-remove" title="Verknüpfung entfernen" :disabled="ilBusy"
                      @click="onUnlinkIssue(it.id)">✕</button>
            </li>
          </ul>
          <p v-else class="il-empty">Noch keine Issues verknüpft.</p>
          <div class="il-add">
            <input v-model="ilUrl" class="il-input" placeholder="https://github.com/owner/repo/issues/123"
                   @keyup.enter="onLinkIssue" />
            <button class="btn-secondary il-btn" :disabled="ilBusy || !ilUrl.trim()" @click="onLinkIssue">
              {{ ilBusy ? '⏳ …' : '🔗 Verknüpfen' }}
            </button>
          </div>
          <p v-if="ilError" class="il-err">{{ ilError }}</p>
        </fieldset>

        <!-- #1564: Herkunft — Anforderungen/Controls aus CRA, NIS2, DSGVO, AI Act -->
        <fieldset v-if="risiko?.id && reqLinks.length" class="cra-map-section">
          <legend>📌 Ausgewiesen für Anforderungen / Controls</legend>
          <p class="cra-map-hint">
            Dieses Risiko wurde an folgenden Stellen für eine (teilweise) Nichterfüllung ausgewiesen.
            Bewerte es hier über die Felder oben.
          </p>
          <ul class="req-link-list">
            <li v-for="l in reqLinks" :key="`${l.modul}-${l.object_kind}-${l.object_id}`">
              <span class="req-link-mod">{{ l.modul_label }}</span>
              {{ kindLabel(l.object_kind) }} <strong>{{ l.object_id }}</strong>
              <span class="req-link-proj">· Projekt „{{ l.projekt }}"</span>
            </li>
          </ul>
        </fieldset>

        <!-- #17 Stufe 2: CRA-Anforderungen verknüpfen (nur wenn Projekt mit CRA verknüpft) -->
        <fieldset v-if="risiko?.id && linkedCraProjekt" class="cra-map-section">
          <legend>🔗 CRA-Anforderungen (Nachweis)</legend>
          <p class="cra-map-hint">
            Verknüpfe dieses Risiko mit den CRA-Anforderungen aus Projekt
            <strong>{{ linkedCraProjekt }}</strong>, auf die es einzahlt. Die Zuordnung
            ist <em>rein informativ</em> (Abdeckungs-Nachweis, AI1-01) und blendet keine
            Anforderungen aus.
          </p>
          <div v-if="craReqLoading" class="cra-map-loading">Lade Anforderungen …</div>
          <div v-else-if="craRequirements.length === 0" class="cra-map-hint">
            Keine CRA-Anforderungen gefunden.
          </div>
          <div v-else class="cra-req-list">
            <label v-for="r in craRequirements" :key="r.id" class="cra-req-item">
              <input type="checkbox" :value="r.id" v-model="selectedCraReqs" />
              <span class="cra-req-id">{{ r.id }}</span>
              <span class="cra-req-title">{{ r.titel || r.title }}</span>
            </label>
          </div>
          <div class="cra-map-foot">
            <button class="btn-secondary" @click="saveCraMapping"
                    :disabled="craMapSaving || craReqLoading">
              {{ craMapSaving ? 'Speichert…' : 'Zuordnung speichern' }}
            </button>
            <span v-if="craMapMsg" :class="['cra-map-msg', craMapMsgKind]">{{ craMapMsg }}</span>
          </div>
        </fieldset>

        <div v-if="error" class="alert alert-error">{{ error }}</div>
      </div>

      <div class="modal-footer">
        <button v-if="risiko?.id" class="btn-danger-outline" @click="onDelete">Löschen</button>
        <span class="spacer"></span>
        <button class="btn-secondary" @click="onCancel">Abbrechen</button>
        <button class="btn-primary" @click="onSave" :disabled="saving">
          {{ saving ? 'Speichert…' : 'Speichern' }}
        </button>
      </div>
    </div>

    <!-- #866/#868/#869/#870: gemeinsames KI-Wizard-Modal (Copy-Paste-Bewertung) -->
    <WizardPromptModal
      v-if="wizard.open"
      :title="`Risiko-Bewertung: ${form.risk_name || 'Risiko'}`"
      :prompt="wizard.prompt"
      schema-hint='Antwort als JSON: { "felder": { … }, "bewertung": "…" }'
      :busy="busy === 'json'"
      @apply="onApplyWizard"
      @close="wizard.open = false"
    >
      <template #before>
        <DataPreviewWarning
          :fields="previewFields"
          :sensitive="['Beschreibung']"
          :provider="aiProvider"
          @confirm="wizard.confirmed = true"
        />
        <p v-if="wizard.error" class="alert alert-error" style="margin-top:10px">{{ wizard.error }}</p>
      </template>
      <template #after>
        <OutputDestinationHint
          destination="Befüllt die Framework-Felder und den Bewertungstext des Risikos."
          impact="Aktualisiert Risikowert und Risiko-Level nach dem Übernehmen."
        />
      </template>
    </WizardPromptModal>

    <!-- Issue-Import-Modal -->
    <div v-if="issueModal.open" class="modal-overlay nested" @mousedown.self="issueModal.open = false">
      <div class="modal-content prompt-modal">
        <div class="modal-header">
          <h3>📥 Issue-Inhalt importieren</h3>
          <button class="btn-close" @click="issueModal.open = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">
            <strong>Automatisch:</strong> Issue-URL eingeben → System holt Title + Body + Kommentare via GitHub/GitLab-API.<br />
            <strong>Manuell:</strong> Text unten direkt einfügen.
          </p>
          <div class="issue-url-row">
            <input
              v-model="issueModal.url"
              type="url"
              placeholder="https://github.com/owner/repo/issues/123"
              class="issue-url-input"
            />
            <button class="btn-secondary" @click="onFetchIssue" :disabled="!issueModal.url || issueModal.fetching">
              {{ issueModal.fetching ? '⏳ Lade…' : '📡 Auto-Holen' }}
            </button>
          </div>
          <div v-if="issueModal.fetchError" class="alert alert-error">{{ issueModal.fetchError }}</div>
          <textarea v-model="issueModal.text" rows="10"
                    placeholder="Issue-Body, Kommentare, Code-Review-Feedback…"></textarea>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="issueModal.open = false">Abbrechen</button>
          <button class="btn-primary" @click="onApplyIssue" :disabled="!issueModal.text">
            In Bewertung einfügen
          </button>
        </div>
      </div>
    </div>

    <!-- Re-Assessment-Modal -->
    <div v-if="reAssessmentModal.open" class="modal-overlay nested" @mousedown.self="reAssessmentModal.open = false">
      <div class="modal-content prompt-modal" style="width: min(820px, 96vw)">
        <div class="modal-header">
          <h3>🔄 Neubewertung mit Issue-Feedback</h3>
          <button class="btn-close" @click="reAssessmentModal.open = false">✕</button>
        </div>
        <div class="modal-body">
          <!-- Schritt 1: Modus wählen -->
          <div v-if="reAssessmentModal.step === 'mode'">
            <p class="hint">Wie soll die Neubewertung erfolgen?</p>
            <div class="re-mode-cards">
              <button class="re-mode-card" @click="reAssessmentModal.step = 'context-local'">
                <div class="re-mode-icon">⚡</div>
                <div class="re-mode-title">Automatisch (KI-API)</div>
                <div class="re-mode-desc">
                  Direkter Aufruf an Ollama / Cloud-Provider. Bewertung wird
                  direkt aktualisiert. Empfohlen.
                </div>
              </button>
              <button class="re-mode-card" @click="reAssessmentModal.step = 'context-prompt'">
                <div class="re-mode-icon">📝</div>
                <div class="re-mode-title">Manuell (Prompt/JSON)</div>
                <div class="re-mode-desc">
                  Prompt generieren → in ChatGPT/Claude einfügen → JSON-Antwort
                  zurückspielen über „JSON-Antwort einfügen".
                </div>
              </button>
            </div>
          </div>

          <!-- Schritt 2: Issue-Kontext -->
          <div v-else>
            <p class="hint">
              <strong>{{ reAssessmentModal.step === 'context-local' ? 'Automatisch' : 'Manuell' }}</strong> · Issue-Body / Audit-Feedback unten einfügen.
              <a href="#" @click.prevent="reAssessmentModal.step = 'mode'">← Modus ändern</a>
            </p>
            <div class="issue-url-row">
              <input v-model="reAssessmentModal.url"
                     placeholder="Optional: Issue-URL für Auto-Fetch (https://github.com/.../issues/123)"
                     class="issue-url-input" />
              <button class="btn-secondary" @click="onReAssessmentFetchUrl"
                      :disabled="!reAssessmentModal.url || reAssessmentModal.fetching">
                {{ reAssessmentModal.fetching ? '⏳ Lade…' : '📡 Auto-Holen' }}
              </button>
            </div>
            <textarea v-model="reAssessmentModal.context" rows="8"
                      placeholder="Issue-Body, neue Findings, Audit-Feedback…"></textarea>

            <div v-if="reAssessmentModal.prompt" class="re-prompt">
              <h4>Re-Assessment-Prompt</h4>
              <pre class="prompt-text">{{ reAssessmentModal.prompt }}</pre>
              <!-- #1068: KI-Antwort einfügen + übernehmen (fehlte bisher) -->
              <h4 style="margin-top: 12px;">KI-Antwort einfügen</h4>
              <textarea v-model="reAssessmentModal.response" rows="6"
                        placeholder='JSON-Antwort der KI hier einfügen, z.B. {"felder": {…}, "bewertung": "…"}'></textarea>
            </div>

            <!-- #1421: Auto-Neubewertung — geteiltes Live-Fenster + Ergebnis-Zusammenfassung -->
            <div v-if="reAssessmentModal.running" style="margin-top: 12px;">
              <KiStreamView :url="reAssessStreamUrl" :body="{ issue_context: reAssessmentModal.context }"
                            :pipeline="true" @done="onReAssessDone" @error="onReAssessError">
                <template #result="{ payload }">
                  <div class="auto-result-score">
                    <span class="ars-label">Risiko</span>
                    <span class="ars-value">{{ payload.risiko_label || '—' }}<span class="ars-max"> ({{ payload.risikowert ?? '–' }})</span></span>
                  </div>
                  <div v-if="payload.risiko_veraenderung" class="auto-result-block">
                    <h4>Risiko-Veränderung</h4>
                    <p class="auto-result-text">{{ reAssessChangeLabel(payload.risiko_veraenderung) }}<span v-if="payload.begruendung_veraenderung"> — {{ payload.begruendung_veraenderung }}</span></p>
                  </div>
                  <div v-if="payload.bewertung_text" class="auto-result-block">
                    <h4>Begründung der KI</h4>
                    <p class="auto-result-text">{{ payload.bewertung_text }}</p>
                  </div>
                  <div v-if="payload.empfehlungen && payload.empfehlungen.length" class="auto-result-block">
                    <h4>Empfohlene Maßnahmen</h4>
                    <ul class="auto-result-list">
                      <li v-for="(e, i) in payload.empfehlungen" :key="i">{{ e }}</li>
                    </ul>
                  </div>
                  <div v-if="payload.cra_referenz" class="auto-result-block">
                    <h4>Normbezug</h4>
                    <p class="auto-result-text">{{ payload.cra_referenz }}</p>
                  </div>
                  <p class="llm-disclaimer">🤖 KI-generiert<span v-if="payload.provider"> ({{ payload.provider === 'cloud' ? 'Cloud' : 'Lokal' }})</span> — fachlich zu prüfen. Die Neubewertung wurde übernommen.</p>
                </template>
              </KiStreamView>
            </div>
            <div v-if="reAssessmentModal.error" class="alert alert-error" style="margin-top: 10px;">
              ⚠ {{ reAssessmentModal.error }}
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="reAssessmentModal.open = false">Schließen</button>

          <template v-if="reAssessmentModal.step === 'context-local'">
            <button v-if="!reAssessmentModal.running" class="btn-primary" @click="onRunReAssessmentLocal"
                    :disabled="!reAssessmentModal.context">
              ⚡ Neubewertung starten
            </button>
            <button v-else-if="reAssessmentModal.done" class="btn-primary" @click="reAssessmentModal.open = false">
              Verstanden, übernehmen
            </button>
            <span v-else class="muted">⏳ Läuft …</span>
          </template>
          <template v-else-if="reAssessmentModal.step === 'context-prompt'">
            <button v-if="!reAssessmentModal.prompt" class="btn-primary" @click="onGenerateReAssessment"
                    :disabled="!reAssessmentModal.context || busy === 're-assessment'">
              {{ busy === 're-assessment' ? 'Lädt…' : 'Prompt generieren' }}
            </button>
            <button v-if="reAssessmentModal.prompt" class="btn-secondary" @click="copyReAssessment">
              📋 Kopieren
            </button>
            <button v-if="reAssessmentModal.prompt" class="btn-primary" @click="onApplyReAssessment"
                    :disabled="!reAssessmentModal.response || busy === 're-assessment'">
              {{ busy === 're-assessment' ? '⏳ Übernehme…' : '✅ Antwort übernehmen' }}
            </button>
          </template>
        </div>
      </div>
    </div>

    <!-- #1573: einheitlicher Auto-Bewertungs-Dialog (alle Module) — Bestätigung → Live-Stream → Ergebnis -->
    <AutoBewertungDialog v-if="ollamaOpen" :title="form.risk_name" :stream-url="autoStreamUrl"
      :preview-fields="previewFields" :sensitive="['Beschreibung']" wert-label="Risiko"
      destination="Die KI bewertet das Risiko direkt; Felder + Bewertung werden gespeichert."
      @close="ollamaOpen = false" @done="onOllamaDone" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRisikobewertungStore, type Risiko, type FrameworkField } from '../../stores/risikobewertung'
import WizardPromptModal from '../../components/shared/WizardPromptModal.vue'
import DataPreviewWarning from '../../components/shared/DataPreviewWarning.vue'
import OutputDestinationHint from '../../components/shared/OutputDestinationHint.vue'
import KiStreamView from '../../components/shared/KiStreamView.vue'
import AutoBewertungDialog from '../../components/shared/AutoBewertungDialog.vue'
import KiHerkunftBadge from '../../components/shared/KiHerkunftBadge.vue'
import { useKiHerkunftStore } from '../../stores/kiHerkunft'

const props = defineProps<{
  risiko: Risiko | null
  projektName: string
  defaultFramework?: string
  /** Wenn true, kann Framework nicht geändert werden (kommt aus Projekt). */
  fixedFramework?: boolean
}>()

const emit = defineEmits<{
  saved: [risiko: Risiko]
  deleted: [riskId: number]
  cancel: []
}>()

const store = useRisikobewertungStore()

// #1765: Nach einer KI-Bewertung die Herkunfts-Karte nachziehen — sonst
// erschiene der Hinweis „KI-Entwurf, ungeprüft" erst nach einem Neuladen.
const kiHerkunft = useKiHerkunftStore()
const kiHerkunftNachziehen = () => {
  kiHerkunft.reload('risikobewertung', props.projektName, 'risk')
}
const error = ref('')
const saving = ref(false)
const liveScore = ref<any | null>(null)

const form = ref<any>({
  risk_name: '',
  beschreibung: '',
  framework: props.defaultFramework || 'STRIDE',
  felder: {},
  bewertung_text: '',
  is_resolved: false,
  resolved_reason: '',
})

const frameworkInfo = computed(() =>
  store.frameworks.find(f => f.id === form.value.framework) || null
)

const currentFields = computed<FrameworkField[]>(() =>
  store.frameworkFields[form.value.framework] || []
)

const groupedFields = computed(() => {
  const groups: Record<string, FrameworkField[]> = {}
  for (const f of currentFields.value) {
    const g = f.gruppe || 'Bewertung'
    if (!groups[g]) groups[g] = []
    groups[g].push(f)
  }
  return groups
})

watch(() => props.risiko, (r) => {
  if (r) {
    form.value = {
      risk_name: r.risk_name || r.name || '',
      beschreibung: r.beschreibung || '',
      framework: r.framework || props.defaultFramework || 'STRIDE',
      felder: { ...(r.felder || {}) },
      bewertung_text: r.bewertung_text || '',
      is_resolved: !!r.is_resolved,
      resolved_reason: r.resolved_reason || '',
    }
    error.value = ''
    if (form.value.framework) {
      store.fetchFrameworkFields(form.value.framework).then(() => recalc())
    }
  } else {
    form.value = {
      risk_name: '',
      beschreibung: '',
      framework: props.defaultFramework || 'STRIDE',
      felder: {},
      bewertung_text: '',
      is_resolved: false,
      resolved_reason: '',
    }
    if (form.value.framework) {
      store.fetchFrameworkFields(form.value.framework)
    }
  }
}, { immediate: true })

const onFrameworkChanged = async () => {
  await store.fetchFrameworkFields(form.value.framework)
  // Felder zurücksetzen, weil Framework gewechselt
  form.value.felder = {}
  liveScore.value = null
}

let recalcTimer: number | undefined
const recalc = () => {
  if (recalcTimer) window.clearTimeout(recalcTimer)
  recalcTimer = window.setTimeout(async () => {
    if (!form.value.framework) return
    const result = await store.calculateScore(form.value.framework, form.value.felder)
    if (result) liveScore.value = result
  }, 200)
}

const onSave = async () => {
  error.value = ''
  if (!form.value.risk_name?.trim()) {
    error.value = 'Risiko-Name ist Pflicht.'
    return
  }
  saving.value = true

  let result: Risiko | null = null
  if (props.risiko?.id) {
    result = await store.updateRisiko(props.projektName, props.risiko.id, form.value)
    // Resolve-Status separat aktualisieren wenn nötig
    if (result && (form.value.is_resolved !== !!props.risiko.is_resolved)) {
      await store.resolveRisiko(props.projektName, props.risiko.id, form.value.is_resolved, form.value.resolved_reason)
    }
  } else {
    result = await store.createRisiko(props.projektName, form.value)
  }
  saving.value = false

  if (result) {
    emit('saved', result)
  } else {
    error.value = store.error || 'Fehler beim Speichern.'
  }
}

const onDelete = async () => {
  if (!props.risiko?.id) return
  if (!confirm(`Risiko "${form.value.risk_name}" wirklich löschen?`)) return
  const ok = await store.deleteRisiko(props.risiko.id, props.projektName)
  if (ok) emit('deleted', props.risiko.id)
}

const onCancel = () => emit('cancel')

// #1674: formale Risikobehandlung / Akzeptanz
const akzBusy = ref(false)
const akzForm = ref({
  behandlung: (props.risiko as any)?.behandlung || 'offen',
  kategorie: (props.risiko as any)?.akzeptanz_kategorie || 'restrisiko',
  grund: (props.risiko as any)?.akzeptanz_grund || '',
  von: (props.risiko as any)?.akzeptanz_von || '',
  rechtsgrundlage: (props.risiko as any)?.rechtsgrundlage || '',
})
const onBehandlung = async () => {
  if (!props.risiko?.id) return
  akzBusy.value = true
  const ok = await store.setBehandlung(props.projektName, props.risiko.id, { ...akzForm.value })
  akzBusy.value = false
  if (ok) emit('saved', props.risiko)
}

// ---- LLM-Aktionen ----
const busy = ref<'' | 'prompt' | 'json' | 'ollama' | 'issue' | 're-assessment'>('')

// #866: gemeinsames KI-Wizard-Modal (ersetzt Prompt-/JSON-Einzelmodals)
const wizard = ref<{ open: boolean; prompt: string; error: string; confirmed: boolean }>({
  open: false, prompt: '', error: '', confirmed: false,
})
const ollamaOpen = ref(false)  // #1573: einheitlicher AutoBewertungDialog
const aiProvider = ref<'on_prem' | 'cloud'>('on_prem')
const previewFields = computed(() => [
  { label: 'Projekt', value: props.projektName },
  { label: 'Risiko', value: form.value.risk_name },
  { label: 'Framework', value: form.value.framework },
  { label: 'Beschreibung', value: form.value.beschreibung },
])
const issueModal = ref({ open: false, text: '', url: '', fetching: false, fetchError: '' })
const autoStreamUrl = computed(() =>
  `/api/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/${props.risiko?.id ?? ''}/ollama/stream`)
const reAssessmentModal = ref({
  open: false,
  step: 'mode' as 'mode' | 'context-local' | 'context-prompt',
  context: '',
  prompt: '',
  response: '',  // #1068: KI-Antwort zum manuellen Re-Assessment-Prompt
  url: '',
  fetching: false,
  streamingStatus: '',
  chunks: '',
  bytes: 0,
  error: '',
  done: false,
  running: false,  // #1421 — Auto-Neubewertung läuft (KiStreamView aktiv)
})

// #1421 — Re-Assessment-Auto-Modus nutzt dieselbe geteilte KiStreamView wie die
// normale Auto-Bewertung (Live-Fenster + Ergebnis-Zusammenfassung, auch Cloud).
const reAssessStreamUrl = computed(() =>
  `/api/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/${props.risiko?.id ?? ''}/re-assessment/stream`)

// #1068: KI-Antwort des manuellen Re-Assessment-Prompts übernehmen (wie der normale Wizard).
const onApplyReAssessment = async () => {
  const raw = reAssessmentModal.value.response
  if (!props.risiko?.id || !props.projektName || !raw.trim()) return
  reAssessmentModal.value.error = ''
  busy.value = 're-assessment'
  const result = await store.parseRiskResponse(props.projektName, props.risiko.id, raw, true)
  busy.value = ''
  if (result) {
    if (result.felder) form.value.felder = result.felder
    if (result.bewertung_text) form.value.bewertung_text = result.bewertung_text
    liveScore.value = {
      risikowert: result.risikowert,
      risiko_label: result.risiko_label,
      detail_text: result.detail_text,
      farbe: SCORE_COLORS_MAP[result.risiko_label] || '#888',
    }
    reAssessmentModal.value.open = false
    emit('saved', { ...props.risiko, ...result } as any)
    kiHerkunftNachziehen()
  } else {
    reAssessmentModal.value.error = store.error || 'Antwort konnte nicht geparsed werden'
  }
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
  } catch {}
}

const onShowWizard = async () => {
  if (!props.risiko?.id || !props.projektName) return
  busy.value = 'prompt'
  wizard.value = { open: false, prompt: '', error: '', confirmed: false }
  const prompt = await store.getRiskPrompt(props.projektName, props.risiko.id)
  busy.value = ''
  if (prompt) {
    wizard.value = { open: true, prompt, error: '', confirmed: false }
  } else {
    error.value = store.error || 'Prompt konnte nicht generiert werden'
  }
}

const onApplyWizard = async (rawText: string) => {
  if (!props.risiko?.id || !props.projektName || !rawText) return
  wizard.value.error = ''
  busy.value = 'json'
  const result = await store.parseRiskResponse(props.projektName, props.risiko.id, rawText, true)
  busy.value = ''
  if (result) {
    if (result.felder) form.value.felder = result.felder
    if (result.bewertung_text) form.value.bewertung_text = result.bewertung_text
    liveScore.value = {
      risikowert: result.risikowert,
      risiko_label: result.risiko_label,
      detail_text: result.detail_text,
      farbe: SCORE_COLORS_MAP[result.risiko_label] || '#888',
    }
    wizard.value.open = false
    emit('saved', { ...props.risiko, ...result } as any)
    kiHerkunftNachziehen()
  } else {
    wizard.value.error = store.error || 'Antwort konnte nicht geparsed werden'
  }
}

// #1573: einheitlicher AutoBewertungDialog (Bestätigung → Live-Stream → Ergebnis)
const onOllama = () => {
  if (!props.risiko?.id || !props.projektName) return
  ollamaOpen.value = true
}

// Ergebnis ins Formular + Live-Score übernehmen und Parent aktualisieren.
const onOllamaDone = (data: any) => {
  if (data.felder) form.value.felder = data.felder
  if (data.bewertung_text) form.value.bewertung_text = data.bewertung_text
  liveScore.value = {
    risikowert: data.risikowert,
    risiko_label: data.risiko_label,
    detail_text: data.detail_text,
    farbe: SCORE_COLORS_MAP[data.risiko_label] || '#888',
  }
  if (props.risiko) emit('saved', { ...props.risiko, ...data } as any)
  kiHerkunftNachziehen()
}

const onShowImportIssue = async () => {
  issueModal.value = { open: true, text: '', url: '', fetching: false, fetchError: '' }
  // Bereits verknüpfte Issues aus linked_issues vorbefüllen + Inhalt holen
  if (props.risiko?.id && props.projektName) {
    try {
      const { default: api } = await import('../../api/client')
      const r = await api.get(
        `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/${props.risiko.id}/linked-issues`,
      )
      const first = (r.data?.items || [])[0]
      if (first?.url) {
        issueModal.value.url = first.url
        await onFetchIssue()
      }
    } catch { /* leer bleiben ist ok */ }
  }
}

const onFetchIssue = async () => {
  const url = issueModal.value.url.trim()
  if (!url) return
  issueModal.value.fetching = true
  issueModal.value.fetchError = ''
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post('/risikobewertung/issue-content', { url })
    issueModal.value.text = r.data.combined || r.data.body || ''
  } catch (e: any) {
    issueModal.value.fetchError = e?.response?.data?.error || 'Issue konnte nicht geladen werden'
  } finally {
    issueModal.value.fetching = false
  }
}

const onApplyIssue = async () => {
  if (!props.risiko?.id || !props.projektName || !issueModal.value.text) return
  busy.value = 'issue'
  const result = await store.importIssueText(props.projektName, props.risiko.id, issueModal.value.text)
  busy.value = ''
  if (result?.ok) {
    form.value.bewertung_text = result.bewertung_text
    issueModal.value.open = false
    emit('saved', { ...props.risiko, bewertung_text: result.bewertung_text } as any)
  }
}

const onShowReAssessment = async () => {
  reAssessmentModal.value = {
    open: true, step: 'mode',
    context: '', prompt: '', response: '', url: '', fetching: false,
    streamingStatus: '', chunks: '', bytes: 0, error: '', done: false, running: false,
  }
  // Verknüpfte Issue-URL vorbefüllen (für Auto-Holen-Button)
  if (props.risiko?.id && props.projektName) {
    try {
      const { default: api } = await import('../../api/client')
      const r = await api.get(
        `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/${props.risiko.id}/linked-issues`,
      )
      const first = (r.data?.items || [])[0]
      if (first?.url) reAssessmentModal.value.url = first.url
    } catch { /* still ist ok */ }
  }
}

const onReAssessmentFetchUrl = async () => {
  const url = reAssessmentModal.value.url.trim()
  if (!url) return
  reAssessmentModal.value.fetching = true
  reAssessmentModal.value.error = ''
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post('/risikobewertung/issue-content', { url })
    reAssessmentModal.value.context = r.data.combined || r.data.body || ''
  } catch (e: any) {
    reAssessmentModal.value.error = e?.response?.data?.error || 'Issue konnte nicht geladen werden'
  } finally {
    reAssessmentModal.value.fetching = false
  }
}

const onGenerateReAssessment = async () => {
  if (!props.risiko?.id || !props.projektName || !reAssessmentModal.value.context) return
  busy.value = 're-assessment'
  const prompt = await store.reAssessmentPrompt(props.projektName, props.risiko.id, reAssessmentModal.value.context)
  busy.value = ''
  if (prompt) {
    reAssessmentModal.value.prompt = prompt
  } else {
    error.value = store.error || 'Re-Assessment-Prompt fehlgeschlagen'
  }
}

const onRunReAssessmentLocal = () => {
  if (!props.risiko?.id || !props.projektName || !reAssessmentModal.value.context) return
  reAssessmentModal.value.error = ''
  reAssessmentModal.value.done = false
  reAssessmentModal.value.running = true  // KiStreamView startet (autostart)
  busy.value = 're-assessment'
}

// #1421 — KiStreamView meldet das finale 'done': Ergebnis live anwenden + speichern.
const onReAssessDone = (d: any) => {
  reAssessmentModal.value.done = true
  busy.value = ''
  if (d.felder) form.value.felder = d.felder
  if (d.bewertung_text) form.value.bewertung_text = d.bewertung_text
  liveScore.value = {
    risikowert: d.risikowert,
    risiko_label: d.risiko_label,
    detail_text: d.detail_text,
    farbe: SCORE_COLORS_MAP[d.risiko_label] || '#888',
  }
  emit('saved', { ...props.risiko, ...d } as any)
  kiHerkunftNachziehen()
}

const onReAssessError = (m: string) => {
  reAssessmentModal.value.done = true
  reAssessmentModal.value.running = false
  reAssessmentModal.value.error = m
  busy.value = ''
}

const reAssessChangeLabel = (v: string): string => ({
  reduziert: '↓ Risiko reduziert',
  unveraendert: '→ unverändert',
  erhoeht: '↑ Risiko erhöht',
}[v] || v)

const copyReAssessment = () => copyToClipboard(reAssessmentModal.value.prompt)

const SCORE_COLORS_MAP: Record<string, string> = {
  'Kritisch': '#c62828',
  'Hoch': '#e65100',
  'Mittel': '#f57f17',
  'Niedrig': '#558b2f',
  'Sehr niedrig': '#2e7d32',
  'Akzeptabel': '#2e7d32',
  'Existenzbedrohend': '#b71c1c',
}

// ---- #17 Stufe 2: CRA-Anforderungs-Mapping ----
const linkedCraProjekt = computed<string | null>(
  () => store.selectedProjektObj?.linked_cra_projekt || null,
)
const craRequirements = ref<Array<{ id: string; titel?: string; title?: string }>>([])
const selectedCraReqs = ref<string[]>([])
const craReqLoading = ref(false)
const craMapSaving = ref(false)
const craMapMsg = ref('')
const craMapMsgKind = ref<'ok' | 'err'>('ok')

async function loadCraMapping() {
  craRequirements.value = []
  selectedCraReqs.value = []
  craMapMsg.value = ''
  if (!props.risiko?.id || !linkedCraProjekt.value) return
  craReqLoading.value = true
  try {
    const { default: api } = await import('../../api/client')
    const [reqs, mapping] = await Promise.all([
      api.get(`/cra/projekte/${encodeURIComponent(linkedCraProjekt.value)}/anforderungen`),
      api.get(`/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/${props.risiko.id}/cra-requirements`),
    ])
    craRequirements.value = Array.isArray(reqs.data) ? reqs.data : []
    selectedCraReqs.value = mapping.data?.anforderungen || []
  } catch {
    craRequirements.value = []
  } finally {
    craReqLoading.value = false
  }
}

async function saveCraMapping() {
  if (!props.risiko?.id) return
  craMapSaving.value = true
  craMapMsg.value = ''
  try {
    const { default: api } = await import('../../api/client')
    await api.post(
      `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/${props.risiko.id}/cra-requirements`,
      { anforderungen: selectedCraReqs.value },
    )
    craMapMsg.value = 'Zuordnung gespeichert.'
    craMapMsgKind.value = 'ok'
  } catch (e: any) {
    craMapMsg.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
    craMapMsgKind.value = 'err'
  } finally {
    craMapSaving.value = false
  }
}

watch(() => props.risiko?.id, loadCraMapping)

// #1564: Herkunft des Risikos über alle Module
const reqLinks = ref<Array<{ modul: string; modul_label: string; object_kind: string; object_id: string; projekt: string }>>([])
const kindLabel = (k: string) => ({ requirement: 'Anforderung', owasp: 'OWASP-Control', owasp_llm: 'OWASP-LLM' } as Record<string, string>)[k] || k
async function loadReqLinks() {
  reqLinks.value = []
  if (!props.risiko?.id) return
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.get(`/risikobewertung/projekte/${encodeURIComponent(props.projektName)}/risiken/${props.risiko.id}/req-links`)
    reqLinks.value = r.data?.items || []
  } catch { /* optional */ }
}
watch(() => props.risiko?.id, loadReqLinks, { immediate: true })

// #1685: bestehende Issues an das Risiko verknüpfen (mehrere möglich)
const linkedIssues = ref<Array<{ id: string; url: string; title: string; state: string; issue_number: number | null; provider: string }>>([])
const ilUrl = ref('')
const ilBusy = ref(false)
const ilError = ref('')
async function loadLinkedIssues() {
  linkedIssues.value = []
  if (!props.risiko?.id) return
  linkedIssues.value = await store.listRiskIssues(props.projektName, props.risiko.id)
}
async function onLinkIssue() {
  if (!props.risiko?.id || !ilUrl.value.trim()) return
  ilBusy.value = true; ilError.value = ''
  const res = await store.linkRiskIssue(props.projektName, props.risiko.id, ilUrl.value.trim())
  ilBusy.value = false
  if (res) { ilUrl.value = ''; await loadLinkedIssues() }
  else { ilError.value = store.error || 'Verknüpfen fehlgeschlagen' }
}
async function onUnlinkIssue(linkId: string) {
  if (!props.risiko?.id) return
  ilBusy.value = true; ilError.value = ''
  const ok = await store.unlinkRiskIssue(props.projektName, props.risiko.id, linkId)
  ilBusy.value = false
  if (ok) await loadLinkedIssues()
  else ilError.value = store.error || 'Entfernen fehlgeschlagen'
}
watch(() => props.risiko?.id, loadLinkedIssues, { immediate: true })

onMounted(async () => {
  await store.fetchFrameworks()
  if (form.value.framework) {
    await store.fetchFrameworkFields(form.value.framework)
    if (props.risiko?.id) recalc()
  }
  await loadCraMapping()
  // #867/#877: aktiven KI-Provider für die Daten-Transparenz laden
  try {
    const { default: api } = await import('../../api/client')
    const res = await api.get('/ai/provider-status')
    aiProvider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Default on_prem */ }
})
</script>

<style scoped>
.issue-url-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}
.issue-url-input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  font-family: inherit;
}
.issue-url-input:focus {
  border-color: var(--primary, #1565c0);
  outline: none;
  box-shadow: 0 0 0 3px rgba(21,101,192,0.12);
}

.ollama-modal { width: min(720px, 96vw); }
/* #1407 — Ergebnis-Zusammenfassung (Parität mit CRA) */
.auto-result-score { display: flex; align-items: baseline; gap: 10px; margin: 10px 0 14px; }
.auto-result-score .ars-label { font-size: 12px; color: #607d8b; text-transform: uppercase; letter-spacing: .04em; }
.auto-result-score .ars-value { font-size: 22px; font-weight: 700; color: #1565c0; }
.auto-result-score .ars-max { font-size: 14px; font-weight: 600; color: #90a4ae; }
.auto-result-block { margin-bottom: 12px; }
.auto-result-block h4 { margin: 0 0 4px; font-size: 13px; color: #37474f; }
.auto-result-text { margin: 0; white-space: pre-wrap; line-height: 1.5; color: #263238; }
.auto-result-list { margin: 0; padding-left: 20px; line-height: 1.5; color: #263238; }
.auto-result-list li { margin-bottom: 3px; }
.llm-disclaimer { margin: 10px 0 0; font-size: 12px; color: #78909c; font-style: italic; }
.re-mode-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}
.re-mode-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
  padding: 16px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  background: white;
  cursor: pointer;
  font: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.re-mode-card:hover {
  border-color: var(--primary, #1565c0);
  box-shadow: 0 2px 8px rgba(21,101,192,0.12);
}
.re-mode-icon { font-size: 28px; margin-bottom: 6px; }
.re-mode-title { font-size: 15px; font-weight: 600; color: var(--primary, #1565c0); margin-bottom: 6px; }
.re-mode-desc { font-size: 12px; color: var(--text-muted, #666); }
@media (max-width: 600px) { .re-mode-cards { grid-template-columns: 1fr; } }

.ollama-status {
  display: flex; align-items: center; gap: 10px;
  font-size: 15px; margin-bottom: 8px;
}
.ollama-meter {
  font-size: 12px; color: var(--text-muted, #757575); margin-bottom: 12px;
}
.phase-pipeline {
  display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap;
  background: #f5f7fa; border-radius: 8px; padding: 8px;
}
.phase-step {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 6px;
  font-size: 12px; color: #757575;
  background: white; border: 1px solid #e0e0e0;
}
.phase-step.active { color: #1565c0; border-color: #1565c0; font-weight: 600; background: #e3f2fd; }
.phase-step.done { color: #2e7d32; border-color: #c8e6c9; background: #f1f8e9; }
.phase-icon { font-size: 14px; }
.ollama-stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 8px; margin: 12px 0;
}
.ollama-stats .stat {
  display: flex; flex-direction: column; align-items: center;
  padding: 8px; background: #fafafa; border: 1px solid #eee;
  border-radius: 6px;
}
.ollama-stats .stat-label { font-size: 11px; color: #757575; text-transform: uppercase; }
.ollama-stats .stat-value { font-size: 16px; font-weight: 600; color: #1565c0; margin-top: 2px; }
.ollama-chunks {
  max-height: 280px; overflow: auto;
  background: #fafafa; border: 1px solid #e0e0e0;
  border-radius: 6px; padding: 10px;
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
  white-space: pre-wrap; word-break: break-word;
}
.spinner {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid #1565c0; border-top-color: transparent;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 720px;
  width: 90%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h3 {
  margin: 0;
  color: var(--color-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 22px;
  color: #999;
  cursor: pointer;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.modal-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--color-border);
}

.spacer {
  flex: 1;
}

.form-row {
  margin-bottom: 12px;
}

.form-row label {
  display: block;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.form-row input,
.form-row select,
.form-row textarea {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
}

.form-row textarea {
  resize: vertical;
  min-height: 60px;
  line-height: 1.5;
}

.form-row .bewertung-textarea {
  min-height: 200px;
  font-family: 'Segoe UI', system-ui, sans-serif;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  cursor: pointer;
}

.framework-fields {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 12px;
}

.framework-fields legend {
  padding: 0 6px;
  font-weight: 600;
  font-size: 12px;
  color: var(--color-primary);
  text-transform: uppercase;
}

.score-preview {
  background: #f5f5f5;
  padding: 12px 16px;
  border-radius: 6px;
  border-left: 4px solid #888;
  margin: 16px 0;
}

.score-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.score-label {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.score-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary);
}

.score-badge {
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 13px;
}

.score-preview details {
  margin-top: 8px;
  font-size: 12px;
}

.score-preview pre {
  background: white;
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  overflow-x: auto;
  white-space: pre-wrap;
}

.hint-text {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #888;
}

.hint-text pre {
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  white-space: pre-wrap;
  max-height: 200px;
  overflow-y: auto;
}

.resolved-row {
  display: flex; align-items: center; gap: 12px;
  margin: 8px 0 4px;
  padding: 6px 10px;
  background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px;
}
.resolved-toggle {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 500; white-space: nowrap;
  cursor: pointer;
}
.resolved-toggle input { width: auto; margin: 0; }
.resolved-reason {
  flex: 1; padding: 4px 8px; font-size: 13px;
  border: 1px solid var(--color-border, #d0d4dc); border-radius: 4px;
}

.alert {
  padding: 10px 14px;
  border-radius: 4px;
  margin: 12px 0;
  font-size: 13px;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
}

.btn-primary,
.btn-secondary,
.btn-danger-outline {
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  border: none;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:disabled {
  opacity: 0.6;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}

.btn-danger-outline {
  background: white;
  color: #d32f2f;
  border: 1px solid #d32f2f;
}

.btn-danger-outline:hover {
  background: #ffebee;
}

/* #1683 — Risikobehandlung (CRA-Nachweis): kompaktes, ausgerichtetes Layout */
.akz-section {
  background: #fbf7f0;
  border-color: #e4c9a0;
}
.akz-section legend {
  color: #a86b1a;
}
.akz-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}
.akz-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-weight: 600;
  font-size: 13px;
}
.akz-behandlung { min-width: 220px; }
.akz-field select,
.akz-field input,
.akz-field textarea {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
  font-weight: 400;
}
.akz-field textarea {
  resize: vertical;
  min-height: 52px;
  line-height: 1.5;
}
.akz-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  margin-bottom: 2px;
  background: #e8f5e9;
  color: #2e7d32;
  border: 1px solid #c8e6c9;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.akz-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
  margin-top: 12px;
}
.akz-grid .akz-span { grid-column: 1 / -1; }
.akz-actions {
  margin-top: 12px;
}
.akz-actions .btn-secondary {
  background: white;
  border: 1px solid #e4c9a0;
  color: #a86b1a;
  font-size: 12px;
  padding: 6px 14px;
}
.akz-actions .btn-secondary:hover:not(:disabled) {
  background: #a86b1a;
  color: white;
}
.akz-actions .btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
@media (max-width: 600px) { .akz-grid { grid-template-columns: 1fr; } }

/* #1685 — Verknüpfte Issues */
.issuelink-section { background: #f4f7f4; border-color: #c3dcc3; }
.issuelink-section legend { color: #2e7d32; }
.il-hint { font-size: 12px; color: #607d8b; margin: 0 0 8px; }
.il-list { list-style: none; margin: 0 0 10px; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.il-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; background: white; border: 1px solid #d7e7d7; border-radius: 6px; }
.il-link { flex: 1; color: #1565c0; text-decoration: none; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.il-link:hover { text-decoration: underline; }
.il-num { color: #78909c; font-weight: 600; margin-right: 4px; }
.il-state { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; text-transform: lowercase; }
.il-state.open { background: #e8f5e9; color: #2e7d32; }
.il-state.closed { background: #eceff1; color: #607d8b; }
.il-remove { background: none; border: none; color: #c62828; cursor: pointer; font-size: 14px; padding: 2px 6px; border-radius: 4px; }
.il-remove:hover:not(:disabled) { background: #ffebee; }
.il-remove:disabled { opacity: 0.4; cursor: not-allowed; }
.il-empty { font-size: 12px; color: #90a4ae; font-style: italic; margin: 0 0 10px; }
.il-add { display: flex; gap: 8px; align-items: center; }
.il-input { flex: 1; padding: 7px 10px; border: 1px solid var(--color-border, #e0e0e0); border-radius: 4px; font-size: 13px; font-family: inherit; }
.il-btn { background: white; border: 1px solid #c3dcc3; color: #2e7d32; font-size: 12px; padding: 6px 14px; white-space: nowrap; }
.il-btn:hover:not(:disabled) { background: #2e7d32; color: white; }
.il-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.il-err { color: #c62828; font-size: 12px; margin: 8px 0 0; }

/* LLM-Section */
.llm-section {
  background: #f3f6fb;
  border-color: #b3d4f5;
}

.llm-section legend {
  color: #1565c0;
}

.llm-buttons {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.llm-buttons .btn-secondary {
  background: white;
  border: 1px solid #b3d4f5;
  color: #1565c0;
  font-size: 12px;
  padding: 6px 12px;
}

.llm-buttons .btn-secondary:hover:not(:disabled) {
  background: #1565c0;
  color: white;
}

.llm-buttons .btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.llm-hint {
  font-size: 11px;
  color: #666;
  margin: 8px 0 0 0;
  line-height: 1.6;
}

/* Nested-Modal (über dem Risiko-Editor) */
.modal-overlay.nested {
  z-index: 1200;
}

.prompt-modal {
  max-width: 800px;
}

.prompt-modal .modal-body {
  padding: 12px 20px;
}

.prompt-modal .hint {
  color: #666;
  font-size: 13px;
  margin: 0 0 12px;
}

.prompt-modal .prompt-text {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  max-height: 50vh;
  overflow-y: auto;
  font-family: monospace;
  border: 1px solid #ddd;
}

.prompt-modal textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  resize: vertical;
}

.preview {
  background: #e8f5e9;
  padding: 10px 14px;
  border-radius: 4px;
  margin-top: 12px;
  font-size: 13px;
  border: 1px solid #81c784;
}

.preview h4 {
  margin: 0 0 6px;
  color: #2e7d32;
  font-size: 13px;
}

.preview pre {
  background: white;
  padding: 6px;
  border-radius: 3px;
  font-size: 11px;
  max-height: 200px;
  overflow-y: auto;
}

.re-prompt {
  margin-top: 12px;
}

.re-prompt h4 {
  margin: 0 0 6px;
  font-size: 13px;
}

/* #17 Stufe 2: CRA-Anforderungs-Mapping */
.cra-map-section {
  border: 1px solid #90caf9;
  background: #f3f9ff;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 12px;
}
.cra-map-section legend {
  padding: 0 6px;
  font-weight: 600;
  font-size: 12px;
  color: #1565c0;
  text-transform: uppercase;
}
.cra-map-hint { font-size: 12px; color: #555; margin: 0 0 8px; line-height: 1.5; }
.cra-map-loading { font-size: 12px; color: #888; }
.cra-req-list {
  max-height: 220px; overflow-y: auto;
  border: 1px solid #d0d7de; border-radius: 6px;
  background: white; padding: 4px;
}
.cra-req-item {
  display: flex; align-items: baseline; gap: 8px;
  padding: 4px 6px; font-size: 12px; cursor: pointer; border-radius: 4px;
}
.cra-req-item:hover { background: #e3f2fd; }
.cra-req-item input { width: auto; margin: 0; }
.cra-req-id { font-weight: 600; color: #1565c0; white-space: nowrap; }
.cra-req-title { color: #333; }
.cra-map-foot { display: flex; align-items: center; gap: 12px; margin-top: 10px; }
.cra-map-msg { font-size: 12px; }
.cra-map-msg.ok { color: #2e7d32; }
.cra-map-msg.err { color: #c62828; }
.req-link-list { margin: 4px 0 0; padding-left: 18px; font-size: 13px; }
.req-link-mod { display: inline-block; background: #e3f2fd; color: #1565c0; border-radius: 10px; padding: 0 8px; font-size: 11px; font-weight: 600; margin-right: 4px; }
.req-link-proj { color: #777; font-size: 12px; }
</style>
