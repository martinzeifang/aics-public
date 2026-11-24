<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>{{ $t('nis2.nIS2PflichtDokuPanel.nIS2DokumentationHierStarten') }}</h3>
      <p>{{ $t('nis2.nIS2PflichtDokuPanel.nIS2DirectiveEUVerlangtVonWesentlich') }} <strong>{{ $t('common.dieseSeiteIstDerErsteSchritt') }}</strong>.</p>
      <div class="workflow">
        <strong>{{ $t('common.reihenfolge') }}</strong>
        <ol>
          <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n1AssetInventar') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.alleITOTDatenCloudAssetsImScopeErfas') }}</li>
          <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n2RisikoRegister') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.proAssetRisikenBewertenMatrix') }}</li>
          <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n3IncidentResponsePlan') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.cSIRTKontaktHHMMeldepflichtSetup') }}</li>
          <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n4SupplyChainSecurity') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.vendorListeAssessmentZertifikate') }}</li>
          <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n5BusinessContinuityPlan') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.rPORTOBackupDRKrisenstab') }}</li>
        </ol>
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

    <!-- N1 Asset-Inventar -->
    <details class="section" open>
      <summary><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n1AssetInventar2') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.v0Assets', { v0: store.assets.length }) }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.nIS2ArtLitAVerlangtEineVollstandigeB') }}
          <span class="initiale">{{ $t('nis2.nIS2PflichtDokuPanel.vertraulichkeit') }}</span> /
          <span class="initiale">{{ $t('nis2.nIS2PflichtDokuPanel.integritaet') }}</span> /
          <span class="initiale">{{ $t('nis2.nIS2PflichtDokuPanel.verfuegbarkeit') }}</span>
          {{ $t('nis2.nIS2PflichtDokuPanel.jeweilsNormalHochSehrHoch') }}
          <br><em>{{ $t('nis2.nIS2PflichtDokuPanel.basisFurAlleAnderenBereicheOhneAsset') }}</em>
        </div>
        <!-- #1072: Repo-Scan (Asset-Wizard #1095 → Assistenten-Tab) -->
        <div class="scan-bar">
          <button class="btn-secondary" :disabled="scanBusy" @click="scanAssets">{{ $t('nis2.nIS2PflichtDokuPanel.repoScannenComposeHelmK8sTerraformTo') }}</button>
          <span v-if="scanMsg.n1" class="scan-msg">{{ scanMsg.n1 }}</span>
        </div>
        <div v-if="assetSuggestions.length" class="suggest-box">
          <strong>{{ $t('nis2.nIS2PflichtDokuPanel.v0Vorschlage', { v0: assetSuggestions.length }) }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.ubernehmen') }}
          <ul>
            <li v-for="(s, i) in assetSuggestions" :key="`as-${i}`">
              <button class="btn-link" @click="applyAssetSuggestion(s)">+ {{ s.asset_name }}</button>
              <small>({{ s.asset_typ }}, {{ s.kritikalitaet }}) — {{ s.source_path }}</small>
            </li>
          </ul>
        </div>
        <div class="form-grid">
          <input v-model="assetForm.asset_name" placeholder="Asset-Name (z.B. Web-Server, ERP-DB)" />
          <select v-model="assetForm.asset_typ">
            <option value="it">IT</option><option value="ot">OT</option>
            <option value="daten">{{ $t('nis2.nIS2PflichtDokuPanel.daten') }}</option><option value="cloud-service">{{ $t('nis2.nIS2PflichtDokuPanel.cloudService') }}</option>
            <option value="netzwerk">{{ $t('nis2.nIS2PflichtDokuPanel.netzwerk') }}</option><option value="personen">{{ $t('nis2.nIS2PflichtDokuPanel.personen') }}</option>
          </select>
          <select v-model="assetForm.kritikalitaet">
            <option value="niedrig">{{ $t('common.niedrig') }}</option><option value="mittel">{{ $t('common.mittel') }}</option>
            <option value="hoch">{{ $t('common.hoch') }}</option><option value="kritisch">{{ $t('common.kritisch') }}</option>
          </select>
          <input v-model="assetForm.verantwortlich" :placeholder="$t('common.verantwortlich')" />
          <input v-model="assetForm.standort" :placeholder="$t('nis2.nIS2PflichtDokuPanel.standort')" />
          <input v-model.number="assetForm.schutzbedarf_v" type="number" min="1" max="3" placeholder="V (1-3)" />
          <input v-model.number="assetForm.schutzbedarf_i" type="number" min="1" max="3" placeholder="I (1-3)" />
          <input v-model.number="assetForm.schutzbedarf_a" type="number" min="1" max="3" placeholder="A (1-3)" />
          <button class="btn-primary" @click="addAsset">{{ $t('nis2.nIS2PflichtDokuPanel.assetHinzufugen') }}</button>
        </div>
        <table>
          <thead><tr><th>{{ $t('common.name') }}</th><th>{{ $t('common.typ') }}</th><th>{{ $t('nis2.nIS2PflichtDokuPanel.krit') }}</th><th>V/I/A</th><th>{{ $t('common.verantwortlich') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in store.assets" :key="a.id">
              <td>{{ a.asset_name }}</td>
              <td>{{ a.asset_typ }}</td>
              <td><span :class="`crit crit-${a.kritikalitaet}`">{{ a.kritikalitaet }}</span></td>
              <td>{{ a.schutzbedarf_v }}/{{ a.schutzbedarf_i }}/{{ a.schutzbedarf_a }}</td>
              <td>{{ a.verantwortlich }}</td>
              <td><button class="btn-link" @click="store.deleteAsset(a.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- N2 Risiko-Register -->
    <details class="section">
      <summary><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n2RisikoRegister2') }}</strong> ({{ openRisikoCount }}/{{ store.risiken.length }} offen)</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.nIS2ArtLitBVerlangtEinDokumentiertes') }} <code>offen</code> → <code>in-behandlung</code> → <code>akzeptiert</code> {{ $t('nis2.nIS2PflichtDokuPanel.oder') }} <code>mitigiert</code>.
          <br><em>{{ $t('nis2.nIS2PflichtDokuPanel.auditorWillSehenJedesKritischeAssetH') }}</em>
        </div>
        <!-- S7 (#1077): Manuelle N2-Risikoverwaltung deaktiviert. Risiken werden ab
             Sprint #21 zentral in der Risikobewertung gepflegt und im Risiko-Cockpit
             aggregiert. Bestands-Einträge bleiben read-only sichtbar. -->
        <div class="help-box info">
          ℹ️ <strong>{{ $t('nis2.nIS2PflichtDokuPanel.dieseRisikenWerdenAbSprintNichtMehrM') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.pflegenSieRisikenInDer') }} <strong>{{ $t('nav.risikobewertung.label') }}</strong>{{ $t('nis2.nIS2PflichtDokuPanel.das') }}
          <strong>{{ $t('nis2.nIS2PflichtDokuPanel.risikoCockpit') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.zeigtSieAggregiertDieFolgendeListeIs') }}
        </div>
        <div class="rb-import-bar">
          <span>{{ $t('nis2.nIS2PflichtDokuPanel.risikenAusDem') }} <strong>{{ $t('nis2.nIS2PflichtDokuPanel.risikobewertungsModul') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.alsAltBestandUbernehmen') }}</span>
          <button class="btn-secondary" @click="openRbImport">{{ $t('nis2.nIS2PflichtDokuPanel.ausRBImportieren') }}</button>
        </div>
        <!-- #2062 -->
        <div v-if="store.risiken.length" class="tabelle-scroll">
        <table>
          <thead><tr><th>ID</th><th>{{ $t('common.titel') }}</th><th>{{ $t('nis2.nIS2PflichtDokuPanel.asset') }}</th><th>{{ $t('nis2.nIS2PflichtDokuPanel.score') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('common.quelle') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in store.risiken" :key="r.id">
              <td><code>{{ r.risiko_id }}</code></td>
              <td>{{ r.titel }}</td>
              <td>{{ r.asset_ref }}</td>
              <td><span :class="`score score-${scoreClass(r.risikoscore)}`">{{ r.risikoscore }}</span></td>
              <td><span class="status-readonly">{{ r.status }}</span></td>
              <td>
                <span v-if="riskQuelle(r)" class="quelle-badge" :title="riskQuelle(r)">{{ riskQuelle(r) }}</span>
                <span v-else class="hint">manuell</span>
              </td>
              <td>
                <button class="btn-del" :title="$t('nis2.nIS2PflichtDokuPanel.risikoLoschen')" @click="onDeleteRisiko(r)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
        </div>
        <p v-else class="hint">{{ $t('nis2.nIS2PflichtDokuPanel.keineAltEintrageImNIS2RisikoRegister') }}</p>
      </div>
    </details>

    <!-- N3 Incident-Response -->
    <details class="section">
      <summary><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n3IncidentResponsePlan2') }}</strong> {{ store.incidentResponse.csirt_kontakt ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.nIS2ArtVerlangtEine') }} <strong>{{ $t('nis2.nIS2PflichtDokuPanel.dreistufigeMeldepflicht') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.beiJedemSignifikantenCyberVorfallAnD') }}
          <ul style="margin: 6px 0 0 16px;">
            <li><strong>24h</strong>{{ $t('nis2.nIS2PflichtDokuPanel.fruhwarnungEsIstWasPassiertDetailsFo') }}</li>
            <li><strong>72h</strong>{{ $t('nis2.nIS2PflichtDokuPanel.notificationMitErsterSchadensEinscha') }}</li>
            <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.monat') }}</strong>{{ $t('nis2.nIS2PflichtDokuPanel.finalReportMitRootCauseLessonsLearne') }}</li>
          </ul>
          <em>{{ $t('nis2.nIS2PflichtDokuPanel.hierDefinierstDuKontaktSLAsEskalatio') }} <strong>{{ $t('nis2.nIS2PflichtDokuPanel.wizardN8') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.automatisch') }}</em>
        </div>
        <!-- #1074: SECURITY.md-Scan für CSIRT-Kontakt-Defaults -->
        <div class="scan-bar">
          <button class="btn-secondary" :disabled="scanBusy" @click="scanIncidentResponse">{{ $t('nis2.nIS2PflichtDokuPanel.sECURITYMdScannenCSIRTKontakt') }}</button>
          <span v-if="scanMsg.n3" class="scan-msg">{{ scanMsg.n3 }}</span>
        </div>
        <div class="form-grid">
          <input v-model="store.incidentResponse.csirt_kontakt" :placeholder="$t('nis2.nIS2PflichtDokuPanel.cSIRTKontaktZBCERTBundBSI')" />
          <input v-model="store.incidentResponse.csirt_email" :placeholder="$t('nis2.nIS2PflichtDokuPanel.cSIRTEMail')" />
          <input v-model="store.incidentResponse.early_warning_sla" placeholder="Early-Warning-SLA (Default: 24h)" />
          <input v-model="store.incidentResponse.notification_sla" placeholder="Notification-SLA (Default: 72h)" />
          <input v-model="store.incidentResponse.final_report_sla" placeholder="Final-Report-SLA (Default: 1 Monat)" />
          <input v-model="store.incidentResponse.incident_manager" :placeholder="$t('nis2.nIS2PflichtDokuPanel.incidentManager')" />
          <input v-model="store.incidentResponse.playbook_url" :placeholder="$t('nis2.nIS2PflichtDokuPanel.playbookURL')" />
          <textarea v-model="store.incidentResponse.eskalation_pfad" :placeholder="$t('nis2.nIS2PflichtDokuPanel.eskalationspfadMarkdown')" rows="2" />
        </div>
        <button class="btn-primary" @click="store.saveIncidentResponse(store.incidentResponse)">{{ $t('common.save') }}</button>
      </div>
    </details>

    <!-- N4 Supply-Chain -->
    <details class="section">
      <summary><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n4SupplyChainSecurity2') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.v0Vendors', { v0: store.vendors.length }) }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.nIS2ArtLitDVerlangtExplizit') }}
          <strong>{{ $t('nis2.nIS2PflichtDokuPanel.lieferkettenSicherheit') }}</strong>{{ $t('nis2.nIS2PflichtDokuPanel.alleDrittanbieterCloudSaaSMSPHardwar') }}
          <br><em>{{ $t('nis2.nIS2PflichtDokuPanel.hierLegstDuDieVendorenAnDasEigentlic') }} <strong>{{ $t('nis2.nIS2PflichtDokuPanel.wizardN9') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.perChatGPT') }}</em>
        </div>
        <!-- #1075: SBOM + package.json/requirements.txt → Vendor-Vorschläge -->
        <div class="scan-bar">
          <button class="btn-secondary" :disabled="scanBusy" @click="scanVendors">{{ $t('nis2.nIS2PflichtDokuPanel.repoScannenSBOMDependencies') }}</button>
          <span v-if="scanMsg.n4" class="scan-msg">{{ scanMsg.n4 }}</span>
        </div>
        <div v-if="vendorSuggestions.length" class="suggest-box">
          <strong>{{ $t('nis2.nIS2PflichtDokuPanel.v0VendorVorschlage', { v0: vendorSuggestions.length }) }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.ubernehmen') }}
          <ul>
            <li v-for="(s, i) in vendorSuggestions" :key="`vs-${i}`">
              <button class="btn-link" @click="applyVendorSuggestion(s)">+ {{ s.vendor_name }}</button>
              <small>{{ s.leistung }} — {{ s.source_path }}</small>
            </li>
          </ul>
        </div>
        <div class="form-grid">
          <input v-model="vendorForm.vendor_name" :placeholder="$t('nis2.nIS2PflichtDokuPanel.vendorName')" />
          <input v-model="vendorForm.leistung" :placeholder="$t('common.leistung')" />
          <select v-model="vendorForm.kritikalitaet">
            <option value="niedrig">{{ $t('common.niedrig') }}</option><option value="mittel">{{ $t('common.mittel') }}</option>
            <option value="hoch">{{ $t('common.hoch') }}</option><option value="kritisch">{{ $t('common.kritisch') }}</option>
          </select>
          <input v-model.number="vendorForm.assessment_score" type="number" min="0" max="100" :placeholder="$t('nis2.nIS2PflichtDokuPanel.score2')" />
          <input v-model="vendorZertifikateInput" :placeholder="$t('nis2.nIS2PflichtDokuPanel.zertifikateZBISO27001SOC2')" />
          <input v-model="vendorForm.sla_url" :placeholder="$t('nis2.nIS2PflichtDokuPanel.sLAURL')" />
          <input v-model="vendorForm.dpa_url" :placeholder="$t('nis2.nIS2PflichtDokuPanel.dPAURL')" />
          <button class="btn-primary" @click="addVendor">{{ $t('nis2.nIS2PflichtDokuPanel.vendorHinzufugen') }}</button>
        </div>
        <table>
          <thead><tr><th>{{ $t('common.name') }}</th><th>{{ $t('common.leistung') }}</th><th>{{ $t('nis2.nIS2PflichtDokuPanel.krit') }}</th><th>{{ $t('nis2.nIS2PflichtDokuPanel.score') }}</th><th>{{ $t('nis2.nIS2PflichtDokuPanel.zertifikate') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="v in store.vendors" :key="v.id">
              <td>{{ v.vendor_name }}</td>
              <td>{{ v.leistung }}</td>
              <td><span :class="`crit crit-${v.kritikalitaet}`">{{ v.kritikalitaet }}</span></td>
              <td>{{ v.assessment_score }}</td>
              <td>{{ (v.zertifikate || []).join(', ') }}</td>
              <td><button class="btn-link" @click="store.deleteVendor(v.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- N5 BCP -->
    <details class="section">
      <summary><strong>{{ $t('nis2.nIS2PflichtDokuPanel.n5BusinessContinuityPlan2') }}</strong> {{ store.bcp.backup_strategie ? `RPO ${store.bcp.rpo_minuten}min · RTO ${store.bcp.rto_minuten}min` : '' }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.nIS2ArtLitCVerlangtEinen') }}
          <strong>{{ $t('nis2.nIS2PflichtDokuPanel.businessContinuityUndDisasterRecover') }}</strong>{{ $t('nis2.nIS2PflichtDokuPanel.kernkennzahlen') }}
          <ul style="margin: 6px 0 0 16px;">
            <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.rPO') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.recoveryPointObjectiveMaximalerDaten') }}</li>
            <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.rTO') }}</strong> {{ $t('nis2.nIS2PflichtDokuPanel.recoveryTimeObjectiveMaximaleAusfall') }}</li>
            <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.backupStrategie') }}</strong>{{ $t('nis2.nIS2PflichtDokuPanel.typisch') }} <code>3-2-1</code> {{ $t('nis2.nIS2PflichtDokuPanel.kopienMedienOffsite') }}</li>
            <li><strong>{{ $t('nis2.nIS2PflichtDokuPanel.testFrequenz') }}</strong>{{ $t('nis2.nIS2PflichtDokuPanel.mindJahrlicheBCPUbungDokumentieren') }}</li>
          </ul>
          <em>{{ $t('nis2.nIS2PflichtDokuPanel.sektorSpezifischeDefaultsZBBankenRPO') }}</em>
        </div>
        <!-- #1076: docker-compose-Scan für Backup-Hinweise (Volumes/Datenbanken) -->
        <div class="scan-bar">
          <button class="btn-secondary" :disabled="scanBusy" @click="scanBcp">{{ $t('nis2.nIS2PflichtDokuPanel.dockerComposeScannenBackupHinweise') }}</button>
          <span v-if="scanMsg.n5" class="scan-msg">{{ scanMsg.n5 }}</span>
        </div>
        <div class="form-grid">
          <input v-model.number="store.bcp.rpo_minuten" type="number" placeholder="RPO (Minuten)" />
          <input v-model.number="store.bcp.rto_minuten" type="number" placeholder="RTO (Minuten)" />
          <input v-model="store.bcp.backup_strategie" placeholder="Backup-Strategie (z.B. 3-2-1)" />
          <input v-model="store.bcp.backup_haeufigkeit" :placeholder="$t('nis2.nIS2PflichtDokuPanel.backupHaufigkeit')" />
          <input v-model="store.bcp.backup_aufbewahrung" :placeholder="$t('nis2.nIS2PflichtDokuPanel.aufbewahrung')" />
          <input v-model="store.bcp.dr_standort" :placeholder="$t('nis2.nIS2PflichtDokuPanel.dRStandort')" />
          <input v-model="store.bcp.test_datum" type="date" />
          <input v-model="store.bcp.test_frequenz" :placeholder="$t('nis2.nIS2PflichtDokuPanel.testFrequenz')" />
          <input v-model="store.bcp.bcp_url" :placeholder="$t('nis2.nIS2PflichtDokuPanel.bCPDokuURL')" />
        </div>
        <button class="btn-primary" @click="store.saveBcp(store.bcp)">{{ $t('common.save') }}</button>
      </div>
    </details>

    <!-- 🤖 Hinweis: KI-Assistenten leben im eigenen Tab (#1095) -->
    <div class="assist-hint">
      {{ $t('nis2.nIS2PflichtDokuPanel.alleNIS2AssistentenAssetWizardEntity') }}
      <button class="btn-link-inline" @click="goToAssistenten">{{ $t('common.zumAssistenten') }}</button>
    </div>

    <!-- RB-Import-Modal (#582) -->
    <div v-if="rbImportModal.open" class="wizard-modal-overlay" @mousedown.self="closeRbImport">
      <div class="wizard-modal">
        <h3>{{ $t('nis2.nIS2PflichtDokuPanel.risikenAusRisikobewertungImportieren') }}</h3>
        <p v-if="rbImportModal.firma" class="hint">{{ $t('common.firma') }} <strong>{{ rbImportModal.firma }}</strong></p>
        <p v-if="rbImportModal.warnings?.length" class="hint" style="color: #e65100">
          ⚠️ {{ rbImportModal.warnings.join(', ') }}
        </p>
        <div v-if="rbImportModal.risiken?.length" class="rb-list">
          <div v-for="r in rbImportModal.risiken" :key="r.id" :class="['rb-item', { imported: r.already_imported }]">
            <label>
              <input type="checkbox" :value="r.id" v-model="rbImportModal.selected" :disabled="r.already_imported" />
              <strong>{{ r.risk_name }}</strong>
              <span v-if="r.risikowert" class="score-badge">{{ r.risikowert }}/100 · {{ r.risiko_label }}</span>
              <span v-if="r.already_imported" class="hint" style="margin-left: 8px">{{ $t('nis2.nIS2PflichtDokuPanel.bereitsImportiert') }}</span>
              <div class="rb-meta">{{ r.beschreibung?.substring(0, 200) }}{{ r.beschreibung?.length > 200 ? '…' : '' }}</div>
              <div class="rb-meta" style="font-size: 11px; color: #999">
                {{ $t('nis2.nIS2PflichtDokuPanel.projektV0FrameworkV1', { v0: r.projekt_name, v1: r.framework || '—' }) }}
              </div>
            </label>
          </div>
        </div>
        <div v-else class="hint">{{ $t('nis2.nIS2PflichtDokuPanel.keineImportierbarenRisikenFurDieseFi') }}</div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeRbImport">{{ $t('common.close') }}</button>
          <button class="btn-primary" :disabled="!rbImportModal.selected?.length || rbImporting"
                  @click="doRbImport">
            {{ rbImporting ? '…' : `📥 ${rbImportModal.selected?.length || 0} Risiko(s) importieren` }}
          </button>
        </div>
        <div v-if="rbImportModal.result" class="parsed-result">
          {{ $t('nis2.nIS2PflichtDokuPanel.importiert') }} <strong>{{ rbImportModal.result.imported }}</strong>
          <span v-if="rbImportModal.result.skipped?.length"> {{ $t('nis2.nIS2PflichtDokuPanel.ubersprungenV0', { v0: rbImportModal.result.skipped.length }) }}</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useNis2Store } from '../../stores/nis2'
import { t } from '../../i18n'

// S12 (#1082): Verweis auf den zentralen Assistenten-Tab der NIS2-View.
const emit = defineEmits<{ (e: 'open-assistenten'): void }>()
const goToAssistenten = () => emit('open-assistenten')

const store = useNis2Store()

const assetForm = ref<any>({ asset_name: '', asset_typ: 'it', kritikalitaet: 'mittel',
  verantwortlich: '', standort: '', schutzbedarf_v: 1, schutzbedarf_i: 1, schutzbedarf_a: 1 })
// S7 (#1077): risikoForm/addRisiko/updateRisikoStatus entfernt — N2-Risiken sind
// read-only; gepflegt werden sie in der Risikobewertung (Cockpit-Aggregation).
const vendorForm = ref<any>({ vendor_name: '', leistung: '', kritikalitaet: 'mittel',
  assessment_score: 0, sla_url: '', dpa_url: '' })
const vendorZertifikateInput = ref('')

const status = computed(() => store.pflichtDokuStatus)
const openRisikoCount = computed(() =>
  store.risiken.filter((r: any) => r.status === 'offen' || r.status === 'in-behandlung').length,
)

const statusItems = computed(() => {
  const s = status.value
  if (!s) return []
  return [
    { key: 'assets', label: t('nis2.nIS2PflichtDokuPanel.assets'), ok: s.assets?.ok, detail: `${s.assets?.count || 0} (${s.assets?.high_critical || 0} kritisch)` },
    { key: 'risiken', label: t('common.risiken'), ok: s.risiken?.ok, detail: `${s.risiken?.open || 0} offen` },
    { key: 'ir', label: t('nis2.nIS2PflichtDokuPanel.incidentResponse'), ok: s.incident_response?.ok, detail: s.incident_response?.ok ? 'CSIRT gesetzt' : 'fehlt' },
    { key: 'sc', label: t('nis2.nIS2PflichtDokuPanel.supplyChain'), ok: s.supply_chain?.ok, detail: `${s.supply_chain?.count || 0} Vendors` },
    { key: 'bcp', label: t('nis2.nIS2PflichtDokuPanel.bCP'), ok: s.bcp?.ok, detail: s.bcp?.ok ? `RPO ${s.bcp.rpo}min/RTO ${s.bcp.rto}min` : 'fehlt' },
  ]
})

const scoreClass = (s: number) => s >= 12 ? 'critical' : s >= 8 ? 'high' : s >= 4 ? 'medium' : 'low'

// #1365: Quell-Verlinkung importierter N2-Risiken (Risikobewertung) anzeigen
const riskQuelle = (r: any): string => {
  if (r?.source_modul === 'risikobewertung') {
    const ref = r.source_ref ? `: ${r.source_ref}` : ''
    const rid = r.source_risk_id ? ` #${r.source_risk_id}` : ''
    return `Risikobewertung${ref}${rid}`
  }
  return ''
}

const onDeleteRisiko = async (r: any) => {
  if (!window.confirm(`Risiko "${r.risiko_id} – ${r.titel || ''}" wirklich aus dem NIS2-Register löschen?`)) return
  await store.deleteRisiko(r.id)
}

const reloadAll = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchAssets(), store.fetchRisiken(), store.fetchIncidentResponse(),
    store.fetchVendors(), store.fetchBcp(), store.fetchPflichtDokuStatus(),
  ])
}

onMounted(reloadAll)
watch(() => store.selectedProjekt, reloadAll)

const addAsset = async () => {
  if (await store.saveAsset(assetForm.value)) {
    assetForm.value = { asset_name: '', asset_typ: 'it', kritikalitaet: 'mittel',
      verantwortlich: '', standort: '', schutzbedarf_v: 1, schutzbedarf_i: 1, schutzbedarf_a: 1 }
    await store.fetchPflichtDokuStatus()
  }
}

const addVendor = async () => {
  const payload = { ...vendorForm.value,
    zertifikate: vendorZertifikateInput.value.split(',').map(s => s.trim()).filter(Boolean),
  }
  if (await store.saveVendor(payload)) {
    vendorForm.value = { vendor_name: '', leistung: '', kritikalitaet: 'mittel',
      assessment_score: 0, sla_url: '', dpa_url: '' }
    vendorZertifikateInput.value = ''
    await store.fetchPflichtDokuStatus()
  }
}

// ──────────────────────────────────────────────────────────────────
// Sprint #21 — N1–N5 Repo-Scan Auto-Fill + N1-Wizard (#1072–#1076)
// ──────────────────────────────────────────────────────────────────
const scanBusy = ref(false)
const scanMsg = ref<Record<string, string>>({ n1: '', n3: '', n4: '', n5: '' })
const assetSuggestions = ref<any[]>([])
const vendorSuggestions = ref<any[]>([])

const scanAssets = async () => {
  scanBusy.value = true; scanMsg.value.n1 = 'Scanne Repository…'
  const res = await store.suggestAssets()
  scanBusy.value = false
  if (!res) { scanMsg.value.n1 = store.error || t('common.error'); return }
  assetSuggestions.value = res.suggestions || []
  scanMsg.value.n1 = `${assetSuggestions.value.length} Vorschläge aus ${res.repo || 'Repo'}`
}
const applyAssetSuggestion = async (s: any) => {
  await store.saveAsset({
    asset_name: s.asset_name, asset_typ: s.asset_typ, kritikalitaet: s.kritikalitaet,
    beschreibung: s.beschreibung,
  })
  assetSuggestions.value = assetSuggestions.value.filter(x => x !== s)
  await store.fetchPflichtDokuStatus()
}

const scanIncidentResponse = async () => {
  scanBusy.value = true; scanMsg.value.n3 = 'Scanne SECURITY.md…'
  const sug = await store.suggestIncidentResponse()
  scanBusy.value = false
  if (!sug) { scanMsg.value.n3 = store.error || t('common.error'); return }
  if (!sug.csirt_email && !sug.csirt_kontakt) { scanMsg.value.n3 = 'Kein CSIRT-Kontakt in SECURITY.md gefunden'; return }
  if (sug.csirt_kontakt) store.incidentResponse.csirt_kontakt = sug.csirt_kontakt
  if (sug.csirt_email) store.incidentResponse.csirt_email = sug.csirt_email
  if (sug.eskalation_pfad && !store.incidentResponse.eskalation_pfad) store.incidentResponse.eskalation_pfad = sug.eskalation_pfad
  scanMsg.value.n3 = `Vorschlag übernommen aus ${sug.source_path || 'SECURITY.md'} (bitte speichern)`
}

const scanVendors = async () => {
  scanBusy.value = true; scanMsg.value.n4 = 'Scanne SBOM/Dependencies…'
  const res = await store.suggestVendors()
  scanBusy.value = false
  if (!res) { scanMsg.value.n4 = store.error || t('common.error'); return }
  vendorSuggestions.value = res.suggestions || []
  scanMsg.value.n4 = `${vendorSuggestions.value.length} Vendor-Vorschläge aus ${res.repo || 'Repo'}`
}
const applyVendorSuggestion = async (s: any) => {
  await store.saveVendor({
    vendor_name: s.vendor_name, leistung: s.leistung, kritikalitaet: s.kritikalitaet,
  })
  vendorSuggestions.value = vendorSuggestions.value.filter(x => x !== s)
  await store.fetchPflichtDokuStatus()
}

const scanBcp = async () => {
  scanBusy.value = true; scanMsg.value.n5 = 'Scanne docker-compose…'
  const sug = await store.suggestBcp()
  scanBusy.value = false
  if (!sug || !sug.source_path) { scanMsg.value.n5 = store.error || t('nis2.nIS2PflichtDokuPanel.keineBackupHinweiseGefunden'); return }
  if (sug.backup_strategie && !store.bcp.backup_strategie) store.bcp.backup_strategie = sug.backup_strategie
  store.bcp.notizen = [store.bcp.notizen, sug.notizen].filter(Boolean).join('\n\n')
  scanMsg.value.n5 = `Hinweise aus ${sug.source_path} übernommen (bitte speichern)`
}

// #582 RB-Import
const rbImportModal = ref<any>({ open: false, risiken: [], firma: '', selected: [], result: null, warnings: [] })
const rbImporting = ref(false)

const openRbImport = async () => {
  rbImportModal.value = { open: true, risiken: [], firma: '', selected: [], result: null, warnings: [] }
  const data = await store.fetchRbRisks()
  if (data) {
    rbImportModal.value.risiken = data.risiken || []
    rbImportModal.value.firma = data.firma || ''
    rbImportModal.value.warnings = data.warnings || []
  }
}

const closeRbImport = () => { rbImportModal.value = { open: false, risiken: [], firma: '', selected: [], result: null, warnings: [] } }

const doRbImport = async () => {
  if (!rbImportModal.value.selected.length) return
  rbImporting.value = true
  try {
    const res = await store.importRbRisks(rbImportModal.value.selected)
    rbImportModal.value.result = res
    if (res?.imported) {
      // Liste neu laden
      const data = await store.fetchRbRisks()
      if (data) rbImportModal.value.risiken = data.risiken || []
      rbImportModal.value.selected = []
      setTimeout(closeRbImport, 2000)
    }
  } finally {
    rbImporting.value = false
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

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; margin-bottom: 10px; }
.form-grid input, .form-grid select, .form-grid textarea {
  padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit;
}
.form-grid textarea { grid-column: 1 / -1; }

.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #0d47a1; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 16px; }

table { width: 100%; border-collapse: collapse; margin-top: 10px; }
table th, table td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #eee; }
table th { background: #f5f5f5; font-weight: 600; }

.crit { padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: 600; }
.crit-niedrig { background: #e3f2fd; color: #1565c0; }
.crit-mittel { background: #fff3e0; color: #e65100; }
.crit-hoch { background: #ffe0e0; color: #c62828; }
.crit-kritisch { background: #c62828; color: white; }

.score { padding: 2px 10px; border-radius: 3px; font-weight: 600; }
.score-low { background: #e3f2fd; color: #1565c0; }
.score-medium { background: #fff3e0; color: #e65100; }
.score-high { background: #ffe0e0; color: #c62828; }
.score-critical { background: #c62828; color: white; }

.hint { color: #666; font-size: 13px; margin-top: 6px; }

/* #1365: Quell-Verlinkung + Löschen importierter N2-Risiken */
.quelle-badge {
  display: inline-block; max-width: 220px; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; vertical-align: middle;
  background: #e3f2fd; color: #1565c0; border: 1px solid #90caf9;
  border-radius: 10px; padding: 1px 8px; font-size: 12px;
}
.btn-del {
  background: none; border: none; cursor: pointer; font-size: 14px; padding: 2px 4px;
  border-radius: 4px;
}
.btn-del:hover { background: #ffebee; }

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
.btn-secondary:hover { background: #ddd; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.help-box {
  background: #fff8e1; border-left: 4px solid #ffc107; padding: 10px 14px;
  margin: 0 0 12px; border-radius: 4px; font-size: 13px; line-height: 1.55; color: #444;
}
.help-box code { background: #fff3cd; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
.help-box.info { background: #e3f2fd; border-left-color: #1565c0; }

/* #1072–#1076 Repo-Scan UI */
.scan-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 0 12px; }
.scan-msg { font-size: 12px; color: #555; }
.suggest-box {
  background: #e8f5e9; border-left: 4px solid #43a047; padding: 8px 14px;
  margin: 0 0 12px; border-radius: 4px; font-size: 13px;
}
.suggest-box ul { margin: 6px 0 0; padding-left: 14px; }
.suggest-box li { margin: 2px 0; }
.suggest-box .btn-link { font-size: 13px; color: #1565c0; }
.suggest-box small { color: #666; margin-left: 6px; }

.assist-hint {
  background: #ede7f6; border-left: 4px solid #7b1fa2; padding: 8px 14px;
  border-radius: 4px; font-size: 13px; margin: 0 0 12px; color: #4a148c;
}
.status-readonly {
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  background: #eceff1; color: #455a64; font-size: 12px;
}
.btn-link-inline {
  background: none; border: none; color: #1565c0; text-decoration: underline;
  cursor: pointer; padding: 0; font-size: 13px;
}

.rb-import-bar {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 14px; background: #f3e5f5; border-radius: 6px; margin-bottom: 12px;
  font-size: 13px;
}
.rb-list { max-height: 50vh; overflow-y: auto; margin-top: 12px; }
.rb-item {
  padding: 10px 12px; border: 1px solid #e0e0e0; border-radius: 4px; margin-bottom: 6px;
  background: white; cursor: pointer;
}
.rb-item:hover { background: #fafafa; }
.rb-item.imported { opacity: 0.55; background: #f5f5f5; }
.rb-item label { cursor: pointer; display: block; }
.rb-item input[type="checkbox"] { margin-right: 8px; }
.rb-meta { color: #555; font-size: 12px; margin: 4px 0 0 22px; line-height: 1.4; }
.score-badge {
  background: #1565c0; color: white; padding: 1px 8px; border-radius: 3px;
  font-size: 11px; margin-left: 8px;
}

/* #1954: Der hervorgehobene Anfangsbuchstabe der CIA-Triade ist
   sprachabhängig (V-I-A deutsch, C-I-A englisch). Er darf deshalb nicht im
   Template stehen — das Wort kommt ganz aus dem Katalog. */
.initiale::first-letter { font-weight: 700; }
</style>
