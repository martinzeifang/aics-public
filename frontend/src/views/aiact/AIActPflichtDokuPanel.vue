<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>📋 AI-Act-Dokumentation — Hier starten</h3>
      <p>Die EU-KI-Verordnung 2024/1689 (AI Act) verlangt für KI-Systeme eine
        umfangreiche technische Dokumentation. <strong>Diese Seite ist der erste Schritt</strong>.</p>
      <div class="workflow">
        <strong>Reihenfolge:</strong>
        <ol>
          <li><strong>A6 Risk-Tier-Klassifikator</strong> ⇒ prohibited / high-risk / limited / minimal</li>
          <li><strong>A7 Use-Case-Template</strong> ⇒ branchen-Defaults in einem Klick</li>
          <li><strong>A1 System-Doku</strong> (Art. 11 + Annex IV) — Architektur + Training + Tests</li>
          <li><strong>A2 Data-Governance</strong> (Art. 10) — Trainings-/Validation-Data + Bias</li>
          <li><strong>A3 Risk-Management</strong> (Art. 9) — Lifecycle-Risiken erfassen</li>
          <li><strong>A4 Human-Oversight</strong> (Art. 14) — Intervention-Mechanismen</li>
          <li><strong>A5 Post-Market-Monitoring</strong> (Art. 72-73) — Drift + Incident-SLA</li>
          <li><strong>A8 + A9</strong> Konformitätserklärung + Transparenz-Texte generieren</li>
        </ol>
      </div>
    </div>

    <div v-if="riskTierInfo" class="risk-tier-card" :class="`tier-${riskTierInfo.tier}`">
      <strong>📌 AI-Act Risk-Tier:</strong>
      <span class="tier-badge">{{ riskTierInfo.tier.toUpperCase() }}</span>
      <span v-if="riskTierInfo.annex_iii_kategorie" class="kat">{{ riskTierInfo.annex_iii_kategorie }}</span>
      <div v-if="riskTierInfo.begruendung" class="reason">{{ riskTierInfo.begruendung }}</div>
      <div v-if="riskTierInfo.konformitaetsbewertung" class="conf">
        Konformitätsbewertung: <strong>{{ riskTierInfo.konformitaetsbewertung }}</strong>
      </div>
    </div>

    <!-- Cross-Module-Verknüpfungen (Sprint γ-C #537-#540) -->
    <div class="cross-module-bar">
      <strong>🔗 Cross-Module:</strong>
      <router-link to="/dsgvo" class="btn-cross" title="#537 — DSFA-Pflicht-Check für KI-Verarbeitung">
        → DSGVO (DSFA)
      </router-link>
      <router-link to="/cra" class="btn-cross" title="#538 — KI als Produkt mit digitalen Elementen">
        → CRA (Produkt)
      </router-link>
      <router-link to="/nis2" class="btn-cross" title="#539 — KI im KRITIS-Sektor: erhöhte NIS2-Anforderungen">
        → NIS2 (KRITIS)
      </router-link>
      <router-link to="/risikobewertung" class="btn-cross" title="#540 — STRIDE-LLM-Risikoanalyse">
        → Risikobewertung (STRIDE-LLM)
      </router-link>
      <small class="hint">Aus dem AI-Act-Inventar zu zugehörigen Compliance-Bereichen springen.</small>
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
      <summary><strong>A1 — Technische System-Doku</strong> {{ status?.system_doku?.ok ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 11 + Annex IV: vollständige technische Doku
          des KI-Systems — Architektur, Training-Methodology, Compute-Resources,
          Performance-Metrics, Cybersecurity-Maßnahmen, Accuracy/Robustness.
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
          <input v-model="store.systemDoku.system_name" placeholder="System-Name" />
          <input v-model="store.systemDoku.version" placeholder="Version" />
          <input v-model="store.systemDoku.provider" placeholder="Anbieter (Provider)" />
          <input v-model="store.systemDoku.intended_purpose" placeholder="Intended Purpose" />
          <input v-model="store.systemDoku.architecture" placeholder="Architektur (z.B. Transformer-LLM 7B)" />
          <input v-model="store.systemDoku.training_methodology" placeholder="Training-Methodology" />
          <input v-model="store.systemDoku.computational_resources" placeholder="Compute-Resources" />
          <textarea v-model="store.systemDoku.test_methodology" placeholder="Test-Methodology" rows="2" />
          <textarea v-model="store.systemDoku.cybersecurity_measures" placeholder="Cybersecurity-Maßnahmen" rows="2" />
          <textarea v-model="store.systemDoku.accuracy_robustness" placeholder="Accuracy / Robustness Notes" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveSystemDoku(store.systemDoku)">Speichern</button>
      </div>
    </details>

    <!-- A2 Data-Governance -->
    <details class="section">
      <summary><strong>A2 — Data-Governance</strong> {{ status?.data_governance?.ok ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 10: Trainings-/Validation-/Test-Daten-Governance.
          Bias-Assessment + Mitigation + GDPR-Rechtsgrundlage falls personenbezogene Daten.
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
          <input v-model="store.dataGovernance.training_data_source" placeholder="Training-Data-Source" />
          <input v-model="store.dataGovernance.training_data_size" placeholder="Training-Data-Size" />
          <input v-model="store.dataGovernance.validation_data_split" placeholder="Validation-Split (z.B. 10%)" />
          <input v-model="store.dataGovernance.test_data_split" placeholder="Test-Split (z.B. 10%)" />
          <input v-model="store.dataGovernance.data_collection_method" placeholder="Collection-Method" />
          <input v-model="store.dataGovernance.data_labelling_method" placeholder="Labelling-Method" />
          <textarea v-model="store.dataGovernance.bias_assessment" placeholder="Bias-Assessment" rows="2" />
          <textarea v-model="store.dataGovernance.bias_mitigation" placeholder="Bias-Mitigation" rows="2" />
          <label style="grid-column: 1 / -1;">
            <input type="checkbox" v-model="store.dataGovernance.personal_data_used" />
            Personenbezogene Daten verwendet
          </label>
          <input v-if="store.dataGovernance.personal_data_used"
                 v-model="store.dataGovernance.legal_basis_gdpr"
                 placeholder="GDPR-Rechtsgrundlage (z.B. Art. 6(1)(f))" />
          <textarea v-model="store.dataGovernance.representativeness" placeholder="Representativeness der Daten" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveDataGovernance(store.dataGovernance)">Speichern</button>
      </div>
    </details>

    <!-- A3 Risk-Management -->
    <details class="section">
      <summary><strong>A3 — Risk-Management</strong>
        ({{ riskLink.linked_risk_projekt
          ? (riskLink.summary ? riskLink.summary.offen + '/' + riskLink.summary.total + ' offen' : 'verknüpft')
          : 'nicht verknüpft' }})</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 9: kontinuierliches Risiko-Management-System
          über den gesamten KI-Lebenszyklus (Design → Development → Deployment → Monitoring).
          Pro Risiko: Lifecycle-Phase, Kategorie, Severity × Likelihood, Mitigation, Residual-Risk.
        </div>
        <!-- #1044: A3 über das Risikobewertungs-Modul (Bewertungsart „EU-AI-Act") -->
        <div class="link-box">
          <p class="hint">Risiken werden im <strong>Risikobewertungs-Modul</strong> mit der Bewertungsart
            <strong>„EU-AI-Act" (Art. 9)</strong> gepflegt und hier verknüpft — inkl. Scoring, Export und Issue-Tracking.</p>
          <template v-if="!riskLink.linked_risk_projekt">
            <div class="link-row">
              <select v-model="riskLinkSel">
                <option value="">— Risikobewertungs-Projekt wählen —</option>
                <option v-for="c in riskCandidates" :key="c.name" :value="c.name">
                  {{ c.framework_match ? '⭐ ' : '' }}{{ c.name }} ({{ c.framework || '—' }}){{ c.unternehmen ? ' · ' + c.unternehmen : '' }}{{ c.firma_match ? ' · gleiche Firma' : '' }}
                </option>
              </select>
              <button class="btn-primary" :disabled="!riskLinkSel" @click="doSetRiskLink">Verknüpfen</button>
              <router-link to="/risikobewertung" class="btn-cross" title="Risikobewertung öffnen">↗ Risikoprojekt anlegen</router-link>
            </div>
            <p v-if="!riskCandidates.length" class="hint">
              Noch kein Risikobewertungs-Projekt vorhanden — lege eines mit der Bewertungsart „EU-AI-Act" an.</p>
            <p v-else class="hint">⭐ = Bewertungsart EU-AI-Act (empfohlen für A3).</p>
          </template>
          <div v-else>
            <p>✔ Verknüpft mit <strong>{{ riskLink.linked_risk_projekt }}</strong>
              <span v-if="riskLink.summary"> · {{ riskLink.summary.offen }} offen / {{ riskLink.summary.total }} gesamt
                ({{ riskLink.summary.framework || '—' }})</span>
              <button class="btn-link" @click="doDeleteRiskLink">lösen</button>
              <router-link to="/risikobewertung" class="btn-link">↗ im Risikobewertungs-Modul öffnen</router-link>
            </p>
            <table v-if="linkedRisks.length">
              <thead><tr><th>Nr</th><th>Risiko</th><th>Framework</th><th>Wert</th><th>Label</th><th>Status</th></tr></thead>
              <tbody>
                <tr v-for="r in linkedRisks" :key="r.id">
                  <td>{{ r.nr }}</td><td>{{ r.risk_name }}</td><td>{{ r.framework }}</td>
                  <td>{{ r.risikowert ?? '—' }}</td><td>{{ r.risiko_label || '—' }}</td>
                  <td>{{ r.is_resolved ? '✓ behoben' : 'offen' }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="hint">Noch keine Risiken im verknüpften Projekt.</p>
          </div>
        </div>

      </div>
    </details>

    <!-- A4 Human-Oversight -->
    <details class="section">
      <summary><strong>A4 — Human-Oversight</strong> {{ status?.human_oversight?.ok ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 14: menschliche Aufsicht über KI-Output.
          Modi: <code>in-the-loop</code> (Mensch entscheidet je Output), <code>on-the-loop</code> (überwacht),
          <code>in-command</code> (kann jederzeit eingreifen). Plus Intervention-Mechanismen + Training.
        </div>
        <p class="assistent-hint">
          🤖 Vorschlag für Oversight-Modus + Intervention-Mechanismen?
          <strong>Zum Assistenten →</strong> Reiter „🤖 Assistenten" · „A4 — Human-Oversight-Wizard".
        </p>
        <div class="form-grid">
          <select v-model="store.humanOversight.oversight_mode">
            <option value="human-in-the-loop">human-in-the-loop</option>
            <option value="human-on-the-loop">human-on-the-loop</option>
            <option value="human-in-command">human-in-command</option>
          </select>
          <textarea v-model="store.humanOversight.intervention_mechanisms" placeholder="Intervention-Mechanismen (z.B. Stop-Button)" rows="2" />
          <textarea v-model="store.humanOversight.monitoring_interface" placeholder="Monitoring-Interface" rows="2" />
          <textarea v-model="store.humanOversight.output_interpretation_aids" placeholder="Erklärungen / Confidence-Scores" rows="2" />
          <textarea v-model="store.humanOversight.abnormal_behavior_detection" placeholder="Abnormal-Behavior-Detection" rows="2" />
          <textarea v-model="store.humanOversight.training_program" placeholder="Training für Aufsichtspersonen" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveHumanOversight(store.humanOversight)">Speichern</button>
      </div>
    </details>

    <!-- A5 Post-Market-Monitoring -->
    <details class="section">
      <summary><strong>A5 — Post-Market-Monitoring</strong> {{ status?.post_market_monitoring?.ok ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 72-73: nach Markteintritt kontinuierliche
          Überwachung + Incident-Reporting (15 Tage SLA an Marktaufsicht bei schweren Vorfällen).
          Drift-Detection, User-Feedback-Kanal, Performance-Threshold-Definition.
        </div>

        <!-- A5 Hilfe-Block (ausklappbar) -->
        <details class="pmm-help" @toggle="onPmmHelpToggle">
          <summary>ℹ️ Hilfe: Behörde, Monitoring-Snippets, Schwellen-Beispiele, EU-Artikel</summary>
          <div v-if="pmmHelp" class="pmm-help-body">
            <p v-if="pmmHelp.behoerde"><strong>Zuständige Behörde:</strong> {{ pmmHelp.behoerde }}</p>
            <p v-if="pmmHelp.serious_incident_reporting_sla_default">
              <strong>Default-SLA (schwere Vorfälle):</strong> {{ pmmHelp.serious_incident_reporting_sla_default }}
            </p>
            <p v-if="pmmHelp.eu_articles"><strong>EU-Artikel:</strong> {{ pmmHelp.eu_articles }}</p>
            <div v-if="pmmHelp.monitoring_plan_snippets?.length">
              <strong>Monitoring-Plan-Snippets:</strong>
              <ul>
                <li v-for="(s, i) in pmmHelp.monitoring_plan_snippets" :key="`mp${i}`">
                  {{ s }}
                  <button class="btn-link" title="In Monitoring-Plan übernehmen"
                          @click="appendSnippet('monitoring_plan', s)">➕</button>
                </li>
              </ul>
            </div>
            <div v-if="pmmHelp.incident_threshold_examples?.length">
              <strong>Incident-Threshold-Beispiele:</strong>
              <ul>
                <li v-for="(s, i) in pmmHelp.incident_threshold_examples" :key="`it${i}`">
                  {{ s }}
                  <button class="btn-link" title="Als Incident-Threshold übernehmen"
                          @click="setField('incident_threshold', s)">➕</button>
                </li>
              </ul>
            </div>
          </div>
          <p v-else class="hint">Lade Hilfe…</p>
        </details>

        <p class="assistent-hint">
          🤖 Vorschlag für Monitoring-Plan, Drift-Detection und Incident-SLA?
          <strong>Zum Assistenten →</strong> Reiter „🤖 Assistenten" · „A5 — Monitoring-Plan-Wizard".
        </p>

        <div class="form-grid">
          <textarea v-model="store.pmm.monitoring_plan" placeholder="Monitoring-Plan" rows="2" />
          <input v-model="store.pmm.performance_metrics" placeholder="Performance-Metrics" />
          <input v-model="store.pmm.drift_detection" placeholder="Drift-Detection-Methode" />
          <input v-model="store.pmm.user_feedback_channel" placeholder="User-Feedback-Channel" />
          <input v-model="store.pmm.incident_threshold" placeholder="Incident-Threshold (z.B. Genauigkeit -5%)" />
          <input v-model="store.pmm.market_surveillance_contact" placeholder="Marktaufsicht-Kontakt (z.B. BNetzA)" />
          <input v-model="store.pmm.serious_incident_reporting_sla" placeholder="SLA Reporting (Default: 15 Tage)" />
        </div>
        <button class="btn-primary" @click="store.savePmm(store.pmm)">Speichern</button>
      </div>
    </details>

    <!-- KI-Assistenten / Wizards: verschoben in den Reiter „🤖 Assistenten" (#1082) -->
    <div class="assistent-banner">
      <strong>🤖 KI-Assistenten &amp; Wizards</strong>
      <p>
        Risk-Tier-Klassifikator (A6), Use-Case-Templates (A7), EU-DOC/Transparenz (A8/A9),
        Spezial-Wizards (LLM-Card, High-Risk-DOC, Prompt-Injection-Tests, HITL, EU-DB) und
        Erweiterungen (Model-Card-Import, OWASP-Watch, Chat, EU-Office-Report, Pre-Market-Check)
        sowie die Human-Oversight- und Monitoring-Plan-Wizards findest du jetzt im eigenen Reiter.
      </p>
      <p class="assistent-hint"><strong>Zum Assistenten →</strong> Reiter „🤖 Assistenten".</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import SuggestBar from './SuggestBar.vue'

const store = useAiActStore()

// ── Auto-Fill (A1/A2) ────────────────────────────────────────────────
const SYSTEM_DOKU_LABELS: Record<string, string> = {
  system_name: 'System-Name', version: 'Version', provider: 'Anbieter',
  intended_purpose: 'Intended Purpose', architecture: 'Architektur',
  training_methodology: 'Training-Methodology', computational_resources: 'Compute-Resources',
  test_methodology: 'Test-Methodology', cybersecurity_measures: 'Cybersecurity-Maßnahmen',
  accuracy_robustness: 'Accuracy / Robustness',
}
const DATA_GOV_LABELS: Record<string, string> = {
  training_data_source: 'Training-Data-Source', training_data_size: 'Training-Data-Size',
  validation_data_split: 'Validation-Split', test_data_split: 'Test-Split',
  data_collection_method: 'Collection-Method', data_labelling_method: 'Labelling-Method',
  bias_assessment: 'Bias-Assessment', bias_mitigation: 'Bias-Mitigation',
  personal_data_used: 'Personenbezogene Daten', legal_basis_gdpr: 'GDPR-Rechtsgrundlage',
  representativeness: 'Representativeness',
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
    const meta = JSON.parse(store.selectedProjektObj?.meta_json || '{}')
    return meta?.aiact?.risk_tier || null
  } catch { return null }
})

const statusItems = computed(() => {
  const s = status.value
  if (!s) return []
  return [
    { key: 'sd', label: 'System-Doku', ok: s.system_doku?.ok, detail: s.system_doku?.ok ? 'erfasst' : 'fehlt' },
    { key: 'dg', label: 'Data-Governance', ok: s.data_governance?.ok, detail: s.data_governance?.ok ? 'erfasst' : 'fehlt' },
    { key: 'rm', label: 'Risiken', ok: s.risk_management?.ok, detail: `${s.risk_management?.open || 0} offen` },
    { key: 'ho', label: 'Oversight', ok: s.human_oversight?.ok, detail: s.human_oversight?.ok ? 'aktiv' : 'fehlt' },
    { key: 'pmm', label: 'Post-Market', ok: s.post_market_monitoring?.ok, detail: s.post_market_monitoring?.ok ? 'erfasst' : 'fehlt' },
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
