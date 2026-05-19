<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>📋 CRA-Pflicht-Doku — der Start für jedes CRA-Projekt</h3>
      <p>Der EU Cyber Resilience Act verlangt für jedes Produkt mit digitalen Elementen einen
        festen Satz an dokumentierten Artefakten. <strong>Diese Seite ist der erste Schritt</strong> —
        ohne sie sind die Anforderungen weiter rechts nicht sinnvoll beantwortbar.</p>

      <div class="workflow">
        <strong>Empfohlene Reihenfolge:</strong>
        <ol>
          <li><strong>1. Klassifikator (C6)</strong> ⇒ Bestimmt die Produktklasse
            (Default / Wichtig Klasse 1+2 / Kritisch). Filtert danach automatisch die
            relevanten Anforderungen im nächsten Tab.</li>
          <li><strong>2. Branchen-Template (C7)</strong> ⇒ Setzt branchenübliche
            Defaults (SLAs, Support-Jahre, Threat-Framework) in einem Klick.</li>
          <li><strong>3. SBOM / PSIRT / Vuln / Support-Period / Threat-Model (C1–C5)</strong>
            ⇒ Die 5 Pflicht-Artefakte. „🔍 Aus GitHub-Repo erkennen" füllt was es kann
            automatisch aus deinem Repo.</li>
          <li><strong>4. Vuln-Policy + Update-Policy (C8/C9)</strong> ⇒ Generieren
            fertige Markdown-Texte für SECURITY.md / docs/updates.md.</li>
        </ol>
      </div>

      <div class="storage-hint">
        <strong>Wo wird das gespeichert?</strong>
        Die Daten landen in den Modul-Datenbanken (<code>cra_sbom</code>, <code>cra_psirt</code>,
        <code>cra_vuln</code>, <code>cra_support_period</code>, <code>cra_threatmodel</code>) und im
        Projekt selbst (<code>cra_projekte.produktklasse</code>, <code>meta_json.cra.klassifikator</code>).
        Werden im Bericht-Tab automatisch eingebunden und in die CRA-Konformitätsbewertung übernommen.
      </div>
    </div>

    <!-- Auto-Detect-Action -->
    <div class="autodetect-bar">
      <div class="autodetect-info">
        <strong>🔍 Aus GitHub-Repo erkennen</strong>
        <small>Scannt SECURITY.md, Releases, Security-Advisories, Threat-Model-Dateien — füllt leere Felder automatisch.</small>
      </div>
      <input v-model="autodetectRepo" placeholder="owner/repo (optional, sonst aus Projekt-Verknüpfung)" />
      <button class="btn-secondary" :disabled="autodetectBusy" @click="runAutodetect(true)">Vorschau (Dry-Run)</button>
      <button class="btn-primary" :disabled="autodetectBusy" @click="runAutodetect(false)">{{ autodetectBusy ? '...' : 'Erkennen + Anwenden' }}</button>
    </div>

    <div v-if="autodetectResult" class="autodetect-result">
      <div>
        <strong>Funde:</strong>
        SBOM={{ autodetectResult.summary?.sbom_count || 0 }},
        PSIRT-Felder={{ autodetectResult.summary?.psirt_fields || 0 }},
        Vulns={{ autodetectResult.summary?.vuln_count || 0 }},
        Support-Period={{ autodetectResult.summary?.support_period_set ? '✓' : '–' }},
        ThreatModel={{ autodetectResult.summary?.threatmodel_set ? '✓' : '–' }}
        <span v-if="autodetectResult.applied">
          — übernommen: SBOM+{{ autodetectResult.applied.sbom }}, PSIRT+{{ autodetectResult.applied.psirt }},
          Vuln+{{ autodetectResult.applied.vuln }}, SP={{ autodetectResult.applied.support_period }},
          TM={{ autodetectResult.applied.threatmodel }}
        </span>
        <span v-else class="hint">(Dry-Run — nichts gespeichert)</span>
      </div>
      <div v-if="autodetectResult.findings?.access" class="diagnose">
        Repo-Zugang: {{ autodetectResult.findings.access.accessible ? '✓' : '✗' }}
        ({{ autodetectResult.findings.access.auth_used || 'unbekannt' }},
        Rate-Limit {{ autodetectResult.findings.access.rate_limit_hint || '?' }})
      </div>
      <div v-if="autodetectResult.findings?.warnings?.length" class="warnings">
        <strong>⚠️ Hinweise:</strong>
        <ul><li v-for="(w, i) in autodetectResult.findings.warnings" :key="i">{{ w }}</li></ul>
      </div>
    </div>

    <!-- Klassifikator-Status (#578) -->
    <div v-if="klassifikatorInfo" class="klassifikator-card">
      <div class="kl-header">
        <strong>📌 CRA-Klassifikator-Ergebnis</strong>
        <span :class="['kl-badge', `kl-${klassifikatorInfo.klasse}`]">{{ klasseLabel(klassifikatorInfo.klasse) }}</span>
        <span v-if="klassifikatorInfo.konfidenz" class="kl-confidence">Konfidenz: {{ klassifikatorInfo.konfidenz }}</span>
      </div>
      <div v-if="klassifikatorInfo.begruendung" class="kl-reason">{{ klassifikatorInfo.begruendung }}</div>
      <div v-if="klassifikatorInfo.konformitaetsbewertung" class="kl-conformity">
        Konformitäts-Bewertung: <strong>{{ klassifikatorInfo.konformitaetsbewertung }}</strong>
      </div>
      <div v-if="klassifikatorInfo.indikatoren?.length" class="kl-indicators">
        <em>Indikatoren:</em> {{ klassifikatorInfo.indikatoren.join(' · ') }}
      </div>
    </div>

    <!-- Status-Übersicht -->
    <div v-if="status" class="status-grid">
      <div v-for="b in statusItems" :key="b.key" :class="['status-card', b.ok ? 'ok' : 'todo']">
        <div class="status-icon">{{ b.ok ? '✅' : '⚠️' }}</div>
        <div class="status-label">{{ b.label }}</div>
        <div class="status-detail">{{ b.detail }}</div>
      </div>
    </div>

    <!-- C1: SBOM -->
    <details class="section" open>
      <summary><strong>C1 — SBOM-Verzeichnis</strong> ({{ store.sboms.length }} Einträge)</summary>
      <div class="section-body">
        <div class="form-grid">
          <input v-model="sbomForm.release_version" placeholder="Release-Version (z.B. 1.2.0)" />
          <select v-model="sbomForm.sbom_format">
            <option value="spdx">SPDX</option>
            <option value="cyclonedx">CycloneDX</option>
          </select>
          <input v-model.number="sbomForm.komponenten_count" type="number" placeholder="Komponenten-Anzahl" />
          <input v-model="sbomForm.quelle" placeholder="Quelle (z.B. ci-artifact:gh-run-1234)" />
          <input v-model="sbomForm.blob_path" placeholder="Pfad zur SBOM-Datei" />
          <input v-model="sbomLizenzenInput" placeholder="Lizenzen (Komma-getrennt: MIT, Apache-2.0)" />
          <button class="btn-primary" @click="addSbom">SBOM hinzufügen</button>
        </div>
        <table class="sbom-table">
          <thead><tr><th>Release</th><th>Format</th><th>Komp.</th><th>Datum</th><th>Quelle</th><th></th></tr></thead>
          <tbody>
            <tr v-for="s in store.sboms" :key="s.id">
              <td>{{ s.release_version }}</td>
              <td>{{ s.sbom_format }}</td>
              <td>{{ s.komponenten_count }}</td>
              <td>{{ (s.sbom_datum || '').slice(0,10) }}</td>
              <td>{{ s.quelle }}</td>
              <td><button class="btn-link" @click="store.deleteSbom(s.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- C2: PSIRT -->
    <details ref="psirtSection" class="section">
      <summary><strong>C2 — PSIRT-Prozess</strong> {{ store.psirt.intake_kanal ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="form-grid">
          <input v-model="store.psirt.intake_kanal" placeholder="Intake-Kanal (z.B. security@example.com)" />
          <input v-model="store.psirt.triage_sla" placeholder="Triage-SLA (z.B. 24h)" />
          <input v-model="store.psirt.fix_sla_critical" placeholder="Fix-SLA Critical (z.B. 7 Tage)" />
          <input v-model="store.psirt.fix_sla_high" placeholder="Fix-SLA High" />
          <input v-model="store.psirt.fix_sla_medium" placeholder="Fix-SLA Medium" />
          <input v-model="store.psirt.disclosure_policy_url" placeholder="Disclosure-Policy-URL" />
          <input v-model="store.psirt.security_md_url" placeholder="SECURITY.md-URL" />
          <textarea v-model="store.psirt.notizen" placeholder="Notizen" rows="2" />
        </div>
        <button class="btn-primary" @click="store.savePsirt(store.psirt)">Speichern</button>
      </div>
    </details>

    <!-- C3: Vuln-Tracker -->
    <details class="section">
      <summary><strong>C3 — Vulnerability-Tracker</strong> ({{ openVulnCount }}/{{ store.vulns.length }} offen)</summary>
      <div class="section-body">
        <div class="form-grid">
          <input v-model="vulnForm.cve_id" placeholder="CVE-ID (z.B. CVE-2026-1234)" />
          <input v-model="vulnForm.titel" placeholder="Titel" />
          <select v-model="vulnForm.schwere">
            <option value="low">low</option><option value="medium">medium</option>
            <option value="high">high</option><option value="critical">critical</option>
            <option value="unknown">unknown</option>
          </select>
          <input v-model.number="vulnForm.cvss_score" type="number" step="0.1" placeholder="CVSS-Score" />
          <input v-model="vulnForm.affected_component" placeholder="Betroffene Komponente" />
          <input v-model="vulnForm.fixed_in_version" placeholder="Fixed in Version" />
          <select v-model="vulnForm.status">
            <option value="open">open</option><option value="triaging">triaging</option>
            <option value="fixed">fixed</option><option value="disclosed">disclosed</option>
            <option value="wontfix">wontfix</option>
          </select>
          <button class="btn-primary" @click="addVuln">Hinzufügen</button>
        </div>
        <table class="vuln-table">
          <thead><tr><th>CVE</th><th>Schwere</th><th>CVSS</th><th>Komponente</th><th>Status</th><th>Fix in</th><th></th></tr></thead>
          <tbody>
            <tr v-for="v in store.vulns" :key="v.id" :class="`vuln-${v.status}`">
              <td>{{ v.cve_id }}</td>
              <td><span :class="`sev sev-${v.schwere}`">{{ v.schwere }}</span></td>
              <td>{{ v.cvss_score }}</td>
              <td>{{ v.affected_component }}</td>
              <td>
                <select :value="v.status" @change="updateVulnStatus(v, ($event.target as HTMLSelectElement).value)">
                  <option value="open">open</option><option value="triaging">triaging</option>
                  <option value="fixed">fixed</option><option value="disclosed">disclosed</option>
                  <option value="wontfix">wontfix</option>
                </select>
              </td>
              <td>{{ v.fixed_in_version }}</td>
              <td><button class="btn-link" @click="store.deleteVuln(v.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- C4: Support-Period -->
    <details ref="spSection" class="section">
      <summary><strong>C4 — Support-Period</strong> {{ store.supportPeriod.eol_datum ? `bis ${store.supportPeriod.eol_datum}` : '' }}</summary>
      <div class="section-body">
        <div class="form-grid">
          <input v-model="store.supportPeriod.markteintritt_datum" type="date" />
          <input v-model.number="store.supportPeriod.support_jahre" type="number" placeholder="Support-Jahre (CRA Default: 5)" />
          <input v-model="store.supportPeriod.update_kanal" placeholder="Update-Kanal (z.B. Auto-Update)" />
          <textarea v-model="store.supportPeriod.rationale" placeholder="Rationale (Begründung)" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveSupportPeriod(store.supportPeriod)">Speichern (EOL wird berechnet)</button>
        <p v-if="store.supportPeriod.eol_datum" class="hint">
          → End-of-Support: <strong>{{ store.supportPeriod.eol_datum }}</strong>
        </p>
      </div>
    </details>

    <!-- C5: Threat-Model -->
    <details class="section">
      <summary><strong>C5 — Threat-Model</strong> {{ store.threatModel.framework || '' }}</summary>
      <div class="section-body">
        <div class="form-grid">
          <select v-model="store.threatModel.framework">
            <option value="STRIDE">STRIDE</option>
            <option value="PASTA">PASTA</option>
            <option value="LINDDUN">LINDDUN</option>
          </select>
          <input v-model="store.threatModel.diagram_url" placeholder="Diagram-URL (optional)" />
          <textarea v-model="store.threatModel.scope" placeholder="Scope" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveThreatModel(store.threatModel)">Speichern</button>
      </div>
    </details>

    <!-- Phase B — KI-Wizards -->
    <details class="section wizards" open>
      <summary><strong>🤖 KI-Assistenten</strong> — Klassifikator + Branchen-Templates + Policy-Generatoren</summary>
      <div class="section-body">

        <div class="wizard-card">
          <h4>C6 — CRA-Klassifikator</h4>
          <p>Bestimmt automatisch die Produktklasse (default / Annex III Klasse I+II / Annex IV).</p>
          <div class="wizard-actions">
            <button class="btn-primary" @click="openWizard('klassifikator')">Prompt generieren</button>
          </div>
        </div>

        <div class="wizard-card">
          <h4>C7 — Branchen-Template anwenden</h4>
          <p>Setzt sinnvolle Defaults für PSIRT-SLAs, Support-Jahre und Threat-Framework je Branche.</p>
          <div class="wizard-actions">
            <select v-model="selectedBranche">
              <option value="">— Branche wählen —</option>
              <option v-for="t in store.branchenTemplates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
            <button class="btn-primary" :disabled="!selectedBranche" @click="applyBranche">Anwenden</button>
          </div>
          <div v-if="brancheApplied" class="branche-applied">
            ✅ Template <strong>{{ brancheAppliedName }}</strong> angewendet — folgende Defaults wurden gesetzt:
            <ul>
              <li v-for="(v, k) in brancheAppliedDefaults" :key="k"><strong>{{ k }}</strong>: {{ v }}</li>
            </ul>
          </div>
        </div>

        <div class="wizard-card">
          <h4>C8 — Vulnerability-Disclosure-Policy</h4>
          <p>Generiert einen vollständigen Policy-Text passend zur PSIRT-Konfiguration.</p>
          <div class="wizard-actions">
            <button class="btn-primary" @click="openWizard('vuln-policy')">Prompt generieren</button>
          </div>
        </div>

        <div class="wizard-card">
          <h4>C9 — Security-Update-Policy</h4>
          <p>Generiert eine Update-Policy mit Kadenz, Out-of-Band-Verfahren und EOL-Kommunikation.</p>
          <div class="wizard-actions">
            <button class="btn-primary" @click="openWizard('update-policy')">Prompt generieren</button>
          </div>
        </div>
      </div>
    </details>

    <!-- Wizard-Dialog -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @click.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <p class="hint">1. Kopiere den Prompt nach ChatGPT. 2. Antwort als JSON hier einfügen. 3. „Anwenden" speichert das Ergebnis.</p>

        <label>Prompt (zum Kopieren)</label>
        <textarea readonly :value="wizardModal.prompt" rows="8" class="mono"></textarea>
        <button class="btn-link" @click="copyPrompt">📋 Kopieren</button>

        <label>ChatGPT-Antwort (JSON)</label>
        <textarea v-model="wizardModal.response" rows="6" class="mono" placeholder="Hier die ChatGPT-Antwort einfügen..."></textarea>

        <div v-if="wizardModal.parsed" class="parsed-result">
          <strong v-if="wizardModal.parsed.applied" style="color: #2e7d32;">✓ Angewendet + gespeichert</strong>
          <strong v-else style="color: #e65100;">Geparsed (nur Vorschau, nicht gespeichert)</strong>
          <pre>{{ JSON.stringify(wizardModal.parsed, null, 2) }}</pre>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeWizard">Abbrechen</button>
          <button class="btn-secondary" :disabled="!wizardModal.response" @click="parseOnly">Nur parsen</button>
          <button class="btn-primary" :disabled="!wizardModal.response" @click="parseAndApply">Parsen + Anwenden</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCraStore } from '../../stores/cra'

const store = useCraStore()

const sbomForm = ref({ release_version: '', sbom_format: 'spdx', komponenten_count: 0, quelle: '', blob_path: '' })
const sbomLizenzenInput = ref('')
const vulnForm = ref({ cve_id: '', titel: '', schwere: 'unknown', cvss_score: 0, affected_component: '', fixed_in_version: '', status: 'open' })

// #578: Sections-Refs für programmatisches Aufklappen + Klassifikator-Anzeige
const psirtSection = ref<HTMLDetailsElement | null>(null)
const spSection = ref<HTMLDetailsElement | null>(null)

const klassifikatorInfo = computed(() => {
  try {
    const meta = JSON.parse(store.selectedProjektObj?.meta_json || '{}')
    return meta?.cra?.klassifikator || null
  } catch { return null }
})

const KLASSE_LABELS: Record<string, string> = {
  default: 'Default — Annex I',
  important_i: 'Wichtig Klasse 1 (Annex III)',
  important_ii: 'Wichtig Klasse 2 (Annex III)',
  critical: 'Kritisch (Annex IV)',
}
const klasseLabel = (k: string) => KLASSE_LABELS[k] || k

const status = computed(() => store.pflichtDokuStatus)
const openVulnCount = computed(() => store.vulns.filter((v: any) => v.status === 'open' || v.status === 'triaging').length)

const statusItems = computed(() => {
  const s = status.value
  if (!s) return []
  return [
    { key: 'sbom', label: 'SBOM', ok: s.sbom?.ok, detail: `${s.sbom?.count || 0} Releases` },
    { key: 'psirt', label: 'PSIRT', ok: s.psirt?.ok, detail: s.psirt?.ok ? 'aktiv' : 'fehlt' },
    { key: 'vuln', label: 'Vulns', ok: s.vuln?.ok, detail: `${s.vuln?.open || 0} offen` },
    { key: 'sp', label: 'Support-Period', ok: s.support_period?.ok, detail: s.support_period?.eol || 'EOL fehlt' },
    { key: 'tm', label: 'Threat-Model', ok: s.threatmodel?.ok, detail: s.threatmodel?.ok ? 'dokumentiert' : 'fehlt' },
  ]
})

const reloadAll = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchSboms(),
    store.fetchPsirt(),
    store.fetchVulns(),
    store.fetchSupportPeriod(),
    store.fetchThreatModel(),
    store.fetchPflichtDokuStatus(),
  ])
}

onMounted(reloadAll)
watch(() => store.selectedProjekt, reloadAll)

const addSbom = async () => {
  const payload = {
    ...sbomForm.value,
    lizenzen: sbomLizenzenInput.value.split(',').map(s => s.trim()).filter(Boolean),
  }
  const ok = await store.saveSbom(payload)
  if (ok) {
    sbomForm.value = { release_version: '', sbom_format: 'spdx', komponenten_count: 0, quelle: '', blob_path: '' }
    sbomLizenzenInput.value = ''
    await store.fetchPflichtDokuStatus()
  }
}

const addVuln = async () => {
  const ok = await store.saveVuln({ ...vulnForm.value })
  if (ok) {
    vulnForm.value = { cve_id: '', titel: '', schwere: 'unknown', cvss_score: 0, affected_component: '', fixed_in_version: '', status: 'open' }
    await store.fetchPflichtDokuStatus()
  }
}

const updateVulnStatus = async (v: any, newStatus: string) => {
  await store.saveVuln({ ...v, status: newStatus, fixed_at: newStatus === 'fixed' ? new Date().toISOString().slice(0,10) : v.fixed_at })
  await store.fetchPflichtDokuStatus()
}

// #558 Auto-Detect
const autodetectRepo = ref('')
const autodetectBusy = ref(false)
const autodetectResult = ref<any | null>(null)

const runAutodetect = async (dryRun: boolean) => {
  autodetectBusy.value = true
  autodetectResult.value = null
  try {
    autodetectResult.value = await store.autodetectPflichtDoku(autodetectRepo.value, dryRun)
    if (!dryRun) await reloadAll()
  } finally {
    autodetectBusy.value = false
  }
}

// Phase B — KI-Wizards
const selectedBranche = ref('')
const brancheApplied = ref(false)
const brancheAppliedName = ref('')
const brancheAppliedDefaults = ref<Record<string, any>>({})
const wizardModal = ref<any>({ open: false, kind: '', title: '', prompt: '', response: '', parsed: null })

onMounted(() => store.fetchBranchenTemplates())

const applyBranche = async () => {
  if (!selectedBranche.value) return
  const tpl = store.branchenTemplates.find((t: any) => t.id === selectedBranche.value)
  const ok = await store.applyBranchenTemplate(selectedBranche.value)
  if (ok) {
    brancheApplied.value = true
    brancheAppliedName.value = tpl?.name || selectedBranche.value
    brancheAppliedDefaults.value = tpl?.pflicht_doku_defaults || {}
    await reloadAll()
    setTimeout(() => { brancheApplied.value = false }, 8000)
  }
}

const wizardTitles: Record<string, string> = {
  'klassifikator': 'CRA-Klassifikator',
  'vuln-policy': 'Vulnerability-Disclosure-Policy',
  'update-policy': 'Security-Update-Policy',
}

const openWizard = async (kind: 'klassifikator' | 'vuln-policy' | 'update-policy') => {
  const prompt = await store.getWizardPrompt(kind)
  wizardModal.value = { open: true, kind, title: wizardTitles[kind], prompt, response: '', parsed: null }
}

const closeWizard = () => { wizardModal.value = { open: false, kind: '', title: '', prompt: '', response: '', parsed: null } }

const copyPrompt = () => navigator.clipboard?.writeText(wizardModal.value.prompt)

const parseOnly = async () => {
  wizardModal.value.parsed = await store.parseWizardResponse(wizardModal.value.kind, wizardModal.value.response, false)
}

const parseAndApply = async () => {
  const kind = wizardModal.value.kind
  wizardModal.value.parsed = await store.parseWizardResponse(kind, wizardModal.value.response, true)
  // Projekt-Daten neu laden (Klassifikator schreibt in projekt.produktklasse + meta)
  await store.fetchProjekte()
  await reloadAll()
  // #578: nach Apply die richtige Section aufklappen + ins Viewport scrollen
  if (wizardModal.value.parsed?.applied) {
    setTimeout(() => {
      closeWizard()
      if (kind === 'vuln-policy' && psirtSection.value) {
        psirtSection.value.open = true
        psirtSection.value.scrollIntoView({ behavior: 'smooth', block: 'center' })
      } else if (kind === 'update-policy' && spSection.value) {
        spSection.value.open = true
        spSection.value.scrollIntoView({ behavior: 'smooth', block: 'center' })
      } else if (kind === 'klassifikator') {
        document.querySelector('.klassifikator-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 1200) // 1.2s sichtbares Feedback im Modal, dann Auto-Close
  }
}
</script>

<style scoped>
.pflicht-doku { display: flex; flex-direction: column; gap: 16px; }
.info-banner { background: #e3f2fd; padding: 16px 20px; border-radius: 8px; border-left: 4px solid #1565c0; }
.info-banner h3 { margin: 0 0 8px; color: #1565c0; }
.info-banner p { margin: 0 0 12px; color: #444; line-height: 1.5; }
.workflow {
  background: white; padding: 12px 18px; border-radius: 6px; margin: 12px 0;
  font-size: 14px;
}
.workflow strong { color: #0d47a1; }
.workflow ol { margin: 8px 0 0 0; padding-left: 22px; }
.workflow li { margin: 6px 0; color: #333; line-height: 1.5; }
.storage-hint {
  background: #f5f5f5; padding: 10px 14px; border-radius: 4px; margin-top: 12px;
  font-size: 13px; color: #555; line-height: 1.6;
}
.storage-hint code { background: #e8eaf6; padding: 1px 5px; border-radius: 3px; color: #1a237e; font-size: 12px; }

.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.status-card { padding: 14px; border-radius: 8px; text-align: center; border: 2px solid; }
.status-card.ok { background: #e8f5e9; border-color: #4caf50; }
.status-card.todo { background: #fff3e0; border-color: #ff9800; }
.status-icon { font-size: 28px; }
.status-label { font-weight: 600; margin-top: 4px; }
.status-detail { font-size: 12px; color: #666; margin-top: 4px; }

.section { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 12px 16px; }
.section summary { cursor: pointer; padding: 8px 0; font-size: 15px; user-select: none; }
.section-body { padding-top: 12px; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin-bottom: 12px; }
.form-grid input, .form-grid select, .form-grid textarea {
  padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit;
}
.form-grid textarea { grid-column: 1 / -1; }

.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #0d47a1; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 16px; }

table { width: 100%; border-collapse: collapse; margin-top: 12px; }
table th, table td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #eee; }
table th { background: #f5f5f5; font-weight: 600; }

.sev { padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: 600; }
.sev-low { background: #e3f2fd; color: #1565c0; }
.sev-medium { background: #fff3e0; color: #e65100; }
.sev-high { background: #ffe0e0; color: #c62828; }
.sev-critical { background: #c62828; color: white; }
.sev-unknown { background: #eee; color: #666; }

.vuln-fixed { opacity: 0.6; }
.vuln-wontfix { opacity: 0.5; font-style: italic; }

.hint { color: #666; font-size: 13px; margin-top: 8px; }

.autodetect-bar {
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  background: #fff8e1; border: 1px solid #ffc107; border-radius: 8px; flex-wrap: wrap;
}
.autodetect-info { display: flex; flex-direction: column; flex: 1; min-width: 220px; }
.autodetect-info strong { color: #e65100; }
.autodetect-info small { color: #666; font-size: 12px; }
.autodetect-bar input { flex: 1; min-width: 200px; padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; }
.autodetect-result {
  padding: 10px 14px; background: #e8f5e9; border-left: 4px solid #4caf50;
  border-radius: 4px; font-size: 13px;
}

.wizards { background: #f3e5f5; border-color: #ce93d8; }
.wizard-card { background: white; padding: 14px; border-radius: 6px; margin-bottom: 12px; border-left: 4px solid #7b1fa2; }
.wizard-card h4 { margin: 0 0 6px; color: #4a148c; }
.wizard-card p { margin: 0 0 10px; color: #555; font-size: 13px; }
.wizard-actions { display: flex; gap: 8px; align-items: center; }

.wizard-modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.wizard-modal {
  background: white; padding: 24px; border-radius: 10px; max-width: 800px; width: 90%; max-height: 90vh; overflow-y: auto;
}
.wizard-modal h3 { margin: 0 0 8px; color: #4a148c; }
.wizard-modal label { display: block; margin-top: 12px; font-weight: 600; font-size: 13px; }
.wizard-modal textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.wizard-modal .mono { font-family: monospace; font-size: 12px; }

.parsed-result { background: #e8f5e9; padding: 12px; border-radius: 4px; margin-top: 12px; }
.parsed-result pre { margin: 6px 0 0; white-space: pre-wrap; font-size: 12px; }

.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.btn-secondary { background: #eee; color: #333; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary:hover { background: #ddd; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.klassifikator-card {
  background: #e8eaf6; border: 2px solid #3f51b5; border-radius: 8px;
  padding: 14px 18px; display: flex; flex-direction: column; gap: 8px;
}
.kl-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.kl-badge {
  padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 13px;
}
.kl-default { background: #e0e0e0; color: #424242; }
.kl-important_i { background: #fff3e0; color: #e65100; }
.kl-important_ii { background: #ffe0b2; color: #bf360c; }
.kl-critical { background: #ffcdd2; color: #b71c1c; }
.kl-confidence { color: #666; font-size: 12px; }
.kl-reason { color: #1a237e; font-size: 14px; }
.kl-conformity { color: #283593; font-size: 13px; }
.kl-indicators { color: #555; font-size: 12px; font-style: italic; }

.branche-applied {
  background: #e8f5e9; border-left: 4px solid #4caf50; padding: 10px 14px;
  border-radius: 4px; margin-top: 10px; font-size: 13px;
}
.branche-applied ul { margin: 6px 0 0 18px; padding: 0; }
</style>
