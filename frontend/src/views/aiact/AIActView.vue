<template>
  <ModuleShell
    class="aiact-view"
    :title="$t('aiact.aIActView.eUAIActCompliance')"
    :subtitle="$t('aiact.aIActView.verordnungEUAnforderungenInKapitelnO')"
    module-name="aiact"
    :tabs="store.selectedProjektObj ? visibleTabs : []"
    :groups="store.selectedProjektObj ? visibleNavGroups : []"
    persist-key="aiact"
    v-model="activeTab"
  >
    <HelpDialog
      :open="helpOpen"
      :title="$t('aiact.aIActView.eUAIActErlauterungDerKapitel')"
      subtitle="Verordnung (EU) 2024/1689 — EU AI Act"
      header-bg="#1565c0"
      :kapitel="constants?.kapitel"
      :bewertung-skala="constants?.bewertung_skala"
      @close="helpOpen = false"
    />

    <FehlerHinweis :text="store.error" @close="store.error = ''" />

    <div v-if="!store.selectedProjektObj" class="empty-state">
      <h3>{{ store.projekte.length === 0 ? $t('aiact.aIActView.nochKeineAIActBewertungen') : $t('aiact.aIActView.firmaWahlen') }}</h3>
      <p v-if="store.projekte.length === 0">
        {{ $t('aiact.aIActView.aIActIst') }} <strong>{{ $t('aiact.aIActView.organisationsUndSystembezogen') }}</strong>{{ $t('aiact.aIActView.jeFirmaEineOrganisationsBewertungFir') }}
      </p>
      <p v-else>{{ $t('common.wahleLinksEineFirmaAusDerSid') }}</p>
      <router-link to="/firmen" class="btn-primary">{{ $t('common.zurFirmenverwaltung') }}</router-link>
    </div>

    <!-- Projekt-Leiste (ModuleShell #project-bar) -->
    <template v-if="store.selectedProjektObj" #project-bar>
      <h3 class="project-name">{{ store.selectedProjektObj.name }}</h3>
      <!-- #1543: Scope-Badge + KI-System anlegen (hybrides Modell, Epic #1540) -->
      <span v-if="isSystem" class="scope-badge system"
            :title="`KI-System der Firma ${scopeInfo?.firma || ''} — firmenweite Bereiche (AI-Literacy) kommen aus der Organisation ${scopeInfo?.org_projekt || ''}`">
        {{ $t('aiact.aIActView.kISystemV0', { v0: store.selectedProjektObj.produkt || store.selectedProjektObj.name }) }}
      </span>
      <span v-else class="scope-badge org"
            :title="`Organisations-Bewertung — ${scopeInfo?.systeme.length || 0} KI-System(e) angelegt`">
        {{ $t('aiact.aIActView.organisationV0KISystemE', { v0: scopeInfo?.systeme.length || 0 }) }}
      </span>
      <FirmaSelector
        :model-value="(store.selectedProjektObj as any)?.organisation || (store.selectedProjektObj as any)?.unternehmen || ''"
        :saving="reassignSaving"
        :success-text="reassignMsg.ok"
        :error-text="reassignMsg.err"
        @save="onReassignFirma"
      />
      <!-- #1851: die sieben projektweiten Handlungen aus der geteilten
           Werkzeugleiste. Die Massenbewertung ist mitgewandert — sie gilt dem
           Projekt und war vorher nur aus dem Anforderungs-Tab erreichbar.

           Bei einer **gesperrten Organisation** (#1562: ≥ 1 KI-System angelegt,
           die Register werden dort gepflegt) zeigt die Leiste nur die drei
           lesenden Handlungen (`nur-lesend`). Vier der sieben liefen dort in
           den 409 des `before_request`-Guards — `allowed_suffixes` kennt nur
           `''`, `systeme`, `repo-config` und `issues/sync` —, und ein
           sichtbarer Knopf vor einem 409 ist derselbe Defekt wie ein Knopf
           ohne Route (#1846/#1805). Umgekehrt die Leiste ganz wegzulassen
           nähme dem Anwender den Abgleich, die Neubewertungs-Übersicht und
           das Audit-Log, die er dort haben darf. -->
      <ProjektWerkzeugleiste
        api-base="/aiact"
        :projekt-name="store.selectedProjekt || ''"
        :mass-adapter="reqAdapter"
        :objekt-wort="$t('geteilt.projektWerkzeugleiste.anforderungen')"
        :wert-wort="$t('geteilt.projektWerkzeugleiste.bewertungenWort')"
        :nur-lesend="orgLocked"
        @reload="reloadProjekt"
      >
        <template #eigene>
          <button class="btn-secondary" @click="openSystemDialog"
                  :title="$t('aiact.aIActView.eigeneAIActBewertungFurEinKISystemPr')">{{ $t('aiact.aIActView.kISystemAnlegen') }}</button>
          <button class="btn-danger-mini" @click="confirmDeleteProjekt"
                  :title="$t('common.projektLoschen2')">{{ $t('common.projektLoschen') }}</button>
        </template>
      </ProjektWerkzeugleiste>
    </template>

    <!-- Repo-Konfiguration pro Projekt (#862) -->
    <template v-if="store.selectedProjektObj && store.selectedProjekt" #repo-config>
      <RepoConfigPanel
        :api-base="'/aiact'"
        :projekt-name="store.selectedProjekt"
      />
    </template>

    <template v-if="store.selectedProjektObj">
      <!-- Tab: Dashboard — einheitlich (#1250) -->
      <div v-if="activeTab === 'dashboard' && orgLocked" class="tab-content">
        <AIActSystemOverview :firma="scopeInfo?.firma || ''" :systeme="scopeInfo?.systeme || []"
                             @open="(n: string) => { store.selectedProjekt = n }" />
      </div>
      <div v-else-if="activeTab === 'dashboard'" class="tab-content">
        <ModuleDashboard
          :gesamt="{ percent: dashboardGesamtPct, ampel: store.reifegrad?.ampel }"
          :gesamt-stats="dashboardStats"
          :bereiche="dashboardBereiche"
          :offene-punkte="dashboardLuecken"
          :schwelle="dashboardSchwelle"
          :dok-fertig="dokFertig"
          :dok-gesamt="dokGesamt"
          :risiko="risiko"
          :risiko-loading="risikoLoading"
          @open-bereich="(id) => { activeTab = 'anforderungen'; filterKapitel = id }"
          @open-luecken="activeTab = 'anforderungen'"
          @open-punkt="(id) => { activeTab = 'anforderungen'; openAnforderung(id) }"
          @open-dokumente="activeTab = 'dokumente'"
          @open-risiken="openRisikoCockpit"
        />
      </div>

      <!-- Tab: Pflicht-Doku -->
      <div v-if="activeTab === 'pflichtdoku'" class="tab-content">
        <AIActPflichtDokuPanel />
      </div>

      <!-- Tab: OWASP-LLM-Register (#1087) -->
      <div v-if="activeTab === 'owasp-llm'" class="tab-content">
        <OwaspLlmPanel />
      </div>

      <!-- Tab: Art. 5 Verbots-Screening (#1206) -->
      <div v-if="activeTab === 'art5'" class="tab-content">
        <Art5ScreeningPanel />
      </div>

      <!-- Tab: Art. 4 AI-Literacy (#1199) -->
      <div v-if="activeTab === 'literacy'" class="tab-content">
        <LiteracyPanel />
      </div>

      <!-- Tab: Änderungsverwaltung je KI-System (Art. 43 Abs. 4, #1756) -->
      <div v-if="activeTab === 'aenderungen'" class="tab-content">
        <AenderungenPanel @goto="(t: string) => activeTab = t" />
      </div>

      <!-- Tab: Art. 73 Serious-Incident-Register (#1197) -->
      <div v-if="activeTab === 'incidents'" class="tab-content">
        <IncidentsPanel />
      </div>

      <!-- Tab: Art. 27 FRIA-Workflow (#1196) -->
      <div v-if="activeTab === 'fria'" class="tab-content">
        <FriaPanel />
      </div>

      <!-- Tab: Art. 43/48 Konformität + CE (#1198) -->
      <div v-if="activeTab === 'conformity'" class="tab-content">
        <ConformityPanel />
      </div>

      <!-- Tab: Art. 51-55 GPAI-Modell (#1195) -->
      <div v-if="activeTab === 'gpai'" class="tab-content">
        <GpaiPanel />
      </div>

      <!-- Tab: Assistenten (#1082) -->
      <div v-if="activeTab === 'assistenten'" class="tab-content">
        <AIActAssistentenTab @open-in-register="activeTab = 'dokumente'" />
      </div>

      <!-- Tab: Dokumente (Sprint #24) -->
      <div v-if="activeTab === 'dokumente'" class="tab-content">
        <DokumenteRegister
          :modul="'aiact'"
          :projekt="store.selectedProjekt"
          @open-assistent="activeTab = 'assistenten'"
        />
      </div>

      <!-- Tab: Risiko-Cockpit (#1082) -->
      <div v-if="activeTab === 'cockpit'" class="tab-content">
        <div v-if="cockpitLoading" class="cockpit-hint">{{ $t('aiact.aIActView.ladeRisikoCockpit') }}</div>
        <RiskCockpit v-else-if="cockpitFirmenId != null" :firmen-id="cockpitFirmenId" />
        <div v-else class="cockpit-hint">
          {{ $t('common.projektKeinerFirmaZugeordnet') }}
        </div>
      </div>

      <!-- Tab: Bericht (B2 #1093) -->
      <div v-if="activeTab === 'berichte'" class="tab-content">
        <!-- Sprint #35: einheitliches Berichts-Center (Vorbild SOC/CRA) -->
        <ReportCenterPanel
          v-if="store.selectedProjekt"
          :api-base="`/aiact/projekte/${encodeURIComponent(store.selectedProjekt)}`"
          :title="$t('aiact.aIActView.aIActBerichtsCenter')"
        />
      </div>

      <!-- Tab: Anforderungen -->
      <div v-if="activeTab === 'anforderungen'" class="tab-content">
        <!-- Toolbar -->
        <div class="anf-toolbar">
          <input v-model="searchQuery" :placeholder="$t('common.anforderungenDurchsuchen')" class="search" />
          <select v-model="filterKapitel" class="filter">
            <option value="">{{ $t('common.alleKapitel') }}</option>
            <option v-for="k in chapters" :key="k" :value="k">{{ k }} – {{ chapterTitle(k) }}</option>
          </select>
          <select v-model="filterStatus" class="filter">
            <option value="all">{{ $t('common.alle') }}</option>
            <option value="pending">{{ $t('common.ausstehend') }}</option>
            <option value="partial">{{ $t('common.teilweise') }}</option>
            <option value="complete">{{ $t('common.vollstaendig') }}</option>
          </select>
          <button class="btn-secondary" @click="repoScanOpen = true">{{ $t('aiact.aIActView.repoScan') }}</button>
          <!-- Die Massenbewertung steht seit #1851 in der Projekt-Leiste, in
               allen sechs Modulen an derselben Stelle. -->
          <DownloadButton :endpoint="stripApi(exportUrl('md'))" class="export-btn">{{ $t('aiact.aIActView.markdown') }}</DownloadButton>
          <ImportButton
            v-if="store.selectedProjekt"
            variant="secondary"
            :endpoint="`/aiact/projekte/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
            label="⬆️ Import"
            @imported="onImported"
          />
        </div>

        <!-- Anforderungs-Liste -->
        <div class="anf-list">
          <!-- #2062 -->
          <div v-if="visible.length > 0" class="tabelle-scroll">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>{{ $t('common.kapitel') }}</th>
                <th>{{ $t('common.titel') }}</th>
                <th>{{ $t('aiact.aIActView.oWASPLLM') }}</th>
                <th>{{ $t('common.bewertung') }}</th>
                <th>{{ $t('common.status') }}</th>
                <th>{{ $t('common.gewichtung') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in visible" :key="r.id" @click="editingReq = r">
                <td><code>{{ r.id }}</code></td>
                <td>{{ r.kapitel }}</td>
                <td class="title-cell">{{ r.titel }}<NeubewertungBadge :text="r.kommentar" modul="aiact"
                  :projekt="store.selectedProjekt" objekt-pfad="anforderungen"
                  :objekt-id="r.id" @bestaetigt="reloadProjekt()" /></td>
                <td>
                  <div class="llm-badges">
                    <span v-for="risk in r.owasp_llm" :key="risk.id"
                          :title="risk.title" class="llm-badge">
                      {{ risk.id }}
                    </span>
                  </div>
                </td>
                <td>
                  <span class="score-pill" :style="{ background: scoreColor(r.bewertung) }">
                    {{ r.bewertung }}
                  </span>
                </td>
                <td><span :class="['status-pill', r.status]">{{ statusLabel(r.status) }}</span></td>
                <td>{{ r.gewichtung }}</td>
              </tr>
            </tbody>
          </table>
          </div>
          <div v-else class="empty">{{ $t('common.keineAnforderungenZumFilter') }}</div>
        </div>
      </div>
    </template>

    <template #modals>
      <!-- Editor (shared) -->
      <RequirementEditor
        v-if="editingReq"
        :requirement="editingReq"
        @save="onSaveBewertung"
        @cancel="editingReq = null"
      >
        <template #actions>
          <!-- #1561: Art. 9 — Nachweis über verknüpfte Risikobewertung -->
          <Hr01RiskLinkBox v-if="editingReq.id === 'AIA-HR-01'" @saved="onActionSaved" />
          <RequirementActions
            :requirement="editingReq"
            :projekt-name="store.selectedProjekt || ''"
            api-base="/aiact"
            :default-repo="defaultRepoFromMeta"
            @saved="onActionSaved"
            @error="(msg: string) => store.error = msg"
          />
        </template>
      </RequirementEditor>

      <!-- Repo-Scan-Dialog -->
      <div v-if="repoScanOpen" class="modal-overlay" @mousedown.self="repoScanOpen = false">
        <div class="modal-content">
          <h3>{{ $t('aiact.aIActView.repositoryScan') }}</h3>
          <p class="hint">{{ $t('aiact.aIActView.scanntEinGitHubRepositoryAufSicherhe') }}</p>
          <div class="form-row">
            <label>{{ $t('aiact.aIActView.repositoryOptional') }}</label>
            <input v-model="repoInput.repo" :placeholder="$t('aiact.aIActView.leerLassenImProjektHinterlegtesRepos')" />
            <small class="hint">{{ $t('aiact.aIActView.leerDasInDerRepoKonfigurationDiesesP') }}</small>
          </div>
          <div class="form-row">
            <label>{{ $t('aiact.aIActView.branchOptional') }}</label>
            <input v-model="repoInput.branch" placeholder="main" />
          </div>
          <div v-if="scanLoading" class="info">{{ $t('aiact.aIActView.scanLauftKannDauern') }}</div>

          <div v-if="store.repoSuggestions.length > 0" class="suggestions">
            <h4>{{ $t('aiact.aIActView.v0Vorschlage', { v0: store.repoSuggestions.length }) }}</h4>
            <div v-for="s in store.repoSuggestions" :key="s.field_id" class="suggestion-card">
              <div class="sugg-header">
                <code>{{ s.field_id }}</code>
                <span class="sugg-score" :style="{ background: scoreColor(s.score) }">
                  {{ $t('aiact.aIActView.vorschlagV0', { v0: s.score }) }}
                </span>
                <span class="sugg-conf">{{ $t('aiact.aIActView.konfidenzV0', { v0: Math.round(s.confidence * 100) }) }}</span>
              </div>
              <p>{{ s.kommentar }}</p>
              <details v-if="s.rationale">
                <summary>{{ $t('aiact.aIActView.rationale') }}</summary>
                <pre>{{ s.rationale }}</pre>
              </details>
              <button class="btn-small" @click="acceptSuggestion(s)">{{ $t('common.uebernehmen') }}</button>
            </div>
          </div>

          <div class="modal-actions">
            <button class="btn-secondary" @click="repoScanOpen = false">{{ $t('common.close') }}</button>
            <button class="btn-primary" @click="onRunScan" :disabled="scanLoading">
              {{ scanLoading ? $t('aiact.aIActView.ladt') : $t('aiact.aIActView.scanStarten') }}
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- #1543: KI-System anlegen -->
    <div v-if="systemDialog.open" class="modal-overlay" @mousedown.self="systemDialog.open = false">
      <div class="modal-content">
        <h3>{{ $t('aiact.aIActView.kISystemAnlegen') }}</h3>
        <p class="hint">
          {{ $t('aiact.aIActView.eigeneAIActBewertungFurEinKISystemDe') }} <strong>{{ scopeInfo?.firma }}</strong>
          {{ $t('aiact.aIActView.nameV0LtProduktGtRisikoklasseArtFRIA', { v0: scopeInfo?.firma }) }}
        </p>
        <div v-if="scopeInfo?.firmen_produkte.length" class="form-row">
          <label>{{ $t('aiact.aIActView.produktAusDerFirmenverwaltung') }}</label>
          <select v-model="systemDialog.produkt">
            <option value="">{{ $t('aiact.aIActView.freiEingeben') }}</option>
            <option v-for="fp in scopeInfo.firmen_produkte" :key="fp.name" :value="fp.name" :disabled="fp.angelegt">
              {{ fp.name }}{{ fp.angelegt ? $t('aiact.aIActView.bereitsAngelegt') : '' }}
            </option>
          </select>
        </div>
        <div class="form-row">
          <label>{{ $t('aiact.aIActView.produktKISystem') }}</label>
          <input v-model="systemDialog.produkt" placeholder="z. B. Support-Chatbot" />
        </div>
        <div class="form-row">
          <label>{{ $t('aiact.aIActView.beschreibungZweckbestimmung') }}</label>
          <textarea v-model="systemDialog.beschreibung" rows="3"
                    :placeholder="$t('aiact.aIActView.wofurWirdDasKISystemEingesetztGrundl')" />
        </div>
        <!-- #1562: beim ersten KI-System die bisherigen Bewertungen der Organisation übernehmen -->
        <label v-if="!scopeInfo?.systeme.length && scopeInfo?.org_has_data" class="check-row">
          <input type="checkbox" v-model="systemDialog.uebernehmen" />
          {{ $t('aiact.aIActView.bestehendeBewertungenDerOrganisation') }}
          <small class="hint">{{ $t('aiact.aIActView.anforderungenRegisterVorfalleSowieRi') }}</small>
        </label>
        <p v-if="!scopeInfo?.systeme.length" class="hint">
          {{ $t('aiact.aIActView.mitDemErstenKISystemFuhrtDieOrganisa') }}
        </p>
        <FehlerHinweis :text="systemDialog.error" @close="systemDialog.error = ''" />
        <div class="modal-actions">
          <button class="btn-secondary" @click="systemDialog.open = false">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="onCreateSystem" :disabled="systemDialog.busy || !systemDialog.produkt.trim()">
            {{ systemDialog.busy ? $t('aiact.aIActView.legeAn') : $t('aiact.aIActView.anlegenOffnen') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Die beiden Massenbewertungs-Dialoge öffnet die Werkzeugleiste selbst. -->
  </ModuleShell>
</template>

<script setup lang="ts">
import DownloadButton from '../../components/shared/DownloadButton.vue'
import NeubewertungBadge from '../../components/shared/NeubewertungBadge.vue'

const stripApi = (u: string): string => u.replace(/^\/api/, '')
import { ref, computed, onMounted, watch } from 'vue'
import { useProjektLader } from '../../composables/useProjektLader'
import { useAiActStore, type AIActScope } from '../../stores/aiact'
import { useFirmenStore } from '../../stores/firmen'
import { useRoute } from 'vue-router'
import FirmaSelector from '../../components/shared/FirmaSelector.vue'
import ModuleDashboard from '../../components/shared/ModuleDashboard.vue'
import type { DashboardStat } from '../../components/shared/ModuleDashboard.vue'
import { useModuleDashboard } from '../../composables/useModuleDashboard'
import RequirementEditor from '../../components/shared/RequirementEditor.vue'
import RequirementActions from '../../components/shared/RequirementActions.vue'
import ProjektWerkzeugleiste from '../../components/shared/ProjektWerkzeugleiste.vue'
import { requirementAdapter } from '../../utils/massAdapters'
import ImportButton from '../../components/shared/ImportButton.vue'
import HelpDialog from '../../components/shared/HelpDialog.vue'
import ModuleShell from '../../components/shared/ModuleShell.vue'
import ReportCenterPanel from '../../components/shared/ReportCenterPanel.vue'
import apiClient from '../../api/client'
import AIActPflichtDokuPanel from './AIActPflichtDokuPanel.vue'
import OwaspLlmPanel from './OwaspLlmPanel.vue'
import Art5ScreeningPanel from './Art5ScreeningPanel.vue'
import LiteracyPanel from './LiteracyPanel.vue'
import Hr01RiskLinkBox from './Hr01RiskLinkBox.vue'
import AIActSystemOverview from './AIActSystemOverview.vue'
import IncidentsPanel from './IncidentsPanel.vue'
import AenderungenPanel from './AenderungenPanel.vue'
import FriaPanel from './FriaPanel.vue'
import ConformityPanel from './ConformityPanel.vue'
import GpaiPanel from './GpaiPanel.vue'
import AIActAssistentenTab from './AIActAssistentenTab.vue'
import DokumenteRegister from '../shared/DokumenteRegister.vue'
import RiskCockpit from '../shared/RiskCockpit.vue'
import RepoConfigPanel from '../../components/RepoConfigPanel.vue'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'

const store = useAiActStore()
const firmenStore = useFirmenStore()
const route = useRoute()
const helpOpen = ref(false)

// Abgleich, Übernahme und Stapel-Anlage am Projekt kommen seit #1851 aus
// `ProjektWerkzeugleiste`. Zwei Dinge sind dabei weggefallen: die
// `alert()`-Fenster, die den Browser anhielten, bevor man das Ergebnis in der
// Liste ansehen konnte — und das fest mitgeschickte `provider: 'github'` der
// Stapel-Anlage. Das war hier als einzigem Modul so und überstimmte ein
// Projekt, das auf GitLab konfiguriert ist; den Provider löst jetzt der
// Server aus der Repo-Konfiguration auf (`shared.issue_api.loese_repo`).

const tabs = [
  { id: 'dashboard', label: uebersetze('common.dashboard') },
  { id: 'pflichtdoku', label: uebersetze('common.dokumentation') },
  { id: 'cockpit', label: uebersetze('common.risikoCockpit') },
  { id: 'anforderungen', label: uebersetze('common.anforderungen') },
  { id: 'art5', label: '🚫 Art. 5 Verbote' },
  { id: 'literacy', label: uebersetze('aiact.aIActView.aILiteracy') },
  { id: 'aenderungen', label: uebersetze('aiact.aIActView.anderungen') },
  { id: 'incidents', label: uebersetze('aiact.aIActView.artVorfalle') },
  { id: 'fria', label: '⚖️ Art. 27 FRIA' },
  { id: 'conformity', label: uebersetze('aiact.aIActView.artKonformitat') },
  { id: 'gpai', label: '🧠 Art. 51-55 GPAI' },
  { id: 'owasp-llm', label: uebersetze('aiact.aIActView.oWASPLLM') },
  { id: 'assistenten', label: uebersetze('common.assistenten') },
  { id: 'dokumente', label: uebersetze('common.dokumente') },
  { id: 'berichte', label: uebersetze('common.berichte') },
]

// Gruppierte Navigation (Sprint #34, #1373) — gemeinsame Taxonomie
const navGroups = [
  { id: 'ueberblick', label: uebersetze('common.uberblick'), tabs: [
    { id: 'dashboard', label: uebersetze('common.dashboard') },
    { id: 'cockpit', label: uebersetze('common.risikoCockpit') },
  ] },
  { id: 'register', label: uebersetze('common.complianceRegister'), tabs: [
    { id: 'anforderungen', label: uebersetze('common.anforderungen') },
    { id: 'art5', label: '🚫 Art. 5 Verbote' },
    { id: 'fria', label: '⚖️ Art. 27 FRIA' },
    { id: 'conformity', label: uebersetze('aiact.aIActView.artKonformitat') },
    { id: 'gpai', label: '🧠 Art. 51-55 GPAI' },
    { id: 'owasp-llm', label: uebersetze('aiact.aIActView.oWASPLLM') },
  ] },
  // #1756: Die Änderungsverwaltung gehört in den Tagesbetrieb und nicht zu den
  // Registern: Sie ist kein einmalig herzustellender Zustand, sondern der
  // wiederkehrende Vorgang bei jeder Änderung am System — fachlich dasselbe
  // Fach wie die Vorfallmeldung, mit der sie sich auch den Rechenweg teilt
  // (Art. 73 als Prüfpunkt). Deshalb hier und **kein neues Menü**.
  { id: 'tagesbetrieb', label: uebersetze('common.tagesbetrieb'), tabs: [
    { id: 'aenderungen', label: uebersetze('aiact.aIActView.anderungen') },
    { id: 'incidents', label: uebersetze('aiact.aIActView.artVorfalle') },
  ] },
  { id: 'doku', label: uebersetze('common.dokumentation2'), tabs: [
    { id: 'pflichtdoku', label: uebersetze('common.dokumentation') },
    { id: 'literacy', label: uebersetze('aiact.aIActView.aILiteracy') },
    { id: 'dokumente', label: uebersetze('common.dokumente') },
    { id: 'assistenten', label: uebersetze('common.assistenten') },
  ] },
  { id: 'berichte', label: uebersetze('common.berichte2'), tabs: [
    { id: 'berichte', label: uebersetze('common.berichte') },
  ] },
]
const activeTab = ref<string>('dashboard')
// #1573/#1851: ein Adapter für beide Massenbewertungen — die Dialoge dazu
// öffnet die Projekt-Werkzeugleiste.
const reqAdapter = computed(() => requirementAdapter('/aiact', store.selectedProjekt || '', store.anforderungen))
const constants = ref<any | null>(null)

// #1250: einheitliches Dashboard
const { dokFertig, dokGesamt, risiko, risikoLoading, loadAll: loadDashboardExtras } =
  useModuleDashboard('aiact')
const loadConstants = async () => {
  if (constants.value) return
  try {
    const res = await apiClient.get('/aiact/constants')
    constants.value = res.data
  } catch { /* ignore */ }
}

// Risiko-Cockpit-Auflösung (#1082): Projekt → Firma
const cockpitFirmenId = ref<number | null>(null)
const cockpitLoading = ref(false)
const resolveCockpit = async () => {
  cockpitFirmenId.value = null
  if (!store.selectedProjekt) return
  cockpitLoading.value = true
  try {
    const res = await apiClient.get(
      '/risk-cockpit/by-projekt/aiact/' + encodeURIComponent(store.selectedProjekt),
    )
    const d = res.data || {}
    cockpitFirmenId.value = d.unassigned ? null : (d.firmen_id ?? null)
  } catch {
    cockpitFirmenId.value = null
  } finally {
    cockpitLoading.value = false
  }
}
watch([activeTab, () => store.selectedProjekt], ([tab]) => {
  if (tab === 'cockpit') resolveCockpit()
})

const confirmDeleteProjekt = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`AI-Act-Projekt "${store.selectedProjekt}" wirklich löschen?\n\nAlle Bewertungen gehen verloren.`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const onImported = async () => {
  if (!store.selectedProjekt) return
  await store.fetchAnforderungen(store.selectedProjekt)
  await store.fetchReifegrad(store.selectedProjekt)
}

const creating = ref(false)
const newForm = ref({ name: '', organisation: '', produkt: '', beschreibung: '' })
const editingReq = ref<any | null>(null)

const defaultRepoFromMeta = computed(() => {
  try {
    const meta = JSON.parse(store.selectedProjektObj?.meta || '{}')
    return meta?.linked_app?.repo?.replace('https://github.com/', '') || ''
  } catch {
    return ''
  }
})

const repoScanOpen = ref(false)
const scanLoading = ref(false)
const repoInput = ref({ repo: '', branch: '' })

const searchQuery = ref('')
const filterKapitel = ref('')
const filterStatus = ref<'all' | 'pending' | 'partial' | 'complete'>('all')

const KAPITEL_TITEL: Record<string, string> = {
  HR: uebersetze('aiact.aIActView.highRiskRequirements'),
  GOV: uebersetze('aiact.aIActView.governance'),
  DATA: uebersetze('aiact.aIActView.datenGovernance'),
  OPS: uebersetze('aiact.aIActView.operationsPostMarket'),
}

const chapterTitle = (k: string): string => KAPITEL_TITEL[k] || k

const chapters = computed(() => {
  const set = new Set<string>()
  for (const a of store.anforderungen) set.add(a.kapitel)
  return Array.from(set).sort()
})

const kapitelStats = computed(() => {
  const stats: Record<string, { bewertet: number; gesamt: number }> = {}
  for (const a of store.anforderungen) {
    if (!stats[a.kapitel]) stats[a.kapitel] = { bewertet: 0, gesamt: 0 }
    stats[a.kapitel].gesamt++
    if (a.bewertung > 0) stats[a.kapitel].bewertet++
  }
  return stats
})

// #1250: AI-Act-Reifegrad (gesamt_pct/kapitel_pct/ampel) → einheitliche Dashboard-Props
const dashboardGesamtPct = computed(() => Number(store.reifegrad?.gesamt_pct ?? 0))
// #2041: Schlüssel + Werte statt fertiger Sätze.
const dashboardStats = computed<DashboardStat[]>(() => [
  { key: 'geteilt.moduleDashboard.statBewertet',
    werte: { v0: store.reifegrad?.bewertete_count ?? 0,
             v1: store.reifegrad?.gesamt_count ?? store.anforderungen.length } },
  { key: 'geteilt.moduleDashboard.statAnforderungen', werte: { v0: store.anforderungen.length } },
])
const dashboardBereiche = computed(() =>
  Object.entries(store.reifegrad?.kapitel_pct || {}).map(([kapitel, pct]: [string, any]) => ({
    id: kapitel,
    title: chapterTitle(kapitel),
    percent: Number(pct ?? 0),
    bewertet: kapitelStats.value[kapitel]?.bewertet ?? 0,
    gesamt: kapitelStats.value[kapitel]?.gesamt ?? 0,
  })),
)
const dashboardLuecken = computed(() =>
  store.anforderungen
    .filter((a: any) => Number(a.bewertung ?? 0) < 5)
    .map((a: any) => ({ id: a.id, titel: a.titel, bewertung: Number(a.bewertung ?? 0) }))
    .sort((x, y) => x.bewertung - y.bewertung),
)

/** #2066: Die Schwelle, mit der der Server gerechnet hat — nicht geraten. */
const dashboardSchwelle = computed(() => store.reifegrad?.luecken_schwelle ?? 4)
const openAnforderung = (id: string) => {
  const r = store.anforderungen.find((a: any) => a.id === id)
  if (r) editingReq.value = r
}

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

const SCORE_COLORS = ['#9e9e9e', '#c62828', '#e65100', '#f57f17', '#558b2f', '#2e7d32']
const scoreColor = (s: number) => SCORE_COLORS[s] || '#9e9e9e'

const statusLabel = (s: string): string => {
  if (s === 'complete') return uebersetze('common.vollstaendig')
  if (s === 'partial') return uebersetze('common.teilweise')
  return uebersetze('common.ausstehend')
}

const exportUrl = (fmt: string): string => {
  if (!store.selectedProjekt) return '#'
  return `/api/aiact/projekte/${encodeURIComponent(store.selectedProjekt)}/report?format=${fmt}`
}

const startNew = () => {
  newForm.value = { name: '', organisation: '', produkt: '', beschreibung: '' }
  creating.value = true
  if (firmenStore.firmen.length === 0) firmenStore.fetchFirmen()
}

// Issue #436: Firma des Projekts nachtraeglich aendern
// AI Act nutzt 'organisation' statt 'unternehmen' als Spalten-Name
const reassignSaving = ref(false)
const reassignMsg = ref<{ ok: string; err: string }>({ ok: '', err: '' })
const onReassignFirma = async (newFirma: string) => {
  if (!store.selectedProjekt) return
  reassignSaving.value = true
  reassignMsg.value = { ok: '', err: '' }
  try {
    await store.updateProjekt(store.selectedProjekt, { organisation: newFirma } as any)
    await store.fetchProjekte()
    reassignMsg.value.ok = newFirma ? `✓ Firma geändert auf „${newFirma}"` : uebersetze('common.firmenzuordnungEntfernt')
    setTimeout(() => { reassignMsg.value = { ok: '', err: '' } }, 4000)
  } catch (e: any) {
    reassignMsg.value.err = e?.response?.data?.error || uebersetze('common.fehlerBeimSpeichern')
  } finally {
    reassignSaving.value = false
  }
}

const onCreate = async () => {
  if (!newForm.value.name.trim()) {
    store.error = uebersetze('common.projektnameIstPflicht')
    return
  }
  const result = await store.createProjekt(newForm.value)
  if (result) {
    store.selectedProjekt = result.name
    creating.value = false
    await reloadProjekt()
  }
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

const onRunScan = async () => {
  if (!store.selectedProjekt) return
  // #1065: leeres Repo erlaubt → Backend nutzt das im Projekt hinterlegte Repository
  scanLoading.value = true
  await store.repoScan(store.selectedProjekt, repoInput.value.repo, repoInput.value.branch)
  scanLoading.value = false
}

const acceptSuggestion = async (s: any) => {
  if (!store.selectedProjekt) return
  const ok = await store.saveBewertung(store.selectedProjekt, s.field_id, {
    bewertung: s.score,
    kommentar: s.kommentar,
  })
  if (ok) {
    store.repoSuggestions = store.repoSuggestions.filter(x => x.field_id !== s.field_id)
    await store.fetchAnforderungen(store.selectedProjekt)
    await store.fetchReifegrad(store.selectedProjekt)
  }
}

/**
 * #2025/#2044: Entprellt und gegen Überholer gesichert. Diese Funktion
 * wurde aus 6 Stellen gerufen und startete je Lauf mehrere
 * parallele Lader — ein Tab-Wechsel, ein gespeicherter Wert und ein
 * geschlossenes Modal in derselben Sekunde ergaben drei vollständige
 * Ladungen. Gemessen: 37 Schwälle an einem Tag, der größte mit 56
 * Anfragen in 4 Sekunden, darin dieselbe Anfrage bis zu 4×.
 */
const _ladeProjekt = async (_projekt: string) => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchAnforderungen(store.selectedProjekt),
    store.fetchReifegrad(store.selectedProjekt),
    loadDashboardExtras(store.selectedProjekt),
  ])
}

const _lader = useProjektLader(_ladeProjekt)
const reloadProjekt = () => _lader.nachladen(store.selectedProjekt)

watch(() => store.selectedProjekt, async (n) => {
  if (n) await reloadProjekt()
})

// #1541/#1543: hybrides Modell — Organisation + KI-Systeme (Epic #1540)
const scopeInfo = ref<AIActScope | null>(null)
const isSystem = computed(() => (store.selectedProjektObj as any)?.scope === 'system')
async function loadScope() {
  scopeInfo.value = store.selectedProjekt ? await store.fetchScope(store.selectedProjekt) : null
}
watch(() => store.selectedProjekt, loadScope, { immediate: true })

const systemDialog = ref({ open: false, produkt: '', beschreibung: '', busy: false, error: '', uebernehmen: true })
async function openSystemDialog() {
  await loadScope()
  systemDialog.value = { open: true, produkt: '', beschreibung: '', busy: false, error: '', uebernehmen: true }
}

// #1562: Organisation mit KI-Systemen → nur firmenweite Tabs
const ORG_TABS = new Set(['dashboard', 'cockpit', 'literacy', 'dokumente', 'berichte'])
const orgLocked = computed(() => !isSystem.value && !!scopeInfo.value?.locked)
// Scope-abhängige Sichtbarkeit — zwei Regeln in einer Stelle:
// #1569: Risiko-Cockpit nur auf Firmenebene (Organisation), nicht je KI-System.
// #1756: Die Änderungsverwaltung umgekehrt nur je KI-System — Bezugseinheit des
//        Art. 43 Abs. 4 ist das System, nicht die Organisation. In einer
//        gesperrten Organisation (#1562) greift ohnehin schon ORG_TABS.
const withoutCockpit = <T extends { id: string }>(list: T[]) =>
  list.filter(t => (t.id !== 'cockpit' || !isSystem.value)
                && (t.id !== 'aenderungen' || isSystem.value))
const visibleTabs = computed(() => {
  if (!orgLocked.value) return withoutCockpit(tabs)
  return tabs.filter(t => ORG_TABS.has(t.id)).map(t => t.id === 'dashboard' ? { ...t, label: uebersetze('aiact.aIActView.kISysteme') } : t)
})
const visibleNavGroups = computed(() => {
  if (!orgLocked.value) {
    return navGroups.map(g => ({ ...g, tabs: withoutCockpit(g.tabs) })).filter(g => g.tabs.length)
  }
  return navGroups
    .map(g => ({ ...g, tabs: g.tabs.filter(t => ORG_TABS.has(t.id))
      .map(t => t.id === 'dashboard' ? { ...t, label: uebersetze('aiact.aIActView.kISysteme') } : t) }))
    .filter(g => g.tabs.length)
})
watch(isSystem, (sys) => {
  if (sys && activeTab.value === 'cockpit') activeTab.value = 'dashboard'
  // #1756: Der gemerkte Reiter (persist-key) kann aus einem KI-System stammen;
  // in einer Organisation gibt es ihn nicht.
  if (!sys && activeTab.value === 'aenderungen') activeTab.value = 'dashboard'
})
// KI-System: „Risiken öffnen" springt zum Cockpit der Organisation.
function openRisikoCockpit() {
  if (isSystem.value) {
    const org = scopeInfo.value?.org_projekt
    if (!org || org === store.selectedProjekt) return
    store.selectedProjekt = org  // Watcher lädt das Projekt neu
  }
  activeTab.value = 'cockpit'
}
watch(orgLocked, (locked) => {
  if (locked && !ORG_TABS.has(activeTab.value)) activeTab.value = 'dashboard'
})
async function onCreateSystem() {
  const org = scopeInfo.value?.org_projekt || store.selectedProjekt
  if (!org) return
  systemDialog.value.busy = true
  systemDialog.value.error = ''
  const p = await store.createSystem(org, systemDialog.value.produkt.trim(), systemDialog.value.beschreibung.trim(),
                                     systemDialog.value.uebernehmen)
  systemDialog.value.busy = false
  if (!p) {
    systemDialog.value.error = store.error || uebersetze('aiact.aIActView.kISystemKonnteNichtAngelegtWerden')
    store.error = null
    return
  }
  systemDialog.value.open = false
  store.selectedProjekt = p.name
  activeTab.value = 'dashboard'
}

onMounted(async () => {
  await loadConstants()
  await store.fetchProjekte()
  const proj = (route.query.projekt || '') as string
  if (proj) store.selectedProjekt = proj
  if (store.selectedProjekt) await reloadProjekt()
})
</script>

<style scoped>
.aiact-view { max-width: 1400px; }

.project-name { margin: 0; font-size: 16px; flex: 1; color: var(--color-text-primary); }
.project-company { font-weight: 400; color: var(--color-text-secondary); font-size: 13px; }
.btn-danger-mini {
  background: #ffebee; color: #c62828; border: 1px solid #ef5350;
  padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
}
.btn-danger-mini:hover { background: #ffcdd2; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px; margin-bottom: 12px;
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
.form-row input, .form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px;
}

.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.dashboard {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.gauge-card {
  background: white; border: 1px solid var(--color-border); border-radius: 8px; padding: 16px;
  display: flex; align-items: center; justify-content: center;
}

.chapters-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px;
}

.anf-toolbar {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
}

.search { flex: 1; min-width: 200px; padding: 6px 10px; border: 1px solid var(--color-border);
  border-radius: 4px; font-size: 13px; }

.filter, .export-btn {
  padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px;
  background: white; text-decoration: none; color: #333;
}

.export-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }

.anf-list {
  background: white; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden;
}

.anf-list table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}

.anf-list th {
  background: #f5f5f5; text-align: left; padding: 10px; font-weight: 600;
  border-bottom: 1px solid var(--color-border);
}

.anf-list tbody tr { cursor: pointer; }
.anf-list tbody tr:hover { background: #f5f5f5; }
.anf-list td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; }

.title-cell { max-width: 400px; }

.llm-badges { display: flex; gap: 3px; flex-wrap: wrap; }

.llm-badge {
  background: #fff3e0; color: #e65100;
  padding: 2px 6px;
  font-size: 10px;
  border-radius: 3px;
  font-weight: 600;
}

.score-pill {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 11px; font-weight: 600;
}

.status-pill {
  padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
}

.status-pill.pending { background: #f3e5f5; color: #6a1b9a; }
.status-pill.partial { background: #fff3e0; color: #e65100; }
.status-pill.complete { background: #e8f5e9; color: #2e7d32; }

.empty { padding: 40px; text-align: center; color: #888; }

/* Repo-Scan-Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}

.modal-content {
  background: white; border-radius: 8px; padding: 24px;
  max-width: 700px; width: 90%; max-height: 90vh; overflow-y: auto;
}

.modal-content h3 { margin: 0 0 8px; color: var(--color-primary); }

.hint { color: #888; font-size: 13px; margin-bottom: 16px; }

.info {
  background: #fff8e1; color: #e65100; padding: 8px 12px; border-radius: 4px;
  margin: 12px 0; font-size: 13px;
}

.suggestions { margin-top: 16px; }
.suggestions h4 { margin: 0 0 8px; }

.suggestion-card {
  background: #f9f9f9;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.sugg-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.sugg-score {
  padding: 2px 10px; border-radius: 3px; color: white; font-size: 12px; font-weight: 600;
}
.sugg-conf { font-size: 11px; color: #666; }

.suggestion-card p { margin: 0 0 6px; font-size: 13px; color: #333; }

.suggestion-card pre {
  background: white; padding: 6px; border-radius: 4px;
  font-size: 11px; max-height: 100px; overflow-y: auto;
}

.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

.btn-primary, .btn-secondary, .btn-small {
  padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;
}

.btn-primary { background: var(--color-primary); color: white; }
.btn-primary:disabled { opacity: 0.6; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-small { padding: 5px 10px; background: white; border: 1px solid var(--color-border); font-size: 12px; }

@media (max-width: 768px) {
  .dashboard { grid-template-columns: 1fr; }
}

.check-row { display: block; font-size: 13px; margin: 4px 0 8px; }
.check-row input { margin-right: 6px; }
.check-row .hint { display: block; margin: 2px 0 0 22px; }
.scope-badge {
  display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;
  white-space: nowrap;
}
.scope-badge.org { background: #e3f2fd; color: #1565c0; }
.scope-badge.system { background: #ede7f6; color: #4527a0; }

.cockpit-hint {
  background: #fff8e1; border-left: 4px solid #ffb300; border-radius: 6px;
  padding: 16px 20px; color: #6d4c00; font-size: 14px;
}
</style>
