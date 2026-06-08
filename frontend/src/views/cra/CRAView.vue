<template>
  <div class="cra-view">
    <div class="header">
      <h2>CRA – Cyber Resilience Act</h2>
      <p>Verordnung (EU) 2024/2847 · 32 Anforderungen + 10 OWASP Proactive Controls</p>
      <ModuleHelpButton module="cra" />
    </div>

    <HelpDialog
      :open="helpOpen"
      title="CRA – Erläuterung der Kapitel"
      subtitle="Verordnung (EU) 2024/2847 — Cyber Resilience Act"
      header-bg="#1565c0"
      :kapitel="store.constants?.kapitel"
      :bewertung-skala="store.constants?.bewertung_skala"
      @close="helpOpen = false"
    />

    <div v-if="store.error" class="alert alert-error">{{ store.error }}</div>

    <div v-if="!store.selectedProjektObj && !creating" class="empty-state">
      <h3>{{ store.projekte.length === 0 ? 'Noch kein CRA-Projekt' : 'Projekt wählen' }}</h3>
      <p>Wähle links ein Projekt oder lege ein neues an.</p>
      <button class="btn-primary" @click="startNew">+ Neues CRA-Projekt</button>
    </div>

    <div v-else-if="creating" class="form-card">
      <h3>Neues CRA-Projekt</h3>
      <div class="form-row">
        <label>Projektname *</label>
        <input v-model="newForm.name" placeholder="z.B. Mein Produkt CRA-Readiness" />
      </div>
      <!-- Issue #427/#429: Firmen-Dropdown statt Freitext -->
      <div class="form-row">
        <label>Firma</label>
        <select v-model="newForm.unternehmen">
          <option value="">— ohne Firma —</option>
          <option v-for="k in firmenStore.firmen" :key="k.name" :value="k.name">
            {{ k.name }}<span v-if="k.company"> ({{ k.company }})</span>
          </option>
        </select>
        <small class="hint">Verknüpft das Projekt mit einem Firmen aus der Firmenverwaltung.</small>
      </div>
      <div class="form-row">
        <label>Produkt</label>
        <input v-model="newForm.produkt" />
      </div>
      <div class="form-row">
        <label>Produktklasse</label>
        <select v-model="newForm.produktklasse">
          <option value="default">— Default —</option>
          <option value="important_i">Important Class I (Annex III)</option>
          <option value="important_ii">Important Class II (Annex III)</option>
          <option value="critical_i">Critical Class I (Annex IV)</option>
          <option value="critical_ii">Critical Class II (Annex IV)</option>
        </select>
      </div>
      <div class="form-row">
        <label>Beschreibung</label>
        <textarea v-model="newForm.beschreibung" rows="3"></textarea>
      </div>
      <div class="form-actions">
        <button class="btn-secondary" @click="creating = false">Abbrechen</button>
        <button class="btn-primary" @click="onCreate">Anlegen</button>
      </div>
    </div>

    <template v-else-if="store.selectedProjektObj">
      <!-- Tab-Navigation -->
      <div class="project-bar">
        <h3 class="project-name">{{ store.selectedProjektObj?.name }}
          <span v-if="store.selectedProjektObj?.produkt" class="project-company">— {{ store.selectedProjektObj.produkt }}</span>
        </h3>
        <FirmaSelector
          :model-value="(store.selectedProjektObj as any)?.unternehmen || ''"
          :saving="reassignSaving"
          :success-text="reassignMsg.ok"
          :error-text="reassignMsg.err"
          @save="onReassignFirma"
        />
        <button class="btn-secondary" @click="bulkCreateIssues" :disabled="issuesBusy" title="Für alle offenen Anforderungs-Gaps (Score &lt; 5) GitHub-Issues anlegen">{{ issuesBusy ? '⏳ Anlegen…' : '🐙 Issues anlegen' }}</button>
        <button class="btn-secondary" @click="syncIssues" :disabled="syncingIssues" title="Status aller verlinkten Issues dieses Projekts von GitHub/GitLab aktualisieren">{{ syncingIssues ? '⏳ Sync…' : '🔄 Issues synchronisieren' }}</button>
        <button class="btn-secondary" @click="importIssues" :disabled="importingIssues" title="Inhalt (Titel/Status/Kommentare) aller verlinkten Issues in die jeweiligen Anforderungs-Bewertungen übernehmen">{{ importingIssues ? '⏳ Übernehme…' : '📥 Issue-Feedback übernehmen' }}</button>
        <button class="btn-danger-mini" @click="confirmDeleteProjekt" title="Projekt löschen">🗑️ Projekt löschen</button>
      </div>

      <!-- #862: Pro-Projekt-Repository-Konfiguration (für Issue-Anlage/Sync) -->
      <RepoConfigPanel
        v-if="store.selectedProjekt"
        :api-base="'/cra'"
        :projekt-name="store.selectedProjekt"
      />

      <div class="tabs">
        <button v-for="t in tabs" :key="t.id"
                :class="['tab-btn', { active: activeTab === t.id }]"
                @click="activeTab = t.id">
          {{ t.label }}
        </button>
      </div>

      <!-- Tab: Dashboard (F5e) -->
      <div v-if="activeTab === 'dashboard'" class="tab-content">
        <div class="dashboard">
          <div class="gauge-card">
            <MaturityGauge
              :percent="Math.round(store.reifegrad?.gesamt?.prozent ?? 0)"
              :ampel="store.reifegrad?.gesamt?.ampel"
              label="Gesamt-Reifegrad"
            />
            <div class="gauge-stats">
              <div>{{ store.reifegrad?.gesamt?.punkte_aktuell ?? 0 }} / {{ store.reifegrad?.gesamt?.punkte_max ?? 0 }} Punkte</div>
              <div>{{ store.anforderungen.length }} Anforderungen · {{ store.owaspControls.length }} OWASP</div>
            </div>
          </div>

          <div class="chapters-grid">
            <ChapterCard
              v-for="(data, kapitel) in store.reifegrad?.kapitel || {}"
              :key="kapitel"
              :id="String(kapitel)"
              :title="chapterTitle(String(kapitel))"
              :percent="Math.round(data.prozent ?? 0)"
              :bewertet="data.bewertet ?? 0"
              :gesamt="data.gesamt ?? 0"
              :ampel="data.ampel"
              @click="activeTab = 'requirements'; filterKapitel = String(kapitel)"
            />
          </div>
        </div>

        <!-- OWASP Status -->
        <div class="owasp-status-card">
          <h3>🛡️ OWASP Proactive Controls</h3>
          <div class="owasp-bar">
            <div v-for="c in store.owaspControls" :key="c.id"
                 :class="['owasp-segment', { evaluated: c.score > 0 }]"
                 :title="`${c.id}: ${c.title} (${c.score}/5)`"
                 @click="activeTab = 'owasp'">
              <span>{{ c.id.replace('OWASP-PC-', '') }}</span>
            </div>
          </div>
          <div class="owasp-stats">
            {{ owaspEvaluated }} / {{ store.owaspControls.length }} bewertet
            ·
            ø {{ owaspAvg.toFixed(1) }} / 5
          </div>
        </div>

        <!-- Lücken -->
        <div v-if="(store.reifegrad?.luecken || []).length > 0" class="luecken-section">
          <h3>🚨 Top-Lücken</h3>
          <div class="luecken-list">
            <div v-for="l in (store.reifegrad?.luecken || []).slice(0, 8)"
                 :key="l.id" class="luecken-item"
                 @click="editAnforderungById(l.id)">
              <code>{{ l.id }}</code>
              <strong>{{ l.titel }}</strong>
              <span class="luecken-meta">{{ l.kapitel }} · Gew. {{ l.gewichtung }} · Score {{ l.bewertung }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab: Anforderungen (F5f) -->
      <div v-if="activeTab === 'requirements'" class="tab-content">
        <div class="anf-toolbar">
          <input v-model="searchQuery" placeholder="Suche…" class="search" />
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
          <button class="btn-secondary" @click="customDialogOpen = true">+ Custom</button>
          <button class="btn-secondary" @click="repoScanOpen = true">🔍 Repo-Scan</button>
          <span class="info">{{ visibleAnforderungen.length }} / {{ store.anforderungen.length }}</span>
          <span v-if="linkedRiskProjekt" class="coverage-info"
                :title="`Anforderungen mit mindestens einem verknüpften Risiko aus „${linkedRiskProjekt}“ (rein informativ)`">
            🔗 {{ coverageSummary.abgedeckt }}/{{ coverageSummary.gesamt }} mit Risiko
          </span>
        </div>

        <div class="anf-list">
          <table v-if="visibleAnforderungen.length > 0">
            <thead>
              <tr>
                <th>ID</th>
                <th>Kapitel</th>
                <th>Titel</th>
                <th>Bewertung</th>
                <th>Status</th>
                <th v-if="linkedRiskProjekt" title="Anzahl verknüpfter Risiken aus dem Risikobewertungs-Projekt (rein informativ)">🔗 Risiken</th>
                <th>Gewicht</th>
                <th>Quelle</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in visibleAnforderungen" :key="r.id" @click="editingReq = r">
                <td><code>{{ r.id }}</code></td>
                <td>{{ r.kapitel }}</td>
                <td class="title-cell">{{ r.titel }}</td>
                <td><span class="score-pill" :style="{ background: scoreColor(r.bewertung) }">{{ r.bewertung }}</span></td>
                <td><span :class="['status-pill', r.status]">{{ statusLabel(r.status) }}</span></td>
                <td v-if="linkedRiskProjekt">
                  <span v-if="(riskCoverage[r.id] || 0) > 0"
                        class="risk-badge"
                        :title="`${riskCoverage[r.id]} verknüpfte(s) Risiko(en) in „${linkedRiskProjekt}“`">
                    {{ riskCoverage[r.id] }}
                  </span>
                  <span v-else class="risk-badge-empty" title="Keine verknüpften Risiken">–</span>
                </td>
                <td>{{ r.gewichtung }}</td>
                <td><span class="quelle-tag" v-if="r.quelle !== 'standard'">{{ r.quelle }}</span></td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">Keine Anforderungen zum Filter.</div>
        </div>
      </div>

      <!-- Tab: OWASP (F5g) -->
      <div v-if="activeTab === 'owasp'" class="tab-content">
        <div class="owasp-grid">
          <div v-for="c in store.owaspControls" :key="c.id" class="owasp-card"
               @click="editingOwasp = c">
            <div class="owasp-header">
              <span class="owasp-id">{{ c.id }}</span>
              <span class="score-pill" :style="{ background: scoreColor(c.score) }">{{ c.score }}/5</span>
            </div>
            <h4>{{ c.title }}</h4>
            <p class="owasp-desc">{{ truncate(c.description, 150) }}</p>
            <div class="owasp-meta">
              <span class="evidence-count">📎 {{ (c.evidence || []).length }} Evidence</span>
              <span v-if="c.cra_articles?.length" class="cra-articles">
                CRA: {{ c.cra_articles.slice(0, 2).join(', ') }}{{ c.cra_articles.length > 2 ? '…' : '' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab: Pflicht-Doku (Phase A, #472-#476) -->
      <div v-if="activeTab === 'pflichtdoku'" class="tab-content">
        <PflichtDokuPanel @open-assistenten="activeTab = 'assistenten'" />
      </div>

      <!-- Tab: Assistenten (S11 / #1081) -->
      <div v-if="activeTab === 'assistenten'" class="tab-content">
        <AssistentenPanel v-if="store.selectedProjekt" @applied="onAssistentenApplied" />
        <div v-else class="action-card">
          <p class="hint">Bitte zuerst ein CRA-Projekt auswählen.</p>
        </div>
      </div>

      <!-- Tab: Risiko-Cockpit (S11 / #1081) -->
      <div v-if="activeTab === 'risikocockpit'" class="tab-content">
        <RiskCockpitPanel v-if="store.selectedProjekt" :projekt="store.selectedProjekt" />
        <div v-else class="action-card">
          <p class="hint">Bitte zuerst ein CRA-Projekt auswählen.</p>
        </div>
      </div>

      <!-- Tab: Fragebogen (F5h) -->
      <div v-if="activeTab === 'fragebogen'" class="tab-content">
        <div class="action-card">
          <h3>📊 Excel-Fragebogen</h3>
          <p>Exportiert alle 32 Anforderungen mit aktuellen Bewertungen als bearbeitbare Excel-Datei. Zur Offline-Erfassung oder als Übergabe.</p>
          <div class="action-buttons">
            <DownloadButton :endpoint="stripApi(exportUrl('fragebogen'))" class="btn-primary">⬇️ Fragebogen herunterladen</DownloadButton>
            <span class="hint">Format: .xlsx mit Farbcodierung pro Kapitel</span>
          </div>
        </div>

        <div class="action-card" style="margin-top: 16px;">
          <h3>📤 Excel-Fragebogen importieren</h3>
          <p>Lädt einen ausgefüllten Fragebogen hoch und überschreibt die Bewertungen im Projekt.</p>
          <div class="action-buttons">
            <ImportButton
              v-if="store.selectedProjekt"
              :endpoint="`/cra/projekte/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
              label="⬆️ Fragebogen hochladen"
              @imported="onCraImported"
            />
          </div>
        </div>
      </div>

      <!-- Tab: Risikoanalyse (#882/#883) — Verknüpfung zum Modul Risikobewertung -->
      <div v-if="activeTab === 'risikoanalyse'" class="tab-content">
        <RisikoanalysePanel v-if="store.selectedProjekt" :projekt-name="store.selectedProjekt" />
        <div v-else class="action-card">
          <p class="hint">Bitte zuerst ein CRA-Projekt auswählen.</p>
        </div>
      </div>

      <!-- Tab: Bericht (F5h) -->
      <div v-if="activeTab === 'bericht'" class="tab-content">
        <div class="action-card">
          <h3>📄 Compliance-Bericht</h3>
          <p>Vollständiger Report mit Management Summary, Kapitelanalyse und optional Maßnahmenplan.</p>

          <div class="report-options">
            <label class="checkbox-label">
              <input type="checkbox" v-model="reportOpts.massnahmenplan" />
              Maßnahmenplan einschließen
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="reportOpts.detailanforderungen" />
              Detail-Anforderungen einschließen
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="reportOpts.quellen" />
              Quellenangaben (10 Referenzen)
            </label>
          </div>

          <div class="action-buttons">
            <DownloadButton :endpoint="stripApi(reportUrl('docx'))" class="btn-primary">📝 Word-Report</DownloadButton>
            <DownloadButton :endpoint="stripApi(reportUrl('pdf'))" class="btn-primary">📄 PDF-Report</DownloadButton>
          </div>
        </div>
      </div>
    </template>

    <!-- Editor (shared) -->
    <RequirementEditor
      v-if="editingReq"
      :requirement="editingReq"
      @save="onSaveBewertung"
      @cancel="editingReq = null"
    >
      <template #actions>
        <RequirementActions
          v-if="editingReq?.id"
          :requirement="editingReq"
          :projekt-name="store.selectedProjekt || ''"
          api-base="/cra"
          :default-repo="defaultRepoFromMeta"
          @saved="onActionSaved"
          @error="(msg: string) => store.error = msg"
        />
      </template>
    </RequirementEditor>

    <!-- OWASP-Editor (custom inline) -->
    <div v-if="editingOwasp" class="modal-overlay" @mousedown.self="editingOwasp = null">
      <div class="modal-content owasp-edit-modal">
        <div class="modal-header">
          <h3>{{ editingOwasp.id }}: {{ editingOwasp.title }}</h3>
          <button class="btn-close" @click="editingOwasp = null">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">{{ editingOwasp.description }}</p>
          <div class="cra-mapping" v-if="editingOwasp.cra_articles?.length">
            <strong>CRA-Mapping:</strong> {{ editingOwasp.cra_articles.join(' · ') }}
          </div>
          <div class="evidence-hint">
            <strong>Hinweise:</strong> {{ editingOwasp.evidence_hint }}
          </div>

          <div class="form-row">
            <label>Score (0-5)</label>
            <input v-model.number="owaspForm.status" type="range" min="0" max="5" />
            <span class="score-display" :style="{ background: scoreColor(owaspForm.status) }">
              {{ owaspForm.status }}
            </span>
          </div>
          <div class="form-row">
            <label>Kommentar</label>
            <textarea v-model="owaspForm.kommentar" rows="3"></textarea>
          </div>
          <div class="form-row">
            <label>Evidence (URLs/Pfade, kommagetrennt)</label>
            <textarea v-model="owaspForm.evidenceText" rows="3"
                      placeholder="https://github.com/.../SECURITY.md"></textarea>
          </div>

          <RequirementActions
            v-if="editingOwasp?.id"
            :requirement="editingOwasp"
            :projekt-name="store.selectedProjekt || ''"
            api-base="/cra"
            object-kind="owasp"
            :default-repo="defaultRepoFromMeta"
            @saved="onOwaspActionSaved"
            @error="(msg: string) => store.error = msg"
          />
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="editingOwasp = null">Abbrechen</button>
          <button class="btn-primary" @click="onSaveOwasp">Speichern</button>
        </div>
      </div>
    </div>

    <!-- Repo-Scan-Dialog -->
    <div v-if="repoScanOpen" class="modal-overlay" @mousedown.self="repoScanOpen = false">
      <div class="modal-content scan-modal">
        <div class="modal-header">
          <h3>🔍 Full Repo-Scan</h3>
          <button class="btn-close" @click="repoScanOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">Scannt das Repository auf ~65 Sicherheits-Signale und generiert Vorschläge für CRA-Anforderungen + OWASP-Controls.</p>
          <div class="form-row">
            <label>Repository-URL *</label>
            <input v-model="scanInput.repo" placeholder="https://github.com/owner/repo" />
          </div>
          <div class="form-row">
            <label>Branch</label>
            <input v-model="scanInput.branch" placeholder="main" />
          </div>
          <div v-if="scanLoading" class="info">⏳ Scan läuft… (kann dauern)</div>
          <div v-if="scanError" class="alert-error">⚠️ {{ scanError }}</div>

          <div v-if="store.requirementSuggestions.length > 0 || store.owaspSuggestions.length > 0" class="suggestions">
            <h4>Vorschläge: {{ store.requirementSuggestions.length }} Anforderungen, {{ store.owaspSuggestions.length }} OWASP</h4>
            <div v-for="s in [...store.requirementSuggestions, ...store.owaspSuggestions]"
                 :key="s.field_id" class="suggestion-card">
              <div class="sugg-header">
                <code>{{ s.field_id }}</code>
                <span class="sugg-score" :style="{ background: scoreColor(s.score) }">{{ s.score }}</span>
                <span class="sugg-conf">Konfidenz: {{ Math.round(s.confidence * 100) }}%</span>
              </div>
              <p>{{ s.kommentar }}</p>
              <button class="btn-small" @click="acceptSugg(s)">Übernehmen</button>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="repoScanOpen = false">Schließen</button>
          <button class="btn-primary" @click="runScan" :disabled="scanLoading">
            {{ scanLoading ? 'Lädt…' : 'Scan starten' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Custom-Anforderungs-Dialog -->
    <div v-if="customDialogOpen" class="modal-overlay" @mousedown.self="customDialogOpen = false">
      <div class="modal-content">
        <h3>Neue Custom-Anforderung</h3>
        <div class="form-row">
          <label>ID *</label>
          <input v-model="customForm.id" placeholder="z.B. AI1-CUSTOM-01" />
        </div>
        <div class="form-row">
          <label>Kapitel</label>
          <select v-model="customForm.kapitel">
            <option v-for="k in chapters" :key="k" :value="k">{{ k }}</option>
            <option value="IMPL">IMPL</option>
          </select>
        </div>
        <div class="form-row">
          <label>Titel *</label>
          <input v-model="customForm.titel" />
        </div>
        <div class="form-row">
          <label>Beschreibung</label>
          <textarea v-model="customForm.beschreibung" rows="3"></textarea>
        </div>
        <div class="form-row">
          <label>Hinweise</label>
          <textarea v-model="customForm.hinweise" rows="2"></textarea>
        </div>
        <div class="form-row">
          <label>Gewichtung (1-3)</label>
          <input v-model.number="customForm.gewichtung" type="number" min="1" max="3" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="customDialogOpen = false">Abbrechen</button>
          <button class="btn-primary" @click="onSaveCustom">Anlegen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import DownloadButton from '../../components/shared/DownloadButton.vue'

const stripApi = (u: string): string => u.replace(/^\/api/, '')
import { ref, computed, onMounted, watch } from 'vue'
import { useCraStore } from '../../stores/cra'
import { useFirmenStore } from '../../stores/firmen'
import { useRoute } from 'vue-router'
import MaturityGauge from '../../components/shared/MaturityGauge.vue'
import ChapterCard from '../../components/shared/ChapterCard.vue'
import RequirementEditor from '../../components/shared/RequirementEditor.vue'
import RequirementActions from '../../components/shared/RequirementActions.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import HelpDialog from '../../components/shared/HelpDialog.vue'
import ModuleHelpButton from '../../components/shared/ModuleHelpButton.vue'
import PflichtDokuPanel from './PflichtDokuPanel.vue'
import FirmaSelector from '../../components/shared/FirmaSelector.vue'
import RepoConfigPanel from '../../components/RepoConfigPanel.vue'
import RisikoanalysePanel from './RisikoanalysePanel.vue'
import AssistentenPanel from './AssistentenPanel.vue'
import RiskCockpitPanel from './RiskCockpitPanel.vue'

const store = useCraStore()
const firmenStore = useFirmenStore()
const route = useRoute()

const tabs = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'pflichtdoku', label: '📋 Pflicht-Doku (Start hier)' },
  { id: 'requirements', label: '✅ Anforderungen' },
  { id: 'owasp', label: '🛡️ OWASP SbD' },
  { id: 'assistenten', label: '🤖 Assistenten' },
  { id: 'risikocockpit', label: '📊 Risiko-Cockpit' },
  { id: 'fragebogen', label: '📥 Fragebogen' },
  { id: 'risikoanalyse', label: '🔍 Risikoanalyse' },
  { id: 'bericht', label: '📄 Bericht' },
]
const activeTab = ref<'dashboard' | 'requirements' | 'owasp' | 'pflichtdoku' | 'assistenten' | 'risikocockpit' | 'fragebogen' | 'risikoanalyse' | 'bericht'>('dashboard')

const creating = ref(false)
const newForm = ref({ name: '', unternehmen: '', produkt: '', produktklasse: 'default', beschreibung: '' })

const editingReq = ref<any | null>(null)
const editingOwasp = ref<any | null>(null)
const owaspForm = ref({ status: 0, kommentar: '', evidenceText: '' })

// #577: Beim Öffnen Form aus dem Control-State vorbelegen
watch(editingOwasp, (c) => {
  if (!c) return
  const evArr = Array.isArray(c.evidence)
    ? c.evidence.map((e: any) => typeof e === 'string' ? e : (e.url || e.path || ''))
    : []
  owaspForm.value = {
    status: Number(c.status ?? c.score ?? 0),
    kommentar: c.kommentar ?? '',
    evidenceText: evArr.filter(Boolean).join(', '),
  }
})

// Default-Repo aus Projekt-meta_json (für RequirementActions)
const defaultRepoFromMeta = computed(() => {
  try {
    const meta = JSON.parse(store.selectedProjektObj?.meta_json || '{}')
    return meta?.linked_app?.repo?.replace('https://github.com/', '') || ''
  } catch {
    return ''
  }
})

const helpOpen = ref(false)
const customDialogOpen = ref(false)
const customForm = ref({ id: '', kapitel: 'IMPL', titel: '', beschreibung: '', hinweise: '', gewichtung: 1 })

const repoScanOpen = ref(false)
const scanLoading = ref(false)
const scanError = ref('')
const scanInput = ref({ repo: '', branch: 'main' })

// Beim Öffnen: gespeicherte Repo-URL aus Projekt-Meta vorbefüllen
watch(repoScanOpen, (open) => {
  if (!open) return
  scanError.value = ''
  try {
    const meta = JSON.parse(store.selectedProjektObj?.meta_json || '{}')
    const linked = meta?.linked_app || {}
    if (linked.repo && !scanInput.value.repo) {
      scanInput.value.repo = String(linked.repo)
    }
    if (linked.branch && !scanInput.value.branch) {
      scanInput.value.branch = String(linked.branch)
    }
  } catch { /* ignore */ }
})

const reportOpts = ref({ massnahmenplan: true, detailanforderungen: true, quellen: true })

const syncingIssues = ref(false)
async function syncIssues() {
  if (!store.selectedProjekt) return
  syncingIssues.value = true
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post(`/cra/projekte/${encodeURIComponent(store.selectedProjekt)}/issues/sync`, {}, { timeout: 120000 })
    const d = r.data || {}
    alert(`Issues synchronisiert: ${d.synced || 0} aktualisiert, ${d.errors || 0} Fehler (gesamt ${d.total || 0}), davon ${d.auto_completed || 0} automatisch als vollständig bearbeitet markiert.`)
  } catch (e: any) {
    alert(e?.response?.data?.error || 'Issue-Sync fehlgeschlagen.')
  } finally { syncingIssues.value = false }
}

const importingIssues = ref(false)
async function importIssues() {
  if (!store.selectedProjekt) return
  if (!confirm('Inhalt aller verlinkten Issues in die jeweiligen Anforderungs-Bewertungen (Kommentar) übernehmen?')) return
  importingIssues.value = true
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post(`/cra/projekte/${encodeURIComponent(store.selectedProjekt)}/issues/import`, {}, { timeout: 120000 })
    const d = r.data || {}
    alert(`Issue-Feedback übernommen: ${d.imported || 0} Anforderungen aktualisiert, ${d.failed || 0} ohne Inhalt (gesamt ${d.total || 0}).`)
    await store.fetchAnforderungen(store.selectedProjekt)
  } catch (e: any) {
    alert(e?.response?.data?.error || 'Issue-Feedback-Import fehlgeschlagen.')
  } finally { importingIssues.value = false }
}

const issuesBusy = ref(false)
async function bulkCreateIssues() {
  // #862: Kein prompt() mehr — das pro Projekt im RepoConfigPanel gespeicherte
  // Repository wird serverseitig genutzt (kein `repo` im Request).
  if (!store.selectedProjekt) return
  issuesBusy.value = true
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.post(
      `/cra/projekte/${encodeURIComponent(store.selectedProjekt)}/issues/bulk`,
      { only_gaps: true, skip_linked: true },
      { timeout: 120000 },
    )
    const s = r.data?.summary || {}
    alert(`Issues angelegt: ${s.created || 0} erstellt, ${s.skipped || 0} übersprungen, ${s.failed || 0} fehlgeschlagen.`)
  } catch (e: any) {
    const msg = e?.response?.data?.error || ''
    if (e?.response?.status === 400 && msg.includes('Kein Repository')) {
      alert('Bitte zuerst das Repository im Panel speichern.')
    } else {
      alert(msg || 'Massen-Issue-Anlage fehlgeschlagen.')
    }
  } finally { issuesBusy.value = false }
}

const confirmDeleteProjekt = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`CRA-Projekt "${store.selectedProjekt}" wirklich löschen?\n\nAlle Bewertungen, OWASP-Checks und KI-Drafts gehen verloren.`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const onCraImported = async () => {
  if (!store.selectedProjekt) return
  await store.fetchAnforderungen(store.selectedProjekt)
  await store.fetchReifegrad(store.selectedProjekt)
}

const searchQuery = ref('')
const filterKapitel = ref('')
const filterStatus = ref<'all' | 'pending' | 'partial' | 'complete'>('all')

const KAPITEL_TITEL: Record<string, string> = {
  AI1: 'Annex I Part I',
  AI2: 'Annex I Part II',
  ART13: 'Artikel 13',
  ART14: 'Artikel 14',
  IMPL: 'Implementation',
}

const chapterTitle = (k: string): string => KAPITEL_TITEL[k] || k

const chapters = computed(() => {
  const set = new Set<string>()
  for (const a of store.anforderungen) set.add(a.kapitel)
  return Array.from(set).sort()
})

const visibleAnforderungen = computed(() => {
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

const owaspEvaluated = computed(() => store.owaspControls.filter(c => c.score > 0).length)
const owaspAvg = computed(() => {
  const evaluated = store.owaspControls.filter(c => c.score > 0)
  if (evaluated.length === 0) return 0
  return evaluated.reduce((sum, c) => sum + c.score, 0) / evaluated.length
})

const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']
const scoreColor = (s: number) => SCORE_COLORS[s] || '#9e9e9e'
const statusLabel = (s: string): string => {
  if (s === 'complete') return 'Vollständig'
  if (s === 'partial') return 'Teilweise'
  return 'Ausstehend'
}
const truncate = (s: string, n: number): string => (s && s.length > n) ? s.substring(0, n) + '…' : s

const exportUrl = (kind: 'fragebogen'): string => {
  if (!store.selectedProjekt) return '#'
  return `/api/cra/projekte/${encodeURIComponent(store.selectedProjekt)}/${kind}`
}

const reportUrl = (fmt: string): string => {
  if (!store.selectedProjekt) return '#'
  const opts = Object.entries(reportOpts.value)
    .filter(([_, v]) => v)
    .map(([k]) => k)
    .join(',')
  return `/api/cra/projekte/${encodeURIComponent(store.selectedProjekt)}/report?format=${fmt}&options=${opts}`
}

// ---- Aktionen ----
// Issue #436: Firma des Projekts nachtraeglich aendern
const reassignSaving = ref(false)
const reassignMsg = ref<{ ok: string; err: string }>({ ok: '', err: '' })
const onReassignFirma = async (newFirma: string) => {
  if (!store.selectedProjekt) return
  reassignSaving.value = true
  reassignMsg.value = { ok: '', err: '' }
  try {
    await store.updateProjekt(store.selectedProjekt as string, { unternehmen: newFirma } as any)
    await store.fetchProjekte()
    reassignMsg.value.ok = newFirma ? `✓ Firma geändert auf „${newFirma}"` : '✓ Firmenzuordnung entfernt'
    setTimeout(() => { reassignMsg.value = { ok: '', err: '' } }, 4000)
  } catch (e: any) {
    reassignMsg.value.err = e?.response?.data?.error || 'Fehler beim Speichern'
  } finally {
    reassignSaving.value = false
  }
}

const startNew = () => {
  newForm.value = { name: '', unternehmen: '', produkt: '', produktklasse: 'default', beschreibung: '' }
  creating.value = true
  if (firmenStore.firmen.length === 0) firmenStore.fetchFirmen()
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

const editAnforderungById = (id: string) => {
  const r = store.anforderungen.find(a => a.id === id)
  if (r) editingReq.value = r
}

const onSaveBewertung = async (data: any) => {
  if (!editingReq.value) return
  const ok = await store.saveBewertung(editingReq.value.id, data)
  if (ok) {
    editingReq.value = null
    await reloadProjekt()
  }
}

const onSaveOwasp = async () => {
  if (!editingOwasp.value) return
  const evidence = owaspForm.value.evidenceText
    .split(/[\n,]/).map(s => s.trim()).filter(Boolean)
  const ok = await store.updateOwaspControl(editingOwasp.value.id, {
    status: owaspForm.value.status,
    kommentar: owaspForm.value.kommentar,
    evidence,
  })
  if (ok) {
    editingOwasp.value = null
    if (store.selectedProjekt) await store.fetchOwaspControls(store.selectedProjekt)
  }
}

const onSaveCustom = async () => {
  if (!customForm.value.id || !customForm.value.titel) return
  const ok = await store.saveCustomAnforderung(customForm.value)
  if (ok) {
    customDialogOpen.value = false
    customForm.value = { id: '', kapitel: 'IMPL', titel: '', beschreibung: '', hinweise: '', gewichtung: 1 }
    await reloadProjekt()
  }
}

const runScan = async () => {
  if (!scanInput.value.repo) return
  scanLoading.value = true
  scanError.value = ''
  store.error = null
  const result = await store.fullRepoScan(scanInput.value.repo, scanInput.value.branch)
  scanLoading.value = false
  if (!result) {
    scanError.value = store.error || 'Scan fehlgeschlagen'
    return
  }
  // Erfolg → URL ins Projekt-Meta persistieren
  try {
    const meta = JSON.parse(store.selectedProjektObj?.meta_json || '{}')
    meta.linked_app = {
      ...(meta.linked_app || {}),
      repo: scanInput.value.repo,
      branch: scanInput.value.branch || '',
    }
    if (store.selectedProjekt) {
      await store.updateProjekt(store.selectedProjekt, { meta_json: JSON.stringify(meta) } as any)
    }
  } catch { /* meta-update best-effort */ }
}

const acceptSugg = async (s: any) => {
  const isOwasp = s.field_id.startsWith('OWASP-PC-')
  const ok = await store.acceptSuggestion(
    s.field_id, s.score, s.kommentar, isOwasp ? 'owasp' : 'requirement',
  )
  if (ok) {
    await reloadProjekt()
  }
}

const reloadProjekt = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchAnforderungen(store.selectedProjekt),
    store.fetchOwaspControls(store.selectedProjekt),
    store.fetchReifegrad(store.selectedProjekt),
    loadRiskCoverage(),
  ])
}

// #1081: Assistenten-Tab hat einen Wizard angewendet (z.B. Klassifikator
// ändert produktklasse, Branchen-Template setzt Pflicht-Doku-Defaults) —
// Projektliste + abgeleitete Daten neu laden.
const onAssistentenApplied = async () => {
  await store.fetchProjekte()
  await reloadProjekt()
}

// #886: Abdeckung „verknüpfte Risiken" pro Anforderung (rein informativ —
// filtert die Anforderungsliste NICHT). Spalte nur bei verknüpftem RB-Projekt.
const riskCoverage = ref<Record<string, number>>({})
const linkedRiskProjekt = ref<string | null>(null)
const coverageSummary = computed(() => {
  const ids = store.anforderungen.map((a: any) => String(a.id))
  const gesamt = ids.length
  const abgedeckt = ids.filter((id: string) => (riskCoverage.value[id] || 0) > 0).length
  return { abgedeckt, gesamt }
})
const loadRiskCoverage = async () => {
  riskCoverage.value = {}
  linkedRiskProjekt.value = null
  if (!store.selectedProjekt) return
  try {
    const { default: api } = await import('../../api/client')
    const r = await api.get(`/cra/projekte/${encodeURIComponent(store.selectedProjekt)}/risk-coverage`)
    linkedRiskProjekt.value = r.data?.linked_risk_projekt || null
    riskCoverage.value = r.data?.coverage || {}
  } catch {
    /* keine Verknüpfung / Fehler → keine Spalte, Liste bleibt vollständig */
  }
}

// ---- Aktionen-Saved-Handler (von RequirementActions) ----

const onActionSaved = async () => {
  editingReq.value = null
  await reloadProjekt()
}

const onOwaspActionSaved = async () => {
  editingOwasp.value = null
  if (store.selectedProjekt) {
    await store.fetchOwaspControls(store.selectedProjekt)
  }
}

watch(() => store.selectedProjekt, async (n) => {
  if (n) await reloadProjekt()
})

// OWASP-Modal: Form mit aktuellen Werten befüllen wenn Modal öffnet
watch(() => editingOwasp.value, (c) => {
  if (c) {
    owaspForm.value = {
      status: Number(c.score ?? c.status ?? 0),
      kommentar: c.kommentar || '',
      evidenceText: (c.evidence || []).map((e: any) =>
        typeof e === 'string' ? e : (e?.url || e?.path || JSON.stringify(e)),
      ).join('\n'),
    }
  }
})

onMounted(async () => {
  await Promise.all([
    store.fetchProjekte(),
    store.fetchConstants(),
  ])
  // Issue #435: Deep-Link via ?projekt=<name> aus FirmenView
  const proj = (route.query.projekt || '') as string
  if (proj) {
    store.selectedProjekt = proj
  }
  if (store.selectedProjekt) await reloadProjekt()
})
</script>

<style scoped>
.cra-view { max-width: 1400px; }

.header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header { display: flex; align-items: flex-end; gap: 16px; }
.header h2 { margin: 0; font-size: 22px; flex: 1; }
.header p { margin: 2px 0 0; color: #888; font-size: 13px; flex: 2; }
.help-btn {
  background: var(--color-background); color: var(--color-primary);
  border: 1px solid var(--color-border); padding: 6px 14px; border-radius: 4px;
  cursor: pointer; font-size: 14px;
}
.help-btn:hover { background: var(--color-border); }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350;
}

.empty-state, .form-card {
  background: white; padding: 32px; border-radius: 8px; border: 1px solid var(--color-border);
}
.empty-state { text-align: center; }
.empty-state h3 { margin: 0 0 12px; }
.empty-state p { color: #888; margin-bottom: 20px; }
.form-card { max-width: 600px; }
.form-card h3 { margin: 0 0 16px; }

.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input,
.form-row select,
.form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px;
}
.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.tabs {
  display: flex; gap: 2px; margin-bottom: 16px;
  border-bottom: 2px solid var(--color-border);
}

.project-bar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: var(--color-background);
  border: 1px solid var(--color-border); border-radius: 6px;
  margin-bottom: 12px;
}
.project-name { margin: 0; font-size: 16px; flex: 1; color: var(--color-text-primary); }
.project-company { font-weight: 400; color: var(--color-text-secondary); font-size: 13px; }
.btn-danger-mini {
  background: #ffebee; color: #c62828; border: 1px solid #ef5350;
  padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.btn-danger-mini:hover { background: #ffcdd2; }

.tab-btn {
  background: none; border: none; padding: 10px 18px;
  font-size: 14px; font-weight: 500; cursor: pointer;
  border-bottom: 3px solid transparent; color: #666;
}

.tab-btn.active {
  color: var(--color-primary); border-bottom-color: var(--color-primary);
  background: #f5f5f5;
}

.tab-content { padding: 8px 0; }

/* Dashboard */
.dashboard {
  display: grid; grid-template-columns: 280px 1fr; gap: 16px; margin-bottom: 16px;
}
.gauge-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 16px;
  display: flex; flex-direction: column; align-items: center;
}
.gauge-stats { margin-top: 12px; text-align: center; font-size: 12px; color: #666; }
.gauge-stats div { margin-bottom: 4px; }

.chapters-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px;
}

.owasp-status-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 16px; margin-bottom: 16px;
}
.owasp-status-card h3 { margin: 0 0 12px; font-size: 16px; }

.owasp-bar {
  display: flex; gap: 4px; margin-bottom: 8px;
}
.owasp-segment {
  flex: 1; padding: 8px;
  background: #f5f5f5; color: #999;
  text-align: center;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  border-radius: 4px;
}
.owasp-segment.evaluated {
  background: var(--color-primary); color: white;
}
.owasp-stats { font-size: 12px; color: #666; }

.luecken-section {
  background: white; border: 1px solid var(--color-border);
  border-radius: 6px; padding: 12px 16px;
}
.luecken-section h3 { margin: 0 0 8px; font-size: 14px; }

.luecken-list { display: flex; flex-direction: column; gap: 4px; }
.luecken-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  background: #fff8e1; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.luecken-item:hover { background: #fff3c4; }
.luecken-item code { background: white; padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.luecken-item strong { flex: 1; font-weight: 500; }
.luecken-meta { font-size: 11px; color: #666; }

/* Anforderungen */
.anf-toolbar {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
}
.search { flex: 1; min-width: 200px; padding: 6px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px; }
.filter { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; }
.info { color: #888; font-size: 12px; margin-left: auto; }

.anf-list {
  background: white; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden;
}
.anf-list table { width: 100%; border-collapse: collapse; font-size: 13px; }
.anf-list th {
  background: #f5f5f5; text-align: left; padding: 10px; font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}
.anf-list tbody tr { cursor: pointer; }
.anf-list tbody tr:hover { background: #f5f5f5; }
.anf-list td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; }
.title-cell { max-width: 400px; }

.score-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
}

.status-pill {
  padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
}
.status-pill.pending { background: #f3e5f5; color: #6a1b9a; }
.status-pill.partial { background: #fff3e0; color: #e65100; }
.status-pill.complete { background: #e8f5e9; color: #2e7d32; }

.quelle-tag {
  background: #e8f5e9; color: #2e7d32;
  padding: 2px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 600;
}

/* #886: Badge „verknüpfte Risiken" pro Anforderung */
.risk-badge {
  display: inline-block; min-width: 20px; text-align: center;
  background: #e3f2fd; color: #1565c0; border: 1px solid #90caf9;
  padding: 1px 7px; border-radius: 10px;
  font-size: 11px; font-weight: 700;
}
.risk-badge-empty { color: #bbb; font-size: 12px; }
.coverage-info {
  color: #1565c0; font-size: 12px; font-weight: 600;
  background: #e3f2fd; border: 1px solid #bbdefb;
  padding: 2px 8px; border-radius: 10px; margin-left: 8px;
}

/* OWASP */
.owasp-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;
}

.owasp-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 14px; cursor: pointer; transition: all 0.15s;
}
.owasp-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-color: var(--color-primary); }

.owasp-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
}
.owasp-id {
  background: #1565c0; color: white;
  padding: 3px 8px; border-radius: 3px;
  font-size: 11px; font-weight: 700; font-family: monospace;
}

.owasp-card h4 { margin: 0 0 8px; font-size: 14px; }

.owasp-desc {
  margin: 0 0 8px; font-size: 12px; color: #555; line-height: 1.4;
}

.owasp-meta {
  display: flex; justify-content: space-between; gap: 8px;
  font-size: 11px; color: #666; flex-wrap: wrap;
}

/* Action-Tabs (Fragebogen, Bericht) */
.action-card {
  background: white; padding: 24px; border-radius: 8px; border: 1px solid var(--color-border);
  max-width: 700px;
}
.action-card h3 { margin: 0 0 8px; }
.action-card p { color: #666; margin-bottom: 16px; }
.action-buttons { display: flex; gap: 12px; align-items: center; }
.action-buttons .hint { font-size: 12px; color: #888; }

.report-options {
  display: flex; flex-direction: column; gap: 8px;
  margin-bottom: 16px; padding: 12px;
  background: #f9f9f9; border-radius: 4px;
}
.checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; }

/* OWASP-Edit Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: white; border-radius: 8px;
  max-width: 700px; width: 95%; max-height: 90vh;
  display: flex; flex-direction: column;
}
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
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

.cra-mapping, .evidence-hint {
  background: #f9f9f9; padding: 8px 12px; border-radius: 4px;
  margin-bottom: 12px; font-size: 12px;
}

.score-display {
  display: inline-block; padding: 4px 12px; border-radius: 4px;
  color: white; font-weight: 600; min-width: 40px; text-align: center;
}

.suggestions { margin-top: 16px; }
.suggestions h4 { margin: 0 0 8px; font-size: 13px; }
.suggestion-card {
  background: #f9f9f9; border: 1px solid var(--color-border);
  border-radius: 4px; padding: 10px 12px; margin-bottom: 8px;
}
.sugg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.sugg-score { padding: 2px 10px; border-radius: 3px; color: white; font-size: 12px; font-weight: 600; }
.sugg-conf { font-size: 11px; color: #666; }
.suggestion-card p { margin: 0 0 6px; font-size: 12px; color: #333; }

.info {
  background: #fff8e1; color: #e65100; padding: 8px 12px;
  border-radius: 4px; font-size: 13px; border: 1px solid #ffd54f;
  margin: 12px 0;
}

.empty { padding: 40px; text-align: center; color: #888; }

.btn-primary, .btn-secondary, .btn-small {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
  text-decoration: none; display: inline-block;
}
.btn-primary { background: var(--color-primary); color: white; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-small {
  padding: 5px 10px; background: white;
  border: 1px solid var(--color-border); font-size: 12px;
}

/* OWASP-Editor: KI + Issues Sektionen */
.llm-section, .issues-section {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 10px 14px;
  margin-top: 16px;
  background: #f9f9f9;
}

.llm-section legend, .issues-section legend {
  padding: 0 6px;
  font-weight: 600;
  font-size: 12px;
  color: var(--color-primary);
  text-transform: uppercase;
}

.llm-buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.btn-llm {
  background: white;
  border: 1px solid #b3d4f5;
  color: #1565c0;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.btn-llm:hover:not(:disabled) {
  background: #1565c0;
  color: white;
}

.btn-llm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.muted {
  color: #888;
  font-size: 12px;
  font-style: italic;
}

.issues-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.issue-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: white;
  border-radius: 3px;
  font-size: 12px;
}

.issue-state {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
}

.issue-state.open { background: #e3f2fd; color: #1565c0; }
.issue-state.closed { background: #e8f5e9; color: #2e7d32; }

.issue-link {
  flex: 1;
  color: #333;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.issue-link:hover { text-decoration: underline; color: var(--color-primary); }

.btn-tiny {
  background: none;
  border: 1px solid #ddd;
  width: 22px;
  height: 22px;
  border-radius: 3px;
  cursor: pointer;
  color: #888;
  font-size: 12px;
}

.btn-tiny:hover { background: #ffebee; color: #c62828; border-color: #c62828; }

.modal-overlay.nested {
  z-index: 1100;
}

.prompt-modal {
  max-width: 800px;
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

.preview a { color: #2e7d32; }
.preview pre { white-space: pre-wrap; font-size: 12px; max-height: 200px; overflow-y: auto; }

.form-row small {
  display: block;
  font-size: 11px;
  color: #888;
  margin-top: 2px;
}

@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; }
}
</style>
