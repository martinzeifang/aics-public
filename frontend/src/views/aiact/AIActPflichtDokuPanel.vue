<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>{{ $t('aiact.aIActPflichtDokuPanel.aIActDokumentationHierStarten') }}</h3>
      <p>{{ $t('aiact.aIActPflichtDokuPanel.dieEUKIVerordnungAIActVerlangtFurKIS') }} <strong>{{ $t('common.dieseSeiteIstDerErsteSchritt') }}</strong>.</p>
      <div class="workflow">
        <strong>{{ $t('common.reihenfolge') }}</strong>
        <ol>
          <li><strong>{{ $t('aiact.aIActPflichtDokuPanel.a6RiskTierKlassifikator') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.prohibitedHighRiskLimitedMinimal') }}</li>
          <li><strong>{{ $t('aiact.aIActPflichtDokuPanel.a7UseCaseTemplate') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.branchenDefaultsInEinemKlick') }}</li>
          <li><strong>{{ $t('aiact.aIActPflichtDokuPanel.a1SystemDoku') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.artAnnexIVArchitekturTrainingTests') }}</li>
          <li><strong>{{ $t('aiact.aIActPflichtDokuPanel.a2DataGovernance') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.artTrainingsValidationDataBias') }}</li>
          <li><strong>{{ $t('aiact.aIActPflichtDokuPanel.a3RiskManagement') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.artLifecycleRisikenErfassen') }}</li>
          <li><strong>{{ $t('aiact.aIActPflichtDokuPanel.a4HumanOversight') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.artInterventionMechanismen') }}</li>
          <li><strong>{{ $t('aiact.aIActPflichtDokuPanel.a5PostMarketMonitoring') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.artDriftIncidentSLA') }}</li>
          <li><strong>A8 + A9</strong> {{ $t('aiact.aIActPflichtDokuPanel.konformitatserklarungTransparenzText') }}</li>
        </ol>
      </div>
    </div>

    <div v-if="riskTierInfo" class="risk-tier-card" :class="`tier-${riskTierInfo.tier}`">
      <strong>{{ $t('aiact.aIActPflichtDokuPanel.aIActRiskTier') }}</strong>
      <span class="tier-badge">{{ riskTierInfo.tier.toUpperCase() }}</span>
      <span v-if="riskTierInfo.annex_iii_kategorie" class="kat">{{ riskTierInfo.annex_iii_kategorie }}</span>
      <div v-if="riskTierInfo.begruendung" class="reason">{{ riskTierInfo.begruendung }}</div>
      <div v-if="riskTierInfo.konformitaetsbewertung" class="conf">
        {{ $t('aiact.aIActPflichtDokuPanel.konformitatsbewertung') }} <strong>{{ riskTierInfo.konformitaetsbewertung }}</strong>
      </div>
    </div>

    <!-- Cross-Module-Verknüpfungen (Sprint γ-C #537-#540) -->
    <div class="cross-module-bar">
      <strong>{{ $t('aiact.aIActPflichtDokuPanel.crossModule') }}</strong>
      <router-link to="/dsgvo" class="btn-cross" :title="$t('aiact.aIActPflichtDokuPanel.dSFAPflichtCheckFurKIVerarbeitung')">
        {{ $t('aiact.aIActPflichtDokuPanel.dSGVODSFA') }}
      </router-link>
      <router-link to="/cra" class="btn-cross" :title="$t('aiact.aIActPflichtDokuPanel.kIAlsProduktMitDigitalenElementen')">
        {{ $t('aiact.aIActPflichtDokuPanel.cRAProdukt') }}
      </router-link>
      <router-link to="/nis2" class="btn-cross" :title="$t('aiact.aIActPflichtDokuPanel.kIImKRITISSektorErhohteNIS2Anforderu')">
        {{ $t('aiact.aIActPflichtDokuPanel.nIS2KRITIS') }}
      </router-link>
      <router-link to="/risikobewertung" class="btn-cross" title="#540 — STRIDE-LLM-Risikoanalyse">
        {{ $t('aiact.aIActPflichtDokuPanel.risikobewertungSTRIDELLM') }}
      </router-link>
      <small class="hint">{{ $t('aiact.aIActPflichtDokuPanel.ausDemAIActInventarZuZugehorigenComp') }}</small>
    </div>

    <div v-if="status" class="status-grid">
      <div v-for="b in statusItems" :key="b.key" :class="['status-card', b.ok ? 'ok' : 'todo']">
        <div class="status-icon">{{ b.ok ? '✅' : '⚠️' }}</div>
        <div class="status-label">{{ b.label }}</div>
        <div class="status-detail">{{ b.detail }}</div>
      </div>
    </div>

    <!-- A1 System-Doku -->
    <details class="section" open>
      <summary><strong>{{ $t('aiact.aIActPflichtDokuPanel.a1TechnischeSystemDoku') }}</strong> {{ status?.system_doku?.ok ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.aIActArtAnnexIVVollstandigeTechnisch') }}
        </div>

        <!-- Auto-Fill (A1) -->
        <SuggestBar
          :busy="sd.busy"
          :suggestions="sd.suggestions"
          :existing="store.systemDoku"
          :field-labels="SYSTEM_DOKU_LABELS"
          @from-repo="runSuggest('sd', 'repo')"
          @from-url="(u: string) => runSuggest('sd', 'url', u)"
          @apply-one="(f: string) => applySuggestion('sd', f)"
          @apply-all="applyAllSuggestions('sd')"
        />

        <div class="form-grid">
          <input v-model="store.systemDoku.system_name" :placeholder="$t('aiact.aIActPflichtDokuPanel.systemName')" />
          <input v-model="store.systemDoku.version" :placeholder="$t('common.version')" />
          <input v-model="store.systemDoku.provider" :placeholder="$t('aiact.aIActPflichtDokuPanel.anbieterProvider')" />
          <input v-model="store.systemDoku.intended_purpose" :placeholder="$t('aiact.aIActPflichtDokuPanel.intendedPurpose')" />
          <input v-model="store.systemDoku.architecture" :placeholder="$t('aiact.aIActPflichtDokuPanel.architekturZBTransformerLLMB')" />
          <input v-model="store.systemDoku.training_methodology" :placeholder="$t('aiact.aIActPflichtDokuPanel.trainingMethodology')" />
          <input v-model="store.systemDoku.computational_resources" :placeholder="$t('aiact.aIActPflichtDokuPanel.computeResources')" />
          <textarea v-model="store.systemDoku.test_methodology" :placeholder="$t('aiact.aIActPflichtDokuPanel.testMethodology')" rows="2" />
          <textarea v-model="store.systemDoku.cybersecurity_measures" :placeholder="$t('aiact.aIActPflichtDokuPanel.cybersecurityMassnahmen')" rows="2" />
          <textarea v-model="store.systemDoku.accuracy_robustness" :placeholder="$t('aiact.aIActPflichtDokuPanel.accuracyRobustnessNotes')" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveSystemDoku(store.systemDoku)">{{ $t('common.save') }}</button>
      </div>
    </details>

    <!-- A2 Data-Governance -->
    <details class="section">
      <summary><strong>{{ $t('aiact.aIActPflichtDokuPanel.a2DataGovernance2') }}</strong> {{ status?.data_governance?.ok ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.aIActArtTrainingsValidationTestDaten') }}
        </div>

        <!-- Auto-Fill (A2) -->
        <SuggestBar
          :busy="dg.busy"
          :suggestions="dg.suggestions"
          :existing="store.dataGovernance"
          :field-labels="DATA_GOV_LABELS"
          @from-repo="runSuggest('dg', 'repo')"
          @from-url="(u: string) => runSuggest('dg', 'url', u)"
          @apply-one="(f: string) => applySuggestion('dg', f)"
          @apply-all="applyAllSuggestions('dg')"
        />

        <div class="form-grid">
          <input v-model="store.dataGovernance.training_data_source" :placeholder="$t('aiact.aIActPflichtDokuPanel.trainingDataSource')" />
          <input v-model="store.dataGovernance.training_data_size" :placeholder="$t('aiact.aIActPflichtDokuPanel.trainingDataSize')" />
          <input v-model="store.dataGovernance.validation_data_split" placeholder="Validation-Split (z.B. 10%)" />
          <input v-model="store.dataGovernance.test_data_split" placeholder="Test-Split (z.B. 10%)" />
          <input v-model="store.dataGovernance.data_collection_method" :placeholder="$t('aiact.aIActPflichtDokuPanel.collectionMethod')" />
          <input v-model="store.dataGovernance.data_labelling_method" :placeholder="$t('aiact.aIActPflichtDokuPanel.labellingMethod')" />
          <textarea v-model="store.dataGovernance.bias_assessment" :placeholder="$t('aiact.aIActPflichtDokuPanel.biasAssessment')" rows="2" />
          <textarea v-model="store.dataGovernance.bias_mitigation" :placeholder="$t('aiact.aIActPflichtDokuPanel.biasMitigation')" rows="2" />
          <label style="grid-column: 1 / -1;">
            <input type="checkbox" v-model="store.dataGovernance.personal_data_used" />
            {{ $t('aiact.aIActPflichtDokuPanel.personenbezogeneDatenVerwendet') }}
          </label>
          <input v-if="store.dataGovernance.personal_data_used"
                 v-model="store.dataGovernance.legal_basis_gdpr"
                 :placeholder="$t('aiact.aIActPflichtDokuPanel.gDPRRechtsgrundlageZBArtF')" />
          <textarea v-model="store.dataGovernance.representativeness" :placeholder="$t('aiact.aIActPflichtDokuPanel.representativenessDerDaten')" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveDataGovernance(store.dataGovernance)">{{ $t('common.save') }}</button>
      </div>
    </details>

    <!-- A3 Risk-Management -->
    <details class="section">
      <summary><strong>{{ $t('aiact.aIActPflichtDokuPanel.a3RiskManagement2') }}</strong>
        ({{ riskLink.linked_risk_projekt
          ? (riskLink.summary ? $t('common.v0VonV1Offen', { v0: riskLink.summary.offen, v1: riskLink.summary.total }) : $t('aiact.aIActPflichtDokuPanel.verknupft'))
          : $t('aiact.aIActPflichtDokuPanel.nichtVerknupft') }})</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.aIActArtKontinuierlichesRisikoManage') }}
        </div>
        <!-- #1044: A3 über das Risikobewertungs-Modul (Bewertungsart „EU-AI-Act") -->
        <div class="link-box">
          <p class="hint">{{ $t('aiact.aIActPflichtDokuPanel.risikenWerdenIm') }} <strong>{{ $t('aiact.aIActPflichtDokuPanel.risikobewertungsModul') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.mitDerBewertungsart') }}
            <strong>{{ $t('aiact.aIActPflichtDokuPanel.eUAIActArt') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.gepflegtUndHierVerknupftInklScoringE') }}</p>
          <template v-if="!riskLink.linked_risk_projekt">
            <div class="link-row">
              <select v-model="riskLinkSel">
                <option value="">{{ $t('aiact.aIActPflichtDokuPanel.risikobewertungsProjektWahlen') }}</option>
                <option v-for="c in riskCandidates" :key="c.name" :value="c.name">
                  {{ c.framework_match ? '⭐ ' : '' }}{{ c.name }} ({{ c.framework || '—' }}){{ c.unternehmen ? ' · ' + c.unternehmen : '' }}{{ c.firma_match ? $t('aiact.aIActPflichtDokuPanel.gleicheFirma') : '' }}
                </option>
              </select>
              <button class="btn-primary" :disabled="!riskLinkSel" @click="doSetRiskLink">{{ $t('common.verknupfen') }}</button>
              <router-link to="/risikobewertung" class="btn-cross" :title="$t('aiact.aIActPflichtDokuPanel.risikobewertungOffnen')">{{ $t('aiact.aIActPflichtDokuPanel.risikoprojektAnlegen') }}</router-link>
            </div>
            <p v-if="!riskCandidates.length" class="hint">
              {{ $t('aiact.aIActPflichtDokuPanel.nochKeinRisikobewertungsProjektVorha') }}</p>
            <p v-else class="hint">{{ $t('aiact.aIActPflichtDokuPanel.bewertungsartEUAIActEmpfohlenFurA3') }}</p>
          </template>
          <div v-else>
            <p>{{ $t('aiact.aIActPflichtDokuPanel.verknupftMit') }} <strong>{{ riskLink.linked_risk_projekt }}</strong>
              <span v-if="riskLink.summary"> · {{ riskLink.summary.offen }} offen / {{ riskLink.summary.total }} gesamt
                ({{ riskLink.summary.framework || '—' }})</span>
              <button class="btn-link" @click="doDeleteRiskLink">{{ $t('aiact.aIActPflichtDokuPanel.losen') }}</button>
              <router-link to="/risikobewertung" class="btn-link">{{ $t('aiact.aIActPflichtDokuPanel.imRisikobewertungsModulOffnen') }}</router-link>
            </p>
            <table v-if="linkedRisks.length">
              <thead><tr><th>Nr</th><th>{{ $t('common.risiko') }}</th><th>{{ $t('common.framework') }}</th><th>{{ $t('aiact.aIActPflichtDokuPanel.wert') }}</th><th>{{ $t('aiact.aIActPflichtDokuPanel.label') }}</th><th>{{ $t('common.status') }}</th></tr></thead>
              <tbody>
                <tr v-for="r in linkedRisks" :key="r.id">
                  <td>{{ r.nr }}</td><td>{{ r.risk_name }}</td><td>{{ r.framework }}</td>
                  <td>{{ r.risikowert ?? '—' }}</td><td>{{ r.risiko_label || '—' }}</td>
                  <td>{{ r.is_resolved ? '✓ behoben' : 'offen' }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="hint">{{ $t('aiact.aIActPflichtDokuPanel.nochKeineRisikenImVerknupftenProjekt') }}</p>
          </div>
        </div>

      </div>
    </details>

    <!-- A4 Human-Oversight -->
    <details class="section">
      <summary><strong>{{ $t('aiact.aIActPflichtDokuPanel.a4HumanOversight2') }}</strong> {{ status?.human_oversight?.ok ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.aIActArtMenschlicheAufsichtUberKIOut') }} <code>in-the-loop</code> {{ $t('aiact.aIActPflichtDokuPanel.menschEntscheidetJeOutput') }} <code>on-the-loop</code> {{ $t('aiact.aIActPflichtDokuPanel.uberwacht') }}
          <code>in-command</code> {{ $t('aiact.aIActPflichtDokuPanel.kannJederzeitEingreifenPlusIntervent') }}
        </div>
        <p class="assistent-hint">
          {{ $t('aiact.aIActPflichtDokuPanel.vorschlagFurOversightModusInterventi') }}
          <strong>{{ $t('aiact.aIActPflichtDokuPanel.zumAssistenten') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.reiterAssistentenA4HumanOversightWiz') }}
        </p>
        <div class="form-grid">
          <select v-model="store.humanOversight.oversight_mode">
            <option value="human-in-the-loop">human-in-the-loop</option>
            <option value="human-on-the-loop">human-on-the-loop</option>
            <option value="human-in-command">human-in-command</option>
          </select>
          <textarea v-model="store.humanOversight.intervention_mechanisms" placeholder="Intervention-Mechanismen (z.B. Stop-Button)" rows="2" />
          <textarea v-model="store.humanOversight.monitoring_interface" :placeholder="$t('aiact.aIActPflichtDokuPanel.monitoringInterface')" rows="2" />
          <textarea v-model="store.humanOversight.output_interpretation_aids" :placeholder="$t('aiact.aIActPflichtDokuPanel.erklarungenConfidenceScores')" rows="2" />
          <textarea v-model="store.humanOversight.abnormal_behavior_detection" :placeholder="$t('aiact.aIActPflichtDokuPanel.abnormalBehaviorDetection')" rows="2" />
          <textarea v-model="store.humanOversight.training_program" :placeholder="$t('aiact.aIActPflichtDokuPanel.trainingFurAufsichtspersonen')" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveHumanOversight(store.humanOversight)">{{ $t('common.save') }}</button>
      </div>
    </details>

    <!-- A5 Post-Market-Monitoring -->
    <details class="section">
      <summary><strong>{{ $t('aiact.aIActPflichtDokuPanel.a5PostMarketMonitoring2') }}</strong> {{ status?.post_market_monitoring?.ok ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.aIActArtNachMarkteintrittKontinuierl') }}
        </div>

        <!-- A5 Hilfe-Block (ausklappbar) -->
        <details class="pmm-help" @toggle="onPmmHelpToggle">
          <summary>{{ $t('aiact.aIActPflichtDokuPanel.iHilfeBehordeMonitoringSnippetsSchwe') }}</summary>
          <div v-if="pmmHelp" class="pmm-help-body">
            <p v-if="pmmHelp.behoerde"><strong>{{ $t('aiact.aIActPflichtDokuPanel.zustandigeBehorde') }}</strong> {{ pmmHelp.behoerde }}</p>
            <p v-if="pmmHelp.serious_incident_reporting_sla_default">
              <strong>{{ $t('aiact.aIActPflichtDokuPanel.defaultSLASchwereVorfalle') }}</strong> {{ pmmHelp.serious_incident_reporting_sla_default }}
            </p>
            <p v-if="pmmHelp.eu_articles"><strong>{{ $t('aiact.aIActPflichtDokuPanel.eUArtikel') }}</strong> {{ pmmHelp.eu_articles }}</p>
            <div v-if="pmmHelp.monitoring_plan_snippets?.length">
              <strong>{{ $t('aiact.aIActPflichtDokuPanel.monitoringPlanSnippets') }}</strong>
              <ul>
                <li v-for="(s, i) in pmmHelp.monitoring_plan_snippets" :key="`mp${i}`">
                  {{ s }}
                  <button class="btn-link" :title="$t('aiact.aIActPflichtDokuPanel.inMonitoringPlanUbernehmen')"
                          @click="appendSnippet('monitoring_plan', s)">➕</button>
                </li>
              </ul>
            </div>
            <div v-if="pmmHelp.incident_threshold_examples?.length">
              <strong>{{ $t('aiact.aIActPflichtDokuPanel.incidentThresholdBeispiele') }}</strong>
              <ul>
                <li v-for="(s, i) in pmmHelp.incident_threshold_examples" :key="`it${i}`">
                  {{ s }}
                  <button class="btn-link" :title="$t('aiact.aIActPflichtDokuPanel.alsIncidentThresholdUbernehmen')"
                          @click="setField('incident_threshold', s)">➕</button>
                </li>
              </ul>
            </div>
          </div>
          <p v-else class="hint">{{ $t('aiact.aIActPflichtDokuPanel.ladeHilfe') }}</p>
        </details>

        <p class="assistent-hint">
          {{ $t('aiact.aIActPflichtDokuPanel.vorschlagFurMonitoringPlanDriftDetec') }}
          <strong>{{ $t('aiact.aIActPflichtDokuPanel.zumAssistenten') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.reiterAssistentenA5MonitoringPlanWiz') }}
        </p>

        <div class="form-grid">
          <textarea v-model="store.pmm.monitoring_plan" :placeholder="$t('aiact.aIActPflichtDokuPanel.monitoringPlan')" rows="2" />
          <input v-model="store.pmm.performance_metrics" :placeholder="$t('aiact.aIActPflichtDokuPanel.performanceMetrics')" />
          <input v-model="store.pmm.drift_detection" :placeholder="$t('aiact.aIActPflichtDokuPanel.driftDetectionMethode')" />
          <input v-model="store.pmm.user_feedback_channel" :placeholder="$t('aiact.aIActPflichtDokuPanel.userFeedbackChannel')" />
          <input v-model="store.pmm.incident_threshold" placeholder="Incident-Threshold (z.B. Genauigkeit -5%)" />
          <input v-model="store.pmm.market_surveillance_contact" placeholder="Marktaufsicht-Kontakt (z.B. BNetzA)" />
          <input v-model="store.pmm.serious_incident_reporting_sla" :placeholder="$t('aiact.aIActPflichtDokuPanel.sLAReportingDefaultTage')" />
        </div>
        <button class="btn-primary" @click="store.savePmm(store.pmm)">{{ $t('common.save') }}</button>
      </div>
    </details>

    <!-- KI-Assistenten / Wizards: verschoben in den Reiter „🤖 Assistenten" (#1082) -->
    <div class="assistent-banner">
      <strong>{{ $t('aiact.aIActPflichtDokuPanel.kIAssistentenAmpWizards') }}</strong>
      <p>
        {{ $t('aiact.aIActPflichtDokuPanel.riskTierKlassifikatorA6UseCaseTempla') }}
      </p>
      <p class="assistent-hint"><strong>{{ $t('aiact.aIActPflichtDokuPanel.zumAssistenten') }}</strong> {{ $t('aiact.aIActPflichtDokuPanel.reiterAssistenten') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import SuggestBar from './SuggestBar.vue'
import { t } from '../../i18n'

const store = useAiActStore()

// ── Auto-Fill (A1/A2) ────────────────────────────────────────────────
const SYSTEM_DOKU_LABELS: Record<string, string> = {
  system_name: t('aiact.aIActPflichtDokuPanel.systemName'), version: t('common.version'), provider: t('aiact.aIActPflichtDokuPanel.anbieter'),
  intended_purpose: t('aiact.aIActPflichtDokuPanel.intendedPurpose'), architecture: t('aiact.aIActPflichtDokuPanel.architektur'),
  training_methodology: t('aiact.aIActPflichtDokuPanel.trainingMethodology'), computational_resources: t('aiact.aIActPflichtDokuPanel.computeResources'),
  test_methodology: t('aiact.aIActPflichtDokuPanel.testMethodology'), cybersecurity_measures: t('aiact.aIActPflichtDokuPanel.cybersecurityMassnahmen'),
  accuracy_robustness: t('aiact.aIActPflichtDokuPanel.accuracyRobustness'),
}
const DATA_GOV_LABELS: Record<string, string> = {
  training_data_source: t('aiact.aIActPflichtDokuPanel.trainingDataSource'), training_data_size: t('aiact.aIActPflichtDokuPanel.trainingDataSize'),
  validation_data_split: t('aiact.aIActPflichtDokuPanel.validationSplit'), test_data_split: t('aiact.aIActPflichtDokuPanel.testSplit'),
  data_collection_method: t('aiact.aIActPflichtDokuPanel.collectionMethod'), data_labelling_method: t('aiact.aIActPflichtDokuPanel.labellingMethod'),
  bias_assessment: t('aiact.aIActPflichtDokuPanel.biasAssessment'), bias_mitigation: t('aiact.aIActPflichtDokuPanel.biasMitigation'),
  personal_data_used: t('aiact.aIActPflichtDokuPanel.personenbezogeneDaten'), legal_basis_gdpr: t('aiact.aIActPflichtDokuPanel.gDPRRechtsgrundlage'),
  representativeness: t('aiact.aIActPflichtDokuPanel.representativeness'),
}

type SuggestSection = 'sd' | 'dg'
const sd = ref<any>({ busy: false, suggestions: null })
const dg = ref<any>({ busy: false, suggestions: null })
const suggestState = (sec: SuggestSection) => (sec === 'sd' ? sd : dg)

const runSuggest = async (sec: SuggestSection, source: 'repo' | 'url', url?: string) => {
  const st = suggestState(sec)
  st.value.busy = true
  st.value.suggestions = null
  try {
    const res = sec === 'sd'
      ? await store.suggestSystemDoku(source, url)
      : await store.suggestDataGovernance(source, url)
    st.value.suggestions = res?.suggestions || null
  } finally {
    st.value.busy = false
  }
}

const reloadSection = async (sec: SuggestSection) => {
  if (sec === 'sd') await store.fetchSystemDoku()
  else await store.fetchDataGovernance()
  await store.fetchPflichtDokuStatus()
}

const applySuggestion = async (sec: SuggestSection, field: string) => {
  const st = suggestState(sec)
  const sug = st.value.suggestions?.[field]
  if (!sug) return
  const ok = sec === 'sd'
    ? await store.applySystemDoku({ [field]: sug.value })
    : await store.applyDataGovernance({ [field]: sug.value })
  if (ok) {
    if (st.value.suggestions) delete st.value.suggestions[field]
    await reloadSection(sec)
  }
}

const applyAllSuggestions = async (sec: SuggestSection) => {
  const st = suggestState(sec)
  const all = st.value.suggestions
  if (!all) return
  const fields: Record<string, any> = {}
  for (const f of Object.keys(all)) fields[f] = all[f].value
  if (!Object.keys(fields).length) return
  if (!window.confirm(`Alle ${Object.keys(fields).length} Vorschläge übernehmen? Bestehende Werte werden überschrieben.`)) return
  const ok = sec === 'sd'
    ? await store.applySystemDoku(fields)
    : await store.applyDataGovernance(fields)
  if (ok) {
    st.value.suggestions = null
    await reloadSection(sec)
  }
}

const status = computed(() => store.pflichtDokuStatus)

const riskTierInfo = computed(() => {
  try {
    // #1858: hier stand `meta_json`. Das Feld heißt in **diesem** Modul
    // `meta` — `_serialize_projekt` in `server/api/aiact.py` ist eine
    // Positivliste und gibt die Rohspalte `meta_json` gar nicht heraus
    // (anders als CRA, DSGVO und WiBA, nach deren Muster diese Zeile
    // geschrieben wurde). `meta_json` war also immer `undefined`, der
    // Entwurf damit `{}` und `riskTierInfo` **immer null** — die Karte mit
    // der Einstufung des KI-Systems konnte nie erscheinen, obwohl der
    // Assistent A1 sie nach `meta.aiact.risk_tier` schreibt und Bericht
    // (`ai_act/report_export.py`) und FRIA (`ai_act/fria.py`) sie lesen.
    const meta = JSON.parse(store.selectedProjektObj?.meta || '{}')
    return meta?.aiact?.risk_tier || null
  } catch { return null }
})

const statusItems = computed(() => {
  const s = status.value
  if (!s) return []
  return [
    { key: 'sd', label: t('aiact.aIActPflichtDokuPanel.systemDoku'), ok: s.system_doku?.ok, detail: s.system_doku?.ok ? 'erfasst' : 'fehlt' },
    { key: 'dg', label: t('aiact.aIActPflichtDokuPanel.dataGovernance'), ok: s.data_governance?.ok, detail: s.data_governance?.ok ? 'erfasst' : 'fehlt' },
    { key: 'rm', label: t('common.risiken'), ok: s.risk_management?.ok, detail: `${s.risk_management?.open || 0} offen` },
    { key: 'ho', label: t('aiact.aIActPflichtDokuPanel.oversight'), ok: s.human_oversight?.ok, detail: s.human_oversight?.ok ? 'aktiv' : 'fehlt' },
    { key: 'pmm', label: t('aiact.aIActPflichtDokuPanel.postMarket'), ok: s.post_market_monitoring?.ok, detail: s.post_market_monitoring?.ok ? 'erfasst' : 'fehlt' },
  ]
})

// ── A3 Risikobewertungs-Verknüpfung (#1044) ──────────────────────────
const riskLink = ref<any>({ linked_risk_projekt: null })
const riskCandidates = ref<any[]>([])
const riskLinkSel = ref('')
const linkedRisks = ref<any[]>([])

const loadRiskLink = async () => {
  if (!store.selectedProjekt) return
  riskLink.value = await store.fetchRiskLink()
  riskCandidates.value = await store.fetchRiskLinkCandidates()
  if (riskLink.value.linked_risk_projekt) {
    const lr = await store.fetchLinkedRisks()
    linkedRisks.value = lr.risiken || []
  } else {
    linkedRisks.value = []
  }
}
const doSetRiskLink = async () => {
  if (!riskLinkSel.value) return
  const res = await store.setRiskLink(riskLinkSel.value)
  if (res) { riskLinkSel.value = ''; await loadRiskLink() }
}
const doDeleteRiskLink = async () => {
  if (await store.deleteRiskLink()) await loadRiskLink()
}

const reloadAll = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchSystemDoku(), store.fetchDataGovernance(),
    store.fetchHumanOversight(), store.fetchPmm(), store.fetchPflichtDokuStatus(),
    loadRiskLink(),
  ])
}

onMounted(reloadAll)
watch(() => store.selectedProjekt, reloadAll)

// ── A5 PMM-Hilfe ─────────────────────────────────────────────────────
const pmmHelp = ref<any>(null)
const onPmmHelpToggle = async (ev: Event) => {
  const el = ev.target as HTMLDetailsElement
  if (el.open && !pmmHelp.value) {
    pmmHelp.value = await store.fetchPmmHelp()
  }
}
const setField = (field: string, value: string) => {
  store.pmm[field] = value
}
const appendSnippet = (field: string, value: string) => {
  const cur = store.pmm[field] ? String(store.pmm[field]).trim() : ''
  store.pmm[field] = cur ? `${cur}\n${value}` : value
}
</script>

<style scoped>
.pflicht-doku { display: flex; flex-direction: column; gap: 14px; padding: 16px 0; }
.info-banner { background: #e3f2fd; padding: 16px 20px; border-radius: 8px; border-left: 4px solid #1565c0; }
.info-banner h3 { margin: 0 0 8px; color: #1565c0; }
.info-banner p { margin: 0 0 10px; color: #444; }
.workflow { background: white; padding: 12px 16px; border-radius: 6px; }
.workflow ol { margin: 6px 0 0 18px; padding: 0; }
.workflow li { margin: 4px 0; color: #333; }

.risk-tier-card {
  padding: 12px 16px; border-radius: 8px; border-left: 4px solid;
  display: flex; flex-direction: column; gap: 6px;
}
.risk-tier-card.tier-prohibited { background: #ffcdd2; border-color: #b71c1c; }
.risk-tier-card.tier-high-risk { background: #ffe0b2; border-color: #bf360c; }
.risk-tier-card.tier-limited-risk { background: #fff9c4; border-color: #f57f17; }
.risk-tier-card.tier-minimal-risk { background: #e8f5e9; border-color: #2e7d32; }
.tier-badge { font-weight: 700; font-size: 14px; padding: 2px 10px; border-radius: 4px; background: white; }
.kat { color: #555; font-size: 13px; }
.reason { color: #333; font-size: 13px; }
.conf { font-size: 12px; color: #555; }

.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
.status-card { padding: 12px; border-radius: 6px; text-align: center; border: 2px solid; }
.status-card.ok { background: #e8f5e9; border-color: #4caf50; }
.status-card.todo { background: #fff3e0; border-color: #ff9800; }
.status-icon { font-size: 26px; }
.status-label { font-weight: 600; margin-top: 4px; }
.status-detail { font-size: 12px; color: #666; margin-top: 2px; }

.section { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 10px 16px; }
.section summary { cursor: pointer; padding: 6px 0; font-size: 15px; }
.section-body { padding-top: 10px; }

.help-box {
  background: #fff8e1; border-left: 4px solid #ffc107; padding: 10px 14px;
  margin: 0 0 12px; border-radius: 4px; font-size: 13px; line-height: 1.55; color: #444;
}
.help-box code { background: #fff3cd; padding: 1px 5px; border-radius: 3px; font-size: 12px; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin-bottom: 10px; }
.form-grid input, .form-grid select, .form-grid textarea {
  padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit;
}
.form-grid textarea { grid-column: 1 / -1; }

.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #0d47a1; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 16px; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

table { width: 100%; border-collapse: collapse; margin-top: 10px; }
table th, table td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #eee; }
table th { background: #f5f5f5; font-weight: 600; }

.wizards { background: #f3e5f5; border-color: #ce93d8; }
.wizards-d { background: #ede7f6; border-color: #b39ddb; }
.wizards-d .wizard-card { border-left-color: #4527a0; }
.wizards-d .wizard-card h4 { color: #311b92; }
.badge {
  background: #4527a0; color: white; font-size: 11px;
  padding: 1px 7px; border-radius: 10px; margin-left: 6px; vertical-align: middle;
}

.wizards-e { background: #e0f2f1; border-color: #80cbc4; }
.wizards-e .wizard-card { border-left-color: #00695c; }
.wizards-e .wizard-card h4 { color: #004d40; }
.wizards-e .badge { background: #00695c; }

.watch-table { width: 100%; margin-top: 8px; font-size: 13px; }
.watch-table th, .watch-table td { padding: 5px 8px; }
.watch-badge {
  padding: 2px 8px; border-radius: 10px; font-weight: 600; font-size: 11px;
  text-transform: uppercase;
}
.watch-mitigiert { background: #c8e6c9; color: #1b5e20; }
.watch-offen { background: #ffe0b2; color: #bf360c; }
.watch-na { background: #eceff1; color: #455a64; }

.pre-market-result {
  padding: 12px 16px; border-radius: 6px; margin-top: 12px;
  border-left: 4px solid;
}
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
.wizard-card { background: white; padding: 12px; border-radius: 6px; margin-bottom: 12px; border-left: 4px solid #7b1fa2; }
.wizard-card h4 { margin: 0 0 6px; color: #4a148c; }
.wizard-card p { margin: 0 0 8px; color: #555; font-size: 13px; }
.wizard-card .row { display: flex; gap: 8px; align-items: center; }
.wizard-card select { flex: 1; padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; }
.hint { color: #666; font-size: 13px; margin-top: 6px; }

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
.wizard-modal textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.wizard-modal .mono { font-family: monospace; font-size: 12px; }
.parsed-result { background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 12px; }
.parsed-result pre { margin: 6px 0 0; white-space: pre-wrap; font-size: 12px; }
.wizard-error { background: #fdecea; color: #b71c1c; border: 1px solid #f5c6cb;
  padding: 10px 12px; border-radius: 4px; margin-top: 12px; font-size: 13px; }
.link-box { background: #f1f8ff; border: 1px solid #cfe3ff; border-radius: 6px; padding: 12px; margin-bottom: 10px; }
.link-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.subsection { margin-top: 10px; }
.subsection > summary { cursor: pointer; color: #555; font-size: 13px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.btn-secondary { background: #eee; color: #333; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }

.wizard-launch {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin: 0 0 12px;
}
.pmm-help {
  background: #e3f2fd; border-left: 4px solid #1565c0; border-radius: 4px;
  padding: 8px 14px; margin: 0 0 12px; font-size: 13px;
}
.pmm-help summary { cursor: pointer; font-weight: 600; color: #1565c0; }
.pmm-help-body { padding-top: 8px; line-height: 1.5; color: #444; }
.pmm-help-body p { margin: 4px 0; }
.pmm-help-body ul { margin: 4px 0 8px 18px; padding: 0; }
.pmm-help-body li { margin: 3px 0; }

.cross-module-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 14px; background: #ede7f6; border-left: 4px solid #5e35b1;
  border-radius: 6px; font-size: 13px;
}
.cross-module-bar strong { color: #311b92; }
.btn-cross {
  padding: 4px 12px; background: white; border: 1px solid #5e35b1;
  color: #311b92; border-radius: 4px; font-size: 13px; text-decoration: none;
  transition: all 0.2s;
}
.btn-cross:hover { background: #5e35b1; color: white; }
.cross-module-bar .hint { color: #5e35b1; flex-basis: 100%; font-size: 12px; }

.assistent-banner {
  background: #f3e5f5; border: 1px solid #ce93d8; border-left: 4px solid #7b1fa2;
  border-radius: 8px; padding: 14px 18px;
}
.assistent-banner strong { color: #4a148c; }
.assistent-banner p { margin: 6px 0 0; color: #555; font-size: 13px; line-height: 1.5; }
.assistent-hint {
  margin: 8px 0 0; color: #6a1b9a; font-size: 13px;
}
.assistent-hint strong { color: #4a148c; }
</style>
