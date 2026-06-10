<template>
  <ModuleShell
    class="dsgvo-view"
    title="DSGVO – Datenschutz-Grundverordnung"
    subtitle="Verordnung (EU) 2016/679 · 36 Anforderungen in 6 Kapiteln · 0-5-Bewertung mit Gewichtung"
    module-name="dsgvo"
    :tabs="store.selectedProjektObj ? tabs : []"
    v-model="activeTab"
  >
    <HelpDialog
      :open="helpOpen"
      title="DSGVO – Erläuterung der Kapitel"
      subtitle="Verordnung (EU) 2016/679 — Datenschutz-Grundverordnung"
      header-bg="#1565c0"
      :kapitel="store.constants?.kapitel"
      :bewertung-skala="store.constants?.bewertung_skala"
      @close="helpOpen = false"
    />

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <div v-if="!store.selectedProjektObj" class="empty-state">
      <h3>{{ store.projekte.length === 0 ? 'Noch keine DSGVO-Bewertungen' : 'Firma wählen' }}</h3>
      <p v-if="store.projekte.length === 0">
        DSGVO ist <strong>firmenbezogen</strong> — pro Firma eine Bewertung.
        Lege einen Firmen mit aktiviertem DSGVO-Modul in der Firmenverwaltung an;
        die DSGVO-Bewertung wird dann automatisch erzeugt.
      </p>
      <p v-else>Wähle links einen Firmen aus der Sidebar.</p>
      <router-link to="/firmen" class="btn-primary">→ Zur Firmenverwaltung</router-link>
    </div>

    <template v-else>
      <!-- Tab: Dashboard — einheitlich (#1250), konsolidiert das frühere DSMS-Cockpit -->
      <div v-if="activeTab === 'dashboard'" class="tab-content">
        <ModuleDashboard
          :gesamt="{ percent: dashboardGesamtPct, ampel: dashboardGesamtAmpel }"
          :gesamt-stats="dashboardStats"
          :bereiche="dashboardBereiche"
          :offene-punkte="dashboardLuecken"
          :fristen-tab="true"
          :fristen="dashboardFristen"
          :dok-fertig="dokFertig"
          :dok-gesamt="dokGesamt"
          :risiko="risiko"
          :risiko-loading="risikoLoading"
          @open-bereich="onOpenBereich"
          @open-luecken="activeTab = 'anforderungen'"
          @open-punkt="(id) => { activeTab = 'anforderungen'; openAnforderung(id) }"
          @open-fristen="(tab) => { if (tab) activeTab = tab }"
          @open-dokumente="activeTab = 'dokumente'"
          @open-risiken="activeTab = 'cockpit'"
        />
      </div>

      <div v-if="activeTab === 'pflichtdoku'" class="tab-content">
        <DSGVOPflichtDokuPanel @open-assistenten="activeTab = 'assistenten'" @open-tab="activeTab = $event" />
      </div>

      <!-- Assistenten-Tab (#1083) -->
      <div v-if="activeTab === 'assistenten'" class="tab-content">
        <div class="assistenten-intro">
          <h3>🤖 DSGVO-Assistenten</h3>
          <p>Geführte KI- und Anlege-Assistenten für die DSGVO-Dokumentation. Wähle einen Assistenten —
            du wirst zum passenden Bereich geführt.</p>
        </div>
        <AssistentenKachelGrid
          :wizards="dsgvoWizards"
          grouped
          :modul="'dsgvo'"
          :projekt="store.selectedProjekt"
          @open="onAssistentOpen"
        />
      </div>

      <!-- Tab: Dokumente (Sprint #24) -->
      <div v-if="activeTab === 'dokumente'" class="tab-content">
        <DokumenteRegister
          :modul="'dsgvo'"
          :projekt="store.selectedProjekt"
          @open-assistent="activeTab = 'assistenten'"
        />
      </div>

      <!-- Risiko-Cockpit-Tab (#1083) -->
      <div v-if="activeTab === 'cockpit'" class="tab-content">
        <div v-if="cockpitLoading" class="cockpit-hint">Lädt Firmen-Zuordnung…</div>
        <RiskCockpit v-else-if="cockpitFirmenId != null" :firmen-id="cockpitFirmenId" />
        <div v-else class="cockpit-hint warn">
          Projekt keiner Firma zugeordnet — im Admin zuordnen (Firmen-Zuordnung).
        </div>
      </div>

      <div v-if="activeTab === 'anforderungen'" class="tab-content">
        <!-- Anforderungs-Toolbar -->
        <div class="anf-toolbar">
          <input v-model="searchQuery" placeholder="Anforderungen durchsuchen…" class="search" />
          <select v-model="filterKapitel" class="filter">
            <option value="">Alle Kapitel</option>
            <option v-for="k in chapters" :key="k" :value="k">{{ k }}</option>
          </select>
          <select v-model="filterStatus" class="filter">
            <option value="all">Alle</option>
            <option value="pending">Ausstehend</option>
            <option value="partial">Teilweise</option>
            <option value="complete">Vollständig</option>
          </select>
          <span class="info">{{ visible.length }} / {{ store.anforderungen.length }}</span>

          <div class="export-group">
            <span>Export:</span>
            <DownloadButton :endpoint="stripApi(exportUrl('xlsx'))" class="export-btn">📊 Excel</DownloadButton>
            <DownloadButton :endpoint="stripApi(exportUrl('docx'))" class="export-btn">📝 Word</DownloadButton>
            <DownloadButton :endpoint="stripApi(exportUrl('pdf'))" class="export-btn">📄 PDF</DownloadButton>
            <ImportButton
              v-if="store.selectedProjekt"
              variant="secondary"
              :endpoint="`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
              label="⬆️ Import"
              @imported="onImported"
            />
          </div>
        </div>

        <!-- Anforderungs-Liste -->
        <div class="anf-list">
          <table v-if="visible.length > 0">
            <thead>
              <tr>
                <th>ID</th>
                <th>Kapitel</th>
                <th>Titel</th>
                <th>Bewertung</th>
                <th>Status</th>
                <th>Gewichtung</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in visible" :key="r.id" @click="editAnforderung(r)">
                <td><code>{{ r.id }}</code></td>
                <td>
                  <span class="kapitel-tag" :style="{ background: kapitelColor(r.kapitel), color: '#fff' }">
                    {{ r.kapitel }}
                  </span>
                </td>
                <td class="title-cell">{{ r.titel }}</td>
                <td>
                  <span class="score-pill" :style="{ background: scoreColor(r.bewertung) }">
                    {{ r.bewertung }}
                  </span>
                </td>
                <td>
                  <span :class="['status-pill', r.status]">{{ statusLabel(r.status) }}</span>
                </td>
                <td>{{ r.gewichtung }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">Keine Anforderungen zum Filter.</div>
        </div>
      </div>

      <!-- TOM-Tab -->
      <div v-if="activeTab === 'tom'" class="tab-content">
        <div class="generator-card">
          <h3>🔒 TOM-Entwurf (Art. 32 DSGVO)</h3>
          <p>Generiert einen vollständigen Entwurf der Technischen und Organisatorischen Maßnahmen (TOM) als Word-Dokument auf Basis der Bewertungen aus dem Anforderungs-Tab.</p>
          <div class="tom-list">
            <div v-for="t in tomAbschnitte" :key="t.id" class="tom-item">
              <strong>{{ t.id }}</strong> – {{ t.titel }}
              <span class="muted">({{ t.untertitel }})</span>
            </div>
          </div>
          <div v-if="tomDraft" class="ai-draft-info">
            <strong>🤖 KI-Draft vorhanden</strong> · {{ Object.keys(tomDraft.payload?.abschnitte || {}).length }} Abschnitte ·
            <span class="muted">Stand: {{ formatDate(tomDraft.updated_at) }}</span>
            <details class="mt-1">
              <summary>Vorschau</summary>
              <div v-for="(a, id) in (tomDraft.payload?.abschnitte || {})" :key="id" class="ai-section">
                <strong>{{ id }}</strong>
                <ul>
                  <li v-for="m in (a.vorhandene_massnahmen || [])" :key="m">✓ {{ m }}</li>
                  <li v-for="g in (a.luecken || [])" :key="g" class="gap">⚠ Lücke: {{ g }}</li>
                </ul>
              </div>
            </details>
          </div>
          <div class="action-row">
            <button class="btn-secondary" @click="onTomGeneratePrompt" :disabled="aiBusy">
              {{ aiBusy ? 'Lädt…' : '🤖 KI-Prompt erstellen (aus Firmen-Dokumenten)' }}
            </button>
            <DownloadButton
              :endpoint="`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt || '')}/tom/export`"
              label="📝 TOM-Entwurf herunterladen (DOCX)"
              variant="primary"
            />
          </div>
        </div>
      </div>

      <!-- Datenschutzerklärung-Tab -->
      <div v-if="activeTab === 'privacy'" class="tab-content">
        <div class="generator-card">
          <h3>📜 Datenschutzerklärung</h3>
          <p>Erstelle einen Entwurf einer Website/App-Datenschutzerklärung. Fülle die Felder aus, ungesetzte Felder werden im Dokument als <code>[PLATZHALTER]</code> markiert.</p>

          <div class="privacy-form" v-if="privacyFelder">
            <details v-for="grp in privacyGruppen" :key="grp" class="form-group" :open="grp === 'Verantwortlicher'">
              <summary>{{ grp }}</summary>
              <div class="form-grid">
                <div v-for="f in feldsByGruppe(grp)" :key="f.key" class="form-cell">
                  <label>{{ f.label }}<span v-if="f.required" class="req">*</span></label>
                  <textarea v-if="f.key === 'rechtsgrundlage_beschreibung' || f.key === 'drittland_beschreibung' || f.key === 'speicherdauer_sonstiges' || f.key === 'zwecke_sonstiges'"
                            v-model="privacyIntake[f.key]" rows="2"></textarea>
                  <select v-else-if="f.type === 'bool'" v-model="privacyIntake[f.key]">
                    <option :value="undefined">— wählen —</option>
                    <option :value="true">Ja</option>
                    <option :value="false">Nein</option>
                  </select>
                  <div v-else-if="f.type === 'checklist'" class="checklist">
                    <label v-for="opt in f.optionen" :key="opt[0]" class="check-row">
                      <input type="checkbox" :value="opt[0]"
                             :checked="(privacyIntake[f.key] || []).includes(opt[0])"
                             @change="onZweckToggle(f.key, opt[0], $event)" />
                      {{ opt[1] }}
                    </label>
                  </div>
                  <input v-else v-model="privacyIntake[f.key]" :placeholder="f.tip || ''" />
                  <small v-if="f.tip && f.type !== 'checklist'" class="hint">{{ f.tip }}</small>
                </div>
              </div>
            </details>
          </div>

          <div class="action-row">
            <button class="btn-secondary" @click="onPrivacyGeneratePrompt" :disabled="aiBusy">
              {{ aiBusy ? 'Lädt…' : '🤖 KI-Vorbefüllung (aus Firmen-Dokumenten)' }}
            </button>
            <button class="btn-secondary" @click="savePrivacyIntake">💾 Speichern</button>
            <DownloadButton
              :endpoint="`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt || '')}/privacy/export`"
              label="📜 Datenschutzerklärung herunterladen (DOCX)"
              variant="primary"
            />
            <span v-if="privacyMsg" class="hint" :class="{ ok: privacyMsgOk }">{{ privacyMsg }}</span>
          </div>
        </div>
      </div>

      <!-- Schulungs-Tab -->
      <div v-if="activeTab === 'training'" class="tab-content">
        <div class="generator-card">
          <h3>🎓 Jahresschulung</h3>
          <p>Generiert ein Schulungs-Skript inkl. Quiz für ausgewählte Zielgruppen.</p>

          <div class="training-zielgruppen">
            <h4>Zielgruppen</h4>
            <label v-for="(meta, key) in (trainingOutline?.zielgruppen || {})" :key="key" class="check-row">
              <input type="checkbox" :value="key"
                     :checked="trainingZielgruppen.includes(String(key))"
                     @change="onZielgruppeToggle(String(key), $event)" />
              <strong :style="{ color: meta.farbe }">{{ meta.label }}</strong>
              <span class="muted">— {{ meta.beschreibung }}</span>
            </label>
          </div>

          <div class="action-row">
            <button class="btn-primary" @click="downloadTraining" :disabled="trainingBusy">
              {{ trainingBusy ? 'Lädt…' : '🎓 Schulung herunterladen (DOCX)' }}
            </button>
            <span v-if="trainingMsg" class="hint" :class="{ err: trainingErr }">{{ trainingMsg }}</span>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'tom-katalog'" class="tab-content">
        <TomKatalogPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>
      <div v-if="activeTab === 'betroffenenrechte'" class="tab-content">
        <BetroffenenrechtePanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>
      <div v-if="activeTab === 'loeschkonzept'" class="tab-content">
        <LoeschkonzeptPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>
      <div v-if="activeTab === 'transfer'" class="tab-content">
        <TransferPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>
      <div v-if="activeTab === 'einwilligung'" class="tab-content">
        <EinwilligungPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>
      <div v-if="activeTab === 'dsgvo-dsb'" class="tab-content">
        <DsbPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>

      <!-- Datenpannen (#1193) -->
      <div v-if="activeTab === 'datenpannen'" class="tab-content">
        <DatenpannenPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>

      <!-- LIA-Register (#1205) -->
      <div v-if="activeTab === 'lia'" class="tab-content">
        <LiaPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>

      <!-- Subprozessoren (#1214) -->
      <div v-if="activeTab === 'subprozessoren'" class="tab-content">
        <SubprozessorenPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>

      <!-- Zweckänderung (#1215) -->
      <div v-if="activeTab === 'zweckaenderung'" class="tab-content">
        <ZweckaenderungPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>

      <!-- Joint Controller (#1216) -->
      <div v-if="activeTab === 'joint-controller'" class="tab-content">
        <JointControllerPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>

      <!-- EU-Vertreter (#1219) -->
      <div v-if="activeTab === 'eu-vertreter'" class="tab-content">
        <EuVertreterPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>

      <!-- Jährlicher Kontrollplan (Milestone #24) -->
      <div v-if="activeTab === 'kontrollen'" class="tab-content">
        <KontrollenPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>
      <div v-if="activeTab === 'jahresbericht'" class="tab-content">
        <JahresberichtPanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <p v-else class="hint">Bitte zuerst ein DSGVO-Projekt auswählen.</p>
      </div>
      <div v-if="activeTab === 'berichte'" class="tab-content">
        <h3 style="margin: 8px 0 8px; color: #1565c0; font-size: 15px;">DSMS-Gesamtbericht</h3>
        <ExportPanel
          module="dsgvo"
          :projekt-name="store.selectedProjekt || ''"
          :formats="['pdf', 'docx', 'xlsx']"
        />
        <h3 style="margin: 24px 0 8px; color: #1565c0; font-size: 15px;">Einzelberichte je Bereich</h3>
        <BerichtsCenterPanel :projekt-name="store.selectedProjekt" />
      </div>

      <!-- Bericht-Tab (B2 #1093) -->
    </template>

    <!-- Projekt-Leiste (ModuleShell #project-bar) -->
    <template v-if="store.selectedProjektObj" #project-bar>
      <h3 class="project-name">{{ store.selectedProjektObj?.name }}
        <span v-if="store.selectedProjektObj?.unternehmen" class="project-company">— {{ store.selectedProjektObj.unternehmen }}</span>
      </h3>
      <FirmaSelector
        :model-value="(store.selectedProjektObj as any)?.unternehmen || ''"
        :saving="reassignSaving"
        :success-text="reassignMsg.ok"
        :error-text="reassignMsg.err"
        @save="onReassignFirma"
      />
      <button class="btn-secondary" @click="syncIssues" :disabled="syncingIssues" title="Status aller verlinkten Issues dieses Projekts von GitHub/GitLab aktualisieren">{{ syncingIssues ? '⏳ Sync…' : '🔄 Issues synchronisieren' }}</button>
      <button class="btn-secondary" @click="bulkCreateIssues" :disabled="bulkCreating" title="Für alle DSGVO-Gaps (Bewertung &lt; 5) automatisch Issues im konfigurierten Repository anlegen">{{ bulkCreating ? '⏳ Anlegen…' : '🐙 Issues anlegen' }}</button>
      <button class="btn-danger-mini" @click="confirmDeleteProjekt" title="Projekt löschen">🗑️ Löschen</button>
    </template>

    <!-- #862: Pro-Projekt-Repository-Konfiguration (für Issue-Anlage/Sync) -->
    <template v-if="store.selectedProjektObj && store.selectedProjekt" #repo-config>
      <RepoConfigPanel :api-base="'/dsgvo'" :projekt-name="store.selectedProjekt" />
    </template>

    <template #modals>
      <!-- Editor (Details + KI-Bewertung) -->
      <RequirementEditor
        v-if="editingReq"
        :requirement="editingReq"
        @save="onSaveBewertung"
        @cancel="editingReq = null"
      >
        <template #actions>
          <RequirementActions
            :requirement="editingReq"
            :projekt-name="store.selectedProjekt || ''"
            api-base="/dsgvo"
            @saved="onActionSaved"
            @error="(msg: string) => store.error = msg"
          />
        </template>
      </RequirementEditor>

      <!-- KI-Prompt-Modal -->
      <div v-if="aiPromptModal.open" class="modal-overlay" @mousedown.self="aiPromptModal.open = false">
        <div class="modal-content modal-wide">
          <div class="modal-header">
            <h3>🤖 ChatGPT-Prompt — {{ aiPromptModal.kind === 'tom' ? 'TOM-Entwurf' : 'Datenschutzerklärung' }}</h3>
            <button class="btn-close" @click="aiPromptModal.open = false">✕</button>
          </div>
          <div class="modal-body">
            <p class="hint">
              <strong>Firma:</strong> {{ aiPromptModal.firma || '—' }} ·
              <strong>Evidence-Auszüge:</strong> {{ aiPromptModal.evidence_count }}
            </p>
            <div v-if="aiPromptModal.evidence_count === 0" class="alert alert-warn">
              ⚠️ Keine Firmen-Dokumente vorhanden. Lade zuerst unter <em>Firmen → Evidence</em>
              für "{{ aiPromptModal.firma }}" PDFs/DOCXs hoch, damit ChatGPT konkretere Inhalte
              generieren kann.
            </div>
            <button class="btn-mini" @click="copyToClipboard(aiPromptModal.prompt)">📋 Prompt kopieren</button>
            <textarea readonly :value="aiPromptModal.prompt" rows="14" class="prompt-textarea"></textarea>

            <hr style="margin: 16px 0;" />
            <p class="hint">Kopiere den Prompt in ChatGPT, dann füge die JSON-Antwort hier ein:</p>
            <textarea v-model="aiResponseRaw" rows="10" class="prompt-textarea"
                      placeholder="ChatGPT-Antwort hier einfügen…"></textarea>
            <span v-if="aiImportMsg" class="hint" :class="{ ok: aiImportOk, err: !aiImportOk }">{{ aiImportMsg }}</span>
          </div>
          <div class="modal-footer">
            <button class="btn-secondary" @click="aiPromptModal.open = false">Schließen</button>
            <button class="btn-primary" @click="onAiImport" :disabled="!aiResponseRaw || aiBusy">
              {{ aiBusy ? 'Importiere…' : '✓ Antwort übernehmen' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </ModuleShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import { useFirmenStore } from '../../stores/firmen'
import { useRoute } from 'vue-router'
import FirmaSelector from '../../components/shared/FirmaSelector.vue'
import RepoConfigPanel from '../../components/RepoConfigPanel.vue'
import ModuleDashboard from '../../components/shared/ModuleDashboard.vue'
import { useModuleDashboard } from '../../composables/useModuleDashboard'
import { useDsgvoCockpitStore } from '../../stores/dsgvoCockpit'
import RequirementEditor from '../../components/shared/RequirementEditor.vue'
import RequirementActions from '../../components/shared/RequirementActions.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import DownloadButton from '../../components/shared/DownloadButton.vue'
import HelpDialog from '../../components/shared/HelpDialog.vue'
import ModuleShell from '../../components/shared/ModuleShell.vue'
import ExportPanel from '../../components/shared/ExportPanel.vue'
import apiClient from '../../api/client'
import DSGVOPflichtDokuPanel from './DSGVOPflichtDokuPanel.vue'
import TomKatalogPanel from './TomKatalogPanel.vue'
import BetroffenenrechtePanel from './BetroffenenrechtePanel.vue'
import LoeschkonzeptPanel from './LoeschkonzeptPanel.vue'
import TransferPanel from './TransferPanel.vue'
import EinwilligungPanel from './EinwilligungPanel.vue'
import DsbPanel from './DsbPanel.vue'
import DatenpannenPanel from './DatenpannenPanel.vue'
import LiaPanel from './LiaPanel.vue'
import SubprozessorenPanel from './SubprozessorenPanel.vue'
import ZweckaenderungPanel from './ZweckaenderungPanel.vue'
import JointControllerPanel from './JointControllerPanel.vue'
import EuVertreterPanel from './EuVertreterPanel.vue'
import KontrollenPanel from './KontrollenPanel.vue'
import JahresberichtPanel from './JahresberichtPanel.vue'
import BerichtsCenterPanel from './BerichtsCenterPanel.vue'
import AssistentenKachelGrid from '../../components/assistenten/AssistentenKachelGrid.vue'
import DokumenteRegister from '../shared/DokumenteRegister.vue'
import { buildWizardList, type WizardDescriptor } from '../../components/assistenten/registry'
import RiskCockpit from '../shared/RiskCockpit.vue'

const store = useDsgvoStore()
const firmenStore = useFirmenStore()
const route = useRoute()
const stripApi = (u: string): string => u.replace(/^\/api/, '')

// #1250: einheitliches Dashboard + konsolidiertes DSMS-Cockpit
const dsmsStore = useDsgvoCockpitStore()
const { dokFertig, dokGesamt, risiko, risikoLoading, loadAll: loadDashboardExtras } =
  useModuleDashboard('dsgvo')

const helpOpen = ref(false)
const creating = ref(false)

const syncingIssues = ref(false)
async function syncIssues() {
  if (!store.selectedProjekt) return
  syncingIssues.value = true
  try {
    const r = await apiClient.post(`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/issues/sync`, {}, { timeout: 120000 })
    const d = r.data || {}
    alert(`Issues synchronisiert: ${d.synced || 0} aktualisiert, ${d.errors || 0} Fehler (gesamt ${d.total || 0}).`)
  } catch (e: any) {
    alert(e?.response?.data?.error || 'Issue-Sync fehlgeschlagen.')
  } finally { syncingIssues.value = false }
}

const tabs = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'pflichtdoku', label: '📋 Dokumentation' },
  { id: 'cockpit', label: '📊 Risiko-Cockpit' },
  { id: 'anforderungen', label: '✅ Anforderungen' },
  { id: 'assistenten', label: '🤖 Assistenten' },
  { id: 'dokumente', label: '📄 Dokumente' },
  { id: 'tom-katalog', label: '🔐 TOM-Katalog' },
  { id: 'betroffenenrechte', label: '📨 Betroffenenrechte' },
  { id: 'loeschkonzept', label: '🗑️ Löschkonzept' },
  { id: 'transfer', label: '🌍 Drittlandtransfer' },
  { id: 'einwilligung', label: '✍️ Einwilligungen' },
  { id: 'dsgvo-dsb', label: '🛡️ DSB' },
  { id: 'datenpannen', label: '🚨 Datenpannen' },
  { id: 'lia', label: '⚖️ LIA-Register' },
  { id: 'subprozessoren', label: '🔗 Subprozessoren' },
  { id: 'zweckaenderung', label: '🔄 Zweckänderung' },
  { id: 'joint-controller', label: '🤝 Joint Controller' },
  { id: 'eu-vertreter', label: '🇪🇺 EU-Vertreter' },
  { id: 'tom', label: '🔒 TOM-Generator' },
  { id: 'privacy', label: '📜 Datenschutzerklärung' },
  { id: 'training', label: '🎓 Schulung' },
  { id: 'kontrollen', label: '🗓️ Kontrollen' },
  { id: 'jahresbericht', label: '📅 Jahresbericht' },
  { id: 'berichte', label: '📄 Berichte' },
]
const activeTab = ref<string>('dashboard')

// Assistenten-Tab (#1083): DSGVO-Wizards als WizardDescriptor-Liste.
const dsgvoWizards: WizardDescriptor[] = buildWizardList([
  {
    id: 'dsgvo-tom-ai',
    title: 'TOM-Entwurf (Art. 32)',
    description: 'KI-gestützter Entwurf der Technischen und Organisatorischen Maßnahmen aus Firmen-Dokumenten.',
    kategorie: 'dokumentation',
    icon: '🔒',
  },
  {
    id: 'dsgvo-privacy-ai',
    title: 'Datenschutzerklärung',
    description: 'Website/App-Datenschutzerklärung entwerfen — mit KI-Vorbefüllung aus Firmen-Dokumenten.',
    kategorie: 'dokumentation',
    icon: '📜',
  },
  {
    id: 'dsgvo-vvt',
    title: 'VVT-Eintrag (Art. 30)',
    description: 'Geführter Anlege-Assistent für Verarbeitungstätigkeiten im Verzeichnis (VVT).',
    kategorie: 'dokumentation',
    icon: '🪄',
  },
  {
    id: 'dsgvo-rechtsgrundlage',
    title: 'D6 — Rechtsgrundlage',
    description: 'Bestimmt automatisch die passende Rechtsgrundlage (Art. 6) je VVT-Eintrag.',
    kategorie: 'compliance',
    icon: '⚖️',
  },
  {
    id: 'dsgvo-branche',
    title: 'D7 — Branchen-Template',
    description: 'Legt TOM-Defaults für die Branche an (E-Commerce / B2B-SaaS / Healthcare / HR).',
    kategorie: 'compliance',
    icon: '⚡',
  },
  {
    id: 'dsgvo-datenpanne',
    title: 'D8 — Datenpannen-Meldung',
    description: 'Generiert Meldungstexte für die 72h-Meldung an Aufsicht + Information der Betroffenen.',
    kategorie: 'compliance',
    icon: '🚨',
  },
  {
    id: 'dsgvo-betroffenenrechte',
    title: 'D9 — Betroffenenrechte',
    description: 'Antwort-Templates für Auskunfts-/Löschungs-/Portabilitäts-Anträge (Art. 15/17/20).',
    kategorie: 'compliance',
    icon: '📝',
  },
  {
    id: 'dsgvo-training',
    title: 'Jahresschulung',
    description: 'Schulungs-Skript inkl. Quiz für ausgewählte Zielgruppen (DOCX).',
    kategorie: 'dokumentation',
    icon: '🎓',
  },
])

const onAssistentOpen = (id: string) => {
  switch (id) {
    case 'dsgvo-tom-ai':
      activeTab.value = 'tom'
      break
    case 'dsgvo-privacy-ai':
      activeTab.value = 'privacy'
      break
    case 'dsgvo-training':
      activeTab.value = 'training'
      break
    // VVT + D6/D7/D8/D9 leben im Pflicht-Doku-Panel.
    case 'dsgvo-vvt':
    case 'dsgvo-rechtsgrundlage':
    case 'dsgvo-branche':
    case 'dsgvo-datenpanne':
    case 'dsgvo-betroffenenrechte':
      activeTab.value = 'pflichtdoku'
      break
    default:
      break
  }
}

// Risiko-Cockpit-Tab (#1083): Firmen-Zuordnung des Projekts auflösen.
const cockpitFirmenId = ref<number | null>(null)
const cockpitLoading = ref(false)
const loadCockpitFirma = async () => {
  if (!store.selectedProjekt) {
    cockpitFirmenId.value = null
    return
  }
  cockpitLoading.value = true
  try {
    const res = await apiClient.get(
      `/risk-cockpit/by-projekt/dsgvo/${encodeURIComponent(store.selectedProjekt)}`,
    )
    cockpitFirmenId.value = res.data?.unassigned ? null : (res.data?.firmen_id ?? null)
  } catch {
    cockpitFirmenId.value = null
  } finally {
    cockpitLoading.value = false
  }
}

// TOM
const tomAbschnitte = ref<any[]>([])
const loadTom = async () => {
  if (tomAbschnitte.value.length) return
  try {
    const res = await apiClient.get('/dsgvo/tom/abschnitte')
    tomAbschnitte.value = res.data
  } catch { /* ignore */ }
}

// Privacy intake
const privacyFelder = ref<any[] | null>(null)
const privacyGruppen = ref<string[]>([])
const privacyIntake = ref<Record<string, any>>({})
const privacyMsg = ref('')
const privacyMsgOk = ref(false)
const feldsByGruppe = (grp: string) =>
  (privacyFelder.value || []).filter(f => f.group === grp)
const loadPrivacySchema = async () => {
  if (privacyFelder.value) return
  try {
    const res = await apiClient.get('/dsgvo/privacy/intake-schema')
    privacyFelder.value = res.data.felder
    privacyGruppen.value = res.data.gruppen
  } catch { /* ignore */ }
}
const loadPrivacyIntake = async () => {
  if (!store.selectedProjekt) return
  try {
    const res = await apiClient.get(`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/privacy/intake`)
    privacyIntake.value = res.data.intake || {}
  } catch { /* ignore */ }
}
const savePrivacyIntake = async () => {
  if (!store.selectedProjekt) return
  try {
    await apiClient.put(`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/privacy/intake`,
      privacyIntake.value)
    privacyMsgOk.value = true
    privacyMsg.value = '✓ Gespeichert.'
    setTimeout(() => privacyMsg.value = '', 3000)
  } catch (e: any) {
    privacyMsgOk.value = false
    privacyMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
  }
}
const onZweckToggle = (key: string, value: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  const arr = (privacyIntake.value[key] || []) as string[]
  if (checked && !arr.includes(value)) arr.push(value)
  else if (!checked && arr.includes(value)) arr.splice(arr.indexOf(value), 1)
  privacyIntake.value[key] = [...arr]
}

// KI-Generator (TOM + Privacy)
const aiBusy = ref(false)
const aiResponseRaw = ref('')
const aiImportMsg = ref('')
const aiImportOk = ref(false)
const aiPromptModal = ref<{
  open: boolean
  kind: 'tom' | 'privacy'
  prompt: string
  firma: string
  evidence_count: number
}>({ open: false, kind: 'tom', prompt: '', firma: '', evidence_count: 0 })

const tomDraft = ref<any | null>(null)

const formatDate = (s?: string | null): string => {
  if (!s) return '—'
  try { return new Date(s).toLocaleString('de-DE') } catch { return s }
}

const loadTomDraft = async () => {
  if (!store.selectedProjekt) return
  try {
    const res = await apiClient.get(
      `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/tom/ai-draft`,
    )
    tomDraft.value = res.data?.draft || null
  } catch { tomDraft.value = null }
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    aiImportMsg.value = '✓ In Zwischenablage kopiert.'
    aiImportOk.value = true
    setTimeout(() => aiImportMsg.value = '', 3000)
  } catch {
    aiImportMsg.value = 'Konnte nicht kopieren — Text manuell markieren.'
    aiImportOk.value = false
  }
}

const onTomGeneratePrompt = async () => {
  if (!store.selectedProjekt) return
  aiBusy.value = true
  aiResponseRaw.value = ''
  aiImportMsg.value = ''
  try {
    const res = await apiClient.post(
      `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/tom/ai-prompt`,
      {},
    )
    aiPromptModal.value = {
      open: true,
      kind: 'tom',
      prompt: res.data.prompt,
      firma: res.data.firma || '',
      evidence_count: res.data.evidence_count || 0,
    }
  } catch (e: any) {
    aiImportMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
    aiImportOk.value = false
  } finally {
    aiBusy.value = false
  }
}

const onPrivacyGeneratePrompt = async () => {
  if (!store.selectedProjekt) return
  aiBusy.value = true
  aiResponseRaw.value = ''
  aiImportMsg.value = ''
  try {
    const res = await apiClient.post(
      `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/privacy/ai-prompt`,
      {},
    )
    aiPromptModal.value = {
      open: true,
      kind: 'privacy',
      prompt: res.data.prompt,
      firma: res.data.firma || '',
      evidence_count: res.data.evidence_count || 0,
    }
  } catch (e: any) {
    aiImportMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
    aiImportOk.value = false
  } finally {
    aiBusy.value = false
  }
}

const onAiImport = async () => {
  if (!store.selectedProjekt || !aiResponseRaw.value) return
  aiBusy.value = true
  aiImportMsg.value = ''
  try {
    const path = aiPromptModal.value.kind === 'tom'
      ? `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/tom/ai-import`
      : `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/privacy/ai-import`
    const res = await apiClient.post(path, { raw: aiResponseRaw.value, merge: true })
    aiImportOk.value = true
    if (aiPromptModal.value.kind === 'tom') {
      aiImportMsg.value = `✓ ${res.data.abschnitte_count} Abschnitte importiert. TOM-DOCX nutzt jetzt KI-Inhalte.`
      await loadTomDraft()
    } else {
      aiImportMsg.value = `✓ ${res.data.fields_set} Felder befüllt (${res.data.missing.length} Pflichtfelder noch leer).`
      await loadPrivacyIntake()
    }
    setTimeout(() => { aiPromptModal.value.open = false; aiResponseRaw.value = '' }, 1800)
  } catch (e: any) {
    aiImportOk.value = false
    aiImportMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
  } finally {
    aiBusy.value = false
  }
}

// Training
const trainingOutline = ref<any | null>(null)
const trainingZielgruppen = ref<string[]>(['alle'])
const trainingBusy = ref(false)
const trainingMsg = ref('')
const trainingErr = ref(false)
const loadTrainingOutline = async () => {
  if (trainingOutline.value) return
  try {
    const res = await apiClient.get('/dsgvo/training/outline')
    trainingOutline.value = res.data
  } catch { /* ignore */ }
}
const onZielgruppeToggle = (key: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  if (checked && !trainingZielgruppen.value.includes(key)) {
    trainingZielgruppen.value.push(key)
  } else if (!checked) {
    trainingZielgruppen.value = trainingZielgruppen.value.filter(z => z !== key)
  }
}
const downloadTraining = async () => {
  if (!store.selectedProjekt) return
  trainingBusy.value = true
  trainingMsg.value = ''
  trainingErr.value = false
  try {
    const res = await apiClient.post(
      `/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/training/export`,
      { zielgruppen: trainingZielgruppen.value },
      { responseType: 'blob', timeout: 120000 },
    )
    const blob = res.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `Schulung_${store.selectedProjekt}.docx`
    a.click()
    URL.revokeObjectURL(url)
    trainingMsg.value = '✓ Heruntergeladen.'
    setTimeout(() => trainingMsg.value = '', 3000)
  } catch (e: any) {
    trainingErr.value = true
    trainingMsg.value = `Fehler: ${e?.response?.data?.error || e.message}`
  } finally {
    trainingBusy.value = false
  }
}

// Lazy-load tab data
watch(activeTab, async (t) => {
  if (t === 'tom') { await loadTom(); await loadTomDraft() }
  if (t === 'privacy') { await loadPrivacySchema(); await loadPrivacyIntake() }
  if (t === 'training') await loadTrainingOutline()
  if (t === 'cockpit') await loadCockpitFirma()
})
const newForm = ref({ name: '', unternehmen: '', organisationstyp: 'verantwortlicher', beschreibung: '' })
const editingReq = ref<any | null>(null)
const searchQuery = ref('')
const filterKapitel = ref('')
const filterStatus = ref<'all' | 'pending' | 'partial' | 'complete'>('all')

const onImported = async () => {
  if (!store.selectedProjekt) return
  await store.fetchAnforderungen(store.selectedProjekt)
  await store.fetchReifegrad(store.selectedProjekt)
}

const chapters = computed(() => {
  const set = new Set<string>()
  for (const a of store.anforderungen) set.add(a.kapitel)
  return Array.from(set).sort()
})

const visible = computed(() => {
  let list = store.anforderungen
  if (filterKapitel.value) list = list.filter(a => a.kapitel === filterKapitel.value)
  if (filterStatus.value !== 'all') list = list.filter(a => a.status === filterStatus.value)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(a =>
      a.id.toLowerCase().includes(q) ||
      (a.titel || '').toLowerCase().includes(q) ||
      (a.beschreibung || '').toLowerCase().includes(q),
    )
  }
  return list
})

const kapitelColor = (id: string): string => {
  return store.constants?.kapitel?.[id]?.farbe || '#1565c0'
}
const kapitelTitle = (id: string): string => {
  return store.constants?.kapitel?.[id]?.titel || id
}

// ChapterCard braucht bewertet/gesamt — pro Kapitel aus den Anforderungen ableiten.
const kapitelCounts = (kap: string): { bewertet: number; gesamt: number } => {
  const inKap = store.anforderungen.filter(a => a.kapitel === kap)
  return {
    gesamt: inKap.length,
    bewertet: inKap.filter(a => a.status === 'complete').length,
  }
}

// #1250: einheitliches Dashboard — DSMS-Cockpit (Bereiche/Fristen/Reifegrad)
// in den Dashboard-Tab konsolidiert; Bereichskarten = DSMS-Bereiche.
const STATUS_AMPEL: Record<string, string | undefined> = {
  gruen: 'gruen', gelb: 'orange', rot: 'rot', leer: undefined,
}
const dashboardGesamtPct = computed(() => dsmsStore.cockpit?.gesamt_reifegrad ?? 0)
const dashboardGesamtAmpel = computed(() => {
  const p = dashboardGesamtPct.value
  return p >= 70 ? 'gruen' : p >= 40 ? 'orange' : 'rot'
})
const dashboardStats = computed(() => [
  `${dsmsStore.cockpit?.areas.length ?? 0} DSMS-Bereiche`,
  `${store.reifegrad?.bewertete_count ?? 0} / ${store.reifegrad?.gesamt_count ?? 0} Anforderungen bewertet`,
])
const dashboardBereiche = computed(() =>
  (dsmsStore.cockpit?.areas || []).map(a => ({
    id: a.key,
    title: a.label,
    percent: a.reifegrad_pct,
    bewertet: 0,
    gesamt: 0,
    ampel: STATUS_AMPEL[a.status],
  })),
)
const dashboardFristen = computed(() =>
  (dsmsStore.cockpit?.offene_aufgaben || []).map(t => ({
    text: `${t.area_label}: ${t.text}`,
    due: t.due,
    overdue: t.overdue,
    tab: t.tab,
  })),
)
const dashboardLuecken = computed(() =>
  store.anforderungen
    .filter(a => Number(a.bewertung ?? 0) < 5)
    .map(a => ({ id: a.id, titel: a.titel, bewertung: Number(a.bewertung ?? 0) }))
    .sort((x, y) => x.bewertung - y.bewertung),
)
const openAnforderung = (id: string) => {
  const r = store.anforderungen.find(a => a.id === id)
  if (r) editingReq.value = r
}
// DSMS-Bereichskarte → passenden Detail-Tab öffnen (key ist meist die tab-id).
const onOpenBereich = (key: string) => {
  const area = dsmsStore.cockpit?.areas.find(a => a.key === key)
  if (area?.tab) activeTab.value = area.tab
}

const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']
const scoreColor = (s: number) => SCORE_COLORS[s] || '#9e9e9e'
const statusLabel = (s: string): string => {
  if (s === 'complete') return 'Vollständig'
  if (s === 'partial') return 'Teilweise'
  return 'Ausstehend'
}

const exportUrl = (fmt: string): string => {
  if (!store.selectedProjekt) return '#'
  return `/api/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/report?format=${fmt}`
}

const confirmDeleteProjekt = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`DSGVO-Projekt "${store.selectedProjekt}" wirklich löschen?\n\nAlle Bewertungen, Intake-Daten und KI-Drafts gehen verloren.`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const startNew = () => {
  newForm.value = { name: '', unternehmen: '', organisationstyp: 'verantwortlicher', beschreibung: '' }
  creating.value = true
  if (firmenStore.firmen.length === 0) firmenStore.fetchFirmen()
}

// Issue #436: Firma des Projekts nachtraeglich aendern
const reassignSaving = ref(false)
const reassignMsg = ref<{ ok: string; err: string }>({ ok: '', err: '' })
const onReassignFirma = async (newFirma: string) => {
  if (!store.selectedProjekt) return
  reassignSaving.value = true
  reassignMsg.value = { ok: '', err: '' }
  try {
    await store.updateProjekt(store.selectedProjekt, { unternehmen: newFirma } as any)
    await store.fetchProjekte()
    reassignMsg.value.ok = newFirma ? `✓ Firma geändert auf „${newFirma}"` : '✓ Firmenzuordnung entfernt'
    setTimeout(() => { reassignMsg.value = { ok: '', err: '' } }, 4000)
  } catch (e: any) {
    reassignMsg.value.err = e?.response?.data?.error || 'Fehler beim Speichern'
  } finally {
    reassignSaving.value = false
  }
}

const onCreate = async () => {
  if (!newForm.value.name.trim()) {
    store.error = 'Projektname ist Pflicht.'
    return
  }
  const result = await store.createProjekt(newForm.value)
  if (result) {
    store.selectedProjekt = result.name
    creating.value = false
    await reloadProjekt()
  }
}

const editAnforderung = (req: any) => {
  editingReq.value = req
}

const onActionSaved = async () => {
  editingReq.value = null
  await reloadProjekt()
}

const onSaveBewertung = async (data: any) => {
  if (!editingReq.value || !store.selectedProjekt) return
  const ok = await store.saveBewertung(store.selectedProjekt, editingReq.value.id, data)
  if (ok) {
    editingReq.value = null
    await store.fetchReifegrad(store.selectedProjekt)
    await store.fetchAnforderungen(store.selectedProjekt)
  }
}

const reloadProjekt = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchAnforderungen(store.selectedProjekt),
    store.fetchReifegrad(store.selectedProjekt),
    dsmsStore.fetchCockpit(store.selectedProjekt),
    loadDashboardExtras(store.selectedProjekt),
  ])
}

watch(() => store.selectedProjekt, async (n) => {
  cockpitFirmenId.value = null
  if (n) {
    await reloadProjekt()
    if (activeTab.value === 'cockpit') await loadCockpitFirma()
  }
}, { immediate: false })

onMounted(async () => {
  await store.fetchConstants()
  await store.fetchProjekte()
  // Issue #434: Deep-Link via ?projekt=<firma> aus FirmenView
  const proj = (route.query.projekt || '') as string
  if (proj) {
    store.selectedProjekt = proj
  } else if (!store.selectedProjekt && store.projekte.length > 0) {
    store.selectedProjekt = store.projekte[0].name
  }
  if (store.selectedProjekt) await reloadProjekt()
})

const bulkCreating = ref(false)
async function bulkCreateIssues() {
  if (!store.selectedProjekt) return
  bulkCreating.value = true
  try {
    const res = await apiClient.post(`/dsgvo/projekte/${encodeURIComponent(store.selectedProjekt)}/issues/bulk`, {}, { timeout: 120000 })
    const d = (res && res.data) ? res.data : {}
    alert(`Issues angelegt: ${d.created ?? 0} · übersprungen: ${d.skipped ?? 0} · fehlgeschlagen: ${d.failed ?? 0}`)
    await store.fetchAnforderungen(store.selectedProjekt)
  } catch (e: any) {
    if (e && e.response && e.response.status === 400) {
      alert('Kein Repository konfiguriert. Bitte zuerst Repository im Panel speichern.')
    } else {
      store.error = (e && e.response && e.response.data && e.response.data.error) || 'Issues konnten nicht angelegt werden.'
    }
  } finally {
    bulkCreating.value = false
  }
}
</script>

<style scoped>
.dsgvo-view { max-width: 1400px; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350;
}

.empty-state {
  background: var(--color-surface); padding: 32px; border-radius: 8px;
  border: 1px solid var(--color-border); text-align: center;
}
.empty-state h3 { margin: 0 0 12px; }
.empty-state p { color: var(--color-text-secondary); margin-bottom: 20px; }

.project-name { margin: 0; font-size: 16px; flex: 1; color: var(--color-text-primary); }
.project-company { font-weight: 400; color: var(--color-text-secondary); font-size: 13px; }

.btn-danger-mini {
  background: #ffebee; color: #c62828; border: 1px solid #ef5350;
  padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.btn-danger-mini:hover { background: #ffcdd2; }

.tab-content { padding: 8px 0; }

.dashboard {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.gauge-card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  padding: 16px; border-radius: 8px;
  display: flex; flex-direction: column; align-items: center;
}
.gauge-stats { margin-top: 12px; font-size: 13px; color: var(--color-text-secondary); text-align: center; }
.chapters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.anf-toolbar {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  background: var(--color-surface); padding: 10px; border-radius: 6px;
  border: 1px solid var(--color-border); margin-bottom: 8px;
}
.search { flex: 1; min-width: 200px; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; }
.filter { padding: 6px 8px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; }
.info { font-size: 12px; color: var(--color-text-secondary); }
.export-group { display: flex; gap: 6px; align-items: center; margin-left: auto; }
.export-group span { font-size: 12px; color: var(--color-text-secondary); }
.export-btn { font-size: 12px; }

.anf-list { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
.anf-list table { width: 100%; border-collapse: collapse; }
.anf-list th {
  background: var(--color-background); text-align: left;
  padding: 8px 10px; font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--color-border);
}
.anf-list td {
  padding: 8px 10px; border-bottom: 1px solid var(--color-border); font-size: 13px;
}
.anf-list tbody tr { cursor: pointer; }
.anf-list tbody tr:hover { background: var(--color-background); }
.title-cell { max-width: 500px; }
code { background: var(--color-background); padding: 2px 6px; border-radius: 3px; font-size: 12px; }
.kapitel-tag {
  font-family: monospace; font-size: 11px;
  padding: 2px 8px; border-radius: 3px; font-weight: 600;
}
.score-pill {
  display: inline-block; min-width: 26px; padding: 2px 8px;
  border-radius: 12px; color: #fff; text-align: center; font-weight: 700;
}
.status-pill { font-size: 12px; padding: 2px 10px; border-radius: 12px; font-weight: 600; }
.status-pill.pending { background: #ffebee; color: #c62828; }
.status-pill.partial { background: #fff3e0; color: #e65100; }
.status-pill.complete { background: #e8f5e9; color: #2e7d32; }
.empty { padding: 32px; text-align: center; color: var(--color-text-secondary); }

.btn-primary {
  background: var(--color-primary); color: #fff; border: none;
  padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 500;
  text-decoration: none; display: inline-block;
}
.btn-primary:hover { background: var(--color-primary-dark); }
.btn-secondary {
  background: var(--color-background); color: var(--color-primary);
  border: 1px solid var(--color-border);
  padding: 8px 16px; border-radius: 4px; cursor: pointer;
}
.btn-secondary:hover { background: var(--color-border); }

.generator-card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  padding: 24px; border-radius: 8px;
}
.generator-card h3 { margin: 0 0 8px; }
.generator-card > p { color: var(--color-text-secondary); margin: 0 0 16px; }

.tom-list { margin: 12px 0; }
.tom-item { padding: 6px 12px; background: var(--color-background); margin-bottom: 4px; border-radius: 4px; }
.muted { color: var(--color-text-secondary); font-size: 13px; }

.privacy-form { margin: 16px 0; }
.form-group { background: var(--color-background); border-radius: 6px; padding: 8px 14px; margin-bottom: 8px; }
.form-group summary { font-weight: 600; cursor: pointer; padding: 4px 0; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding-top: 12px; }
.form-cell { display: flex; flex-direction: column; gap: 4px; }
.form-cell label { font-size: 13px; font-weight: 600; }
.form-cell label .req { color: #c62828; }
.form-cell input, .form-cell select, .form-cell textarea {
  padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: var(--color-surface); color: var(--color-text-primary);
}
.form-cell .hint { font-size: 11px; color: var(--color-text-secondary); }
.checklist { display: flex; flex-direction: column; gap: 4px; }
.check-row { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; padding: 4px 0; }
.check-row input[type="checkbox"] { margin: 0; }

.training-zielgruppen { margin-bottom: 16px; }
.training-zielgruppen h4 { margin: 0 0 8px; }

.action-row {
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  padding-top: 16px; border-top: 1px solid var(--color-border); margin-top: 16px;
}
.hint.ok { color: var(--color-success); }
.hint.err { color: var(--color-error); }

.assistenten-intro {
  background: var(--color-surface); border: 1px solid var(--color-border);
  padding: 16px 20px; border-radius: 8px; margin-bottom: 16px;
}
.assistenten-intro h3 { margin: 0 0 6px; }
.assistenten-intro p { margin: 0; color: var(--color-text-secondary); font-size: 13px; }

.cockpit-hint {
  background: var(--color-surface); border: 1px solid var(--color-border);
  padding: 24px; border-radius: 8px; color: var(--color-text-secondary);
  text-align: center;
}
.cockpit-hint.warn {
  background: #fff3e0; border-color: #ff9800; color: #e65100;
}

/* KI-Prompt-Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: white; border-radius: 8px;
  max-width: 700px; width: 95%; max-height: 90vh;
  display: flex; flex-direction: column;
}
.modal-content.modal-wide { max-width: 860px; }
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid var(--color-border);
}
.modal-header h3 { margin: 0; color: var(--color-primary); font-size: 16px; }
.btn-close { background: none; border: none; font-size: 22px; color: #999; cursor: pointer; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.modal-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 12px 20px; border-top: 1px solid var(--color-border);
}
.prompt-textarea {
  width: 100%; padding: 8px; border: 1px solid var(--color-border);
  border-radius: 4px; font-family: monospace; font-size: 12px; resize: vertical;
}
.btn-mini {
  background: white; border: 1px solid var(--color-border);
  padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px;
  margin-bottom: 8px;
}
.alert-warn {
  background: #fff3e0; color: #e65100; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ff9800; font-size: 13px;
}
.hint { font-size: 12px; color: var(--color-text-secondary); }
.gap { color: #e65100; }
</style>
