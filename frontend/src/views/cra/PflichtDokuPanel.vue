<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>{{ $t('cra.pflichtDokuPanel.cRADokumentationDerStartFurJedesCRAP') }}</h3>
      <p>{{ $t('cra.pflichtDokuPanel.derEUCyberResilienceActVerlangtFurJe') }} <strong>{{ $t('common.dieseSeiteIstDerErsteSchritt') }}</strong> {{ $t('cra.pflichtDokuPanel.ohneSieSindDieAnforderungenWeiterRec') }}</p>

      <div class="workflow">
        <strong>{{ $t('cra.pflichtDokuPanel.empfohleneReihenfolge') }}</strong>
        <ol>
          <li><strong>{{ $t('cra.pflichtDokuPanel.klassifikatorC6') }}</strong> {{ $t('cra.pflichtDokuPanel.bestimmtDieProduktklasseDefaultWicht') }}</li>
          <li><strong>{{ $t('cra.pflichtDokuPanel.branchenTemplateC7') }}</strong> {{ $t('cra.pflichtDokuPanel.setztBranchenublicheDefaultsSLAsSupp') }}</li>
          <li><strong>{{ $t('cra.pflichtDokuPanel.sBOMPSIRTVulnSupportPeriodThreatMode') }}</strong>
            {{ $t('cra.pflichtDokuPanel.diePflichtArtefakteAusGitHubRepoErke') }}</li>
          <li><strong>{{ $t('cra.pflichtDokuPanel.vulnPolicyUpdatePolicyC8C9') }}</strong> {{ $t('cra.pflichtDokuPanel.generierenFertigeMarkdownTexteFurSEC') }}</li>
        </ol>
      </div>

      <div class="storage-hint">
        <strong>{{ $t('cra.pflichtDokuPanel.woWirdDasGespeichert') }}</strong>
        {{ $t('cra.pflichtDokuPanel.dieDatenLandenInDenModulDatenbanken') }}<code>cra_sbom</code>, <code>cra_psirt</code>,
        <code>cra_vuln</code>, <code>cra_support_period</code>, <code>cra_threatmodel</code>{{ $t('cra.pflichtDokuPanel.undImProjektSelbst') }}<code>cra_projekte.produktklasse</code>, <code>meta_json.cra.klassifikator</code>{{ $t('cra.pflichtDokuPanel.werdenImBerichtTabAutomatischEingebu') }}
      </div>
    </div>

    <!-- CRA-Klassifizierung (#1247): Produktklasse manuell + C6/C7-Read-Back -->
    <div class="klass-section">
      <h3>{{ $t('cra.pflichtDokuPanel.cRAKlassifizierung') }}</h3>

      <div class="klass-row">
        <label>{{ $t('cra.pflichtDokuPanel.produktklasseManuellEditierbar') }}</label>
        <select v-model="klassWahl" @change="saveKlasse">
          <option value="default">{{ $t('cra.pflichtDokuPanel.defaultAnnexI') }}</option>
          <option value="important_i">{{ $t('cra.pflichtDokuPanel.wichtigKlasseAnnexIII') }}</option>
          <option value="important_ii">{{ $t('cra.pflichtDokuPanel.wichtigKlasseAnnexIII2') }}</option>
          <option value="critical">{{ $t('cra.pflichtDokuPanel.kritischAnnexIV') }}</option>
        </select>
        <span v-if="klassSaved" class="klass-saved">{{ $t('cra.pflichtDokuPanel.gespeichert') }}</span>
      </div>

      <!-- C6-Ergebnis -->
      <div v-if="klass?.klassifikator" class="klass-card">
        <div class="klass-card-head">
          <strong>{{ $t('cra.pflichtDokuPanel.c6KlassifikatorErgebnis') }}</strong>
          <span :class="['klass-source', klass.klassifikator.source === 'manuell' ? 'src-manual' : 'src-wizard']">
            {{ klass.klassifikator.source === 'manuell' ? $t('cra.pflichtDokuPanel.manuellUberschrieben') : $t('cra.pflichtDokuPanel.perAssistentGesetzt') }}
          </span>
        </div>
        <div class="klass-detail">{{ $t('cra.pflichtDokuPanel.klasse') }} <strong>{{ klasseLabel(klass.klassifikator.klasse) }}</strong></div>
        <div v-if="klass.klassifikator.begruendung" class="klass-detail">{{ klass.klassifikator.begruendung }}</div>
        <div v-if="klass.klassifikator.updated_at" class="klass-detail klass-muted">
          {{ $t('cra.pflichtDokuPanel.standV0', { v0: (klass.klassifikator.updated_at || '').slice(0, 16).replace('T', ' ') }) }}
        </div>
      </div>
      <p v-else class="hint">{{ $t('cra.pflichtDokuPanel.c6KlassifikatorNochNichtGelaufenUber') }}</p>

      <!-- C7-Ergebnis -->
      <div v-if="klass?.branche && (klass.branche.template_name || klass.branche.defaults)" class="klass-card">
        <div class="klass-card-head"><strong>{{ $t('cra.pflichtDokuPanel.c7BranchenTemplate') }}</strong></div>
        <div class="klass-detail">
          {{ $t('cra.pflichtDokuPanel.template') }} <strong>{{ klass.branche.template_name || $t('cra.pflichtDokuPanel.keinesAngewendet') }}</strong>
        </div>
        <ul v-if="klass.branche.defaults" class="klass-defaults">
          <li>{{ $t('cra.pflichtDokuPanel.pSIRTTriageSLAV0', { v0: klass.branche.defaults.triage_sla || '—' }) }}</li>
          <li>{{ $t('cra.pflichtDokuPanel.pSIRTFixSLACriticalV0', { v0: klass.branche.defaults.fix_sla_critical || '—' }) }}</li>
          <li>{{ $t('cra.pflichtDokuPanel.supportJahreV0', { v0: klass.branche.defaults.support_jahre ?? '—' }) }}</li>
          <li>{{ $t('cra.pflichtDokuPanel.threatFrameworkV0', { v0: klass.branche.defaults.threat_framework || '—' }) }}</li>
        </ul>
      </div>

      <button class="btn-link assistenten-link" @click="emit('open-assistenten')">{{ $t('common.zumAssistenten') }}</button>

      <!-- Versions-Änderungen aus GitHub/GitLab (#1248) -->
      <div class="version-import">
        <h4>{{ $t('cra.pflichtDokuPanel.versionsAnderungenKonformitatserklar') }}</h4>
        <div class="version-bar">
          <button class="btn-secondary" :disabled="versionsBusy" @click="loadVersions">
            {{ versionsBusy ? '…' : $t('cra.pflichtDokuPanel.versionenLaden') }}
          </button>
          <template v-if="repoVersions.length">
            <select v-model="versionBase">
              <option value="">{{ $t('cra.pflichtDokuPanel.vonBase') }}</option>
              <option v-for="v in repoVersions" :key="'b-' + v.name" :value="v.name">{{ v.name }}</option>
            </select>
            <select v-model="versionHead">
              <option value="">{{ $t('cra.pflichtDokuPanel.bisHead') }}</option>
              <option v-for="v in repoVersions" :key="'h-' + v.name" :value="v.name">{{ v.name }}</option>
            </select>
            <button class="btn-primary" :disabled="!versionBase || !versionHead || diffBusy" @click="loadDiff">
              {{ diffBusy ? '…' : $t('cra.pflichtDokuPanel.anderungenLaden') }}
            </button>
          </template>
        </div>
        <p v-if="versionMsg" class="hint" :class="{ 'klass-err': versionErr }">{{ versionMsg }}</p>
        <div v-if="versionDiff" class="version-diff">
          <strong>{{ versionDiff.base }} → {{ versionDiff.head }}</strong>{{ $t('cra.pflichtDokuPanel.v0CommitsV1GeanderteDateien', { v0: versionDiff.commit_count, v1: versionDiff.file_count }) }}
          <ul class="version-commits">
            <li v-for="(c, i) in (versionDiff.commits || []).slice(0, 12)" :key="i">
              {{ (c.message || '').split('\n')[0] }}<span v-if="c.sha" class="klass-muted"> ({{ c.sha }})</span>
            </li>
          </ul>
          <p class="hint">{{ $t('cra.pflichtDokuPanel.imAssistentenTabPerWesentlicheAnderu') }}</p>
        </div>
      </div>
    </div>

    <!-- Auto-Detect-Action -->
    <div class="autodetect-bar">
      <div class="autodetect-info">
        <strong>{{ $t('cra.pflichtDokuPanel.ausGitHubRepoErkennen') }}</strong>
        <small>{{ $t('cra.pflichtDokuPanel.scanntSECURITYMdReleasesSecurityAdvi') }}</small>
      </div>
      <input v-model="autodetectRepo" :placeholder="$t('cra.pflichtDokuPanel.ownerRepoOptionalSonstAusProjektVerk')" />
      <button class="btn-secondary" :disabled="autodetectBusy" @click="runAutodetect(true)">{{ $t('cra.pflichtDokuPanel.vorschauDryRun') }}</button>
      <button class="btn-primary" :disabled="autodetectBusy" @click="runAutodetect(false)">{{ autodetectBusy ? '...' : $t('cra.pflichtDokuPanel.erkennenAnwenden') }}</button>
    </div>

    <div v-if="autodetectResult" class="autodetect-result">
      <div>
        <strong>{{ $t('cra.pflichtDokuPanel.funde') }}</strong>
        SBOM={{ autodetectResult.summary?.sbom_count || 0 }},
        PSIRT-Felder={{ autodetectResult.summary?.psirt_fields || 0 }},
        Vulns={{ autodetectResult.summary?.vuln_count || 0 }},
        Support-Period={{ autodetectResult.summary?.support_period_set ? '✓' : '–' }},
        ThreatModel={{ autodetectResult.summary?.threatmodel_set ? '✓' : '–' }}
        <span v-if="autodetectResult.applied">
          {{ $t('cra.pflichtDokuPanel.ubernommenSBOMV0PSIRTV1VulnV2SPV3TMV', { v0: autodetectResult.applied.sbom, v1: autodetectResult.applied.psirt, v2: autodetectResult.applied.vuln, v3: autodetectResult.applied.support_period, v4: autodetectResult.applied.threatmodel }) }}
        </span>
        <span v-else class="hint">{{ $t('cra.pflichtDokuPanel.dryRunNichtsGespeichert') }}</span>
      </div>
      <div v-if="autodetectResult.findings?.access" class="diagnose">
        Repo-Zugang: {{ autodetectResult.findings.access.accessible ? '✓' : '✗' }}
        ({{ autodetectResult.findings.access.auth_used || 'unbekannt' }},
        Rate-Limit {{ autodetectResult.findings.access.rate_limit_hint || '?' }})
      </div>
      <div v-if="autodetectResult.findings?.warnings?.length" class="warnings">
        <strong>{{ $t('cra.pflichtDokuPanel.hinweise') }}</strong>
        <ul><li v-for="(w, i) in autodetectResult.findings.warnings" :key="i">{{ w }}</li></ul>
      </div>
    </div>

    <!-- Klassifikator-Status (#578) -->
    <div v-if="klassifikatorInfo" class="klassifikator-card">
      <div class="kl-header">
        <strong>{{ $t('cra.pflichtDokuPanel.cRAKlassifikatorErgebnis') }}</strong>
        <span :class="['kl-badge', `kl-${klassifikatorInfo.klasse}`]">{{ klasseLabel(klassifikatorInfo.klasse) }}</span>
        <span v-if="klassifikatorInfo.konfidenz" class="kl-confidence">{{ $t('cra.pflichtDokuPanel.konfidenzV0', { v0: klassifikatorInfo.konfidenz }) }}</span>
      </div>
      <div v-if="klassifikatorInfo.begruendung" class="kl-reason">{{ klassifikatorInfo.begruendung }}</div>
      <div v-if="klassifikatorInfo.konformitaetsbewertung" class="kl-conformity">
        {{ $t('cra.pflichtDokuPanel.konformitatsBewertung') }} <strong>{{ klassifikatorInfo.konformitaetsbewertung }}</strong>
      </div>
      <div v-if="klassifikatorInfo.indikatoren?.length" class="kl-indicators">
        <em>{{ $t('cra.pflichtDokuPanel.indikatoren') }}</em> {{ klassifikatorInfo.indikatoren.join(' · ') }}
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

    <!-- C1: SBOM — Übersicht bleibt hier, Verwaltung liegt im eigenen Untermenü -->
    <details class="section" open>
      <summary><strong>{{ $t('cra.pflichtDokuPanel.c1SBOMVerzeichnis') }}</strong> {{ $t('cra.pflichtDokuPanel.v0Eintrage', { v0: store.sboms.length }) }}</summary>
      <div class="section-body">
        <p class="hint">{{ $t('cra.pflichtDokuPanel.sBOMUebersichtHinweis') }}</p>
        <button class="btn-primary sbom-open" @click="emit('open-sbom')">
          {{ $t('cra.pflichtDokuPanel.sBOMVerzeichnisOeffnen') }}
        </button>
      </div>
    </details>

    <!-- C2: PSIRT -->
    <details ref="psirtSection" class="section">
      <summary><strong>{{ $t('cra.pflichtDokuPanel.c2PSIRTProzess') }}</strong> {{ store.psirt.intake_kanal ? '✅' : '' }}</summary>
      <div class="section-body">
        <div class="form-grid">
          <input v-model="store.psirt.intake_kanal" :placeholder="$t('cra.pflichtDokuPanel.phIntakeKanal')" />
          <input v-model="store.psirt.triage_sla" :placeholder="$t('cra.pflichtDokuPanel.phTriageSla')" />
          <input v-model="store.psirt.fix_sla_critical" :placeholder="$t('cra.pflichtDokuPanel.fixSLACriticalZBTage')" />
          <input v-model="store.psirt.fix_sla_high" :placeholder="$t('cra.pflichtDokuPanel.fixSLAHigh')" />
          <input v-model="store.psirt.fix_sla_medium" :placeholder="$t('cra.pflichtDokuPanel.fixSLAMedium')" />
          <input v-model="store.psirt.disclosure_policy_url" :placeholder="$t('cra.pflichtDokuPanel.disclosurePolicyURL')" />
          <input v-model="store.psirt.security_md_url" placeholder="SECURITY.md-URL" />
          <!-- #1796: Das Feld gab es im Datenmodell und im Prüfpunkt, nur nicht
               in der Maske — der Punkt „fehlt: PSIRT-Kontakt" war damit nicht
               erfüllbar. -->
          <input v-model="psirtKontakte"
                 :placeholder="$t('cra.pflichtDokuPanel.pSIRTKontakteMehrereMitKommaTrennen')" />
          <textarea v-model="store.psirt.notizen" :placeholder="$t('common.notizen')" rows="2" />
        </div>
        <button class="btn-primary" @click="store.savePsirt(store.psirt)">{{ $t('common.save') }}</button>
      </div>
    </details>

    <!-- C3: In-App Vulnerability-Sync (#947/#948) -->
    <details class="section" open>
      <summary><strong>{{ $t('cra.pflichtDokuPanel.c3SchwachstellenSync') }}</strong> {{ $t('cra.pflichtDokuPanel.gitHubGitLabCraVuln') }}</summary>
      <div class="section-body">
        <div class="sync-bar">
          <button class="btn-primary" :disabled="store.syncRunning" @click="runVulnSync">
            {{ store.syncRunning ? $t('cra.pflichtDokuPanel.syncLauft') : $t('cra.pflichtDokuPanel.syncJetzt') }}
          </button>
          <span v-if="store.syncState" class="sync-last">
            {{ $t('cra.pflichtDokuPanel.letzterSync') }} <strong>{{ (store.syncState.last_run_at || '').slice(0, 16) }}</strong>
            {{ $t('cra.pflichtDokuPanel.v0NeuV1AktualisiertV2Unverandert', { v0: store.syncState.inserted, v1: store.syncState.updated, v2: store.syncState.unchanged }) }}
            <span v-if="store.syncState.new_hc > 0" class="sync-hc">{{ $t('cra.pflichtDokuPanel.v0NeueHighCritical', { v0: store.syncState.new_hc }) }}</span>
          </span>
          <span v-else class="sync-last">{{ $t('cra.pflichtDokuPanel.nochKeinSyncGelaufen') }}</span>
        </div>
        <p v-if="syncMsg" class="sync-msg">{{ syncMsg }}</p>
        <details v-if="store.syncRuns.length" class="sync-history">
          <summary>{{ $t('cra.pflichtDokuPanel.historieV0', { v0: store.syncRuns.length }) }}</summary>
          <table class="vuln-table">
            <thead><tr><th>{{ $t('cra.pflichtDokuPanel.start') }}</th><th>{{ $t('common.status') }}</th><th>neu</th><th>{{ $t('cra.pflichtDokuPanel.akt') }}</th><th>{{ $t('cra.pflichtDokuPanel.unverand') }}</th><th>{{ $t('cra.pflichtDokuPanel.highCrit') }}</th></tr></thead>
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
      <summary><strong>{{ $t('cra.pflichtDokuPanel.c3VulnerabilityTracker') }}</strong> ({{ openVulnCount }}/{{ store.vulns.length }} offen)</summary>
      <div class="section-body">
        <div class="form-grid">
          <input v-model="vulnForm.cve_id" :placeholder="$t('cra.pflichtDokuPanel.phCveId')" />
          <input v-model="vulnForm.titel" :placeholder="$t('common.titel')" />
          <select v-model="vulnForm.schwere">
            <option value="low">low</option><option value="medium">medium</option>
            <option value="high">high</option><option value="critical">critical</option>
            <option value="unknown">unknown</option>
          </select>
          <input v-model.number="vulnForm.cvss_score" type="number" step="0.1" :placeholder="$t('cra.pflichtDokuPanel.cVSSScore')" />
          <input v-model="vulnForm.affected_component" :placeholder="$t('cra.pflichtDokuPanel.betroffeneKomponente')" />
          <input v-model="vulnForm.fixed_in_version" :placeholder="$t('cra.pflichtDokuPanel.fixedInVersion')" />
          <select v-model="vulnForm.status">
            <option value="open">open</option><option value="triaging">triaging</option>
            <option value="fixed">fixed</option><option value="disclosed">disclosed</option>
            <option value="wontfix">wontfix</option>
          </select>
          <button class="btn-primary" @click="addVuln">{{ $t('cra.pflichtDokuPanel.hinzufugen') }}</button>
        </div>
        <div class="vuln-filter">
          <label><input type="radio" value="offen" v-model="vulnFilter" /> {{ $t('cra.pflichtDokuPanel.nurOffene') }}</label>
          <label><input type="radio" value="alle" v-model="vulnFilter" /> {{ $t('cra.pflichtDokuPanel.alle') }}</label>
          <span class="muted">{{ $t('cra.pflichtDokuPanel.v0VonV1Angezeigt', { v0: visibleVulns.length, v1: store.vulns.length }) }}</span>
        </div>
        <!-- #1761: Art. 13 Abs. 6 — Meldung an den Hersteller der Komponente -->
        <div v-if="store.upstreamBefund" class="upstream-zeile">
          <strong>{{ $t('cra.pflichtDokuPanel.meldepflichtAnKomponentenHersteller') }}</strong>
          <span class="muted">{{ $t('cra.pflichtDokuPanel.artAbs') }}</span>
          <template v-if="store.upstreamBefund.ohne_komponentenliste">
            <span class="komp-warn">{{ $t('cra.pflichtDokuPanel.keineKomponentenlisteFremdbezugNicht') }}</span>
          </template>
          <template v-else>
            <span class="komp-pill">{{ store.upstreamBefund.pflichtig }} pflichtig</span>
            <span class="komp-pill geprueft">{{ store.upstreamBefund.gemeldet }} gemeldet</span>
            <span class="komp-pill" :class="{ offen: store.upstreamBefund.offen }">
              {{ store.upstreamBefund.offen }} offen</span>
            <span v-if="store.upstreamBefund.ueberfaellig" class="komp-pill weg">
              {{ $t('cra.pflichtDokuPanel.v0Uberfallig', { v0: store.upstreamBefund.ueberfaellig }) }}</span>
          </template>
        </div>
        <!-- #2062 -->
        <div class="tabelle-scroll">
        <table class="vuln-table">
          <thead><tr><th>{{ $t('cra.pflichtDokuPanel.cVE') }}</th><th>{{ $t('common.schwere') }}</th><th>{{ $t('common.cVSS') }}</th><th>{{ $t('cra.pflichtDokuPanel.komponente') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('cra.pflichtDokuPanel.fixIn') }}</th><th>{{ $t('cra.pflichtDokuPanel.upstream') }}</th><th>{{ $t('cra.pflichtDokuPanel.issue') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-if="!visibleVulns.length"><td colspan="9" class="muted">{{ $t('cra.pflichtDokuPanel.keineEintrageFurDiesenFilter') }}</td></tr>
            <tr v-for="v in visibleVulns" :key="v.id" :class="`vuln-${v.status}`">
              <td :title="v.titel || ''">{{ v.cve_id }}
                <NeubewertungBadge :text="v.triage_kommentar" modul="cra"
                                   :projekt="store.selectedProjekt" objekt-pfad="vulns"
                                   :objekt-id="v.id" @bestaetigt="reloadAll()" />
                <!-- #1584: Finding aus einem Pentest-Bericht der Firma -->
                <span v-if="v.source === 'pentest'" class="src-pentest"
                      :title="$t('cra.pflichtDokuPanel.ausEinemPentestBerichtDerFirmaUberno')">{{ $t('cra.pflichtDokuPanel.pentest') }}</span>
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
                  <button class="btn-mini" :title="$t('cra.pflichtDokuPanel.meldungAnDenHerstellerErfassen')"
                          @click="upstreamForm = upstreamEntwurf(v)">✉️</button>
                </template>
                <span v-else class="muted" :title="upstreamGrund(v)">—</span>
              </td>
              <td class="vuln-issue-cell">
                <!-- #1041/#1847: CVE → Issue. Die Bedienung kommt aus dem
                     geteilten Baustein; „Entknüpfen" gab es hier bisher nicht,
                     obwohl die Store-Funktion dafür seit #1041 ungenutzt dalag. -->
                <IssueVerknuepfung
                  api-base="/cra"
                  :projekt-name="store.selectedProjekt || ''"
                  objekt-pfad="vulns"
                  :objekt-id="v.id"
                  :objekt-titel="v.cve_id"
                  text-ziel="den Triage-Kommentar"
                  darstellung="zeile"
                  @geaendert="store.fetchVulns()"
                  @uebernommen="store.fetchVulns()"
                />
              </td>
              <td><button class="btn-link" @click="store.deleteVuln(v.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
        </div>

        <!-- #1761: Erfassung der Meldung. „Gemeldet" verlangt Kanal und
             Referenz — ohne sie ist die Meldung behauptet, nicht dokumentiert
             (Art. 13 Abs. 6 verlangt die Dokumentation ausdrücklich). -->
        <div v-if="upstreamForm" class="upstream-form">
          <strong>{{ $t('cra.pflichtDokuPanel.meldungAnDenHerstellerV0', { v0: upstreamForm.cve_id }) }}</strong>
          <div class="form-grid">
            <select v-model="upstreamForm.status">
              <option value="offen">{{ $t('cra.pflichtDokuPanel.offen') }}</option>
              <option value="gemeldet">{{ $t('cra.pflichtDokuPanel.gemeldet') }}</option>
              <option value="nicht_erforderlich">{{ $t('cra.pflichtDokuPanel.nichtErforderlich') }}</option>
            </select>
            <input v-model="upstreamForm.kanal"
                   :placeholder="$t('cra.pflichtDokuPanel.kanalZBGitHubSecurityAdvisorySecurit')" />
            <input v-model="upstreamForm.referenz"
                   :placeholder="$t('cra.pflichtDokuPanel.referenzURLAdvisoryOderTicketNummer')" />
            <input v-model="upstreamForm.gemeldet_am" type="date" :title="$t('cra.pflichtDokuPanel.meldedatum')" />
            <input v-model="upstreamForm.begruendung"
                   :placeholder="$t('cra.pflichtDokuPanel.begrundungPflichtBeiNichtErforderlic')" />
            <button class="btn-primary" :disabled="upstreamBusy" @click="speichereUpstream">
              {{ $t('common.save') }}</button>
            <button class="btn-link" @click="upstreamForm = null">{{ $t('common.cancel') }}</button>
          </div>
        </div>
      </div>
    </details>

    <!-- C4: Support-Period -->
    <details ref="spSection" class="section">
      <summary><strong>{{ $t('cra.pflichtDokuPanel.c4SupportPeriod') }}</strong> {{ store.supportPeriod.eol_datum ? `bis ${store.supportPeriod.eol_datum}` : '' }}</summary>
      <div class="section-body">
        <div class="form-grid">
          <input v-model="store.supportPeriod.markteintritt_datum" type="date" />
          <input v-model.number="store.supportPeriod.support_jahre" type="number" :placeholder="$t('cra.pflichtDokuPanel.supportJahreCRADefault')" />
          <input v-model="store.supportPeriod.update_kanal" :placeholder="$t('cra.pflichtDokuPanel.phUpdateKanal')" />
          <textarea v-model="store.supportPeriod.rationale"
                    :placeholder="begruendungPlaceholder" rows="2" />
          <!-- #1209: Art. 13(16) Support-Ende beim Kauf sichtbar -->
          <input v-model="store.supportPeriod.support_end_kaufhinweis_url" :placeholder="$t('cra.pflichtDokuPanel.phSupportEndeKaufhinweis')" />
          <input v-model="store.supportPeriod.support_end_kaufhinweis_nachweis" :placeholder="$t('cra.pflichtDokuPanel.nachweisSupportEndeHinweisArt')" />
        </div>

        <!-- #1762: Zwei Kanäle, zwei Zusagen. Das Alt-Feld „Update-Kanal“ oben
             bleibt stehen (Bestandsdaten); getrennt ausgewiesen wird hier. -->
        <div class="zusagen">
          <p class="zusagen-titel">{{ $t('cra.pflichtDokuPanel.updateZusagenAnDenKunden') }}
            <span class="stelle-unsicher" :title="$t('cra.pflichtDokuPanel.dasIssueVerortetDieZusagenBeiArtAbsD')">{{ $t('cra.pflichtDokuPanel.artStelleNichtGepruft') }}</span>
          </p>
          <div class="form-grid">
            <input v-model="store.supportPeriod.sicherheitsupdate_kanal"
                   :placeholder="$t('cra.pflichtDokuPanel.kanalFurSicherheitsupdatesZBSecurity')" />
            <input v-model="store.supportPeriod.funktionsupdate_kanal"
                   :placeholder="$t('cra.pflichtDokuPanel.kanalFurFunktionsupdatesZBReleaseKan')" />
            <input v-model="store.supportPeriod.update_zusagen_nachweis"
                   :placeholder="$t('cra.pflichtDokuPanel.woStehenDieseZusagenURLDokument')" />
          </div>
          <label class="check">
            <input type="checkbox" v-model="store.supportPeriod.sicherheitsupdates_kostenlos" />
            {{ $t('cra.pflichtDokuPanel.sicherheitsupdatesWerdenImUnterstutz') }} <strong>kostenlos</strong> bereitgestellt
          </label>
          <label class="check">
            <input type="checkbox" v-model="store.supportPeriod.kanaele_getrennt" />
            {{ $t('cra.pflichtDokuPanel.sicherheitsupdatesSind') }} <strong>getrennt</strong> {{ $t('cra.pflichtDokuPanel.vonFunktionsupdatesBeziehbar') }}
          </label>
          <p class="hint">
            {{ $t('cra.pflichtDokuPanel.beidesSindZusagenAufDieSichDerKundeV') }}
          </p>
        </div>

        <button class="btn-primary" @click="speichereSupport">{{ $t('cra.pflichtDokuPanel.speichernEOLFristenWerdenBerechnet') }}</button>
        <p v-if="store.supportPeriodFehler" class="sp-fehler">
          {{ store.supportPeriodFehler }}
        </p>
        <p v-if="store.supportPeriod.eol_datum" class="hint">
          {{ $t('cra.pflichtDokuPanel.endOfSupport') }} <strong>{{ store.supportPeriod.eol_datum }}</strong>
        </p>

        <!-- #1762: Fristenlauf statt nur Datumsanzeige. Für Art. 14 gibt es eine
             Fristenuhr, hier bisher nicht — eine 2035 ablaufende Frist fiel
             niemandem auf. -->
        <div class="fristen">
          <p class="fristen-titel">{{ $t('cra.pflichtDokuPanel.fristenlauf') }}
            <span v-if="store.supportFristen.schlechteste_ampel"
                  :class="['ampel', `ampel-${store.supportFristen.schlechteste_ampel}`]">
              {{ ampelText(store.supportFristen.schlechteste_ampel) }}
            </span>
            <button class="btn-link" @click="store.fetchSupportFristen()">aktualisieren</button>
          </p>
          <p v-if="!store.supportFristen.berechenbar" class="hint">
            {{ $t('cra.pflichtDokuPanel.nochNichtBestimmbarOhneMarkteintritt') }}
          </p>
          <ul v-else class="retention-fristen">
            <li v-for="f in store.supportFristen.fristen" :key="f.key">
              <span :class="['ampel', `ampel-${f.ampel}`]">{{ ampelText(f.ampel) }}</span>
              {{ f.label }}:
              <strong>{{ f.datum || '—' }}</strong>
              <span v-if="f.tage_verbleibend !== null && f.tage_verbleibend >= 0"
                    class="hint"> {{ $t('cra.pflichtDokuPanel.v0Tage', { v0: f.tage_verbleibend }) }}</span>
              <span v-else-if="f.tage_verbleibend !== null" class="hint">
                {{ $t('cra.pflichtDokuPanel.seitV0TagenVerstrichen', { v0: -f.tage_verbleibend }) }}</span>
              <span class="ref">{{ f.ref }}</span>
            </li>
          </ul>
        </div>
      </div>
    </details>

    <!-- #1207: PSIRT-SLA-Tracking gegen offene CVEs -->
    <details class="section" @toggle="store.fetchSlaStatus()">
      <summary><strong>{{ $t('cra.pflichtDokuPanel.sLATrackingOffeneCVEs') }}</strong>
        <span v-if="store.slaStatus.violations" class="sla-badge violation">{{ $t('cra.pflichtDokuPanel.v0Uberfallig', { v0: store.slaStatus.violations }) }}</span>
        <span v-if="store.slaStatus.due_soon" class="sla-badge due">{{ $t('cra.pflichtDokuPanel.v0BaldFallig', { v0: store.slaStatus.due_soon }) }}</span>
      </summary>
      <div class="section-body">
        <button class="btn-secondary" @click="store.fetchSlaStatus()">{{ $t('common.aktualisieren3') }}</button>
        <p v-if="!store.slaStatus.psirt_set" class="hint">{{ $t('cra.pflichtDokuPanel.pSIRTSLAsNochNichtHinterlegtC2') }}</p>
        <table v-if="store.slaStatus.items?.length" class="sla-table">
          <thead><tr><th>{{ $t('cra.pflichtDokuPanel.cVE') }}</th><th>{{ $t('common.schwere') }}</th><th>{{ $t('cra.pflichtDokuPanel.sLA') }}</th><th>{{ $t('cra.pflichtDokuPanel.sollFix') }}</th><th>{{ $t('common.status') }}</th></tr></thead>
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
        <p v-else class="hint">{{ $t('cra.pflichtDokuPanel.keineOffenenCVEs') }}</p>
      </div>
    </details>

    <!-- C5: Threat-Model -->
    <details class="section">
      <summary><strong>{{ $t('cra.pflichtDokuPanel.c5ThreatModel') }}</strong> {{ store.threatModel.framework || '' }}</summary>
      <div class="section-body">
        <div class="form-grid">
          <select v-model="store.threatModel.framework">
            <option v-for="fw in THREAT_FRAMEWORKS" :key="fw.id" :value="fw.id">{{ fw.label }}</option>
          </select>
          <input v-model="store.threatModel.diagram_url" :placeholder="$t('cra.pflichtDokuPanel.phDiagramUrl')" />
          <textarea v-model="store.threatModel.scope" :placeholder="$t('cra.pflichtDokuPanel.scope')" rows="2" />
        </div>
        <p v-if="store.threatModel.framework_source === 'risk_link'" class="fw-hint fw-ok">
          {{ $t('cra.pflichtDokuPanel.frameworkAusVerknupfterRisikobewertu') }}
        </p>
        <p v-else-if="store.threatModel.framework_source === 'manual_override'" class="fw-hint fw-warn">
          {{ $t('cra.pflichtDokuPanel.manuellAbweichendVonDerRisikobewertu') }}
        </p>
        <button class="btn-primary" @click="store.saveThreatModel(store.threatModel)">{{ $t('common.save') }}</button>
      </div>
    </details>

    <!-- Risiken → Issue-Tracking (#1008) -->
    <details class="section">
      <summary><strong>{{ $t('cra.pflichtDokuPanel.risikenAmpIssueTracking') }}</strong>
        <span v-if="riskLinked">({{ risiken.length }})</span>
      </summary>
      <div class="section-body">
        <p v-if="!riskLinked" class="hint">
          {{ $t('cra.pflichtDokuPanel.keinRisikobewertungsProjektVerknupft') }}
        </p>
        <p v-else-if="!risiken.length" class="hint">{{ $t('cra.pflichtDokuPanel.keineRisikenImVerknupftenProjekt') }}</p>
        <table v-else>
          <thead>
            <tr><th>Nr</th><th>{{ $t('common.risiko') }}</th><th>{{ $t('cra.pflichtDokuPanel.wert') }}</th><th>{{ $t('cra.pflichtDokuPanel.label') }}</th><th>{{ $t('cra.pflichtDokuPanel.issues') }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in risiken" :key="r.id">
              <td>{{ r.nr }}</td>
              <td>{{ r.risk_name }}<span v-if="r.is_resolved" title="behoben"> ✓</span>
                <NeubewertungBadge :text="r.bewertung_text" modul="cra"
                                   :projekt="store.selectedProjekt" objekt-pfad="risiken"
                                   :objekt-id="r.id" @bestaetigt="loadRisiken()" /></td>
              <td>{{ r.risikowert ?? '—' }}</td>
              <td>{{ r.risiko_label || '—' }}</td>
              <!-- #1008/#1847: Pillen und Knöpfe lagen in zwei Zellen, obwohl
                   sie dieselbe Sache sind; der geteilte Baustein bringt beides
                   mit. Nachladen über `loadRisiken` ist Pflicht: Der Abgleich
                   schreibt „⚠️ Neubewertung erforderlich" in `bewertung_text`
                   (#1850), und der Badge in Spalte „Risiko" liest genau das. -->
              <td class="risk-actions">
                <IssueVerknuepfung
                  api-base="/cra"
                  :projekt-name="store.selectedProjekt || ''"
                  objekt-pfad="risiken"
                  :objekt-id="r.id"
                  :objekt-titel="`#${r.nr ?? r.id}`"
                  text-ziel="die Bemerkung"
                  darstellung="zeile"
                  @geaendert="loadRisiken()"
                  @uebernommen="loadRisiken()"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- Phase B — KI-Wizards: jetzt im eigenen Assistenten-Tab (S11 / #1081) -->
    <div class="assistenten-hint">
      <span>{{ $t('cra.pflichtDokuPanel.klassifikatorBranchenTemplatesUndPol') }}</span>
      <button class="btn-link assistenten-link" @click="emit('open-assistenten')">{{ $t('common.zumAssistenten') }}</button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCraStore } from '../../stores/cra'
import { THREAT_FRAMEWORKS } from './threatFrameworks'
import NeubewertungBadge from '../../components/shared/NeubewertungBadge.vue'
// #1847: Issue-Bedienung an Risiken und Schwachstellen — kompakte Zeilenform.
// `safeUrl` (#1175) braucht diese Datei nicht mehr selbst; der Baustein filtert
// die Issue-Links.
import IssueVerknuepfung from '../../components/shared/IssueVerknuepfung.vue'
import { t } from '../../i18n'

const store = useCraStore()

// #1207: Label für SLA-Status-Pille.
function slaLabel(s: string) {
  return ({ on_track: 'On Track', faellig: t('cra.pflichtDokuPanel.fallig'), ueberfaellig: t('cra.pflichtDokuPanel.uberfallig'),
    unbekannt: t('cra.pflichtDokuPanel.unbekannt') } as Record<string, string>)[s] || s
}

const emit = defineEmits<{
  /** Bittet den Host (CRAView), zum Assistenten-Tab zu wechseln (#1081). */
  (e: 'open-assistenten'): void
  /** Bittet den Host (CRAView), ins SBOM-Untermenü zu wechseln. */
  (e: 'open-sbom'): void
}>()

const vulnForm = ref({ cve_id: '', titel: '', schwere: 'unknown', cvss_score: 0, affected_component: '', fixed_in_version: '', status: 'open' })

// #1796: Die Spalte hält eine Liste, die Maske zeigt eine Zeile. Getippt wird
// ein String — `cra.psirt.normalisiere` trennt ihn serverseitig, damit die
// Lesart an **einer** Stelle liegt und nicht in jedem Formular neu entsteht.
const psirtKontakte = computed<string>({
  get: () => {
    const w = store.psirt?.psirt_contacts
    return Array.isArray(w) ? w.join(', ') : (w || '')
  },
  set: (wert: string) => { store.psirt.psirt_contacts = wert },
})

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
//
// Anlegen, Abgleichen, Übernehmen, Verknüpfen und Entknüpfen stecken seit
// #1847 in `IssueVerknuepfung`. Hier bleibt nur, was diese Maske wirklich
// kennt: welche Risiken es gibt. Die Issue-Liste holt der Baustein selbst —
// vorher lief dafür je Risiko eine eigene Abfrage aus dieser Datei.
const risiken = ref<any[]>([])
const riskLinked = ref(false)

const loadRisiken = async () => {
  if (!store.selectedProjekt) return
  const res = await store.fetchRisiken()
  riskLinked.value = !!res.linked
  risiken.value = res.risiken || []
}

onMounted(loadRisiken)
watch(() => store.selectedProjekt, loadRisiken)

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

/* Risiken → Issue (#1008). Pillen- und Knopf-Stile liegen seit #1847 im
   geteilten Baustein — hier bleibt nur die Zelle, die sie trägt. */
.risk-actions { white-space: nowrap; }
.btn-mini {
  font-size: 12px; padding: 3px 8px; margin-left: 4px; border-radius: 4px;
  border: 1px solid #1565c0; background: #fff; color: #1565c0; cursor: pointer;
}
.btn-mini:disabled { opacity: 0.5; cursor: default; }

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
.sbom-open { margin-top: 4px; }

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
