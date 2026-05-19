<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>📋 AI-Act-Pflicht-Doku — Start hier</h3>
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

    <div v-if="status" class="status-grid">
      <div v-for="b in statusItems" :key="b.key" :class="['status-card', b.ok ? 'ok' : 'todo']">
        <div class="status-icon">{{ b.ok ? '✅' : '⚠️' }}</div>
        <div class="status-label">{{ b.label }}</div>
        <div class="status-detail">{{ b.detail }}</div>
      </div>
    </div>

    <!-- A1 System-Doku -->
    <details class="section" open>
      <summary><strong>A1 — Technische System-Doku</strong> {{ store.systemDoku.system_name ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 11 + Annex IV: vollständige technische Doku
          des KI-Systems — Architektur, Training-Methodology, Compute-Resources,
          Performance-Metrics, Cybersecurity-Maßnahmen, Accuracy/Robustness.
        </div>
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
      <summary><strong>A2 — Data-Governance</strong> {{ store.dataGovernance.training_data_source ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 10: Trainings-/Validation-/Test-Daten-Governance.
          Bias-Assessment + Mitigation + GDPR-Rechtsgrundlage falls personenbezogene Daten.
        </div>
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
      <summary><strong>A3 — Risk-Management</strong> ({{ openRiskCount }}/{{ store.aiactRisks.length }} offen)</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 9: kontinuierliches Risiko-Management-System
          über den gesamten KI-Lebenszyklus (Design → Development → Deployment → Monitoring).
          Pro Risiko: Lifecycle-Phase, Kategorie, Severity × Likelihood, Mitigation, Residual-Risk.
        </div>
        <div class="form-grid">
          <input v-model="riskForm.risk_id" placeholder="Risk-ID (z.B. AIA-R-001)" />
          <input v-model="riskForm.titel" placeholder="Titel" />
          <select v-model="riskForm.lifecycle_phase">
            <option value="design">Design</option><option value="development">Development</option>
            <option value="deployment">Deployment</option><option value="monitoring">Monitoring</option>
          </select>
          <select v-model="riskForm.risk_category">
            <option value="safety">Safety</option><option value="fundamental-rights">Fundamental Rights</option>
            <option value="bias">Bias</option><option value="security">Security</option><option value="other">Other</option>
          </select>
          <select v-model="riskForm.severity">
            <option value="niedrig">Niedrig</option><option value="mittel">Mittel</option>
            <option value="hoch">Hoch</option><option value="kritisch">Kritisch</option>
          </select>
          <select v-model="riskForm.likelihood">
            <option value="unwahrscheinlich">Unwahrscheinlich</option><option value="mittel">Mittel</option>
            <option value="wahrscheinlich">Wahrscheinlich</option><option value="sehr-wahrscheinlich">Sehr wahrscheinlich</option>
          </select>
          <button class="btn-primary" @click="addRisk">Risiko hinzufügen</button>
        </div>
        <table>
          <thead><tr><th>ID</th><th>Titel</th><th>Phase</th><th>Kategorie</th><th>Score</th><th>Status</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in store.aiactRisks" :key="r.id">
              <td><code>{{ r.risk_id }}</code></td>
              <td>{{ r.titel }}</td>
              <td>{{ r.lifecycle_phase }}</td>
              <td>{{ r.risk_category }}</td>
              <td><strong>{{ r.risk_score }}</strong></td>
              <td>{{ r.status }}</td>
              <td><button class="btn-link" @click="store.deleteAiactRisk(r.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- A4 Human-Oversight -->
    <details class="section">
      <summary><strong>A4 — Human-Oversight</strong> {{ store.humanOversight.oversight_mode || '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 14: menschliche Aufsicht über KI-Output.
          Modi: <code>in-the-loop</code> (Mensch entscheidet je Output), <code>on-the-loop</code> (überwacht),
          <code>in-command</code> (kann jederzeit eingreifen). Plus Intervention-Mechanismen + Training.
        </div>
        <div class="form-grid">
          <select v-model="store.humanOversight.oversight_mode">
            <option value="human-in-the-loop">human-in-the-loop</option>
            <option value="human-on-the-loop">human-on-the-loop</option>
            <option value="human-in-command">human-in-command</option>
          </select>
          <input v-model="store.humanOversight.intervention_mechanisms" placeholder="Intervention-Mechanismen (z.B. Stop-Button)" />
          <input v-model="store.humanOversight.monitoring_interface" placeholder="Monitoring-Interface" />
          <input v-model="store.humanOversight.output_interpretation_aids" placeholder="Erklärungen / Confidence-Scores" />
          <textarea v-model="store.humanOversight.abnormal_behavior_detection" placeholder="Abnormal-Behavior-Detection" rows="2" />
          <textarea v-model="store.humanOversight.training_program" placeholder="Training für Aufsichtspersonen" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveHumanOversight(store.humanOversight)">Speichern</button>
      </div>
    </details>

    <!-- A5 Post-Market-Monitoring -->
    <details class="section">
      <summary><strong>A5 — Post-Market-Monitoring</strong> {{ store.pmm.monitoring_plan ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> AI Act Art. 72-73: nach Markteintritt kontinuierliche
          Überwachung + Incident-Reporting (15 Tage SLA an Marktaufsicht bei schweren Vorfällen).
          Drift-Detection, User-Feedback-Kanal, Performance-Threshold-Definition.
        </div>
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

    <!-- Phase B: KI-Wizards -->
    <details class="section wizards" open>
      <summary><strong>🤖 KI-Assistenten</strong> — Risk-Tier + Use-Case + EU-DOC + Transparenz</summary>
      <div class="section-body">
        <div class="wizard-card">
          <h4>A6 — Risk-Tier-Klassifikator</h4>
          <p><strong>Output:</strong> bestimmt automatisch ob prohibited / high-risk (Annex III) /
            limited (Art. 50 Transparenz) / minimal. Schreibt in <code>meta_json.aiact.risk_tier</code>.</p>
          <button class="btn-primary" @click="openWizard('risk-tier')">📝 Prompt generieren</button>
        </div>

        <div class="wizard-card">
          <h4>A7 — Use-Case-Template anwenden</h4>
          <p><strong>Output:</strong> setzt Defaults für Oversight-Mode + Reporting-SLA passend zum Use-Case.</p>
          <div class="row">
            <select v-model="selectedUseCase">
              <option value="">— Use-Case wählen —</option>
              <option v-for="t in store.useCaseTemplates" :key="t.id" :value="t.id">
                {{ t.name }} ({{ t.tier }})
              </option>
            </select>
            <button class="btn-primary" :disabled="!selectedUseCase" @click="applyUseCase">⚡ Anwenden</button>
          </div>
          <p v-if="useCaseApplied" class="hint">✅ Template <strong>{{ useCaseAppliedName }}</strong> angewendet.</p>
        </div>

        <div class="wizard-card">
          <h4>A8 — EU-Konformitätserklärung (Annex V)</h4>
          <p><strong>Output:</strong> fertiger Markdown-Text der EU-DOC nach Annex V — angewandte Normen,
            Konformitätsbewertung-Modul, Notified-Body-Hinweis. Wird in <code>system_doku.notizen</code> angehängt.</p>
          <button class="btn-primary" @click="openWizard('eu-doc')">📝 Prompt generieren</button>
        </div>

        <div class="wizard-card">
          <h4>A9 — Transparenz-Hinweise (Art. 50)</h4>
          <p><strong>Output:</strong> User-Facing-Texte für Chatbot-Disclosure / Deepfake-Markierung /
            Emotion-Recognition-Hinweis + Platzierungs-Vorschlag.</p>
          <button class="btn-primary" @click="openWizard('transparency')">📝 Prompt generieren</button>
        </div>
      </div>
    </details>

    <!-- Wizard-Modal -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @click.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <p class="hint">1. Prompt nach ChatGPT kopieren. 2. JSON-Antwort hier einfügen. 3. „Parsen + Anwenden".</p>
        <label>Prompt</label>
        <textarea readonly :value="wizardModal.prompt" rows="8" class="mono"></textarea>
        <button class="btn-link" @click="copyPrompt">📋 Kopieren</button>
        <label>ChatGPT-Antwort (JSON)</label>
        <textarea v-model="wizardModal.response" rows="6" class="mono" placeholder="JSON hier einfügen..."></textarea>
        <div v-if="wizardModal.parsed" class="parsed-result">
          <strong v-if="wizardModal.parsed.applied" style="color: #2e7d32;">✓ Angewendet + gespeichert</strong>
          <strong v-else style="color: #e65100;">Geparsed (Vorschau)</strong>
          <pre>{{ JSON.stringify(wizardModal.parsed, null, 2) }}</pre>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeWizard">Abbrechen</button>
          <button class="btn-primary" :disabled="!wizardModal.response" @click="parseAndApply">Parsen + Anwenden</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAiActStore } from '../../stores/aiact'

const store = useAiActStore()

const riskForm = ref<any>({ risk_id: '', titel: '', lifecycle_phase: 'design', risk_category: 'safety',
  severity: 'mittel', likelihood: 'mittel' })

const status = computed(() => store.pflichtDokuStatus)
const openRiskCount = computed(() =>
  store.aiactRisks.filter((r: any) => r.status === 'offen' || r.status === 'in-behandlung').length)

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

const reloadAll = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchSystemDoku(), store.fetchDataGovernance(), store.fetchAiactRisks(),
    store.fetchHumanOversight(), store.fetchPmm(), store.fetchPflichtDokuStatus(),
  ])
}

onMounted(async () => {
  await store.fetchUseCaseTemplates()
  await reloadAll()
})
watch(() => store.selectedProjekt, reloadAll)

const addRisk = async () => {
  if (await store.saveAiactRisk(riskForm.value)) {
    riskForm.value = { risk_id: '', titel: '', lifecycle_phase: 'design', risk_category: 'safety',
      severity: 'mittel', likelihood: 'mittel' }
    await store.fetchPflichtDokuStatus()
  }
}

const selectedUseCase = ref('')
const useCaseApplied = ref(false)
const useCaseAppliedName = ref('')
const wizardModal = ref<any>({ open: false, kind: '', title: '', prompt: '', response: '', parsed: null })

const applyUseCase = async () => {
  if (!selectedUseCase.value) return
  const tpl = store.useCaseTemplates.find((t: any) => t.id === selectedUseCase.value)
  if (await store.applyUseCaseTemplate(selectedUseCase.value)) {
    useCaseApplied.value = true
    useCaseAppliedName.value = tpl?.name || selectedUseCase.value
    await reloadAll()
    setTimeout(() => { useCaseApplied.value = false }, 6000)
  }
}

const WIZARD_TITLES: Record<string, string> = {
  'risk-tier': 'AI-Act Risk-Tier-Klassifikator',
  'eu-doc': 'EU-Konformitätserklärung (Annex V)',
  'transparency': 'Transparenz-Hinweise (Art. 50)',
}

const openWizard = async (kind: 'risk-tier' | 'eu-doc' | 'transparency') => {
  const prompt = await store.getWizardPrompt(kind)
  wizardModal.value = { open: true, kind, title: WIZARD_TITLES[kind], prompt, response: '', parsed: null }
}
const closeWizard = () => { wizardModal.value = { open: false, kind: '', title: '', prompt: '', response: '', parsed: null } }
const copyPrompt = () => navigator.clipboard?.writeText(wizardModal.value.prompt)
const parseAndApply = async () => {
  const { kind, response } = wizardModal.value
  wizardModal.value.parsed = await store.parseWizardResponse(kind, response, true)
  await store.fetchProjekte()
  await reloadAll()
  if (wizardModal.value.parsed?.applied) {
    setTimeout(closeWizard, 1200)
  }
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
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.btn-secondary { background: #eee; color: #333; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
</style>
