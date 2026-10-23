<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>📋 CRA-Dokumentation — der Start für jedes CRA-Projekt</h3>
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

    <!-- CRA-Klassifizierung (#1247): Produktklasse manuell + C6/C7-Read-Back -->
    <div class="klass-section">
      <h3>🏷️ CRA-Klassifizierung</h3>

      <div class="klass-row">
        <label>Produktklasse (manuell editierbar)</label>
        <select v-model="klassWahl" @change="saveKlasse">
          <option value="default">Default — Annex I</option>
          <option value="important_i">Wichtig Klasse 1 (Annex III)</option>
          <option value="important_ii">Wichtig Klasse 2 (Annex III)</option>
          <option value="critical">Kritisch (Annex IV)</option>
        </select>
        <span v-if="klassSaved" class="klass-saved">✓ gespeichert</span>
      </div>

      <!-- C6-Ergebnis -->
      <div v-if="klass?.klassifikator" class="klass-card">
        <div class="klass-card-head">
          <strong>C6 — Klassifikator-Ergebnis</strong>
          <span :class="['klass-source', klass.klassifikator.source === 'manuell' ? 'src-manual' : 'src-wizard']">
            {{ klass.klassifikator.source === 'manuell' ? '✋ manuell überschrieben' : '🤖 per Assistent gesetzt' }}
          </span>
        </div>
        <div class="klass-detail">Klasse: <strong>{{ klasseLabel(klass.klassifikator.klasse) }}</strong></div>
        <div v-if="klass.klassifikator.begruendung" class="klass-detail">{{ klass.klassifikator.begruendung }}</div>
        <div v-if="klass.klassifikator.updated_at" class="klass-detail klass-muted">
          Stand: {{ (klass.klassifikator.updated_at || '').slice(0, 16).replace('T', ' ') }}
        </div>
      </div>
      <p v-else class="hint">C6-Klassifikator noch nicht gelaufen — über den Assistenten oder manuell oben setzen.</p>

      <!-- C7-Ergebnis -->
      <div v-if="klass?.branche && (klass.branche.template_name || klass.branche.defaults)" class="klass-card">
        <div class="klass-card-head"><strong>C7 — Branchen-Template</strong></div>
        <div class="klass-detail">
          Template: <strong>{{ klass.branche.template_name || '(keines angewendet)' }}</strong>
        </div>
        <ul v-if="klass.branche.defaults" class="klass-defaults">
          <li>PSIRT Triage-SLA: {{ klass.branche.defaults.triage_sla || '—' }}</li>
          <li>PSIRT Fix-SLA Critical: {{ klass.branche.defaults.fix_sla_critical || '—' }}</li>
          <li>Support-Jahre: {{ klass.branche.defaults.support_jahre ?? '—' }}</li>
          <li>Threat-Framework: {{ klass.branche.defaults.threat_framework || '—' }}</li>
        </ul>
      </div>

      <button class="btn-link assistenten-link" @click="emit('open-assistenten')">🤖 Zum Assistenten →</button>

      <!-- Versions-Änderungen aus GitHub/GitLab (#1248) -->
      <div class="version-import">
        <h4>📦 Versions-Änderungen (Konformitätserklärung / Techn. Doku)</h4>
        <div class="version-bar">
          <button class="btn-secondary" :disabled="versionsBusy" @click="loadVersions">
            {{ versionsBusy ? '…' : 'Versionen laden' }}
          </button>
          <template v-if="repoVersions.length">
            <select v-model="versionBase">
              <option value="">— von (base) —</option>
              <option v-for="v in repoVersions" :key="'b-' + v.name" :value="v.name">{{ v.name }}</option>
            </select>
            <select v-model="versionHead">
              <option value="">— bis (head) —</option>
              <option v-for="v in repoVersions" :key="'h-' + v.name" :value="v.name">{{ v.name }}</option>
            </select>
            <button class="btn-primary" :disabled="!versionBase || !versionHead || diffBusy" @click="loadDiff">
              {{ diffBusy ? '…' : 'Änderungen laden' }}
            </button>
          </template>
        </div>
        <p v-if="versionMsg" class="hint" :class="{ 'klass-err': versionErr }">{{ versionMsg }}</p>
        <div v-if="versionDiff" class="version-diff">
          <strong>{{ versionDiff.base }} → {{ versionDiff.head }}</strong>:
          {{ versionDiff.commit_count }} Commits, {{ versionDiff.file_count }} geänderte Dateien
          <ul class="version-commits">
            <li v-for="(c, i) in (versionDiff.commits || []).slice(0, 12)" :key="i">
              {{ (c.message || '').split('\n')[0] }}<span v-if="c.sha" class="klass-muted"> ({{ c.sha }})</span>
            </li>
          </ul>
          <p class="hint">→ Im Assistenten-Tab per „🤖 Wesentliche Änderungen" zusammenfassen und als Dokument speichern.</p>
        </div>
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
          <!-- #1771: Ein Produkt besteht oft aus mehreren Artefakten. Ohne
               Benennung kollidieren zwei SBOMs derselben Version. -->
          <input v-model="sbomForm.artefakt" placeholder="Artefakt (z.B. anwendung, webserver)" />
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
        <!-- #1769: Was an der richtigen Stelle liegt, soll die Anwendung
             selbst finden. Format, Anzahl, Lizenzen und die Komponentenliste
             kommen dann aus der Datei statt aus dem Formular darüber. -->
        <div class="sbom-einlesen">
          <button class="btn-mini" :disabled="einlesenBusy" @click="sbomEinlesen">
            {{ einlesenBusy ? '… liest' : '📂 Aus Ablageort einlesen' }}</button>
          <span class="hint-klein">
            Dateien unter <code>data/cra/sbom/{{ projektOrdner }}/*.json</code>
            (CycloneDX oder SPDX) werden gelesen und angelegt. Vorhandene Zeilen
            bleiben unberührt.
          </span>
          <span v-if="einlesenMeldung" class="einlesen-meldung">{{ einlesenMeldung }}</span>
        </div>
        <table class="sbom-table">
          <thead><tr><th>Release</th><th>Artefakt</th><th>Format</th><th>Komp.</th><th>Datum</th><th>SBOM</th><th>Quelle</th><th>Komponenten</th><th></th></tr></thead>
          <tbody>
            <template v-for="s in store.sboms" :key="s.id">
            <tr>
              <td>{{ s.release_version }}</td>
              <td>{{ s.artefakt || '—' }}</td>
              <td>{{ s.sbom_format }}</td>
              <td>{{ s.komponenten_count }}</td>
              <td>{{ (s.sbom_datum || '').slice(0,10) }}</td>
              <td>
                <!-- #1422: SBOM direkt als Link/Download abrufbar -->
                <a v-if="sbomLink(s)" :href="sbomLink(s)" target="_blank" rel="noopener" class="sbom-dl">📄 Abrufen</a>
                <span v-else class="muted">—</span>
              </td>
              <td>{{ s.quelle }}</td>
              <td>
                <!-- #1761: Die Komponentenliste ist der Inhalt der SBOM. Ohne
                     sie ist die Sorgfaltspflicht (Art. 13 Abs. 5) nicht
                     belegbar — der Hinweis sagt das, statt es zu verschweigen. -->
                <button class="btn-mini" @click="toggleKomponenten(s)">
                  {{ offeneSbom === s.id ? '▾' : '▸' }} Liste &amp; Vergleich</button>
                <!-- #1761: `liste_anzahl` kommt mit der SBOM-Liste vom Server.
                     Vorher stand hier der lazy geladene Store — der ist vor dem
                     Aufklappen leer, und die Warnung behauptete „keine Liste",
                     wo eine existierte. Ein falsches „nicht belegbar" ist so
                     schlimm wie ein falsches „belegt". -->
                <span v-if="!komponentenVorhanden(s)"
                      class="komp-warn" title="Art. 13 Abs. 5 — ohne Komponentenliste nicht belegbar">
                  ⚠️ keine Liste</span>
                <span v-else class="komp-ok">{{ komponentenAnzahl(s) }} Komponenten</span>
              </td>
              <td><button class="btn-link" @click="store.deleteSbom(s.id)">🗑️</button></td>
            </tr>
            <tr v-if="offeneSbom === s.id" class="komp-row">
              <td colspan="9">
                <div class="komp-import">
                  <label>SBOM-Datei (CycloneDX- oder SPDX-JSON) einlesen:
                    <input type="file" accept=".json,application/json" @change="sbomDatei(s, $event)" />
                  </label>
                  <span v-if="kompBusy" class="muted">liest …</span>
                  <span v-if="kompMeldung" class="komp-meldung">{{ kompMeldung }}</span>
                </div>
                <!-- #1770: Container-Produkte liefern die SBOM nicht als Datei,
                     sondern als signierte Attestation am Image. Steht im Feld
                     „Pfad zur SBOM-Datei" eine Image-Referenz, holt die
                     Anwendung sie selbst. -->
                <div v-if="istImageRef(s)" class="komp-import">
                  <button class="btn-mini" :disabled="registryBusy === s.id"
                          @click="ausRegistry(s)">
                    {{ registryBusy === s.id ? '… holt' : '🛡️ SBOM vom Image holen' }}</button>
                  <span class="hint-klein">
                    Attestation zu <code>{{ s.blob_path }}</code> aus der Registry
                    (nur Registries aus der Positivliste).
                  </span>
                  <span v-if="registryMeldung[String(s.id)]" class="komp-meldung">
                    {{ registryMeldung[String(s.id)] }}</span>
                </div>

                <!-- Gerechneter Befund: neu / angehoben / entfallen -->
                <div v-if="befundFuer(s)" class="komp-befund">
                  <strong>Vergleich</strong>
                  <span v-if="befundFuer(s).erstbewertung" class="muted">
                    Erst-Release ohne Vorgänger — jede Komponente gilt als neu integriert.</span>
                  <span v-else class="muted">
                    gegen {{ befundFuer(s).vorgaenger_version || '—' }}</span>
                  <span class="komp-pill neu">neu {{ (befundFuer(s).vergleich?.neu || []).length }}</span>
                  <span class="komp-pill hoch">angehoben {{ (befundFuer(s).vergleich?.angehoben || []).length }}</span>
                  <span class="komp-pill weg">entfallen {{ (befundFuer(s).vergleich?.entfallen || []).length }}</span>
                  <span class="komp-pill">unverändert {{ befundFuer(s).vergleich?.unveraendert || 0 }}</span>
                  <span class="komp-pill" :class="{ offen: (befundFuer(s).unbewertet || []).length }">
                    {{ befundFuer(s).bewertet || 0 }}/{{ befundFuer(s).pflichtig || 0 }} bewertet</span>
                </div>

                <div v-if="(store.sbomKomponenten[String(s.id)] || []).length" class="komp-bewertung">
                  <select v-model="kompStatus">
                    <option value="geprueft">geprüft</option>
                    <option value="nicht_relevant">nicht relevant</option>
                    <option value="offen">zurücksetzen (offen)</option>
                  </select>
                  <input v-model="kompNotiz" class="komp-notiz"
                         placeholder="Begründung (mind. 10 Zeichen) — was wurde geprüft?" />
                  <button class="btn-primary" :disabled="!kompAuswahl.length || kompBusy"
                          @click="bewerteAuswahl(s)">
                    {{ kompAuswahl.length }} Komponente(n) bewerten</button>
                  <button class="btn-link" @click="auswahlPflichtig(s)">
                    Auswahl: alle neuen/angehobenen</button>
                  <button class="btn-link" @click="kompAuswahl = []">Auswahl leeren</button>
                  <!-- #1773: Der Weg für den Regelfall. 184 Komponenten einzeln
                       zu begründen ist die Stelle, an der ein Prüfpunkt
                       umgangen statt beantwortet wird. -->
                  <button class="btn-mini" @click="klassenFuer = s">
                    🧩 Nach Klassen bewerten</button>
                </div>

                <table class="komp-table" v-if="(store.sbomKomponenten[String(s.id)] || []).length">
                  <thead><tr><th></th><th>Komponente</th><th>Version</th><th>Lieferant</th>
                    <th>Lizenz</th><th>Befunde</th><th>Bewertung</th></tr></thead>
                  <tbody>
                    <tr v-for="k in (store.sbomKomponenten[String(s.id)] || [])" :key="k.id"
                        :class="{ 'komp-neu': istPflichtig(s, k) }">
                      <td><input type="checkbox" :value="k.id" v-model="kompAuswahl" /></td>
                      <td :title="k.purl || ''">{{ k.name }}
                        <span v-if="istPflichtig(s, k)" class="komp-pill neu">neu/angehoben</span>
                      </td>
                      <td>{{ k.version || '—' }}</td>
                      <td>{{ k.lieferant || '—' }}</td>
                      <td>{{ k.lizenz || '—' }}</td>
                      <!-- #1774: Beides lag in der Anwendung, nur nicht an
                           derselben Stelle — wer hier bewertete, musste den
                           Befund im C3-Reiter nachsehen. -->
                      <td :title="befundTitel(k)">
                        <span v-if="k.befunde_offen" class="komp-pill weg">
                          🛡️ {{ k.befunde_offen }} offen</span>
                        <span v-else-if="(k.befunde || []).length" class="komp-pill geprueft">
                          🛡️ {{ k.befunde.length }} behandelt</span>
                        <span v-else class="muted">—</span>
                      </td>
                      <td :title="k.bewertung_notiz || ''">
                        <span class="komp-pill" :class="k.bewertung_status">
                          {{ KOMP_LABEL[k.bewertung_status] || k.bewertung_status }}</span>
                        <span v-if="k.bewertet_von" class="muted"> · {{ k.bewertet_von }}</span>
                        <!-- Widerspruch in der eigenen Akte: „berührt die
                             Sicherheitseigenschaften nicht" trotz offenem Befund. -->
                        <span v-if="k.befunde_offen && k.bewertung_status === 'nicht_relevant'"
                              class="komp-warn"
                              title="Der offene Befund belegt das Gegenteil — Bewertung korrigieren">
                          ⚠️ Widerspruch</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
            </template>
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

    <!-- C3: In-App Vulnerability-Sync (#947/#948) -->
    <details class="section" open>
      <summary><strong>C3 — Schwachstellen-Sync</strong> (GitHub/GitLab → cra_vuln)</summary>
      <div class="section-body">
        <div class="sync-bar">
          <button class="btn-primary" :disabled="store.syncRunning" @click="runVulnSync">
            {{ store.syncRunning ? '⏳ Sync läuft…' : '🔄 Sync jetzt' }}
          </button>
          <span v-if="store.syncState" class="sync-last">
            Letzter Sync: <strong>{{ (store.syncState.last_run_at || '').slice(0, 16) }}</strong>
            · {{ store.syncState.inserted }} neu · {{ store.syncState.updated }} aktualisiert
            · {{ store.syncState.unchanged }} unverändert
            <span v-if="store.syncState.new_hc > 0" class="sync-hc">· ⚠ {{ store.syncState.new_hc }} neue High/Critical</span>
          </span>
          <span v-else class="sync-last">Noch kein Sync gelaufen.</span>
        </div>
        <p v-if="syncMsg" class="sync-msg">{{ syncMsg }}</p>
        <details v-if="store.syncRuns.length" class="sync-history">
          <summary>Historie ({{ store.syncRuns.length }})</summary>
          <table class="vuln-table">
            <thead><tr><th>Start</th><th>Status</th><th>neu</th><th>akt.</th><th>unveränd.</th><th>High/Crit</th></tr></thead>
            <tbody>
              <tr v-for="r in store.syncRuns" :key="r.id">
                <td>{{ (r.started_at || '').slice(0, 16) }}</td>
                <td>{{ r.status }}</td>
                <td>{{ r.report?.inserted ?? '–' }}</td>
                <td>{{ r.report?.updated ?? '–' }}</td>
                <td>{{ r.report?.unchanged ?? '–' }}</td>
                <td>{{ r.report?.new_high_critical ?? '–' }}</td>
              </tr>
            </tbody>
          </table>
        </details>
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
        <div class="vuln-filter">
          <label><input type="radio" value="offen" v-model="vulnFilter" /> nur offene</label>
          <label><input type="radio" value="alle" v-model="vulnFilter" /> alle</label>
          <span class="muted">{{ visibleVulns.length }} von {{ store.vulns.length }} angezeigt</span>
        </div>
        <!-- #1761: Art. 13 Abs. 6 — Meldung an den Hersteller der Komponente -->
        <div v-if="store.upstreamBefund" class="upstream-zeile">
          <strong>Meldepflicht an Komponenten-Hersteller</strong>
          <span class="muted">(Art. 13 Abs. 6)</span>
          <template v-if="store.upstreamBefund.ohne_komponentenliste">
            <span class="komp-warn">⚠️ keine Komponentenliste — Fremdbezug nicht
              belegbar, siehe C1</span>
          </template>
          <template v-else>
            <span class="komp-pill">{{ store.upstreamBefund.pflichtig }} pflichtig</span>
            <span class="komp-pill geprueft">{{ store.upstreamBefund.gemeldet }} gemeldet</span>
            <span class="komp-pill" :class="{ offen: store.upstreamBefund.offen }">
              {{ store.upstreamBefund.offen }} offen</span>
            <span v-if="store.upstreamBefund.ueberfaellig" class="komp-pill weg">
              {{ store.upstreamBefund.ueberfaellig }} überfällig</span>
          </template>
        </div>
        <table class="vuln-table">
          <thead><tr><th>CVE</th><th>Schwere</th><th>CVSS</th><th>Komponente</th><th>Status</th><th>Fix in</th><th>Upstream</th><th>Issue</th><th></th></tr></thead>
          <tbody>
            <tr v-if="!visibleVulns.length"><td colspan="9" class="muted">Keine Einträge für diesen Filter.</td></tr>
            <tr v-for="v in visibleVulns" :key="v.id" :class="`vuln-${v.status}`">
              <td :title="v.titel || ''">{{ v.cve_id }}
                <!-- #1584: Finding aus einem Pentest-Bericht der Firma -->
                <span v-if="v.source === 'pentest'" class="src-pentest"
                      title="Aus einem Pentest-Bericht der Firma übernommen (Firmen → 🛡️ Pentests)">🛡️ Pentest</span>
                <div v-if="v.source === 'pentest' && v.titel" class="vuln-titel">{{ v.titel }}</div>
              </td>
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
              <!-- #1761: Pflicht, Stand und Erfassung in einer Spalte. Wo keine
                   Pflicht besteht, steht der Grund — sonst sieht „—" wie ein
                   Versäumnis aus. -->
              <td class="upstream-cell">
                <template v-if="upstreamPflichtig(v)">
                  <span class="komp-pill" :class="upstreamPill(v).cls"
                        :title="v.upstream_begruendung || v.upstream_referenz || ''">
                    {{ upstreamPill(v).label }}</span>
                  <button class="btn-mini" title="Meldung an den Hersteller erfassen"
                          @click="upstreamForm = upstreamEntwurf(v)">✉️</button>
                </template>
                <span v-else class="muted" :title="upstreamGrund(v)">—</span>
              </td>
              <td class="vuln-issue-cell">
                <!-- #1041: CVE → Issue per Knopfdruck + Status -->
                <template v-for="li in (vulnIssues[String(v.id)] || [])" :key="li.id">
                  <a class="issue-pill" :href="safeUrl(li.url)" target="_blank" rel="noopener"
                     :title="li.title">#{{ li.issue_number || li.issue_iid }} · {{ li.state || 'open' }}</a>
                </template>
                <button class="btn-mini" :disabled="vulnBusy[String(v.id)]"
                        title="GitHub/GitLab-Issue erstellen" @click="createVulnIssue(v)">🐙</button>
                <button v-if="(vulnIssues[String(v.id)] || []).length" class="btn-mini"
                        :disabled="vulnBusy[String(v.id)]" title="Status synchronisieren"
                        @click="syncVulnIssue(v)">🔄</button>
              </td>
              <td><button class="btn-link" @click="store.deleteVuln(v.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>

        <!-- #1761: Erfassung der Meldung. „Gemeldet" verlangt Kanal und
             Referenz — ohne sie ist die Meldung behauptet, nicht dokumentiert
             (Art. 13 Abs. 6 verlangt die Dokumentation ausdrücklich). -->
        <div v-if="upstreamForm" class="upstream-form">
          <strong>Meldung an den Hersteller — {{ upstreamForm.cve_id }}</strong>
          <div class="form-grid">
            <select v-model="upstreamForm.status">
              <option value="offen">offen</option>
              <option value="gemeldet">gemeldet</option>
              <option value="nicht_erforderlich">nicht erforderlich</option>
            </select>
            <input v-model="upstreamForm.kanal"
                   placeholder="Kanal (z.B. GitHub Security Advisory, security@…)" />
            <input v-model="upstreamForm.referenz"
                   placeholder="Referenz (URL, Advisory- oder Ticket-Nummer)" />
            <input v-model="upstreamForm.gemeldet_am" type="date" title="Meldedatum" />
            <input v-model="upstreamForm.begruendung"
                   placeholder="Begründung (Pflicht bei „nicht erforderlich“)" />
            <button class="btn-primary" :disabled="upstreamBusy" @click="speichereUpstream">
              Speichern</button>
            <button class="btn-link" @click="upstreamForm = null">Abbrechen</button>
          </div>
        </div>
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
          <textarea v-model="store.supportPeriod.rationale"
                    :placeholder="begruendungPlaceholder" rows="2" />
          <!-- #1209: Art. 13(16) Support-Ende beim Kauf sichtbar -->
          <input v-model="store.supportPeriod.support_end_kaufhinweis_url" placeholder="Support-Ende-Kaufhinweis (URL, Art. 13(16))" />
          <input v-model="store.supportPeriod.support_end_kaufhinweis_nachweis" placeholder="Nachweis Support-Ende-Hinweis (Art. 13(16))" />
        </div>

        <!-- #1762: Zwei Kanäle, zwei Zusagen. Das Alt-Feld „Update-Kanal“ oben
             bleibt stehen (Bestandsdaten); getrennt ausgewiesen wird hier. -->
        <div class="zusagen">
          <p class="zusagen-titel">Update-Zusagen an den Kunden
            <span class="stelle-unsicher" title="Das Issue verortet die Zusagen bei Art. 13 Abs. 12–14; die Stelle ist in diesem Repo nicht am Verordnungstext nachgeprüft.">Art. 13 (Stelle nicht geprüft)</span>
          </p>
          <div class="form-grid">
            <input v-model="store.supportPeriod.sicherheitsupdate_kanal"
                   placeholder="Kanal für Sicherheitsupdates (z. B. Security-Repo)" />
            <input v-model="store.supportPeriod.funktionsupdate_kanal"
                   placeholder="Kanal für Funktionsupdates (z. B. Release-Kanal)" />
            <input v-model="store.supportPeriod.update_zusagen_nachweis"
                   placeholder="Wo stehen diese Zusagen? (URL/Dokument)" />
          </div>
          <label class="check">
            <input type="checkbox" v-model="store.supportPeriod.sicherheitsupdates_kostenlos" />
            Sicherheitsupdates werden im Unterstützungszeitraum <strong>kostenlos</strong> bereitgestellt
          </label>
          <label class="check">
            <input type="checkbox" v-model="store.supportPeriod.kanaele_getrennt" />
            Sicherheitsupdates sind <strong>getrennt</strong> von Funktionsupdates beziehbar
          </label>
          <p class="hint">
            Beides sind Zusagen, auf die sich der Kunde verlässt — sie stehen
            deshalb auch in der Kundenfassung des Berichts.
          </p>
        </div>

        <button class="btn-primary" @click="speichereSupport">Speichern (EOL + Fristen werden berechnet)</button>
        <p v-if="store.supportPeriodFehler" class="sp-fehler">
          {{ store.supportPeriodFehler }}
        </p>
        <p v-if="store.supportPeriod.eol_datum" class="hint">
          → End-of-Support: <strong>{{ store.supportPeriod.eol_datum }}</strong>
        </p>

        <!-- #1762: Fristenlauf statt nur Datumsanzeige. Für Art. 14 gibt es eine
             Fristenuhr, hier bisher nicht — eine 2035 ablaufende Frist fiel
             niemandem auf. -->
        <div class="fristen">
          <p class="fristen-titel">Fristenlauf
            <span v-if="store.supportFristen.schlechteste_ampel"
                  :class="['ampel', `ampel-${store.supportFristen.schlechteste_ampel}`]">
              {{ ampelText(store.supportFristen.schlechteste_ampel) }}
            </span>
            <button class="btn-link" @click="store.fetchSupportFristen()">aktualisieren</button>
          </p>
          <p v-if="!store.supportFristen.berechenbar" class="hint">
            Noch nicht bestimmbar — ohne Markteintritt weiß niemand, wie lange die
            technische Akte zu halten ist.
          </p>
          <ul v-else class="retention-fristen">
            <li v-for="f in store.supportFristen.fristen" :key="f.key">
              <span :class="['ampel', `ampel-${f.ampel}`]">{{ ampelText(f.ampel) }}</span>
              {{ f.label }}:
              <strong>{{ f.datum || '—' }}</strong>
              <span v-if="f.tage_verbleibend !== null && f.tage_verbleibend >= 0"
                    class="hint"> ({{ f.tage_verbleibend }} Tage)</span>
              <span v-else-if="f.tage_verbleibend !== null" class="hint">
                (seit {{ -f.tage_verbleibend }} Tagen verstrichen)</span>
              <span class="ref">{{ f.ref }}</span>
            </li>
          </ul>
        </div>
      </div>
    </details>

    <!-- #1207: PSIRT-SLA-Tracking gegen offene CVEs -->
    <details class="section" @toggle="store.fetchSlaStatus()">
      <summary><strong>SLA-Tracking (offene CVEs)</strong>
        <span v-if="store.slaStatus.violations" class="sla-badge violation">{{ store.slaStatus.violations }} überfällig</span>
        <span v-if="store.slaStatus.due_soon" class="sla-badge due">{{ store.slaStatus.due_soon }} bald fällig</span>
      </summary>
      <div class="section-body">
        <button class="btn-secondary" @click="store.fetchSlaStatus()">Aktualisieren</button>
        <p v-if="!store.slaStatus.psirt_set" class="hint">PSIRT-SLAs noch nicht hinterlegt (C2).</p>
        <table v-if="store.slaStatus.items?.length" class="sla-table">
          <thead><tr><th>CVE</th><th>Schwere</th><th>SLA</th><th>Soll-Fix</th><th>Status</th></tr></thead>
          <tbody>
            <tr v-for="i in store.slaStatus.items" :key="i.id">
              <td>{{ i.cve_id }}</td>
              <td>{{ i.schwere }}</td>
              <td>{{ i.sla_text || '—' }}</td>
              <td>{{ i.due_at ? i.due_at.slice(0, 10) : '—' }}</td>
              <td><span class="sla-status" :class="'st-' + i.status">{{ slaLabel(i.status) }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="hint">Keine offenen CVEs.</p>
      </div>
    </details>

    <!-- C5: Threat-Model -->
    <details class="section">
      <summary><strong>C5 — Threat-Model</strong> {{ store.threatModel.framework || '' }}</summary>
      <div class="section-body">
        <div class="form-grid">
          <select v-model="store.threatModel.framework">
            <option v-for="fw in THREAT_FRAMEWORKS" :key="fw.id" :value="fw.id">{{ fw.label }}</option>
          </select>
          <input v-model="store.threatModel.diagram_url" placeholder="Diagram-URL (optional)" />
          <textarea v-model="store.threatModel.scope" placeholder="Scope" rows="2" />
        </div>
        <p v-if="store.threatModel.framework_source === 'risk_link'" class="fw-hint fw-ok">
          ✓ Framework aus verknüpfter Risikobewertung übernommen (konsistenter Risiko-Score).
        </p>
        <p v-else-if="store.threatModel.framework_source === 'manual_override'" class="fw-hint fw-warn">
          ⚠ Manuell abweichend von der Risikobewertung — bewusste Abweichung bitte im Scope/Notizen begründen.
        </p>
        <button class="btn-primary" @click="store.saveThreatModel(store.threatModel)">Speichern</button>
      </div>
    </details>

    <!-- Risiken → Issue-Tracking (#1008) -->
    <details class="section">
      <summary><strong>Risiken &amp; Issue-Tracking</strong>
        <span v-if="riskLinked">({{ risiken.length }})</span>
      </summary>
      <div class="section-body">
        <p v-if="!riskLinked" class="hint">
          Kein Risikobewertungs-Projekt verknüpft — bitte zuerst im Reiter „Risiko-Verknüpfung" zuordnen.
        </p>
        <p v-else-if="!risiken.length" class="hint">Keine Risiken im verknüpften Projekt.</p>
        <table v-else>
          <thead>
            <tr><th>Nr</th><th>Risiko</th><th>Wert</th><th>Label</th><th>Issue</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="r in risiken" :key="r.id">
              <td>{{ r.nr }}</td>
              <td>{{ r.risk_name }}<span v-if="r.is_resolved" title="behoben"> ✓</span></td>
              <td>{{ r.risikowert ?? '—' }}</td>
              <td>{{ r.risiko_label || '—' }}</td>
              <td>
                <template v-for="li in (riskIssues[String(r.id)] || [])" :key="li.id">
                  <a class="issue-pill" :href="safeUrl(li.url)" target="_blank" rel="noopener"
                     :title="li.title">#{{ li.issue_number || li.issue_iid }} · {{ li.state || 'open' }}</a>
                </template>
                <span v-if="!(riskIssues[String(r.id)] || []).length" class="issue-none">—</span>
              </td>
              <td class="risk-actions">
                <button class="btn-mini" :disabled="riskBusy[String(r.id)]"
                        @click="createRiskIssue(r)">🐙 Issue</button>
                <button v-if="(riskIssues[String(r.id)] || []).length" class="btn-mini"
                        :disabled="riskBusy[String(r.id)]" @click="syncRiskIssue(r)">🔄</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- Phase B — KI-Wizards: jetzt im eigenen Assistenten-Tab (S11 / #1081) -->
    <div class="assistenten-hint">
      <span>🤖 Klassifikator, Branchen-Templates und Policy-Generatoren findest du jetzt im eigenen Assistenten-Tab.</span>
      <button class="btn-link assistenten-link" @click="emit('open-assistenten')">🤖 Zum Assistenten →</button>
    </div>

    <!-- #1773: Fremdkomponenten nach Klassen bewerten, mit KI-Entwurf je Gruppe -->
    <KomponentenKlassenModal v-if="klassenFuer"
                             :sbom-id="klassenFuer.id"
                             :version="klassenFuer.release_version"
                             :artefakt="klassenFuer.artefakt"
                             @close="klassenFuer = null"
                             @geaendert="nachKlassenBewertung" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { safeUrl } from '../../utils/safeUrl'  // #1175: Schema-Allowlist für Issue-Links
import { useCraStore } from '../../stores/cra'
import { THREAT_FRAMEWORKS } from './threatFrameworks'
import KomponentenKlassenModal from '../../components/cra/KomponentenKlassenModal.vue'

const store = useCraStore()

// #1207: Label für SLA-Status-Pille.
function slaLabel(s: string) {
  return ({ on_track: 'On Track', faellig: 'Fällig', ueberfaellig: 'Überfällig',
    unbekannt: 'Unbekannt' } as Record<string, string>)[s] || s
}

const emit = defineEmits<{
  /** Bittet den Host (CRAView), zum Assistenten-Tab zu wechseln (#1081). */
  (e: 'open-assistenten'): void
}>()

const sbomForm = ref({ release_version: '', artefakt: '', sbom_format: 'spdx', komponenten_count: 0, quelle: '', blob_path: '' })
// #1422: SBOM als Link abrufbar — blob_path ist i.d.R. eine URL (Release-Asset /
// Actions-Run / Workflow-Datei aus dem Autodetect). Nur http(s) verlinken.
const sbomLink = (s: any): string => {
  const p = String(s?.blob_path || '').trim()
  return /^https?:\/\//i.test(p) ? p : ''
}
const sbomLizenzenInput = ref('')

// #1770: SBOM-Attestation am Image holen.
const registryBusy = ref<number | null>(null)
const registryMeldung = ref<Record<string, string>>({})
/** Sieht der Pfad nach einer Image-Referenz aus (und nicht nach einer URL)? */
const istImageRef = (s: any): boolean => {
  const p = String(s?.blob_path || '').trim()
  if (!p || /^https?:\/\//i.test(p) || p.startsWith('/')) return false
  return /^[a-z0-9.\-]+(:\d+)?\/[a-z0-9._\-/]+(:[\w][\w.\-]*)?(@sha256:[0-9a-f]{64})?$/i.test(p)
}
const ausRegistry = async (s: any) => {
  registryBusy.value = s.id
  registryMeldung.value = { ...registryMeldung.value, [String(s.id)]: '' }
  try {
    const d = await store.sbomAusRegistry(s.id)
    registryMeldung.value = {
      ...registryMeldung.value,
      [String(s.id)]: d
        ? `${d.komponenten} Komponenten aus der Attestation (${d.digest?.slice(0, 19)}…)`
          + (d.zusammengefasst ? ` · ${d.zusammengefasst} Mehrfachnennung(en) zusammengefasst` : '')
        : (store.error || 'Attestation nicht abrufbar'),
    }
  } finally {
    registryBusy.value = null
  }
}

// #1769: SBOMs aus dem Ablageort übernehmen.
const einlesenBusy = ref(false)
const einlesenMeldung = ref('')
const projektOrdner = computed(() =>
  String(store.selectedProjekt || '').replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, '_'))

const sbomEinlesen = async () => {
  einlesenBusy.value = true
  einlesenMeldung.value = ''
  try {
    const data = await store.einleseSboms()
    if (!data) { einlesenMeldung.value = store.error || 'Einlesen fehlgeschlagen'; return }
    const n = (data.angelegt || []).length
    if (!data.gefunden) {
      einlesenMeldung.value = `Nichts gefunden unter ${data.ablageort}/${projektOrdner.value}/`
    } else if (!n) {
      einlesenMeldung.value =
        `${data.gefunden} Datei(en) gefunden — alle bereits erfasst (${(data.uebersprungen || []).join(', ')}).`
    } else {
      const liste = (data.angelegt || [])
        .map((a: any) => `${a.release_version} (${a.komponenten} Komponenten)`).join(', ')
      einlesenMeldung.value = `${n} SBOM(s) übernommen: ${liste}`
    }
  } catch (e: any) {
    einlesenMeldung.value = e?.response?.data?.error || 'Einlesen fehlgeschlagen'
  } finally {
    einlesenBusy.value = false
  }
}
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

// #1673: Status-Filter für den Vulnerability-Tracker (erledigte ausblendbar)
const ERLEDIGT_STATUS = ['fixed', 'disclosed', 'wontfix']
const vulnFilter = ref<'offen' | 'alle'>('offen')
const visibleVulns = computed(() => vulnFilter.value === 'alle'
  ? store.vulns
  : store.vulns.filter((v: any) => !ERLEDIGT_STATUS.includes(v.status)))

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

// ── #1762: Unterstützungszeitraum — Begründungspflicht und Fristenampel ─────

/** Der Platzhalter sagt, wann die Begründung Pflicht ist, nicht erst die
 *  Fehlermeldung nach dem Speichern. Erzwungen wird sie serverseitig. */
const begruendungPlaceholder = computed(() => {
  const jahre = Number(store.supportPeriod?.support_jahre ?? 5)
  return jahre < 5
    ? 'Begründung PFLICHT: unter 5 Jahren nur bei kürzerer erwarteter Nutzungsdauer'
    : 'Begründung (z. B. erwartete Nutzungsdauer, Produktstrategie)'
})

const AMPEL_TEXT: Record<string, string> = {
  gruen: 'läuft', gelb: 'unter 1 Jahr', rot: 'unter 90 Tagen',
  verstrichen: 'verstrichen', unbekannt: 'unbekannt',
}
const ampelText = (a: string) => AMPEL_TEXT[a] || a

async function speichereSupport() {
  await store.saveSupportPeriod(store.supportPeriod)
}

const reloadAll = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchSboms(),
    store.fetchPsirt(),
    store.fetchVulns(),
    store.fetchSupportPeriod(),
    store.fetchSupportFristen(),   // #1762: Fristenlauf der Aufbewahrungsfristen
    store.fetchThreatModel(),
    store.fetchPflichtDokuStatus(),
    store.fetchSyncStatus(),
    store.fetchSyncRuns(),
    // #1761: Wer ist dem Komponenten-Hersteller zu melden? Gerechnet, nicht
    // behauptet — die Spalte „Upstream" wäre sonst leer und sähe aus wie
    // „nichts zu tun".
    store.fetchUpstreamStatus(),
  ])
  offeneSbom.value = null
  kompAuswahl.value = []
  kompBefunde.value = {}
  upstreamForm.value = null
}

onMounted(reloadAll)
watch(() => store.selectedProjekt, reloadAll)

// ── CRA-Klassifizierung (#1247) ─────────────────────────────────────────────
const klass = ref<any | null>(null)
const klassWahl = ref('default')
const klassSaved = ref(false)

const loadKlass = async () => {
  if (!store.selectedProjekt) return
  klass.value = await store.fetchKlassifizierung()
  klassWahl.value = klass.value?.produktklasse || 'default'
}

const saveKlasse = async () => {
  const res = await store.setKlassifizierung(klassWahl.value)
  if (res) {
    klassSaved.value = true
    setTimeout(() => { klassSaved.value = false }, 2000)
    await loadKlass()
    await store.fetchAnforderungen(store.selectedProjekt!)  // Anforderungs-Filter neu (#1247)
    await store.fetchPflichtDokuStatus()
  }
}

onMounted(loadKlass)
watch(() => store.selectedProjekt, loadKlass)

// ── Versions-Import (#1248) ─────────────────────────────────────────────────
const repoVersions = ref<any[]>([])
const versionBase = ref('')
const versionHead = ref('')
const versionsBusy = ref(false)
const diffBusy = ref(false)
const versionDiff = ref<any | null>(null)
const versionMsg = ref('')
const versionErr = ref(false)

const loadVersions = async () => {
  versionsBusy.value = true
  versionMsg.value = ''
  versionErr.value = false
  try {
    const res = await store.fetchRepoVersions()
    if (res?.error) {
      versionErr.value = true
      versionMsg.value = res.error
      repoVersions.value = []
    } else {
      repoVersions.value = res?.versions || []
      if (!repoVersions.value.length) versionMsg.value = 'Keine Versionen/Tags gefunden.'
    }
  } finally {
    versionsBusy.value = false
  }
}

const loadDiff = async () => {
  diffBusy.value = true
  versionMsg.value = ''
  versionErr.value = false
  versionDiff.value = null
  try {
    const res = await store.fetchVersionDiff(versionBase.value, versionHead.value)
    if (res?.error) {
      versionErr.value = true
      versionMsg.value = res.error
    } else {
      versionDiff.value = res
    }
  } finally {
    diffBusy.value = false
  }
}

watch(() => store.selectedProjekt, () => {
  repoVersions.value = []
  versionDiff.value = null
  versionBase.value = ''
  versionHead.value = ''
  versionMsg.value = ''
})

// ── Risiken → Issue (#1008) ─────────────────────────────────────────────────
const risiken = ref<any[]>([])
const riskLinked = ref(false)
const riskIssues = ref<Record<string, any[]>>({})
const riskBusy = ref<Record<string, boolean>>({})

const loadRisiken = async () => {
  if (!store.selectedProjekt) return
  const res = await store.fetchRisiken()
  riskLinked.value = !!res.linked
  risiken.value = res.risiken || []
  // Verknüpfte Issues je Risiko nachladen
  for (const r of risiken.value) {
    riskIssues.value[String(r.id)] = await store.fetchRiskIssues(r.id)
  }
}

const createRiskIssue = async (r: any) => {
  riskBusy.value[String(r.id)] = true
  try {
    const res = await store.createRiskIssue(r.id, {})
    if (res?.created) {
      riskIssues.value[String(r.id)] = await store.fetchRiskIssues(r.id)
    }
  } finally {
    riskBusy.value[String(r.id)] = false
  }
}

const syncRiskIssue = async (r: any) => {
  riskBusy.value[String(r.id)] = true
  try {
    const res = await store.syncRiskIssues(r.id)
    if (res?.resolved) r.is_resolved = true
    riskIssues.value[String(r.id)] = await store.fetchRiskIssues(r.id)
  } finally {
    riskBusy.value[String(r.id)] = false
  }
}

onMounted(loadRisiken)
watch(() => store.selectedProjekt, loadRisiken)

// ── Schwachstellen → Issue (#1041) ──────────────────────────────────────────
const vulnIssues = ref<Record<string, any[]>>({})
const vulnBusy = ref<Record<string, boolean>>({})

const loadVulnIssues = async () => {
  if (!store.selectedProjekt) return
  for (const v of (store.vulns || [])) {
    vulnIssues.value[String(v.id)] = await store.fetchVulnIssues(v.id)
  }
}

const createVulnIssue = async (v: any) => {
  vulnBusy.value[String(v.id)] = true
  try {
    const res = await store.createVulnIssue(v.id, {})
    if (res?.created) vulnIssues.value[String(v.id)] = await store.fetchVulnIssues(v.id)
  } finally {
    vulnBusy.value[String(v.id)] = false
  }
}

const syncVulnIssue = async (v: any) => {
  vulnBusy.value[String(v.id)] = true
  try {
    const res = await store.syncVulnIssues(v.id)
    if (res?.resolved) v.status = 'fixed'
    vulnIssues.value[String(v.id)] = await store.fetchVulnIssues(v.id)
  } finally {
    vulnBusy.value[String(v.id)] = false
  }
}

watch(() => store.vulns, loadVulnIssues, { deep: false })

// C3 In-App-Sync (#947/#948)
const syncMsg = ref('')
const runVulnSync = async () => {
  syncMsg.value = ''
  const report = await store.startVulnSync('all')
  if (report) {
    syncMsg.value = `✓ Sync fertig: ${report.inserted ?? 0} neu, ${report.updated ?? 0} aktualisiert, `
      + `${report.unchanged ?? 0} unverändert`
      + ((report.new_high_critical ?? 0) > 0 ? ` — ⚠ ${report.new_high_critical} neue High/Critical!` : '')
  } else if (store.error) {
    syncMsg.value = `⚠ ${store.error}`
  }
}

const addSbom = async () => {
  const payload = {
    ...sbomForm.value,
    lizenzen: sbomLizenzenInput.value.split(',').map(s => s.trim()).filter(Boolean),
  }
  const ok = await store.saveSbom(payload)
  if (ok) {
    sbomForm.value = { release_version: '', artefakt: '', sbom_format: 'spdx', komponenten_count: 0, quelle: '', blob_path: '' }
    sbomLizenzenInput.value = ''
    await store.fetchPflichtDokuStatus()
  }
}

// ── #1761: Komponentenliste je SBOM (Art. 13 Abs. 5) ───────────────────────
// Die Bewertung hängt an der **Komponente**, nicht am Release: Die
// Sorgfaltspflicht ist eine Aussage über eine bestimmte Abhängigkeit. Erst
// dadurch ist der Release-Prüfpunkt gerechnet statt behauptet.

const KOMP_LABEL: Record<string, string> = {
  offen: 'offen', geprueft: 'geprüft', nicht_relevant: 'nicht relevant',
}
const offeneSbom = ref<number | null>(null)
const kompAuswahl = ref<number[]>([])
const kompStatus = ref('geprueft')
const kompNotiz = ref('')
const kompBusy = ref(false)
const kompMeldung = ref('')
/** Gerechneter Befund je Release-Version — Schlüssel ist die Version. */
const kompBefunde = ref<Record<string, any>>({})

const befundFuer = (s: any) => kompBefunde.value[String(s?.release_version || '')] || null

// #1761: Wie viele Komponenten sind zu dieser SBOM erfasst? Der Server liefert
// `liste_anzahl` mit der SBOM-Liste; der bereits geladene Store hat Vorrang,
// damit ein frischer Import sofort sichtbar ist, ohne die Liste neu zu holen.
const komponentenAnzahl = (s: any): number => {
  const geladen = (store.sbomKomponenten[String(s?.id)] || []).length
  if (geladen) return geladen
  return Number(s?.liste_anzahl || 0)
}
const komponentenVorhanden = (s: any): boolean => komponentenAnzahl(s) > 0

const ladeBefund = async (s: any) => {
  if (!s?.release_version) return
  const b = await store.fetchSbomVergleich(String(s.release_version))
  if (b) kompBefunde.value = { ...kompBefunde.value, [String(s.release_version)]: b }
}

const toggleKomponenten = async (s: any) => {
  kompMeldung.value = ''
  kompAuswahl.value = []
  if (offeneSbom.value === s.id) { offeneSbom.value = null; return }
  offeneSbom.value = s.id
  await Promise.all([store.fetchSbomKomponenten(s.id), ladeBefund(s)])
}

/** Schlüssel der neu aufgenommenen oder angehobenen Komponenten dieser SBOM. */
const pflichtKeys = (s: any): string[] => {
  const b = befundFuer(s)
  if (!b) return []
  return [...(b.vergleich?.neu || []), ...(b.vergleich?.angehoben || [])]
    .map((z: any) => String(z.komponent_key))
}
const istPflichtig = (s: any, k: any) =>
  pflichtKeys(s).includes(String(k?.komponent_key))

// #1774: Was gegen diese Komponente vorliegt — die Quelle steht mit dabei, weil
// sie den Unterschied macht: Ein Dependabot-Befund hat der Hersteller der
// Komponente selbst veröffentlicht, ein Pentest-Befund ist ein eigener Fund
// (Art. 13 Abs. 6).
const befundTitel = (k: any): string => {
  const liste = k?.befunde || []
  if (!liste.length) return 'Kein Befund dieser Komponente zugeordnet'
  return liste.map((b: any) => `${b.cve_id || b.titel} · ${b.schwere} · `
    + `${b.offen ? 'offen' : b.status} · ${b.quelle_label}`).join('\n')
}

// #1773: Gruppenbewertung. Nach dem Übernehmen müssen Liste **und** Befund neu
// gelesen werden — der gerechnete Prüfpunkt hat sich geändert.
const klassenFuer = ref<any | null>(null)
const nachKlassenBewertung = async () => {
  const s = klassenFuer.value
  if (!s) return
  await Promise.all([store.fetchSbomKomponenten(s.id), ladeBefund(s)])
}

const auswahlPflichtig = (s: any) => {
  const keys = pflichtKeys(s)
  kompAuswahl.value = (store.sbomKomponenten[String(s.id)] || [])
    .filter((k: any) => keys.includes(String(k.komponent_key)))
    .map((k: any) => k.id)
}

const sbomDatei = async (s: any, ev: Event) => {
  const datei = (ev.target as HTMLInputElement)?.files?.[0]
  if (!datei) return
  kompBusy.value = true
  kompMeldung.value = ''
  try {
    const res = await store.importSbomKomponenten(s.id, { sbom: await datei.text() })
    kompMeldung.value = res
      ? `${res.gespeichert} Komponente(n) gelesen (${res.format || 'Liste'})`
        + (res.bewertungen_uebernommen
          ? `, ${res.bewertungen_uebernommen} Bewertung(en) übernommen` : '')
      : `⚠ ${store.error}`
    if (res) await Promise.all([ladeBefund(s), store.fetchPflichtDokuStatus()])
  } finally {
    kompBusy.value = false
    ;(ev.target as HTMLInputElement).value = ''
  }
}

const bewerteAuswahl = async (s: any) => {
  kompBusy.value = true
  kompMeldung.value = ''
  try {
    const ok = await store.bewerteSbomKomponenten(
      kompAuswahl.value, kompStatus.value, kompNotiz.value)
    if (!ok) { kompMeldung.value = `⚠ ${store.error}`; return }
    kompAuswahl.value = []
    kompNotiz.value = ''
    await Promise.all([store.fetchSbomKomponenten(s.id), ladeBefund(s)])
  } finally {
    kompBusy.value = false
  }
}

// ── #1761: Meldung an den Hersteller der Komponente (Art. 13 Abs. 6) ───────

const upstreamForm = ref<any | null>(null)
const upstreamBusy = ref(false)

const upstreamInfo = (v: any) => store.upstreamPflicht[String(v?.id)] || null
const upstreamPflichtig = (v: any) => !!upstreamInfo(v)?.pflichtig
const upstreamGrund = (v: any) => upstreamInfo(v)?.grund || ''

const upstreamPill = (v: any): { cls: string; label: string } => {
  const st = String(v?.upstream_status || 'offen')
  if (st === 'gemeldet') return { cls: 'geprueft', label: 'gemeldet' }
  if (st === 'nicht_erforderlich') return { cls: 'nicht_relevant', label: 'nicht erforderlich' }
  // Überfällig heißt: Wir sind mit dem Befund nach außen gegangen, ohne den
  // Hersteller der Komponente zu unterrichten — das färbt die Ampel rot.
  return upstreamInfo(v)?.ueberfaellig
    ? { cls: 'weg', label: 'überfällig' }
    : { cls: 'offen', label: 'offen' }
}

const upstreamEntwurf = (v: any) => ({
  id: v.id, cve_id: v.cve_id,
  status: String(v.upstream_status || 'offen'),
  kanal: String(v.upstream_kanal || ''),
  referenz: String(v.upstream_referenz || ''),
  begruendung: String(v.upstream_begruendung || ''),
  gemeldet_am: String(v.upstream_gemeldet_am || '').slice(0, 10),
})

const speichereUpstream = async () => {
  if (!upstreamForm.value) return
  upstreamBusy.value = true
  try {
    const f = upstreamForm.value
    const ok = await store.setUpstreamMeldung(f.id, {
      status: f.status, kanal: f.kanal, referenz: f.referenz,
      begruendung: f.begruendung, gemeldet_am: f.gemeldet_am,
    })
    if (ok) upstreamForm.value = null
  } finally {
    upstreamBusy.value = false
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

/**
 * #1081: Die KI-Wizards (Klassifikator C6, Branchen-Template C7, Vuln-/Update-
 * Policy C8/C9) wurden in den eigenen Assistenten-Tab (AssistentenPanel.vue)
 * verschoben. Nach Anwendung dort lädt die CRAView die Pflicht-Doku neu.
 */
</script>

<style scoped>
.pflicht-doku { display: flex; flex-direction: column; gap: 16px; }
.fw-hint { margin: 8px 0; font-size: 13px; line-height: 1.4; }
.fw-hint.fw-ok { color: #1b5e20; }
.fw-hint.fw-warn { color: #b26a00; }
.sync-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.sync-last { font-size: 13px; color: #444; }
.sync-hc { color: #c62828; font-weight: 600; }
.sync-msg { margin: 8px 0 0; font-size: 13px; color: #1b5e20; }
.sync-history { margin-top: 10px; }
.sync-history > summary { cursor: pointer; font-size: 13px; color: #1565c0; }
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

/* Risiken → Issue (#1008) */
.risk-actions { white-space: nowrap; }
.btn-mini {
  font-size: 12px; padding: 3px 8px; margin-left: 4px; border-radius: 4px;
  border: 1px solid #1565c0; background: #fff; color: #1565c0; cursor: pointer;
}
.btn-mini:disabled { opacity: 0.5; cursor: default; }
.issue-pill {
  display: inline-block; font-size: 12px; padding: 1px 7px; margin: 0 3px 2px 0;
  border-radius: 10px; background: #e3f2fd; color: #0d47a1; text-decoration: none;
}
.issue-none { color: #999; }

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

.assistenten-hint {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  background: #f3e5f5; border-left: 4px solid #7b1fa2;
  padding: 12px 16px; border-radius: 8px; font-size: 13px; color: #4a148c;
}
.assistenten-link {
  margin-left: auto; font-weight: 600; color: #6a1b9a;
  background: none; border: none; cursor: pointer; font-size: 13px;
}
.assistenten-link:hover { text-decoration: underline; }

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

/* #1207: SLA-Tracking */
.sla-badge { display: inline-block; padding: 1px 6px; margin-left: 8px; border-radius: 4px; font-size: 11px; color: #fff; }
.sla-badge.violation { background: #c62828; }
.sla-badge.due { background: #f9a825; color: #000; }
.sla-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }
.sla-table th, .sla-table td { border-bottom: 1px solid #e0e0e0; padding: 4px 8px; text-align: left; }
.sla-status { padding: 1px 6px; border-radius: 4px; font-size: 11px; color: #fff; }
.sla-status.st-on_track { background: #2e7d32; }
.sla-status.st-faellig { background: #f9a825; color: #000; }
.sla-status.st-ueberfaellig { background: #c62828; }
.sla-status.st-unbekannt { background: #90a4ae; }
.retention-fristen { margin: 8px 0 0 18px; font-size: 12px; color: #455a64; }
/* #1762 — Update-Zusagen + Fristenampel */
.zusagen { border-top: 1px dashed #cfd8e3; margin-top: 10px; padding-top: 10px; }
.zusagen-titel { font-size: 13px; font-weight: 600; color: #37474f; margin: 0 0 8px; }
.stelle-unsicher { font-weight: 400; font-size: 11px; color: #8d6e63; margin-left: 6px; border-bottom: 1px dotted #8d6e63; cursor: help; }
.check { display: block; font-size: 13px; color: #37474f; margin: 4px 0; }
.check input { margin-right: 6px; }
.sp-fehler { color: #c62828; font-size: 13px; margin-top: 8px; }
.fristen { border-top: 1px dashed #cfd8e3; margin-top: 12px; padding-top: 10px; }
.fristen-titel { font-size: 13px; font-weight: 600; color: #37474f; margin: 0 0 6px; }
.fristen .ref { color: #90a4ae; font-size: 11px; margin-left: 6px; }
.ampel { display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 11px; font-weight: 600; background: #eceff1; color: #455a64; margin-right: 6px; }
.ampel-gruen { background: #e8f5e9; color: #2e7d32; }
.ampel-gelb { background: #fff8e1; color: #ef6c00; }
.ampel-rot { background: #ffebee; color: #c62828; }
.ampel-verstrichen { background: #ffebee; color: #b71c1c; }

/* #1247/#1248: CRA-Klassifizierung + Versions-Import */
.klass-section {
  background: #fff; border: 2px solid #1565c0; border-radius: 8px;
  padding: 16px 20px; display: flex; flex-direction: column; gap: 12px;
}
.klass-section h3 { margin: 0; color: #1565c0; font-size: 16px; }
.klass-section h4 { margin: 0 0 8px; color: #0d47a1; font-size: 14px; }
.klass-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.klass-row label { font-weight: 600; font-size: 13px; }
.klass-row select { padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.klass-saved { color: #2e7d32; font-size: 13px; font-weight: 600; }
.klass-card { background: #e8eaf6; border-radius: 6px; padding: 10px 14px; }
.klass-card-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.klass-source { font-size: 12px; padding: 2px 8px; border-radius: 10px; }
.src-manual { background: #fff3e0; color: #e65100; }
.src-wizard { background: #e3f2fd; color: #1565c0; }
.klass-detail { font-size: 13px; color: #283593; margin-top: 4px; }
.klass-muted { color: #777; }
.klass-err { color: #c62828; }
.klass-defaults { margin: 6px 0 0 18px; font-size: 12px; color: #455a64; }
.version-import { border-top: 1px solid #e0e0e0; padding-top: 12px; }
.version-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.version-bar select { padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.version-diff { background: #f5f5f5; border-radius: 6px; padding: 10px 14px; margin-top: 10px; font-size: 13px; }
.version-commits { margin: 6px 0 0 18px; font-size: 12px; color: #333; }
.src-pentest { display: inline-block; margin-left: 4px; padding: 0 6px; border-radius: 8px; font-size: 11px;
  background: #ede7f6; color: #4527a0; white-space: nowrap; }
.vuln-titel { font-size: 12px; color: #546e7a; margin-top: 2px; }
.vuln-filter { display: flex; gap: 14px; align-items: center; margin: 6px 0; font-size: 13px; }
.vuln-filter .muted { color: #90a4ae; }

/* #1761 — Komponentenliste je SBOM (Art. 13 Abs. 5) + Upstream-Meldung (Abs. 6) */
.komp-warn { margin-left: 6px; font-size: 12px; color: #e65100; white-space: nowrap; }
.sbom-einlesen { display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
                 margin: 8px 0 4px; }
.hint-klein { font-size: 12px; color: #607d8b; }
.einlesen-meldung { font-size: 12px; color: #2e7d32; }
.komp-ok { margin-left: 6px; font-size: 12px; color: #2e7d32; white-space: nowrap; }
.komp-row > td { background: #fafafa; padding: 10px 12px; }
.komp-import { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 13px; }
.komp-meldung { color: #2e7d32; font-size: 12px; }
.komp-befund { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin: 10px 0; font-size: 13px; }
.komp-bewertung { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.komp-bewertung select { padding: 5px 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.komp-notiz { flex: 1 1 260px; padding: 5px 8px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.komp-pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px;
  background: #eceff1; color: #37474f; white-space: nowrap; }
.komp-pill.neu { background: #e3f2fd; color: #1565c0; }
.komp-pill.hoch { background: #fff8e1; color: #e65100; }
.komp-pill.weg { background: #ffebee; color: #c62828; }
.komp-pill.offen { background: #fff3e0; color: #e65100; }
.komp-pill.geprueft { background: #e8f5e9; color: #2e7d32; }
.komp-pill.nicht_relevant { background: #ede7f6; color: #4527a0; }
.komp-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 6px; }
.komp-table th, .komp-table td { border-bottom: 1px solid #e0e0e0; padding: 4px 6px; text-align: left; }
.komp-table tr.komp-neu > td { background: #f1f8ff; }
.upstream-zeile { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin: 8px 0; font-size: 13px; }
.upstream-cell { white-space: nowrap; }
.upstream-form { background: #f5f5f5; border-radius: 6px; padding: 10px 14px; margin-top: 10px;
  display: flex; flex-direction: column; gap: 8px; font-size: 13px; }
</style>
