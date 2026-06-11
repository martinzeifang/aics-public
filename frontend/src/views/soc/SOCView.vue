<template>
  <div class="soc-view">
    <header class="soc-header">
      <h1>🚨 SOC — Security Operations Center</h1>
      <p class="subtitle">Triage &amp; Dokumentation für Wazuh-Alarme · Incidents · Meldepflichten</p>
    </header>

    <div v-if="store.error" class="banner err">{{ store.error }} <button @click="store.error = null">×</button></div>

    <nav class="tabs">
      <button v-for="t in tabs" :key="t.id" :class="['tab', { active: tab === t.id }]" @click="select(t.id)">{{ t.label }}</button>
    </nav>

    <!-- ── Dashboard ─────────────────────────────────────────────────── -->
    <section v-show="tab === 'dashboard'" class="panel">
      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-val">{{ store.kpis.alerts_new ?? '–' }}</div><div class="kpi-lbl">Neue Alarme</div></div>
        <div class="kpi"><div class="kpi-val">{{ store.kpis.incidents_open ?? '–' }}</div><div class="kpi-lbl">Offene Incidents</div></div>
        <div class="kpi"><div class="kpi-val">{{ pct(store.kpis.fp_rate) }}</div><div class="kpi-lbl">False-Positive-Rate</div></div>
        <div class="kpi"><div class="kpi-val">{{ store.kpis.alerts_total ?? '–' }}</div><div class="kpi-lbl">Alarme gesamt</div></div>
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
      </details>
      <table class="grid">
        <thead><tr><th>Zeit</th><th>Schwere</th><th>Lvl</th><th>Regel</th><th>Agent</th><th>Quell-IP</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="al in store.alerts" :key="al.alert_uid" @click="openAlertDetail(al.alert_uid)" class="clickable">
            <td>{{ shortTs(al.event_ts) }}</td>
            <td><span class="sev-tag" :class="al.severity">{{ sevDe(al.severity) }}</span></td>
            <td>{{ al.rule_level }}</td>
            <td><span v-if="al.kind === 'vulnerability'" class="kind-tag" title="Schwachstelle">🛡️ CVE</span> {{ al.description }}</td>
            <td>{{ al.agent_name }}</td>
            <td>{{ al.srcip }}</td>
            <td><span class="status-pill">{{ alertStatusDe(al.status) }}</span></td>
            <td>Details ›</td>
          </tr>
          <tr v-if="!store.alerts.length"><td colspan="8" class="empty">Keine Alarme. Einrichtung prüfen / Sync auslösen.</td></tr>
        </tbody>
      </table>
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

          <h4>📝 Notizen / dokumentierte Reaktion</h4>
          <div class="note-add big">
            <textarea v-model="noteText" rows="4" placeholder="Reaktion / Bewertung / Maßnahme dokumentieren …"></textarea>
            <button class="primary" @click="addNote">+ Notiz speichern</button>
          </div>

          <h4>🔗 Verknüpfte Wazuh-Alarme</h4>
          <div v-if="!(incAlerts.length)" class="hint">Keine verknüpften Alarme.</div>
          <table v-else class="grid mini">
            <tbody>
              <tr v-for="al in incAlerts" :key="al.alert_uid" class="clickable" @click="openAlertDetail(al.alert_uid)">
                <td><span class="sev-tag" :class="al.severity">{{ sevDe(al.severity) }}</span></td>
                <td>{{ al.description }}</td><td>{{ al.agent_name }}</td><td>{{ shortTs(al.event_ts) }}</td><td>Details ›</td>
              </tr>
            </tbody>
          </table>

          <h4>🤖 KI-Analyse des Incidents</h4>
          <KiAnalysePanel :prompt="incPromptText" :result="incidentAnalysis"
                          @ollama="analyzeIncidentOllama" @paste="parseIncidentPasteResp" />

          <h4>⚖️ Betroffene Regelwerke (steuern die Meldepflicht)</h4>
          <div class="regime-flags">
            <label v-for="r in regimeOptions" :key="r.key"><input type="checkbox" v-model="regimeFlags[r.key]" /> {{ r.label }}</label>
            <button class="primary" @click="saveRegimes">Speichern</button>
          </div>
          <p class="hint">Wähle die einschlägigen Regelwerke und klicke „🔁 Meldepflicht prüfen" oben — die passenden Meldetracks mit Brücken-Buttons (DSGVO/NIS2/CRA/AI-Act) erscheinen dann unten.</p>

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

          <h4>🕓 Verlauf</h4>
          <ul class="timeline">
            <li v-for="e in store.currentIncident.timeline" :key="e.id"><span class="ts">{{ shortTs(e.ts) }}</span> <b>{{ e.event }}</b> {{ e.detail }} <i>({{ e.actor }})</i></li>
          </ul>
      </div>
    </section>

    <!-- ── Assets ────────────────────────────────────────────────────── -->
    <section v-show="tab === 'assets'" class="panel">
      <!-- Liste -->
      <template v-if="!store.currentAsset">
        <div class="filterbar">
          <button @click="store.fetchAssets()">Aktualisieren</button>
          <button class="primary" @click="newAsset">+ Manuelles Asset</button>
          <span style="flex:1"></span>
          <span class="hint">Kritikalität & Tags steuern Priorisierung + Meldepflicht-Router.</span>
        </div>
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
            <label v-if="store.currentAsset.source==='manuell'">Name<input v-model="assetForm.agent_name" /></label>
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
          </div>
        </div>

        <h4>🛡️ Incidents auf diesem Asset ({{ (store.currentAsset.incidents||[]).length }})</h4>
        <table class="grid mini"><tbody>
          <tr v-for="i in store.currentAsset.incidents" :key="i.id" class="clickable" @click="gotoIncident(i.id)">
            <td>#{{ i.id }}</td><td>{{ i.titel }}</td><td><span class="status-pill">{{ incStatusDe(i.status) }}</span></td><td><span class="sev-tag" :class="i.severity">{{ sevDe(i.severity) }}</span></td>
          </tr>
          <tr v-if="!(store.currentAsset.incidents||[]).length"><td colspan="4" class="empty">Keine Incidents.</td></tr>
        </tbody></table>

        <h4>🚨 Alarme auf diesem Asset ({{ (store.currentAsset.alerts||[]).length }})</h4>
        <table class="grid mini"><tbody>
          <tr v-for="al in store.currentAsset.alerts" :key="al.alert_uid" class="clickable" @click="openAlertDetail(al.alert_uid)">
            <td><span class="sev-tag" :class="al.severity">{{ sevDe(al.severity) }}</span></td><td>{{ al.description }}</td><td>{{ shortTs(al.event_ts) }}</td>
          </tr>
          <tr v-if="!(store.currentAsset.alerts||[]).length"><td colspan="3" class="empty">Keine Alarme.</td></tr>
        </tbody></table>
      </div>
    </section>

    <!-- ── Assistenten ───────────────────────────────────────────────── -->
    <section v-show="tab === 'assistenten'" class="panel">
      <div class="kachel-grid">
        <div class="kachel" @click="select('alerts')"><div class="k-icon">🚨</div><div class="k-title">Alarm-Analyse</div><div class="k-desc">Einzelne Wazuh-Alarme per Ollama/Prompt bewerten — im Alarme-Tab.</div></div>
        <div class="kachel" @click="select('incidents')"><div class="k-icon">🛡️</div><div class="k-title">Incident-Analyse</div><div class="k-desc">Gesamtbild eines Incidents aus verknüpften Alarmen — im Incidents-Tab.</div></div>
        <div class="kachel" :class="{active: assistant==='lage'}" @click="openLagebericht"><div class="k-icon">🧭</div><div class="k-title">SOC-Lagebericht</div><div class="k-desc">KI-Lagebericht fürs Management aus KPIs + offenen Incidents.</div></div>
        <div class="kachel" :class="{active: assistant==='owasp'}" @click="openOwasp"><div class="k-icon">🧠</div><div class="k-title">OWASP-LLM-Erkennung</div><div class="k-desc">KI-spezifische Alarme erkennen und ins AI-Act-Register übernehmen.</div></div>
      </div>

      <div v-if="assistant==='lage'" class="assistant-panel">
        <h4>🧭 SOC-Lagebericht</h4>
        <details class="ki-transparency"><summary>🔍 Diese Daten werden an die KI übermittelt</summary><textarea readonly rows="6" class="mono">{{ lagePrompt }}</textarea></details>
        <div class="ki-actions">
          <button class="ai" @click="runLageOllama">🤖 Lokal mit Ollama</button>
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
        <table v-if="owaspDet.length" class="grid mini" style="margin-top:8px">
          <thead><tr><th>OWASP-LLM</th><th>Titel</th><th>Treffer</th></tr></thead>
          <tbody><tr v-for="o in owaspDet" :key="o.llm_id"><td>{{ o.llm_id }}</td><td>{{ o.title }}</td><td>{{ o.count }}</td></tr></tbody>
        </table>
        <p v-else-if="owaspChecked" class="hint">Keine KI-spezifischen Alarme erkannt.</p>
        <div class="issue-form" style="margin-top:8px">
          <input v-model="owaspProjekt" placeholder="AI-Act-Projekt" />
          <button class="primary" :disabled="!owaspDet.length" @click="pushOwasp">In AI-Act-Register übernehmen</button>
          <span v-if="owaspMsg" class="copied">{{ owaspMsg }}</span>
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
import { ref, computed, onMounted, watch } from 'vue'
import { useSocStore } from '../../stores/soc'
import AlertDetailCard from '../../components/soc/AlertDetailCard.vue'
import KiAnalysePanel from '../../components/soc/KiAnalysePanel.vue'

const store = useSocStore()
const tabs = [
  { id: 'dashboard', label: '📊 Dashboard' }, { id: 'alerts', label: '🚨 Alarme' },
  { id: 'incidents', label: '🛡️ Incidents' }, { id: 'assets', label: '🖥️ Assets' },
  { id: 'assistenten', label: '🤖 Assistenten' }, { id: 'setup', label: '⚙️ Einrichtung' },
]
const tab = ref('dashboard')
const severities = ['critical', 'high', 'medium', 'low']
const alertStates = computed(() => store.constants.alert_states || [])

// Deutsche Labels
const SEV_DE: Record<string, string> = { critical: 'Kritisch', high: 'Hoch', medium: 'Mittel', low: 'Niedrig' }
const AS_DE: Record<string, string> = { new: 'Neu', in_review: 'In Prüfung', false_positive: 'False Positive', confirmed: 'Bestätigt', suppressed: 'Unterdrückt' }
const IS_DE: Record<string, string> = { new: 'Neu', in_review: 'In Prüfung', false_positive: 'False Positive', confirmed: 'Bestätigt', contained: 'Eingedämmt', eradicated: 'Beseitigt', resolved: 'Behoben', closed: 'Geschlossen', reopened: 'Wieder geöffnet' }
const TS_DE: Record<string, string> = { offen: 'Offen', in_arbeit: 'In Arbeit', gemeldet: 'Gemeldet', abgeschlossen: 'Abgeschlossen' }
function sevDe(s: string) { return SEV_DE[s] || s }
function alertStatusDe(s: string) { return AS_DE[s] || s }
function incStatusDe(s: string) { return IS_DE[s] || s }
function trackStatusDe(s: string) { return TS_DE[s] || s }

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
  { key: 'dora_scope', label: 'DORA' },
]
const regimeFlags = ref<Record<string, boolean>>({})
const incIssues = ref<any[]>([])
const issueForm = ref<any>({ provider: 'github', repo: '' })
const incLikelihood = ref<any>(null)

const conn = ref<any>({ modus: 'pull', url: '', username: '', secret: '', index_pattern: 'wazuh-alerts-*', min_level: 7, verify_tls: false, push_token: '', name: 'default' })
const mgr = ref<any>({ url: '', username: '', password: '', verify_tls: false })
const testResult = ref<any>(null)
const assetResult = ref<any>(null)
const snippet = ref<any>(null)

function pct(v: any) { return v == null ? '–' : Math.round(v * 100) + '%' }
function shortTs(ts: string) { return (ts || '').replace('T', ' ').slice(0, 16) }
function nextAlert(s: string) { return ['in_review', 'false_positive', 'confirmed', 'suppressed'].filter(x => x !== s) }
function nextIncident(s: string) { return (store.constants.incident_transitions || {})[s] || [] }

async function select(id: string) {
  tab.value = id
  if (id === 'dashboard') { await store.fetchKpis(); await store.fetchControlEvidence() }
  if (id === 'alerts') { await loadAlerts(); await store.fetchAssets() }
  if (id === 'incidents') { await loadIncidents(); await store.fetchAssets() }
  if (id === 'assets') { store.currentAsset = null; await store.fetchAssets() }
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
  if (r?.ok) { closingMode.value = false; closeReason.value = '' }
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
  assetForm.value = { id: a.id, agent_name: a.agent_name, kritikalitaet: a.kritikalitaet ?? 3, umgebung: a.umgebung || '', lifecycle: a.lifecycle || 'aktiv', owner: a.owner || '', datenklasse: a.datenklasse || '', organisation: a.organisation || '', personenbezogen: !!a.personenbezogen, nis2_scope: !!a.nis2_scope, cra_produkt: !!a.cra_produkt, ki_hochrisiko: !!a.ki_hochrisiko, dora_scope: !!a.dora_scope }
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
}
async function removeAsset() { const id = store.currentAsset?.id; if (id) { await store.deleteAsset(id); store.currentAsset = null } }
function gotoIncident(id: number) { store.currentAsset = null; tab.value = 'incidents'; store.getIncident(id) }
async function reassignIncident(e: any) { const v = e.target.value; await store.assignIncident(store.currentIncident.id, v ? Number(v) : null) }
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
const bridgeLabels: Record<string, string> = { dsgvo: '→ DSGVO-Datenpanne anlegen', cra: '→ CRA-Schwachstelle (Art. 14)', nis2: '→ NIS2-Meldeentwurf', aiact: '→ AI-Act-Meldeentwurf', dora: '→ DORA (Stub)' }
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
  incPromptText.value = ''
  if (!id) { incAlerts.value = []; regimeFlags.value = {}; incIssues.value = []; return }
  incAlerts.value = await store.incidentAlerts(id)
  incIssues.value = await store.fetchIncidentIssues(id)
  incLikelihood.value = store.currentIncident?.agent_name ? await store.fetchLikelihood(store.currentIncident.agent_name) : null
  incPromptText.value = await store.incidentPrompt(id)
  const meta = store.currentIncident?.meta_json?.regime_flags || {}
  regimeFlags.value = {
    personenbezogen: !!(meta.personenbezogen || store.currentIncident?.personal_data_involved),
    nis2_scope: !!meta.nis2_scope, cra_produkt: !!meta.cra_produkt,
    ki_hochrisiko: !!meta.ki_hochrisiko, dora_scope: !!meta.dora_scope,
  }
})

onMounted(async () => { await store.fetchConstants(); await store.fetchKpis() })
</script>

<style scoped>
.soc-view { padding: 0 0 40px; }
.soc-header { background: #1565c0; color: #fff; padding: 18px 24px; }
.soc-header h1 { margin: 0; font-size: 20px; }
.subtitle { margin: 4px 0 0; color: #90caf9; font-size: 13px; }
.tabs { display: flex; gap: 2px; background: #e3f2fd; padding: 0 16px; }
.tab { background: none; border: none; padding: 12px 18px; cursor: pointer; font-size: 14px; color: #1565c0; }
.tab.active { background: #fff; border-bottom: 3px solid #1565c0; font-weight: 600; }
.panel { padding: 20px 24px; }
.banner { padding: 8px 12px; border-radius: 4px; margin: 8px 0; }
.banner.err { background: #ffebee; color: #b71c1c; } .banner.ok { background: #e8f5e9; color: #1b5e20; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.kpi { background: #f5f5f5; border-radius: 8px; padding: 18px; text-align: center; }
.kpi-val { font-size: 28px; font-weight: 700; color: #1565c0; } .kpi-lbl { font-size: 13px; color: #666; }
.sev-bars { display: flex; gap: 16px; }
.sev-row { display: flex; align-items: center; gap: 6px; }
.sev-tag { padding: 2px 8px; border-radius: 10px; font-size: 12px; color: #fff; }
.sev-tag.critical { background: #b71c1c; } .sev-tag.high { background: #e65100; }
.sev-tag.medium { background: #f9a825; color: #333; } .sev-tag.low { background: #607d8b; }
.filterbar, .form-actions { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.grid { width: 100%; border-collapse: collapse; font-size: 13px; }
.grid th, .grid td { text-align: left; padding: 7px 10px; border-bottom: 1px solid #eee; }
.grid th { background: #fafafa; color: #555; }
.grid.mini td { padding: 5px 8px; }
.clickable { cursor: pointer; } .clickable:hover { background: #f5fafe; } .clickable.active { background: #e3f2fd; }
.status-pill { background: #eceff1; border-radius: 10px; padding: 2px 8px; font-size: 12px; }
.kind-tag { background: #ede7f6; color: #4527a0; border-radius: 8px; padding: 1px 6px; font-size: 11px; font-weight: 600; }
.supp-box { margin-bottom: 14px; background: #fbfdff; border: 1px solid #e1e6ec; border-radius: 6px; padding: 10px 12px; }
.supp-box summary { cursor: pointer; color: #1565c0; font-weight: 600; }
.supp-form { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin: 8px 0; }
.supp-form input { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.dry { font-size: 12px; color: #6a1b9a; }
.fieldhint { color: #888; font-weight: normal; font-size: 12px; }
button { background: #fff; border: 1px solid #1565c0; color: #1565c0; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 13px; }
button:hover { background: #e3f2fd; }
button.primary { background: #1565c0; color: #fff; } button.ai { border-color: #6a1b9a; color: #6a1b9a; }
button.close { border: none; font-size: 22px; color: #888; padding: 0 8px; }
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
.kachel { background: #fff; border: 1px solid #e1e6ec; border-radius: 8px; padding: 16px; cursor: pointer; transition: box-shadow .15s; }
.kachel:hover { box-shadow: 0 2px 10px rgba(21,101,192,.15); }
.kachel.active { border-color: #1565c0; background: #e3f2fd; }
.k-icon { font-size: 24px; } .k-title { font-weight: 600; color: #1565c0; margin: 6px 0 4px; }
.k-desc { font-size: 12px; color: #777; }
.assistant-panel { background: #fbfdff; border: 1px solid #e1e6ec; border-radius: 8px; padding: 16px; }
.assistant-panel .mono { width: 100%; font-family: Consolas, monospace; font-size: 12px; padding: 8px; border: 1px solid #cfd8dc; border-radius: 4px; }
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
.asset-grid input, .asset-grid select { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.inc-actions { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
.inc-actions .lbl { font-size: 13px; color: #777; }
button.warn { border-color: #b71c1c; color: #b71c1c; }
.close-box, .edit-box { background: #fff3e0; border: 1px solid #ffe0b2; border-radius: 6px; padding: 12px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 8px; }
.edit-box { background: #f5f7fa; border-color: #dde3ea; }
.close-box textarea, .edit-box textarea, .edit-box input, .edit-box select { width: 100%; padding: 7px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.edit-box label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: #555; }
.regime-flags { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; background: #f5f7fa; border: 1px solid #dde3ea; border-radius: 6px; padding: 10px 12px; }
.regime-flags label { display: flex; align-items: center; gap: 5px; font-size: 13px; color: #455; }
.issue-form { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.issue-form input, .issue-form select { padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
.issue-list { list-style: none; padding: 0; font-size: 13px; }
.issue-list li { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.issue-prov { background: #eceff1; border-radius: 8px; padding: 1px 7px; font-size: 11px; color: #555; }
.actions { display: flex; gap: 6px; margin: 8px 0; flex-wrap: wrap; }
.track { background: #fff3e0; border-left: 3px solid #e65100; padding: 8px 12px; margin: 6px 0; border-radius: 4px; }
.bridge-row { display: flex; gap: 6px; margin-top: 6px; }
.bridge-row input { flex: 1; padding: 5px; border: 1px solid #ccc; border-radius: 4px; }
.bridge-done { color: #1b5e20; font-size: 12px; margin-top: 4px; }
.timeline { list-style: none; padding: 0; font-size: 13px; }
.timeline li { padding: 4px 0; border-bottom: 1px dashed #eee; }
.timeline .ts { color: #999; font-size: 11px; margin-right: 6px; }
.note-add { display: flex; gap: 6px; margin-top: 10px; } .note-add input { flex: 1; padding: 6px; border: 1px solid #ccc; border-radius: 4px; }
.note-add.big { flex-direction: column; align-items: stretch; }
.note-add.big textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; font-family: inherit; resize: vertical; }
.note-add.big button { align-self: flex-start; margin-top: 6px; }
.form { display: flex; flex-direction: column; gap: 10px; max-width: 620px; }
.form label { display: flex; flex-direction: column; font-size: 13px; color: #555; gap: 3px; }
.form label.chk { flex-direction: row; align-items: center; gap: 6px; }
.form input, .form select { padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
.help-box { background: #f5f7fa; border: 1px solid #dde3ea; border-radius: 6px; padding: 10px 12px; font-size: 13px; }
.help-box summary { cursor: pointer; color: #1565c0; font-weight: 600; }
.help-box pre, .snippet pre, .prompt-box textarea { font-family: Consolas, monospace; font-size: 12px; background: #263238; color: #cfd8dc; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }
.help-box code { background: #eceff1; padding: 1px 5px; border-radius: 3px; }
.prompt-box { display: flex; flex-direction: column; gap: 6px; margin: 8px 0; }
.prompt-box textarea { width: 100%; }
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
