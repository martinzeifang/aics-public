<template>
  <div class="soc-view">
    <header class="soc-header">
      <h1>🚨 SOC — Security Operations Center</h1>
      <p class="subtitle">Triage &amp; Dokumentation für Wazuh-Alarme · Incidents · Meldepflichten</p>
    </header>

    <div v-if="store.error" class="banner err">{{ store.error }} <button @click="store.error = null">×</button></div>

    <GroupedModuleNav :groups="navGroups" :model-value="tab" persist-key="soc" @update:model-value="select" />

    <!-- ── Dashboard ─────────────────────────────────────────────────── -->
    <section v-show="tab === 'dashboard'" class="panel">
      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-val">{{ store.kpis.alerts_new ?? '–' }}</div><div class="kpi-lbl">Neue Alarme</div></div>
        <div class="kpi"><div class="kpi-val">{{ store.kpis.incidents_open ?? '–' }}</div><div class="kpi-lbl">Offene Incidents</div></div>
        <div class="kpi"><div class="kpi-val">{{ pct(store.kpis.fp_rate) }}</div><div class="kpi-lbl">False-Positive-Rate</div></div>
        <div class="kpi clickable" @click="select('vulnerabilities')" title="Zum Schwachstellen-Register">
          <div class="kpi-val" :class="store.vulnKpi.critical_high ? 'bad' : 'ok'">{{ store.vulnKpi.critical_high ?? '–' }}</div>
          <div class="kpi-lbl">🛡️ offene krit./hohe Schwachstellen</div>
        </div>
      </div>
      <h3>Offene Alarme nach Schwere</h3>
      <div class="sev-bars">
        <div v-for="s in severities" :key="s" class="sev-row">
          <span class="sev-tag" :class="s">{{ sevDe(s) }}</span><span class="sev-count">{{ (store.kpis.open_by_severity || {})[s] || 0 }}</span>
        </div>
      </div>
      <h3>📑 Nachweis „Incident-Handling" (NIS2 Art. 21 / AI-Act Art. 72)</h3>
      <div class="evidence">
        <span>Bearbeitete Alarme: <b>{{ store.controlEvidence.alerts_handled ?? '–' }}</b> ({{ pct(store.controlEvidence.handled_ratio) }})</span>
        <span>Geschlossene Incidents: <b>{{ store.controlEvidence.incidents_closed ?? '–' }}</b></span>
        <span>Offene Incidents: <b>{{ store.controlEvidence.incidents_open ?? '–' }}</b></span>
        <span>MTTR: <b>{{ store.controlEvidence.mttr_hours != null ? store.controlEvidence.mttr_hours + ' h' : '–' }}</b></span>
      </div>
      <p class="hint">Belegt, dass die Detektions-/Reaktions-Fähigkeit tatsächlich arbeitet — als Nachweis für die Pflicht-Controls. Datenquelle: dein Wazuh-Indexer (read-only).</p>

      <h3>⏱️ SLA &amp; Reaktions-Kennzahlen <span class="hint-inline">(#1315)</span></h3>
      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-val">{{ store.slaKpis.mtta_hours != null ? store.slaKpis.mtta_hours + ' h' : '–' }}</div><div class="kpi-lbl">MTTA (Reaktion)</div></div>
        <div class="kpi"><div class="kpi-val">{{ store.slaKpis.mttr_hours != null ? store.slaKpis.mttr_hours + ' h' : '–' }}</div><div class="kpi-lbl">MTTR (Behebung)</div></div>
        <div class="kpi"><div class="kpi-val" :class="slaClass">{{ store.slaKpis.sla_compliance != null ? pct(store.slaKpis.sla_compliance) : '–' }}</div><div class="kpi-lbl">SLA-Einhaltung</div></div>
        <div class="kpi"><div class="kpi-val">{{ store.slaKpis.sla_breached ?? '–' }}</div><div class="kpi-lbl">SLA-Verletzungen</div></div>
      </div>
      <h3>📰 Management-Report <span class="hint-inline">(#1325)</span></h3>
      <div class="ho-add">
        <select v-model="reportPeriod" @change="store.fetchMgmtReport(reportPeriod)">
          <option value="woche">Woche</option><option value="monat">Monat</option><option value="quartal">Quartal</option>
        </select>
        <button @click="store.downloadMgmtReport(reportPeriod, 'pdf')">📄 PDF</button>
        <button @click="store.downloadMgmtReport(reportPeriod, 'docx')">📝 DOCX</button>
      </div>
      <div v-if="store.mgmtReport" class="report-preview">
        <span>Zeitraum seit {{ store.mgmtReport.since }} ({{ store.mgmtReport.days }} T.)</span>
        <span>Incidents: <b>{{ store.mgmtReport.incidents_total }}</b> (geschl. {{ store.mgmtReport.incidents_closed }})</span>
        <span>Neue Alarme: <b>{{ store.mgmtReport.alerts_new }}</b></span>
        <span>MTTR: <b>{{ store.mgmtReport.mttr_hours != null ? store.mgmtReport.mttr_hours + ' h' : '–' }}</b></span>
        <span>SLA: <b>{{ store.mgmtReport.sla_compliance != null ? pct(store.mgmtReport.sla_compliance) : '–' }}</b></span>
      </div>

      <details class="supp-box">
        <summary>🎯 SLA-Ziele je Schweregrad (Minuten)</summary>
        <p class="hint">Zielzeiten für Reaktion (MTTA) und Behebung (MTTR). Überschreitung der Behebungszeit zählt als SLA-Verletzung.</p>
        <table class="sla-tbl">
          <thead><tr><th>Schwere</th><th>Reaktion (Min.)</th><th>Behebung (Min.)</th><th></th></tr></thead>
          <tbody>
            <tr v-for="s in severities" :key="s">
              <td><span class="sev-tag" :class="s">{{ sevDe(s) }}</span></td>
              <td><input type="number" v-model.number="slaEdit[s].ack_minutes" style="width:90px" /></td>
              <td><input type="number" v-model.number="slaEdit[s].resolve_minutes" style="width:90px" /></td>
              <td><button @click="saveSla(s)">💾</button></td>
            </tr>
          </tbody>
        </table>
      </details>
    </section>

    <!-- ── Alarme ────────────────────────────────────────────────────── -->
    <section v-show="tab === 'alerts'" class="panel">
      <div class="filterbar">
        <select v-model="aFilter.kind"><option value="">Alle Arten</option><option value="vulnerability">🛡️ Schwachstellen</option><option value="alert">Sonstige Alarme</option></select>
        <select v-model="aFilter.status"><option value="">Alle Status</option><option v-for="s in alertStates" :key="s" :value="s">{{ alertStatusDe(s) }}</option></select>
        <select v-model="aFilter.severity"><option value="">Alle Schweren</option><option v-for="s in severities" :key="s" :value="s">{{ sevDe(s) }}</option></select>
        <input v-model.number="aFilter.min_level" type="number" placeholder="min. Level" style="width:90px" />
        <button @click="loadAlerts">Filtern</button>
      </div>

      <details class="supp-box" @toggle="onSuppToggle">
        <summary>🔇 Suppression-Regeln (Tuning bekannter False Positives)</summary>
        <p class="hint">Regeln mit Ablaufdatum (TTL) gegen Alarm-Fatigue. Treffer werden automatisch auf „Unterdrückt" gesetzt. Dry-Run zeigt, wie viele der letzten Alarme eine Regel matchen würde.</p>
        <div class="supp-form">
          <input v-model="suppForm.rule_id" placeholder="Regel-ID" style="width:110px" />
          <input v-model="suppForm.agent_glob" placeholder="Agent (glob, z.B. web*)" style="width:160px" />
          <input v-model="suppForm.srcip" placeholder="Quell-IP" style="width:130px" />
          <input v-model="suppForm.reason" placeholder="Begründung" style="flex:1;min-width:160px" />
          <input v-model="suppForm.expires_at" type="date" title="Ablaufdatum (TTL)" />
          <button @click="dryRun">Dry-Run</button>
          <button class="primary" @click="addSupp">+ Regel</button>
          <span v-if="dryResult!==null" class="dry">{{ dryResult }} von 2000 würden matchen</span>
        </div>
        <div class="grid-scroll">
        <table class="grid mini">
          <thead><tr><th>Regel-ID</th><th>Agent</th><th>Quell-IP</th><th>Begründung</th><th>Ablauf</th><th></th></tr></thead>
          <tbody>
            <tr v-for="s in store.suppressions" :key="s.id">
              <td>{{ s.rule_id || '—' }}</td><td>{{ s.agent_glob || '—' }}</td><td>{{ s.srcip || '—' }}</td>
              <td>{{ s.reason }}</td><td>{{ (s.expires_at||'').slice(0,10) || 'kein' }}</td>
              <td><button @click="store.deleteSuppression(s.id)">Löschen</button></td>
            </tr>
            <tr v-if="!store.suppressions.length"><td colspan="6" class="empty">Keine Suppression-Regeln.</td></tr>
          </tbody>
        </table>
        </div>
      </details>
      <div v-if="bulkAlerts.length" class="bulk-bar">
        <b>{{ bulkAlerts.length }}</b> Alarm(e) ausgewählt →
        <select v-model="bulkTargetIncident"><option value="">Incident wählen …</option>
          <option v-for="i in openIncidents" :key="i.id" :value="i.id">#{{ i.id }} {{ i.titel }}</option></select>
        <button class="primary" :disabled="!bulkTargetIncident" @click="doBulkAssign">Zuordnen</button>
        <button @click="bulkAlerts = []">Auswahl leeren</button>
      </div>
      <div class="grid-scroll">
      <table class="grid">
        <thead><tr><th style="width:28px"></th><th>Zeit</th><th>Schwere</th><th>Lvl</th><th>Regel</th><th>Agent</th><th>Quell-IP</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="al in store.alerts" :key="al.alert_uid" class="clickable">
            <td @click.stop><input type="checkbox" :value="al.alert_uid" v-model="bulkAlerts" /></td>
            <td @click="openAlertDetail(al.alert_uid)">{{ shortTs(al.event_ts) }}</td>
            <td @click="openAlertDetail(al.alert_uid)"><span class="sev-tag" :class="al.severity">{{ sevDe(al.severity) }}</span></td>
            <td @click="openAlertDetail(al.alert_uid)">{{ al.rule_level }}</td>
            <td @click="openAlertDetail(al.alert_uid)"><span v-if="al.kind === 'vulnerability'" class="kind-tag" title="Schwachstelle">🛡️ CVE</span><span v-if="al.ioc_hits && al.ioc_hits.length" class="ioc-flag" title="IOC-Treffer (Threat-Intel)">🌐</span> {{ al.description }}</td>
            <td @click="openAlertDetail(al.alert_uid)">{{ al.agent_name }}</td>
            <td @click="openAlertDetail(al.alert_uid)">{{ al.srcip }}</td>
            <td @click="openAlertDetail(al.alert_uid)"><span class="status-pill">{{ alertStatusDe(al.status) }}</span></td>
            <td @click="openAlertDetail(al.alert_uid)">Details ›</td>
          </tr>
          <tr v-if="!store.alerts.length"><td colspan="9" class="empty">Keine Alarme. Einrichtung prüfen / Sync auslösen.</td></tr>
        </tbody>
      </table>
      </div>
    </section>

    <!-- ── Incidents ─────────────────────────────────────────────────── -->
    <section v-show="tab === 'incidents'" class="panel">
      <!-- Liste -->
      <template v-if="!store.currentIncident">
        <div class="filterbar">
          <label class="chk"><input type="checkbox" v-model="incShowClosed" @change="loadIncidents" /> Geschlossene anzeigen</label>
          <span style="flex:1"></span>
          <button :disabled="!selectedIds.length" @click="report('pdf')">📄 PDF-Report ({{ selectedIds.length }})</button>
          <button :disabled="!selectedIds.length" @click="report('docx')">DOCX</button>
        </div>
        <div class="grid-scroll">
        <table class="grid">
          <thead><tr><th></th><th>#</th><th>Titel</th><th>Status</th><th>Schwere</th><th>Owner</th><th>Aktualisiert</th><th></th></tr></thead>
          <tbody>
            <tr v-for="i in store.incidents" :key="i.id">
              <td><input type="checkbox" :value="i.id" v-model="selectedIds" /></td>
              <td>{{ i.id }}</td>
              <td class="clickable" @click="openIncident(i.id)">{{ i.titel }}</td>
              <td><span class="status-pill">{{ incStatusDe(i.status) }}</span></td>
              <td><span class="sev-tag" :class="i.severity">{{ sevDe(i.severity) }}</span></td>
              <td>{{ i.owner }}</td>
              <td>{{ shortTs(i.updated_at) }}</td>
              <td class="clickable" @click="openIncident(i.id)">Details ›</td>
            </tr>
            <tr v-if="!store.incidents.length"><td colspan="8" class="empty">Keine Incidents.</td></tr>
          </tbody>
        </table>
        </div>
      </template>

      <!-- Detailansicht -->
      <div v-else class="inc-detail">
        <div class="detail-bar">
          <button class="link-back" @click="backToList">‹ Zurück zur Liste</button>
          <span style="flex:1"></span>
          <button @click="report('pdf', store.currentIncident.id)">📄 PDF</button>
        </div>
        <div class="inc-headcard">
          <div class="ih-title">#{{ store.currentIncident.id }} — {{ store.currentIncident.titel }}</div>
          <div class="ih-facts">
            <span class="sev-tag" :class="store.currentIncident.severity">{{ sevDe(store.currentIncident.severity) }}</span>
            <span class="status-pill">{{ incStatusDe(store.currentIncident.status) }}</span>
            <span v-if="store.currentIncident.sla" class="sla-pill" :class="{ breach: store.currentIncident.sla.resolve_breached }"
                  :title="`Ziel Behebung: ${store.currentIncident.sla.resolve_target ?? '–'} Min.`">
              ⏱️ SLA {{ store.currentIncident.sla.resolve_breached ? 'verletzt' : 'i.O.' }}
            </span>
            <span v-if="store.currentIncident.owner">👤 {{ store.currentIncident.owner }}</span>
            <span v-if="store.currentIncident.agent_name">🖥️ {{ store.currentIncident.agent_name }}</span>
            <span v-if="store.currentIncident.personal_data_involved" class="pers-flag">Personenbezug</span>
          </div>
          <div v-if="store.currentIncident.status==='closed'" class="closed-note">
            🔒 Geschlossen: {{ store.currentIncident.closed_reason }} <i>({{ store.currentIncident.closed_by }}, {{ shortTs(store.currentIncident.closed_at) }})</i>
          </div>
          <div v-if="incLikelihood && store.currentIncident.agent_name" class="likelihood">
            📈 Empirische Eintrittswahrscheinlichkeit (Agent {{ store.currentIncident.agent_name }}):
            <b>{{ incLikelihood.eintrittswahrscheinlichkeit_label }}</b> (Stufe {{ incLikelihood.eintrittswahrscheinlichkeit_stufe }}/5, {{ incLikelihood.incidents }} Incidents) — Vorschlag für die Risikobewertung
          </div>
        </div>

        <div class="inc-actions">
          <span class="lbl">Status:</span>
          <button v-for="s in nextIncident(store.currentIncident.status).filter(x => x!=='closed')" :key="s" @click="setStatus(s)">→ {{ incStatusDe(s) }}</button>
          <button class="warn" v-if="store.currentIncident.status!=='closed'" @click="closingMode=!closingMode">🔒 Schließen</button>
          <label class="chk"><input type="checkbox" :checked="store.currentIncident.personal_data_involved" @change="togglePersonal($event)" /> Personenbezug</label>
          <button class="primary" @click="evaluate">🔁 Meldepflicht prüfen</button>
          <button @click="startEdit">✏️ Bearbeiten</button>
          <span class="lbl">Asset:</span>
          <select :value="store.currentIncident.asset_id || ''" @change="reassignIncident($event)">
            <option value="">— keins —</option>
            <option v-for="a in store.assets" :key="a.id" :value="a.id">{{ a.agent_name || ('#'+a.id) }}</option>
          </select>
        </div>
        <div v-if="closingMode" class="close-box">
          <textarea v-model="closeReason" rows="2" placeholder="Begründung für den Abschluss (Pflicht, mind. 10 Zeichen) …"></textarea>
          <button class="warn" @click="doClose">Endgültig schließen</button>
        </div>

        <div v-if="editMode" class="edit-box">
          <label>Titel<input v-model="editForm.titel" /></label>
          <label>Schwere<select v-model="editForm.severity"><option v-for="s in severities" :key="s" :value="s">{{ sevDe(s) }}</option></select></label>
          <label>Klassifikation<input v-model="editForm.klassifikation" placeholder="z.B. Unbefugter Zugriff, Malware …" /></label>
          <label>Owner<input v-model="editForm.owner" /></label>
          <label>Beschreibung<textarea v-model="editForm.beschreibung" rows="3"></textarea></label>
          <label>Maßnahmen<textarea v-model="editForm.response_actions" rows="2"></textarea></label>
          <label>Lessons Learned<textarea v-model="editForm.lessons_learned" rows="2"></textarea></label>
          <div class="form-actions"><button class="primary" @click="saveEdit">Speichern</button><button @click="editMode=false">Abbrechen</button></div>
        </div>

        <!-- #1402: zweispaltiges Layout — Inhalte links, Verlauf rechts -->
        <div class="incident-detail-grid">
          <div class="idg-main">
          <h4>📝 Notizen / dokumentierte Reaktion</h4>
          <div class="note-add big">
            <textarea v-model="noteText" rows="4" placeholder="Reaktion / Bewertung / Maßnahme dokumentieren …"></textarea>
            <button class="primary" @click="addNote">+ Notiz speichern</button>
          </div>

          <details class="ki-box" :open="!incidentAnalysis">
            <summary><h4>🤖 KI-Analyse des Incidents</h4><span v-if="incidentAnalysis" class="ki-done">✓ erstellt</span></summary>
            <KiAnalysePanel :prompt="incPromptText" :result="incidentAnalysis"
                            @ollama="analyzeIncidentOllama" @paste="parseIncidentPasteResp" />
          </details>

          <h4>📋 Response-Playbook</h4>
          <div class="pb-assign">
            <select v-model="pbSelect"><option value="">Playbook wählen …</option><option v-for="p in store.playbookCatalog" :key="p.id" :value="p.id">{{ p.name }}</option></select>
            <button class="primary" :disabled="!pbSelect" @click="doAssignPlaybook">Zuordnen</button>
          </div>
          <div v-for="pb in incPlaybooks.playbooks" :key="pb.id" class="playbook">
            <div class="pb-head"><b>{{ pb.name }}</b> <span class="pb-prog">{{ pb.progress.done }}/{{ pb.progress.total }}</span></div>
            <div class="pb-bar"><div class="pb-bar-fill" :style="{ width: pbPct(pb) + '%' }"></div></div>
            <label v-for="s in pb.steps" :key="s.id" class="pb-step" :class="{ done: s.done }">
              <input type="checkbox" :checked="s.done" @change="doToggleStep(pb.id, s.id, $event)" />
              <span>{{ s.text }} <em v-if="s.mandatory" class="pb-mand">Pflicht</em></span>
            </label>
          </div>
          <p v-if="incPlaybooks.mandatory_open" class="warn-text">⚠ {{ incPlaybooks.mandatory_open }} offene Pflicht-Schritt(e) — vor „Behoben" abschließen.</p>

          <h4>🔬 Post-Incident-Review (PIR)</h4>
          <p class="hint">Ursachenanalyse + Lessons Learnt nach NIST SP 800-61 / ISO 27035. Bei eskalierten Incidents ist die Ursachenanalyse vor dem Schließen Pflicht.</p>
          <div class="pir-grid">
            <label>Ursache (Root Cause)<textarea v-model="pirForm.root_cause" rows="5" placeholder="Wodurch wurde der Vorfall ausgelöst?"></textarea></label>
            <label>Was lief gut?<textarea v-model="pirForm.what_went_well" rows="5"></textarea></label>
            <label>Was lief schlecht?<textarea v-model="pirForm.what_went_wrong" rows="5"></textarea></label>
            <label>Lessons Learnt<textarea v-model="pirForm.lessons" rows="5"></textarea></label>
          </div>
          <button class="primary" @click="savePirForm">💾 PIR speichern</button>

          <h5>✅ Abgeleitete Maßnahmen</h5>
          <div class="grid-scroll" v-if="(store.currentIncident.pir_actions || []).length">
          <table class="grid mini">
            <thead><tr><th>Maßnahme</th><th>Owner</th><th>Frist</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-for="a in store.currentIncident.pir_actions" :key="a.id" :class="{ overdue: isOverdue(a) }">
                <td>{{ a.beschreibung }}</td><td>{{ a.owner || '–' }}</td>
                <td>{{ a.frist || '–' }}</td>
                <td><select :value="a.status" @change="changeActionStatus(a.id, $event)">
                  <option v-for="s in pirStates" :key="s" :value="s">{{ s }}</option></select></td>
                <td><button class="link-del" @click="doDeleteAction(a.id)">✕</button></td>
              </tr>
            </tbody>
          </table>
          </div>
          <div class="pir-action-add">
            <input v-model="actionForm.beschreibung" placeholder="Neue Maßnahme …" />
            <input v-model="actionForm.owner" placeholder="Owner" style="width:120px" />
            <input v-model="actionForm.frist" type="date" style="width:150px" />
            <button class="primary" :disabled="!actionForm.beschreibung.trim()" @click="addAction">+ Maßnahme</button>
          </div>

          <h4>🔗 Verknüpfte Wazuh-Alarme</h4>
          <div v-if="!(incAlerts.length)" class="hint">Keine verknüpften Alarme.</div>
          <div class="grid-scroll" v-else>
          <table class="grid mini">
            <tbody>
              <tr v-for="al in incAlerts" :key="al.alert_uid">
                <td class="clickable" @click="openAlertDetail(al.alert_uid)"><span class="sev-tag" :class="al.severity">{{ sevDe(al.severity) }}</span></td>
                <td class="clickable" @click="openAlertDetail(al.alert_uid)">{{ al.description }}</td>
                <td>{{ al.agent_name }}</td><td>{{ shortTs(al.event_ts) }}</td>
                <td><button class="link-del" title="Vom Incident lösen" @click="doUnlinkAlert(al.alert_uid)">✕</button></td>
              </tr>
            </tbody>
          </table>
          </div>
          <details class="add-alerts-box" @toggle="onAddAlertsToggle">
            <summary>+ Weitere Alarme zuordnen</summary>
            <p class="hint">Zuletzt eingegangene, noch nicht diesem Incident zugeordnete Alarme. Mehrfachauswahl möglich.</p>
            <div class="add-alerts-list">
              <label v-for="al in linkableAlerts" :key="al.alert_uid" class="add-alert-row">
                <input type="checkbox" :value="al.alert_uid" v-model="alertsToLink" />
                <span class="sev-tag" :class="al.severity">{{ sevDe(al.severity) }}</span>
                <span class="aa-desc">{{ al.description }}</span>
                <span class="aa-meta">{{ al.agent_name }} · {{ shortTs(al.event_ts) }}</span>
              </label>
              <div v-if="!linkableAlerts.length" class="hint">Keine weiteren Alarme verfügbar.</div>
            </div>
            <button class="primary" :disabled="!alertsToLink.length" @click="doLinkAlerts">{{ alertsToLink.length }} Alarm(e) zuordnen</button>
          </details>

          <h4>🔒 Beweissicherung / Asservaten</h4>
          <p class="hint">Beweismittel SHA-256-gesichert mit lückenloser Chain of Custody (ISO/IEC 27037 · BSI DER.2.2). Aufbewahrungsfrist je Asservat konfigurierbar.</p>
          <div class="evi-add">
            <input ref="eviFileInput" type="file" @change="onEviFile" />
            <input v-model="eviForm.beschreibung" placeholder="Beschreibung (optional)" />
            <label class="evi-ret">Aufbewahrung (Tage)<input v-model.number="eviForm.retention_days" type="number" style="width:90px" /></label>
            <button class="primary" :disabled="!eviFile" @click="doUploadEvidence">⬆️ Sichern</button>
            <button @click="doFreezeSnapshot">❄️ Rohlog-Snapshot einfrieren</button>
          </div>
          <div class="grid-scroll" v-if="evidence.length">
          <table class="grid mini">
            <thead><tr><th>Typ</th><th>Datei</th><th>SHA-256</th><th>Größe</th><th>Aufbewahrung bis</th><th></th></tr></thead>
            <tbody>
              <tr v-for="e in evidence" :key="e.id" :class="{ 'evi-deleted': e.deleted_at }">
                <td>{{ e.kind === 'log_snapshot' ? '❄️ Snapshot' : '📄 Datei' }}</td>
                <td>{{ e.filename }}<div v-if="e.beschreibung" class="evi-desc">{{ e.beschreibung }}</div></td>
                <td><code class="sha">{{ (e.sha256 || '').slice(0, 12) }}…</code></td>
                <td>{{ fmtBytes(e.size) }}</td>
                <td>{{ e.retention_until }}</td>
                <td class="evi-actions">
                  <template v-if="!e.deleted_at">
                    <button class="link-btn" @click="store.downloadEvidence(e.id, e.filename)">⬇️</button>
                    <button class="link-btn" @click="showCustody(e.id)">📜 CoC</button>
                    <button class="link-del" @click="doDeleteEvidence(e.id)">✕</button>
                  </template>
                  <span v-else class="evi-del-note">gelöscht ({{ e.deleted_by }})</span>
                </td>
              </tr>
            </tbody>
          </table>
          </div>
          <div v-else class="hint">Noch keine Asservate gesichert.</div>
          <div v-if="custodyView" class="custody-panel">
            <div class="custody-head"><b>📜 Chain of Custody — {{ custodyView.evidence.filename }}</b><button class="close" @click="custodyView = null">×</button></div>
            <ul class="custody-list">
              <li v-for="c in custodyView.custody" :key="c.id"><span class="ts">{{ shortTs(c.ts) }}</span> <b>{{ c.action }}</b> <i>{{ c.actor }}</i> {{ c.note }}</li>
            </ul>
          </div>


          <h4>⚖️ Betroffene Regelwerke (steuern die Meldepflicht)</h4>
          <div class="regime-flags">
            <label v-for="r in regimeOptions" :key="r.key"><input type="checkbox" v-model="regimeFlags[r.key]" /> {{ r.label }}</label>
            <button class="primary" @click="saveRegimes">Speichern</button>
          </div>
          <p class="hint">Wähle die einschlägigen Regelwerke und klicke „🔁 Meldepflicht prüfen" oben — die passenden Meldetracks mit Brücken-Buttons (DSGVO/NIS2/CRA/AI-Act) erscheinen dann unten.</p>

          <h4>📈 Eskalation</h4>
          <div v-if="(store.currentIncident.escalation_path || []).length" class="esc-path">
            <div v-for="e in store.currentIncident.escalation_path" :key="e.id" class="esc-step">
              <span class="esc-stufe">Stufe {{ e.stufe }}</span>
              <span>{{ e.rolle }}<template v-if="e.person"> · {{ e.person }}</template><template v-if="e.kontakt"> · {{ e.kontakt }}</template></span>
              <span class="esc-frist">≤ {{ e.frist_minuten }} Min.</span>
              <button @click="doEscalate(e.stufe)">→ eskalieren</button>
            </div>
          </div>
          <p v-else class="hint">Keine Eskalationsmatrix für Severity „{{ sevDe(store.currentIncident.severity) }}" — im Tab „📞 Betrieb" pflegen.</p>

          <h4>📋 Meldetracks</h4>
          <div v-if="!(store.currentIncident.meldetracks||[]).length" class="hint">Noch keine — „🔁 Meldepflicht prüfen" wertet die Asset-Tags aus.</div>
          <div v-for="t in store.currentIncident.meldetracks" :key="t.id" class="track">
            <strong>{{ t.regime.toUpperCase() }}</strong> · {{ t.legal }} · <span class="status-pill">{{ trackStatusDe(t.status) }}</span>
            <ul><li v-for="d in t.deadlines" :key="d.key">{{ d.label }}: <em>{{ d.due_at ? shortTs(d.due_at) : 'n/a' }}</em></li></ul>
            <div v-if="t.target_ref" class="bridge-done">✓ verknüpft: {{ t.target_ref }}</div>
            <div v-else class="bridge-row">
              <input v-model="bridgeProjekt[t.regime]" :placeholder="bridgeHint(t.regime)" />
              <button class="primary" @click="runBridge(t.regime)">{{ bridgeLabel(t.regime) }}</button>
            </div>
          </div>

          <h4>🔗 Issue-Tracking (GitHub/GitLab)</h4>
          <div class="issue-form">
            <select v-model="issueForm.provider"><option value="github">GitHub</option><option value="gitlab">GitLab</option></select>
            <input v-model="issueForm.repo" :placeholder="issueForm.provider==='github' ? 'owner/repo' : 'group/project'" style="flex:1;min-width:160px" />
            <button class="primary" @click="createIssue">Issue erstellen</button>
          </div>
          <ul class="issue-list">
            <li v-for="is in incIssues" :key="is.id">
              <a :href="is.url" target="_blank">{{ is.title || is.url }}</a>
              <span class="issue-prov">{{ is.provider }}</span>
              <button @click="delIssue(is.id)">×</button>
            </li>
            <li v-if="!incIssues.length" class="hint">Noch keine verknüpften Issues. (Token-Env GITHUB_TOKEN/GITLAB_TOKEN nötig.)</li>
          </ul>

          </div><!-- /.idg-main -->
          <aside class="idg-aside">
            <h4>🕓 Verlauf</h4>
            <ul class="timeline">
              <li v-for="e in store.currentIncident.timeline" :key="e.id">
                <span class="ts">{{ shortTs(e.ts) }}</span>
                <b class="tl-event">{{ e.event }}</b>
                <span v-if="e.detail" class="tl-detail">{{ e.detail }}</span>
                <i class="tl-actor">{{ e.actor }}</i>
              </li>
              <li v-if="!(store.currentIncident.timeline || []).length" class="hint">Noch kein Verlauf erfasst.</li>
            </ul>
          </aside>
        </div><!-- /.incident-detail-grid -->
      </div>
    </section>

    <!-- ── Assets ────────────────────────────────────────────────────── -->
    <section v-show="tab === 'assets'" class="panel">
      <!-- Liste -->
      <template v-if="!store.currentAsset">
        <div class="filterbar">
          <button @click="store.fetchAssets()">Aktualisieren</button>
          <button class="primary" @click="newAsset">+ Manuelles Asset</button>
          <button @click="showAssetDiscovery = !showAssetDiscovery">🔎 Agentlose Erkennung (Syslog)</button>
          <span style="flex:1"></span>
          <span class="hint">Kritikalität & Tags steuern Priorisierung + Meldepflicht-Router.</span>
        </div>

        <!-- #1401: Agentlose Asset-Erkennung direkt bei den Assets (read-only Syslog-Discovery) -->
        <div v-if="showAssetDiscovery" class="assistant-panel" style="margin-bottom:12px">
          <h4>🔎 Agentlose Erkennung — Syslog-Quellen (read-only)</h4>
          <p class="hint">Erkennt Quellen, die per Syslog an den Wazuh-Manager (Agent <code>000</code>) liefern, also <b>ohne installierten Agenten</b> — read-only über den Indexer, kein Sync. Voraussetzung: PULL-Indexer-Verbindung in der Einrichtung.</p>
          <div class="issue-form">
            <label>Zeitfenster
              <select v-model.number="syslogHours">
                <option :value="1">1 Stunde</option><option :value="2">2 Stunden</option>
                <option :value="6">6 Stunden</option><option :value="24">24 Stunden</option>
                <option :value="168">7 Tage</option>
              </select>
            </label>
            <button @click="runSyslogDiscovery" :disabled="syslogBusy">{{ syslogBusy ? 'Suche …' : 'Quellen erkennen' }}</button>
            <span v-if="syslogMsg" class="copied">{{ syslogMsg }}</span>
          </div>
          <div v-if="syslogErr" class="banner err" style="margin-top:8px">{{ syslogErr }}</div>
          <div class="grid-scroll" v-if="syslogSources.length">
          <table class="grid mini" style="margin-top:8px">
            <thead><tr>
              <th style="width:28px"><input type="checkbox" :checked="syslogAllChecked" @change="toggleAllSyslog($event)" /></th>
              <th>Hostname</th><th>Absender-IP</th><th>Programm</th><th>Treffer</th><th>Zuletzt</th>
            </tr></thead>
            <tbody>
              <tr v-for="(s, i) in syslogSources" :key="(s.hostname || s.ip) + 'a' + i">
                <td><input type="checkbox" v-model="syslogSelected" :value="i" /></td>
                <td>{{ s.hostname || '—' }}</td><td>{{ s.ip || '—' }}</td>
                <td>{{ s.program || '—' }}</td><td>{{ s.count }}</td><td>{{ shortTs(s.last_seen) }}</td>
              </tr>
            </tbody>
          </table>
          </div>
          <p v-else-if="syslogChecked && !syslogErr" class="hint">Keine neuen Syslog-Quellen im Zeitfenster (oder alle bereits inventarisiert).</p>
          <div v-if="syslogSources.length" class="issue-form" style="margin-top:8px">
            <button class="primary" :disabled="!syslogSelected.length" @click="createSyslogAssets">{{ syslogSelected.length }} als Assets anlegen</button>
          </div>
        </div>
        <div class="grid-scroll">
        <table class="grid">
          <thead><tr><th>Asset</th><th>Status</th><th>Krit.</th><th>Umgebung</th><th>Risiko</th><th>Alarme</th><th>Incidents</th><th>Tags</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in store.assets" :key="a.id" class="clickable" @click="openAsset(a.id)">
              <td><b>{{ a.agent_name || '(unbenannt)' }}</b><div class="sub">{{ a.ip }} {{ a.os ? '· '+a.os : '' }}</div></td>
              <td><span class="agent-status" :class="a.agent_status || a.source">{{ statusDe(a) }}</span></td>
              <td><span class="krit-badge" :class="'k'+a.kritikalitaet">{{ a.kritikalitaet }}</span></td>
              <td>{{ a.umgebung || '—' }}</td>
              <td><span class="ampel" :class="a.risk?.ampel">{{ a.risk?.score ?? 0 }}</span></td>
              <td>{{ a.alert_count }}</td><td>{{ a.incident_count }}</td>
              <td class="tags-cell">{{ tagSummary(a) || '—' }}</td>
              <td>Details ›</td>
            </tr>
            <tr v-if="!store.assets.length"><td colspan="9" class="empty">Keine Assets. In der Einrichtung aus dem Wazuh-Manager importieren oder „+ Manuelles Asset".</td></tr>
          </tbody>
        </table>
        </div>
      </template>

      <!-- Detail -->
      <div v-else class="inc-detail">
        <div class="detail-bar"><button class="link-back" @click="store.currentAsset=null">‹ Zurück zur Liste</button></div>
        <div class="inc-headcard">
          <div class="ih-title">🖥️ {{ store.currentAsset.agent_name || '(manuelles Asset)' }}</div>
          <div class="ih-facts">
            <span class="agent-status" :class="store.currentAsset.agent_status || store.currentAsset.source">{{ statusDe(store.currentAsset) }}</span>
            <span class="ampel" :class="store.currentAsset.risk?.ampel">Risiko {{ store.currentAsset.risk?.score ?? 0 }}</span>
            <span v-if="store.currentAsset.ip">🌐 {{ store.currentAsset.ip }}</span>
            <span v-if="store.currentAsset.os">💿 {{ store.currentAsset.os }}</span>
            <span v-if="store.currentAsset.agent_version">Wazuh {{ store.currentAsset.agent_version }}</span>
            <span v-if="store.currentAsset.last_keepalive">letzter Kontakt: {{ shortTs(store.currentAsset.last_keepalive) }}</span>
          </div>
        </div>

        <div class="edit-box">
          <div class="asset-grid">
            <label v-if="['manuell','syslog'].includes(store.currentAsset.source)">Name<input v-model="assetForm.agent_name" placeholder="z.B. Hostname statt IP" /></label>
            <label>Kritikalität<select v-model.number="assetForm.kritikalitaet"><option v-for="k in [1,2,3,4,5]" :key="k" :value="k">{{ k }} – {{ kritLabel(k) }}</option></select></label>
            <label>Umgebung<select v-model="assetForm.umgebung"><option value="">—</option><option value="prod">Prod</option><option value="test">Test</option><option value="dev">Dev</option></select></label>
            <label>Lifecycle<select v-model="assetForm.lifecycle"><option value="aktiv">aktiv</option><option value="ausser_betrieb">außer Betrieb</option></select></label>
            <label>Owner<input v-model="assetForm.owner" /></label>
            <label>Datenklasse<input v-model="assetForm.datenklasse" placeholder="z.B. vertraulich" /></label>
            <label>Firma<input v-model="assetForm.organisation" /></label>
          </div>
          <div class="regime-flags" style="margin-top:8px">
            <label v-for="r in regimeOptions" :key="r.key"><input type="checkbox" v-model="assetForm[r.key]" /> {{ r.label }}</label>
          </div>
          <div class="form-actions" style="margin-top:8px">
            <button class="primary" @click="saveAssetForm">Speichern</button>
            <button v-if="store.currentAsset.source==='manuell'" class="warn" @click="removeAsset">Löschen</button>
            <span v-if="assetMsg" class="copied">{{ assetMsg }}</span>
          </div>
        </div>

        <h4>🛡️ Incidents auf diesem Asset ({{ (store.currentAsset.incidents||[]).length }})</h4>
        <div class="grid-scroll">
        <table class="grid mini"><tbody>
          <tr v-for="i in store.currentAsset.incidents" :key="i.id" class="clickable" @click="gotoIncident(i.id)">
            <td>#{{ i.id }}</td><td>{{ i.titel }}</td><td><span class="status-pill">{{ incStatusDe(i.status) }}</span></td><td><span class="sev-tag" :class="i.severity">{{ sevDe(i.severity) }}</span></td>
          </tr>
          <tr v-if="!(store.currentAsset.incidents||[]).length"><td colspan="4" class="empty">Keine Incidents.</td></tr>
        </tbody></table>
        </div>

        <h4>🚨 Alarme auf diesem Asset ({{ (store.currentAsset.alerts||[]).length }})</h4>
        <div class="grid-scroll">
        <table class="grid mini"><tbody>
          <tr v-for="al in store.currentAsset.alerts" :key="al.alert_uid" class="clickable" @click="openAlertDetail(al.alert_uid)">
            <td><span class="sev-tag" :class="al.severity">{{ sevDe(al.severity) }}</span></td><td>{{ al.description }}</td><td>{{ shortTs(al.event_ts) }}</td>
          </tr>
          <tr v-if="!(store.currentAsset.alerts||[]).length"><td colspan="3" class="empty">Keine Alarme.</td></tr>
        </tbody></table>
        </div>
      </div>
    </section>

    <!-- ── Schwachstellen-Register (#1343) ───────────────────────────── -->
    <section v-show="tab === 'vulnerabilities'" class="panel">
      <div class="mass-head">
        <h3>🛡️ Schwachstellen-Register <span class="hint-inline">(Wazuh-States, #1343)</span></h3>
        <div>
          <button @click="doVulnSync" :disabled="vulnSyncing">{{ vulnSyncing ? '⏳ Sync läuft …' : '🔄 Schwachstellen synchronisieren' }}</button>
        </div>
      </div>
      <p class="hint">Vollständiger Ist-Bestand der von Wazuh erkannten Schwachstellen — unabhängig davon, ob je ein Alarm ausgelöst wurde. Standard: nur erfasst/informativ. Bewusst als Alarm/Incident aufnehmen über „Aufnehmen".</p>
      <div v-if="vulnSyncMsg" class="banner ok">{{ vulnSyncMsg }}</div>

      <div class="cov-kpis">
        <div class="kpi"><div class="kpi-val bad">{{ store.vulnKpi.critical ?? 0 }}</div><div class="kpi-lbl">Kritisch</div></div>
        <div class="kpi"><div class="kpi-val bad">{{ store.vulnKpi.high ?? 0 }}</div><div class="kpi-lbl">Hoch</div></div>
        <div class="kpi"><div class="kpi-val">{{ store.vulnKpi.total ?? 0 }}</div><div class="kpi-lbl">Offen gesamt</div></div>
      </div>

      <div class="filterbar">
        <select v-model="vFilter.severity" @change="loadVulns"><option value="">Alle Schweren</option><option v-for="s in severities" :key="s" :value="s">{{ sevDe(s) }}</option></select>
        <select v-model="vFilter.triage_status" @change="loadVulns"><option value="">Alle Triage</option><option v-for="s in (store.vulnTriageStates || [])" :key="s" :value="s">{{ vulnTriageDe(s) }}</option></select>
        <label class="chk"><input type="checkbox" v-model="vShowSolved" @change="loadVulns" /> behobene (Solved) zeigen</label>
        <button @click="loadVulns">Aktualisieren</button>
      </div>

      <div v-if="vulnBulk.length" class="bulk-bar">
        <b>{{ vulnBulk.length }}</b> ausgewählt →
        <select v-model="vulnBulkTriage"><option value="">Triage wählen …</option>
          <option v-for="s in vulnTriageBulkable" :key="s" :value="s">{{ vulnTriageDe(s) }}</option></select>
        <button class="primary" :disabled="!vulnBulkTriage" @click="doBulkVulnTriage">Setzen</button>
        <button @click="vulnBulk = []">Auswahl leeren</button>
      </div>

      <div class="grid-scroll">
      <table class="grid">
        <thead><tr><th style="width:28px"></th><th>CVE</th><th>Schwere</th><th>CVSS</th><th>Paket</th><th>Fix</th><th>Asset</th><th>Wazuh</th><th>Triage</th><th></th></tr></thead>
        <tbody>
          <tr v-for="v in store.vulnerabilities" :key="v.id">
            <td><input type="checkbox" :value="v.id" v-model="vulnBulk" /></td>
            <td><a v-if="v.advisory_url" :href="v.advisory_url" target="_blank" rel="noopener">{{ v.cve_id }}</a><span v-else>{{ v.cve_id }}</span></td>
            <td><span class="sev-tag" :class="v.severity">{{ sevDe(v.severity) }}</span></td>
            <td>{{ v.cvss_score || '–' }}</td>
            <td>{{ v.package_name }} <span class="muted">{{ v.package_version }}</span></td>
            <td>{{ v.fixed_version || '—' }}</td>
            <td>{{ v.agent_name || '—' }}</td>
            <td><span class="status-pill" :class="{ solved: v.wazuh_status === 'Solved' }">{{ v.wazuh_status }}</span></td>
            <td>
              <select :value="v.triage_status" @change="onVulnTriage(v, $event)" :disabled="v.triage_status === 'promoted'">
                <option v-for="s in vulnTriageBulkable" :key="s" :value="s">{{ vulnTriageDe(s) }}</option>
                <option v-if="v.triage_status === 'promoted'" value="promoted">{{ vulnTriageDe('promoted') }}</option>
              </select>
            </td>
            <td>
              <button v-if="v.promoted_alert_uid || v.promoted_incident_id" disabled title="Bereits aufgenommen">✓ aufgenommen</button>
              <template v-else>
                <button @click="doPromote(v, 'alert')" title="Als regulären Alarm in den Triage-Workflow">+ Alarm</button>
                <button @click="doPromote(v, 'incident')" title="Direkt als Incident anlegen">+ Incident</button>
              </template>
            </td>
          </tr>
          <tr v-if="!store.vulnerabilities.length"><td colspan="10" class="empty">Keine Schwachstellen. Sync auslösen (States-Index) oder Filter prüfen.</td></tr>
        </tbody>
      </table>
      </div>
    </section>

    <!-- ── Maßnahmen (PIR-Tracking, zentral) ─────────────────────────── -->
    <section v-show="tab === 'massnahmen'" class="panel">
      <div class="mass-head">
        <h3>📋 Offene Maßnahmen aus Post-Incident-Reviews</h3>
        <div>
          <label class="chk"><input type="checkbox" v-model="massOnlyOpen" @change="loadMass" /> nur offene</label>
          <button @click="store.exportPirActions()">⬇️ CSV-Export</button>
        </div>
      </div>
      <p class="hint">Maßnahmen werden über den Abschluss des Incidents hinaus verfolgt (NIST/ISO 27035). Überfällige Fristen sind rot markiert.</p>
      <div class="grid-scroll" v-if="store.pirActions.length">
      <table class="grid">
        <thead><tr><th>Incident</th><th>Maßnahme</th><th>Owner</th><th>Frist</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="a in store.pirActions" :key="a.id" :class="{ overdue: isOverdue(a) }">
            <td><a class="inc-link" @click="openIncidentFromAction(a.incident_id)">#{{ a.incident_id }}</a>
              <div class="mass-inc-t">{{ a.incident_titel }}</div></td>
            <td>{{ a.beschreibung }}</td><td>{{ a.owner || '–' }}</td>
            <td>{{ a.frist || '–' }}</td>
            <td><select :value="a.status" @change="changeActionStatusGlobal(a.id, $event)">
              <option v-for="s in pirStates" :key="s" :value="s">{{ s }}</option></select></td>
          </tr>
        </tbody>
      </table>
      </div>
      <div v-else class="hint">Keine {{ massOnlyOpen ? 'offenen ' : '' }}Maßnahmen.</div>
    </section>

    <!-- ── Betrieb: Schicht/On-Call, Eskalation, RACI (#1318) ────────── -->
    <section v-show="tab === 'betrieb'" class="panel">
      <h3>🔁 Schichtübergabe (Handover)</h3>
      <div class="ho-add">
        <select v-model="hoForm.schicht"><option v-for="s in ['Früh','Spät','Nacht']" :key="s" :value="s">{{ s }}</option></select>
        <input v-model="hoForm.datum" type="date" />
        <input v-model="hoForm.an_user" placeholder="Übergabe an …" />
        <input v-model="hoForm.offene_punkte" placeholder="Offene Punkte" style="flex:1" />
        <button class="primary" @click="doSaveHandover">+ Übergabe</button>
      </div>
      <div class="grid-scroll" v-if="store.handovers.length">
      <table class="grid mini">
        <thead><tr><th>Datum</th><th>Schicht</th><th>Von→An</th><th>Offene Punkte</th><th></th></tr></thead>
        <tbody>
          <tr v-for="h in store.handovers" :key="h.id">
            <td>{{ h.datum }}</td><td>{{ h.schicht }}</td><td>{{ h.von_user }} → {{ h.an_user || '–' }}</td>
            <td>{{ h.offene_punkte }}</td>
            <td><button class="link-del" @click="store.deleteHandover(h.id)">✕</button></td>
          </tr>
        </tbody>
      </table>
      </div>
      <div v-else class="hint">Noch keine Schichtübergaben.</div>

      <h3>📈 Eskalationsmatrix</h3>
      <p class="hint">Wer wird bei welcher Severity auf welcher Stufe (mit Frist) benachrichtigt. SOC-CMM People/Process · ISO 27035.</p>
      <div class="grid-scroll">
      <table class="grid mini">
        <thead><tr><th>Severity</th><th>Stufe</th><th>Rolle</th><th>Person</th><th>Kontakt</th><th>Frist (Min.)</th><th></th></tr></thead>
        <tbody>
          <tr v-for="e in store.escalation" :key="e.id">
            <td><span class="sev-tag" :class="e.severity">{{ sevDe(e.severity) }}</span></td>
            <td>{{ e.stufe }}</td><td>{{ e.rolle }}</td><td>{{ e.person || '–' }}</td>
            <td>{{ e.kontakt || '–' }}</td><td>{{ e.frist_minuten }}</td>
            <td><button class="link-del" @click="store.deleteEscalation(e.id)">✕</button></td>
          </tr>
        </tbody>
      </table>
      </div>
      <div class="esc-add">
        <select v-model="escForm.severity"><option v-for="s in severities" :key="s" :value="s">{{ sevDe(s) }}</option></select>
        <input v-model.number="escForm.stufe" type="number" placeholder="Stufe" style="width:70px" />
        <input v-model="escForm.rolle" placeholder="Rolle" />
        <input v-model="escForm.person" placeholder="Person" />
        <input v-model="escForm.kontakt" placeholder="Kontakt (Tel/Mail)" />
        <input v-model.number="escForm.frist_minuten" type="number" placeholder="Frist" style="width:80px" />
        <button class="primary" :disabled="!escForm.rolle" @click="doSaveEscalation">+ Zeile</button>
      </div>

      <h3>🧩 RACI je Vorfallstyp</h3>
      <div class="grid-scroll" v-if="store.raci.length">
      <table class="grid mini">
        <thead><tr><th>Vorfallstyp</th><th>Rolle</th><th>RACI</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in store.raci" :key="r.id">
            <td>{{ r.vorfallstyp }}</td><td>{{ r.rolle }}</td><td><b>{{ r.raci }}</b></td>
            <td><button class="link-del" @click="store.deleteRaci(r.id)">✕</button></td>
          </tr>
        </tbody>
      </table>
      </div>
      <div class="esc-add">
        <input v-model="raciForm.vorfallstyp" placeholder="Vorfallstyp (z. B. Phishing)" />
        <input v-model="raciForm.rolle" placeholder="Rolle" />
        <select v-model="raciForm.raci"><option v-for="x in ['R','A','C','I']" :key="x" :value="x">{{ x }}</option></select>
        <button class="primary" :disabled="!raciForm.vorfallstyp || !raciForm.rolle" @click="doSaveRaci">+ RACI</button>
      </div>
    </section>

    <!-- ── Detektion: Use-Cases + ATT&CK-Heatmap (#1321) ─────────────── -->
    <section v-show="tab === 'detektion'" class="panel">
      <h3>🛰️ Detection-Use-Case-Register</h3>
      <p class="hint">Welche Bedrohung wird durch welche Wazuh-Regel(n) erkannt, gemappt auf MITRE ATT&CK. BSI DER.1 · NIST CSF Detect.</p>
      <div v-if="store.coverage" class="cov-kpis">
        <div class="kpi"><div class="kpi-val">{{ pct(store.coverage.coverage.coverage_pct) }}</div><div class="kpi-lbl">ATT&CK-Abdeckung</div></div>
        <div class="kpi"><div class="kpi-val ok">{{ store.coverage.coverage.counts.covered }}</div><div class="kpi-lbl">abgedeckt</div></div>
        <div class="kpi"><div class="kpi-val mid">{{ store.coverage.coverage.counts.partial }}</div><div class="kpi-lbl">teilweise</div></div>
        <div class="kpi"><div class="kpi-val bad">{{ store.coverage.coverage.counts.gap }}</div><div class="kpi-lbl">Lücken</div></div>
      </div>
      <div class="grid-scroll" v-if="store.usecases.length">
      <table class="grid mini">
        <thead><tr><th>Use-Case</th><th>Bedrohung</th><th>ATT&CK</th><th>Wazuh-Regeln</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in store.usecases" :key="u.id">
            <td>{{ u.name }}</td><td>{{ u.bedrohung }}</td>
            <td><span v-for="t in u.attack_techniques" :key="t" class="att-chip">{{ t }}</span></td>
            <td><code class="sha">{{ u.wazuh_rules }}</code></td>
            <td><select :value="u.status" @change="changeUcStatus(u, $event)"><option v-for="s in store.detectionStates" :key="s" :value="s">{{ s }}</option></select></td>
            <td><button class="link-del" @click="store.deleteUsecase(u.id)">✕</button></td>
          </tr>
        </tbody>
      </table>
      </div>
      <div v-else class="hint">Noch keine Use-Cases.</div>
      <div class="uc-add">
        <input v-model="ucForm.name" placeholder="Use-Case-Name" />
        <input v-model="ucForm.bedrohung" placeholder="Bedrohung" />
        <input v-model="ucForm.attack" placeholder="ATT&CK (z. B. T1566,T1059)" />
        <input v-model="ucForm.wazuh_rules" placeholder="Wazuh-Regeln/Gruppen" />
        <select v-model="ucForm.status"><option v-for="s in store.detectionStates" :key="s" :value="s">{{ s }}</option></select>
        <button class="primary" :disabled="!ucForm.name.trim()" @click="doSaveUsecase">+ Use-Case</button>
      </div>

      <div class="cov-src-head">
        <h3>🗺️ MITRE-ATT&CK-Coverage-Heatmap</h3>
        <div class="cov-src">
          <span class="lbl">Coverage-Quelle:</span>
          <select :value="store.coverageSource" @change="changeCoverageSource($event)">
            <option value="beides">Alarme + Regelwerk</option>
            <option value="alarme">nur synchronisierte Alarme</option>
            <option value="regelwerk">nur installiertes Regelwerk</option>
          </select>
        </div>
      </div>
      <div v-if="store.coverage" class="heatmap">
        <div v-for="tac in store.coverage.coverage.tactics" :key="tac.id" class="heat-col">
          <div class="heat-tactic" :title="tac.id">{{ tac.name }}</div>
          <div v-for="t in tac.techniques" :key="t.id" class="heat-cell" :class="'h-' + t.status"
               :title="heatTitle(t)">
            {{ t.id }}<span v-if="t.by_alerts">·🔔</span><span v-if="t.by_rules && t.by_rules.length">·📚{{ t.by_rules.length }}</span>
          </div>
        </div>
      </div>
      <div class="heat-legend"><span class="h-covered">abgedeckt</span> <span class="h-partial">teilweise (geplant/Tuning)</span> <span class="h-gap">Lücke</span> · 🔔 = reale Alarme · 📚 = durch Regel(n) abgedeckt</div>

      <details v-if="store.coverage && store.coverage.rule_candidates && store.coverage.rule_candidates.length" class="supp-box" open>
        <summary>🧩 Regelwerk-Abdeckung bestätigen ({{ store.coverage.rule_candidates.length }}) — durch Regel(n) abgedeckte Techniken ohne aktiven Use-Case</summary>
        <div class="issue-form" style="margin:6px 0">
          <button class="primary" :disabled="confirmAllBusy" @click="doConfirmAllCandidates">
            {{ confirmAllBusy ? 'Bestätige …' : `✓ Alle ${store.coverage.rule_candidates.length} bestätigen` }}
          </button>
          <span class="hint">Legt für alle vorgeschlagenen Techniken Use-Cases an bzw. aktiviert sie.</span>
        </div>
        <div class="grid-scroll">
        <table class="grid mini">
          <thead><tr><th>Technik</th><th>Taktik</th><th>Regel-IDs</th><th></th></tr></thead>
          <tbody>
            <tr v-for="c in store.coverage.rule_candidates" :key="c.technique">
              <td><b>{{ c.technique }}</b> {{ c.name }}</td>
              <td><i>{{ c.tactic }}</i></td>
              <td><span v-for="r in c.rule_ids" :key="r" class="att-chip" :title="`Wazuh-Regel ${r}`">{{ r }}</span></td>
              <td><button class="primary sm" @click="doConfirmCandidate(c)">✓ bestätigen{{ c.existing_usecase_id ? ' (aktivieren)' : '' }}</button></td>
            </tr>
          </tbody>
        </table>
        </div>
      </details>

      <details v-if="store.coverage && store.coverage.suggestions.length" class="supp-box">
        <summary>💡 Vorschläge aus realen Alarmen ({{ store.coverage.suggestions.length }}) — Techniken ohne Use-Case</summary>
        <ul><li v-for="s in store.coverage.suggestions" :key="s.id"><b>{{ s.id }}</b> {{ s.name }} <i>({{ s.tactic }})</i></li></ul>
      </details>
      <details v-if="store.coverage && store.coverage.gaps.length" class="supp-box">
        <summary>🕳️ Lücken-Report ({{ store.coverage.gaps.length }} Techniken ohne Detektion)</summary>
        <ul class="gap-list"><li v-for="g in store.coverage.gaps" :key="g.id"><b>{{ g.id }}</b> {{ g.name }} <i>({{ g.tactic }})</i></li></ul>
      </details>

      <!-- ── Regelwerk-Explorer (#1348) ──────────────────────────────── -->
      <div class="mass-head">
        <h3>📚 Wazuh-Regelwerk (read-only)</h3>
        <button class="primary" :disabled="store.rulesLoading" @click="doSyncRules">
          {{ store.rulesLoading ? '⏳ lädt…' : '⬇ Regelwerk laden/aktualisieren' }}
        </button>
      </div>
      <p class="hint">
        Das komplette installierte Regelwerk read-only durchsuchen (id, Level, Beschreibung,
        Gruppen, ATT&CK, Datei, Status). Quelle: Wazuh-Manager-API. BSI DER.1 · NIST CSF Detect ·
        SOC-CMM Technology. Der Manager-API-Benutzer braucht die Berechtigung
        <code>rules:read</code> (z. B. eine <i>soc-reader</i>-Rolle).
      </p>
      <p class="hint" v-if="store.rulesSync">
        Zuletzt geladen: {{ store.rulesSync.last_run_at ? new Date(store.rulesSync.last_run_at).toLocaleString() : '–' }}
        <span v-if="store.rulesSync.last_status === 'ok'"> · {{ store.rulesSync.last_count }} Regeln</span>
        <span v-else-if="store.rulesSync.last_status === 'error'" class="bad"> · ⚠ {{ store.rulesSync.last_error }}</span>
        <span v-if="ruleSyncMsg"> · {{ ruleSyncMsg }}</span>
      </p>

      <div class="uc-add">
        <input v-model="ruleFilter.q" placeholder="Volltext (Beschreibung/ID/Datei)" style="flex:1" @keyup.enter="doFetchRules" />
        <input v-model="ruleFilter.group" placeholder="Gruppe (z. B. authentication)" />
        <input v-model="ruleFilter.mitre" placeholder="ATT&CK (z. B. T1110)" style="width:130px" />
        <input v-model.number="ruleFilter.min_level" type="number" placeholder="≥ Level" style="width:80px" />
        <select v-model="ruleFilter.status">
          <option value="">Status (alle)</option>
          <option value="enabled">enabled</option>
          <option value="disabled">disabled</option>
        </select>
        <button class="primary" @click="doFetchRules">🔍 Suchen</button>
        <button @click="resetRuleFilter">Zurücksetzen</button>
      </div>
      <p class="hint" v-if="store.rulesTotal">{{ store.rulesShown }} von {{ store.rulesTotal }} Regeln angezeigt.</p>

      <div class="grid-scroll" v-if="store.rules.length">
      <table class="grid mini">
        <thead><tr><th>ID</th><th>Level</th><th>Beschreibung</th><th>Gruppen</th><th>ATT&CK</th><th>Datei</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="r in store.rules" :key="r.id" class="clickable" @click="ruleDetail = r">
            <td><code class="sha">{{ r.id }}</code></td>
            <td>{{ r.level }}</td>
            <td>{{ r.description }}</td>
            <td><span v-for="g in (r.groups || []).slice(0, 4)" :key="g" class="att-chip">{{ g }}</span><span v-if="(r.groups || []).length > 4" class="hint">+{{ r.groups.length - 4 }}</span></td>
            <td><span v-for="m in r.mitre" :key="m" class="att-chip">{{ m }}</span></td>
            <td><code class="sha">{{ r.filename }}</code></td>
            <td>{{ r.status || '–' }}</td>
          </tr>
        </tbody>
      </table>
      </div>
      <div v-else class="hint">Noch kein Regelwerk geladen oder kein Treffer — „Regelwerk laden/aktualisieren" klicken.</div>

      <div v-if="ruleDetail" class="supp-box rule-detail">
        <div class="mass-head">
          <h4>Regel {{ ruleDetail.id }} (Level {{ ruleDetail.level }})</h4>
          <button class="link-del" @click="ruleDetail = null">✕</button>
        </div>
        <p>{{ ruleDetail.description }}</p>
        <p class="hint"><b>Datei:</b> <code class="sha">{{ ruleDetail.filename }}</code> · <b>Status:</b> {{ ruleDetail.status || '–' }}</p>
        <p class="hint" v-if="(ruleDetail.groups || []).length"><b>Gruppen:</b> <span v-for="g in ruleDetail.groups" :key="g" class="att-chip">{{ g }}</span></p>
        <p class="hint" v-if="(ruleDetail.mitre || []).length"><b>ATT&CK:</b> <span v-for="m in ruleDetail.mitre" :key="m" class="att-chip">{{ m }}</span></p>
      </div>
    </section>

    <!-- ── Threat-Intelligence / IOC (#1322) ─────────────────────────── -->
    <section v-show="tab === 'threatintel'" class="panel">
      <div class="mass-head">
        <h3>🌐 Threat-Intelligence — IOC-Feeds</h3>
        <button @click="doRescanIocs">🔄 Alarme neu abgleichen</button>
      </div>
      <p class="hint">IOC-Feeds (IP/Domain/Hash/URL) pflegen; Alarme bei Treffer markieren + priorisieren. ISO/IEC 27001 A.5.7 · NIST CSF Identify.</p>

      <details class="supp-box">
        <summary>📥 Import (CSV / Wertliste)</summary>
        <p class="hint">Eine Zeile je IOC: <code>wert[;typ[;confidence[;beschreibung]]]</code>. Typ wird sonst erraten (IP/Hash/URL/Domain).</p>
        <textarea v-model="iocImport.text" rows="4" placeholder="1.2.3.4;ip;90;C2&#10;evil.example.test&#10;44d88612fea8a8f36de82e1278abb02f" style="width:100%"></textarea>
        <div class="ho-add">
          <input v-model="iocImport.quelle" placeholder="Quelle (z. B. MISP, OTX)" />
          <button class="primary" :disabled="!iocImport.text.trim()" @click="doImportIocs">Importieren</button>
          <span v-if="iocImport.result" class="hint">{{ iocImport.result }}</span>
        </div>
      </details>

      <div class="ho-add">
        <select v-model="iocForm.typ"><option v-for="t in store.iocTypes" :key="t" :value="t">{{ t }}</option></select>
        <input v-model="iocForm.wert" placeholder="Wert (IP/Domain/Hash/URL)" style="flex:1" />
        <input v-model="iocForm.quelle" placeholder="Quelle" />
        <input v-model.number="iocForm.confidence" type="number" placeholder="Conf." style="width:70px" />
        <input v-model="iocForm.gueltig_bis" type="date" />
        <button class="primary" :disabled="!iocForm.wert.trim()" @click="doSaveIoc">+ IOC</button>
      </div>
      <div class="grid-scroll" v-if="store.iocs.length">
      <table class="grid mini">
        <thead><tr><th>Typ</th><th>Wert</th><th>Quelle</th><th>Conf.</th><th>Gültig bis</th><th></th></tr></thead>
        <tbody>
          <tr v-for="i in store.iocs" :key="i.id" :class="{ 'evi-deleted': !i.enabled }">
            <td><span class="att-chip">{{ i.typ }}</span></td>
            <td><code class="sha">{{ i.wert }}</code></td><td>{{ i.quelle || '–' }}</td>
            <td>{{ i.confidence }}</td><td>{{ i.gueltig_bis || '∞' }}</td>
            <td><button class="link-del" @click="store.deleteIoc(i.id)">✕</button></td>
          </tr>
        </tbody>
      </table>
      </div>
      <div v-else class="hint">Noch keine IOCs gepflegt.</div>

      <h3>🔔 Alarme mit IOC-Treffer ({{ store.iocAlerts.length }})</h3>
      <div class="grid-scroll" v-if="store.iocAlerts.length">
      <table class="grid mini">
        <thead><tr><th>Zeit</th><th>Schwere</th><th>Beschreibung</th><th>IOC-Treffer</th></tr></thead>
        <tbody>
          <tr v-for="al in store.iocAlerts" :key="al.alert_uid" class="clickable" @click="openAlertDetail(al.alert_uid)">
            <td>{{ shortTs(al.event_ts) }}</td><td><span class="sev-tag" :class="al.severity">{{ sevDe(al.severity) }}</span></td>
            <td>{{ al.description }}</td>
            <td><span v-for="(h, idx) in al.ioc_hits" :key="idx" class="ioc-hit">{{ h.typ }}:{{ h.wert }}</span></td>
          </tr>
        </tbody>
      </table>
      </div>
      <div v-else class="hint">Keine Alarme mit IOC-Treffer.</div>
    </section>

    <!-- ── Log-Quellen / Coverage + Health (#1324) ───────────────────── -->
    <section v-show="tab === 'logquellen'" class="panel">
      <h3>📡 Log-Quellen &amp; Coverage</h3>
      <p class="hint">Welche Quellen/Agenten sind onboarded, senden sie noch (Health), welche kritischen Assets fehlen. BSI DER.1 · OPS.1.1.5.</p>
      <div v-if="store.logHealth" class="cov-kpis">
        <div class="kpi"><div class="kpi-val ok">{{ store.logHealth.counts.aktiv }}</div><div class="kpi-lbl">aktiv</div></div>
        <div class="kpi"><div class="kpi-val mid">{{ store.logHealth.counts.still }}</div><div class="kpi-lbl">still (>{{ store.logHealth.silent_days }} Tage)</div></div>
        <div class="kpi"><div class="kpi-val bad">{{ store.logHealth.counts.offline }}</div><div class="kpi-lbl">offline</div></div>
        <div class="kpi"><div class="kpi-val bad">{{ store.logHealth.gap_count }}</div><div class="kpi-lbl">Coverage-Lücken</div></div>
      </div>
      <div class="grid-scroll" v-if="store.logHealth && store.logHealth.sources.length">
      <table class="grid mini">
        <thead><tr><th>Quelle</th><th>Typ</th><th>Health</th><th>Kritikalität</th><th>Letzter Eingang</th><th>Alarme</th><th></th></tr></thead>
        <tbody>
          <tr v-for="s in store.logHealth.sources" :key="s.name" :class="{ overdue: s.is_gap }">
            <td>{{ s.name }}<span v-if="s.is_gap" title="Coverage-Lücke (kritisch)"> 🕳️</span></td>
            <td>{{ s.typ }}</td>
            <td><span class="health-pill" :class="'hp-' + s.status">{{ s.status }}</span></td>
            <td>{{ s.kritikalitaet ?? '–' }}</td>
            <td>{{ s.last_eingang ? shortTs(s.last_eingang) : '—' }}<span v-if="s.age_days != null" class="ueb-date"> ({{ s.age_days }} T.)</span></td>
            <td>{{ s.alert_count }}</td>
            <td></td>
          </tr>
        </tbody>
      </table>
      </div>
      <div v-else class="hint">Keine Log-Quellen — Assets im „🖥️ Assets"-Tab importieren.</div>

      <h3>➕ Nicht-Agent-Quellen (Register)</h3>
      <p class="hint">Erwartete Quellen ohne Wazuh-Agent (Syslog, Firewall, Cloud) erfassen, damit Ausbleiben als Lücke sichtbar wird.</p>
      <div class="ho-add">
        <input v-model="lsForm.name" placeholder="Name (muss Alarm-agent_name entsprechen)" />
        <input v-model="lsForm.typ" placeholder="Typ (syslog/firewall/cloud)" />
        <label class="chk"><input type="checkbox" v-model="lsForm.erwartet" /> erwartet</label>
        <button class="primary" :disabled="!lsForm.name.trim()" @click="doSaveLogSource">+ Quelle</button>
      </div>
      <div class="grid-scroll" v-if="store.logHealth && store.logHealth.register.length">
      <table class="grid mini">
        <thead><tr><th>Name</th><th>Typ</th><th>Erwartet</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in store.logHealth.register" :key="r.id">
            <td>{{ r.name }}</td><td>{{ r.typ }}</td><td>{{ r.erwartet ? 'ja' : 'nein' }}</td>
            <td><button class="link-del" @click="store.deleteLogSource(r.id)">✕</button></td>
          </tr>
        </tbody>
      </table>
      </div>
    </section>

    <!-- ── Threat-Hunting (#1323) ────────────────────────────────────── -->
    <section v-show="tab === 'hunting'" class="panel">
      <h3>🔭 Threat-Hunting</h3>
      <p class="hint">Proaktive, hypothesengetriebene Hunts (oft ATT&CK-basiert): Hypothese → Ad-hoc-Indexer-Query → Findings → Ergebnis. SOC-CMM Services · NIST CSF Detect.</p>

      <details class="supp-box" open>
        <summary>🔎 Ad-hoc-Indexer-Query (read-only)</summary>
        <p class="hint">Lucene/query_string gegen den Wazuh-Indexer, z. B. <code>data.srcip:1.2.3.4 AND rule.level:&gt;=10</code>.</p>
        <textarea v-model="huntQuery" rows="2" placeholder="data.win.eventID:4625 AND rule.level:>=5" style="width:100%"></textarea>
        <div class="ho-add">
          <button class="primary" :disabled="!huntQuery.trim()" @click="doRunQuery">▶ Ausführen</button>
          <span v-if="huntResult" class="hint">{{ huntResult.ok ? `${huntResult.total} Treffer (${huntResult.hits.length} angezeigt)` : '⚠ ' + huntResult.error }}</span>
        </div>
        <div class="grid-scroll" v-if="huntResult && huntResult.ok && huntResult.hits.length">
        <table class="grid mini">
          <thead><tr><th>Zeit</th><th>Schwere</th><th>Beschreibung</th><th>Agent</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in huntResult.hits" :key="i">
              <td>{{ shortTs(h.event_ts) }}</td><td><span class="sev-tag" :class="h.severity">{{ sevDe(h.severity) }}</span></td>
              <td>{{ h.description }}</td><td>{{ h.agent_name }}</td>
            </tr>
          </tbody>
        </table>
        </div>
      </details>

      <div class="ho-add">
        <input v-model="huntForm.hypothese" placeholder="Hypothese" style="flex:1" />
        <input v-model="huntForm.attack_bezug" placeholder="ATT&CK (z. B. T1021)" style="width:140px" />
        <input v-model="huntForm.jaeger" placeholder="Jäger" style="width:120px" />
        <input v-model="huntForm.datum" type="date" />
        <button class="primary" :disabled="!huntForm.hypothese.trim()" @click="doSaveHunt">+ Hunt</button>
      </div>
      <div v-for="h in store.hunts" :key="h.id" class="ueb-card">
        <div class="ueb-head">
          <b>{{ h.hypothese }}</b>
          <span v-if="h.attack_bezug" class="att-chip">{{ h.attack_bezug }}</span>
          <span class="ueb-date">{{ h.datum }} · {{ h.jaeger }}</span>
          <span class="ueb-erg" :class="'erg-' + (h.ergebnis === 'bestaetigt' ? 'bestanden' : h.ergebnis === 'verworfen' ? 'teilweise' : '')">{{ h.ergebnis }}</span>
          <button class="link-del" @click="store.deleteHunt(h.id)">✕</button>
        </div>
        <div class="ueb-body">
          <label>Query<input v-model="h.query" /></label>
          <label>Findings<textarea v-model="h.findings" rows="2"></textarea></label>
          <div class="ueb-row">
            <label>Status<select v-model="h.status"><option value="laufend">laufend</option><option value="abgeschlossen">abgeschlossen</option></select></label>
            <label>Ergebnis<select v-model="h.ergebnis"><option value="offen">offen</option><option value="bestaetigt">bestätigt</option><option value="verworfen">verworfen</option></select></label>
          </div>
          <div class="ho-add">
            <button class="primary" @click="doUpdateHunt(h)">💾 Speichern</button>
            <button @click="doEscalateHunt(h)">→ als Incident eskalieren</button>
          </div>
        </div>
      </div>
      <div v-if="!store.hunts.length" class="hint">Noch keine Hunts dokumentiert.</div>
    </section>

    <!-- ── SOC-Reifegrad (SOC-CMM) (#1326) ───────────────────────────── -->
    <section v-show="tab === 'reifegrad'" class="panel">
      <div class="mass-head">
        <h3>📊 SOC-Reifegrad-Self-Assessment (SOC-CMM)</h3>
        <div>
          <button @click="store.exportAssessment('pdf')">📄 PDF</button>
          <button @click="store.exportAssessment('docx')">📝 DOCX</button>
        </div>
      </div>
      <p class="hint">Selbstbewertung entlang der 5 SOC-CMM-Domänen mit Mapping zu ISO 27035 / NIST CSF / BSI DER, Reifegrad 0–5. Vorbefüllung aus echten SOC-Daten.</p>
      <div v-if="store.assessment" class="cov-kpis">
        <div class="kpi"><div class="kpi-val" :class="reifeClass(assessSummary.gesamt)">{{ assessSummary.gesamt.toFixed(2) }}</div><div class="kpi-lbl">Gesamt-Reifegrad / 5</div></div>
        <div v-for="d in assessSummary.domains" :key="d.key" class="kpi">
          <div class="kpi-val" :class="reifeClass(d.reifegrad)">{{ d.reifegrad.toFixed(1) }}</div><div class="kpi-lbl">{{ d.name }}</div>
        </div>
      </div>
      <div v-if="store.assessment" v-for="d in store.assessment.catalog" :key="d.key" class="reife-domain">
        <h4>{{ d.name }}</h4>
        <div class="grid-scroll">
        <table class="grid mini">
          <thead><tr><th>Aspekt</th><th>Norm</th><th>Reifegrad (0–5)</th></tr></thead>
          <tbody>
            <tr v-for="a in d.aspekte" :key="a.key">
              <td>{{ a.name }}<span v-if="store.assessment.suggestions[a.key] != null" class="auto-hint" title="Vorschlag aus echten Daten"> 💡{{ store.assessment.suggestions[a.key] }}</span></td>
              <td class="reife-norm">{{ a.norm }}</td>
              <td><select v-model.number="scoreModel[a.key]"><option v-for="n in [0,1,2,3,4,5]" :key="n" :value="n">{{ n }}</option></select></td>
            </tr>
          </tbody>
        </table>
        </div>
      </div>
      <div class="ho-add">
        <input v-model="assessForm.durchgefuehrt_von" placeholder="Durchgeführt von" />
        <input v-model="assessForm.datum" type="date" />
        <button class="primary" @click="doSaveAssessment">💾 Assessment speichern</button>
      </div>
      <details v-if="store.assessment && store.assessment.history.length" class="supp-box">
        <summary>📈 Reifegrad-Verlauf ({{ store.assessment.history.length }} Assessments)</summary>
        <div class="grid-scroll">
        <table class="grid mini">
          <thead><tr><th>Datum</th><th>Von</th><th>Gesamt-Reifegrad</th></tr></thead>
          <tbody>
            <tr v-for="h in store.assessment.history" :key="h.id">
              <td>{{ h.datum || shortTs(h.created_at) }}</td><td>{{ h.durchgefuehrt_von }}</td>
              <td><b>{{ h.gesamt_reifegrad }}</b> / 5</td>
            </tr>
          </tbody>
        </table>
        </div>
      </details>
    </section>

    <!-- ── Übungen / Tests (#1319) ───────────────────────────────────── -->
    <section v-show="tab === 'uebungen'" class="panel">
      <div class="mass-head">
        <h3>🎯 SOC-Übungen &amp; Detection-Tests</h3>
        <button @click="store.exportUebungen()">⬇️ CSV-Export</button>
      </div>
      <p class="hint">ISO 22398 (Übungs-Lebenszyklus Design→Develop→Conduct→Evaluate→Improve) · ISO/IEC 27035 (Lessons Learnt) · BSI DER.4. Tabletop-Szenarien + Detection-Tests mit Zielen, MSEL-Injects, After-Action-Report und nachverfolgtem Improvement Plan.</p>
      <div class="ueb-add">
        <select v-model="uebForm.typ"><option value="tabletop">Tabletop</option><option value="detection_test">Detection-Test</option></select>
        <input v-model="uebForm.titel" placeholder="Titel" style="flex:1" />
        <input v-model="uebForm.datum" type="date" />
        <input v-model="uebForm.teilnehmer" placeholder="Teilnehmer" />
        <button class="primary" :disabled="!uebForm.titel.trim()" @click="doSaveUebung">+ Übung planen</button>
      </div>
      <div v-for="u in store.uebungen" :key="u.id" class="ueb-card">
        <div class="ueb-head">
          <span class="ueb-typ">{{ u.typ === 'detection_test' ? '🔬 Detection-Test' : '🗣️ Tabletop' }}</span>
          <b>{{ u.titel }}</b>
          <span class="ueb-date">{{ u.datum }}</span>
          <span class="ueb-erg" :class="'erg-' + u.ergebnis">{{ u.ergebnis }}</span>
          <button @click="toggleUebDetail(u.id)">{{ openUebId === u.id ? '▲ schließen' : '▼ ISO-22398-Details' }}</button>
          <button class="link-del" @click="store.deleteUebung(u.id)">✕</button>
        </div>
        <!-- Lebenszyklus-Stepper -->
        <div class="ueb-lifecycle">
          <span v-for="(ph, i) in store.uebungMeta.lifecycle" :key="ph"
                :class="['lc-step', { active: (u.lifecycle || 'design') === ph, done: lcIndex(u.lifecycle) > i }]">
            {{ i + 1 }}. {{ lcLabel(ph) }}
          </span>
        </div>
        <div class="ueb-body">
          <label>Szenario<textarea v-model="u.szenario" rows="2"></textarea></label>
          <div class="ueb-row" v-if="u.typ === 'detection_test'">
            <label>Erwartete Erkennung<input v-model="u.erwartete_erkennung" /></label>
            <label>Tatsächliche Erkennung<input v-model="u.tatsaechliche_erkennung" /></label>
          </div>
          <div class="ueb-row">
            <label>Lebenszyklus-Phase<select v-model="u.lifecycle"><option v-for="ph in store.uebungMeta.lifecycle" :key="ph" :value="ph">{{ lcLabel(ph) }}</option></select></label>
            <label>Status<select v-model="u.status"><option v-for="s in store.uebungMeta.states" :key="s" :value="s">{{ s }}</option></select></label>
            <label>Ergebnis<select v-model="u.ergebnis"><option v-for="e in store.uebungMeta.ergebnis" :key="e" :value="e">{{ e }}</option></select></label>
          </div>
          <div class="ueb-row">
            <label>Übungsleitung<input v-model="u.uebungsleitung" placeholder="Exercise Director" /></label>
            <label>Moderator<input v-model="u.moderator" /></label>
            <label>Evaluator<input v-model="u.evaluator" /></label>
          </div>
          <label>Auswertung<textarea v-model="u.auswertung" rows="2"></textarea></label>
          <label>Abgeleitete Maßnahmen (Freitext)<textarea v-model="u.massnahmen" rows="2"></textarea></label>
          <button class="primary" @click="doUpdateUebung(u)">💾 Speichern</button>
        </div>

        <!-- ISO-22398-Detail-Bereich (Ziele, MSEL, AAR, Improvement Plan) -->
        <div v-if="openUebId === u.id && store.currentUebung && store.currentUebung.id === u.id" class="ueb-detail">
          <!-- Übungsziele -->
          <h4>🎯 Übungsziele &amp; Bewertungskriterien (Performance-Objectives)</h4>
          <table class="ueb-tab">
            <thead><tr><th>Ziel</th><th>Typ</th><th>Kriterien</th><th>Soll</th><th>Ist</th><th>Bewertung</th><th></th></tr></thead>
            <tbody>
              <tr v-for="z in store.currentUebung.ziele" :key="z.id">
                <td><input v-model="z.ziel" /></td>
                <td><select v-model="z.typ"><option v-for="t in store.uebungMeta.ziel_types" :key="t" :value="t">{{ t }}</option></select></td>
                <td><input v-model="z.kriterien" /></td>
                <td><input v-model="z.soll" /></td>
                <td><input v-model="z.ist" /></td>
                <td><select v-model="z.bewertung"><option v-for="b in store.uebungMeta.ziel_bewertung" :key="b" :value="b">{{ b }}</option></select></td>
                <td><button @click="store.saveUebungZiel(u.id, z)">💾</button><button class="link-del" @click="store.deleteUebungZiel(u.id, z.id)">✕</button></td>
              </tr>
              <tr>
                <td><input v-model="zielForm.ziel" placeholder="Neues Ziel" /></td>
                <td><select v-model="zielForm.typ"><option v-for="t in store.uebungMeta.ziel_types" :key="t" :value="t">{{ t }}</option></select></td>
                <td><input v-model="zielForm.kriterien" placeholder="Kriterien" /></td>
                <td><input v-model="zielForm.soll" /></td>
                <td><input v-model="zielForm.ist" /></td>
                <td><select v-model="zielForm.bewertung"><option v-for="b in store.uebungMeta.ziel_bewertung" :key="b" :value="b">{{ b }}</option></select></td>
                <td><button class="primary" :disabled="!zielForm.ziel.trim()" @click="addZiel(u.id)">+</button></td>
              </tr>
            </tbody>
          </table>

          <!-- MSEL-Injects -->
          <h4>📋 Szenario-Verlauf (MSEL · getaktete Injects)</h4>
          <table class="ueb-tab">
            <thead><tr><th>Zeit</th><th>Inject</th><th>Erwartete Reaktion</th><th>Tatsächl. Reaktion</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-for="inj in store.currentUebung.injects" :key="inj.id">
                <td><input v-model="inj.zeit" style="width:70px" /></td>
                <td><input v-model="inj.beschreibung" /></td>
                <td><input v-model="inj.erwartete_reaktion" /></td>
                <td><input v-model="inj.tatsaechliche_reaktion" /></td>
                <td><select v-model="inj.status"><option v-for="s in store.uebungMeta.inject_states" :key="s" :value="s">{{ s }}</option></select></td>
                <td><button @click="store.saveUebungInject(u.id, inj)">💾</button><button class="link-del" @click="store.deleteUebungInject(u.id, inj.id)">✕</button></td>
              </tr>
              <tr>
                <td><input v-model="injForm.zeit" placeholder="T+15" style="width:70px" /></td>
                <td><input v-model="injForm.beschreibung" placeholder="Inject" /></td>
                <td><input v-model="injForm.erwartete_reaktion" /></td>
                <td><input v-model="injForm.tatsaechliche_reaktion" /></td>
                <td><select v-model="injForm.status"><option v-for="s in store.uebungMeta.inject_states" :key="s" :value="s">{{ s }}</option></select></td>
                <td><button class="primary" :disabled="!injForm.beschreibung.trim()" @click="addInject(u.id)">+</button></td>
              </tr>
            </tbody>
          </table>

          <!-- After-Action-Report -->
          <h4>📝 After-Action-Report (ISO/IEC 27035)</h4>
          <div class="ueb-aar">
            <label>Stärken<textarea v-model="u.aar_staerken" rows="2"></textarea></label>
            <label>Verbesserungsbereiche<textarea v-model="u.aar_verbesserung" rows="2"></textarea></label>
            <label>Lessons Learned<textarea v-model="u.aar_lessons" rows="2"></textarea></label>
            <label>Empfehlungen<textarea v-model="u.aar_empfehlungen" rows="2"></textarea></label>
            <label>Übungsplan (EXPLAN)<textarea v-model="u.explan" rows="2"></textarea></label>
            <div class="ueb-row">
              <label>AAR-Freigabe durch<input v-model="u.aar_signoff_by" placeholder="Name (optional)" /></label>
              <button class="primary" @click="doSaveAar(u)">💾 AAR speichern</button>
            </div>
          </div>

          <!-- Improvement Plan -->
          <h4>🛠️ Improvement Plan / Korrekturmaßnahmen (verfolgt bis Erledigung)</h4>
          <table class="ueb-tab">
            <thead><tr><th>Maßnahme</th><th>Owner</th><th>Frist</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr v-for="m in store.currentUebung.massnahmen_plan" :key="m.id">
                <td>{{ m.beschreibung }}</td>
                <td>{{ m.owner || '—' }}</td>
                <td>{{ m.frist || '—' }}</td>
                <td><select :value="m.status" @change="store.setUebungMassnahmeStatus(u.id, m.id, ($event.target as HTMLSelectElement).value)">
                  <option v-for="s in store.uebungMeta.mass_states" :key="s" :value="s">{{ s }}</option></select></td>
                <td><button class="link-del" @click="store.deleteUebungMassnahme(u.id, m.id)">✕</button></td>
              </tr>
              <tr>
                <td><input v-model="massForm.beschreibung" placeholder="Maßnahme" /></td>
                <td><input v-model="massForm.owner" placeholder="Owner" /></td>
                <td><input v-model="massForm.frist" type="date" /></td>
                <td><select v-model="massForm.status"><option v-for="s in store.uebungMeta.mass_states" :key="s" :value="s">{{ s }}</option></select></td>
                <td><button class="primary" :disabled="!massForm.beschreibung.trim()" @click="addMass(u.id)">+</button></td>
              </tr>
            </tbody>
          </table>

          <div class="ueb-aar-export">
            <button @click="store.exportAar(u.id, 'docx')">⬇️ AAR DOCX</button>
            <button @click="store.exportAar(u.id, 'pdf')">⬇️ AAR PDF</button>
          </div>
        </div>
      </div>
      <div v-if="!store.uebungen.length" class="hint">Noch keine Übungen geplant.</div>
    </section>

    <!-- ── Berichts-Center (#1350) ───────────────────────────────────── -->
    <section v-show="tab === 'berichte'" class="panel">
      <div class="mass-head">
        <h3>📑 Berichts-Center <span class="hint-inline">(ISO 27035 / SOC-CMM)</span></h3>
      </div>
      <p class="hint">Vier Berichtstypen über einen frei einstellbaren Zeitraum als Word (DOCX) oder PDF —
        inkl. Bearbeitungszeiten (MTTA/MTTR, Zeit bis Triage). Quartals-/Jahresberichte werden bei
        aktiviertem Scheduler automatisch erzeugt und unten gelistet.</p>

      <div class="bericht-zeitraum">
        <span class="bz-title">🗓️ Berichtszeitraum</span>
        <label>Schnellauswahl
          <select v-model="berichtPreset" @change="applyPreset">
            <option value="custom">Frei (von/bis)</option>
            <option value="30">Letzte 30 Tage</option>
            <option value="90">Letzte 90 Tage</option>
            <option value="quartal">Aktuelles Quartal</option>
            <option value="jahr">Aktuelles Jahr</option>
          </select>
        </label>
        <label>Von <input type="date" v-model="berichtVon" @change="berichtPreset='custom'" /></label>
        <label>Bis <input type="date" v-model="berichtBis" @change="berichtPreset='custom'" /></label>
      </div>

      <div class="report-grid">
        <div v-for="t in store.berichtTypen" :key="t.key" class="report-card">
          <div class="report-head">
            <span class="report-titel">{{ t.titel }}</span>
            <span class="report-norm">{{ t.norm }}</span>
          </div>
          <p class="report-desc">{{ t.beschreibung }}</p>
          <div class="report-actions">
            <button class="primary" :disabled="berichtBusy === t.key + ':docx'" @click="dlBericht(t.key, 'docx')">{{ berichtBusy === t.key + ':docx' ? '⏳ …' : '📝 Word' }}</button>
            <button :disabled="berichtBusy === t.key + ':pdf'" @click="dlBericht(t.key, 'pdf')">{{ berichtBusy === t.key + ':pdf' ? '⏳ …' : '📄 PDF' }}</button>
          </div>
        </div>
      </div>

      <h3>📂 Automatisch erzeugte Berichte <span class="hint-inline">({{ store.berichtRuns.length }})</span></h3>
      <div class="grid-scroll">
      <table class="grid">
        <thead><tr><th>Erzeugt</th><th>Typ</th><th>Periode</th><th>Zeitraum</th><th>Format</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in store.berichtRuns" :key="r.id">
            <td>{{ shortTs(r.created_at) }}</td>
            <td>{{ berichtTitel(r.typ) }}</td>
            <td>{{ r.periode || '—' }}</td>
            <td>{{ r.von }} – {{ r.bis }}</td>
            <td>{{ (r.format || '').toUpperCase() }}</td>
            <td><span class="status-pill" :class="{ bad: r.status === 'failed' }">{{ r.status === 'failed' ? 'Fehler' : 'OK' }}</span></td>
            <td><button v-if="r.status !== 'failed' && r.dateiname" class="link-btn" @click="store.downloadBerichtRun(r.id, r.dateiname)">⬇️</button></td>
          </tr>
          <tr v-if="!store.berichtRuns.length"><td colspan="7" class="empty">Noch keine automatisch erzeugten Berichte. Unten unter „Geplante Berichte" einen Zeitplan anlegen.</td></tr>
        </tbody>
      </table>
      </div>

      <!-- #1405: Automatische Berichterzeugung grafisch konfigurieren -->
      <h3>⏰ Geplante Berichte <span class="hint-inline">(automatische Erzeugung)</span></h3>
      <p class="hint">Lege fest, welche Berichte automatisch erzeugt und in der Historie abgelegt werden. Einfache Presets: quartalsweise (1. des Quartals) oder jährlich (1. Januar).</p>
      <div class="issue-form" style="flex-wrap:wrap;gap:8px">
        <select v-model="schedForm.typ">
          <option value="">Berichtstyp …</option>
          <option v-for="t in store.berichtTypen" :key="t.key" :value="t.key">{{ t.titel }}</option>
        </select>
        <select v-model="schedForm.periode">
          <option value="quartal">Quartalsweise</option>
          <option value="jahr">Jährlich</option>
        </select>
        <select v-model="schedForm.format">
          <option value="docx">Word</option>
          <option value="pdf">PDF</option>
        </select>
        <button class="primary" :disabled="!schedForm.typ || schedBusy" @click="addSchedule">+ Zeitplan anlegen</button>
        <span v-if="schedMsg" class="copied">{{ schedMsg }}</span>
      </div>
      <div class="grid-scroll" v-if="schedules.length">
      <table class="grid mini" style="margin-top:8px">
        <thead><tr><th>Bericht</th><th>Periode</th><th>Format</th><th>Aktiv</th><th></th></tr></thead>
        <tbody>
          <tr v-for="s in schedules" :key="s.id">
            <td>{{ berichtTitel(s.typ) }}</td>
            <td>{{ s.periode === 'jahr' ? 'Jährlich (1. Jan)' : 'Quartalsweise' }}</td>
            <td>{{ (s.format || 'docx').toUpperCase() }}</td>
            <td><label class="chk"><input type="checkbox" :checked="!!s.aktiv" @change="toggleSchedule(s)" /> {{ s.aktiv ? 'an' : 'aus' }}</label></td>
            <td><button class="link-del" title="Zeitplan löschen" @click="deleteSchedule(s.id)">✕</button></td>
          </tr>
        </tbody>
      </table>
      </div>
      <p v-else class="hint">Keine geplanten Berichte. Lege oben einen Zeitplan an.</p>
    </section>

    <!-- ── Assistenten ───────────────────────────────────────────────── -->
    <section v-show="tab === 'assistenten'" class="panel">
      <div class="kachel-grid">
        <div class="kachel" @click="select('alerts')"><div class="k-icon">🚨</div><div class="k-title">Alarm-Analyse</div><div class="k-desc">Einzelne Wazuh-Alarme per KI (lokal/Cloud) oder Prompt bewerten — im Alarme-Tab.</div></div>
        <div class="kachel" @click="select('incidents')"><div class="k-icon">🛡️</div><div class="k-title">Incident-Analyse</div><div class="k-desc">Gesamtbild eines Incidents aus verknüpften Alarmen — im Incidents-Tab.</div></div>
        <div class="kachel" :class="{active: assistant==='lage'}" @click="openLagebericht"><div class="k-icon">🧭</div><div class="k-title">SOC-Lagebericht</div><div class="k-desc">KI-Lagebericht fürs Management aus KPIs + offenen Incidents.</div></div>
        <div class="kachel" :class="{active: assistant==='owasp'}" @click="openOwasp"><div class="k-icon">🧠</div><div class="k-title">OWASP-LLM-Erkennung</div><div class="k-desc">KI-spezifische Alarme erkennen und ins AI-Act-Register übernehmen.</div></div>
        <div class="kachel" :class="{active: assistant==='syslog'}" @click="openSyslog"><div class="k-icon">🔎</div><div class="k-title">Syslog-Quellen-Discovery (read-only)</div><div class="k-desc">Agentlose Syslog-Quellen (Wazuh-Manager) der letzten N h erkennen und als Asset anlegen — kein Sync.</div></div>
      </div>

      <div v-if="assistant==='lage'" class="assistant-panel">
        <h4>🧭 SOC-Lagebericht</h4>
        <details class="ki-transparency"><summary>🔍 Diese Daten werden an die KI übermittelt</summary><textarea readonly rows="6" class="mono">{{ lagePrompt }}</textarea></details>
        <div class="ki-actions">
          <button class="ai" @click="runLageOllama">⚡ Direkt mit KI ausführen</button>
          <button @click="copyLage">📋 Prompt kopieren</button>
          <span v-if="lageCopied" class="copied">✓ in die Zwischenablage kopiert</span>
        </div>
        <div class="ki-paste"><textarea v-model="lagePaste" rows="3" class="mono" placeholder="KI-Antwort einfügen …"></textarea><button class="primary" :disabled="!lagePaste" @click="applyLagePaste">Übernehmen</button></div>
        <div v-if="lageText" class="lage-result"><pre>{{ lageText }}</pre></div>
      </div>

      <div v-if="assistant==='owasp'" class="assistant-panel">
        <h4>🧠 OWASP-LLM-Erkennung</h4>
        <p class="hint">Erkennt KI-spezifische Angriffe (z. B. Prompt Injection) in den Alarmen und kann sie als Evidenz ins AI-Act-OWASP-LLM-Register übernehmen.</p>
        <button @click="detectOwasp">Erkennen</button>
        <div class="grid-scroll" v-if="owaspDet.length">
        <table class="grid mini" style="margin-top:8px">
          <thead><tr><th>OWASP-LLM</th><th>Titel</th><th>Treffer</th></tr></thead>
          <tbody><tr v-for="o in owaspDet" :key="o.llm_id"><td>{{ o.llm_id }}</td><td>{{ o.title }}</td><td>{{ o.count }}</td></tr></tbody>
        </table>
        </div>
        <p v-else-if="owaspChecked" class="hint">Keine KI-spezifischen Alarme erkannt.</p>
        <div class="issue-form" style="margin-top:8px">
          <input v-model="owaspProjekt" placeholder="AI-Act-Projekt" />
          <button class="primary" :disabled="!owaspDet.length" @click="pushOwasp">In AI-Act-Register übernehmen</button>
          <span v-if="owaspMsg" class="copied">{{ owaspMsg }}</span>
        </div>
      </div>

      <div v-if="assistant==='syslog'" class="assistant-panel">
        <h4>🔎 Syslog-Quellen-Discovery (read-only)</h4>
        <p class="hint">Erkennt agentlose Quellen, die per Syslog an den Wazuh-Manager (Agent <code>000</code>) liefern — read-only über den Indexer, <b>kein Sync, keine Änderung an Wazuh</b>. Voraussetzung: PULL-Indexer-Verbindung in der Einrichtung.</p>
        <div class="issue-form">
          <label>Zeitfenster
            <select v-model.number="syslogHours">
              <option :value="1">1 Stunde</option><option :value="2">2 Stunden</option>
              <option :value="6">6 Stunden</option><option :value="24">24 Stunden</option>
            </select>
          </label>
          <button @click="runSyslogDiscovery" :disabled="syslogBusy">{{ syslogBusy ? 'Suche …' : 'Quellen erkennen' }}</button>
          <span v-if="syslogMsg" class="copied">{{ syslogMsg }}</span>
        </div>
        <div v-if="syslogErr" class="banner err" style="margin-top:8px">{{ syslogErr }}</div>
        <div class="grid-scroll" v-if="syslogSources.length">
        <table class="grid mini" style="margin-top:8px">
          <thead><tr>
            <th style="width:28px"><input type="checkbox" :checked="syslogAllChecked" @change="toggleAllSyslog($event)" /></th>
            <th>Hostname</th><th>Absender-IP</th><th>Programm</th><th>Treffer</th><th>Zuletzt</th>
          </tr></thead>
          <tbody>
            <tr v-for="(s, i) in syslogSources" :key="(s.hostname || s.ip) + i">
              <td><input type="checkbox" v-model="syslogSelected" :value="i" /></td>
              <td>{{ s.hostname || '—' }}</td>
              <td>{{ s.ip || '—' }}</td>
              <td>{{ s.program || '—' }}</td>
              <td>{{ s.count }}</td>
              <td>{{ shortTs(s.last_seen) }}</td>
            </tr>
          </tbody>
        </table>
        </div>
        <p v-else-if="syslogChecked && !syslogErr" class="hint">Keine neuen Syslog-Quellen im Zeitfenster (oder alle bereits inventarisiert).</p>
        <div v-if="syslogSources.length" class="issue-form" style="margin-top:8px">
          <button class="primary" :disabled="!syslogSelected.length" @click="createSyslogAssets">{{ syslogSelected.length }} als Assets anlegen</button>
        </div>
      </div>
    </section>

    <!-- ── Einrichtung / Wizard ──────────────────────────────────────── -->
    <section v-show="tab === 'setup'" class="panel">
      <h3>Wazuh anbinden</h3>
      <p class="hint">Generisch für jede Wazuh 4.x. <b>PULL</b> (empfohlen): nur ein read-only-Indexer-User nötig, keine Änderung an Wazuh. <b>PUSH</b>: Wazuh-Integrator leitet weiter.</p>
      <div class="form">
        <label>Modus
          <select v-model="conn.modus"><option value="pull">PULL (Indexer abfragen)</option><option value="push">PUSH (Integrator)</option></select>
        </label>
        <template v-if="conn.modus === 'pull'">
          <label>Indexer-URL<input v-model="conn.url" placeholder="https://wazuh-indexer:9200" /></label>
          <label>Benutzer<input v-model="conn.username" placeholder="soc-reader" /></label>
          <label>Passwort<input v-model="conn.secret" type="password" placeholder="••••••" /></label>
          <label>Index-Muster<input v-model="conn.index_pattern" /></label>
          <label>Mindest-Level<input v-model.number="conn.min_level" type="number" /></label>
          <label class="chk"><input type="checkbox" v-model="conn.verify_tls" /> TLS-Zertifikat prüfen (bei self-signed aus)</label>

          <details class="help-box">
            <summary>❓ Wie lege ich den read-only-Benutzer in Wazuh an?</summary>
            <p>Der SOC-Benutzer braucht nur <b>Leserechte</b> auf den Alarm-Index. Zwei Wege:</p>
            <p><b>A) Über das Wazuh-Dashboard</b> (OpenSearch): <i>Security → Roles → „soc_read" anlegen</i> mit Index-Permission <code>read</code> auf <code>wazuh-alerts-*</code>; dann <i>Internal users → „soc-reader"</i> mit Passwort anlegen und unter <i>Role mappings</i> der Rolle zuordnen.</p>
            <p><b>B) Per API</b> (auf dem Indexer-Host, Admin-Zertifikat):</p>
            <pre>API=https://localhost:9200/_plugins/_security/api
# Rolle
curl -k --cert admin.pem --key admin-key.pem -XPUT $API/roles/soc_read \
 -H 'Content-Type: application/json' -d '{"cluster_permissions":["cluster_composite_ops_ro"],
 "index_permissions":[{"index_patterns":["wazuh-alerts-*"],"allowed_actions":["read"]}]}'
# Benutzer
curl -k --cert admin.pem --key admin-key.pem -XPUT $API/internalusers/soc-reader \
 -H 'Content-Type: application/json' -d '{"password":"&lt;starkes-Passwort&gt;"}'
# Zuordnung
curl -k --cert admin.pem --key admin-key.pem -XPUT $API/rolesmapping/soc_read \
 -H 'Content-Type: application/json' -d '{"users":["soc-reader"]}'</pre>
            <p class="hint">Danach Benutzer + Passwort oben eintragen, „TLS prüfen" bei self-signed-Zertifikat ausschalten.</p>
          </details>

          <div class="form-actions">
            <button @click="doTest">Verbindung testen</button>
            <button class="primary" @click="doSave">Speichern</button>
            <button @click="doSync">Jetzt synchronisieren</button>
          </div>
          <div v-if="testResult" class="banner" :class="testResult.ok ? 'ok' : 'err'">{{ testResult.hinweis || testResult.error }}</div>
        </template>
        <template v-else>
          <label>Push-Token (Shared Secret)<input v-model="conn.push_token" placeholder="langes Zufallsgeheimnis" /></label>
          <label>Mindest-Level<input v-model.number="conn.min_level" type="number" /></label>
          <div class="form-actions"><button class="primary" @click="doSave">Speichern</button><button @click="genSnippet">Wazuh-Anleitung erzeugen</button></div>
          <div v-if="snippet" class="snippet">
            <p>1) In <code>/var/ossec/etc/ossec.conf</code> einfügen:</p><pre>{{ snippet.ossec_conf }}</pre>
            <p>2) Skript <code>{{ snippet.script_path }}</code> anlegen:</p><pre>{{ snippet.script }}</pre>
            <p>3) Rechte + Neustart:</p><pre>{{ (snippet.install || []).join('\n') }}</pre>
          </div>
        </template>
      </div>

      <h3>Asset-Import aus Wazuh-Manager</h3>
      <p class="hint">Holt die Agentenliste über die Wazuh-Manager-API (Port 55000) und legt sie als Assets an.</p>
      <div class="form">
        <label>Manager-URL <span class="fieldhint">(Standard-Port <b>55000</b>)</span><input v-model="mgr.url" placeholder="https://192.168.10.100:55000" /></label>
        <label>API-Benutzer<input v-model="mgr.username" placeholder="soc-reader" /></label>
        <label>API-Passwort<input v-model="mgr.password" type="password" placeholder="••••••" /></label>
        <label class="chk"><input type="checkbox" v-model="mgr.verify_tls" /> TLS-Zertifikat prüfen</label>

        <details class="help-box">
          <summary>❓ Wie lege ich den API-Benutzer in Wazuh an?</summary>
          <p>Der Asset-Import braucht einen <b>read-only-Benutzer der Wazuh-Manager-API</b> (Port 55000) mit der Rolle <code>agents_readonly</code>. Zwei Wege:</p>
          <p><b>A) Über das Wazuh-Dashboard:</b> <i>Server management → Security → Users → Create user</i> (Benutzer + Passwort); dann unter <i>Roles mapping</i> dem User die Rolle <code>agents_readonly</code> zuordnen.</p>
          <p><b>B) Per API</b> (auf dem Manager-Host, als API-Admin <code>wazuh-wui</code>):</p>
          <pre>API=https://localhost:55000
TOKEN=$(curl -sk -u wazuh-wui:&lt;admin-pw&gt; -X POST "$API/security/user/authenticate?raw=true")
# Benutzer anlegen (Policy: Groß/Klein/Zahl/Sonderzeichen)
curl -sk -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -X POST "$API/security/users" -d '{"username":"soc-reader","password":"&lt;passwort&gt;"}'
# Rolle agents_readonly (id 4) zuweisen — &lt;ID&gt; aus der Anlage-Antwort
curl -sk -H "Authorization: Bearer $TOKEN" -X POST "$API/security/users/&lt;ID&gt;/roles?role_ids=4"</pre>
          <p class="hint">Wichtig: Port <b>55000</b>, „TLS prüfen" bei self-signed aus. Das Passwort beim Öffnen des Tabs erneut eingeben (Feld wird aus Sicherheitsgründen geleert).</p>
        </details>

        <div class="form-actions">
          <button class="primary" @click="saveManager">💾 Speichern</button>
          <button @click="doRefreshAssets">Agenten importieren</button>
        </div>
        <div v-if="assetResult" class="banner" :class="assetResult.ok ? 'ok' : 'err'">{{ assetResult.hinweis || assetResult.error }}</div>
      </div>
    </section>

    <!-- ── Alarm-Detail-Modal ────────────────────────────────────────── -->
    <div v-if="selectedAlert" class="modal-overlay" @click.self="closeAlert">
      <div class="modal">
        <div class="modal-head"><h3>Alarm-Details</h3><button class="close" @click="closeAlert">×</button></div>
        <div class="modal-body">
          <AlertDetailCard :alert="selectedAlert" />
          <div class="modal-actions">
            <span class="lbl">Triage:</span>
            <button v-for="s in nextAlert(selectedAlert.status)" :key="s" @click="triageInModal(s)">{{ alertStatusDe(s) }}</button>
            <button class="primary" @click="escalateFromModal">→ Incident anlegen</button>
          </div>
          <div class="modal-actions">
            <span class="lbl">Asset:</span>
            <select :value="selectedAlert.asset_id || ''" @change="reassignAlert($event)">
              <option value="">— keins —</option>
              <option v-for="a in store.assets" :key="a.id" :value="a.id">{{ a.agent_name || ('#'+a.id) }}</option>
            </select>
          </div>
          <h4>🤖 KI-Analyse</h4>
          <KiAnalysePanel :prompt="modalAlertPrompt" :result="selectedAlert.analysis_json"
                          @ollama="analyzeInModal" @paste="parsePasteAlert" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSocStore } from '../../stores/soc'
import apiClient from '../../api/client'
import AlertDetailCard from '../../components/soc/AlertDetailCard.vue'
import KiAnalysePanel from '../../components/soc/KiAnalysePanel.vue'
import GroupedModuleNav from '../../components/shared/GroupedModuleNav.vue'

const store = useSocStore()
// Gruppierte Navigation (Sprint #34, #1370) — gemeinsame Taxonomie
const navGroups = [
  { id: 'ueberblick', label: '📊 Überblick', tabs: [
    { id: 'dashboard', label: '📊 Dashboard' },
    { id: 'reifegrad', label: '📊 Reifegrad' },
  ] },
  { id: 'tagesbetrieb', label: '🛠️ Tagesbetrieb', tabs: [
    { id: 'alerts', label: '🚨 Alarme' },
    { id: 'incidents', label: '🛡️ Incidents' },
    { id: 'vulnerabilities', label: '🛡️ Schwachstellen' },
    { id: 'massnahmen', label: '📋 Maßnahmen' },
    { id: 'betrieb', label: '📞 Betrieb' },
  ] },
  { id: 'detektion', label: '🛰️ Detektion', tabs: [
    { id: 'detektion', label: '🛰️ Detektion' },
    { id: 'threatintel', label: '🌐 Threat-Intel' },
    { id: 'hunting', label: '🔭 Hunting' },
    { id: 'logquellen', label: '📡 Log-Quellen' },
    { id: 'assets', label: '🖥️ Assets' },
  ] },
  { id: 'doku', label: '📄 Dokumentation', tabs: [
    { id: 'uebungen', label: '🎯 Übungen' },
    { id: 'assistenten', label: '🤖 Assistenten' },
  ] },
  { id: 'berichte', label: '📑 Berichte', tabs: [
    { id: 'berichte', label: '📄 Berichte' },
  ] },
  { id: 'verwaltung', label: '⚙️ Verwaltung', tabs: [
    { id: 'setup', label: '⚙️ Einrichtung' },
  ] },
]
const tab = ref('dashboard')
const severities = ['critical', 'high', 'medium', 'low']
const alertStates = computed(() => store.constants.alert_states || [])

// Deutsche Labels
const SEV_DE: Record<string, string> = { critical: 'Kritisch', high: 'Hoch', medium: 'Mittel', low: 'Niedrig' }
const AS_DE: Record<string, string> = { new: 'Neu', in_review: 'In Prüfung', false_positive: 'False Positive', confirmed: 'Bestätigt', suppressed: 'Unterdrückt' }
const IS_DE: Record<string, string> = { new: 'Neu', in_review: 'In Prüfung', false_positive: 'False Positive', confirmed: 'Bestätigt', contained: 'Eingedämmt', eradicated: 'Beseitigt', resolved: 'Behoben', closed: 'Geschlossen', reopened: 'Wieder geöffnet' }
const TS_DE: Record<string, string> = { offen: 'Offen', in_arbeit: 'In Arbeit', gemeldet: 'Gemeldet', abgeschlossen: 'Abgeschlossen' }
const VT_DE: Record<string, string> = { new: 'Neu', acknowledged: 'Gesichtet', risk_accepted: 'Risiko akzeptiert', false_positive: 'False Positive', promoted: 'Aufgenommen' }
function sevDe(s: string) { return SEV_DE[s] || s }
function alertStatusDe(s: string) { return AS_DE[s] || s }
function incStatusDe(s: string) { return IS_DE[s] || s }
function trackStatusDe(s: string) { return TS_DE[s] || s }
function vulnTriageDe(s: string) { return VT_DE[s] || s }

// Schwachstellen-Register (#1343) — manuell setzbare Triage-Stati (ohne 'promoted')
const vulnTriageBulkable = ['new', 'acknowledged', 'risk_accepted', 'false_positive']
const vFilter = ref<any>({ severity: '', triage_status: '' })
const vShowSolved = ref(false)
const vulnBulk = ref<number[]>([])
const vulnBulkTriage = ref('')
const vulnSyncing = ref(false)
const vulnSyncMsg = ref('')

const aFilter = ref<any>({ status: '', severity: '', min_level: null, kind: '' })
const suppForm = ref<any>({ rule_id: '', agent_glob: '', srcip: '', reason: '', expires_at: '' })
const dryResult = ref<number | null>(null)
const noteText = ref('')
const bridgeProjekt = ref<Record<string, string>>({})
// Incidents: Liste/Detail, Filter, Auswahl, Schließen, Bearbeiten
const incShowClosed = ref(false)
const selectedIds = ref<number[]>([])
const closingMode = ref(false)
const closeReason = ref('')
const editMode = ref(false)
const editForm = ref<any>({})

// Alarm-Detail-Modal
const selectedAlert = ref<any | null>(null)
const modalAlertPrompt = ref('')

// Incident-Analyse + Regelwerke
const incAlerts = ref<any[]>([])
const incPromptText = ref('')
const incidentAnalysis = computed(() => store.currentIncident?.meta_json?.analysis || null)
const regimeOptions = [
  { key: 'personenbezogen', label: 'Personenbezug (DSGVO)' },
  { key: 'nis2_scope', label: 'NIS2' },
  { key: 'cra_produkt', label: 'CRA-Produkt' },
  { key: 'ki_hochrisiko', label: 'Hochrisiko-KI (AI-Act)' },
]
const regimeFlags = ref<Record<string, boolean>>({})
const incIssues = ref<any[]>([])
const issueForm = ref<any>({ provider: 'github', repo: '' })
const incLikelihood = ref<any>(null)
const pbSelect = ref('')
const incPlaybooks = ref<any>({ playbooks: [], mandatory_open: 0 })
const slaEdit = ref<Record<string, any>>({
  critical: { ack_minutes: 15, resolve_minutes: 240 }, high: { ack_minutes: 30, resolve_minutes: 480 },
  medium: { ack_minutes: 60, resolve_minutes: 1440 }, low: { ack_minutes: 240, resolve_minutes: 4320 },
})

// PIR + Maßnahmen (#1316)
const pirForm = ref<any>({ root_cause: '', what_went_well: '', what_went_wrong: '', lessons: '' })
const actionForm = ref<any>({ beschreibung: '', owner: '', frist: '' })
const massOnlyOpen = ref(true)
const pirStates = ['offen', 'in_arbeit', 'erledigt']

const conn = ref<any>({ modus: 'pull', url: '', username: '', secret: '', index_pattern: 'wazuh-alerts-*', min_level: 7, verify_tls: false, push_token: '', name: 'default' })
const mgr = ref<any>({ url: '', username: '', password: '', verify_tls: false })
const testResult = ref<any>(null)
const assetResult = ref<any>(null)
const snippet = ref<any>(null)

function pct(v: any) { return v == null ? '–' : Math.round(v * 100) + '%' }
const slaClass = computed(() => {
  const c = store.slaKpis?.sla_compliance
  return c == null ? '' : c >= 0.9 ? 'ok' : c >= 0.7 ? 'mid' : 'bad'
})
async function saveSla(s: string) { await store.saveSla({ severity: s, ...slaEdit.value[s] }) }
// PIR + Maßnahmen (#1316)
function isOverdue(a: any) {
  if (!a.frist || a.status === 'erledigt') return false
  return a.frist < new Date().toISOString().slice(0, 10)
}
async function savePirForm() { await store.savePir(store.currentIncident.id, { ...pirForm.value }) }
async function addAction() {
  await store.createPirAction(store.currentIncident.id, { ...actionForm.value })
  actionForm.value = { beschreibung: '', owner: '', frist: '' }
}
async function changeActionStatus(id: number, e: any) {
  await store.updatePirAction(id, { status: e.target.value }); await store.getIncident(store.currentIncident.id)
}
async function doDeleteAction(id: number) {
  await store.deletePirAction(id); await store.getIncident(store.currentIncident.id)
}
async function loadMass() { await store.fetchPirActions(massOnlyOpen.value) }
async function changeActionStatusGlobal(id: number, e: any) {
  await store.updatePirAction(id, { status: e.target.value }); await loadMass()
}
async function openIncidentFromAction(iid: number) { tab.value = 'incidents'; await openIncident(iid) }
// Bulk-Alarm-Zuordnung (#1328)
const alertsToLink = ref<string[]>([])
const linkableAlerts = computed(() => {
  const linked = new Set(incAlerts.value.map((a: any) => a.alert_uid))
  return (store.alerts || []).filter((a: any) => !linked.has(a.alert_uid)).slice(0, 50)
})
async function onAddAlertsToggle(e: any) {
  if (e.target.open && !store.alerts.length) await store.fetchAlerts({})
}
async function doLinkAlerts() {
  if (!alertsToLink.value.length) return
  await store.linkIncidentAlerts(store.currentIncident.id, alertsToLink.value)
  alertsToLink.value = []
  incAlerts.value = await store.incidentAlerts(store.currentIncident.id)
  await store.getIncident(store.currentIncident.id)
}
async function doUnlinkAlert(uid: string) {
  await store.unlinkIncidentAlert(store.currentIncident.id, uid)
  incAlerts.value = await store.incidentAlerts(store.currentIncident.id)
}
// Beweissicherung / Asservaten (#1317)
const evidence = ref<any[]>([])
const eviFile = ref<File | null>(null)
const eviFileInput = ref<any>(null)
const eviForm = ref<any>({ beschreibung: '', retention_days: 365 })
const custodyView = ref<any>(null)
function fmtBytes(n: number) {
  if (!n) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB']; let i = 0; let v = n
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(i ? 1 : 0)} ${u[i]}`
}
function onEviFile(e: any) { eviFile.value = e.target.files?.[0] || null }
async function loadEvidence(id: number) { evidence.value = (await store.fetchEvidence(id)) || [] }
async function doUploadEvidence() {
  if (!eviFile.value) return
  const r = await store.uploadEvidence(store.currentIncident.id, eviFile.value, eviForm.value.retention_days, eviForm.value.beschreibung)
  if (r?.ok) {
    eviFile.value = null; eviForm.value = { beschreibung: '', retention_days: 365 }
    if (eviFileInput.value) eviFileInput.value.value = ''
    await loadEvidence(store.currentIncident.id)
  }
}
async function doFreezeSnapshot() {
  const r = await store.freezeSnapshot(store.currentIncident.id)
  if (r?.ok) await loadEvidence(store.currentIncident.id)
}
async function showCustody(eid: number) { custodyView.value = await store.fetchCustody(eid) }
async function doDeleteEvidence(eid: number) {
  const reason = window.prompt('Begründung für die Löschung (mind. 10 Zeichen, Chain of Custody bleibt erhalten):')
  if (!reason) return
  const r = await store.deleteEvidence(eid, reason)
  if (r?.ok) { await loadEvidence(store.currentIncident.id); if (custodyView.value?.evidence?.id === eid) custodyView.value = null }
}
// SOC-Reifegrad (#1326)
const scoreModel = ref<Record<string, number>>({})
const assessForm = ref<any>({ durchgefuehrt_von: '', datum: new Date().toISOString().slice(0, 10) })
function loadAssessment() {
  store.fetchAssessment().then(() => {
    const a = store.assessment; if (!a) return
    const m: Record<string, number> = {}
    for (const d of a.catalog) for (const asp of d.aspekte) {
      m[asp.key] = a.latest[asp.key]?.reifegrad ?? a.suggestions[asp.key] ?? 0
    }
    scoreModel.value = m
  })
}
const assessSummary = computed(() => {
  const a = store.assessment
  if (!a) return { gesamt: 0, domains: [] }
  const domains = a.catalog.map((d: any) => {
    const vals = d.aspekte.map((x: any) => scoreModel.value[x.key] || 0)
    const avg = vals.length ? vals.reduce((s: number, v: number) => s + v, 0) / vals.length : 0
    return { key: d.key, name: d.name, reifegrad: avg }
  })
  const all = a.catalog.flatMap((d: any) => d.aspekte.map((x: any) => scoreModel.value[x.key] || 0))
  const gesamt = all.length ? all.reduce((s: number, v: number) => s + v, 0) / all.length : 0
  return { gesamt, domains }
})
function reifeClass(v: number) { return v >= 4 ? 'ok' : v >= 2.5 ? 'mid' : 'bad' }
async function doSaveAssessment() {
  await store.saveAssessment({ ...assessForm.value, scores: scoreModel.value })
}
// Management-Report (#1325)
const reportPeriod = ref('monat')
// Berichts-Center (#1350)
const berichtPreset = ref('90')
const berichtVon = ref('')
const berichtBis = ref('')
const berichtBusy = ref('')
function _isoDay(d: Date) { return d.toISOString().slice(0, 10) }
function applyPreset() {
  const today = new Date()
  if (berichtPreset.value === 'custom') return
  if (berichtPreset.value === '30' || berichtPreset.value === '90') {
    const days = parseInt(berichtPreset.value, 10)
    const from = new Date(today); from.setDate(from.getDate() - days)
    berichtVon.value = _isoDay(from); berichtBis.value = _isoDay(today)
  } else if (berichtPreset.value === 'quartal') {
    const q = Math.floor(today.getMonth() / 3)
    berichtVon.value = _isoDay(new Date(today.getFullYear(), q * 3, 1))
    berichtBis.value = _isoDay(today)
  } else if (berichtPreset.value === 'jahr') {
    berichtVon.value = _isoDay(new Date(today.getFullYear(), 0, 1))
    berichtBis.value = _isoDay(today)
  }
}
applyPreset()
function berichtTitel(key: string) { return store.berichtTypen.find((t: any) => t.key === key)?.titel || key }

// #1405: geplante (automatische) Berichte
const schedules = ref<any[]>([])
const schedForm = ref<{ typ: string; periode: string; format: string }>({ typ: '', periode: 'quartal', format: 'docx' })
const schedBusy = ref(false)
const schedMsg = ref('')
async function fetchSchedules() {
  try { schedules.value = (await apiClient.get('/soc/berichte/schedule')).data?.schedules || [] }
  catch { schedules.value = [] }
}
async function addSchedule() {
  if (!schedForm.value.typ) return
  schedBusy.value = true; schedMsg.value = ''
  try {
    await apiClient.post('/soc/berichte/schedule', { ...schedForm.value })
    schedForm.value = { typ: '', periode: 'quartal', format: 'docx' }
    schedMsg.value = '✓ Zeitplan angelegt'
    await fetchSchedules()
    setTimeout(() => { schedMsg.value = '' }, 3000)
  } catch (e: any) { store.error = e?.response?.data?.error || 'Zeitplan konnte nicht angelegt werden' }
  finally { schedBusy.value = false }
}
async function toggleSchedule(s: any) {
  try { await apiClient.patch(`/soc/berichte/schedule/${s.id}`, { aktiv: !s.aktiv }); await fetchSchedules() }
  catch (e: any) { store.error = e?.response?.data?.error || 'Fehler' }
}
async function deleteSchedule(id: number) {
  try { await apiClient.delete(`/soc/berichte/schedule/${id}`); await fetchSchedules() }
  catch (e: any) { store.error = e?.response?.data?.error || 'Fehler' }
}
async function dlBericht(typ: string, fmt: string) {
  berichtBusy.value = `${typ}:${fmt}`
  try { await store.downloadBericht(typ, berichtVon.value || null, berichtBis.value || null, fmt) }
  finally { berichtBusy.value = '' }
}
// Log-Quellen (#1324)
const lsForm = ref<any>({ name: '', typ: '', erwartet: true })
async function doSaveLogSource() {
  if (!lsForm.value.name.trim()) return
  await store.saveLogSource({ ...lsForm.value })
  lsForm.value = { name: '', typ: '', erwartet: true }
}
// Threat-Hunting (#1323)
const huntForm = ref<any>({ hypothese: '', attack_bezug: '', jaeger: '', datum: new Date().toISOString().slice(0, 10) })
const huntQuery = ref('')
const huntResult = ref<any>(null)
async function doRunQuery() { huntResult.value = await store.runHuntQuery(huntQuery.value) }
async function doSaveHunt() {
  if (!huntForm.value.hypothese.trim()) return
  await store.saveHunt({ ...huntForm.value, query: huntQuery.value })
  huntForm.value = { hypothese: '', attack_bezug: '', jaeger: '', datum: new Date().toISOString().slice(0, 10) }
}
async function doUpdateHunt(h: any) {
  await store.saveHunt({ id: h.id, query: h.query, findings: h.findings, status: h.status, ergebnis: h.ergebnis })
}
async function doEscalateHunt(h: any) {
  const r = await store.escalateHunt(h.id, { severity: 'medium' })
  if (r?.ok) { tab.value = 'incidents'; await loadIncidents(); await openIncident(r.incident_id) }
}
// Threat-Intelligence / IOC (#1322)
const iocForm = ref<any>({ typ: 'ip', wert: '', quelle: '', confidence: 50, gueltig_bis: '' })
const iocImport = ref<any>({ text: '', quelle: 'import', result: '' })
async function doSaveIoc() {
  if (!iocForm.value.wert.trim()) return
  await store.saveIoc({ ...iocForm.value })
  iocForm.value = { typ: 'ip', wert: '', quelle: '', confidence: 50, gueltig_bis: '' }
}
async function doImportIocs() {
  const r = await store.importIocs(iocImport.value.text, iocImport.value.quelle)
  if (r?.ok) iocImport.value = { text: '', quelle: 'import', result: `${r.imported} importiert, ${r.alerts_matched} Alarme getroffen` }
}
async function doRescanIocs() {
  const r = await store.rescanIocs()
  if (r?.ok) store.error = null
}
// Detektion: Use-Cases (#1321)
const ucForm = ref<any>({ name: '', bedrohung: '', attack: '', wazuh_rules: '', status: 'geplant' })
function parseAttack(s: string): string[] { return (s || '').split(/[,\s]+/).map(x => x.trim()).filter(Boolean) }
async function doSaveUsecase() {
  if (!ucForm.value.name.trim()) return
  await store.saveUsecase({ name: ucForm.value.name, bedrohung: ucForm.value.bedrohung,
    attack_techniques: parseAttack(ucForm.value.attack), wazuh_rules: ucForm.value.wazuh_rules,
    status: ucForm.value.status })
  ucForm.value = { name: '', bedrohung: '', attack: '', wazuh_rules: '', status: 'geplant' }
}
async function changeUcStatus(u: any, e: any) {
  await store.saveUsecase({ id: u.id, name: u.name, bedrohung: u.bedrohung,
    attack_techniques: u.attack_techniques, wazuh_rules: u.wazuh_rules, status: e.target.value })
}
// #1349 — Coverage-Quelle umschalten, Regelwerk-Abdeckung je Technik, Kandidaten bestätigen
async function changeCoverageSource(e: any) { await store.fetchCoverage(e.target.value) }
function heatTitle(t: any): string {
  const parts = [`${t.id} ${t.name} — ${t.status}`]
  if (t.by_alerts) parts.push('reale Alarme')
  if (t.by_rules && t.by_rules.length) parts.push(`durch Regel(n) abgedeckt: ${t.by_rules.join(', ')}`)
  return parts.join(' · ')
}
async function doConfirmCandidate(c: any) {
  await store.confirmUsecase({ technique: c.technique, rule_ids: c.rule_ids, existing_usecase_id: c.existing_usecase_id })
}
// #1400: alle Regelwerk-Kandidaten auf einmal bestätigen
const confirmAllBusy = ref(false)
async function doConfirmAllCandidates() {
  const cands = [...(store.coverage?.rule_candidates || [])]
  if (!cands.length) return
  confirmAllBusy.value = true
  try { await store.confirmUsecasesBulk(cands) } finally { confirmAllBusy.value = false }
}
// Regelwerk-Explorer (#1348) — read-only Wazuh-Regelwerk durchsuchen
const ruleFilter = ref<any>({ q: '', group: '', mitre: '', min_level: '', status: '' })
const ruleDetail = ref<any>(null)
const ruleSyncMsg = ref('')
async function doFetchRules() { await store.fetchRules({ ...ruleFilter.value }) }
function resetRuleFilter() {
  ruleFilter.value = { q: '', group: '', mitre: '', min_level: '', status: '' }
  doFetchRules()
}
async function doSyncRules() {
  ruleSyncMsg.value = ''
  const r = await store.syncRules()
  if (r) ruleSyncMsg.value = `${r.count} Regeln geladen.`
}
// SOC-Übungen (#1319)
const uebForm = ref<any>({ typ: 'tabletop', titel: '', datum: new Date().toISOString().slice(0, 10), teilnehmer: '' })
async function doSaveUebung() {
  if (!uebForm.value.titel.trim()) return
  await store.saveUebung({ ...uebForm.value })
  uebForm.value = { typ: 'tabletop', titel: '', datum: new Date().toISOString().slice(0, 10), teilnehmer: '' }
}
async function doUpdateUebung(u: any) {
  await store.saveUebung({ id: u.id, szenario: u.szenario, status: u.status, ergebnis: u.ergebnis,
    lifecycle: u.lifecycle, uebungsleitung: u.uebungsleitung, moderator: u.moderator, evaluator: u.evaluator,
    erwartete_erkennung: u.erwartete_erkennung, tatsaechliche_erkennung: u.tatsaechliche_erkennung,
    auswertung: u.auswertung, massnahmen: u.massnahmen })
}
// ISO-22398-Detailbereich (#1351)
const openUebId = ref<number | null>(null)
const _lcLabels: Record<string, string> = { design: 'Design', develop: 'Develop', conduct: 'Conduct', evaluate: 'Evaluate', improve: 'Improve' }
function lcLabel(ph: string) { return _lcLabels[ph] || ph }
function lcIndex(ph: string) { return Math.max(0, (store.uebungMeta.lifecycle || []).indexOf(ph || 'design')) }
const zielForm = ref<any>({ ziel: '', typ: 'testing', kriterien: '', soll: '', ist: '', bewertung: 'offen' })
const injForm = ref<any>({ zeit: '', beschreibung: '', erwartete_reaktion: '', tatsaechliche_reaktion: '', status: 'geplant' })
const massForm = ref<any>({ beschreibung: '', owner: '', frist: '', status: 'offen' })
async function toggleUebDetail(id: number) {
  if (openUebId.value === id) { openUebId.value = null; return }
  openUebId.value = id
  await store.fetchUebung(id)
}
async function addZiel(uebungId: number) {
  if (!zielForm.value.ziel.trim()) return
  await store.saveUebungZiel(uebungId, { ...zielForm.value })
  zielForm.value = { ziel: '', typ: 'testing', kriterien: '', soll: '', ist: '', bewertung: 'offen' }
}
async function addInject(uebungId: number) {
  if (!injForm.value.beschreibung.trim()) return
  await store.saveUebungInject(uebungId, { ...injForm.value })
  injForm.value = { zeit: '', beschreibung: '', erwartete_reaktion: '', tatsaechliche_reaktion: '', status: 'geplant' }
}
async function addMass(uebungId: number) {
  if (!massForm.value.beschreibung.trim()) return
  await store.saveUebungMassnahme(uebungId, { ...massForm.value })
  massForm.value = { beschreibung: '', owner: '', frist: '', status: 'offen' }
}
async function doSaveAar(u: any) {
  await store.saveUebung({ id: u.id, aar_staerken: u.aar_staerken, aar_verbesserung: u.aar_verbesserung,
    aar_lessons: u.aar_lessons, aar_empfehlungen: u.aar_empfehlungen, explan: u.explan,
    aar_signoff_by: u.aar_signoff_by })
  await store.fetchUebung(u.id)
}
// Betrieb: Handover / Eskalation / RACI (#1318)
const hoForm = ref<any>({ schicht: 'Früh', datum: new Date().toISOString().slice(0, 10), an_user: '', offene_punkte: '' })
const escForm = ref<any>({ severity: 'high', stufe: 1, rolle: '', person: '', kontakt: '', frist_minuten: 30 })
const raciForm = ref<any>({ vorfallstyp: '', rolle: '', raci: 'R' })
async function doSaveHandover() {
  if (!hoForm.value.datum) return
  await store.saveHandover({ ...hoForm.value })
  hoForm.value.offene_punkte = ''; hoForm.value.an_user = ''
}
async function doSaveEscalation() {
  if (!escForm.value.rolle) return
  await store.saveEscalation({ ...escForm.value })
  escForm.value.rolle = ''; escForm.value.person = ''; escForm.value.kontakt = ''
}
async function doSaveRaci() {
  if (!raciForm.value.vorfallstyp || !raciForm.value.rolle) return
  await store.saveRaci({ ...raciForm.value })
  raciForm.value.rolle = ''
}
async function doEscalate(stufe: number) {
  const r = await store.escalateIncident(store.currentIncident.id, stufe)
  if (r?.ok) store.error = null
}
const bulkAlerts = ref<string[]>([])
const bulkTargetIncident = ref('')
const openIncidents = computed(() => (store.incidents || []).filter((i: any) => i.status !== 'closed'))
async function doBulkAssign() {
  if (!bulkTargetIncident.value || !bulkAlerts.value.length) return
  const r = await store.linkIncidentAlerts(Number(bulkTargetIncident.value), bulkAlerts.value)
  if (r?.ok) { bulkAlerts.value = []; bulkTargetIncident.value = ''; await loadAlerts() }
}
function shortTs(ts: string) { return (ts || '').replace('T', ' ').slice(0, 16) }
function nextAlert(s: string) { return ['in_review', 'false_positive', 'confirmed', 'suppressed'].filter(x => x !== s) }
function nextIncident(s: string) { return (store.constants.incident_transitions || {})[s] || [] }

async function select(id: string) {
  tab.value = id
  if (id === 'dashboard') {
    await store.fetchKpis(); await store.fetchControlEvidence(); await store.fetchSlaKpis()
    await store.fetchMgmtReport(reportPeriod.value)
    const cfg = store.slaKpis?.sla_config || {}
    for (const s of severities) if (cfg[s]) slaEdit.value[s] = { ...cfg[s] }
    // KPI „offene krit./hohe Schwachstellen" für die Dashboard-Kachel (#1343)
    await store.fetchVulnerabilities({ limit: 1 })
  }
  if (id === 'alerts') { await loadAlerts(); await store.fetchAssets(); await store.fetchIncidents() }
  if (id === 'incidents') { await loadIncidents(); await store.fetchAssets() }
  if (id === 'assets') { store.currentAsset = null; await store.fetchAssets() }
  if (id === 'vulnerabilities') await loadVulns()
  if (id === 'massnahmen') await loadMass()
  if (id === 'betrieb') { await store.fetchHandovers(); await store.fetchEscalation(); await store.fetchRaci() }
  if (id === 'uebungen') await store.fetchUebungen()
  if (id === 'detektion') { await store.fetchUsecases(); await store.fetchCoverage(); await store.fetchRules() }
  if (id === 'threatintel') await store.fetchIocs()
  if (id === 'hunting') await store.fetchHunts()
  if (id === 'logquellen') await store.fetchLogSources()
  if (id === 'reifegrad') loadAssessment()
  if (id === 'berichte') { await store.fetchBerichte(); await fetchSchedules() }
  if (id === 'setup') await loadSetup()
}
async function loadIncidents() {
  store.currentIncident = null
  await store.fetchIncidents(incShowClosed.value ? { include_closed: 'true' } : {})
}
async function loadSetup() {
  await store.fetchConnections()
  const c: any = (store.connections || [])[0]
  if (c) {
    conn.value = { ...conn.value, modus: c.modus, url: c.url, username: c.username, index_pattern: c.index_pattern, min_level: c.min_level, verify_tls: c.verify_tls, name: c.name, secret: '' }
    mgr.value = { url: c.manager_url || '', username: c.manager_user || '', password: '', verify_tls: mgr.value.verify_tls }
  }
}
async function loadAlerts() {
  const p: any = {}
  if (aFilter.value.status) p.status = aFilter.value.status
  if (aFilter.value.severity) p.severity = aFilter.value.severity
  if (aFilter.value.min_level) p.min_level = aFilter.value.min_level
  if (aFilter.value.kind) p.kind = aFilter.value.kind
  await store.fetchAlerts(p)
}

// Schwachstellen-Register (#1343)
async function loadVulns() {
  const p: any = {}
  if (vFilter.value.severity) p.severity = vFilter.value.severity
  if (vFilter.value.triage_status) p.triage_status = vFilter.value.triage_status
  p.only_active = vShowSolved.value ? 0 : 1
  await store.fetchVulnerabilities(p)
}
let vulnPoll: any = null
async function doVulnSync() {
  vulnSyncMsg.value = ''
  const r = await store.syncVulnerabilities()
  if (!r?.ok) {
    if (r?.error) store.error = r.error
    if (r?.running) vulnSyncing.value = true
    return
  }
  vulnSyncing.value = true
  if (vulnPoll) clearInterval(vulnPoll)
  vulnPoll = setInterval(async () => {
    const st = await store.vulnSyncStatus()
    if (st && !st.running) {
      clearInterval(vulnPoll); vulnPoll = null; vulnSyncing.value = false
      const res = st.last_result
      if (res?.ok) vulnSyncMsg.value = `✓ Sync abgeschlossen: ${res.active} aktiv (neu ${res.inserted}, behoben ${res.solved})`
      else if (res?.error) store.error = res.error
      await loadVulns()
    }
  }, 2000)
}
async function onVulnTriage(v: any, e: any) {
  const status = e.target.value
  const r = await store.triageVulnerability(v.id, status)
  if (r?.ok) v.triage_status = status
  await loadVulns()
}
async function doBulkVulnTriage() {
  if (!vulnBulkTriage.value) return
  await store.bulkTriageVulnerabilities(vulnBulk.value, vulnBulkTriage.value)
  vulnBulk.value = []; vulnBulkTriage.value = ''
  await loadVulns()
}
async function doPromote(v: any, target: 'alert' | 'incident') {
  const r = await store.promoteVulnerability(v.id, target)
  if (!r?.ok) { if (r?.error) store.error = r.error; return }
  if (target === 'incident' && r.incident_id) {
    tab.value = 'incidents'; await loadIncidents(); await openIncident(r.incident_id)
  } else {
    vulnSyncMsg.value = '✓ Als Alarm aufgenommen — im Alarme-Tab im Triage-Workflow sichtbar.'
    await loadVulns()
  }
}

// Suppression / Tuning
async function onSuppToggle(e: any) { if (e.target.open) await store.fetchSuppressions() }
async function addSupp() {
  if (!suppForm.value.rule_id && !suppForm.value.agent_glob && !suppForm.value.srcip) { store.error = 'Mindestens ein Kriterium angeben.'; return }
  await store.addSuppression({ ...suppForm.value, expires_at: suppForm.value.expires_at || null })
  suppForm.value = { rule_id: '', agent_glob: '', srcip: '', reason: '', expires_at: '' }; dryResult.value = null
}
async function dryRun() { const r = await store.dryRunSuppression(suppForm.value); dryResult.value = r?.matched ?? 0 }

// Assistenten
const assistant = ref('')
const lagePrompt = ref(''); const lagePaste = ref(''); const lageText = ref(''); const lageCopied = ref(false)
const owaspDet = ref<any[]>([]); const owaspChecked = ref(false); const owaspProjekt = ref(''); const owaspMsg = ref('')
async function openLagebericht() { assistant.value = 'lage'; lageText.value = ''; lagePrompt.value = await store.lageberichtPrompt() }
async function copyLage() { try { await navigator.clipboard.writeText(lagePrompt.value); lageCopied.value = true; setTimeout(() => (lageCopied.value = false), 2500) } catch { /* */ } }
async function runLageOllama() { lageText.value = 'Analyse läuft …'; lageText.value = await store.runLagebericht() }
async function applyLagePaste() { lageText.value = await store.runLagebericht(lagePaste.value) }
function openOwasp() { assistant.value = 'owasp'; owaspChecked.value = false; owaspDet.value = []; owaspMsg.value = '' }
async function detectOwasp() { owaspDet.value = await store.fetchOwaspLlm(); owaspChecked.value = true }
async function pushOwasp() {
  if (!owaspProjekt.value) { store.error = 'AI-Act-Projekt angeben.'; return }
  const r = await store.pushOwaspLlm(owaspProjekt.value)
  owaspMsg.value = r?.ok ? `✓ ${r.pushed} Kategorie(n) übernommen` : (r?.error || 'Fehler')
}

// Syslog-Quellen-Discovery (#1347)
const syslogHours = ref(24)
const showAssetDiscovery = ref(false)  // #1401: agentlose Erkennung im Assets-Tab
const syslogSources = ref<any[]>([])
const syslogSelected = ref<number[]>([])
const syslogBusy = ref(false); const syslogChecked = ref(false)
const syslogMsg = ref(''); const syslogErr = ref('')
const syslogAllChecked = computed(() => syslogSources.value.length > 0 && syslogSelected.value.length === syslogSources.value.length)
function openSyslog() { assistant.value = 'syslog'; syslogSources.value = []; syslogSelected.value = []; syslogChecked.value = false; syslogMsg.value = ''; syslogErr.value = '' }
function toggleAllSyslog(e: any) { syslogSelected.value = e.target.checked ? syslogSources.value.map((_, i) => i) : [] }
async function runSyslogDiscovery() {
  syslogBusy.value = true; syslogMsg.value = ''; syslogErr.value = ''; syslogSelected.value = []
  try {
    const r = await store.discoverSyslog(syslogHours.value)
    syslogSources.value = r?.sources || []
    syslogChecked.value = true
    if (!r?.ok) syslogErr.value = r?.error || 'Discovery fehlgeschlagen'
  } finally { syslogBusy.value = false }
}
async function createSyslogAssets() {
  const sel = syslogSelected.value.map((i) => syslogSources.value[i]).filter(Boolean)
  if (!sel.length) return
  const r = await store.createAssetsFromSyslog(sel)
  if (r?.ok) {
    syslogMsg.value = `✓ ${r.created} angelegt${r.skipped ? `, ${r.skipped} übersprungen` : ''}`
    await runSyslogDiscovery()  // Liste neu laden → angelegte verschwinden (Dedup)
  }
}

// Alarm-Detail-Modal
async function openAlertDetail(uid: string) { selectedAlert.value = await store.getAlert(uid); modalAlertPrompt.value = await store.alertPrompt(uid) }
function closeAlert() { selectedAlert.value = null }
async function refreshSelected() { if (selectedAlert.value) selectedAlert.value = await store.getAlert(selectedAlert.value.alert_uid) }
async function triageInModal(status: string) { await store.triageAlert(selectedAlert.value.alert_uid, status); await refreshSelected(); await loadAlerts() }
async function analyzeInModal() { await store.analyzeAlert(selectedAlert.value.alert_uid); await refreshSelected() }
async function parsePasteAlert(resp: string) { await store.analyzeAlert(selectedAlert.value.alert_uid, resp); await refreshSelected() }
async function reassignAlert(e: any) { const v = e.target.value; await store.assignAlert(selectedAlert.value.alert_uid, v ? Number(v) : null); await refreshSelected() }
async function escalateFromModal() {
  const al = selectedAlert.value
  const r = await store.createIncident({ titel: al.description || 'Incident', severity: al.severity, agent_name: al.agent_name, alert_uids: [al.alert_uid], mitre: al.mitre })
  closeAlert(); tab.value = 'incidents'; await store.fetchIncidents(); if (r?.id) await store.getIncident(r.id)
}

// Incident — Liste/Detail
async function openIncident(id: number) { closingMode.value = false; editMode.value = false; await store.getIncident(id) }
function backToList() { store.currentIncident = null; loadIncidents() }
async function setStatus(s: string) { await store.setIncidentStatus(store.currentIncident.id, s) }
async function doClose() {
  const r = await store.closeIncident(store.currentIncident.id, closeReason.value)
  if (r?.ok) {
    closingMode.value = false; closeReason.value = ''
    // Nur beim Schließen: sofort (ohne Re-Fetch, #1454) zurück zur Übersicht.
    backToList()
  }
}
function startEdit() {
  const i = store.currentIncident
  editForm.value = { titel: i.titel, severity: i.severity, klassifikation: i.klassifikation, owner: i.owner, beschreibung: i.beschreibung, response_actions: i.response_actions, lessons_learned: i.lessons_learned }
  editMode.value = true
}
async function saveEdit() { await store.updateIncident(store.currentIncident.id, editForm.value); editMode.value = false }
async function report(format: string, singleId?: number) {
  const ids = singleId ? [singleId] : selectedIds.value
  if (!ids.length) { store.error = 'Bitte Incidents auswählen.'; return }
  await store.downloadReport(ids, format)
}
async function saveManager() {
  mgr.value.url = normMgrUrl(mgr.value.url)
  await store.saveConnection({ name: conn.value.name || 'default', modus: conn.value.modus, manager_url: mgr.value.url, manager_user: mgr.value.username, manager_secret: mgr.value.password })
  assetResult.value = { ok: true, hinweis: 'Manager-Zugang gespeichert.' }
}
async function togglePersonal(e: any) { await store.updateIncident(store.currentIncident.id, { personal_data_involved: e.target.checked ? 1 : 0 }) }
async function evaluate() { await store.evaluateIncident(store.currentIncident.id) }
async function addNote() { if (noteText.value) { await store.addNote(store.currentIncident.id, noteText.value); noteText.value = '' } }
// Assets (Master-Detail)
const assetForm = ref<any>({})
const assetMsg = ref('')
const KRIT = ['', 'niedrig', 'gering', 'mittel', 'hoch', 'kritisch']
function kritLabel(k: number) { return KRIT[k] || '' }
function statusDe(a: any) {
  if (a.source === 'manuell') return 'Manuell'
  const m: Record<string, string> = { active: 'Aktiv', disconnected: 'Getrennt', never_connected: 'Nie verbunden', pending: 'Ausstehend' }
  return m[a.agent_status] || a.agent_status || 'Agent'
}
function tagSummary(a: any) {
  return regimeOptions.filter(r => a[r.key]).map(r => r.label.replace(/ \(.*\)/, '')).join(', ')
}
function _assetToForm(a: any) {
  assetForm.value = { id: a.id, agent_name: a.agent_name, kritikalitaet: a.kritikalitaet ?? 3, umgebung: a.umgebung || '', lifecycle: a.lifecycle || 'aktiv', owner: a.owner || '', datenklasse: a.datenklasse || '', organisation: a.organisation || '', personenbezogen: !!a.personenbezogen, nis2_scope: !!a.nis2_scope, cra_produkt: !!a.cra_produkt, ki_hochrisiko: !!a.ki_hochrisiko }
}
async function openAsset(id: number) { const a = await store.fetchAssetDetail(id); if (a) _assetToForm(a) }
function newAsset() {
  store.currentAsset = { source: 'manuell', kritikalitaet: 3, lifecycle: 'aktiv', incidents: [], alerts: [], risk: { score: 0, ampel: 'gruen' } }
  _assetToForm(store.currentAsset)
}
async function saveAssetForm() {
  const r = await store.saveAsset({ ...assetForm.value, source: store.currentAsset.source || 'agent' })
  if (r?.id) await openAsset(r.id); else if (assetForm.value.id) await openAsset(assetForm.value.id)
  await store.fetchAssets()
  // #1466: Rückmeldung nach dem Speichern (vorher kommentarlos gespeichert).
  assetMsg.value = '✓ Gespeichert.'
  setTimeout(() => { assetMsg.value = '' }, 3000)
}
async function removeAsset() { const id = store.currentAsset?.id; if (id) { await store.deleteAsset(id); store.currentAsset = null } }
function gotoIncident(id: number) { store.currentAsset = null; tab.value = 'incidents'; store.getIncident(id) }
async function reassignIncident(e: any) { const v = e.target.value; await store.assignIncident(store.currentIncident.id, v ? Number(v) : null) }
async function loadIncPlaybooks(id: number) { incPlaybooks.value = (await store.fetchIncidentPlaybooks(id)) || { playbooks: [], mandatory_open: 0 } }
async function doAssignPlaybook() {
  if (!pbSelect.value) return
  await store.assignPlaybook(store.currentIncident.id, Number(pbSelect.value))
  pbSelect.value = ''; await loadIncPlaybooks(store.currentIncident.id); await store.getIncident(store.currentIncident.id)
}
async function doToggleStep(instanceId: number, stepId: number, e: any) {
  await store.togglePlaybookStep(store.currentIncident.id, instanceId, stepId, e.target.checked)
  await loadIncPlaybooks(store.currentIncident.id)
}
function pbPct(pb: any) { return pb.progress?.total ? Math.round(pb.progress.done / pb.progress.total * 100) : 0 }
async function analyzeIncidentOllama() { await store.analyzeIncident(store.currentIncident.id) }
async function parseIncidentPasteResp(resp: string) { await store.analyzeIncident(store.currentIncident.id, resp) }
async function createIssue() {
  if (!issueForm.value.repo) { store.error = 'Repository (owner/repo) angeben.'; return }
  const r = await store.createIncidentIssue(store.currentIncident.id, { provider: issueForm.value.provider, repo: issueForm.value.repo })
  if (r?.created) { issueForm.value.repo = ''; incIssues.value = await store.fetchIncidentIssues(store.currentIncident.id); await store.getIncident(store.currentIncident.id) }
}
async function delIssue(linkId: string) { await store.deleteIncidentIssue(store.currentIncident.id, linkId); incIssues.value = await store.fetchIncidentIssues(store.currentIncident.id) }
async function saveRegimes() {
  const id = store.currentIncident.id
  await store.setRegimes(id, regimeFlags.value)
  if (regimeFlags.value.personenbezogen !== !!store.currentIncident.personal_data_involved) {
    await store.updateIncident(id, { personal_data_involved: regimeFlags.value.personenbezogen ? 1 : 0 })
  }
}

// Brücken
const bridgeLabels: Record<string, string> = { dsgvo: '→ DSGVO-Datenpanne anlegen', cra: '→ CRA-Schwachstelle (Art. 14)', nis2: '→ NIS2-Meldeentwurf', aiact: '→ AI-Act-Meldeentwurf' }
function bridgeLabel(r: string) { return bridgeLabels[r] || `→ ${r}` }
function bridgeHint(r: string) { return r === 'dsgvo' ? 'DSGVO-Projekt …' : r === 'cra' ? 'CRA-Projekt …' : r === 'nis2' ? 'NIS2-Projekt …' : r === 'aiact' ? 'AI-Act-Projekt …' : 'Projekt …' }
async function runBridge(regime: string) {
  const projekt = bridgeProjekt.value[regime]
  if (!projekt) { store.error = 'Bitte Zielprojekt angeben.'; return }
  await store.runBridge(store.currentIncident.id, regime, projekt)
}

// Einrichtung
async function doTest() { testResult.value = await store.testConnection(conn.value) }
async function doSave() { await store.saveConnection(conn.value); await store.fetchConnections() }
async function doSync() { const r = await store.sync(conn.value.name); testResult.value = { ok: r.ok, hinweis: r.ok ? `${r.new} neue Alarme übernommen.` : r.error } }
async function genSnippet() { snippet.value = await store.fetchSnippet(conn.value.push_token || '<TOKEN>', conn.value.min_level) }
function normMgrUrl(u: string) {
  let url = (u || '').trim()
  if (!url) return url
  if (!/^https?:\/\//.test(url)) url = 'https://' + url
  // Default-Port 55000 ergänzen, wenn keiner angegeben ist
  const afterScheme = url.replace(/^https?:\/\//, '')
  if (!/:\d+(\/|$)/.test(afterScheme)) url = url.replace(/\/+$/, '') + ':55000'
  return url
}
async function doRefreshAssets() {
  const r = await store.refreshAssets({ manager_url: normMgrUrl(mgr.value.url), username: mgr.value.username, password: mgr.value.password, verify_tls: mgr.value.verify_tls, name: conn.value.name || 'default' })
  assetResult.value = { ok: r.ok, hinweis: r.ok ? `${r.imported} Agenten importiert.` : r.error }
}

// Beim Incident-Wechsel: verknüpfte Alarme, KI-Prompt (Transparenz) + Regelwerke laden
watch(() => store.currentIncident?.id, async (id) => {
  incPromptText.value = ''; pbSelect.value = ''
  if (!id) { incAlerts.value = []; regimeFlags.value = {}; incIssues.value = []; incPlaybooks.value = { playbooks: [], mandatory_open: 0 }; evidence.value = []; custodyView.value = null; return }
  custodyView.value = null; eviFile.value = null
  const p = store.currentIncident?.pir || {}
  pirForm.value = { root_cause: p.root_cause || '', what_went_well: p.what_went_well || '',
                    what_went_wrong: p.what_went_wrong || '', lessons: p.lessons || '' }
  actionForm.value = { beschreibung: '', owner: '', frist: '' }
  const agent = store.currentIncident?.agent_name
  // #1467: Detail-Zusatzdaten PARALLEL laden (vorher 7 awaits seriell → spürbarer
  // „Hänger" beim Öffnen). allSettled: ein langsamer/fehlschlagender Call blockiert
  // die übrigen nicht mehr. loadIncPlaybooks braucht zuerst den Playbook-Katalog.
  if (!store.playbookCatalog.length) await store.fetchPlaybooks()
  await Promise.allSettled([
    loadEvidence(id),
    loadIncPlaybooks(id),
    store.incidentAlerts(id).then((v) => { incAlerts.value = v }),
    store.fetchIncidentIssues(id).then((v) => { incIssues.value = v }),
    (agent ? store.fetchLikelihood(agent) : Promise.resolve(null)).then((v) => { incLikelihood.value = v }),
    store.incidentPrompt(id).then((v) => { incPromptText.value = v }),
  ])
  // Race-Schutz: während des Ladens kann der Nutzer schon weitergeklickt haben.
  if (store.currentIncident?.id !== id) return
  const meta = store.currentIncident?.meta_json?.regime_flags || {}
  regimeFlags.value = {
    personenbezogen: !!(meta.personenbezogen || store.currentIncident?.personal_data_involved),
    nis2_scope: !!meta.nis2_scope, cra_produkt: !!meta.cra_produkt,
    ki_hochrisiko: !!meta.ki_hochrisiko,
  }
})

onMounted(async () => { await store.fetchConstants(); await store.fetchKpis() })
// #1482: laufenden Vuln-Sync-Poll beim Verlassen der SOC-Ansicht stoppen (sonst
// pollt das Interval nach dem Unmount weiter).
onUnmounted(() => { if (vulnPoll) { clearInterval(vulnPoll); vulnPoll = null } })
</script>

<style scoped>
/* #1359: einheitliche Design-Tokens für alle SOC-Tabs — eine Quelle für Karten-/
   Eingabe-Rahmen + Karten-Hover, statt verstreuter, leicht abweichender Literale
   (#e1e6ec/#e0e0e0 für Karten, #ccc/#cfd8dc für Eingaben). Sorgt für eine konsistente
   Optik über Dashboard, Alarme, Incidents, Detektion, Assistenten, Berichte … */
.soc-view {
  padding: 0 0 40px;
  --soc-card-border: #e1e6ec;
  --soc-input-border: #cfd8dc;
  --soc-card-hover: 0 2px 10px rgba(21,101,192,.15);
}
.soc-header { background: #1565c0; color: #fff; padding: 18px 24px; }
.soc-header h1 { margin: 0; font-size: 20px; }
.subtitle { margin: 4px 0 0; color: #90caf9; font-size: 13px; }
.tabs { display: flex; gap: 2px; background: #e3f2fd; padding: 0 16px; flex-wrap: wrap; }
.tab { background: none; border: none; padding: 12px 18px; cursor: pointer; font-size: 14px; color: #1565c0; border-bottom: 3px solid transparent; transition: background .12s, border-color .12s; }
.tab:hover { background: #d6e9fb; }
.tab.active { background: #fff; border-bottom: 3px solid #1565c0; font-weight: 600; }
.panel { padding: 20px 24px; max-width: 1400px; }
.banner { padding: 8px 12px; border-radius: 4px; margin: 8px 0; }
.banner.err { background: #ffebee; color: #b71c1c; } .banner.ok { background: #e8f5e9; color: #1b5e20; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.kpi { background: #fff; border: 1px solid var(--soc-card-border); border-radius: 8px; padding: 18px; text-align: center; transition: box-shadow .15s; }
.kpi.clickable:hover { box-shadow: var(--soc-card-hover); }
.kpi-val { font-size: 28px; font-weight: 700; color: #1565c0; line-height: 1.1; }
.kpi-val.bad { color: #b71c1c; } .kpi-val.ok { color: #2e7d32; } .kpi-val.mid { color: #f9a825; }
.kpi-lbl { font-size: 13px; color: #666; margin-top: 4px; }
.sev-bars { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.sev-row { display: flex; align-items: center; gap: 6px; background: #f5f7fa; border: 1px solid var(--soc-card-border); border-radius: 8px; padding: 6px 12px; }
.sev-count { font-weight: 700; color: #37474f; }
.sla-tbl { border-collapse: collapse; font-size: 13px; margin: 8px 0; }
.sla-tbl th, .sla-tbl td { padding: 6px 12px; border-bottom: 1px solid #eef1f4; text-align: left; }
.sla-tbl th { color: #546e7a; font-weight: 600; }
.sla-tbl input { border: 1px solid var(--soc-input-border); border-radius: 4px; padding: 5px; }
.sla-pill { background: #e8f5e9; color: #1b5e20; border-radius: 10px; padding: 2px 8px; font-size: 12px; font-weight: 600; }
.sla-pill.breach { background: #ffebee; color: #b71c1c; }
.sev-tag { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; color: #fff; font-weight: 600; }
.sev-tag.critical { background: #b71c1c; } .sev-tag.high { background: #e65100; }
.sev-tag.medium { background: #f9a825; color: #333; } .sev-tag.low { background: #607d8b; }
.filterbar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; background: #f5f7fa; border: 1px solid var(--soc-card-border); border-radius: 6px; padding: 10px 12px; }
.form-actions { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.filterbar select, .filterbar input { padding: 6px 8px; border: 1px solid var(--soc-input-border); border-radius: 4px; font-size: 13px; }
/* #1465: ECHTE Ursache der Header/Spalten-Fehlausrichtung — die globale Utility
   `.grid { display: grid }` (globals.css) kollidierte mit der Tabellen-Klasse
   `class="grid"`: die Tabelle wurde zum CSS-Grid, thead/tbody zu Grid-Items
   (display:block) → Spalten desynchron. `display: table` stellt das Tabellen-
   Layout wieder her (überschreibt die globale Regel für SOC-Tabellen). */
.grid { display: table; width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; border: 1px solid var(--soc-card-border); border-radius: 8px; }
/* #1463: breite Tabellen (z.B. Assets) horizontal scrollen statt quetschen —
   thead/tbody bleiben EIN Raster, Überschriften decken die Spalten exakt. */
.grid-scroll { overflow-x: auto; max-width: 100%; }
.grid th, .grid td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eef1f4; }
.grid th { background: #f5f7fa; color: #546e7a; font-weight: 600; }
.grid tbody tr:last-child td { border-bottom: none; }
.grid tbody tr:nth-child(even) { background: #fafcfe; }
.grid tbody tr:hover { background: #f0f7fe; }
.grid.mini { border-radius: 6px; }
.grid.mini td { padding: 5px 8px; }
.clickable { cursor: pointer; } .clickable:hover { background: #f0f7fe; } .clickable.active { background: #e3f2fd; }
.status-pill { display: inline-block; background: #eceff1; color: #455a64; border-radius: 10px; padding: 2px 10px; font-size: 12px; font-weight: 600; }
.status-pill.solved { background: #e8f5e9; color: #1b5e20; }
.status-pill.bad { background: #ffebee; color: #b71c1c; }
.muted { color: #999; font-size: 12px; }
.kind-tag { background: #ede7f6; color: #4527a0; border-radius: 8px; padding: 1px 6px; font-size: 11px; font-weight: 600; }
.supp-box { margin-bottom: 14px; background: #fbfdff; border: 1px solid var(--soc-card-border); border-radius: 6px; padding: 10px 12px; }
.supp-box summary { cursor: pointer; color: #1565c0; font-weight: 600; }
.supp-form { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin: 8px 0; }
.supp-form input { padding: 6px; border: 1px solid var(--soc-input-border); border-radius: 4px; font-size: 13px; }
.dry { font-size: 12px; color: #6a1b9a; }
.fieldhint { color: #888; font-weight: normal; font-size: 12px; }
/* Konsistente Abschnitts-Typografie über alle Tabs */
.panel > h3, .panel > .mass-head, .panel > .cov-src-head { margin: 22px 0 8px; }
.panel > h3:first-child, .panel > .mass-head:first-child, .panel > .kpi-grid:first-child { margin-top: 4px; }
.panel h3 { font-size: 15px; color: #1565c0; font-weight: 700; }
.panel > p.hint { margin: 0 0 12px; }
.hint-inline { color: #90a4ae; font-weight: 400; font-size: 12px; }
h5 { margin: 14px 0 6px; color: #455a64; font-size: 13px; font-weight: 700; }
button { background: #fff; border: 1px solid #1565c0; color: #1565c0; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 13px; transition: background .12s, box-shadow .12s; }
button:hover { background: #e3f2fd; }
button:disabled { opacity: .5; cursor: not-allowed; }
button.primary { background: #1565c0; color: #fff; } button.primary:hover { background: #0d47a1; }
button.ai { border-color: #6a1b9a; color: #6a1b9a; } button.ai:hover { background: #f3e5f5; }
button.close { border: none; font-size: 22px; color: #888; padding: 0 8px; } button.close:hover { background: none; color: #455; }
.two-col { display: grid; grid-template-columns: 340px 1fr; gap: 20px; }
.detail-bar { display: flex; align-items: center; margin-bottom: 12px; }
.link-back { border: none; color: #1565c0; background: none; padding: 0; font-size: 14px; }
.inc-headcard { background: #f5f7fa; border: 1px solid #dde3ea; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; }
.ih-title { font-size: 17px; font-weight: 600; color: #263238; }
.ih-facts { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 8px; font-size: 13px; color: #555; }
.pers-flag { background: #ad1457; color: #fff; border-radius: 10px; padding: 2px 8px; font-size: 12px; }
.closed-note { margin-top: 8px; font-size: 13px; color: #b71c1c; }
.likelihood { margin-top: 8px; font-size: 13px; color: #4527a0; }
.evidence { display: flex; gap: 18px; flex-wrap: wrap; background: #f5f7fa; border: 1px solid #dde3ea; border-radius: 6px; padding: 12px 16px; font-size: 13px; color: #455; }
.kachel-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; margin-bottom: 18px; }
.kachel { background: #fff; border: 1px solid var(--soc-card-border); border-radius: 8px; padding: 16px; cursor: pointer; transition: box-shadow .15s; }
.kachel:hover { box-shadow: var(--soc-card-hover); }
.kachel.active { border-color: #1565c0; background: #e3f2fd; }
.k-icon { font-size: 24px; } .k-title { font-weight: 600; color: #1565c0; margin: 6px 0 4px; }
.k-desc { font-size: 12px; color: #777; }
.assistant-panel { background: #fbfdff; border: 1px solid var(--soc-card-border); border-radius: 8px; padding: 16px; }
.assistant-panel .mono { width: 100%; font-family: Consolas, monospace; font-size: 12px; padding: 8px; border: 1px solid var(--soc-input-border); border-radius: 4px; }
.ki-actions { display: flex; gap: 8px; align-items: center; margin: 8px 0; }
.ki-paste { display: flex; flex-direction: column; gap: 6px; }
.copied { color: #1b5e20; font-size: 13px; }
.lage-result { margin-top: 12px; background: #e8f5e9; border-radius: 6px; padding: 12px; }
.lage-result pre { white-space: pre-wrap; font-family: inherit; font-size: 13px; margin: 0; }
.sub { font-size: 11px; color: #999; }
.agent-status { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: #eceff1; color: #555; }
.agent-status.active { background: #e8f5e9; color: #1b5e20; }
.agent-status.disconnected, .agent-status.never_connected { background: #ffebee; color: #b71c1c; }
.agent-status.manuell { background: #ede7f6; color: #4527a0; }
.krit-badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; color: #fff; background: #607d8b; }
.krit-badge.k4 { background: #e65100; } .krit-badge.k5 { background: #b71c1c; }
.krit-badge.k1, .krit-badge.k2 { background: #90a4ae; }
.ampel { padding: 2px 8px; border-radius: 10px; font-size: 12px; color: #fff; }
.ampel.gruen { background: #2e7d32; } .ampel.gelb { background: #f9a825; color: #333; }
.ampel.orange { background: #e65100; } .ampel.rot { background: #b71c1c; }
.tags-cell { font-size: 11px; color: #777; max-width: 200px; }
.asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
.asset-grid label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: #555; }
.asset-grid input, .asset-grid select { padding: 6px; border: 1px solid var(--soc-input-border); border-radius: 4px; font-size: 13px; }
.pb-assign { display: flex; gap: 6px; margin-bottom: 8px; }
.pb-assign select { padding: 6px; border: 1px solid var(--soc-input-border); border-radius: 4px; flex: 1; }
.playbook { background: #fbfdff; border: 1px solid var(--soc-card-border); border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; }
.pb-head { display: flex; justify-content: space-between; font-size: 14px; }
.pb-prog { color: #1565c0; font-weight: 600; }
.pb-bar { height: 6px; background: #eceff1; border-radius: 3px; margin: 6px 0 10px; overflow: hidden; }
.pb-bar-fill { height: 100%; background: #2e7d32; transition: width .2s; }
.pb-step { display: flex; gap: 8px; align-items: flex-start; padding: 4px 0; font-size: 13px; }
.pb-step.done span { color: #999; text-decoration: line-through; }
.pb-mand { color: #b71c1c; font-style: normal; font-size: 11px; background: #ffebee; border-radius: 6px; padding: 0 5px; margin-left: 4px; }
.warn-text { color: #b71c1c; font-size: 13px; }
/* Einklappbare KI-Analyse (#1316-UX) */
.ki-box { margin: 8px 0; }
.ki-box > summary { cursor: pointer; list-style: none; display: flex; align-items: center; gap: 10px; }
.ki-box > summary::-webkit-details-marker { display: none; }
.ki-box > summary h4 { margin: 8px 0; }
.ki-box > summary::before { content: '▸'; color: #1565c0; font-size: 13px; }
.ki-box[open] > summary::before { content: '▾'; }
.ki-done { color: #2e7d32; font-size: 12px; font-weight: 600; }
/* PIR + Maßnahmen (#1316) */
.pir-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 8px 0; }
.pir-grid label { display: flex; flex-direction: column; font-size: 13px; font-weight: 600; gap: 4px; }
.pir-grid textarea { font-family: inherit; font-size: 14px; padding: 8px; resize: vertical; min-height: 110px; line-height: 1.5; }
.pir-action-add { display: flex; gap: 8px; margin: 8px 0; flex-wrap: wrap; }
.pir-action-add input { padding: 6px; }
.pir-action-add input:first-child { flex: 1; min-width: 220px; }
.link-del { background: none; border: none; color: #b71c1c; cursor: pointer; font-size: 15px; }
tr.overdue td { background: #fdecea; }
tr.overdue td:nth-child(4) { color: #b71c1c; font-weight: 700; }
.mass-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.mass-head h3, .mass-head h4, .cov-src-head h3 { margin: 0; }
.mass-head .chk { margin-right: 12px; }
.mass-inc-t { font-size: 12px; color: #607d8b; }
.inc-link { color: #1565c0; cursor: pointer; font-weight: 600; }
.inc-link:hover { text-decoration: underline; }
/* Bulk-Alarm→Incident (#1328) */
.bulk-bar { background: #e3f2fd; border: 1px solid #90caf9; border-radius: 6px; padding: 8px 12px; margin: 8px 0; display: flex; align-items: center; gap: 8px; }
.add-alerts-box { margin: 10px 0; border: 1px solid var(--soc-card-border); border-radius: 6px; padding: 8px 12px; }
.add-alerts-box > summary { cursor: pointer; font-weight: 600; color: #1565c0; }
.add-alerts-list { max-height: 260px; overflow-y: auto; margin: 8px 0; }
.add-alert-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; cursor: pointer; }
.add-alert-row .aa-desc { flex: 1; }
.add-alert-row .aa-meta { color: #607d8b; font-size: 12px; }
/* Beweissicherung (#1317) */
.evi-add { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0; }
.evi-add input[type=text], .evi-add > input:not([type]) { padding: 6px; }
.evi-ret { display: flex; flex-direction: column; font-size: 11px; color: #607d8b; }
.evi-desc { font-size: 12px; color: #607d8b; }
.sha { font-family: Consolas, monospace; font-size: 12px; background: #f3f4f6; padding: 1px 4px; border-radius: 3px; }
.evi-actions { white-space: nowrap; }
.link-btn { background: none; border: none; cursor: pointer; font-size: 14px; padding: 0 4px; }
.evi-deleted { opacity: 0.5; text-decoration: line-through; }
.evi-del-note { font-size: 12px; color: #b71c1c; }
.custody-panel { border: 1px solid #90caf9; border-radius: 6px; padding: 8px 12px; margin: 8px 0; background: #f5faff; }
.custody-head { display: flex; justify-content: space-between; align-items: center; }
.custody-list { margin: 6px 0 0; padding-left: 16px; font-size: 13px; }
.custody-list .ts { color: #607d8b; font-size: 12px; }
/* Betrieb / Eskalation (#1318) */
.ho-add, .esc-add { display: flex; gap: 8px; margin: 8px 0; flex-wrap: wrap; align-items: center; }
.ho-add input, .ho-add select, .esc-add input, .esc-add select { padding: 6px; }
.esc-path { display: flex; flex-direction: column; gap: 6px; margin: 6px 0; }
.esc-step { display: flex; align-items: center; gap: 10px; background: #f5faff; border: 1px solid var(--soc-card-border); border-radius: 6px; padding: 6px 10px; }
.esc-stufe { background: #1565c0; color: #fff; border-radius: 10px; padding: 1px 8px; font-size: 12px; font-weight: 600; }
.esc-frist { color: #607d8b; font-size: 12px; margin-left: auto; }
/* SOC-Übungen (#1319) */
.ueb-add { display: flex; gap: 8px; margin: 8px 0; flex-wrap: wrap; align-items: center; }
.ueb-add input, .ueb-add select { padding: 6px; }
.ueb-card { border: 1px solid var(--soc-card-border); border-radius: 8px; margin: 10px 0; padding: 10px 14px; }
.ueb-head { display: flex; align-items: center; gap: 10px; }
.ueb-typ { font-size: 13px; }
.ueb-date { color: #607d8b; font-size: 12px; }
.ueb-erg { margin-left: auto; padding: 1px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; background: #eee; }
.erg-bestanden { background: #c8e6c9; color: #1b5e20; }
.erg-teilweise { background: #fff3cd; color: #7a5b00; }
.erg-nicht_bestanden { background: #ffcdd2; color: #b71c1c; }
.ueb-body { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.ueb-body label { display: flex; flex-direction: column; font-size: 12px; font-weight: 600; gap: 3px; }
.ueb-body textarea, .ueb-body input, .ueb-body select { font-family: inherit; font-size: 13px; padding: 6px; }
.ueb-row { display: flex; gap: 10px; }
.ueb-row label { flex: 1; }
/* ISO-22398-Übungsdetails (#1351) */
.ueb-lifecycle { display: flex; gap: 4px; flex-wrap: wrap; margin: 8px 0; }
.lc-step { font-size: 11px; padding: 3px 10px; border-radius: 12px; background: #eceff1; color: #607d8b; border: 1px solid var(--soc-input-border); }
.lc-step.done { background: #e8f5e9; color: #2e7d32; border-color: #a5d6a7; }
.lc-step.active { background: #1565c0; color: #fff; border-color: #1565c0; font-weight: 600; }
.ueb-detail { margin-top: 12px; border-top: 1px dashed #cfd8dc; padding-top: 10px; }
.ueb-detail h4 { margin: 14px 0 6px; font-size: 13px; color: #1565c0; }
.ueb-tab { width: 100%; border-collapse: collapse; font-size: 12px; }
.ueb-tab th, .ueb-tab td { border: 1px solid var(--soc-card-border); padding: 4px 6px; text-align: left; vertical-align: top; }
.ueb-tab th { background: #f5f7fa; font-weight: 600; }
.ueb-tab input, .ueb-tab select { width: 100%; box-sizing: border-box; font-size: 12px; padding: 3px; }
.ueb-aar { display: flex; flex-direction: column; gap: 6px; }
.ueb-aar label { display: flex; flex-direction: column; font-size: 12px; font-weight: 600; gap: 3px; }
.ueb-aar textarea, .ueb-aar input { font-family: inherit; font-size: 13px; padding: 6px; }
.ueb-aar-export { display: flex; gap: 8px; margin-top: 12px; }
/* Detektion / ATT&CK-Heatmap (#1321) */
.cov-kpis { display: flex; gap: 12px; margin: 8px 0 16px; flex-wrap: wrap; }
.cov-kpis .kpi { flex: 1; min-width: 130px; padding: 14px 16px; }
.cov-kpis .kpi-val { font-size: 24px; }
.uc-add { display: flex; gap: 8px; margin: 8px 0; flex-wrap: wrap; }
.uc-add input, .uc-add select { padding: 6px; }
.att-chip { display: inline-block; background: #e8eaf6; color: #283593; border-radius: 4px; padding: 1px 6px; margin: 1px; font-size: 11px; font-family: Consolas, monospace; }
.heatmap { display: flex; gap: 6px; overflow-x: auto; padding: 8px 0; }
.heat-col { min-width: 110px; flex-shrink: 0; }
.heat-tactic { font-size: 11px; font-weight: 700; color: #37474f; margin-bottom: 4px; height: 32px; }
.heat-cell { font-size: 10px; font-family: Consolas, monospace; padding: 3px 4px; margin-bottom: 3px; border-radius: 3px; cursor: default; }
.h-covered { background: #c8e6c9; color: #1b5e20; }
.h-partial { background: #fff3cd; color: #7a5b00; }
.h-gap { background: #ffcdd2; color: #b71c1c; }
.cov-src-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.cov-src { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.cov-src .lbl { color: #607d8b; }
button.sm { padding: 2px 8px; font-size: 12px; }
.heat-legend { font-size: 12px; margin: 6px 0; display: flex; gap: 10px; align-items: center; }
.heat-legend span { padding: 1px 8px; border-radius: 3px; }
.gap-list { max-height: 240px; overflow-y: auto; }
/* Threat-Intel / IOC (#1322) */
.ioc-hit { display: inline-block; background: #fff3e0; color: #e65100; border-radius: 4px; padding: 1px 6px; margin: 1px; font-size: 11px; font-family: Consolas, monospace; }
.ioc-flag { font-size: 12px; }
/* Log-Quellen Health (#1324) */
.health-pill { padding: 1px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; }
.hp-aktiv { background: #c8e6c9; color: #1b5e20; }
.hp-still { background: #fff3cd; color: #7a5b00; }
.hp-offline { background: #ffcdd2; color: #b71c1c; }
.hp-unbekannt { background: #eceff1; color: #546e7a; }
/* Management-Report (#1325) */
.report-preview { display: flex; gap: 18px; flex-wrap: wrap; font-size: 13px; margin: 6px 0 8px; color: #37474f; background: #f5f7fa; border: 1px solid var(--soc-card-border); border-radius: 6px; padding: 12px 16px; }
/* Berichts-Center (#1350/#1357) */
.bericht-zeitraum { display: flex; gap: 16px; align-items: center; flex-wrap: wrap;
  background: #f5f7fa; border: 1px solid var(--soc-card-border); border-radius: 8px; padding: 14px 16px; margin-bottom: 18px; }
.bericht-zeitraum .bz-title { font-weight: 700; color: #1565c0; font-size: 14px; }
.bericht-zeitraum label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #607d8b; font-weight: 600; }
.bericht-zeitraum input, .bericht-zeitraum select { padding: 6px 8px; border: 1px solid var(--soc-input-border); border-radius: 4px; font-size: 13px; }
.report-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; margin-bottom: 8px; }
.report-card { background: #fff; border: 1px solid var(--soc-card-border); border-radius: 8px; padding: 16px;
  display: flex; flex-direction: column; transition: box-shadow .15s, border-color .15s; }
.report-card:hover { box-shadow: var(--soc-card-hover); border-color: #90caf9; }
.report-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.report-titel { font-weight: 700; color: #1565c0; font-size: 14px; }
.report-norm { font-size: 11px; color: #90a4ae; font-family: Consolas, monospace; white-space: nowrap; }
.report-desc { font-size: 12px; color: #607d8b; margin: 6px 0 14px; flex: 1; line-height: 1.45; }
.report-actions { display: flex; gap: 8px; padding-top: 10px; border-top: 1px solid #eef1f4; }
.report-actions button { flex: 1; }
/* SOC-Reifegrad (#1326) */
.reife-domain { margin: 10px 0; }
.reife-norm { font-size: 11px; color: #607d8b; }
.auto-hint { color: #f57c00; font-size: 11px; }
.inc-actions { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
.inc-actions .lbl { font-size: 13px; color: #777; }
button.warn { border-color: #b71c1c; color: #b71c1c; }
.close-box, .edit-box { background: #fff3e0; border: 1px solid #ffe0b2; border-radius: 6px; padding: 12px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 8px; }
.edit-box { background: #f5f7fa; border-color: #dde3ea; }
.close-box textarea, .edit-box textarea, .edit-box input, .edit-box select { width: 100%; padding: 7px; border: 1px solid var(--soc-input-border); border-radius: 4px; font-size: 13px; }
.edit-box label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: #555; }
.regime-flags { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; background: #f5f7fa; border: 1px solid #dde3ea; border-radius: 6px; padding: 10px 12px; }
.regime-flags label { display: flex; align-items: center; gap: 5px; font-size: 13px; color: #455; }
.issue-form { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.issue-form input, .issue-form select { padding: 6px; border: 1px solid var(--soc-input-border); border-radius: 4px; font-size: 13px; }
.issue-list { list-style: none; padding: 0; font-size: 13px; }
.issue-list li { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.issue-prov { background: #eceff1; border-radius: 8px; padding: 1px 7px; font-size: 11px; color: #555; }
.actions { display: flex; gap: 6px; margin: 8px 0; flex-wrap: wrap; }
.track { background: #fff3e0; border-left: 3px solid #e65100; padding: 8px 12px; margin: 6px 0; border-radius: 4px; }
.bridge-row { display: flex; gap: 6px; margin-top: 6px; }
.bridge-row input { flex: 1; padding: 5px; border: 1px solid var(--soc-input-border); border-radius: 4px; }
.bridge-done { color: #1b5e20; font-size: 12px; margin-top: 4px; }
/* #1402: Incident-Detail zweispaltig — Inhalt links, Verlauf rechts */
.incident-detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 20px; align-items: start; }
.idg-main { min-width: 0; }
.idg-aside {
  position: sticky; top: 8px;
  background: #fafbfc; border: 1px solid #e3e8ee; border-radius: 8px;
  padding: 10px 14px; max-height: calc(100vh - 40px); overflow-y: auto;
}
.idg-aside h4 { margin-top: 0; }
@media (max-width: 1100px) {
  .incident-detail-grid { grid-template-columns: 1fr; }
  .idg-aside { position: static; max-height: none; }
}

.timeline { list-style: none; padding: 0; font-size: 13px; margin: 0; }
.timeline li { display: flex; flex-direction: column; gap: 1px; padding: 7px 0; border-bottom: 1px dashed #e0e0e0; }
.timeline li:last-child { border-bottom: none; }
.timeline .ts { color: #90a4ae; font-size: 11px; font-variant-numeric: tabular-nums; }
.timeline .tl-event { color: #1565c0; }
.timeline .tl-detail { color: #37474f; }
.timeline .tl-actor { color: #78909c; font-size: 11px; }
.note-add { display: flex; gap: 6px; margin-top: 10px; } .note-add input { flex: 1; padding: 6px; border: 1px solid var(--soc-input-border); border-radius: 4px; }
.note-add.big { flex-direction: column; align-items: stretch; }
.note-add.big textarea { width: 100%; padding: 8px; border: 1px solid var(--soc-input-border); border-radius: 4px; font-size: 13px; font-family: inherit; resize: vertical; }
.note-add.big button { align-self: flex-start; margin-top: 6px; }
.form { display: flex; flex-direction: column; gap: 10px; max-width: 620px; }
.form label { display: flex; flex-direction: column; font-size: 13px; color: #555; gap: 3px; }
.form label.chk { flex-direction: row; align-items: center; gap: 6px; }
.form input, .form select { padding: 8px; border: 1px solid var(--soc-input-border); border-radius: 4px; font-size: 14px; }
.help-box { background: #f5f7fa; border: 1px solid #dde3ea; border-radius: 6px; padding: 10px 12px; font-size: 13px; }
.help-box summary { cursor: pointer; color: #1565c0; font-weight: 600; }
.help-box pre, .snippet pre, .prompt-box textarea { font-family: Consolas, monospace; font-size: 12px; background: #263238; color: #cfd8dc; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }
.help-box code { background: #eceff1; padding: 1px 5px; border-radius: 3px; }
.prompt-box { display: flex; flex-direction: column; gap: 6px; margin: 8px 0; }
.prompt-box textarea { width: 100%; }
/* Einheitliche Eingabefelder in Inline-Add-Formularen */
.ho-add input, .ho-add select, .esc-add input, .esc-add select,
.uc-add input, .uc-add select, .ueb-add input, .ueb-add select,
.evi-add input, .pir-action-add input { border: 1px solid var(--soc-input-border); border-radius: 4px; }
.hint { color: #888; font-size: 13px; } .empty { text-align: center; color: #999; padding: 20px; }
.inc-meta { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 8px 0; font-size: 13px; }
h4 { margin: 16px 0 6px; color: #37474f; font-size: 14px; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: flex-start; justify-content: center; z-index: 1000; padding: 40px 16px; overflow-y: auto; }
.modal { background: #fff; border-radius: 8px; width: min(820px, 100%); box-shadow: 0 8px 30px rgba(0,0,0,.3); }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; border-bottom: 1px solid #eee; }
.modal-head h3 { margin: 0; color: #1565c0; }
.modal-body { padding: 20px; }
.modal-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 16px; align-items: center; }
.modal-actions .lbl { font-size: 13px; color: #777; }
</style>
