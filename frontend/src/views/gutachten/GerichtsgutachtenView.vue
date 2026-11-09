<template>
  <div class="gg-view">
    <div class="header">
      <h2>{{ $t('gutachten.gerichtsgutachtenView.gerichtsgutachtenBISGKonform') }}</h2>
      <p>{{ $t('gutachten.gerichtsgutachtenView.sachverstandigengutachtenNachDINENIS') }}</p>
      <ModuleHelpButton module="gutachten" class="header-help" />
    </div>

    <FehlerHinweis :text="store.error" @close="store.error = ''" />

    <!-- Projekt-Auswahl -->
    <div v-if="!aktuell && !creating" class="card">
      <h3>{{ $t('gutachten.gerichtsgutachtenView.verfahrenWahlen') }}</h3>
      <p v-if="store.projekte.length === 0">{{ $t('gutachten.gerichtsgutachtenView.nochKeineGerichtsgutachtenAngelegt') }}</p>
      <div v-else class="proj-list">
        <button v-for="p in store.projekte" :key="p.name" class="proj-tile" @click="selectProjekt(p.name)">
          <strong>{{ p.name }}</strong>
          <span class="proj-az">{{ p.aktenzeichen || '(ohne AZ)' }}</span>
          <span class="proj-status" :class="`status-${p.status}`">{{ p.status }}</span>
        </button>
      </div>
      <button class="btn-primary" @click="startNew">{{ $t('gutachten.gerichtsgutachtenView.neuesGerichtsgutachten') }}</button>

      <!-- #955/#957 Stammdaten & Vorlagen -->
      <details class="stammdaten-box" @toggle="onStammdatenOpen">
        <summary><strong>{{ $t('gutachten.gerichtsgutachtenView.stammdatenAmpVorlagen') }}</strong> {{ $t('gutachten.gerichtsgutachtenView.gutachterHilfspersonenWordVorlagen') }}</summary>

        <div class="sd-group">
          <h4>{{ $t('gutachten.gerichtsgutachtenView.gutachter') }}</h4>
          <div v-for="g in store.gutachter" :key="g.id" class="sd-row">
            <span>{{ g.name }} <small>{{ g.zertifizierung }}</small></span>
            <button class="btn-link" @click="store.deleteGutachter(g.id)">🗑</button>
          </div>
          <div class="sd-add">
            <input v-model="newGutachter.name" :placeholder="$t('common.name')" />
            <input v-model="newGutachter.zertifizierung" :placeholder="$t('gutachten.gerichtsgutachtenView.zertifizierung')" />
            <input v-model="newGutachter.email" :placeholder="$t('auth.email')" />
            <button class="btn-primary" :disabled="!newGutachter.name" @click="addGutachter">{{ $t('gutachten.gerichtsgutachtenView.gutachter2') }}</button>
          </div>
        </div>

        <div class="sd-group">
          <h4>{{ $t('gutachten.gerichtsgutachtenView.hilfspersonenAZPO') }}</h4>
          <div v-for="h in store.hilfspersonen" :key="h.id" class="sd-row">
            <span>{{ h.name }} <small>{{ h.rolle }}</small></span>
            <button class="btn-link" @click="store.deleteHilfsperson(h.id)">🗑</button>
          </div>
          <div class="sd-add">
            <input v-model="newHilfsperson.name" :placeholder="$t('common.name')" />
            <input v-model="newHilfsperson.rolle" :placeholder="$t('gutachten.gerichtsgutachtenView.rolleZBForensiker')" />
            <button class="btn-primary" :disabled="!newHilfsperson.name" @click="addHilfsperson">{{ $t('gutachten.gerichtsgutachtenView.hilfsperson') }}</button>
          </div>
        </div>

        <div class="sd-group">
          <h4>{{ $t('gutachten.gerichtsgutachtenView.wordVorlagen') }}
            <button class="btn-link" @click="openVarsHelp">{{ $t('gutachten.gerichtsgutachtenView.verfugbareVariablen') }}</button>
          </h4>
          <p class="hint">{{ $t('gutachten.gerichtsgutachtenView.fugeDieVariablenPlatzhalterZB') }} <code>[projekt.aktenzeichen]</code>{{ $t('gutachten.gerichtsgutachtenView.inDeinWordDokumentEinSieWerdenBeimEx') }}</p>
          <div v-for="t in store.templates" :key="t.id" class="sd-row">
            <span>{{ t.name }} <small>{{ t.gutachten_art }}</small>
              <strong v-if="t.ist_default" class="sd-default">{{ $t('gutachten.gerichtsgutachtenView.default') }}</strong>
            </span>
            <span>
              <button class="btn-link" @click="openMapping(t)">{{ $t('gutachten.gerichtsgutachtenView.felderZuordnen') }}</button>
              <button class="btn-link" v-if="!t.ist_default" @click="store.setDefaultTemplate(t.id, t.gutachten_art)">{{ $t('gutachten.gerichtsgutachtenView.default') }}</button>
              <button class="btn-link" @click="store.deleteTemplate(t.id)">🗑</button>
            </span>
          </div>
          <div class="sd-add">
            <input v-model="newTemplate.name" :placeholder="$t('gutachten.gerichtsgutachtenView.vorlagenName')" />
            <select v-model="newTemplate.art">
              <option value="beide">beide</option><option value="gericht">{{ $t('gutachten.gerichtsgutachtenView.gericht') }}</option><option value="privat">{{ $t('gutachten.gerichtsgutachtenView.privat') }}</option>
            </select>
            <input type="file" accept=".docx,.dotx" @change="onTemplateFile" />
            <button class="btn-primary" :disabled="!newTemplate.name || !newTemplate.file" @click="addTemplate">{{ $t('gutachten.gerichtsgutachtenView.hochladen') }}</button>
          </div>
          <p v-if="templateMsg" class="sd-msg">{{ templateMsg }}</p>
        </div>
      </details>
    </div>

    <!-- #962 Variablen-Hilfe (kopierbar) -->
    <div v-if="varsHelpOpen" class="modal-overlay" @click.self="varsHelpOpen = false">
      <div class="modal vars-modal">
        <h3>{{ $t('gutachten.gerichtsgutachtenView.verfugbareVariablenFurWordVorlagen') }}</h3>
        <p class="hint">{{ $t('gutachten.gerichtsgutachtenView.kopiereDiePlatzhalterInDeinWordDokum') }} <code>[befunde]</code>{{ $t('gutachten.gerichtsgutachtenView.fugenMehrereFormatierteAbsatzeEin') }} <code>[gutachten_volltext]</code> {{ $t('gutachten.gerichtsgutachtenView.denKomplettenInhalt') }}</p>

        <div class="vars-section">
          <div class="vars-head">
            <strong>{{ $t('gutachten.gerichtsgutachtenView.einfacheListe') }}</strong>
            <button class="btn-secondary" @click="copyVarsList">{{ $t('gutachten.gerichtsgutachtenView.listeKopieren') }}</button>
          </div>
          <pre class="vars-list">{{ varsListText }}</pre>
        </div>

        <div class="vars-section">
          <div class="vars-head">
            <strong>{{ $t('gutachten.gerichtsgutachtenView.tabelleMitErklarung') }}</strong>
            <button class="btn-secondary" @click="copyVarsTable">{{ $t('gutachten.gerichtsgutachtenView.tabelleKopieren') }}</button>
          </div>
          <table class="vars-table">
            <thead><tr><th>{{ $t('gutachten.gerichtsgutachtenView.variable') }}</th><th>{{ $t('common.typ') }}</th><th>{{ $t('common.description') }}</th></tr></thead>
            <tbody>
              <tr v-for="v in varsSchema" :key="v.key">
                <td><code>{{ v.token }}</code></td>
                <td>{{ v.typ }}</td>
                <td>{{ v.beschreibung }}<span v-if="v.pflicht" class="vars-req"> {{ $t('gutachten.gerichtsgutachtenView.pflicht') }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="varsCopyMsg" class="sd-msg">{{ varsCopyMsg }}</p>
        <div class="actions"><button class="btn-secondary" @click="varsHelpOpen = false">{{ $t('common.close') }}</button></div>
      </div>
    </div>

    <!-- #959 Mapping-Wizard -->
    <div v-if="mappingTpl" class="modal-overlay" @click.self="mappingTpl = null">
      <div class="modal mapping-modal">
        <h3>{{ $t('gutachten.gerichtsgutachtenView.felderZuordnenV0', { v0: mappingTpl.name }) }}</h3>
        <p class="hint">{{ $t('gutachten.gerichtsgutachtenView.ordneJedenPlatzhalterAusDerVorlageEi') }}</p>
        <p v-if="(mappingPlaceholders.length === 0)" class="sd-msg">
          {{ $t('common.keine') }} <code>{{ $t('gutachten.gerichtsgutachtenView.platzhalter') }}</code> {{ $t('gutachten.gerichtsgutachtenView.erkanntRealeVorlagenNutzenPlatzhalte') }} <code>{{ $t('gutachten.gerichtsgutachtenView.aktenzeichen') }}</code>{{ $t('gutachten.gerichtsgutachtenView.docxtplVorlagen') }} <code v-pre>{{ projekt.aktenzeichen }}</code>.
        </p>
        <div class="mapping-table">
          <div v-for="ph in mappingPlaceholders" :key="ph" class="mapping-row">
            <code class="mapping-token">{{ ph }}</code>
            <select v-model="mappingDraft[ph]">
              <option value="">{{ $t('gutachten.gerichtsgutachtenView.nichtAndern') }}</option>
              <option value="__empty__">{{ $t('gutachten.gerichtsgutachtenView.leerLassen') }}</option>
              <optgroup label="Datenfelder">
                <option v-for="v in mappingSchema" :key="v.key" :value="v.key">{{ v.key }} — {{ v.beschreibung }}</option>
              </optgroup>
              <option v-if="mappingDraft[ph] && !isKnownMapValue(mappingDraft[ph])" :value="mappingDraft[ph]">
                (auto) {{ mappingDraft[ph] }}
              </option>
            </select>
          </div>
        </div>
        <div class="actions">
          <button class="btn-secondary" @click="mappingTpl = null">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" @click="saveMapping">{{ $t('gutachten.gerichtsgutachtenView.zuordnungSpeichern') }}</button>
        </div>
        <p v-if="mappingMsg" class="sd-msg">{{ mappingMsg }}</p>
      </div>
    </div>

    <!-- Anlegen-Form -->
    <div v-else-if="creating" class="card">
      <h3>{{ $t('gutachten.gerichtsgutachtenView.neuesGutachtenAnlegen') }}</h3>

      <!-- #663 Toggle Gericht / Privat -->
      <div class="art-toggle">
        <label :class="['toggle-opt', { active: newForm.gutachten_art === 'gericht' }]">
          <input type="radio" value="gericht" v-model="newForm.gutachten_art" />
          ⚖ <strong>{{ $t('gutachten.gerichtsgutachtenView.gerichtsgutachten') }}</strong> {{ $t('gutachten.gerichtsgutachtenView.gerichtsbestelltMitBeweisbeschluss') }}
        </label>
        <label :class="['toggle-opt', { active: newForm.gutachten_art === 'privat' }]">
          <input type="radio" value="privat" v-model="newForm.gutachten_art" />
          📋 <strong>{{ $t('gutachten.gerichtsgutachtenView.privatgutachten') }}</strong> {{ $t('gutachten.gerichtsgutachtenView.mandantenAuftragKeinGericht') }}
        </label>
      </div>

      <p class="hint" v-if="newForm.gutachten_art === 'gericht'">
        {{ $t('gutachten.gerichtsgutachtenView.pflichtNameGerichtAktenzeichenSVName') }}
      </p>
      <p class="hint" v-else>
        {{ $t('gutachten.gerichtsgutachtenView.pflichtNameAuftraggeberAuftragsartSV') }}
      </p>

      <div class="form-grid">
        <label>{{ $t('gutachten.gerichtsgutachtenView.projektName') }} <input v-model="newForm.name"
               :placeholder="newForm.gutachten_art === 'gericht' ? 'z.B. GG-2026-007' : 'z.B. PG-2026-007'" />
          <span v-if="nameError" class="field-error">{{ nameError }}</span>
        </label>

        <!-- Gerichts-Felder -->
        <template v-if="newForm.gutachten_art === 'gericht'">
          <label>{{ $t('gutachten.gerichtsgutachtenView.gericht2') }} <input v-model="newForm.gericht" :placeholder="$t('gutachten.gerichtsgutachtenView.landgericht')" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.kammer') }} <input v-model="newForm.kammer" placeholder="3. Zivilkammer" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.aktenzeichen2') }} <input v-model="newForm.aktenzeichen" placeholder="X 0815/26" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.beweisbeschlussVom') }} <input v-model="newForm.beweisbeschluss_datum" placeholder="03.03.2026" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.klager') }} <input v-model="newForm.klaeger_name" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.anwaltKlager') }} <input v-model="newForm.klaeger_anwalt" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.beklagter') }} <input v-model="newForm.beklagter_name" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.anwaltBeklagter') }} <input v-model="newForm.beklagter_anwalt" /></label>
        </template>

        <!-- Privat-Felder -->
        <template v-else>
          <label>{{ $t('gutachten.gerichtsgutachtenView.auftraggeber') }} <input v-model="newForm.auftraggeber" :placeholder="$t('gutachten.gerichtsgutachtenView.aCMEGmbH')" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.auftragsArt') }}
            <select v-model="newForm.auftrags_art">
              <option value="">{{ $t('common.wahlen') }}</option>
              <option value="Beweissicherung">{{ $t('gutachten.gerichtsgutachtenView.beweissicherung') }}</option>
              <option value="Tauglichkeitsprüfung">{{ $t('gutachten.gerichtsgutachtenView.tauglichkeitsprufung') }}</option>
              <option value="Schaden-Gutachten">{{ $t('gutachten.gerichtsgutachtenView.schadenGutachten') }}</option>
              <option value="Wertgutachten">{{ $t('gutachten.gerichtsgutachtenView.wertgutachten') }}</option>
              <option value="Kaufberatung">{{ $t('gutachten.gerichtsgutachtenView.kaufberatung') }}</option>
              <option value="Sonstiges">{{ $t('common.sonstiges') }}</option>
            </select>
          </label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.auftragsDatum') }} <input v-model="newForm.auftrags_datum" placeholder="2026-05-27" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.auftragsNummer') }} <input v-model="newForm.auftrags_nummer" :placeholder="$t('gutachten.gerichtsgutachtenView.freierCode')" /></label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.honorarvereinbarung') }} <input v-model="newForm.honorarvereinbarung" placeholder="z.B. 650€ Tagessatz" /></label>
        </template>

        <!-- Gemeinsam -->
        <label>{{ $t('common.vertraulichkeit') }} <input v-model="newForm.vertraulichkeit" /></label>
        <label>{{ $t('gutachten.gerichtsgutachtenView.thema') }} <textarea v-model="newForm.thema" rows="2"></textarea></label>

        <label>{{ $t('gutachten.gerichtsgutachtenView.sVName') }} <input v-model="newForm.sv_name" /></label>
        <label>{{ $t('gutachten.gerichtsgutachtenView.sVZertifizierung') }} <input v-model="newForm.sv_zertifizierung" :placeholder="$t('gutachten.gerichtsgutachtenView.zertifizierterITSVBISG')" /></label>
        <label>{{ $t('gutachten.gerichtsgutachtenView.sVAnschrift') }} <input v-model="newForm.sv_anschrift" /></label>
        <label>{{ $t('gutachten.gerichtsgutachtenView.sVKontakt') }} <input v-model="newForm.sv_kontakt" /></label>
      </div>

      <!-- Befangenheits-Check (G0-9) inline -->
      <div v-if="befangCheckResult" class="befang-result" :class="`risiko-${befangCheckResult.risiko}`">
        <strong>{{ befangCheckResult.empfehlung.headline }}</strong>
        <p>{{ befangCheckResult.empfehlung.empfehlung }}</p>
        <ul v-if="befangCheckResult.treffer?.length">
          <li v-for="t in befangCheckResult.treffer" :key="`${t.typ}-${t.projekt_name}`">
            <strong>{{ t.risiko }}</strong> — {{ t.grund }}
          </li>
        </ul>
        <!-- #945: klarstellen, dass dies nur die automatische Namensprüfung ist -->
        <p class="befang-note">
          {{ $t('gutachten.gerichtsgutachtenView.iDiesIstEine') }} <strong>{{ $t('gutachten.gerichtsgutachtenView.automatischeNamensprufung') }}</strong> {{ $t('gutachten.gerichtsgutachtenView.aufVorbefassungDenVollstandigenBefan') }} <strong>{{ $t('gutachten.gerichtsgutachtenView.selbstcheck') }}</strong>.
        </p>
      </div>

      <div class="actions">
        <button class="btn-secondary" @click="cancelNew">{{ $t('common.cancel') }}</button>
        <button class="btn-link" :disabled="!befangReady" @click="runBefangCheck">{{ $t('gutachten.gerichtsgutachtenView.befangenheitsCheck') }}</button>
        <button class="btn-primary" :disabled="!validNewForm" @click="createProjekt">{{ $t('common.anlegen') }}</button>
      </div>
      <p v-if="!validNewForm" class="hint missing-hint">
        {{ $t('gutachten.gerichtsgutachtenView.nochErforderlich') }} <strong>{{ missingFields.join(', ') }}</strong>
      </p>
    </div>

    <!-- Editor -->
    <div v-else-if="aktuell" class="editor">
      <div class="editor-header">
        <h3>{{ aktuell.name }} <small>({{ aktuell.aktenzeichen }})</small></h3>
        <div class="header-actions">
          <button class="btn-link" @click="closeProjekt">{{ $t('gutachten.gerichtsgutachtenView.liste') }}</button>
          <button class="btn-secondary" @click="openPreview">{{ $t('gutachten.gerichtsgutachtenView.vorschau') }}</button>
          <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.wennAusEntfalltKapitelVIIIAsservaten')">
            <input type="checkbox" v-model="includeAnhang" /> {{ $t('gutachten.gerichtsgutachtenView.anhang') }}
          </label>
          <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.methodeWerkzeugBeiBefundenKapIVDruck')">
            <input type="checkbox" v-model="includeMethodeWerkzeug" /> {{ $t('gutachten.gerichtsgutachtenView.methodeWerkzeug') }}
          </label>
          <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.zwischenuberschriftenSollIstKausalit')">
            <input type="checkbox" v-model="includeBeurtSubheadings" /> {{ $t('gutachten.gerichtsgutachtenView.sollIstKausalitatTitel') }}
          </label>
          <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.datumDerVerfahrensereignisseKapIIIDr')">
            <input type="checkbox" v-model="includeVerfahrenDatum" /> {{ $t('gutachten.gerichtsgutachtenView.verfahrenDatum') }}
          </label>
          <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.glossarImAnhangDrucken')">
            <input type="checkbox" v-model="includeGlossar" /> {{ $t('gutachten.gerichtsgutachtenView.glossar') }}
          </label>
          <select v-model="exportTemplateId" class="tpl-select" :title="$t('gutachten.gerichtsgutachtenView.wordVorlageFurExport')">
            <option :value="null">{{ $t('gutachten.gerichtsgutachtenView.standardLayout') }}</option>
            <option v-for="t in store.templates" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
          <button class="btn-secondary" @click="exportDocx">{{ $t('gutachten.gerichtsgutachtenView.dOCX') }}</button>
          <button class="btn-secondary" @click="exportArchiv">{{ $t('gutachten.gerichtsgutachtenView.archivZIP') }}</button>
          <button class="btn-secondary" @click="deleteProjekt">🗑</button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button v-for="t in tabs" :key="t.id" class="tab" :class="{ active: tab === t.id }" @click="tab = t.id">
          {{ t.label }}
        </button>
      </div>

      <!-- Tab: Stammdaten -->
      <div v-if="tab === 'stammdaten'" class="tab-content">
        <div class="art-badge" :class="`art-${aktuell.gutachten_art || 'gericht'}`">
          {{ aktuell.gutachten_art === 'privat' ? $t('gutachten.gerichtsgutachtenView.privatgutachten2') : $t('gutachten.gerichtsgutachtenView.gerichtsgutachten2') }}
        </div>
        <!-- Phase H-A — Audit-Source-Banner (#681) -->
        <div v-if="auditSource && auditSource.audit_projekt" class="result-card status-ok" style="margin: 12px 0; border-left: 4px solid #1565c0;">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.ausComplianceAuditBerichtAbgeleitet') }}</strong>
          <ul style="margin: 8px 0; padding-left: 20px; font-size: 13px;">
            <li>{{ $t('gutachten.gerichtsgutachtenView.auditProjekt') }} <code>{{ auditSource.audit_projekt }}</code></li>
            <li>{{ $t('gutachten.gerichtsgutachtenView.auditDatumV0', { v0: (auditSource.audit_datum || '').slice(0, 10) }) }}</li>
            <li>{{ $t('gutachten.gerichtsgutachtenView.auditFirmaV0', { v0: auditSource.audit_firma }) }}</li>
            <li>Snapshot-SHA-256: <code style="font-size: 11px;">{{ (auditSource.snapshot_sha256 || '').slice(0, 24) }}…</code></li>
            <li>{{ $t('gutachten.gerichtsgutachtenView.konvertiertAmV0VonV1', { v0: (auditSource.konvertiert_am || '').slice(0, 16), v1: auditSource.konvertiert_von }) }}</li>
          </ul>
          <p style="font-size: 12px; color: #c62828;"><strong>{{ $t('gutachten.gerichtsgutachtenView.aZPO') }}</strong> {{ $t('gutachten.gerichtsgutachtenView.ubernommeneBefundSkeletonsSindLEERUn') }}</p>
        </div>
        <div class="form-grid">
          <template v-if="(aktuell.gutachten_art || 'gericht') === 'gericht'">
            <label>{{ $t('gutachten.gerichtsgutachtenView.gericht') }} <input v-model="aktuell.gericht" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.kammer') }} <input v-model="aktuell.kammer" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.aktenzeichen3') }} <input v-model="aktuell.aktenzeichen" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.beweisbeschlussVom') }} <input v-model="aktuell.beweisbeschluss_datum" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.klager') }} <input v-model="aktuell.klaeger_name" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.beklagter') }} <input v-model="aktuell.beklagter_name" /></label>
          </template>
          <template v-else>
            <label>{{ $t('gutachten.gerichtsgutachtenView.auftraggeber2') }} <input v-model="aktuell.auftraggeber" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.auftragsArt2') }} <input v-model="aktuell.auftrags_art" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.auftragsDatum') }} <input v-model="aktuell.auftrags_datum" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.auftragsNummer') }} <input v-model="aktuell.auftrags_nummer" /></label>
            <label>{{ $t('gutachten.gerichtsgutachtenView.honorarvereinbarung') }} <input v-model="aktuell.honorarvereinbarung" /></label>
          </template>
          <label>{{ $t('gutachten.gerichtsgutachtenView.thema') }} <textarea v-model="aktuell.thema" rows="2"></textarea></label>
          <label>{{ $t('common.vertraulichkeit') }}
            <input v-model="aktuell.vertraulichkeit" :disabled="!canEditDeckblatt" />
            <span v-if="!canEditDeckblatt" class="lock-hint">{{ $t('gutachten.gerichtsgutachtenView.nachV0Gesperrt', { v0: aktuell.status }) }}</span>
          </label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.sVName2') }} <input v-model="aktuell.sv_name" /></label>
          <label>{{ $t('common.status') }}
            <select v-model="aktuell.status">
              <option value="in_bearbeitung">{{ $t('gutachten.gerichtsgutachtenView.inBearbeitung') }}</option>
              <option value="finalisiert">{{ $t('gutachten.gerichtsgutachtenView.finalisiert') }}</option>
              <option value="eingereicht">{{ $t('gutachten.gerichtsgutachtenView.eingereicht') }}</option>
            </select>
          </label>
        </div>
        <button class="btn-primary" @click="saveStammdaten">{{ $t('common.save') }}</button>
      </div>

      <!-- Tab: Selbstcheck -->
      <div v-if="tab === 'selbstcheck'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.g2BefangenheitsSelbstcheckZPO') }}
          <button class="help-btn" @click="showHelp('selbstcheck.vorbefassung')" :title="$t('app.hilfe')">ℹ</button>
        </h4>
        <!-- #692 + #696 + #699 — Selbstcheck + EDITIERBARER Fließtext -->
        <div v-if="lastSelbstcheck" class="result-card status-ok" style="margin-bottom: 12px;">
          📌 <strong>{{ $t('gutachten.gerichtsgutachtenView.letzterSelbstcheck') }}</strong> {{ lastSelbstcheck.ereignis_datum }}
          <br/><small>{{ lastSelbstcheck.titel }}</small>
          <div class="fliesstext-block">
            <strong>{{ $t('gutachten.gerichtsgutachtenView.befangenheitsFliesstextGehtInDOCXKap') }}</strong>
            <textarea v-model="fliesstextEdit" rows="9" class="fliesstext-edit"
                      :placeholder="$t('gutachten.gerichtsgutachtenView.generiertenFliesstextHierBearbeiten')"></textarea>
            <div class="row" style="justify-content: flex-end; gap: 6px; margin-top: 6px;">
              <span v-if="fliesstextSaveStatus" class="hint" style="align-self: center;">{{ fliesstextSaveStatus }}</span>
              <button class="btn-link" @click="resetFliesstext">{{ $t('gutachten.gerichtsgutachtenView.originalWiederherstellen') }}</button>
              <button class="btn-primary" :disabled="!fliesstextEdit.trim()" @click="saveFliesstext">{{ $t('common.saveIcon') }}</button>
            </div>
          </div>
        </div>
        <div v-for="f in store.selbstcheckFragen" :key="f.key" class="check-row">
          <strong>{{ f.frage }}</strong>
          <div class="ja-nein">
            <label><input type="radio" :value="'ja'" v-model="selbstcheckAntw[f.key]" /> Ja</label>
            <label><input type="radio" :value="'nein'" v-model="selbstcheckAntw[f.key]" /> {{ $t('common.no') }}</label>
            <label><input type="radio" :value="'unklar'" v-model="selbstcheckAntw[f.key]" /> {{ $t('gutachten.gerichtsgutachtenView.unklar') }}</label>
          </div>
        </div>
        <button class="btn-primary" @click="runSelbstcheck">{{ $t('gutachten.gerichtsgutachtenView.auswerten') }}</button>
        <div v-if="selbstcheckResult" class="result-card" :class="`status-${selbstcheckResult.status}`">
          <strong>{{ selbstcheckResult.empfehlung.headline }}</strong>
          <p>{{ selbstcheckResult.empfehlung.empfehlung }}</p>
          <ul v-if="selbstcheckResult.issues?.length">
            <li v-for="i in selbstcheckResult.issues" :key="i.key">{{ i.level }}: {{ i.message }}</li>
          </ul>
        </div>
      </div>

      <!-- Tab: Beweisfragen -->
      <div v-if="tab === 'beweisfragen'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.iIBeweisfragen') }}</h4>
        <!-- Phase H-B — KI-Generator für Beweisfragen aus Audit-Quelle (#684) -->
        <div v-if="auditSource && auditSource.audit_projekt" class="add-form" style="background: #e3f2fd; border-left: 4px solid #1565c0; margin-bottom: 16px;">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.beweisfragenAusAuditQuelleGenerieren') }}</strong>
          <p class="hint">{{ $t('gutachten.gerichtsgutachtenView.lassChatGPTBeweisfragenAusDemAuditKo') }}</p>
          <div class="row" style="gap: 8px; flex-wrap: wrap;">
            <button class="btn-secondary" @click="generatePgQuestions">{{ $t('common.promptGenerieren') }}</button>
            <button v-if="pgQuestionsPrompt" class="btn-secondary" @click="copyToClipboard(pgQuestionsPrompt)">
              {{ kopiert ? $t('gutachten.gerichtsgutachtenView.kopiert') : $t('gutachten.gerichtsgutachtenView.kopieren') }}</button>
          </div>
          <textarea v-if="pgQuestionsPrompt" v-model="pgQuestionsPrompt" rows="8" style="width:100%; font-family: monospace; font-size: 11px;" readonly></textarea>
          <textarea v-if="pgQuestionsPrompt" v-model="pgQuestionsResponse" rows="6" style="width:100%; margin-top: 8px;"
                    :placeholder="$t('gutachten.gerichtsgutachtenView.chatGPTJSONAntwortHierEinfugen')"></textarea>
          <div v-if="pgQuestionsPrompt" class="row" style="justify-content: flex-end;">
            <button class="btn-primary" :disabled="!pgQuestionsResponse" @click="importPgQuestions">{{ $t('gutachten.gerichtsgutachtenView.antwortImportieren') }}</button>
          </div>
          <div v-if="pgQuestionsImportMsg" class="hint ok">{{ pgQuestionsImportMsg }}</div>
        </div>
        <!-- Phase H-C — Smart Suggestions (Top-3-Lows-Analyse, #688) -->
        <div v-if="auditSource && auditSource.audit_projekt" class="add-form" style="background: #f3e5f5; border-left: 4px solid #6a1b9a; margin-bottom: 16px;">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.smartSuggestionsZuTopAuditLows') }}</strong>
          <button class="btn-secondary" @click="generateSmartSuggestionsPrompt" style="margin-top: 6px;">{{ $t('gutachten.gerichtsgutachtenView.promptGenerieren') }}</button>
          <textarea v-if="smartPrompt" v-model="smartPrompt" rows="6" style="width:100%; font-family: monospace; font-size: 11px;" readonly></textarea>
          <textarea v-if="smartPrompt" v-model="smartResponse" rows="5" style="width:100%;"
                    :placeholder="$t('gutachten.gerichtsgutachtenView.chatGPTAntwortHierEinfugen')"></textarea>
          <button v-if="smartPrompt" class="btn-primary" :disabled="!smartResponse" @click="parseSmartSuggestions">{{ $t('gutachten.gerichtsgutachtenView.parsen') }}</button>
          <pre v-if="smartParsed" style="background:#fff;padding:8px;font-size:12px;">{{ JSON.stringify(smartParsed, null, 2) }}</pre>
        </div>
        <table class="tbl">
          <thead><tr><th>Nr</th><th>{{ $t('gutachten.gerichtsgutachtenView.frage') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.antwortKurz') }}</th><th>{{ $t('common.antwort') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="f in store.beweisfragen" :key="f.id">
              <td>{{ f.nr }}</td>
              <td>{{ f.frage_text }}</td>
              <td>{{ f.antwort_kurz }}</td>
              <td>{{ f.antwort_text }}</td>
              <td>
                <button class="btn-link" @click="editBF(f)" :title="$t('common.edit')">✏</button>
                <button class="btn-link" @click="store.deleteBeweisfrage(f.id, aktuell.name)" :title="$t('common.delete')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <!-- #691 BF-Felder größer + vertikal -->
        <div class="add-form column">
          <div class="row">
            <label style="width:80px;">Nr:
              <input v-model.number="newBF.nr" type="number" style="width:80px" />
            </label>
            <label style="flex:1;">{{ $t('gutachten.gerichtsgutachtenView.antwortKurz2') }}
              <select v-model="newBF.antwort_kurz" style="width:100%">
                <option value="">{{ $t('common.wahlen') }}</option>
                <option value="ja">{{ $t('gutachten.gerichtsgutachtenView.ja') }}</option>
                <option value="nein">{{ $t('cra.releasesPanel.nein') }}</option>
                <option value="teilweise">teilweise</option>
                <option value="non-liquet">non-liquet</option>
              </select>
            </label>
          </div>
          <label>{{ $t('gutachten.gerichtsgutachtenView.frageWortlichAusBeweisbeschluss') }}
            <textarea v-model="newBF.frage_text" rows="3"
                      :placeholder="$t('gutachten.gerichtsgutachtenView.zBWeistDasGelieferteSoftwaresystemEi')"
                      style="width:100%; resize:vertical;"></textarea>
          </label>
          <label>{{ $t('gutachten.gerichtsgutachtenView.antwortAusfuhrlichSatzeMitVerweisZuB') }}
            <textarea v-model="newBF.antwort_text" rows="4"
                      :placeholder="$t('gutachten.gerichtsgutachtenView.jaAusInformationstechnischerSichtWei')"
                      style="width:100%; resize:vertical;"></textarea>
          </label>
          <div class="row" style="justify-content: flex-end;">
            <button v-if="editId.bf" class="btn-secondary" @click="cancelEdit('bf')">{{ $t('common.cancel') }}</button>
            <button class="btn-primary" :disabled="!newBF.frage_text" @click="addBF">
              {{ editId.bf ? $t('gutachten.gerichtsgutachtenView.speichern') : $t('gutachten.gerichtsgutachtenView.hinzu') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Tab: Befunde -->
      <div v-if="tab === 'befunde'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.iVBefunderhebungNurTatsachen') }}
          <button class="help-btn" @click="showHelp('befund.intro')" :title="$t('app.hilfe')">ℹ</button>
        </h4>
        <table class="tbl">
          <thead><tr><th>Nr</th><th>{{ $t('common.titel') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.methode') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.werkzeug') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="b in store.befunde" :key="b.id" :class="{ nonliquet: b.non_liquet }">
              <td>{{ b.nr }}</td>
              <td>{{ b.titel }}</td>
              <td>{{ b.methode }}</td>
              <td>{{ b.werkzeug_name }} {{ b.werkzeug_version }}</td>
              <td>
                <button class="btn-link" @click="editBefund(b)" :title="$t('common.edit')">✏</button>
                <button class="btn-link" @click="store.deleteBefund(b.id, aktuell.name)" :title="$t('common.delete')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <input v-model="newBefund.nr" placeholder="Nr (z.B. 4.1)" />
          <input v-model="newBefund.titel" :placeholder="$t('common.titel')" />
          <div class="row">
            <select v-model="newBefund.methode" style="flex:1">
              <option value="">{{ $t('gutachten.gerichtsgutachtenView.methode2') }}</option>
              <option value="statisch">{{ $t('gutachten.gerichtsgutachtenView.statisch') }}</option>
              <option value="dynamisch">{{ $t('gutachten.gerichtsgutachtenView.dynamisch') }}</option>
              <option value="db">{{ $t('gutachten.gerichtsgutachtenView.db') }}</option>
              <option value="netzwerk">{{ $t('gutachten.gerichtsgutachtenView.netzwerk') }}</option>
              <option value="interview">{{ $t('gutachten.gerichtsgutachtenView.interview') }}</option>
              <option value="live-forensik">{{ $t('gutachten.gerichtsgutachtenView.liveForensik') }}</option>
            </select>
            <button class="help-btn" @click="showHelp('befund.methode')">ℹ</button>
          </div>
          <div class="row">
            <input v-model="newBefund.werkzeug_name" :placeholder="$t('gutachten.gerichtsgutachtenView.werkzeug')" style="flex:1" />
            <input v-model="newBefund.werkzeug_version" :placeholder="$t('common.version')" style="flex:1" />
            <button class="help-btn" @click="showHelp('befund.werkzeug')">ℹ</button>
          </div>
          <label>{{ $t('gutachten.gerichtsgutachtenView.beschreibungTatsachenOnly') }}</label>
          <RichEditor v-model="newBefund.beschreibung_text"
                      @update:modelValue="validateBefundLive" />
          <div v-if="befundLinterHints.length" class="linter-warn">
            ⚠ {{ befundLinterHints.length }} Linter-Hinweis(e):
            <ul><li v-for="h in befundLinterHints.slice(0,5)" :key="h.pos_start">
              <strong>{{ h.term }}</strong>: {{ h.vorschlag }}
            </li></ul>
          </div>
          <button v-if="editId.befund" class="btn-secondary" @click="cancelEdit('befund')">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!newBefund.titel" @click="addBefund">
            {{ editId.befund ? $t('gutachten.gerichtsgutachtenView.speichern') : $t('gutachten.gerichtsgutachtenView.hinzu') }}
          </button>
        </div>
      </div>

      <!-- Tab: Beurteilungen -->
      <div v-if="tab === 'beurteilungen'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.vTechnischeBeurteilung') }}
          <button class="help-btn" @click="showHelp('beurteilung.intro')" :title="$t('app.hilfe')">ℹ</button>
        </h4>
        <table class="tbl">
          <thead><tr><th>Nr</th><th>{{ $t('common.titel') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.norm') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.befunde') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="u in store.beurteilungen" :key="u.id" :class="{ nonliquet: u.non_liquet }">
              <td>{{ u.nr }}</td>
              <td>{{ u.titel }}</td>
              <td>{{ u.norm_referenz }}</td>
              <td>{{ (u.befund_ids || []).join(', ') }}</td>
              <td>
                <button class="btn-link" @click="editBeurt(u)" :title="$t('common.edit')">✏</button>
                <button class="btn-link" @click="store.deleteBeurteilung(u.id, aktuell.name)" :title="$t('common.delete')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div class="add-form column">
          <input v-model="newBeurt.nr" placeholder="Nr (z.B. 5.1)" />
          <input v-model="newBeurt.titel" :placeholder="$t('common.titel')" />
          <div class="row">
            <select v-model="newBeurt.norm_id" style="flex:1">
              <option value="">{{ $t('gutachten.gerichtsgutachtenView.normWahlen') }}</option>
              <option v-for="n in store.normen" :key="n.id" :value="n.id">{{ n.titel }}</option>
            </select>
            <button class="help-btn" @click="showHelp('beurteilung.norm_referenz')">ℹ</button>
          </div>
          <input v-model="newBeurt.norm_referenz" :placeholder="$t('gutachten.gerichtsgutachtenView.normReferenzZBISOIECFaultTolerance')" />
          <label>{{ $t('gutachten.gerichtsgutachtenView.befundIDsKommagetrennt') }}
            <input v-model="newBeurt.befund_ids_str" placeholder="z.B. 1,2" />
          </label>

          <!-- Rich-Text-Editoren für Soll/Ist/Kausalität/Würdigung (#674) -->
          <label>{{ $t('gutachten.gerichtsgutachtenView.sollWasDieNormVerlangt') }} <button class="help-btn" @click="showHelp('beurteilung.soll')">ℹ</button></label>
          <RichEditor v-model="newBeurt.soll_text" />
          <label>{{ $t('gutachten.gerichtsgutachtenView.istBefundVergleich') }} <button class="help-btn" @click="showHelp('beurteilung.ist')">ℹ</button></label>
          <RichEditor v-model="newBeurt.ist_text" />
          <label>{{ $t('gutachten.gerichtsgutachtenView.kausalitat') }} <button class="help-btn" @click="showHelp('beurteilung.kausalitaet')">ℹ</button></label>
          <RichEditor v-model="newBeurt.kausalitaet_text" />
          <label>{{ $t('gutachten.gerichtsgutachtenView.wurdigungJuraSperre') }} <button class="help-btn" @click="showHelp('beurteilung.wuerdigung')">ℹ</button></label>
          <RichEditor v-model="newBeurt.bewertung_text" />
          <div class="actions">
            <button class="btn-link" :disabled="!newBeurt.norm_id" @click="openBeurteilungsWizard">{{ $t('gutachten.gerichtsgutachtenView.kIVorschlagGenerieren') }}</button>
            <button v-if="editId.beurt" class="btn-secondary" @click="cancelEdit('beurt')">{{ $t('common.cancel') }}</button>
            <button class="btn-primary" :disabled="!newBeurt.titel" @click="addBeurteilung">
              {{ editId.beurt ? $t('gutachten.gerichtsgutachtenView.speichern') : $t('gutachten.gerichtsgutachtenView.hinzu') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Tab: Asservaten -->
      <div v-if="tab === 'assets'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.asservatenChainOfCustodyNachISOIEC') }}</h4>
        <table class="tbl">
          <thead><tr><th>{{ $t('gutachten.gerichtsgutachtenView.bezeichnung') }}</th><th>SHA-256</th><th>{{ $t('gutachten.gerichtsgutachtenView.akquisition') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.werkzeug') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in store.assets" :key="a.id">
              <td>{{ a.bezeichnung }}</td>
              <td><code class="hash">{{ (a.sha256 || '').slice(0, 16) }}…</code></td>
              <td>{{ a.akquisitions_utc }}</td>
              <td>{{ a.werkzeug_name }} {{ a.werkzeug_version }}</td>
              <td>
                <button class="btn-link" @click="editAsset(a)" :title="$t('common.edit')">✏</button>
                <a :href="`/api/gutachten/gerichts/assets/${a.id}/sicherungsprotokoll.pdf`"
                   target="_blank" rel="noopener noreferrer" class="btn-link" :title="$t('gutachten.gerichtsgutachtenView.sicherungsprotokoll')">📄</a>
                <button class="btn-link" @click="store.deleteAsset(a.id, aktuell.name)" :title="$t('common.delete')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <input v-model="newAsset.bezeichnung" :placeholder="$t('gutachten.gerichtsgutachtenView.bezeichnung')" />
          <input type="file" @change="onAssetFile" />
          <div v-if="newAsset.sha256" class="sha-display">SHA-256: <code>{{ newAsset.sha256 }}</code></div>
          <input v-model="newAsset.akquisitions_utc" placeholder="UTC (YYYY-MM-DDTHH:MM:SSZ)" />
          <input v-model="newAsset.akquisitions_ort" :placeholder="$t('gutachten.gerichtsgutachtenView.ort')" />
          <input v-model="newAsset.werkzeug_name" :placeholder="$t('gutachten.gerichtsgutachtenView.werkzeug')" />
          <input v-model="newAsset.werkzeug_version" :placeholder="$t('common.version')" />
          <input v-model="newAsset.gegengezeichnet_von" :placeholder="$t('gutachten.gerichtsgutachtenView.gegengezeichnetVon')" />
          <button v-if="editId.asset" class="btn-secondary" @click="cancelEdit('asset')">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!newAsset.bezeichnung || !newAsset.sha256" @click="addAsset">
            {{ editId.asset ? $t('gutachten.gerichtsgutachtenView.speichern') : $t('gutachten.gerichtsgutachtenView.hinzu') }}
          </button>
        </div>
      </div>

      <!-- Tab: Verfahren -->
      <div v-if="tab === 'verfahren'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.iIIVerfahrensgangSymmetrieCheck') }}</h4>
        <button class="btn-secondary" @click="runSymmetrieCheck">{{ $t('gutachten.gerichtsgutachtenView.symmetriePrufen') }}</button>
        <div v-if="symResult" :class="['result-card', symResult.ok ? 'status-ok' : 'status-blockiert']">
          <strong v-if="symResult.ok">{{ $t('gutachten.gerichtsgutachtenView.alleV0ParteikommunikationenSymmetris', { v0: symResult.kommunikationen_anzahl }) }}</strong>
          <strong v-else>{{ $t('gutachten.gerichtsgutachtenView.v0Symmetrieverletzungen', { v0: symResult.verletzungen.length }) }}</strong>
          <ul v-if="symResult.verletzungen?.length">
            <li v-for="v in symResult.verletzungen" :key="v.ereignis_id">
              {{ v.datum }} — {{ v.titel }} (fehlt: {{ v.fehlend.join(', ') }})
            </li>
          </ul>
        </div>
        <table class="tbl">
          <thead><tr><th>{{ $t('common.date') }}</th><th>{{ $t('common.typ') }}</th><th>{{ $t('common.titel') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.empfanger') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="(e, i) in store.verfahrensereignisse" :key="e.id">
              <td>{{ (e.ereignis_datum || '').slice(0, 16) }}</td>
              <td>{{ e.ereignis_typ }}</td>
              <td>{{ e.titel }}</td>
              <td>{{ (e.empfaenger || []).join(', ') }}</td>
              <td>
                <button class="btn-link" :disabled="i === 0" @click="moveVerf(i, -1)" :title="$t('gutachten.gerichtsgutachtenView.nachOben')">▲</button>
                <button class="btn-link" :disabled="i === store.verfahrensereignisse.length - 1" @click="moveVerf(i, 1)" :title="$t('gutachten.gerichtsgutachtenView.nachUnten')">▼</button>
                <button class="btn-link" @click="editVerf(e)" :title="$t('common.edit')">✏</button>
                <button class="btn-link" @click="deleteVerf(e.id)" :title="$t('common.delete')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <label>{{ $t('common.date') }} <input type="date" v-model="newVerf.ereignis_datum" /></label>
          <select v-model="newVerf.ereignis_typ">
            <option value="">{{ $t('gutachten.gerichtsgutachtenView.typ') }}</option>
            <option v-for="t in ereignisTypen" :key="t" :value="t">{{ t }}</option>
          </select>
          <input v-model="newVerf.titel" :placeholder="$t('common.titel')" />
          <textarea v-model="newVerf.beschreibung" :placeholder="$t('common.description')" rows="2"></textarea>
          <label>{{ $t('gutachten.gerichtsgutachtenView.empfanger') }}
            <div>
              <label><input type="checkbox" v-model="newVerfEmp.klaeger" /> {{ $t('gutachten.gerichtsgutachtenView.klager') }}</label>
              <label><input type="checkbox" v-model="newVerfEmp.beklagter" /> {{ $t('gutachten.gerichtsgutachtenView.beklagter') }}</label>
              <label><input type="checkbox" v-model="newVerfEmp.gericht" /> {{ $t('gutachten.gerichtsgutachtenView.gericht') }}</label>
            </div>
          </label>
          <button v-if="editId.verf" class="btn-secondary" @click="cancelEdit('verf')">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!newVerf.titel" @click="addVerf">
            {{ editId.verf ? $t('gutachten.gerichtsgutachtenView.speichern') : $t('gutachten.gerichtsgutachtenView.hinzu') }}
          </button>
        </div>
      </div>

      <!-- Tab: Honorar -->
      <div v-if="tab === 'honorar'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.g0HonorarTrackerZeitbuch') }}</h4>
        <div v-if="store.honorarSummary" class="hon-summary">
          <span>📊 {{ store.honorarSummary.total_stunden }}h</span>
          <span>{{ $t('gutachten.gerichtsgutachtenView.honorarV0', { v0: store.honorarSummary.honorar_eur }) }}</span>
          <span>{{ $t('gutachten.gerichtsgutachtenView.auslagenV0', { v0: store.honorarSummary.auslagen_eur }) }}</span>
          <span>{{ $t('gutachten.gerichtsgutachtenView.offenV0', { v0: store.honorarSummary.offen_eur }) }}</span>
        </div>
        <a :href="`/api/gutachten/gerichts/${encodeURIComponent(aktuell.name)}/rechnung.pdf?auftraggeber=${encodeURIComponent(aktuell.gericht)}`"
           target="_blank" rel="noopener noreferrer" class="btn-secondary">{{ $t('gutachten.gerichtsgutachtenView.rechnungPDF') }}</a>
        <table class="tbl">
          <thead><tr><th>{{ $t('common.date') }}</th><th>{{ $t('common.kategorie') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.min') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.satz') }}</th><th>{{ $t('common.description') }}</th></tr></thead>
          <tbody>
            <tr v-for="e in store.honorarEintraege" :key="e.id">
              <td>{{ (e.datum || '').slice(0, 10) }}</td>
              <td>{{ e.kategorie }}</td>
              <td>{{ e.dauer_minuten }}</td>
              <td>{{ e.stundensatz_eur }}€</td>
              <td>{{ e.beschreibung }}</td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <select v-model="newHon.kategorie">
            <option v-for="k in ['aktenstudium','asservaten','labor','bericht','kommunikation','ortstermin','fortbildung','sonstiges']" :key="k" :value="k">{{ k }}</option>
          </select>
          <input v-model.number="newHon.dauer_minuten" type="number" :placeholder="$t('gutachten.gerichtsgutachtenView.dauerMin')" />
          <input v-model.number="newHon.stundensatz_eur" type="number" step="5" :placeholder="$t('gutachten.gerichtsgutachtenView.stundensatz')" />
          <input v-model="newHon.beschreibung" :placeholder="$t('common.description')" />
          <button class="btn-primary" :disabled="!newHon.dauer_minuten" @click="addHon">{{ $t('gutachten.gerichtsgutachtenView.eintrag') }}</button>
        </div>
      </div>

      <!-- Tab: Forensik (G4) -->
      <div v-if="tab === 'forensik'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.g4ForensikWerkzeuge') }}</h4>

        <!-- G4-2 Werkzeug-Validator -->
        <div class="sub-card">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.werkzeugValidatorG4') }}</strong>
          <button class="btn-link" @click="runToolValidator">{{ $t('gutachten.gerichtsgutachtenView.prufen') }}</button>
          <div v-if="store.werkzeugValidator">
            <div :class="['result-card', store.werkzeugValidator.ok ? 'status-ok' : 'status-blockiert']">
              <strong v-if="store.werkzeugValidator.ok">{{ $t('gutachten.gerichtsgutachtenView.alleWerkzeugeImRegister') }}</strong>
              <strong v-else>⚠ {{ store.werkzeugValidator.unknown_tools.length }} Werkzeug(e) nicht im SV-Register</strong>
            </div>
            <ul v-if="store.werkzeugValidator.unknown_tools?.length">
              <li v-for="t in store.werkzeugValidator.unknown_tools" :key="t.befund_id">
                {{ $t('gutachten.gerichtsgutachtenView.befundV0', { v0: t.befund_nr }) }} <code>{{ t.tool_name }} {{ t.tool_version }}</code>
              </li>
            </ul>
          </div>
        </div>

        <!-- G4-3 MACB-Timeline -->
        <div class="sub-card">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.mACBZeitstempelTabelleG4') }}</strong>
          <table class="tbl">
            <thead><tr><th>{{ $t('gutachten.gerichtsgutachtenView.datei') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.modified') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.accessed') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.changed') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.born') }}</th><th></th></tr></thead>
            <tbody>
              <tr v-for="m in store.macbEintraege" :key="m.id" :class="{ 'risk-row': m.timestomping_risk }">
                <td>{{ m.datei_pfad }}</td>
                <td>{{ m.modified_at }}</td>
                <td>{{ m.accessed_at }}</td>
                <td>{{ m.changed_at }}</td>
                <td>{{ m.born_at }}</td>
                <td>
                  <span v-if="m.timestomping_risk" class="risk-badge">{{ $t('gutachten.gerichtsgutachtenView.timestomping') }}</span>
                  <button class="btn-link" @click="editMacb(m)" :title="$t('common.edit')">✏</button>
                  <button class="btn-link" @click="store.deleteMacb(m.id, aktuell.name)" :title="$t('common.delete')">🗑</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="add-form">
            <input v-model="newMacb.datei_pfad" :placeholder="$t('gutachten.gerichtsgutachtenView.pfad')" style="flex:2" />
            <input v-model="newMacb.modified_at" placeholder="M" />
            <input v-model="newMacb.accessed_at" placeholder="A" />
            <input v-model="newMacb.changed_at" placeholder="C" />
            <input v-model="newMacb.born_at" placeholder="B" />
            <button v-if="editId.macb" class="btn-secondary" @click="cancelEdit('macb')">{{ $t('common.cancel') }}</button>
            <button class="btn-primary" :disabled="!newMacb.datei_pfad" @click="addMacb">
              {{ editId.macb ? $t('gutachten.gerichtsgutachtenView.speichern') : $t('gutachten.gerichtsgutachtenView.hinzu') }}
            </button>
          </div>
        </div>

        <!-- G4-4 Volatility-Checklist -->
        <div class="sub-card">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.orderOfVolatilityG4') }}</strong>
          <p class="hint">{{ $t('gutachten.gerichtsgutachtenView.pflichtBeiMethodeLiveForensikReihenf') }}</p>
          <ol>
            <li v-for="v in store.volatilityChecklist" :key="v.key">
              <strong>{{ v.reihenfolge }}.</strong> {{ v.name }}
            </li>
          </ol>
        </div>

        <!-- G4-5 Log-Klassifikator -->
        <div class="sub-card">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.logKlassifikatorG4') }}</strong>
          <input type="file" @change="onLogClassify" />
          <div v-if="logClassResult" :class="`log-class log-${logClassResult.klasse}`">
            <code>{{ logClassResult.filename }}</code> → <strong>{{ logClassResult.klasse }}</strong>
          </div>
        </div>
      </div>

      <!-- Tab: Hypothesen-Tree (G6-1) + Drittgutachter (G6-2) -->
      <div v-if="tab === 'hypothesen'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.g6HypothesenTreeAlternativeErklarung') }}</h4>
        <table class="tbl">
          <thead><tr><th>{{ $t('gutachten.gerichtsgutachtenView.beurteilungID') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.hypothese') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('common.begruendung') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="h in store.hypothesen" :key="h.id" :class="`hyp-${h.status}`">
              <td>{{ h.beurteilung_id }}</td>
              <td>{{ h.hypothese_text }}</td>
              <td>
                <select :value="h.status" @change="updateHyp(h, ($event.target as HTMLSelectElement).value)">
                  <option value="offen">{{ $t('cra.pflichtDokuPanel.offen') }}</option>
                  <option value="verworfen">verworfen</option>
                  <option value="akzeptiert">akzeptiert</option>
                </select>
              </td>
              <td>{{ h.begruendung }}</td>
              <td>
                <button class="btn-link" @click="editHyp(h)" :title="$t('common.edit')">✏</button>
                <button class="btn-link" @click="store.deleteHypothese(h.id, aktuell.name)" :title="$t('common.delete')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <select v-model.number="newHyp.beurteilung_id">
            <option v-for="u in store.beurteilungen" :key="u.id" :value="u.id">{{ u.nr }} {{ u.titel }}</option>
          </select>
          <input v-model="newHyp.hypothese_text" :placeholder="$t('gutachten.gerichtsgutachtenView.alternativeErklarung')" />
          <select v-model="newHyp.status">
            <option value="offen">{{ $t('cra.pflichtDokuPanel.offen') }}</option>
            <option value="verworfen">verworfen</option>
            <option value="akzeptiert">akzeptiert</option>
          </select>
          <input v-model="newHyp.begruendung" :placeholder="$t('gutachten.gerichtsgutachtenView.begrundungWarumVerworfenAkzeptiert')" />
          <button v-if="editId.hyp" class="btn-secondary" @click="cancelEdit('hyp')">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!newHyp.hypothese_text" @click="addHyp">
            {{ editId.hyp ? $t('gutachten.gerichtsgutachtenView.speichern') : $t('gutachten.gerichtsgutachtenView.hinzu') }}
          </button>
        </div>

        <h4 style="margin-top: 24px">{{ $t('gutachten.gerichtsgutachtenView.g6DrittgutachterSimulatorDINEN') }}</h4>
        <div class="add-form">
          <select v-model.number="drittBefundId">
            <option v-for="b in store.befunde" :key="b.id" :value="b.id">{{ b.nr }} {{ b.titel }}</option>
          </select>
          <button class="btn-primary" :disabled="!drittBefundId" @click="openDrittPrompt">{{ $t('gutachten.gerichtsgutachtenView.promptFurReproduktionsanleitung') }}</button>
        </div>
        <!-- #1838: Hier landet die Antwort jetzt. Vorher gab es für sie keine
             Anzeige — `selbst_audit` im Backend hatte überhaupt keinen
             Aufrufer, und die Anleitung wurde als Beurteilung gespeichert. -->
        <FehlerHinweis v-if="drittFehler" :text="drittFehler" @close="drittFehler = ''" />
        <div v-if="drittResult"
             :class="['result-card', drittResult.drittgutachter_tauglich ? 'status-ok' : 'status-blockiert']">
          <strong v-if="drittResult.drittgutachter_tauglich">
            ✓ Drittgutachter-tauglich ({{ drittResult.score }}/{{ drittResult.max_score }} Kriterien)
          </strong>
          <strong v-else>
            {{ $t('gutachten.gerichtsgutachtenView.nochNichtDrittgutachterTauglichV0V1K', { v0: drittResult.score, v1: drittResult.max_score }) }}
          </strong>
          <ul>
            <li v-for="(erfuellt, name) in drittResult.checks" :key="name">
              {{ erfuellt ? '✓' : '✗' }} {{ DRITT_LABELS[name] || name }}
            </li>
          </ul>
          <template v-if="drittResult.anleitung">
            <p v-if="drittResult.anleitung.reproduzierbarkeits_bewertung">
              <strong>{{ $t('gutachten.gerichtsgutachtenView.reproduzierbarkeit') }}</strong>
              {{ drittResult.anleitung.reproduzierbarkeits_bewertung }}
            </p>
            <ol v-if="drittResult.anleitung.schritte?.length">
              <li v-for="(sch, i) in drittResult.anleitung.schritte" :key="i">{{ sch }}</li>
            </ol>
            <p v-if="drittResult.anleitung.erwartetes_ergebnis">
              <strong>{{ $t('gutachten.gerichtsgutachtenView.erwartetesErgebnis') }}</strong> {{ drittResult.anleitung.erwartetes_ergebnis }}
            </p>
          </template>
          <p class="llm-disclaimer">{{ KI_VORBEHALT }}</p>
        </div>

        <h4 style="margin-top: 24px">{{ $t('gutachten.gerichtsgutachtenView.g6CrossReferenceLinter') }}</h4>
        <button class="btn-secondary" @click="runCrossRef">{{ $t('gutachten.gerichtsgutachtenView.strukturPrufen') }}</button>
        <div v-if="crossRefResult" :class="['result-card', crossRefResult.ok ? 'status-ok' : 'status-blockiert']">
          <strong v-if="crossRefResult.ok">{{ $t('gutachten.gerichtsgutachtenView.strukturSauber') }}</strong>
          <strong v-else>{{ $t('gutachten.gerichtsgutachtenView.v0FehlerV1Warnungen', { v0: crossRefResult.errors.length, v1: crossRefResult.warnings.length }) }}</strong>
          <ul><li v-for="(h, i) in crossRefResult.hints" :key="i">
            <strong>{{ h.level }}</strong>: {{ h.message }}
          </li></ul>
        </div>
      </div>

      <!-- Tab: Peer-Review + Aufbewahrung -->
      <div v-if="tab === 'peer'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.g5PeerReview') }}</h4>
        <div class="add-form">
          <input v-model="newReviewer" :placeholder="$t('gutachten.gerichtsgutachtenView.reviewerName')" />
          <button class="btn-primary" :disabled="!newReviewer" @click="requestPeer">{{ $t('gutachten.gerichtsgutachtenView.reviewAnfordern') }}</button>
        </div>
        <div v-for="r in store.peerReviews" :key="r.id" class="sub-card">
          <strong>{{ r.reviewer_name }}</strong>
          <span :class="`status-${r.status}`" class="status-badge">{{ r.status }}</span>
          <span class="hint">angefordert: {{ r.angefordert_am }}</span>
          <button v-if="r.status !== 'abgeschlossen'" class="btn-link" @click="closePeerReview(r.id)">{{ $t('gutachten.gerichtsgutachtenView.abschliessen') }}</button>
          <ul>
            <li v-for="(k, i) in r.kommentare" :key="i">
              <strong>{{ k.kapitel }}</strong> ({{ k.author }}): {{ k.text }}
            </li>
          </ul>
          <div v-if="r.status !== 'abgeschlossen'" class="add-form">
            <input v-model="peerKomm[r.id].kapitel" :placeholder="$t('gutachten.gerichtsgutachtenView.kapitelIIIVVVI')" style="width:140px" />
            <input v-model="peerKomm[r.id].text" :placeholder="$t('common.kommentar')" style="flex:1" />
            <input v-model="peerKomm[r.id].author" :placeholder="$t('gutachten.gerichtsgutachtenView.author')" style="width:160px" />
            <button class="btn-primary" :disabled="!peerKomm[r.id].text" @click="addKomm(r.id)">{{ $t('gutachten.gerichtsgutachtenView.kommentar') }}</button>
          </div>
        </div>

        <h4 style="margin-top: 24px">{{ $t('gutachten.gerichtsgutachtenView.g5JahreAufbewahrung') }}</h4>
        <div v-if="store.aufbewahrung">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.archivBis') }}</strong> {{ $t('gutachten.gerichtsgutachtenView.v0V1TageVerbleibend', { v0: store.aufbewahrung.archiv_bis_datum, v1: store.aufbewahrung.tage_verbleibend }) }}
        </div>
        <button class="btn-secondary" @click="setAufbew">{{ $t('gutachten.gerichtsgutachtenView.jahreAktivieren') }}</button>

        <h4 style="margin-top: 24px">{{ $t('gutachten.gerichtsgutachtenView.g6AnonymisierteVorschau') }}</h4>
        <button class="btn-secondary" @click="loadAnon">{{ $t('gutachten.gerichtsgutachtenView.anonymisieren') }}</button>
        <pre v-if="anonResult" class="mono" style="max-height:400px; overflow:auto; background:#f5f5f5; padding:8px">{{ JSON.stringify(anonResult, null, 2) }}</pre>
      </div>

      <!-- Tab: Validator -->
      <div v-if="tab === 'validator'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.g5PreExportValidatorSprachLinter') }}</h4>
        <div class="row">
          <button class="btn-primary" @click="runValidator">{{ $t('gutachten.gerichtsgutachtenView.validatorAusfuhren') }}</button>
          <button class="btn-secondary" @click="openPreview">{{ $t('gutachten.gerichtsgutachtenView.dOCXVorschau') }}</button>
        </div>
        <div v-if="validatorResult">
          <div :class="['result-card', validatorResult.release_ready ? 'status-ok' : 'status-blockiert']">
            <strong v-if="validatorResult.release_ready">{{ $t('gutachten.gerichtsgutachtenView.releaseReady') }}</strong>
            <strong v-else>{{ $t('gutachten.gerichtsgutachtenView.nICHTReleaseReadyV0Fehler', { v0: validatorResult.errors_count }) }}</strong>
            <span> {{ $t('gutachten.gerichtsgutachtenView.v0SprachWarnungen', { v0: validatorResult.warnings_count }) }}</span>
          </div>
          <!-- #693 nur sichtbar wenn Inhalt -->
          <div v-if="!validatorResult.errors?.length && !validatorResult.sprach_warnings?.length"
               class="status-ok" style="padding:12px; margin-top:8px; border-radius:4px;">
            {{ $t('gutachten.gerichtsgutachtenView.keineFehlerKeineSprachWarnungenAlles') }}
          </div>
          <div v-if="validatorResult.errors?.length">
            <h5>{{ $t('gutachten.gerichtsgutachtenView.errorsV0', { v0: validatorResult.errors.length }) }}</h5>
            <ul><li v-for="(e, i) in validatorResult.errors" :key="i">{{ e.message }}</li></ul>
          </div>
          <div v-if="validatorResult.sprach_warnings?.length">
            <h5>{{ $t('gutachten.gerichtsgutachtenView.sprachWarnungenV0', { v0: validatorResult.sprach_warnings.length }) }}</h5>
            <ul><li v-for="(w, i) in validatorResult.sprach_warnings.slice(0, 30)" :key="i">
              <strong>{{ w.scope }}</strong> — <em>{{ w.term }}</em>: {{ w.vorschlag }}
            </li></ul>
          </div>
        </div>
      </div>

      <!-- Tab: Glossar (#983/#984) -->
      <div v-if="tab === 'glossar'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.glossarFachbegriffeAmpNormenAnhang') }}</h4>
        <p class="hint">{{ $t('gutachten.gerichtsgutachtenView.wirdBeimExportImAnhangAlphabetischAu') }}</p>
        <div class="row">
          <button class="btn-primary" @click="genGlossar">{{ $t('gutachten.gerichtsgutachtenView.automatischErstellen') }}</button>
          <span v-if="glossarMsg" class="sd-msg">{{ glossarMsg }}</span>
        </div>
        <table class="tbl">
          <thead><tr><th>{{ $t('gutachten.gerichtsgutachtenView.begriff') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.erklarung') }}</th><th>{{ $t('common.typ') }}</th><th>{{ $t('common.quelle') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="g in store.glossar" :key="g.id">
              <td><input v-model="g.begriff" @change="updGlossar(g)" /></td>
              <td><textarea v-model="g.erklaerung" rows="2" @change="updGlossar(g)"></textarea></td>
              <td>{{ g.typ }}</td>
              <td><small>{{ g.quelle }}</small></td>
              <td><button class="btn-link" @click="store.deleteGlossarEntry(aktuell.name, g.id)" :title="$t('common.delete')">🗑</button></td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <input v-model="newGloss.begriff" :placeholder="$t('gutachten.gerichtsgutachtenView.begriff2')" />
          <textarea v-model="newGloss.erklaerung" :placeholder="$t('gutachten.gerichtsgutachtenView.erklarung')" rows="2"></textarea>
          <button class="btn-primary" :disabled="!newGloss.begriff" @click="addGlossar">{{ $t('gutachten.gerichtsgutachtenView.eintrag') }}</button>
        </div>
      </div>

      <!-- Tab: Final-Archiv (#969) -->
      <div v-if="tab === 'finalarchiv'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.finalArchivUnveranderlichGesicherteE') }}</h4>
        <p class="hint">{{ $t('gutachten.gerichtsgutachtenView.ladeDieFinalKorrigierteEndfassungDOC') }}</p>
        <div class="sd-add">
          <input type="file" accept=".docx,.pdf" @change="onFinalFile" />
          <input v-model="finalBemerkung" :placeholder="$t('gutachten.gerichtsgutachtenView.bemerkungOptional')" />
          <button class="btn-primary" :disabled="!finalFile" @click="uploadFinal">{{ $t('gutachten.gerichtsgutachtenView.hochladen') }}</button>
        </div>
        <p v-if="finalMsg" class="sd-msg">{{ finalMsg }}</p>
        <table class="vuln-table" v-if="store.finalExports.length">
          <thead><tr><th>{{ $t('gutachten.gerichtsgutachtenView.hochgeladen') }}</th><th>{{ $t('common.format') }}</th><th>SHA-256</th><th>{{ $t('gutachten.gerichtsgutachtenView.von') }}</th><th>{{ $t('common.status') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="fe in store.finalExports" :key="fe.id" :style="fe.deleted ? 'opacity:.55' : ''">
              <td>{{ (fe.hochgeladen_am || '').slice(0,16) }}</td>
              <td>{{ fe.format }}</td>
              <td><code>{{ (fe.sha256 || '').slice(0,12) }}…</code></td>
              <td>{{ fe.hochgeladen_von }}</td>
              <td>
                <span v-if="fe.deleted" class="sync-hc">{{ $t('gutachten.gerichtsgutachtenView.geloschtV0', { v0: (fe.deleted_at||'').slice(0,10) }) }}</span>
                <span v-else>aktiv</span>
              </td>
              <td>
                <button v-if="!fe.deleted" class="btn-link" @click="store.downloadFinalExport(aktuell.name, fe.id, fe.dateiname)">⬇</button>
                <button v-if="!fe.deleted" class="btn-link" @click="deleteFinal(fe)">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="hint">{{ $t('gutachten.gerichtsgutachtenView.nochKeineEndfassungArchiviert') }}</p>
      </div>
    </div>

    <!-- #690 DOCX-Vorschau -->
    <div v-if="previewOpen" class="modal-bg" @mousedown.self="previewOpen = false">
      <div class="modal preview-modal">
        <div class="preview-header">
          <h3>{{ $t('gutachten.gerichtsgutachtenView.dOCXVorschau') }}</h3>
          <div>
            <button class="btn-secondary" @click="previewOpen = false">{{ $t('common.close') }}</button>
            <button class="btn-primary" @click="() => { previewOpen = false; exportDocx(); }">{{ $t('gutachten.gerichtsgutachtenView.inWordExportieren') }}</button>
          </div>
        </div>
        <div class="preview-body word-page">
          <p class="vertraulichkeit">[{{ aktuell.vertraulichkeit || $t('gutachten.gerichtsgutachtenView.sTRENGVERTRAULICH') }}]</p>
          <h1 class="doc-title">{{ aktuell.gutachten_art === 'privat' ? $t('gutachten.gerichtsgutachtenView.pRIVATGUTACHTEN') : $t('gutachten.gerichtsgutachtenView.sACHVERSTANDIGENGUTACHTEN') }}</h1>

          <!-- Gerichtsgutachten-Deckblatt -->
          <template v-if="(aktuell.gutachten_art || 'gericht') === 'gericht'">
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.gericht3') }}</strong> {{ aktuell.gericht }}<br/>
              <span v-if="aktuell.kammer">{{ aktuell.kammer }}<br/></span>
              {{ $t('gutachten.gerichtsgutachtenView.aktenzeichenV0', { v0: aktuell.aktenzeichen }) }}
            </p>
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.inDemRechtsstreit') }}</strong></p>
            <p class="parteien">
              {{ aktuell.klaeger_name }}<span class="dots">............................................</span> {{ $t('gutachten.gerichtsgutachtenView.klager') }}<br/>
              <span v-if="aktuell.klaeger_anwalt">{{ $t('gutachten.gerichtsgutachtenView.prozessbevollmachtigterV0', { v0: aktuell.klaeger_anwalt }) }}<br/></span>
              <span class="gegen">gegen</span><br/>
              {{ aktuell.beklagter_name }}<span class="dots">............................................</span> {{ $t('gutachten.gerichtsgutachtenView.beklagte') }}<br/>
              <span v-if="aktuell.beklagter_anwalt">{{ $t('gutachten.gerichtsgutachtenView.prozessbevollmachtigteV0', { v0: aktuell.beklagter_anwalt }) }}</span>
            </p>
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.themaDesGutachtens') }}</strong><br/>{{ aktuell.thema }}</p>
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.beweisbeschlussVom2') }}</strong> {{ aktuell.beweisbeschluss_datum }}</p>
          </template>

          <!-- Privatgutachten-Deckblatt -->
          <template v-else>
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.auftraggeber3') }}</strong> {{ aktuell.auftraggeber }}</p>
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.auftragsart') }}</strong> {{ aktuell.auftrags_art }}</p>
            <p v-if="aktuell.auftrags_nummer"><strong>{{ $t('gutachten.gerichtsgutachtenView.auftragsNummer2') }}</strong> {{ aktuell.auftrags_nummer }}</p>
            <p v-if="aktuell.auftrags_datum"><strong>{{ $t('gutachten.gerichtsgutachtenView.auftragsdatum') }}</strong> {{ aktuell.auftrags_datum }}</p>
            <p v-if="aktuell.honorarvereinbarung"><strong>{{ $t('gutachten.gerichtsgutachtenView.honorarvereinbarung2') }}</strong> {{ aktuell.honorarvereinbarung }}</p>
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.thema2') }}</strong><br/>{{ aktuell.thema }}</p>
          </template>

          <p><strong>{{ $t('gutachten.gerichtsgutachtenView.sachverstandiger') }}</strong><br/>
            {{ aktuell.sv_name }}<br/>
            <span v-if="aktuell.sv_zertifizierung">{{ aktuell.sv_zertifizierung }}<br/></span>
            <span v-if="aktuell.sv_anschrift">{{ aktuell.sv_anschrift }}<br/></span>
            <span v-if="aktuell.sv_kontakt">{{ aktuell.sv_kontakt }}</span>
          </p>
          <p><strong>{{ $t('gutachten.gerichtsgutachtenView.datum') }}</strong> {{ new Date().toLocaleDateString('de-DE') }}</p>

          <hr/>
          <h2>{{ $t('gutachten.gerichtsgutachtenView.iIUntersuchungsauftrag') }}</h2>
          <ol>
            <li v-for="f in store.beweisfragen" :key="f.id">{{ f.frage_text }}</li>
          </ol>

          <h2>{{ $t('gutachten.gerichtsgutachtenView.iIIVerfahrensgang') }}</h2>
          <ul>
            <li v-for="e in store.verfahrensereignisse" :key="e.id">
              <strong>{{ (e.ereignis_datum || '').slice(0, 10) }} — {{ e.titel }}</strong>
              <div v-if="e.empfaenger?.length">(an: {{ (e.empfaenger || []).join(', ') }})</div>
              <div v-if="e.beschreibung">{{ e.beschreibung }}</div>
            </li>
          </ul>

          <h2>{{ $t('gutachten.gerichtsgutachtenView.iVBefunderhebung') }}</h2>
          <div v-for="b in store.befunde" :key="b.id" style="margin: 12px 0;">
            <h3>{{ b.nr }} {{ b.titel }}</h3>
            <p v-if="b.methode"><strong>{{ $t('gutachten.gerichtsgutachtenView.methode3') }}</strong> {{ b.methode }}</p>
            <p v-if="b.werkzeug_name"><strong>{{ $t('gutachten.gerichtsgutachtenView.werkzeug2') }}</strong> {{ b.werkzeug_name }} {{ b.werkzeug_version }}</p>
            <div v-html="sanitizeHtml(b.beschreibung_text)"></div>
          </div>

          <h2>{{ $t('gutachten.gerichtsgutachtenView.vTechnischeBeurteilung') }}</h2>
          <div v-for="u in store.beurteilungen" :key="u.id" style="margin: 12px 0;">
            <h3>{{ u.nr }} {{ u.titel }}</h3>
            <p v-if="u.norm_referenz"><strong>{{ $t('gutachten.gerichtsgutachtenView.norm2') }}</strong> {{ u.norm_referenz }}</p>
            <p v-if="u.soll_text"><strong>{{ $t('gutachten.gerichtsgutachtenView.soll') }}</strong></p>
            <div v-html="sanitizeHtml(u.soll_text)"></div>
            <p v-if="u.ist_text"><strong>{{ $t('gutachten.gerichtsgutachtenView.ist') }}</strong></p>
            <div v-html="sanitizeHtml(u.ist_text)"></div>
            <p v-if="u.kausalitaet_text"><strong>{{ $t('gutachten.gerichtsgutachtenView.kausalitat2') }}</strong></p>
            <div v-html="sanitizeHtml(u.kausalitaet_text)"></div>
            <p v-if="u.bewertung_text"><strong>{{ $t('gutachten.gerichtsgutachtenView.wurdigung') }}</strong></p>
            <div v-html="sanitizeHtml(u.bewertung_text)"></div>
          </div>

          <h2>{{ $t('gutachten.gerichtsgutachtenView.vIBeantwortungDerBeweisfragen') }}</h2>
          <div v-for="f in store.beweisfragen" :key="`a-${f.id}`" style="margin: 8px 0;">
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.frageV0', { v0: f.nr }) }}</strong> {{ f.frage_text }}</p>
            <p><strong>{{ $t('gutachten.gerichtsgutachtenView.antwort') }}</strong> {{ f.antwort_kurz }} — {{ f.antwort_text }}</p>
          </div>

          <h2>{{ $t('gutachten.gerichtsgutachtenView.vIISchlussformel') }}</h2>
          <p>{{ $t('gutachten.gerichtsgutachtenView.derUnterzeichnendeVersichertDasGutac') }}</p>
          <p>{{ aktuell.sv_anschrift?.split(',').pop()?.trim() || '' }}, {{ new Date().toLocaleDateString('de-DE') }}</p>
          <p>_______________________________<br/><strong>{{ aktuell.sv_name }}</strong></p>

          <h2>{{ $t('gutachten.gerichtsgutachtenView.vIIIAnhang') }}</h2>
          <!-- #1029: Asservaten-Block nur bei vorhandenen Assets -->
          <template v-if="store.assets.length">
            <h3>{{ $t('gutachten.gerichtsgutachtenView.asservatenChainOfCustodyNachISOIEC') }}</h3>
            <table border="1" cellspacing="0" cellpadding="4">
              <thead><tr><th>{{ $t('gutachten.gerichtsgutachtenView.bezeichnung') }}</th><th>SHA-256</th><th>{{ $t('gutachten.gerichtsgutachtenView.akquisition') }}</th></tr></thead>
              <tbody>
                <tr v-for="a in store.assets" :key="a.id">
                  <td>{{ a.bezeichnung }}</td>
                  <td><code>{{ (a.sha256 || '').slice(0, 16) }}…</code></td>
                  <td>{{ a.akquisitions_utc }}</td>
                </tr>
              </tbody>
            </table>
          </template>
          <!-- #1027: Glossar in der Vorschau anzeigen (wie im DOCX-Export) -->
          <template v-if="store.glossar?.length">
            <h3>{{ $t('gutachten.gerichtsgutachtenView.glossar') }}</h3>
            <table border="1" cellspacing="0" cellpadding="4">
              <thead><tr><th>{{ $t('gutachten.gerichtsgutachtenView.begriff') }}</th><th>{{ $t('gutachten.gerichtsgutachtenView.erklarung') }}</th></tr></thead>
              <tbody>
                <tr v-for="g in store.glossar" :key="g.id">
                  <td>{{ g.begriff }}</td>
                  <td>{{ g.erklaerung }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </div>
    </div>

    <!-- Help-Modal (#671) -->
    <div v-if="helpModal.open" class="modal-bg" @mousedown.self="closeHelp">
      <div class="modal help-modal">
        <h3>ℹ {{ helpModal.data?.title || $t('gutachten.gerichtsgutachtenView.hilfe') }}</h3>
        <p v-if="helpModal.data?.norm" class="help-norm">📜 <strong>{{ $t('gutachten.gerichtsgutachtenView.norm2') }}</strong> {{ helpModal.data.norm }}</p>
        <div v-if="helpModal.data?.was" class="help-section">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.wasDieNormVerlangt') }}</strong>
          <p>{{ helpModal.data.was }}</p>
        </div>
        <div v-if="helpModal.data?.fallstrick" class="help-section help-fallstrick">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.typischerFallstrick') }}</strong>
          <p>{{ helpModal.data.fallstrick }}</p>
        </div>
        <div v-if="helpModal.data?.beispiel" class="help-section help-beispiel">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.beispiel') }}</strong>
          <p>{{ helpModal.data.beispiel }}</p>
        </div>
        <div class="modal-actions">
          <button class="btn-primary" @click="closeHelp">{{ $t('common.close') }}</button>
        </div>
      </div>
    </div>

    <!-- #866/#868/#869/#870: gemeinsames KI-Wizard-Modal (Beurteilung/Drittgutachter) -->
    <WizardPromptModal
      v-if="wizardModal.open"
      :title="wizardModal.title || $t('gutachten.gerichtsgutachtenView.kIVorschlag')"
      :prompt="wizardModal.prompt"
      :schema-hint="$t('gutachten.gerichtsgutachtenView.chatGPTAntwortAlsJSONEinfugen')"
      :busy="wizardModal.busy"
      @apply="onApplyWizard"
      @close="closeWizard"
    
    :egress-vorbestaetigt="wizardModal.confirmed">
      <template #before>
        <!-- §407a-Hinweis ist rechtlich bindend und bleibt erhalten -->
        <div class="disclaimer-407a">{{ $t('gutachten.gerichtsgutachtenView.kIVorschlagFinaleBeurteilungErfolgtD') }}</div>
        <DataPreviewWarning
          :fields="wizardPreviewFields"
          :provider="aiProvider"
          @confirm="wizardModal.confirmed = true"
        />
      </template>
      <template #after>
        <!-- #1838: Zwei Knöpfe öffnen dieses Modal. Der Hinweis muss sagen,
             was mit DIESER Antwort geschieht — vorher stand bei beiden
             „Übernimmt die Felder der Beurteilung", und bei einer
             Reproduktionsanleitung war das sogar zutreffend und falsch
             zugleich: Sie landete wirklich in der Beurteilung. -->
        <OutputDestinationHint
          v-if="wizardModal.zweck === 'drittgutachter'"
          :destination="$t('gutachten.gerichtsgutachtenView.pruftDieReproduktionsanleitungGegenD')"
          :impact="$t('gutachten.gerichtsgutachtenView.dasErgebnisErscheintUnterDemDrittgut')"
        />
        <OutputDestinationHint
          v-else
          :destination="$t('gutachten.gerichtsgutachtenView.ubernimmtDieFelderDerBeurteilungInDe')"
          :impact="$t('gutachten.gerichtsgutachtenView.derSachverstandigePruftUndFinalisier')"
        />
      </template>
    </WizardPromptModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { kopiere } from '../../utils/zwischenablage'
import { KI_VORBEHALT } from '../../utils/aktionen'
import { useGerichtsgutachtenStore } from '../../stores/gerichtsgutachten'
import { authHeader } from '../../api/auth-token'
import RichEditor from '../../components/RichEditor.vue'
import { sanitizeHtml } from '../../utils/sanitizeHtml'
import WizardPromptModal from '../../components/shared/WizardPromptModal.vue'
import ModuleHelpButton from '../../components/shared/ModuleHelpButton.vue'
import DataPreviewWarning from '../../components/shared/DataPreviewWarning.vue'
import OutputDestinationHint from '../../components/shared/OutputDestinationHint.vue'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'

const _htmlToPlain = (html: string): string => {
  const div = document.createElement('div')
  div.innerHTML = html || ''
  return div.textContent || ''
}

const store = useGerichtsgutachtenStore()
const tab = ref('stammdaten')
const creating = ref(false)
const aktuell = computed(() => store.aktuell)

const tabs = [
  { id: 'stammdaten', label: uebersetze('gutachten.gerichtsgutachtenView.deckblatt') },
  { id: 'selbstcheck', label: uebersetze('gutachten.gerichtsgutachtenView.selbstcheck') },
  { id: 'beweisfragen', label: 'II. Beweisfragen' },
  { id: 'befunde', label: 'IV. Befunde' },
  { id: 'beurteilungen', label: 'V. Beurteilungen' },
  { id: 'assets', label: uebersetze('gutachten.gerichtsgutachtenView.asservaten') },
  { id: 'verfahren', label: 'III. Verfahren' },
  { id: 'forensik', label: uebersetze('gutachten.gerichtsgutachtenView.forensikMACBTools') },
  { id: 'hypothesen', label: uebersetze('gutachten.gerichtsgutachtenView.hypothesenTree') },
  { id: 'peer', label: uebersetze('gutachten.gerichtsgutachtenView.peerReview') },
  { id: 'honorar', label: uebersetze('gutachten.gerichtsgutachtenView.honorar') },
  { id: 'validator', label: uebersetze('gutachten.gerichtsgutachtenView.validatorExport') },
  { id: 'glossar', label: uebersetze('gutachten.gerichtsgutachtenView.glossar') },
  { id: 'finalarchiv', label: uebersetze('gutachten.gerichtsgutachtenView.finalArchiv') },
]

const newForm = ref<any>({ name: '', gutachten_art: 'gericht',
  gericht: '', kammer: '', aktenzeichen: '', beweisbeschluss_datum: '',
  auftraggeber: '', auftrags_art: '', auftrags_datum: '', auftrags_nummer: '', honorarvereinbarung: '',
  vertraulichkeit: uebersetze('gutachten.gerichtsgutachtenView.sTRENGVERTRAULICH'), thema: '',
  klaeger_name: '', klaeger_anwalt: '', beklagter_name: '', beklagter_anwalt: '',
  sv_name: '', sv_zertifizierung: '', sv_anschrift: '', sv_kontakt: '' })

const newBF = ref<any>({ nr: 1, frage_text: '', antwort_kurz: '', antwort_text: '' })
const newBefund = ref<any>({ nr: '4.1', titel: '', methode: '', werkzeug_name: '',
  werkzeug_version: '', beschreibung_text: '' })
const newBeurt = ref<any>({ nr: '5.1', titel: '', norm_id: '', norm_referenz: '',
  befund_ids_str: '', soll_text: '', ist_text: '', kausalitaet_text: '', bewertung_text: '' })
const newAsset = ref<any>({ bezeichnung: '', sha256: '', akquisitions_utc: '',
  akquisitions_ort: '', werkzeug_name: '', werkzeug_version: '', gegengezeichnet_von: '' })
const newVerf = ref<any>({ ereignis_typ: 'akteneinsicht', titel: '', beschreibung: '',
  ereignis_datum: new Date().toISOString().slice(0, 10) })  // #979 Datum editierbar
const moveVerf = async (index: number, dir: number) => {  // #979 Reihenfolge
  const list = [...store.verfahrensereignisse]
  const j = index + dir
  if (j < 0 || j >= list.length) return
  ;[list[index], list[j]] = [list[j], list[index]]
  await store.reorderVerfahren(aktuell.value.name, list.map((e: any) => e.id))
}
const newVerfEmp = ref<any>({ klaeger: false, beklagter: false, gericht: false })
const newHon = ref<any>({ kategorie: 'labor', dauer_minuten: 60, stundensatz_eur: 130, beschreibung: '' })

const ereignisTypen = ['akteneinsicht', 'parteikommunikation', 'ortstermin', 'asservat-aufnahme',
  'labor-analyse', 'gutachten-versand', 'selbstcheck', 'befangenheitspruefung', 'sonstiges']

const selbstcheckAntw = ref<any>({})
const selbstcheckResult = ref<any>(null)
const befangCheckResult = ref<any>(null)
const symResult = ref<any>(null)
const validatorResult = ref<any>(null)
const befundLinterHints = ref<any[]>([])

// G7b
const newMacb = ref<any>({ datei_pfad: '', modified_at: '', accessed_at: '', changed_at: '', born_at: '' })
const newHyp = ref<any>({ beurteilung_id: 0, hypothese_text: '', status: 'offen', begruendung: '' })
const drittBefundId = ref<number | null>(null)
// #1838: Ergebnis des Drittgutachter-Audits (DIN EN 16775).
const drittResult = ref<any>(null)
const drittFehler = ref('')
const DRITT_LABELS: Record<string, string> = {
  schritte_vorhanden: uebersetze('gutachten.gerichtsgutachtenView.schritteVorhanden'),
  werkzeuge_genannt: uebersetze('gutachten.gerichtsgutachtenView.werkzeugeVoraussetzungenGenannt'),
  ergebnis_definiert: uebersetze('gutachten.gerichtsgutachtenView.erwartetesErgebnisDefiniert'),
  reproduzierbarkeit_bewertet: uebersetze('gutachten.gerichtsgutachtenView.reproduzierbarkeitBewertet'),
}
const newReviewer = ref('')
const peerKomm = ref<Record<number, any>>({})
const crossRefResult = ref<any>(null)
const logClassResult = ref<any>(null)
const anonResult = ref<any>(null)

// #1838: `zweck` entscheidet, was mit der eingefügten Antwort geschieht. Zwei
// Knöpfe öffnen dieses Modal; vorher kannte der gemeinsame Übernahme-Handler
// den Unterschied nicht und parste beides als Beurteilung.
const wizardModal = ref<any>({ open: false, prompt: '', title: uebersetze('gutachten.gerichtsgutachtenView.kIVorschlag'),
                               busy: false, confirmed: false, zweck: 'beurteilung' })
// #867/#877: aktiver KI-Provider für die Daten-Transparenz
const aiProvider = ref<'on_prem' | 'cloud'>('on_prem')
const wizardPreviewFields = computed(() => [
  { label: uebersetze('common.projekt'), value: aktuell.value?.name },
  { label: uebersetze('gutachten.gerichtsgutachtenView.norm'), value: newBeurt.value?.norm_id },
  { label: uebersetze('gutachten.gerichtsgutachtenView.befundIDs'), value: newBeurt.value?.befund_ids_str },
])

// #671 Help-Modal + #670 Vollbild-Editor
const helpModal = ref<any>({ open: false, data: null })
const fullscreenEditor = ref<string>('')
// #690 DOCX-Vorschau + #692 letzter Selbstcheck + #699 editierbarer Fließtext
const previewOpen = ref(false)
const lastSelbstcheck = ref<any>(null)
const fliesstextEdit = ref('')
const fliesstextOriginal = ref('')
const fliesstextSaveStatus = ref('')
const openPreview = () => { previewOpen.value = true }
const resetFliesstext = () => { fliesstextEdit.value = fliesstextOriginal.value }
const saveFliesstext = async () => {
  if (!lastSelbstcheck.value?.id) return
  fliesstextSaveStatus.value = 'speichert …'
  try {
    const r = await store.saveVerfahren(aktuell.value.name, {
      id: lastSelbstcheck.value.id,
      ereignis_typ: lastSelbstcheck.value.ereignis_typ,
      titel: lastSelbstcheck.value.titel,
      beschreibung: fliesstextEdit.value,
      ereignis_datum: lastSelbstcheck.value.ereignis_datum,
      empfaenger: lastSelbstcheck.value.empfaenger || [],
    })
    fliesstextSaveStatus.value = r ? uebersetze('common.gespeichert') : uebersetze('gutachten.gerichtsgutachtenView.fehler')
    if (r) {
      lastSelbstcheck.value.beschreibung = fliesstextEdit.value
      fliesstextOriginal.value = fliesstextEdit.value
      setTimeout(() => { fliesstextSaveStatus.value = '' }, 3000)
    }
  } catch (e) { fliesstextSaveStatus.value = uebersetze('gutachten.gerichtsgutachtenView.fehler') }
}

const showHelp = async (key: string) => {
  helpModal.value = { open: true, data: await store.fetchHelp(key) }
}
const closeHelp = () => { helpModal.value = { open: false, data: null } }
const toggleFullscreen = (which: string) => {
  fullscreenEditor.value = fullscreenEditor.value === which ? '' : which
}

// #944: Der Name ist der Routen-Schlüssel — Schrägstriche brechen das Routing
// (Projekt nach dem Speichern nicht mehr auswählbar). Hier hart verhindern.
const nameError = computed(() =>
  /[/\\]/.test(newForm.value.name || '')
    ? uebersetze('gutachten.gerichtsgutachtenView.projektNameDarfKeinenSchragstrichOde')
    : '')

const validNewForm = computed(() => {
  if (!newForm.value.name || !newForm.value.sv_name) return false
  if (nameError.value) return false
  if (newForm.value.gutachten_art === 'privat') {
    return !!newForm.value.auftraggeber && !!newForm.value.auftrags_art
  }
  return !!newForm.value.gericht && !!newForm.value.aktenzeichen
})

// #942: zeigt an, welche Pflichtfelder beim deaktivierten „Anlegen" noch fehlen.
const missingFields = computed<string[]>(() => {
  const m: string[] = []
  if (!newForm.value.name) m.push(uebersetze('gutachten.gerichtsgutachtenView.projektName'))
  if (newForm.value.gutachten_art === 'privat') {
    if (!newForm.value.auftraggeber) m.push(uebersetze('gutachten.gerichtsgutachtenView.auftraggeber'))
    if (!newForm.value.auftrags_art) m.push(uebersetze('gutachten.gerichtsgutachtenView.auftragsArt'))
  } else {
    if (!newForm.value.gericht) m.push(uebersetze('gutachten.gerichtsgutachtenView.gericht'))
    if (!newForm.value.aktenzeichen) m.push(uebersetze('gutachten.gerichtsgutachtenView.aktenzeichen'))
  }
  if (!newForm.value.sv_name) m.push(uebersetze('gutachten.gerichtsgutachtenView.sVName'))
  return m
})

// #942: Befangenheits-Check art-abhängig — Privatgutachten prüft gegen den
// Auftraggeber (kein Kläger), Gerichtsgutachten gegen den Kläger.
const befangParty = computed(() =>
  newForm.value.gutachten_art === 'privat'
    ? newForm.value.auftraggeber
    : newForm.value.klaeger_name)
const befangReady = computed(() => !!befangParty.value)

const startNew = () => { creating.value = true; befangCheckResult.value = null }
const cancelNew = () => { creating.value = false; befangCheckResult.value = null }

const runBefangCheck = async () => {
  const party = befangParty.value
  if (!party) return
  const parteien = newForm.value.gutachten_art === 'privat'
    ? [newForm.value.auftraggeber].filter(Boolean)
    : [newForm.value.klaeger_name, newForm.value.beklagter_name].filter(Boolean)
  const r = await store.befangenheitsCheck(
    party,
    newForm.value.thema,
    parteien,
    newForm.value.sv_name,
  )
  befangCheckResult.value = r
}

const createProjekt = async () => {
  const name = await store.createProjekt(newForm.value)
  if (name) { creating.value = false; await selectProjekt(name) }
}

const selectProjekt = async (name: string) => {
  await store.fetchProjekt(name)
  await Promise.all([
    store.fetchBeweisfragen(name), store.fetchBefunde(name), store.fetchBeurteilungen(name),
    store.fetchAssets(name), store.fetchVerfahren(name),
    store.fetchNormen(), store.fetchSelbstcheckFragen(), store.fetchHonorar(name),
    fetchAuditSource(name), store.fetchTemplates(), store.fetchFinalExports(name),
    store.fetchGlossar(name),
  ])
  tab.value = 'stammdaten'
}

// ============================================================
// Phase H — Audit-Source Anzeige + Beweisfragen-Generator + Smart Suggestions
// ============================================================
import apiClient from '../../api/client'
// `t` ist in dieser Maske schon belegt (lokale Variable/Parameter) —
// deshalb unter anderem Namen. Ein Import überdeckt eine lokale
// Bindung nicht, er kollidiert mit ihr: Der Aufruf trifft die
// Variable, und die ist keine Funktion. Gefunden hat das der
// Typprüfer (#1858), nicht der Build.
import { t as uebersetze } from '../../i18n'
const auditSource = ref<any>(null)
const pgQuestionsPrompt = ref('')
const pgQuestionsResponse = ref('')
const pgQuestionsImportMsg = ref('')
const smartPrompt = ref('')
const smartResponse = ref('')
const smartParsed = ref<any>(null)

const fetchAuditSource = async (pgName: string) => {
  try {
    const r = await apiClient.get(`/gutachten/gerichts/${encodeURIComponent(pgName)}/audit-source`)
    auditSource.value = r.data?.audit_source || null
  } catch { auditSource.value = null }
}

const copyToClipboard = async (text: string) => {
  kopiert.value = await kopiere(text)
  if (kopiert.value) setTimeout(() => (kopiert.value = false), 2000)
}

const generatePgQuestions = async () => {
  if (!auditSource.value?.audit_projekt) return
  pgQuestionsImportMsg.value = ''
  try {
    const r = await apiClient.post(
      `/gutachten/${encodeURIComponent(auditSource.value.audit_projekt)}/build-pg-questions-prompt`,
      { auftrags_art: aktuell.value?.auftrags_art || uebersetze('gutachten.gerichtsgutachtenView.tauglichkeitsprufung') },
    )
    pgQuestionsPrompt.value = r.data?.prompt || ''
  } catch (e: any) {
    alert(uebersetze('gutachten.gerichtsgutachtenView.konntePromptNichtErstellen') + (e?.response?.data?.error || e.message))
  }
}

const importPgQuestions = async () => {
  if (!pgQuestionsResponse.value || !aktuell.value?.name) return
  try {
    const r = await apiClient.post(
      `/gutachten/gerichts/${encodeURIComponent(aktuell.value.name)}/import-pg-questions`,
      { raw_response: pgQuestionsResponse.value },
    )
    pgQuestionsImportMsg.value = `✓ ${r.data?.imported || 0} Beweisfragen importiert.`
    pgQuestionsResponse.value = ''
    await store.fetchBeweisfragen(aktuell.value.name)
  } catch (e: any) {
    pgQuestionsImportMsg.value = '⛔ Fehler: ' + (e?.response?.data?.error || e.message)
  }
}

const generateSmartSuggestionsPrompt = async () => {
  if (!auditSource.value?.audit_projekt) return
  try {
    const r = await apiClient.post(
      `/gutachten/${encodeURIComponent(auditSource.value.audit_projekt)}/smart-suggestions-prompt`, {},
    )
    smartPrompt.value = r.data?.prompt || ''
  } catch (e: any) {
    alert(uebersetze('gutachten.gerichtsgutachtenView.fehler2') + (e?.response?.data?.error || e.message))
  }
}

const parseSmartSuggestions = async () => {
  try {
    const r = await apiClient.post('/gutachten/parse-smart-suggestions', { raw_response: smartResponse.value })
    smartParsed.value = r.data
  } catch (e: any) {
    alert(uebersetze('gutachten.gerichtsgutachtenView.parseFehler') + (e?.response?.data?.error || e.message))
  }
}
const closeProjekt = () => { store.aktuell = null }
const saveStammdaten = () => store.updateProjekt(aktuell.value.name, aktuell.value)
const deleteProjekt = async () => {
  if (!confirm(uebersetze('common.wirklichLoeschen'))) return
  await store.deleteProjekt(aktuell.value.name)
  store.aktuell = null
}

const runSelbstcheck = async () => {
  selbstcheckResult.value = await store.runSelbstcheck(aktuell.value.name, selbstcheckAntw.value, aktuell.value.sv_name)
  await store.fetchVerfahren(aktuell.value.name)
  // #696 letzten Selbstcheck + Fließtext aktualisieren
  const sc = (store.verfahrensereignisse || []).filter((e: any) => e.ereignis_typ === 'selbstcheck')
  lastSelbstcheck.value = sc.length ? sc[sc.length - 1] : null
  fliesstextEdit.value = lastSelbstcheck.value?.beschreibung || selbstcheckResult.value?.fliesstext || ''
  fliesstextOriginal.value = fliesstextEdit.value
}

// #677 Edit-State pro Section + Helper
const editId = ref<Record<string, number | null>>({
  bf: null, befund: null, beurt: null, asset: null, verf: null, macb: null, hyp: null,
})

const cancelEdit = (section: string) => {
  editId.value[section] = null
  // Form leeren je nach Section
  if (section === 'bf') newBF.value = { nr: 1, frage_text: '', antwort_kurz: '', antwort_text: '' }
  else if (section === 'befund') {
    newBefund.value = { nr: '', titel: '', methode: '', werkzeug_name: '', werkzeug_version: '', beschreibung_text: '' }
    befundLinterHints.value = []
  }
  else if (section === 'beurt') newBeurt.value = { nr: '', titel: '', norm_id: '', norm_referenz: '', befund_ids_str: '', soll_text: '', ist_text: '', kausalitaet_text: '', bewertung_text: '' }
  else if (section === 'asset') newAsset.value = { bezeichnung: '', sha256: '', akquisitions_utc: '', akquisitions_ort: '', werkzeug_name: '', werkzeug_version: '', gegengezeichnet_von: '' }
  else if (section === 'verf') {
    newVerf.value = { ereignis_typ: 'akteneinsicht', titel: '', beschreibung: '' }
    newVerfEmp.value = { klaeger: false, beklagter: false, gericht: false }
  }
  else if (section === 'macb') newMacb.value = { datei_pfad: '', modified_at: '', accessed_at: '', changed_at: '', born_at: '' }
  else if (section === 'hyp') newHyp.value = { beurteilung_id: 0, hypothese_text: '', status: 'offen', begruendung: '' }
}

const editBF = (f: any) => {
  editId.value.bf = f.id
  newBF.value = { nr: f.nr, frage_text: f.frage_text, antwort_kurz: f.antwort_kurz,
                  antwort_text: f.antwort_text, referenz_beurteilung_ids: f.referenz_beurteilung_ids || [] }
  scrollToAddForm()
}
const editBefund = (b: any) => {
  editId.value.befund = b.id
  newBefund.value = { nr: b.nr, titel: b.titel, methode: b.methode,
                       werkzeug_name: b.werkzeug_name, werkzeug_version: b.werkzeug_version,
                       beschreibung_text: b.beschreibung_text, asset_ids: b.asset_ids || [],
                       erhebung_datum: b.erhebung_datum, erhebung_ort: b.erhebung_ort,
                       zeugen_text: b.zeugen_text }
  scrollToAddForm()
}
const editBeurt = (u: any) => {
  editId.value.beurt = u.id
  newBeurt.value = { nr: u.nr, titel: u.titel, norm_id: '', norm_referenz: u.norm_referenz,
                     befund_ids_str: (u.befund_ids || []).join(','),
                     soll_text: u.soll_text, ist_text: u.ist_text,
                     kausalitaet_text: u.kausalitaet_text, bewertung_text: u.bewertung_text }
  scrollToAddForm()
}
const editAsset = (a: any) => {
  editId.value.asset = a.id
  newAsset.value = { bezeichnung: a.bezeichnung, sha256: a.sha256,
                     akquisitions_utc: a.akquisitions_utc, akquisitions_ort: a.akquisitions_ort,
                     werkzeug_name: a.werkzeug_name, werkzeug_version: a.werkzeug_version,
                     gegengezeichnet_von: a.gegengezeichnet_von }
  scrollToAddForm()
}
const editVerf = (e: any) => {
  editId.value.verf = e.id
  newVerf.value = { ereignis_typ: e.ereignis_typ, titel: e.titel,
                     beschreibung: e.beschreibung, ereignis_datum: e.ereignis_datum }
  const emp = (e.empfaenger || []).map((s: string) => s.toLowerCase())
  newVerfEmp.value = {
    klaeger: emp.some((s: string) => s.includes('kläger') || s.includes('klaeger')),
    beklagter: emp.some((s: string) => s.includes('beklagt')),
    gericht: emp.some((s: string) => s.includes('gericht')),
  }
  scrollToAddForm()
}
const editMacb = (m: any) => {
  editId.value.macb = m.id
  newMacb.value = { datei_pfad: m.datei_pfad, modified_at: m.modified_at,
                     accessed_at: m.accessed_at, changed_at: m.changed_at, born_at: m.born_at }
  scrollToAddForm()
}
const editHyp = (h: any) => {
  editId.value.hyp = h.id
  newHyp.value = { beurteilung_id: h.beurteilung_id, hypothese_text: h.hypothese_text,
                    status: h.status, begruendung: h.begruendung }
  scrollToAddForm()
}
const deleteVerf = async (id: number) => {
  if (!confirm(uebersetze('gutachten.gerichtsgutachtenView.verfahrensereignisLoschen'))) return
  try { await fetch(`/api/gutachten/gerichts/verfahren/${id}`, { method: 'DELETE',
      headers: { ...authHeader() } })  // #1190: zentraler Token-Zugriff (Bug: war localStorage 'access_token')
    await store.fetchVerfahren(aktuell.value.name)
  } catch {}
}
const scrollToAddForm = () => {
  setTimeout(() => {
    const form = document.querySelector('.add-form')
    if (form) form.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 100)
}

const addBF = async () => {
  const data: any = { ...newBF.value }
  if (editId.value.bf) data.id = editId.value.bf
  if (await store.saveBeweisfrage(aktuell.value.name, data)) {
    editId.value.bf = null
    newBF.value = { nr: data.id ? newBF.value.nr : newBF.value.nr + 1, frage_text: '', antwort_kurz: '', antwort_text: '' }
  }
}

let befundLinterTimer: any = null
const validateBefundLive = () => {
  clearTimeout(befundLinterTimer)
  befundLinterTimer = setTimeout(async () => {
    // #674: HTML-Content → Plain-Text für Linter
    const plain = _htmlToPlain(newBefund.value.beschreibung_text)
    const r = await store.validateBefundText(plain)
    befundLinterHints.value = r?.hints || []
  }, 400)
}
const addBefund = async () => {
  const data: any = { ...newBefund.value }
  if (editId.value.befund) data.id = editId.value.befund
  if (await store.saveBefund(aktuell.value.name, data)) {
    editId.value.befund = null
    newBefund.value = { nr: '', titel: '', methode: '', werkzeug_name: '',
      werkzeug_version: '', beschreibung_text: '' }
    befundLinterHints.value = []
  }
}

const addBeurteilung = async () => {
  const ids = (newBeurt.value.befund_ids_str || '').split(',').map((s: string) => Number(s.trim())).filter(Boolean)
  const data: any = { ...newBeurt.value, befund_ids: ids }
  delete data.befund_ids_str
  if (editId.value.beurt) data.id = editId.value.beurt
  if (await store.saveBeurteilung(aktuell.value.name, data)) {
    editId.value.beurt = null
    newBeurt.value = { nr: '', titel: '', norm_id: '', norm_referenz: '', befund_ids_str: '',
      soll_text: '', ist_text: '', kausalitaet_text: '', bewertung_text: '' }
  }
}

const onAssetFile = async (ev: Event) => {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (!f) return
  const hash = await store.uploadAndHash(f)
  if (hash) {
    newAsset.value.sha256 = hash.sha256
    if (!newAsset.value.akquisitions_utc) {
      newAsset.value.akquisitions_utc = new Date().toISOString()
    }
  }
}
const addAsset = async () => {
  const data: any = { ...newAsset.value }
  if (editId.value.asset) data.id = editId.value.asset
  if (await store.saveAsset(aktuell.value.name, data)) {
    editId.value.asset = null
    newAsset.value = { bezeichnung: '', sha256: '', akquisitions_utc: '',
      akquisitions_ort: '', werkzeug_name: '', werkzeug_version: '', gegengezeichnet_von: '' }
  }
}

const addVerf = async () => {
  const emp: string[] = []
  if (newVerfEmp.value.klaeger) emp.push(uebersetze('gutachten.gerichtsgutachtenView.klager'))
  if (newVerfEmp.value.beklagter) emp.push(uebersetze('gutachten.gerichtsgutachtenView.beklagter'))
  if (newVerfEmp.value.gericht) emp.push(uebersetze('gutachten.gerichtsgutachtenView.gericht'))
  const data: any = { ...newVerf.value, empfaenger: emp }
  if (editId.value.verf) data.id = editId.value.verf
  if (await store.saveVerfahren(aktuell.value.name, data)) {
    editId.value.verf = null
    newVerf.value = { ereignis_typ: 'akteneinsicht', titel: '', beschreibung: '' }
    newVerfEmp.value = { klaeger: false, beklagter: false, gericht: false }
  }
}

const runSymmetrieCheck = async () => { symResult.value = await store.symmetrieCheck(aktuell.value.name) }
const runValidator = async () => { validatorResult.value = await store.runSchlussValidator(aktuell.value.name) }

const addHon = async () => {
  const data = { ...newHon.value, projekt_typ: 'gerichts', projekt_name: aktuell.value.name,
    sv_user: aktuell.value.sv_name, tarif_modell: 'jveg' }
  if (await store.saveHonorarEintrag(data)) {
    await store.fetchHonorar(aktuell.value.name)
    newHon.value = { kategorie: 'labor', dauer_minuten: 60, stundensatz_eur: 130, beschreibung: '' }
  }
}

const openBeurteilungsWizard = async () => {
  const ids = (newBeurt.value.befund_ids_str || '').split(',').map((s: string) => Number(s.trim())).filter(Boolean)
  const prompt = await store.beurteilungPrompt(aktuell.value.name, newBeurt.value.norm_id, null, ids)
  wizardModal.value = { open: true, prompt, title: uebersetze('gutachten.gerichtsgutachtenView.beurteilungsWizard'), busy: false, confirmed: false, zweck: 'beurteilung' }
}
const closeWizard = () => { wizardModal.value = { open: false, prompt: '', title: uebersetze('gutachten.gerichtsgutachtenView.kIVorschlag'), busy: false, confirmed: false, zweck: 'beurteilung' } }
const onApplyWizard = async (rawText: string) => {
  if (!rawText) return
  wizardModal.value.busy = true
  try {
    // #1838: Die Antwort gehört dorthin, wo sie angefragt wurde. Vorher ging
    // sie in BEIDEN Fällen durch `beurteilungParse` — die
    // Reproduktionsanleitung für den Drittgutachter landete damit als
    // Beurteilung im Editor, ohne dass etwas fehlschlug.
    if (wizardModal.value.zweck === 'drittgutachter') {
      drittFehler.value = ''
      // Geparst wird serverseitig (kanonischer Parser, kennt Codefences und
      // abgeschnittene Antworten) — nicht im Browser.
      const res = await store.drittgutachterAudit({ response: rawText })
      if (res && !res.error) {
        drittResult.value = res
        closeWizard()
      } else if (res?.error) {
        drittFehler.value = res.error
      }
      // res === null → der Store hat die Meldung schon gesetzt (oben im
      // FehlerHinweis); eine zweite, unschärfere daneben hilft niemandem.
      return
    }
    const parsed = await store.beurteilungParse(aktuell.value.name, rawText, newBeurt.value.norm_id, null)
    if (parsed?.parsed) {
      Object.assign(newBeurt.value, parsed.parsed)
      closeWizard()
    }
  } finally {
    wizardModal.value.busy = false
  }
}

const canEditDeckblatt = computed(() => (aktuell.value?.status || 'in_bearbeitung') === 'in_bearbeitung')  // #966

// #983/#984 Glossar
const newGloss = ref<any>({ begriff: '', erklaerung: '' })
const glossarMsg = ref('')
const genGlossar = async () => {
  glossarMsg.value = ''
  const stats = await store.generateGlossar(aktuell.value.name)
  glossarMsg.value = stats ? `✓ ${stats.inserted} neu, ${stats.updated} ergänzt, ${stats.kept} unverändert`
    : `⚠ ${store.error}`
}
const addGlossar = async () => {
  if (await store.saveGlossarEntry(aktuell.value.name, { ...newGloss.value, quelle: 'manuell' }))
    newGloss.value = { begriff: '', erklaerung: '' }
}
const updGlossar = (g: any) => store.saveGlossarEntry(aktuell.value.name,
  { id: g.id, begriff: g.begriff, erklaerung: g.erklaerung, typ: g.typ, quelle: 'manuell' })

// #969 Final-Archiv
const finalFile = ref<File | null>(null)
const finalBemerkung = ref('')
const finalMsg = ref('')
const onFinalFile = (e: Event) => { finalFile.value = (e.target as HTMLInputElement).files?.[0] || null }
const uploadFinal = async () => {
  finalMsg.value = ''
  if (!finalFile.value) return
  const res = await store.uploadFinalExport(aktuell.value.name, finalFile.value, finalBemerkung.value)
  if (res) { finalMsg.value = `✓ Archiviert (SHA-256 ${String(res.sha256).slice(0,12)}…)`; finalFile.value = null; finalBemerkung.value = '' }
  else finalMsg.value = `⚠ ${store.error}`
}
const deleteFinal = async (fe: any) => {
  const reason = window.prompt('Begründung für die Löschung (mind. 10 Zeichen, wird im Audit-Log protokolliert):') || ''
  if (reason.trim().length < 10) { finalMsg.value = '⚠ Begründung muss mind. 10 Zeichen haben.'; return }
  if (await store.deleteFinalExport(aktuell.value.name, fe.id, reason.trim())) finalMsg.value = '✓ Gelöscht (Soft-Delete, Nachweis bleibt).'
  else finalMsg.value = `⚠ ${store.error}`
}
const includeAnhang = ref(true)  // #956
const includeMethodeWerkzeug = ref(true)  // #967
const includeBeurtSubheadings = ref(true)  // #968
const includeVerfahrenDatum = ref(true)  // #979
const includeGlossar = ref(true)  // #985
const exportTemplateId = ref<number | null>(null)  // #957
const exportDocx = () => store.downloadDocx(
  aktuell.value.name, includeAnhang.value, exportTemplateId.value,
  { methodeWerkzeug: includeMethodeWerkzeug.value, beurteilungSubheadings: includeBeurtSubheadings.value,
    verfahrenDatum: includeVerfahrenDatum.value, glossar: includeGlossar.value })

// #955/#957 Stammdaten & Vorlagen
const newGutachter = ref<any>({ name: '', zertifizierung: '', email: '' })
const newHilfsperson = ref<any>({ name: '', rolle: '' })
const newTemplate = ref<any>({ name: '', art: 'beide', file: null as File | null })
const templateMsg = ref('')
const onStammdatenOpen = (e: Event) => {
  if ((e.target as HTMLDetailsElement).open) {
    store.fetchGutachter(); store.fetchHilfspersonen(); store.fetchTemplates()
  }
}
const addGutachter = async () => {
  if (await store.saveGutachter({ ...newGutachter.value })) newGutachter.value = { name: '', zertifizierung: '', email: '' }
}
const addHilfsperson = async () => {
  if (await store.saveHilfsperson({ ...newHilfsperson.value })) newHilfsperson.value = { name: '', rolle: '' }
}
const onTemplateFile = (e: Event) => {
  const f = (e.target as HTMLInputElement).files?.[0] || null
  newTemplate.value.file = f
  if (f && !newTemplate.value.name) newTemplate.value.name = f.name.replace(/\.[^.]+$/, '')
}
const addTemplate = async () => {
  templateMsg.value = ''
  const res = await store.uploadTemplate(newTemplate.value.file, newTemplate.value.name, newTemplate.value.art)
  if (res) {
    templateMsg.value = `✓ Hochgeladen (${res.engine}). ${res.placeholder_count || 0} Platzhalter erkannt — „🔗 Felder zuordnen" zum Prüfen.`
    newTemplate.value = { name: '', art: 'beide', file: null }
  } else {
    templateMsg.value = `⚠ ${store.error}`
  }
}

// #962 Variablen-Hilfe
const varsHelpOpen = ref(false)
const varsSchema = ref<any[]>([])
const varsCopyMsg = ref('')
const kopiert = ref(false)
const varsListText = computed(() => varsSchema.value.map((v: any) => v.token).join('\n'))
const openVarsHelp = async () => {
  varsCopyMsg.value = ''
  if (!varsSchema.value.length) varsSchema.value = await store.fetchTemplateSchema()
  varsHelpOpen.value = true
}
const _copy = async (text: string, label: string) => {
  varsCopyMsg.value = await kopiere(text)
    ? `✓ ${label} in die Zwischenablage kopiert`
    : uebersetze('gutachten.gerichtsgutachtenView.kopierenNichtMoglichBitteManuellMark')
}
const copyVarsList = () => _copy(varsListText.value, 'Liste')
const copyVarsTable = () => {
  const header = 'Variable\tTyp\tBeschreibung'
  const rows = varsSchema.value.map((v: any) => `${v.token}\t${v.typ}\t${v.beschreibung}${v.pflicht ? ' (Pflicht)' : ''}`)
  _copy([header, ...rows].join('\n'), 'Tabelle')
}

// #959 Mapping-Wizard
const mappingTpl = ref<any>(null)
const mappingPlaceholders = ref<string[]>([])
const mappingDraft = ref<Record<string, string>>({})
const mappingSchema = ref<any[]>([])
const mappingMsg = ref('')
const isKnownMapValue = (v: string) =>
  v === '' || v === '__empty__' || mappingSchema.value.some((s: any) => s.key === v)
const openMapping = async (t: any) => {
  mappingMsg.value = ''
  mappingTpl.value = t
  if (!mappingSchema.value.length) mappingSchema.value = await store.fetchTemplateSchema()
  const det = await store.fetchTemplateDetail(t.id)
  mappingPlaceholders.value = (det?.variablen || []).map((v: any) => v.token)
  const m: Record<string, string> = {}
  for (const ph of mappingPlaceholders.value) m[ph] = (det?.mapping || {})[ph] || ''
  mappingDraft.value = m
}
const saveMapping = async () => {
  if (!mappingTpl.value) return
  const ok = await store.saveTemplateMapping(mappingTpl.value.id, mappingDraft.value)
  if (ok) { mappingMsg.value = '✓ Zuordnung gespeichert'; setTimeout(() => { mappingTpl.value = null }, 700) }
  else mappingMsg.value = `⚠ ${store.error}`
}
const exportArchiv = () => store.downloadArchiv(aktuell.value.name)

// G7b — Forensik
const addMacb = async () => {
  const data: any = { ...newMacb.value }
  if (editId.value.macb) data.id = editId.value.macb
  if (await store.saveMacb(aktuell.value.name, data)) {
    editId.value.macb = null
    newMacb.value = { datei_pfad: '', modified_at: '', accessed_at: '', changed_at: '', born_at: '' }
  }
}
const runToolValidator = () => store.runWerkzeugValidator(aktuell.value.name)
const onLogClassify = async (ev: Event) => {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (!f) return
  logClassResult.value = await store.classifyLogFile(f)
}

// G7b — Hypothesen
const addHyp = async () => {
  const data: any = { ...newHyp.value }
  if (editId.value.hyp) {
    // Hypothese-Update über PUT (nur status + begruendung wird upgedated im Backend)
    await store.updateHypothese(editId.value.hyp, aktuell.value.name, data.status, data.begruendung)
    editId.value.hyp = null
    newHyp.value = { beurteilung_id: 0, hypothese_text: '', status: 'offen', begruendung: '' }
  } else if (await store.saveHypothese(data, aktuell.value.name)) {
    newHyp.value = { beurteilung_id: 0, hypothese_text: '', status: 'offen', begruendung: '' }
  }
}
const updateHyp = (h: any, newStatus: string) => store.updateHypothese(h.id, aktuell.value.name, newStatus, h.begruendung)
const openDrittPrompt = async () => {
  if (!drittBefundId.value) return
  const prompt = await store.drittgutachterPrompt(drittBefundId.value)
  wizardModal.value = { open: true, prompt, title: uebersetze('gutachten.gerichtsgutachtenView.reproduktionsanleitungDrittgutachter'), busy: false, confirmed: false, zweck: 'drittgutachter' }
}
const runCrossRef = async () => { crossRefResult.value = await store.crossRefCheck(aktuell.value.name) }

// G7b — Peer-Review
const requestPeer = async () => {
  if (await store.requestPeerReview(aktuell.value.name, newReviewer.value)) {
    newReviewer.value = ''
    initPeerKomm()
  }
}
const initPeerKomm = () => {
  for (const r of store.peerReviews) {
    if (!peerKomm.value[r.id]) peerKomm.value[r.id] = { kapitel: '', text: '', author: '' }
  }
}
const addKomm = async (rid: number) => {
  const k = peerKomm.value[rid]
  if (await store.addPeerKommentar(rid, aktuell.value.name, k.kapitel, k.text, k.author)) {
    peerKomm.value[rid] = { kapitel: '', text: '', author: '' }
  }
}
const closePeerReview = (rid: number) => store.closePeerReview(rid, aktuell.value.name)
const setAufbew = async () => { await store.setAufbewahrung(aktuell.value.name, 10); await store.fetchAufbewahrung(aktuell.value.name) }
const loadAnon = async () => { anonResult.value = await store.fetchAnonymized(aktuell.value.name) }

onMounted(async () => {
  store.fetchProjekte()
  // #867/#877: aktiven KI-Provider für die Daten-Transparenz laden
  try {
    const { default: api } = await import('../../api/client')
    const res = await api.get('/ai/provider-status')
    aiProvider.value = res.data?.provider === 'cloud' ? 'cloud' : 'on_prem'
  } catch { /* Default on_prem */ }
})
watch(() => store.aktuell, async (v) => {
  if (!v) { tab.value = 'stammdaten'; lastSelbstcheck.value = null }
  else {
    await Promise.all([store.fetchVolatility(), store.fetchMacb(v.name), store.fetchPeerReviews(v.name), store.fetchAufbewahrung(v.name), store.fetchHypothesen(v.name)])
    initPeerKomm()
    // #692 letzten Selbstcheck-Verfahrensereignis laden
    await store.fetchVerfahren(v.name)
    const sc = (store.verfahrensereignisse || []).filter((e: any) => e.ereignis_typ === 'selbstcheck')
    lastSelbstcheck.value = sc.length ? sc[sc.length - 1] : null
    // #696 — Fließtext-Edit-Field füllen
    fliesstextEdit.value = lastSelbstcheck.value?.beschreibung || ''
    fliesstextOriginal.value = fliesstextEdit.value
    fliesstextSaveStatus.value = ''
    // Antworten aus Projekt-meta_json.last_selbstcheck laden (statt JSON-beschreibung)
    try {
      const meta = JSON.parse((v as any).meta_json || '{}')
      if (meta.last_selbstcheck?.antworten) Object.assign(selbstcheckAntw.value, meta.last_selbstcheck.antworten)
    } catch {}
  }
})
</script>

<style scoped>
.gg-view { display: flex; flex-direction: column; gap: 16px; padding: 20px; }
.header { position: relative; }
.header h2 { color: #5d4037; margin: 0; }
.header p { color: #666; margin: 4px 0; }
.header-help { position: absolute; top: 0; right: 0; }
.back-link { color: #1565c0; text-decoration: none; font-size: 13px; }
.alert-error { background: #ffebee; padding: 10px; border-radius: 4px; color: #c62828; cursor: pointer; }
.card { background: white; padding: 16px 20px; border-radius: 6px; border: 1px solid #ddd; }
.proj-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin: 12px 0; }
.proj-tile { padding: 12px; background: #fafafa; border: 1px solid #ccc; border-radius: 6px;
             cursor: pointer; text-align: left; display: flex; flex-direction: column; gap: 4px; }
.proj-tile:hover { background: #fff; border-color: #5d4037; }
.proj-az { font-family: monospace; color: #666; font-size: 12px; }
.proj-status { font-size: 11px; padding: 2px 6px; border-radius: 10px; width: fit-content; }
.status-in_bearbeitung { background: #fff3e0; color: #e65100; }
.status-finalisiert { background: #e8f5e9; color: #2e7d32; }
.status-eingereicht { background: #e3f2fd; color: #1565c0; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 12px 0; }
.form-grid label { display: flex; flex-direction: column; font-size: 13px; color: #555; gap: 4px; }
.form-grid input, .form-grid select, .form-grid textarea {
  padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit;
}
.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
.btn-primary { background: #5d4037; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #3e2723; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #eee; color: #333; border: 1px solid #ccc; padding: 8px 14px; border-radius: 4px; cursor: pointer; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 4px 8px; text-decoration: none; }
.editor-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #ddd; }
.editor-header h3 { margin: 0; color: #3e2723; }
.editor-header small { color: #666; font-family: monospace; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.anhang-toggle { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; color: #444; white-space: nowrap; }
.lock-hint { display: inline-block; margin-left: 8px; font-size: 12px; color: #b26a00; }
.tpl-select { font-size: 13px; padding: 4px 6px; border-radius: 4px; border: 1px solid #d0d7de; max-width: 180px; }
.stammdaten-box { margin-top: 18px; border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px 14px; background: #fafafa; }
.stammdaten-box > summary { cursor: pointer; color: #1565c0; }
.sd-group { margin: 12px 0; }
.sd-group h4 { margin: 6px 0; }
.sd-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid #eee; font-size: 14px; }
.sd-row small { color: #777; }
.sd-default { color: #b8860b; margin-left: 6px; }
.sd-add { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.sd-add input, .sd-add select { padding: 5px 7px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 13px; }
.sd-msg { margin-top: 6px; font-size: 13px; color: #1b5e20; }
.tabs { display: flex; gap: 4px; border-bottom: 2px solid #ddd; flex-wrap: wrap; }
.tab { background: none; border: none; padding: 10px 14px; cursor: pointer; border-bottom: 3px solid transparent; font-size: 13px; }
.tab.active { color: #5d4037; border-bottom-color: #5d4037; font-weight: 600; }
.tab-content { padding: 16px 0; }
.tab-content h4 { margin: 0 0 12px; color: #3e2723; }
.tbl { width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 13px; }
.tbl th, .tbl td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #eee; vertical-align: top; }
.tbl th { background: #f5f5f5; font-weight: 600; }
.tbl tr.nonliquet { background: #fafafa; color: #666; font-style: italic; }
.add-form { display: flex; gap: 8px; align-items: stretch; margin-top: 12px; flex-wrap: wrap; }
.add-form.column { flex-direction: column; }
.add-form input, .add-form select, .add-form textarea {
  padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit;
}
.hash { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-size: 11px; }
.sha-display { background: #e8f5e9; padding: 6px 10px; border-radius: 4px; font-size: 12px; }
.ja-nein { display: flex; gap: 12px; }
.check-row { display: flex; flex-direction: column; gap: 6px; padding: 8px 0; border-bottom: 1px solid #eee; }
.result-card { padding: 12px; border-radius: 4px; margin-top: 12px; border-left: 4px solid; }
.status-ok { background: #e8f5e9; border-color: #2e7d32; }
.status-vorsicht { background: #fff3e0; border-color: #ef6c00; }
.status-blockiert { background: #ffebee; border-color: #c62828; }
.befang-result { padding: 12px; margin: 12px 0; border-radius: 4px; border-left: 4px solid; }
.risiko-hoch { background: #ffebee; border-color: #c62828; }
.risiko-mittel { background: #fff3e0; border-color: #ef6c00; }
.risiko-niedrig { background: #fff8e1; border-color: #fbc02d; }
.risiko-keins { background: #e8f5e9; border-color: #2e7d32; }
.linter-warn { background: #fff3e0; border-left: 4px solid #ef6c00; padding: 8px 12px; margin: 6px 0; font-size: 12px; }
.linter-warn ul { margin: 6px 0 0 18px; }
.hon-summary { display: flex; gap: 16px; padding: 10px; background: #f5f5f5; border-radius: 4px; margin-bottom: 10px; font-weight: 600; }
.hint { color: #666; font-size: 12px; }
.missing-hint { color: #b26a00; margin-top: 6px; }
.field-error { display: block; color: #c62828; font-size: 12px; margin-top: 4px; }
.befang-note { margin-top: 10px; padding-top: 8px; border-top: 1px dashed rgba(0,0,0,.15); font-size: 12px; color: #555; }
.modal-bg, .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: white; padding: 20px; border-radius: 8px; max-width: 800px; width: 90%; max-height: 90vh; overflow-y: auto; }
.mapping-table { margin: 12px 0; display: flex; flex-direction: column; gap: 6px; }
.mapping-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; align-items: center; }
.mapping-token { background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mapping-row select { padding: 5px 7px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 13px; }
.vars-section { margin: 14px 0; }
.vars-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.vars-list { background: #1e1e1e; color: #e0e0e0; padding: 10px 12px; border-radius: 6px; font-size: 12px; max-height: 200px; overflow: auto; white-space: pre; }
.vars-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.vars-table th, .vars-table td { border: 1px solid #e0e0e0; padding: 5px 8px; text-align: left; vertical-align: top; }
.vars-table th { background: #f5f5f5; }
.vars-table code { background: #eef3fb; padding: 1px 5px; border-radius: 3px; white-space: nowrap; }
.vars-req { color: #c62828; font-weight: 600; }
.disclaimer-407a { background: #fff3e0; border-left: 4px solid #ef6c00; padding: 10px; margin: 8px 0; font-size: 12px; font-weight: 600; color: #bf360c; }
.mono { font-family: monospace; font-size: 11px; width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
.art-toggle { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; padding: 8px;
              background: #fafafa; border-radius: 4px; }
.toggle-opt { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border: 2px solid #ddd;
              border-radius: 4px; cursor: pointer; }
.toggle-opt.active { border-color: #5d4037; background: #efebe9; }
.toggle-opt input { margin: 0; }
.art-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px;
             font-weight: 600; margin-bottom: 12px; }
.art-badge.art-gericht { background: #ffebee; color: #c62828; }
.art-badge.art-privat { background: #e3f2fd; color: #1565c0; }
.sub-card { background: #fafafa; padding: 12px; border-radius: 4px; margin-bottom: 12px; }
.sub-card strong { display: block; margin-bottom: 6px; color: #3e2723; }
.risk-row { background: #fff3e0; }
.risk-badge { background: #ef6c00; color: white; padding: 2px 6px; border-radius: 10px; font-size: 11px; }
.log-class { padding: 8px; border-radius: 4px; margin-top: 8px; }
.log-system { background: #e3f2fd; }
.log-application { background: #e8f5e9; }
.log-network { background: #fff3e0; }
.log-unknown { background: #f5f5f5; color: #999; }
.hyp-akzeptiert { background: #e8f5e9; }
.hyp-verworfen { background: #ffebee; color: #999; text-decoration: line-through; }
.status-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-left: 8px; }
/* #670 Rich-Editor + Vollbild */
.editor-wrap { display: flex; flex-direction: column; gap: 4px; margin: 8px 0; }
.editor-header-row { display: flex; justify-content: space-between; align-items: center; }
.editor-header-row label { font-weight: 600; font-size: 13px; color: #555; }
.fullscreen-btn { background: #eee; border: 1px solid #ccc; cursor: pointer; padding: 2px 8px;
                  border-radius: 4px; font-size: 11px; }
.fullscreen-btn:hover { background: #d7ccc8; }
.fullscreen-close { position: fixed; top: 12px; right: 12px; z-index: 2001; background: #c62828;
                    color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.rich-textarea { width: 100%; min-height: 200px; padding: 12px; border: 1px solid #ccc;
                 border-radius: 4px; font: 14px/1.55 'Calibri', 'Segoe UI', sans-serif;
                 resize: vertical; box-sizing: border-box; }
.rich-textarea:focus { outline: 2px solid #5d4037; border-color: #5d4037; }
.rich-textarea.fullscreen { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                            z-index: 2000; padding: 60px 40px; font-size: 16px; line-height: 1.7;
                            border-radius: 0; }
/* #671 Help-Modal */
.help-btn { background: none; border: 1px solid #1565c0; color: #1565c0; border-radius: 50%;
            width: 22px; height: 22px; padding: 0; cursor: pointer; font-size: 13px; line-height: 1;
            margin-left: 6px; vertical-align: middle; }
.help-btn:hover { background: #1565c0; color: white; }
.help-modal { max-width: 700px; }
.help-modal h3 { color: #1565c0; }
.help-norm { background: #e3f2fd; padding: 8px 12px; border-radius: 4px; font-size: 13px; }
.help-section { margin: 12px 0; padding: 8px 0; }
.help-section strong { display: block; margin-bottom: 4px; }
.help-section p { margin: 0; line-height: 1.5; }
.help-fallstrick { background: #fff3e0; padding: 8px 12px; border-left: 3px solid #ef6c00; border-radius: 4px; }
.help-beispiel { background: #e8f5e9; padding: 8px 12px; border-left: 3px solid #2e7d32; border-radius: 4px; }
/* #690 DOCX-Vorschau */
.preview-modal { max-width: 900px; width: 90vw; max-height: 90vh; padding: 0; }
.preview-header { display: flex; justify-content: space-between; align-items: center;
                  padding: 14px 20px; border-bottom: 1px solid #ddd; background: #f5f5f5;
                  border-top-left-radius: 8px; border-top-right-radius: 8px; }
.preview-header h3 { margin: 0; }
.preview-header > div { display: flex; gap: 8px; }
.preview-body { padding: 40px 60px; overflow-y: auto; max-height: calc(90vh - 70px); }
.word-page { font: 11pt/1.5 'Calibri', 'Segoe UI', sans-serif; background: white; color: #222; }
.word-page .vertraulichkeit { text-align: center; color: #c62828; font-weight: bold; font-size: 13pt; }
.word-page .doc-title { text-align: center; font-size: 22pt; font-weight: bold; margin: 20px 0; }
.word-page h2 { color: #1565c0; font-size: 15pt; margin-top: 24px; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
.word-page h3 { font-size: 13pt; margin-top: 14px; color: #444; }
.word-page p { margin: 6px 0; }
.word-page .parteien { background: #fafafa; padding: 10px; border-left: 3px solid #1565c0; }
.word-page .parteien .dots { color: #aaa; letter-spacing: -0.5px; }
.word-page .parteien .gegen { display: inline-block; margin: 4px 0; padding-left: 40%; color: #999; }
.word-page table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 10pt; }
.word-page table th { background: #eef3f7; }
.word-page hr { border: none; border-top: 2px solid #1565c0; margin: 20px 0; }
.fliesstext-block { background: #f5f5f5; padding: 10px 14px; margin-top: 8px;
                    border-left: 3px solid #1565c0; border-radius: 4px; font-size: 12px; }
.fliesstext-block p { margin: 4px 0 0; line-height: 1.5; }
.fliesstext-edit { width: 100%; min-height: 180px; padding: 10px;
                   font: 13px/1.55 'Calibri', 'Segoe UI', sans-serif;
                   border: 1px solid #ccc; border-radius: 4px; resize: vertical;
                   margin-top: 6px; box-sizing: border-box; }
.fliesstext-edit:focus { outline: 2px solid #1565c0; border-color: #1565c0; }
</style>
