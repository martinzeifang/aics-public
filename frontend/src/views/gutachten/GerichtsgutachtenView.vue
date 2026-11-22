<template>
  <div class="gg-view">
    <div class="header">
      <div class="header-text">
        <h2>{{ $t('gutachten.gerichtsgutachtenView.gerichtsgutachtenBISGKonform') }}</h2>
        <p>{{ $t('gutachten.gerichtsgutachtenView.sachverstandigengutachtenNachDINENIS') }}</p>
      </div>
      <div class="header-actions-top">
        <button v-if="aktuell" class="btn-secondary" @click="openPreview">{{ $t('gutachten.gerichtsgutachtenView.vorschau') }}</button>
        <ModuleHelpButton module="gutachten" />
      </div>
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
            <!-- #2129 Konto-Verknüpfung (für Sichtbarkeits-Scoping) -->
            <select v-if="benutzerVerfuegbar" class="sd-user" :value="g.benutzer_id || ''"
                    @change="setzeGutachterBenutzer(g, ($event.target as HTMLSelectElement).value)"
                    :title="'Benutzerkonto verknüpfen'">
              <option value="">— kein Konto —</option>
              <option v-for="u in benutzerListe" :key="u.id" :value="u.id">{{ u.display_name || u.email || u.id }}</option>
            </select>
            <input v-else class="sd-user" :value="g.benutzer_id || ''" :placeholder="'Benutzer-ID (Konto)'"
                   @change="setzeGutachterBenutzer(g, ($event.target as HTMLInputElement).value)" />
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
          <button class="btn-secondary" @click="deleteProjekt">🗑</button>
        </div>
      </div>

      <!-- Tabs -->
      <GroupedModuleNav :groups="navGroups" v-model="tab" persist-key="gutachten-gerichts" />

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
      <!-- Tab: Prüfer & Normen (#2107) -->
      <div v-if="tab === 'pruefer'" class="tab-content">
        <!-- #2108 Prüfer-Register -->
        <h4>Prüfer (Mehr-Prüfer-Verfahren)</h4>
        <p class="hint">Hauptgutachter, Zweitprüfer und weitere Prüfer. Die Autorenschaft an
          Befunden/Beurteilungen und das gegenseitige Review beziehen sich auf diese Prüfer.</p>
        <table class="tbl" v-if="store.pruefer.length">
          <thead><tr><th>Name</th><th>Rolle</th><th></th></tr></thead>
          <tbody>
            <tr v-for="p in store.pruefer" :key="p.id">
              <td>{{ p.name }}</td>
              <td>{{ rolleLabel(p.rolle) }}</td>
              <td><button class="btn-link" @click="store.deletePruefer(aktuell.name, p.id)" :title="$t('common.delete')">🗑</button></td>
            </tr>
          </tbody>
        </table>
        <div class="add-form row">
          <select v-model="newPruefer.gutachter_profil_id" style="flex:1">
            <option :value="null">— Aus Profil (optional) —</option>
            <option v-for="g in store.gutachter" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
          <input v-model="newPruefer.name" :placeholder="$t('gutachten.gerichtsgutachtenView.phNameFrei')" style="flex:1" />
          <select v-model="newPruefer.rolle">
            <option v-for="r in PRUEFER_ROLLEN" :key="r.v" :value="r.v">{{ r.t }}</option>
          </select>
          <button class="btn-primary" @click="addPruefer">{{ $t('gutachten.gerichtsgutachtenView.hinzu') }}</button>
        </div>

        <!-- #2112 Hinterlegte Normen -->
        <h4 style="margin-top:24px">Hinterlegte Normen (Rechts-/Methodengrundlage)</h4>
        <p class="hint">Beim Privatgutachten tragen diese Normen die Grundlage statt der ZPO
          (z. B. DIN EN 16775, ISO/IEC, BSI IT-Grundschutz). Sie erscheinen im Export als
          „Methodische Grundlage".</p>

        <!-- #2128 Normtext-Hinweis: nur Orientierung vs. lizenzierter Volltext hinterlegt -->
        <div class="ki-hinweis" style="margin:12px 0">
          <strong>ℹ Normtexte sind urheberrechtlich geschützt.</strong> Zu ISO-/DIN-Normen
          liegt im Katalog nur eine <em>Orientierung</em> (Titel + Kurzbeschreibung) — <strong>kein
          lizenzierter Normtext</strong>. Die KI-Recherche zitiert daraus nichts und erfindet keine
          Abschnittsnummern. Hinterlege den Normtext unter <em>Administration → Framework-Bibliothek</em>
          (wie bei ISO 27001); danach nutzt die KI-Recherche ihn als belegbaren Normtext.
          <br><strong>OWASP</strong> (ASVS, WSTG, MASVS) und <strong>EU-Recht</strong> lassen sich dort
          <strong>direkt herunterladen</strong> (frei lizenziert); <strong>ISO/DIN</strong> sind
          kostenpflichtig (Beuth) → gekauftes PDF manuell hochladen.
        </div>
        <details v-if="store.normenStatus.length" style="margin-bottom:12px">
          <summary style="cursor:pointer">Normtext-Status ({{ store.normenStatus.filter((n:any)=>n.volltext_abschnitte>0).length }}/{{ store.normenStatus.filter((n:any)=>n.framework).length }} hinterlegt)</summary>
          <ul class="norm-status">
            <li v-for="n in store.normenStatus.filter((n:any)=>n.framework)" :key="n.id">
              <span v-if="n.volltext_abschnitte>0" class="pill pill-ok">📄 Volltext hinterlegt · {{ n.volltext_abschnitte }} Abschnitte</span>
              <span v-else class="pill pill-off">ℹ nur Orientierung</span>
              {{ n.titel }}
            </li>
          </ul>
        </details>
        <table class="tbl" v-if="store.projektNormen.length">
          <thead><tr><th>Norm</th><th>Version</th><th>Quelle</th><th></th></tr></thead>
          <tbody>
            <tr v-for="n in store.projektNormen" :key="n.id">
              <td>{{ n.norm_titel }}<small v-if="n.notiz" class="verfasser"> · {{ n.notiz }}</small></td>
              <td>{{ n.version }}</td>
              <td>{{ n.quelle }}</td>
              <td><button class="btn-link" @click="store.deleteProjektNorm(aktuell.name, n.id)" :title="$t('common.delete')">🗑</button></td>
            </tr>
          </tbody>
        </table>
        <div class="add-form row">
          <select v-model="newNorm.norm_id" style="flex:1">
            <option value="">— Aus Bibliothek wählen —</option>
            <option v-for="n in store.normen" :key="n.id" :value="n.id">{{ n.titel }}</option>
          </select>
          <input v-model="newNorm.norm_titel" :placeholder="$t('gutachten.gerichtsgutachtenView.phFreieNorm')" style="flex:1" :disabled="!!newNorm.norm_id" />
          <input v-model="newNorm.notiz" :placeholder="$t('gutachten.gerichtsgutachtenView.phNotizOptional')" style="flex:1" />
          <button class="btn-primary" @click="addNorm">{{ $t('gutachten.gerichtsgutachtenView.hinzu') }}</button>
        </div>

        <!-- #2130 Eigene Normen anlegen (Wizard) -->
        <details class="eigene-normen" style="margin-top:14px">
          <summary style="cursor:pointer"><strong>➕ Eigene Norm anlegen</strong>
            <span class="muted">— über den Katalog hinaus (erscheint im Picker + Status)</span></summary>
          <p class="hint" style="margin-top:8px">Lege eigene Normen/Methoden an, die hier nicht im Katalog stehen.
            Sie sind danach als Grundlage wählbar; ein erworbenes PDF lässt sich unter
            <em>Administration → Framework-Bibliothek</em> als Normtext hinterlegen.</p>
          <div class="cn-grid">
            <input v-model="newCustomNorm.titel" :placeholder="'Titel* (z. B. ISO/IEC 30111 — Vulnerability handling)'" />
            <input v-model="newCustomNorm.version" :placeholder="'Version/Jahr (z. B. 2019)'" />
            <input v-model="newCustomNorm.domain" :placeholder="'Domäne (z. B. forensik, sicherheit)'" />
            <input v-model="newCustomNorm.soll_kurz" :placeholder="'Kurzbeschreibung / Zweck'" />
            <button class="btn-primary" :disabled="!newCustomNorm.titel.trim()" @click="addCustomNorm">Norm anlegen</button>
          </div>
          <table class="tbl" v-if="store.customNormen.length" style="margin-top:10px">
            <thead><tr><th>Eigene Norm</th><th>Version</th><th>Normtext</th><th></th></tr></thead>
            <tbody>
              <tr v-for="c in store.customNormen" :key="c.id">
                <td>{{ c.titel }}<small v-if="c.soll_kurz" class="verfasser"> · {{ c.soll_kurz }}</small></td>
                <td>{{ c.version }}</td>
                <td>
                  <span v-if="customNormVolltext(c.framework) > 0" class="pill pill-ok">📄 {{ customNormVolltext(c.framework) }} Abschnitte</span>
                  <span v-else class="pill pill-off">ℹ nur Orientierung</span>
                </td>
                <td><button class="btn-link" @click="store.deleteCustomNorm(c.id)" :title="$t('common.delete')">🗑</button></td>
              </tr>
            </tbody>
          </table>
        </details>

        <!-- #2111 Mehrfach-Selbstprüfung -->
        <h4 style="margin-top:24px">Selbstprüfung je Prüfer</h4>
        <p class="hint">Jeder Prüfer legt seine Unabhängigkeits-/Befangenheits-Selbstprüfung ab;
          die anderen können sie gegenseitig bestätigen (ein Prüfer bestätigt nicht die eigene).</p>
        <div v-for="sp in store.selbstpruefungen" :key="sp.id" class="sd-row">
          <div style="flex:1">
            <strong>{{ prueferName(sp.pruefer_id) || ('Prüfer ' + sp.pruefer_id) }}</strong>:
            {{ sp.headline || sp.status }}
            <small v-if="(sp.bestaetigt || []).length" class="verfasser">
              · bestätigt durch {{ (sp.bestaetigt || []).map((b: any) => prueferName(b.pruefer_id)).filter(Boolean).join(', ') }}
            </small>
          </div>
          <select v-model="bestaetiger[sp.id]" style="width:auto">
            <option :value="null">bestätigen als …</option>
            <option v-for="p in store.pruefer.filter((x) => Number(x.id) !== Number(sp.pruefer_id))"
                    :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <button class="btn-link" :disabled="!bestaetiger[sp.id]" @click="bestaetigeSP(sp)">✓ bestätigen</button>
        </div>
        <div class="add-form row">
          <select v-model="newSP.pruefer_id" style="flex:1">
            <option :value="null">Prüfer …</option>
            <option v-for="p in store.pruefer" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <select v-model="newSP.status">
            <option value="bestanden">bestanden</option>
            <option value="hinweis">mit Hinweis</option>
            <option value="issues">Befangenheitsgründe</option>
          </select>
          <input v-model="newSP.headline" :placeholder="$t('gutachten.gerichtsgutachtenView.phErgebnisKurz')" style="flex:1" />
          <button class="btn-primary" @click="addSelbstpruefung">{{ $t('gutachten.gerichtsgutachtenView.hinzu') }}</button>
        </div>

        <!-- #2110 Gegenseitiges Review -->
        <h4 style="margin-top:24px">Gegenseitiges Review (Prüfvermerke)</h4>
        <p class="hint">Ein Prüfer prüft den Inhalt eines <em>anderen</em> Prüfers. Das eigene
          Werk lässt sich nicht reviewen (Vier-Augen-Prinzip).</p>
        <table class="tbl" v-if="store.itemreviews.length">
          <thead><tr><th>Inhalt</th><th>Prüfer</th><th>Status</th><th>Kommentar</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in store.itemreviews" :key="r.id">
              <td>{{ reviewObjektLabel(r.objekt_art, r.objekt_id) }}</td>
              <td>{{ prueferName(r.reviewer_pruefer_id) }}</td>
              <td>{{ r.status }}</td>
              <td>{{ r.kommentar }}</td>
              <td><button class="btn-link" @click="store.deleteItemreview(aktuell.name, r.id)" :title="$t('common.delete')">🗑</button></td>
            </tr>
          </tbody>
        </table>
        <div class="add-form row">
          <select v-model="newReview.objekt_art" @change="newReview.objekt_id = null">
            <option value="befund">Befund</option>
            <option value="beurteilung">Beurteilung</option>
            <option value="beweisfrage">Beweisfrage</option>
          </select>
          <select v-model="newReview.objekt_id" style="flex:1">
            <option :value="null">Inhalt wählen …</option>
            <option v-for="o in reviewObjekte" :key="o.id" :value="o.id">{{ o.label }}</option>
          </select>
          <select v-model="newReview.reviewer_pruefer_id" style="flex:1">
            <option :value="null">Reviewer (Prüfer) …</option>
            <option v-for="p in store.pruefer" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <select v-model="newReview.status">
            <option value="ok">in Ordnung</option>
            <option value="nacharbeit">Nacharbeit</option>
            <option value="offen">offen</option>
          </select>
          <input v-model="newReview.kommentar" placeholder="Kommentar" style="flex:1" />
          <button class="btn-primary" @click="addReview">{{ $t('gutachten.gerichtsgutachtenView.hinzu') }}</button>
        </div>
      </div>

      <!-- Tab: KI-Assistenten (#2114/#2122/#2123) -->
      <div v-if="tab === 'ki'" class="tab-content">
        <div class="ki-hinweis">
          <span class="ki-hinweis-icon">ℹ</span>
          <div>Alle KI-Ergebnisse sind <strong>Vorschläge</strong>. Der Sachverständige prüft,
            bearbeitet und verantwortet den Endtext (§ 407a / beim Privatgutachten DIN EN 16775).
            Zu ISO-/BSI-Normen gibt die KI nur Orientierung mit Prüfhinweis.</div>
        </div>
        <label class="check-row"><input type="checkbox" v-model="kiEgressOk" />
          Datenübermittlung an den KI-Provider bestätigen (erforderlich für die KI-Läufe).</label>

        <!-- #2115 Referenz-Dokumente -->
        <h4 style="margin-top:16px">Referenz-Dokumente</h4>
        <table class="tbl" v-if="store.dokumente.length">
          <thead><tr><th>Datei</th><th>Zeichen</th><th></th></tr></thead>
          <tbody>
            <tr v-for="d in store.dokumente" :key="d.id">
              <td>{{ d.dateiname }}<small v-if="!d.zeichen" class="verfasser"> · kein Text</small></td>
              <td>{{ d.zeichen }}</td>
              <td>
                <a :href="`/api/gutachten/gerichts/dokumente/${d.id}/download`" target="_blank" rel="noopener noreferrer" class="btn-link">⬇</a>
                <button class="btn-link" @click="store.deleteDokument(aktuell.name, d.id); ladeKiQuellen()" :title="$t('common.delete')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <input ref="dokUpload" type="file" accept=".pdf,.docx,.txt,.md" @change="onDokUpload" />

        <!-- #2116/#2122 Intelligente Recherche (Chat + Quellen) -->
        <h4 style="margin-top:24px">Intelligente Recherche</h4>
        <details class="ki-quellen" :open="quellenOffen">
          <summary @click="ladeKiQuellen()">Quellen auswählen (Dokumente, Rechtstexte, Normen)</summary>
          <div class="ki-quellen-grid">
            <div>
              <strong>Projekt-Dokumente</strong>
              <label v-for="d in verfuegbareQuellen.dokumente" :key="'d'+d.id" class="ki-q-item">
                <input type="checkbox" :value="d.id" v-model="quellenAuswahl.dokument_ids" /> {{ d.dateiname }}</label>
            </div>
            <div>
              <strong>Rechtstexte</strong>
              <label v-for="v in verfuegbareQuellen.verordnungen" :key="'v'+v.schluessel" class="ki-q-item">
                <input type="checkbox" :value="v.schluessel" v-model="quellenAuswahl.verordnungen" :disabled="!v.vorhanden" />
                {{ v.titel }}<small v-if="!v.vorhanden" class="verfasser"> · nicht eingelesen</small></label>
            </div>
            <div>
              <strong>Normen-Katalog</strong>
              <label v-for="n in verfuegbareQuellen.normen_katalog" :key="'n'+n.id" class="ki-q-item">
                <input type="checkbox" :value="n.id" v-model="quellenAuswahl.normen" /> {{ n.titel }}</label>
            </div>
          </div>
          <p class="hint">Ohne Auswahl werden die Projekt-Dokumente und die einschlägigen Normen automatisch herangezogen.</p>
        </details>
        <div class="ki-chat">
          <p v-if="!chatNachrichten.length" class="hint" style="text-align:center">Stelle eine Frage — die KI antwortet anhand der gewählten Quellen.</p>
          <div v-for="(m, i) in chatNachrichten" :key="i" :class="['chat-row', m.rolle]">
            <div class="chat-avatar">{{ m.rolle === 'assistant' ? '🤖' : '🧑' }}</div>
            <div class="chat-content">
              <div class="chat-head">
                <span class="chat-rolle">{{ m.rolle === 'assistant' ? 'KI-Assistent' : 'Sie' }}</span>
                <button v-if="m.rolle === 'assistant' && m.text" class="btn-link chat-copy" @click="kopiereChat(m, i)">{{ kopiertIdx === i ? '✓ kopiert' : '📋 kopieren' }}</button>
              </div>
              <ProsaText v-if="m.rolle === 'assistant'" :text="m.text || '…'" />
              <span v-else class="chat-user-text">{{ m.text }}</span>
              <div v-if="m.quellen && m.quellen.length" class="chat-quellen">🔎 {{ m.quellen.map((q: any) => q.dateiname || q.titel).join(', ') }}</div>
            </div>
          </div>
        </div>
        <div class="ki-composer">
          <textarea v-model="chatEingabe" rows="2" :placeholder="$t('gutachten.gerichtsgutachtenView.phKiFrage')"
                    @keydown.enter.exact.prevent="sendeRecherche"></textarea>
          <button class="btn-primary" :disabled="!chatEingabe.trim() || chatBusy || !kiEgressOk" @click="sendeRecherche">
            {{ chatBusy ? '…' : '➤ Senden' }}</button>
        </div>

        <!-- #2118/#2123 Beweisfragen-Assistent -->
        <h4 style="margin-top:24px">Beweisfragen-Assistent</h4>
        <p class="hint">Fließtext (Fall-/Auftragsbeschreibung) → Vorschläge für Beweisfragen.</p>
        <textarea v-model="beweisFliesstext" rows="4" style="width:100%" :placeholder="$t('gutachten.gerichtsgutachtenView.phKiFliesstext')"></textarea>
        <button class="btn-primary" :disabled="!beweisFliesstext.trim() || beweisBusy || !kiEgressOk" @click="erzeugeBeweisfragen">
          {{ beweisBusy ? 'Erzeuge …' : 'Vorschläge erzeugen' }}</button>
        <div v-if="beweisVorschlaege.length" class="sub-card" style="margin-top:12px">
          <div class="row" style="justify-content:space-between">
            <strong>{{ beweisVorschlaege.length }} Vorschläge — bearbeitbar</strong>
            <span>
              <button class="btn-link" @click="beweisAlle(true)">alle</button>
              <button class="btn-link" @click="beweisAlle(false)">keine</button>
            </span>
          </div>
          <div v-for="(v, i) in beweisVorschlaege" :key="i" class="bf-vorschlag">
            <input type="checkbox" v-model="v.checked" />
            <span class="bf-nr">{{ i + 1 }}.</span>
            <textarea v-model="v.text" rows="2" style="flex:1"></textarea>
          </div>
          <button class="btn-primary" @click="uebernehmeBeweisfragen">Ausgewählte als Beweisfragen übernehmen</button>
        </div>
      </div>

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
        <!-- #2120 Selbstcheck je Prüfer -->
        <label v-if="store.pruefer.length" class="check-row">Prüfer:
          <select v-model="selbstcheckPrueferId" style="width:auto">
            <option :value="null">— (ohne Prüfer-Zuordnung) —</option>
            <option v-for="p in store.pruefer" :key="p.id" :value="p.id">{{ p.name }} — {{ rolleLabel(p.rolle) }}</option>
          </select>
        </label>
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
            <tr v-for="(f, i) in store.beweisfragen" :key="f.id">
              <td>{{ f.nr }}</td>
              <td>{{ f.frage_text }}</td>
              <td>{{ f.antwort_kurz }}</td>
              <td>{{ f.antwort_text }}</td>
              <td>
                <button class="btn-link" :disabled="i === 0" :title="'nach oben'" @click="moveBeweisfrage(i, -1)">▲</button>
                <button class="btn-link" :disabled="i === store.beweisfragen.length - 1" :title="'nach unten'" @click="moveBeweisfrage(i, 1)">▼</button>
                <button class="btn-link" @click="editBF(f)" :title="$t('common.edit')">✏</button>
                <button class="btn-link" @click="store.deleteBeweisfrage(f.id, aktuell.name)" :title="$t('common.delete')">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <!-- #691 BF-Felder größer + vertikal -->
        <div class="add-form column">
          <div class="row">
            <label style="width:90px;">Nr
              <input v-model.number="newBF.nr" type="number" style="width:100%" />
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
              <td>{{ b.titel }}<small v-if="prueferName(b.autor_pruefer_id)" class="verfasser"> · {{ prueferName(b.autor_pruefer_id) }}</small></td>
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
          <select v-if="store.pruefer.length" v-model="newBefund.autor_pruefer_id">
            <option :value="null">Verfasser (Prüfer) …</option>
            <option v-for="p in store.pruefer" :key="p.id" :value="p.id">{{ p.name }} — {{ rolleLabel(p.rolle) }}</option>
          </select>
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
          <label>{{ $t('gutachten.gerichtsgutachtenView.beschreibungTatsachenOnly') }} <button class="btn-link" type="button" @click="openFormulierung('befund', _htmlToPlain(newBefund.beschreibung_text), (t) => newBefund.beschreibung_text = t)">✨ formulieren</button></label>
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
              <td>{{ u.titel }}<small v-if="prueferName(u.autor_pruefer_id)" class="verfasser"> · {{ prueferName(u.autor_pruefer_id) }}</small></td>
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
          <select v-if="store.pruefer.length" v-model="newBeurt.autor_pruefer_id">
            <option :value="null">Verfasser (Prüfer) …</option>
            <option v-for="p in store.pruefer" :key="p.id" :value="p.id">{{ p.name }} — {{ rolleLabel(p.rolle) }}</option>
          </select>
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
          <label>{{ $t('gutachten.gerichtsgutachtenView.sollWasDieNormVerlangt') }} <button class="help-btn" @click="showHelp('beurteilung.soll')">ℹ</button> <button class="btn-link" type="button" @click="openFormulierung('soll', _htmlToPlain(newBeurt.soll_text), (t) => newBeurt.soll_text = t)">✨ formulieren</button></label>
          <RichEditor v-model="newBeurt.soll_text" />
          <label>{{ $t('gutachten.gerichtsgutachtenView.istBefundVergleich') }} <button class="help-btn" @click="showHelp('beurteilung.ist')">ℹ</button> <button class="btn-link" type="button" @click="openFormulierung('ist', _htmlToPlain(newBeurt.ist_text), (t) => newBeurt.ist_text = t)">✨ formulieren</button></label>
          <RichEditor v-model="newBeurt.ist_text" />
          <label>{{ $t('gutachten.gerichtsgutachtenView.kausalitat') }} <button class="help-btn" @click="showHelp('beurteilung.kausalitaet')">ℹ</button> <button class="btn-link" type="button" @click="openFormulierung('kausalitaet', _htmlToPlain(newBeurt.kausalitaet_text), (t) => newBeurt.kausalitaet_text = t)">✨ formulieren</button></label>
          <RichEditor v-model="newBeurt.kausalitaet_text" />
          <label>{{ $t('gutachten.gerichtsgutachtenView.wurdigungJuraSperre') }} <button class="help-btn" @click="showHelp('beurteilung.wuerdigung')">ℹ</button> <button class="btn-link" type="button" @click="openFormulierung('wuerdigung', _htmlToPlain(newBeurt.bewertung_text), (t) => newBeurt.bewertung_text = t)">✨ formulieren</button></label>
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
          <select v-if="store.dokumente.length || store.finalExports.length" class="archiv-select" @change="asservatAusArchiv">
            <option value="">— oder aus Datei-Archiv verknüpfen —</option>
            <optgroup v-if="store.dokumente.length" label="Referenz-Dokumente">
              <option v-for="d in store.dokumente" :key="'d'+d.id" :value="'dok:'+d.id">{{ d.dateiname }}</option>
            </optgroup>
            <optgroup v-if="store.finalExports.length" label="Dateiablage">
              <option v-for="f in store.finalExports" :key="'f'+f.id" :value="'fin:'+f.id">{{ f.dateiname }}</option>
            </optgroup>
          </select>
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
        <!--
          #2097: Geprüft wird der **Inhalt**, nicht die Hülle. Bis v8.6.3 gab
          der Endpunkt 404, wenn keine Frist gesetzt war; der Store machte
          daraus `null`, und der Block blieb unsichtbar. Mit #2029 antwortet
          er **200 mit `{}`** — weil eine nicht gesetzte Frist der
          Normalzustand jedes neuen Gutachtens ist und kein Fehler. `{}` ist
          aber wahr, der Block rendert, und beide Werte sind `undefined`;
          vue-i18n lässt einen Platzhalter ohne Wert stehen. In der
          Oberfläche stand wörtlich „Archiv bis: {v0} ({v1} Tage
          verbleibend)".

          Der leere Zustand wird **benannt** und nicht verschwiegen: Eine
          fehlende Zeile sagt dem Anwender nicht, dass die Frist noch
          aussteht — der Knopf darunter schon, aber erst, wenn man ihn deutet.
        -->
        <div v-if="store.aufbewahrung?.archiv_bis_datum">
          <strong>{{ $t('gutachten.gerichtsgutachtenView.archivBis') }}</strong> {{ $t('gutachten.gerichtsgutachtenView.v0V1TageVerbleibend', { v0: store.aufbewahrung.archiv_bis_datum, v1: store.aufbewahrung.tage_verbleibend ?? '—' }) }}
        </div>
        <p v-else class="muted">{{ $t('gutachten.gerichtsgutachtenView.aufbewahrungNichtGesetzt') }}</p>
        <button class="btn-secondary" @click="setAufbew">{{ $t('gutachten.gerichtsgutachtenView.jahreAktivieren') }}</button>

        <h4 style="margin-top: 24px">{{ $t('gutachten.gerichtsgutachtenView.g6AnonymisierteVorschau') }}</h4>
        <button class="btn-secondary" @click="loadAnon">{{ $t('gutachten.gerichtsgutachtenView.anonymisieren') }}</button>
        <pre v-if="anonResult" class="mono" style="max-height:400px; overflow:auto; background:#f5f5f5; padding:8px">{{ JSON.stringify(anonResult, null, 2) }}</pre>
      </div>

      <!-- Tab: Validator -->
      <div v-if="tab === 'validator'" class="tab-content">
        <h4>{{ $t('gutachten.gerichtsgutachtenView.g5PreExportValidatorSprachLinter') }}</h4>
        <div class="sub-card" style="margin-bottom:16px">
          <strong>📄 Bericht erzeugen</strong>
          <div class="export-opts">
            <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.wennAusEntfalltKapitelVIIIAsservaten')">
              <input type="checkbox" v-model="includeAnhang" /> {{ $t('gutachten.gerichtsgutachtenView.anhang') }}</label>
            <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.methodeWerkzeugBeiBefundenKapIVDruck')">
              <input type="checkbox" v-model="includeMethodeWerkzeug" /> {{ $t('gutachten.gerichtsgutachtenView.methodeWerkzeug') }}</label>
            <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.zwischenuberschriftenSollIstKausalit')">
              <input type="checkbox" v-model="includeBeurtSubheadings" /> {{ $t('gutachten.gerichtsgutachtenView.sollIstKausalitatTitel') }}</label>
            <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.datumDerVerfahrensereignisseKapIIIDr')">
              <input type="checkbox" v-model="includeVerfahrenDatum" /> {{ $t('gutachten.gerichtsgutachtenView.verfahrenDatum') }}</label>
            <label class="anhang-toggle" :title="$t('gutachten.gerichtsgutachtenView.glossarImAnhangDrucken')">
              <input type="checkbox" v-model="includeGlossar" /> {{ $t('gutachten.gerichtsgutachtenView.glossar') }}</label>
          </div>
          <div class="bericht-actions">
            <select v-model="exportTemplateId" class="tpl-select" :title="$t('gutachten.gerichtsgutachtenView.wordVorlageFurExport')">
              <option :value="null">{{ $t('gutachten.gerichtsgutachtenView.standardLayout') }}</option>
              <option v-for="t in store.templates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
            <button class="btn-primary" @click="exportDocx">⬇ {{ $t('gutachten.gerichtsgutachtenView.dOCX') }}</button>
            <button class="btn-secondary" @click="exportArchiv">🗜 {{ $t('gutachten.gerichtsgutachtenView.archivZIP') }}</button>
          </div>
        </div>
        <div class="row">
          <button class="btn-primary" @click="runValidator">{{ $t('gutachten.gerichtsgutachtenView.validatorAusfuhren') }}</button>
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

    <!-- #2123 Formulierungshilfe — schlichter Prosa-Dialog -->
    <ModalRahmen v-if="formModal.open" titel="✨ Formulierungshilfe" breite="schmal" @close="formModal.open = false">
      <template #inhalt>
        <p class="hint">Stichworte des Sachverständigen → ausformulierter Vorschlag. Nichts wird automatisch übernommen.</p>
        <div class="sub-card"><em>{{ formModal.stichworte }}</em></div>
        <label v-if="!kiEgressOk" class="check-row"><input type="checkbox" v-model="kiEgressOk" /> Datenübermittlung an den KI-Provider bestätigen.</label>
        <button v-if="!formModal.gestartet" class="btn-primary" :disabled="!kiEgressOk" @click="startFormulierung">Ausformulieren</button>
        <textarea v-if="formModal.gestartet" v-model="formModal.text" rows="8" style="width:100%; margin-top:10px"></textarea>
      </template>
      <template #fuss>
        <button class="btn-secondary" @click="formModal.open = false">Abbrechen</button>
        <button v-if="formModal.gestartet" class="btn-primary" :disabled="formModal.busy || !formModal.text.trim()" @click="uebernehmeFormulierung">Übernehmen</button>
      </template>
    </ModalRahmen>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { KI_VORBEHALT } from '../../utils/aktionen'
import { useGerichtsgutachtenStore } from '../../stores/gerichtsgutachten'
import { authHeader } from '../../api/auth-token'
import RichEditor from '../../components/RichEditor.vue'
import { sanitizeHtml } from '../../utils/sanitizeHtml'
import WizardPromptModal from '../../components/shared/WizardPromptModal.vue'
import ModalRahmen from '../../components/shared/ModalRahmen.vue'
import ProsaText from '../../components/shared/ProsaText.vue'
import GroupedModuleNav from '../../components/shared/GroupedModuleNav.vue'
import { runSse } from '../../composables/useSseRun'
import { kopiere } from '../../utils/zwischenablage'
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
  { id: 'stammdaten', label: '📋 ' + uebersetze('gutachten.gerichtsgutachtenView.deckblatt') },
  { id: 'pruefer', label: '👥 Prüfer & Normen' },
  { id: 'ki', label: '🤖 ' + uebersetze('gutachten.gerichtsgutachtenView.kiAssistenten') },
  { id: 'selbstcheck', label: '🛡 ' + uebersetze('gutachten.gerichtsgutachtenView.selbstcheck') },
  { id: 'beweisfragen', label: '❓ II. Beweisfragen' },
  { id: 'befunde', label: '🔍 IV. Befunde' },
  { id: 'beurteilungen', label: '⚖ V. Beurteilungen' },
  { id: 'assets', label: '📦 ' + uebersetze('gutachten.gerichtsgutachtenView.asservaten') },
  { id: 'verfahren', label: '🗓 III. Verfahren' },
  { id: 'forensik', label: '🧰 ' + uebersetze('gutachten.gerichtsgutachtenView.forensikMACBTools') },
  { id: 'hypothesen', label: '🌳 ' + uebersetze('gutachten.gerichtsgutachtenView.hypothesenTree') },
  { id: 'peer', label: '👁 ' + uebersetze('gutachten.gerichtsgutachtenView.peerReview') },
  { id: 'validator', label: '✅ ' + uebersetze('gutachten.gerichtsgutachtenView.validatorExport') },
  { id: 'glossar', label: '📖 ' + uebersetze('gutachten.gerichtsgutachtenView.glossar') },
  { id: 'finalarchiv', label: '🗄 ' + uebersetze('gutachten.gerichtsgutachtenView.finalArchiv') },
]

const navGroups = [
  { id: 'ueberblick', label: 'Überblick', tabs: [
    { id: 'stammdaten', label: '📋 ' + uebersetze('gutachten.gerichtsgutachtenView.deckblatt') },
    { id: 'pruefer', label: '👥 Prüfer & Normen' },
    { id: 'selbstcheck', label: '🛡 ' + uebersetze('gutachten.gerichtsgutachtenView.selbstcheck') },
  ] },
  { id: 'inhalt', label: 'Gutachten', tabs: [
    { id: 'beweisfragen', label: '❓ II. Beweisfragen' },
    { id: 'verfahren', label: '🗓 III. Verfahren' },
    { id: 'befunde', label: '🔍 IV. Befunde' },
    { id: 'beurteilungen', label: '⚖ V. Beurteilungen' },
    { id: 'assets', label: '📦 ' + uebersetze('gutachten.gerichtsgutachtenView.asservaten') },
  ] },
  { id: 'forensik', label: 'Forensik', tabs: [
    { id: 'forensik', label: '🧰 ' + uebersetze('gutachten.gerichtsgutachtenView.forensikMACBTools') },
    { id: 'hypothesen', label: '🌳 ' + uebersetze('gutachten.gerichtsgutachtenView.hypothesenTree') },
  ] },
  { id: 'kigrp', label: 'KI-Assistenten', tabs: [
    { id: 'ki', label: '🤖 ' + uebersetze('gutachten.gerichtsgutachtenView.kiAssistenten') },
  ] },
  { id: 'bericht', label: 'Bericht', tabs: [
    { id: 'validator', label: '✅ ' + uebersetze('gutachten.gerichtsgutachtenView.validatorExport') },
    { id: 'glossar', label: '📖 ' + uebersetze('gutachten.gerichtsgutachtenView.glossar') },
    { id: 'peer', label: '👁 ' + uebersetze('gutachten.gerichtsgutachtenView.peerReview') },
  ] },
  { id: 'archivgrp', label: '🗄 ' + uebersetze('gutachten.gerichtsgutachtenView.finalArchiv'), tabs: [
    { id: 'finalarchiv', label: '🗄 ' + uebersetze('gutachten.gerichtsgutachtenView.finalArchiv') },
  ] },
]

const newForm = ref<any>({ name: '', gutachten_art: 'gericht',
  gericht: '', kammer: '', aktenzeichen: '', beweisbeschluss_datum: '',
  auftraggeber: '', auftrags_art: '', auftrags_datum: '', auftrags_nummer: '',
  vertraulichkeit: uebersetze('gutachten.gerichtsgutachtenView.sTRENGVERTRAULICH'), thema: '',
  klaeger_name: '', klaeger_anwalt: '', beklagter_name: '', beklagter_anwalt: '',
  sv_name: '', sv_zertifizierung: '', sv_anschrift: '', sv_kontakt: '' })

const newBF = ref<any>({ nr: 1, frage_text: '', antwort_kurz: '', antwort_text: '' })
const newBefund = ref<any>({ nr: '4.1', titel: '', methode: '', werkzeug_name: '',
  werkzeug_version: '', beschreibung_text: '', autor_pruefer_id: null })
const newBeurt = ref<any>({ nr: '5.1', titel: '', norm_id: '', norm_referenz: '',
  befund_ids_str: '', soll_text: '', ist_text: '', kausalitaet_text: '', bewertung_text: '',
  autor_pruefer_id: null })
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
    store.fetchNormen(), store.fetchNormenStatus(), store.fetchCustomNormen(), store.fetchSelbstcheckFragen(),
    fetchAuditSource(name), store.fetchTemplates(), store.fetchFinalExports(name),
    store.fetchGlossar(name),
    // #2107 Mehr-Prüfer-Verfahren
    store.fetchPruefer(name), store.fetchProjektNormen(name),
    store.fetchSelbstpruefung(name), store.fetchItemreviews(name),
    store.fetchDokumente(name),
  ])
  ladeKiQuellen()
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

const selbstcheckPrueferId = ref<number | null>(null)
const runSelbstcheck = async () => {
  selbstcheckResult.value = await store.runSelbstcheck(aktuell.value.name, selbstcheckAntw.value, aktuell.value.sv_name, selbstcheckPrueferId.value)
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
                       zeugen_text: b.zeugen_text, autor_pruefer_id: b.autor_pruefer_id ?? null }
  scrollToAddForm()
}
const editBeurt = (u: any) => {
  editId.value.beurt = u.id
  newBeurt.value = { nr: u.nr, titel: u.titel, norm_id: '', norm_referenz: u.norm_referenz,
                     befund_ids_str: (u.befund_ids || []).join(','),
                     soll_text: u.soll_text, ist_text: u.ist_text,
                     kausalitaet_text: u.kausalitaet_text, bewertung_text: u.bewertung_text,
                     autor_pruefer_id: u.autor_pruefer_id ?? null }
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

// ── #2107 Mehr-Prüfer-Verfahren ──────────────────────────────────────────────
const PRUEFER_ROLLEN = [
  { v: 'hauptgutachter', t: 'Hauptgutachter' },
  { v: 'zweitpruefer', t: 'Zweitprüfer' },
  { v: 'weiterer', t: 'Weiterer Prüfer' },
]
const rolleLabel = (r: string) => PRUEFER_ROLLEN.find(x => x.v === r)?.t || r
const prueferName = (id: any) =>
  store.pruefer.find((p: any) => Number(p.id) === Number(id))?.name || ''

const newPruefer = ref<any>({ name: '', rolle: 'zweitpruefer', gutachter_profil_id: null })
const addPruefer = async () => {
  if (!newPruefer.value.name && !newPruefer.value.gutachter_profil_id) return
  if (await store.savePruefer(aktuell.value.name, { ...newPruefer.value })) {
    newPruefer.value = { name: '', rolle: 'zweitpruefer', gutachter_profil_id: null }
  }
}

const newNorm = ref<any>({ norm_id: '', norm_titel: '', notiz: '' })
// #2130 Eigene Normen anlegen
const newCustomNorm = ref<any>({ titel: '', version: '', domain: '', soll_kurz: '' })
const addCustomNorm = async () => {
  if (!newCustomNorm.value.titel.trim()) return
  if (await store.createCustomNorm({ ...newCustomNorm.value })) {
    newCustomNorm.value = { titel: '', version: '', domain: '', soll_kurz: '' }
  }
}
const customNormVolltext = (framework: string) => {
  const s = store.normenStatus.find((n: any) => n.framework === framework)
  return s ? (s.volltext_abschnitte || 0) : 0
}
const addNorm = async () => {
  const data: any = { notiz: newNorm.value.notiz }
  if (newNorm.value.norm_id) {
    const lib = store.normen.find((n: any) => n.id === newNorm.value.norm_id)
    data.norm_id = newNorm.value.norm_id
    data.norm_titel = lib?.titel || ''
    data.version = lib?.version || ''
    data.quelle = 'bibliothek'
  } else {
    if (!newNorm.value.norm_titel) return
    data.norm_titel = newNorm.value.norm_titel
    data.quelle = 'frei'
  }
  if (await store.saveProjektNorm(aktuell.value.name, data)) {
    newNorm.value = { norm_id: '', norm_titel: '', notiz: '' }
  }
}

const newSP = ref<any>({ pruefer_id: null, status: 'bestanden', headline: '' })
const addSelbstpruefung = async () => {
  if (!newSP.value.pruefer_id) return
  if (await store.saveSelbstpruefung(aktuell.value.name, { ...newSP.value })) {
    newSP.value = { pruefer_id: null, status: 'bestanden', headline: '' }
  }
}
const bestaetiger = ref<any>({})  // sp.id -> pruefer_id
const bestaetigeSP = async (sp: any) => {
  const pid = bestaetiger.value[sp.id]
  if (!pid) return
  await store.bestaetigeSelbstpruefung(aktuell.value.name, sp.id, pid)
  bestaetiger.value[sp.id] = null
}

const newReview = ref<any>({ objekt_art: 'befund', objekt_id: null, reviewer_pruefer_id: null, status: 'ok', kommentar: '' })
const reviewObjekte = computed(() => {
  if (newReview.value.objekt_art === 'befund')
    return store.befunde.map((b: any) => ({ id: b.id, label: `${b.nr} ${b.titel}`, autor: b.autor_pruefer_id }))
  if (newReview.value.objekt_art === 'beurteilung')
    return store.beurteilungen.map((u: any) => ({ id: u.id, label: `${u.nr} ${u.titel}`, autor: u.autor_pruefer_id }))
  return store.beweisfragen.map((f: any) => ({ id: f.id, label: `Beweisfrage ${f.nr}`, autor: f.autor_pruefer_id }))
})
const reviewObjektLabel = (art: string, id: any) => {
  const quelle = art === 'befund' ? store.befunde : art === 'beurteilung' ? store.beurteilungen : store.beweisfragen
  const it: any = quelle.find((x: any) => Number(x.id) === Number(id))
  if (!it) return `${art} #${id}`
  return art === 'beweisfrage' ? `Beweisfrage ${it.nr}` : `${it.nr} ${it.titel}`
}
const addReview = async () => {
  if (!newReview.value.objekt_id || !newReview.value.reviewer_pruefer_id) return
  if (await store.saveItemreview(aktuell.value.name, { ...newReview.value })) {
    newReview.value = { objekt_art: newReview.value.objekt_art, objekt_id: null, reviewer_pruefer_id: null, status: 'ok', kommentar: '' }
  }
}

const asservatAusArchiv = (ev: Event) => {
  const el = ev.target as HTMLSelectElement
  const v = el.value
  if (!v) return
  const [typ, id] = v.split(':')
  const quelle: any[] = typ === 'dok' ? store.dokumente : store.finalExports
  const d = quelle.find((x: any) => String(x.id) === id)
  if (d) {
    newAsset.value.bezeichnung = d.dateiname || newAsset.value.bezeichnung
    newAsset.value.sha256 = d.sha256 || ''
    newAsset.value.original_dateiname = d.dateiname || ''
  }
  el.value = ''
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

// ── #2114/#2122/#2123 KI-Assistenten: Chat-Recherche, Formulierung, Beweisfragen ─
const dokUpload = ref<any>(null)
// Einmalige Egress-Bestätigung (#1519) für die KI-Direktläufe dieser Sitzung.
const kiEgressOk = ref(false)
// Verfügbare + ausgewählte Quellen (#2122)
const verfuegbareQuellen = ref<any>({ dokumente: [], verordnungen: [], normen_katalog: [] })
const quellenAuswahl = ref<any>({ dokument_ids: [], verordnungen: [], normen: [] })
const quellenOffen = ref(false)
const ladeKiQuellen = async () => {
  if (!aktuell.value?.name) return
  verfuegbareQuellen.value = (await store.kiQuellen(aktuell.value.name)) || verfuegbareQuellen.value
}

// Gemeinsamer Streaming-Lauf über /api/ai/run-stream (Egress bereits bestätigt).
const streamKi = async (prompt: string, onChunk: (t: string) => void) => {
  return await runSse('/api/ai/run-stream',
    { prompt, confirmed: true, egress_context: 'gutachten-ki', modul: 'gutachten' },
    (ev: string, data: any) => { if (ev === 'chunk' && data?.text) onChunk(data.text) })
}

// Chat-Recherche (#2122)
const chatNachrichten = ref<any[]>([])
const chatEingabe = ref('')
const chatBusy = ref(false)
const kopiertIdx = ref<number | null>(null)
const kopiereChat = async (m: any, i: number) => {
  if (await kopiere(m.text || '')) { kopiertIdx.value = i; setTimeout(() => { if (kopiertIdx.value === i) kopiertIdx.value = null }, 1500) }
}
const _quellenOderNull = () => {
  const a = quellenAuswahl.value
  if (!a.dokument_ids.length && !a.verordnungen.length && !a.normen.length) return null
  return { dokument_ids: a.dokument_ids, verordnungen: a.verordnungen, normen: a.normen }
}
const sendeRecherche = async () => {
  const frage = chatEingabe.value.trim()
  if (!frage || chatBusy.value || !kiEgressOk.value) return
  chatEingabe.value = ''
  chatNachrichten.value.push({ rolle: 'user', text: frage })
  const verlauf = chatNachrichten.value.map((m: any) => ({ rolle: m.rolle, text: m.text }))
  const res = await store.kiRecherchePrompt(aktuell.value.name, frage, verlauf, _quellenOderNull())
  if (!res) return
  const bubble: any = { rolle: 'assistant', text: '', quellen: res.quellen || [] }
  chatNachrichten.value.push(bubble)
  chatBusy.value = true
  const fin = await streamKi(res.prompt, (t: string) => { bubble.text += t })
  chatBusy.value = false
  if (fin?.ok && fin.text && fin.text.length >= bubble.text.length) bubble.text = fin.text
  else if (!fin?.ok) bubble.text = bubble.text || ('⚠ ' + (fin?.error || 'Kein Ergebnis'))
}

// Beweisfragen-Assistent (#2123)
const beweisFliesstext = ref('')
const beweisVorschlaege = ref<any[]>([])
const beweisBusy = ref(false)
const erzeugeBeweisfragen = async () => {
  if (!beweisFliesstext.value.trim() || beweisBusy.value || !kiEgressOk.value) return
  const prompt = await store.kiBeweisfragenPrompt(aktuell.value.name, beweisFliesstext.value.trim())
  if (!prompt) return
  beweisVorschlaege.value = []
  beweisBusy.value = true
  const fin = await streamKi(prompt, () => {})
  beweisBusy.value = false
  if (fin?.ok && fin.text) {
    const fragen = await store.kiBeweisfragenParse(aktuell.value.name, fin.text)
    beweisVorschlaege.value = (fragen || []).map((t: string) => ({ text: t, checked: true }))
  } else if (!fin?.ok) {
    store.error = fin?.error || 'Die KI lieferte kein Ergebnis.'
  }
}
const moveBeweisfrage = async (i: number, dir: number) => {
  const list = store.beweisfragen
  const j = i + dir
  if (j < 0 || j >= list.length) return
  const a: any = list[i], b: any = list[j]
  await store.saveBeweisfrage(aktuell.value.name, { ...a, nr: b.nr })
  await store.saveBeweisfrage(aktuell.value.name, { ...b, nr: a.nr })
}
const beweisAlle = (an: boolean) => beweisVorschlaege.value.forEach((v: any) => { v.checked = an })
const uebernehmeBeweisfragen = async () => {
  const gewaehlt = beweisVorschlaege.value.filter((v: any) => v.checked && v.text.trim())
  let nr = (store.beweisfragen?.length || 0) + 1
  for (const v of gewaehlt) {
    await store.saveBeweisfrage(aktuell.value.name, { nr: nr++, frage_text: v.text.trim(), antwort_kurz: '', antwort_text: '' })
  }
  beweisVorschlaege.value = []
}

// Formulierungshilfe (#2123): schlichter Prosa-Dialog (kein JSON-Rahmen)
const formModal = ref<any>({ open: false, feld: '', stichworte: '', busy: false, text: '', apply: null, gestartet: false })
const openFormulierung = (feld: string, stichworte: string, apply: (t: string) => void) => {
  if (!stichworte.trim()) return
  formModal.value = { open: true, feld, stichworte: stichworte.trim(), busy: false, text: '', apply, gestartet: false }
}
const startFormulierung = async () => {
  if (!kiEgressOk.value || formModal.value.busy) return
  const prompt = await store.kiFormulierungPrompt(aktuell.value.name, formModal.value.stichworte, formModal.value.feld)
  if (!prompt) return
  formModal.value.gestartet = true
  formModal.value.busy = true
  formModal.value.text = ''
  const fin = await streamKi(prompt, (t: string) => { formModal.value.text += t })
  formModal.value.busy = false
  if (fin?.ok && fin.text && fin.text.length >= formModal.value.text.length) formModal.value.text = fin.text
  else if (!fin?.ok) store.error = fin?.error || 'Die KI lieferte kein Ergebnis.'
}
const uebernehmeFormulierung = () => {
  if (formModal.value.apply && formModal.value.text.trim()) formModal.value.apply(formModal.value.text.trim())
  formModal.value = { open: false, feld: '', stichworte: '', busy: false, text: '', apply: null, gestartet: false }
}

const onDokUpload = async (ev: Event) => {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (!f) return
  const res = await store.uploadDokument(aktuell.value.name, f)
  if (res?.kein_text) {
    store.error = 'Dokument hochgeladen, aber kein durchsuchbarer Text gefunden (evtl. Scan ohne Texterkennung).'
  }
  if (dokUpload.value) dokUpload.value.value = ''
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
// #2129 Benutzerliste für die Gutachter↔Konto-Verknüpfung (nur Admin; sonst leer)
const benutzerListe = ref<any[]>([])
const benutzerVerfuegbar = computed(() => benutzerListe.value.length > 0)
const ladeBenutzer = async () => {
  try { benutzerListe.value = (await apiClient.get('/admin/users')).data || [] }
  catch { benutzerListe.value = [] }  // kein Admin → Textfeld-Fallback
}
const benutzerLabel = (id: string) => {
  const u = benutzerListe.value.find((x: any) => String(x.id) === String(id))
  return u ? (u.display_name || u.email || u.id) : id
}
const setzeGutachterBenutzer = async (g: any, benutzer_id: string) => {
  // Volles Objekt senden — ein Teil-Update würde die übrigen Felder leeren.
  await store.saveGutachter({ ...g, benutzer_id })
}
const onStammdatenOpen = (e: Event) => {
  if ((e.target as HTMLDetailsElement).open) {
    store.fetchGutachter(); store.fetchHilfspersonen(); store.fetchTemplates(); ladeBenutzer()
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
.header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); display: flex; align-items: flex-end; gap: 16px; }
.header-text { flex: 1; }
.header-actions-top { display: flex; align-items: center; gap: 8px; }
.header h2 { margin: 0; font-size: 22px; }
.header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: 13px; }

.back-link { color: #1565c0; text-decoration: none; font-size: 13px; }
.alert-error { background: #ffebee; padding: 10px; border-radius: 4px; color: #c62828; cursor: pointer; }
.card { background: var(--color-surface); padding: 16px 20px; border-radius: 6px; border: 1px solid var(--color-border); }
.proj-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin: 12px 0; }
.proj-tile { padding: 12px; background: #fafafa; border: 1px solid #ccc; border-radius: 6px;
             cursor: pointer; text-align: left; display: flex; flex-direction: column; gap: 4px; }
.proj-tile:hover { background: #fff; border-color: var(--color-primary); }
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
.btn-primary { display: inline-flex; align-items: center; justify-content: center; gap: 6px; background: var(--color-primary); color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: 500; cursor: pointer; }
.btn-primary:hover { background: var(--color-primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { display: inline-flex; align-items: center; justify-content: center; gap: 6px; background: var(--color-background); color: var(--color-primary); border: 1px solid var(--color-border); padding: 8px 14px; border-radius: 4px; font-weight: 500; cursor: pointer; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 4px 8px; text-decoration: none; }
.editor-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--color-border); }
.editor-header h3 { margin: 0; color: var(--color-primary-dark); }
.editor-header small { color: var(--color-text-secondary); font-family: monospace; }
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
.verfasser { color: #64748b; font-weight: normal; }
.export-opts { display: flex; flex-wrap: wrap; gap: 10px 18px; margin-top: 8px; }
.ki-hinweis { display: flex; gap: 10px; align-items: flex-start; background: #e3f2fd; border: 1px solid #90caf9; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #0d47a1; margin-bottom: 12px; }
.ki-hinweis-icon { font-size: 16px; line-height: 1.3; }
/* #2128 Normtext-Status */
.norm-status { list-style: none; padding-left: 0; margin: 8px 0 0; }
.norm-status li { padding: 3px 0; font-size: 13px; }
.norm-status .pill { display: inline-block; border-radius: 10px; padding: 1px 8px; font-size: 11px; margin-right: 8px; }
.norm-status .pill-ok { background: #e8f5e9; color: #1b5e20; border: 1px solid #a5d6a7; }
.norm-status .pill-off { background: #f5f5f5; color: #616161; border: 1px solid #e0e0e0; }
/* #2130 Eigene-Normen-Wizard */
.eigene-normen .cn-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.eigene-normen .cn-grid input { flex: 1 1 200px; }
.eigene-normen .pill { display: inline-block; border-radius: 10px; padding: 1px 8px; font-size: 11px; }
.eigene-normen .pill-ok { background: #e8f5e9; color: #1b5e20; border: 1px solid #a5d6a7; }
.eigene-normen .pill-off { background: #f5f5f5; color: #616161; border: 1px solid #e0e0e0; }
.archiv-select { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; font: inherit; }
.bericht-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 12px; }
.bericht-actions .tpl-select { max-width: 220px; }
.tabs { display: flex; gap: 4px; border-bottom: 2px solid var(--color-border); flex-wrap: wrap; }
.tab { background: none; border: none; padding: 10px 18px; cursor: pointer; border-bottom: 3px solid transparent; font-size: 14px; color: var(--color-text-secondary); }
.tab.active { color: var(--color-primary); border-bottom-color: var(--color-primary); background: var(--color-background); font-weight: 600; }
.tab-content { padding: 16px 0; }
.tab-content h4 { margin: 0 0 12px; color: var(--color-primary-dark); }
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
.modal { background: var(--color-surface); padding: 20px; border-radius: 8px; max-width: 800px; width: 90%; max-height: 90vh; overflow-y: auto; }
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
.toggle-opt.active { border-color: var(--color-primary); background: #efebe9; }
.toggle-opt input { margin: 0; }
.art-badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px;
             font-weight: 600; margin-bottom: 12px; }
.art-badge.art-gericht { background: #ffebee; color: #c62828; }
.art-badge.art-privat { background: #e3f2fd; color: #1565c0; }
.sub-card { background: #fafafa; padding: 12px; border-radius: 4px; margin-bottom: 12px; }
.sub-card strong { display: block; margin-bottom: 6px; color: var(--color-primary-dark); }
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
.rich-textarea:focus { outline: 2px solid var(--color-primary); border-color: var(--color-primary); }
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
                  padding: 14px 20px; border-bottom: 1px solid var(--color-border); background: #f5f5f5;
                  border-top-left-radius: 8px; border-top-right-radius: 8px; }
.preview-header h3 { margin: 0; }
.preview-header > div { display: flex; gap: 8px; }
.preview-body { padding: 40px 60px; overflow-y: auto; max-height: calc(90vh - 70px); }
.word-page { font: 11pt/1.5 'Calibri', 'Segoe UI', sans-serif; background: var(--color-surface); color: #222; }
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

/* #2114/#2122/#2123 KI-Assistenten */
.ki-quellen { margin: 8px 0; border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 12px; }
.ki-quellen summary { cursor: pointer; color: var(--color-primary); }
.ki-quellen-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 10px; }
.ki-q-item { display: block; font-size: 13px; margin: 3px 0; }
.ki-chat { margin: 12px 0; max-height: 460px; overflow-y: auto; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 10px; }
.chat-row { display: flex; gap: 14px; padding: 16px 18px; align-items: flex-start; }
.chat-row + .chat-row { border-top: 1px solid var(--color-border); }
.chat-row.assistant { background: var(--color-background); }
.chat-avatar { width: 30px; height: 30px; border-radius: 6px; display: flex; align-items: center; justify-content: center; background: var(--color-surface); border: 1px solid var(--color-border); flex-shrink: 0; font-size: 16px; }
.chat-row.assistant .chat-avatar { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.chat-content { flex: 1; min-width: 0; font-size: 14px; line-height: 1.55; }
.chat-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 4px; }
.chat-rolle { font-size: 12px; font-weight: 700; color: var(--color-text-primary); }
.chat-copy { font-size: 12px; }
.chat-user-text { white-space: pre-wrap; }
.chat-quellen { font-size: 12px; color: var(--color-text-secondary); margin-top: 8px; border-top: 1px dashed var(--color-border); padding-top: 6px; }
.ki-composer { display: flex; gap: 8px; align-items: flex-end; margin-top: 8px; border: 1px solid var(--color-border); border-radius: 10px; padding: 8px; background: var(--color-surface); }
.ki-composer textarea { flex: 1; border: none; resize: vertical; font: inherit; outline: none; background: transparent; }
.bf-vorschlag { display: flex; gap: 10px; align-items: flex-start; margin: 8px 0; }
.bf-nr { min-width: 22px; text-align: right; color: var(--color-text-secondary); font-weight: 600; padding-top: 7px; }
.modal-overlay { position: fixed; inset: 0; background: rgba(15,23,42,.6); display: flex; align-items: center; justify-content: center; z-index: 2000; padding: 16px; }
.modal-card { background: var(--color-surface); border-radius: 10px; padding: 22px; width: 100%; max-width: 560px; box-shadow: var(--shadow-lg); }
.modal-card h3 { margin: 0 0 10px; color: var(--color-primary-dark); }

</style>
