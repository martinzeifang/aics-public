<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>{{ $t('dsgvo.dSGVOPflichtDokuPanel.dSGVODokumentationHierStarten') }}</h3>
      <p>{{ $t('dsgvo.dSGVOPflichtDokuPanel.dieDSGVOVerlangtVonVerantwortlichenE') }}
        <strong>{{ $t('common.dieseSeiteIstDerErsteSchritt') }}</strong>.</p>
      <div class="workflow">
        <strong>{{ $t('common.reihenfolge') }}</strong>
        <ol>
          <li><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d1VVT') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.artVerarbeitungstatigkeitenErfassen') }}</li>
          <li><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d2TOM') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.artSchutzmassnahmenDokumentieren') }}</li>
          <li><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d3DSFA') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.artFolgenabschatzungBeiHohemRisiko') }}</li>
          <li><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d4AVV') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.artAuftragsverarbeiterTracken') }}</li>
          <li><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d5Datenpannen') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.artRegisterMitHMeldung') }}</li>
          <li>{{ $t('dsgvo.dSGVOPflichtDokuPanel.wizards') }} <strong>D6-D9</strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.rechtsgrundlageBranchenTemplateDaten') }}</li>
        </ol>
      </div>
    </div>

    <div v-if="status" class="status-grid">
      <div v-for="b in statusItems" :key="b.key" :class="['status-card', b.ok ? 'ok' : 'todo']">
        <div class="status-icon">{{ b.ok ? '✅' : '⚠️' }}</div>
        <div class="status-label">{{ b.label }}</div>
        <div class="status-detail">{{ b.detail }}</div>
      </div>
    </div>

    <!-- D1 VVT -->
    <details class="section" open>
      <summary><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d1VVTArt') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.v0Verarbeitungen', { v0: store.vvt.length }) }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.verzeichnisAllerVerarbeitungstatigke') }} <strong>D6</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.bestimmtAutomatischDieRechtsgrundlag') }}
        </div>
        <div class="quick-actions">
          <button class="btn-primary" @click="openVvtWizard()">{{ $t('dsgvo.dSGVOPflichtDokuPanel.neuenVVTEintragErstellen') }}</button>
          <small class="hint">{{ $t('dsgvo.dSGVOPflichtDokuPanel.gefuhrterAnlegeAssistentMitErklarung') }}</small>
        </div>
        <!-- #1101: Rollen-Filter Art. 30(1)/30(2) -->
        <div class="vvt-rolle-filter">
          <span class="filter-label">{{ $t('dsgvo.dSGVOPflichtDokuPanel.rolle') }}</span>
          <button
            class="pill-btn" :class="{ active: store.vvtRolleFilter === '' }"
            @click="store.setVvtRolleFilter('')">{{ $t('common.alle') }}</button>
          <button
            class="pill-btn" :class="{ active: store.vvtRolleFilter === 'verantwortlicher' }"
            @click="store.setVvtRolleFilter('verantwortlicher')">{{ $t('dsgvo.dSGVOPflichtDokuPanel.verantwortlicher') }}</button>
          <button
            class="pill-btn" :class="{ active: store.vvtRolleFilter === 'auftragsverarbeiter' }"
            @click="store.setVvtRolleFilter('auftragsverarbeiter')">{{ $t('dsgvo.dSGVOPflichtDokuPanel.auftragsverarbeiter') }}</button>
        </div>
        <table v-if="store.vvt.length">
          <thead><tr><th>ID</th><th>{{ $t('common.rolle') }}</th><th>{{ $t('common.name') }}</th><th>{{ $t('common.zweck') }}</th><th>{{ $t('common.rechtsgrundlage') }}</th><th>{{ $t('dsgvo.dSGVOPflichtDokuPanel.dSFA') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="v in store.vvt" :key="v.id">
              <td><code>{{ v.vvt_id }}</code></td>
              <td>
                <span class="rolle-pill" :class="(v.rolle || 'verantwortlicher')">
                  {{ (v.rolle || 'verantwortlicher') === 'auftragsverarbeiter' ? 'AV (30(2))' : 'V (30(1))' }}
                </span>
              </td>
              <td>{{ v.name }}</td>
              <td>{{ truncate(v.zweck, 80) }}</td>
              <td>{{ v.rechtsgrundlage }}<template v-if="v.art9_grundlage"> · {{ v.art9_grundlage }}</template></td>
              <td>
                <span v-if="Number(v.dsfa_trigger)" class="dsfa-flag" :title="$t('dsgvo.dSGVOPflichtDokuPanel.dSFAPflichtArt')">{{ $t('dsgvo.dSGVOPflichtDokuPanel.dSFA2') }}</span>
                <span v-else class="hint">—</span>
              </td>
              <td>
                <button class="btn-link" @click="openVvtWizard(v)" :title="$t('common.edit')">✏️</button>
                <button class="btn-link" @click="openRgWizard(v)" :title="$t('dsgvo.dSGVOPflichtDokuPanel.rechtsgrundlageWizard')">🤖</button>
                <button class="btn-link" @click="store.deleteVvt(v.id)" :title="$t('common.delete')">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="hint" style="margin-top: 12px;">{{ $t('dsgvo.dSGVOPflichtDokuPanel.nochKeineVVTEintrage') }}</p>
      </div>
    </details>

    <!-- D2 TOM — Übersicht + Verweis auf TOM-Katalog (#1115) -->
    <details class="section">
      <summary><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d2TOMArt') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.imTOMKatalogGepflegt') }}</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.technischeUndOrganisatorischeMassnah') }} <strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.tOMKatalog') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.gepflegtEntlangDerSDMGewahrleistungs') }} <strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.wirksamkeitsuberprufung') }}</strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.hierInDerPflichtDokuGibtEsNurDieUber') }}
        </div>
        <div class="d2-jump">
          <button class="btn-primary" @click="emit('open-tab', 'tom-katalog')">{{ $t('dsgvo.dSGVOPflichtDokuPanel.zumTOMKatalogArtSDM') }}</button>
        </div>
        <details v-if="store.tom.length" class="legacy">
          <summary>{{ $t('dsgvo.dSGVOPflichtDokuPanel.altTOMEintrageReadOnlyLegacyV0', { v0: store.tom.length }) }}</summary>
          <table>
            <thead><tr><th>{{ $t('common.kategorie') }}</th><th>{{ $t('common.massnahme') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('common.verantwortlich') }}</th></tr></thead>
            <tbody>
              <tr v-for="t in store.tom" :key="t.id">
                <td>{{ t.kategorie }}</td>
                <td>{{ t.massnahme }}</td>
                <td><span :class="`status-pill st-${t.umsetzungsstatus}`">{{ t.umsetzungsstatus }}</span></td>
                <td>{{ t.verantwortlich }}</td>
              </tr>
            </tbody>
          </table>
        </details>
      </div>
    </details>

    <!-- D3 DSFA -->
    <details class="section">
      <summary><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d3DSFAArt') }}</strong> ({{ store.dpia.length }})</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.eineDatenschutzFolgenabschatzungArtI') }} <strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.ubersicht') }}</strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.jedeDSFAWirdIm') }} <strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.gefuhrtenDSFAAssistenten') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.bearbeitetSchwellwertanalyseBeschrei') }}
        </div>
        <div class="d3-actions">
          <button class="btn-primary" @click="startDsfaAssistent">{{ $t('dsgvo.dSGVOPflichtDokuPanel.neueDSFAImAssistentenStarten') }}</button>
        </div>
        <table>
          <thead><tr><th>ID</th><th>{{ $t('common.titel') }}</th><th>{{ $t('dsgvo.dSGVOPflichtDokuPanel.restrisiko') }}</th><th>{{ $t('common.status') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="d in store.dpia" :key="d.id">
              <td><code>{{ d.dpia_id }}</code></td>
              <td>{{ d.titel }}</td>
              <td><span :class="`risk-pill rsk-${d.restrisiko}`">{{ d.restrisiko }}</span></td>
              <td>{{ d.status }}</td>
              <td>
                <button class="btn-link" @click="openDsfaDetail(d)" :title="$t('dsgvo.dSGVOPflichtDokuPanel.dSFADetailsArtAD')">🔎</button>
                <button class="btn-link" @click="store.deleteDpia(d.id)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- DSFA-Detailansicht: Art. 35(7)a+b lokal + Risiken(c)/Maßnahmen(d) read-only (#1085) -->
        <DSFADetailPanel
          v-if="selectedDsfa"
          :dpia="selectedDsfa"
          @close="closeDsfaDetail"
        />
      </div>
    </details>

    <!-- D4 AVV -->
    <details class="section">
      <summary><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d4AVVTrackerArt') }}</strong> ({{ store.avv.length }})</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.auftragsverarbeitungsVertragProDiens') }}
        </div>
        <div class="form-grid">
          <input v-model="avvForm.auftragsverarbeiter" :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.auftragsverarbeiter2')" />
          <input v-model="avvForm.leistung" :placeholder="$t('common.leistung')" />
          <label><input type="checkbox" v-model="avvForm.avv_vorhanden" /> {{ $t('dsgvo.dSGVOPflichtDokuPanel.aVVUnterschrieben') }}</label>
          <input v-model="avvForm.avv_url" :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.aVVURL')" />
          <input v-model="avvForm.avv_datum" type="date" />
          <label><input type="checkbox" v-model="avvForm.drittland" /> {{ $t('common.drittland') }}</label>
          <select v-model="avvForm.drittland_garantie">
            <option value="">{{ $t('dsgvo.dSGVOPflichtDokuPanel.garantieWahlen') }}</option>
            <option value="adaequanz">{{ $t('dsgvo.dSGVOPflichtDokuPanel.angemessenheitsbeschluss') }}</option>
            <option value="SCC">{{ $t('dsgvo.dSGVOPflichtDokuPanel.standardvertragsklauselnSCC') }}</option>
            <option value="BCR">{{ $t('dsgvo.dSGVOPflichtDokuPanel.bindingCorporateRules') }}</option>
          </select>
          <button class="btn-primary" @click="addAvv">{{ $t('dsgvo.dSGVOPflichtDokuPanel.hinzufugen') }}</button>
        </div>
        <table>
          <thead><tr><th>{{ $t('dsgvo.dSGVOPflichtDokuPanel.vendor') }}</th><th>{{ $t('common.leistung') }}</th><th>{{ $t('dsgvo.dSGVOPflichtDokuPanel.aVV') }}</th><th>{{ $t('common.drittland') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in store.avv" :key="a.id">
              <td>{{ a.auftragsverarbeiter }}</td>
              <td>{{ a.leistung }}</td>
              <td>{{ a.avv_vorhanden ? '✓' : '✗' }} {{ a.avv_datum || '' }}</td>
              <td>{{ a.drittland ? `${a.drittland_garantie || '⚠️'}` : '—' }}</td>
              <td><button class="btn-link" @click="store.deleteAvv(a.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- D5 Datenpannen -->
    <details class="section">
      <summary><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.d5DatenpannenArt') }}</strong> ({{ store.datenpannen.length }})</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>{{ $t('common.worumGehtS') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.registerAllerDatenpannenPflichtMeldu') }} <strong>D8</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.generiertDieMeldungstexte') }}
        </div>
        <div class="form-grid">
          <input v-model="panneForm.panne_id" :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.panneID')" />
          <input v-model="panneForm.titel" :placeholder="$t('common.titel')" />
          <input v-model="panneForm.festgestellt_am" type="date" />
          <select v-model="panneForm.art">
            <option value="vertraulichkeit">{{ $t('common.vertraulichkeit') }}</option>
            <option value="integritaet">{{ $t('dsgvo.dSGVOPflichtDokuPanel.integritat') }}</option>
            <option value="verfuegbarkeit">{{ $t('dsgvo.dSGVOPflichtDokuPanel.verfugbarkeit') }}</option>
          </select>
          <input v-model.number="panneForm.betroffene_anzahl" type="number" :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.anzahlBetroffene')" />
          <select v-model="panneForm.risikoeinschaetzung">
            <option value="gering">{{ $t('dsgvo.dSGVOPflichtDokuPanel.gering') }}</option>
            <option value="mittel">{{ $t('common.mittel') }}</option>
            <option value="hoch">{{ $t('common.hoch') }}</option>
          </select>
          <label><input type="checkbox" v-model="panneForm.meldung_aufsicht_pflicht" /> {{ $t('dsgvo.dSGVOPflichtDokuPanel.hMeldungAnAufsicht') }}</label>
          <button class="btn-primary" @click="addPanne">{{ $t('dsgvo.dSGVOPflichtDokuPanel.hinzufugen') }}</button>
        </div>
        <table>
          <thead><tr><th>ID</th><th>{{ $t('common.titel') }}</th><th>{{ $t('dsgvo.dSGVOPflichtDokuPanel.festgestellt') }}</th><th>{{ $t('common.risiko') }}</th><th>{{ $t('common.status') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="p in store.datenpannen" :key="p.id">
              <td><code>{{ p.panne_id }}</code></td>
              <td>{{ p.titel }}</td>
              <td>{{ p.festgestellt_am }}</td>
              <td><span :class="`risk-pill rsk-${p.risikoeinschaetzung}`">{{ p.risikoeinschaetzung }}</span></td>
              <td>{{ p.status }}</td>
              <td>
                <button class="btn-link" @click="openPanneMeldungWizard(p)">🤖 D8</button>
                <button class="btn-link" @click="store.deletePanne(p.id)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- Phase B: KI-Wizards — jetzt im Assistenten-Tab (#1083) -->
    <details class="section wizards" open>
      <summary><strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.kIAssistenten') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.rechtsgrundlageBranchenDatenpannenBe') }}</summary>
      <div class="section-body">
        <p class="assistenten-pointer">
          {{ $t('dsgvo.dSGVOPflichtDokuPanel.dieGefuhrtenKIAssistentenD6Rechtsgru') }} <strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.assistenten') }}</strong>.
        </p>
        <button class="btn-primary" @click="emit('open-assistenten')">{{ $t('common.zumAssistenten') }}</button>
      </div>
    </details>

    <!-- VVT-Anlege-Wizard (#587) -->
    <div v-if="vvtWizard.open" class="wizard-modal-overlay" @mousedown.self="closeVvtWizard">
      <div class="wizard-modal vvt-modal">
        <h3>{{ vvtWizard.editing ? $t('dsgvo.dSGVOPflichtDokuPanel.vVTEintragBearbeiten') : $t('dsgvo.dSGVOPflichtDokuPanel.neuenVVTEintragErstellen') }}</h3>
        <p class="hint">Verzeichnis nach Art. 30 DSGVO — Pflicht für alle Verantwortlichen (auch KMU mit > {{ $t('dsgvo.dSGVOPflichtDokuPanel.mAOderBesondereDatenkategorien') }}</p>

        <fieldset>
          <legend>{{ $t('dsgvo.dSGVOPflichtDokuPanel.rolleArtDSGVO') }}</legend>
          <small class="hint">{{ $t('dsgvo.dSGVOPflichtDokuPanel.artGiltFur') }} <strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.verantwortliche') }}</strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.artFur') }} <strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.auftragsverarbeiter2') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.diePflichtfelderUnterscheidenSich') }}</small>
          <div class="rolle-toggle">
            <label class="rolle-opt" :class="{ active: vvtWizard.data.rolle === 'verantwortlicher' }">
              <input type="radio" value="verantwortlicher" v-model="vvtWizard.data.rolle" />
              {{ $t('dsgvo.dSGVOPflichtDokuPanel.verantwortlicherArt') }}
            </label>
            <label class="rolle-opt" :class="{ active: vvtWizard.data.rolle === 'auftragsverarbeiter' }">
              <input type="radio" value="auftragsverarbeiter" v-model="vvtWizard.data.rolle" />
              {{ $t('dsgvo.dSGVOPflichtDokuPanel.auftragsverarbeiterArt') }}
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>{{ $t('dsgvo.dSGVOPflichtDokuPanel.grunddaten') }}</legend>
          <div class="vvt-grid">
            <label>{{ $t('dsgvo.dSGVOPflichtDokuPanel.vVTID') }} <span class="req">*</span>
              <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.eindeutigeKennzeichnungZB') }} <code>VVT-001</code>{{ $t('dsgvo.dSGVOPflichtDokuPanel.wirdInDSFAAVVReferenziert') }}</small>
              <input v-model="vvtWizard.data.vvt_id" placeholder="VVT-001" />
            </label>
            <label>{{ $t('dsgvo.dSGVOPflichtDokuPanel.nameDerVerarbeitung') }} <span class="req">*</span>
              <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.kurzeSprechendeBezeichnungZBFirmenst') }}</small>
              <input v-model="vvtWizard.data.name" placeholder="z.B. CRM-Firmenstammdaten" />
            </label>
          </div>
          <label class="full">{{ $t('dsgvo.dSGVOPflichtDokuPanel.zweckDerVerarbeitung') }} <span class="req">*</span>
            <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.warumWerdenDieseDatenVerarbeitetKonk') }}</small>
            <textarea v-model="vvtWizard.data.zweck" rows="3"
              :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.zBVertragsabwicklungMitFirmenRechnun')" />
          </label>
        </fieldset>

        <fieldset>
          <legend>{{ $t('dsgvo.dSGVOPflichtDokuPanel.rechtsgrundlageArtDSGVO') }}</legend>
          <small class="hint">{{ $t('dsgvo.dSGVOPflichtDokuPanel.tippWizard') }} <strong>D6</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.kannDiePassendeRechtsgrundlageAutoma') }}</small>
          <div class="vvt-grid">
            <label>{{ $t('common.rechtsgrundlage') }}
              <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.welcherBuchstabeVonArtBeiBesonderenD') }}</small>
              <!-- #1890: Die Liste kommt vom Server (dsgvo/vvt_katalog).
                   Hier stand sie zweimal — und die für Art. 9 war
                   unvollständig (d, e, f fehlten). -->
              <select v-model="vvtWizard.data.rechtsgrundlage">
                <option value="">{{ $t('dsgvo.dSGVOPflichtDokuPanel.wahlen') }}</option>
                <option v-for="e in art6" :key="e.lit" :value="e.wert">
                  {{ e.wert }} — {{ e.label }}
                </option>
              </select>
            </label>
            <label>{{ $t('dsgvo.dSGVOPflichtDokuPanel.artGrundlageBesondereKategorien') }}
              <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.nurBeiBesonderenDatenkategorienGesun') }}</small>
              <select v-model="vvtWizard.data.art9_grundlage">
                <option value="">{{ $t('dsgvo.dSGVOPflichtDokuPanel.keineBesondereKategorie') }}</option>
                <option v-for="e in art9" :key="e.lit" :value="e.wert">
                  {{ e.wert }} — {{ e.label }}
                </option>
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>{{ $t('dsgvo.dSGVOPflichtDokuPanel.betroffeneDatenkategorien') }}</legend>
          <label class="full">{{ $t('dsgvo.dSGVOPflichtDokuPanel.kategorienBetroffenerPersonen') }}
            <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.werIstBetroffenZBFirmenMitarbeiterIn') }}</small>
            <textarea v-model="vvtWizard.data.betroffene_kategorien" rows="2"
              :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.firmenB2BB2CInteressentenEhemaligeFi')" />
          </label>
          <label class="full">{{ $t('dsgvo.dSGVOPflichtDokuPanel.kategorienPersonenbezogenerDaten') }}
            <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.welcheDatenNameAdresseKontaktVertrag') }}</small>
            <textarea v-model="vvtWizard.data.datenkategorien" rows="2"
              :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.nameAnschriftEMailTelefonnummerVertr')" />
          </label>
        </fieldset>

        <fieldset>
          <legend>{{ $t('dsgvo.dSGVOPflichtDokuPanel.empfangerDrittland') }}</legend>
          <label class="full">{{ $t('dsgvo.dSGVOPflichtDokuPanel.empfangerInternExtern') }}
            <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.werBekommtDieDatenInterneAbteilungen') }}</small>
            <textarea v-model="vvtWizard.data.empfaenger" rows="2"
              :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.vertriebBuchhaltungSteuerberaterXYGm')" />
          </label>
          <label class="full">{{ $t('dsgvo.dSGVOPflichtDokuPanel.drittlandtransfer') }}
            <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.werdenDatenInNichtEULanderUbermittel') }}</small>
            <textarea v-model="vvtWizard.data.drittland" rows="2"
              :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.zBUSAViaSCCStripeCloudflareSieheD4AV')" />
          </label>
          <label class="full">{{ $t('dsgvo.dSGVOPflichtDokuPanel.datenflussSchnittstellen') }}
            <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.woherKommenDieDatenWohinFliessenSieS') }}</small>
            <textarea v-model="vvtWizard.data.datenfluss" rows="2"
              placeholder="z.B. Webformular → CRM (PostgreSQL) → Buchhaltung (DATEV-Export) → Steuerberater (SFTP)" />
          </label>
        </fieldset>

        <fieldset>
          <legend>{{ $t('dsgvo.dSGVOPflichtDokuPanel.aufbewahrungTOM') }}</legend>
          <div class="vvt-grid">
            <label>{{ $t('dsgvo.dSGVOPflichtDokuPanel.loschfrist') }} <span class="req">*</span>
              <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.wannWerdenDatenGeloschtFristGemHGBAO') }}</small>
              <input v-model="vvtWizard.data.loeschfrist" :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.zBJahreNachVertragsendeHGB')" />
            </label>
            <label>{{ $t('dsgvo.dSGVOPflichtDokuPanel.tOMReferenz') }}
              <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.welcheTechnischOrganisatorischenMass') }}</small>
              <input v-model="vvtWizard.data.tom_referenz" placeholder="z.B. TOM-Set 'Standard-CRM-Schutz'" />
            </label>
          </div>
          <div class="vvt-grid">
            <label>{{ $t('dsgvo.dSGVOPflichtDokuPanel.verweisLoschkonzept') }}
              <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.strukturierterVerweisAufDenEintragIm') }}</small>
              <!-- #1890: Auswahl aus dem Löschkonzept statt getippter
                   Referenz — ein Verweis, der auf nichts zeigt, sieht aus wie
                   eine Zuordnung. Freitext bleibt möglich (Bestandsdaten und
                   Verweise auf Dokumentabschnitte). -->
              <input v-model="vvtWizard.data.loeschfrist_ref" list="vvt-loesch-refs"
                     :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.zBLKLoschRegelLR')" />
              <datalist id="vvt-loesch-refs">
                <option v-for="o in verweiseLoesch" :key="o.wert" :value="o.wert">
                  {{ o.label }}
                </option>
              </datalist>
            </label>
            <label>{{ $t('dsgvo.dSGVOPflichtDokuPanel.verweisTOMArt') }}
              <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.strukturierteReferenzAufDieZugeordne') }}</small>
              <input v-model="vvtWizard.data.tom_ref" list="vvt-tom-refs"
                     placeholder="z.B. TOM-003, TOM-011" />
              <datalist id="vvt-tom-refs">
                <option v-for="o in verweiseTom" :key="o.wert" :value="o.wert">
                  {{ o.label }}
                </option>
              </datalist>
            </label>
          </div>
          <label class="full dsfa-trigger-row">
            <input type="checkbox" :checked="!!Number(vvtWizard.data.dsfa_trigger)"
              @change="vvtWizard.data.dsfa_trigger = ($event.target as HTMLInputElement).checked ? 1 : 0" />
            <span>
              <strong>{{ $t('dsgvo.dSGVOPflichtDokuPanel.dSFATriggerArt') }}</strong> {{ $t('dsgvo.dSGVOPflichtDokuPanel.voraussichtlichHohesRisikoFurRechteF') }}
            </span>
          </label>
          <!-- #1890: Art. 35 Abs. 3 nennt die drei Regelbeispiele, und die
               Eingaben dafür stehen in dieser Maske. Der gerechnete Hinweis
               steht daneben; beurteilt wird er von der oder dem
               Datenschutzbeauftragten („insbesondere"). -->
          <p v-if="dsfaHinweis" class="dsfa-hinweis full">
            {{ $t('dsgvo.dSGVOPflichtDokuPanel.dieErfasstenAngabenSprechenFurEineDS', { v0: dsfaHinweis.gruende.join('; ') }) }}
            <button v-if="!Number(vvtWizard.data.dsfa_trigger)" class="btn-link"
                    @click="vvtWizard.data.dsfa_trigger = 1">
              {{ $t('dsgvo.dSGVOPflichtDokuPanel.hakenSetzen') }}
            </button>
          </p>
        </fieldset>

        <fieldset>
          <legend>{{ $t('dsgvo.dSGVOPflichtDokuPanel.verantwortlichkeitNotizen') }}</legend>
          <label class="full">{{ $t('dsgvo.dSGVOPflichtDokuPanel.verantwortlichePersonRolle') }}
            <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.werIstInternVerantwortlichNameOderRo') }}</small>
            <input v-model="vvtWizard.data.verantwortlich" :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.zBMariaMullerDatenschutzkoordinatori')" />
          </label>
          <label class="full">{{ $t('common.notizen') }}
            <small>{{ $t('dsgvo.dSGVOPflichtDokuPanel.sonstigeRelevanteInformationenSonder') }}</small>
            <textarea v-model="vvtWizard.data.notizen" rows="3"
              :placeholder="$t('dsgvo.dSGVOPflichtDokuPanel.zBVerzichtAufEinwilligungspflichtWeg')" />
          </label>
        </fieldset>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeVvtWizard">{{ $t('common.cancel') }}</button>
          <button class="btn-primary" :disabled="!vvtWizardValid" @click="saveVvtWizard">
            {{ vvtWizard.editing ? $t('dsgvo.dSGVOPflichtDokuPanel.aktualisieren') : $t('dsgvo.dSGVOPflichtDokuPanel.anlegen') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Wizard-Modal -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @mousedown.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <FehlerHinweis v-if="wizardModal.fehler" :text="wizardModal.fehler"
                       @close="wizardModal.fehler = ''" />
        <p class="hint">{{ $t('dsgvo.dSGVOPflichtDokuPanel.promptChatGPTJSONAntwortHierEinfugen') }}</p>
        <PromptAustausch v-model="wizardModal.response" :prompt="wizardModal.prompt"
                         prompt-titel="Prompt" antwort-titel="ChatGPT-Antwort (JSON)"
                         :nummeriert="false" :prompt-zeilen="8" :antwort-zeilen="6" />
        <div v-if="wizardModal.parsed" class="parsed-result">
          <strong v-if="wizardModal.parsed.applied" style="color: #2e7d32;">{{ $t('dsgvo.dSGVOPflichtDokuPanel.angewendet') }}</strong>
          <strong v-else style="color: #e65100;">{{ $t('dsgvo.dSGVOPflichtDokuPanel.geparsed') }}</strong>
          <pre>{{ JSON.stringify(wizardModal.parsed, null, 2) }}</pre>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeWizard">{{ $t('common.close') }}</button>
          <button class="btn-primary" :disabled="!wizardModal.response" @click="parseAndApply">{{ $t('common.parsenAnwenden') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import PromptAustausch from '../../components/shared/PromptAustausch.vue'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import apiClient from '../../api/client'
import DSFADetailPanel from './DSFADetailPanel.vue'
import { t } from '../../i18n'

const store = useDsgvoStore()

// #1083: Navigation zum Assistenten-Tab in der DSGVOView.
const emit = defineEmits<{ (e: 'open-assistenten'): void; (e: 'open-tab', tab: string): void }>()

// DSFA-Detailansicht (#1085): zeigt Art. 35(7)a+b lokal + Risiken(c)/Maßnahmen(d) read-only
const selectedDsfa = ref<any | null>(null)
const openDsfaDetail = (d: any) => { selectedDsfa.value = d }
const closeDsfaDetail = () => { selectedDsfa.value = null }

const vvtForm = ref<any>({})
// #1115: D3 — DSFA über den geführten Assistenten anlegen (statt simples Formular)
const startDsfaAssistent = async () => {
  const n = (store.dpia?.length || 0) + 1
  const id = 'DSFA-' + String(n).padStart(3, '0')
  await store.saveDpia({ dpia_id: id, titel: t('dsgvo.dSGVOPflichtDokuPanel.neueDSFA'), restrisiko: 'niedrig' })
  await store.fetchPflichtDokuStatus()
  const rec = (store.dpia || []).find((d: any) => d.dpia_id === id)
  if (rec) selectedDsfa.value = rec
}
const avvForm = ref<any>({})
const panneForm = ref<any>({ art: 'vertraulichkeit', risikoeinschaetzung: 'gering' })

const status = computed(() => store.pflichtDokuStatus)
const statusItems = computed(() => {
  const s = status.value
  if (!s) return []
  return [
    { key: 'vvt', label: t('dsgvo.dSGVOPflichtDokuPanel.vVT'), ok: s.vvt?.ok, detail: `${s.vvt?.count || 0}` },
    { key: 'tom', label: t('dsgvo.dSGVOPflichtDokuPanel.tOM'), ok: s.tom?.ok, detail: `${s.tom?.count || 0} (${s.tom?.open || 0} offen)` },
    { key: 'dpia', label: t('dsgvo.dSGVOPflichtDokuPanel.dSFA'), ok: s.dpia?.ok, detail: `${s.dpia?.count || 0}` },
    { key: 'avv', label: t('dsgvo.dSGVOPflichtDokuPanel.aVV'), ok: s.avv?.ok, detail: `${s.avv?.count || 0}` },
    { key: 'pannen', label: t('dsgvo.dSGVOPflichtDokuPanel.datenpannen'), ok: true, detail: `${s.datenpannen?.count || 0}` },
  ]
})

const reloadAll = async () => {
  if (!store.selectedProjekt) return
  await Promise.all([
    store.fetchVvt(), store.fetchTom(), store.fetchDpia(),
    store.fetchAvv(), store.fetchPannen(), store.fetchPflichtDokuStatus(),
  ])
}

onMounted(async () => {
  await store.fetchBranchenTemplates()
  await reloadAll()
  await ladeVvtKataloge()   // #1890
})
watch(() => store.selectedProjekt, async () => {
  await reloadAll()
  await ladeVvtKataloge()
})

const truncate = (s: string, n: number) => (s || '').length > n ? `${(s || '').slice(0, n)}…` : (s || '')

// #587 VVT-Wizard
const vvtWizardEmpty = () => ({
  vvt_id: '', name: '', zweck: '', rechtsgrundlage: '', betroffene_kategorien: '',
  datenkategorien: '', empfaenger: '', drittland: '', loeschfrist: '',
  tom_referenz: '', verantwortlich: '', notizen: '',
  // #1101: Art. 30(1)/(2)-Praxisfelder
  rolle: 'verantwortlicher', art9_grundlage: '', datenfluss: '',
  loeschfrist_ref: '', tom_ref: '', dsfa_trigger: 0,
})
const vvtRolleLabel = (r: string) => r === 'auftragsverarbeiter'
  ? 'Auftragsverarbeiter (Art. 30(2))'
  : t('dsgvo.dSGVOPflichtDokuPanel.verantwortlicherArt')
const vvtWizard = ref<any>({ open: false, editing: false, data: vvtWizardEmpty() })

// #1890: Kataloge und Verweis-Auswahl kommen **vom Server**. Hier standen die
// Listen ein zweites Mal (Spiegel-Liste, #1731/#1735), und die für Art. 9
// Abs. 2 war unvollständig — d, e und f fehlten. Eine unvollständige
// Positivliste ist schlimmer als ein Freitextfeld: Sie sieht abschließend aus.
const vvtKataloge = ref<any>({ art6: [], art9: [], verweise: { tom: [], loeschkonzept: [] } })
const art6 = computed<any[]>(() => vvtKataloge.value.art6 || [])
const art9 = computed<any[]>(() => vvtKataloge.value.art9 || [])
const verweiseTom = computed<any[]>(() => vvtKataloge.value.verweise?.tom || [])
const verweiseLoesch = computed<any[]>(() =>
  vvtKataloge.value.verweise?.loeschkonzept || [])

/** Der gerechnete DSFA-Hinweis zum offenen Eintrag (Art. 35 Abs. 3). */
const dsfaHinweis = computed<any>(() => {
  const d = vvtWizard.value?.data?.dsfa
  return d && d.indiz ? d : null
})

async function ladeVvtKataloge() {
  const projekt = store.selectedProjekt
  if (!projekt) return
  try {
    const { data } = await apiClient.get(
      `/dsgvo/projekte/${encodeURIComponent(projekt)}/vvt/kataloge`)
    vvtKataloge.value = data || vvtKataloge.value
  } catch { /* ohne Katalog bleibt die Maske bedienbar */ }
}
const vvtWizardValid = computed(() => !!vvtWizard.value.data.vvt_id && !!vvtWizard.value.data.name && !!vvtWizard.value.data.zweck && !!vvtWizard.value.data.loeschfrist)

const openVvtWizard = (existing?: any) => {
  if (existing) {
    vvtWizard.value = { open: true, editing: true, data: { ...vvtWizardEmpty(), ...existing } }
  } else {
    vvtWizard.value = { open: true, editing: false, data: vvtWizardEmpty() }
  }
}

const closeVvtWizard = () => { vvtWizard.value = { open: false, editing: false, data: vvtWizardEmpty() } }

const saveVvtWizard = async () => {
  if (!vvtWizardValid.value) return
  const ok = await store.saveVvt(vvtWizard.value.data)
  if (ok) {
    await store.fetchPflichtDokuStatus()
    closeVvtWizard()
  }
}
const addVvt = async () => { if (await store.saveVvt(vvtForm.value)) { vvtForm.value = {}; await store.fetchPflichtDokuStatus() } }
const addAvv = async () => { if (await store.saveAvv(avvForm.value)) { avvForm.value = {}; await store.fetchPflichtDokuStatus() } }
const addPanne = async () => { if (await store.savePanne(panneForm.value)) { panneForm.value = { art: 'vertraulichkeit', risikoeinschaetzung: 'gering' }; await store.fetchPflichtDokuStatus() } }

// Wizards — die Tabellen-Zeilenaktionen D6 (Rechtsgrundlage) + D8 (Datenpannen-
// Meldung) bleiben kontextbezogen hier; die eigenständigen Launcher (D7/D9) sind
// in den Assistenten-Tab umgezogen (#1083).
const wizardModal = ref<any>({ open: false, kind: '', title: '', prompt: '', response: '', parsed: null, extra: {} })

const WIZARD_TITLES: Record<string, string> = {
  'rechtsgrundlage': 'D6 Rechtsgrundlagen-Klassifikator',
  'datenpanne-meldung': 'D8 Datenpannen-Meldung (72h)',
  'betroffenenrechte': 'D9 Betroffenenrechte-Workflow',
}

// #1839: Ohne Prompt öffnete sich das Fenster leer und ohne Meldung. Ein
// leeres Fenster sieht nach einem Defekt aus — die Ursache steht dann im
// `store.error`, den hier niemand neben dem Fenster zeigt.
const _wizardFehler = 'Der Prompt konnte nicht erzeugt werden. Bitte die '
  + t('dsgvo.dSGVOPflichtDokuPanel.meldungObenBeachtenUndErneutVersuche')

const openRgWizard = async (vvtItem: any) => {
  const prompt = await store.getWizardPrompt('rechtsgrundlage', vvtItem)
  wizardModal.value = {
    open: true, kind: 'rechtsgrundlage', title: WIZARD_TITLES['rechtsgrundlage'],
    prompt: prompt || '', response: '', parsed: null,
    extra: { vvt_id: vvtItem.id }, fehler: prompt ? '' : _wizardFehler,
  }
}

const openPanneMeldungWizard = async (p: any) => {
  const prompt = await store.getWizardPrompt('datenpanne-meldung', p)
  wizardModal.value = {
    open: true, kind: 'datenpanne-meldung', title: WIZARD_TITLES['datenpanne-meldung'],
    prompt: prompt || '', response: '', parsed: null,
    extra: { panne_id_db: p.id }, fehler: prompt ? '' : _wizardFehler,
  }
}

const closeWizard = () => { wizardModal.value = { open: false, kind: '', title: '', prompt: '', response: '', parsed: null, extra: {} } }

const parseAndApply = async () => {
  const { kind, response, extra } = wizardModal.value
  wizardModal.value.parsed = await store.parseWizardResponse(kind, response, extra, true)
  await reloadAll()
  if (wizardModal.value.parsed?.applied) {
    setTimeout(closeWizard, 1200)
  }
}
</script>

<style scoped>
/* #1890 */
.dsfa-hinweis { font-size: 12px; color: #ef6c00; margin: 4px 0; }
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
.help-box {
  background: #fff8e1; border-left: 4px solid #ffc107; padding: 10px 14px;
  margin: 0 0 12px; border-radius: 4px; font-size: 13px; line-height: 1.55; color: #444;
}

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; margin-bottom: 10px; }
.form-grid input, .form-grid select { padding: 7px 10px; border: 1px solid #ccc; border-radius: 4px; font: inherit; }
.form-grid label { display: flex; align-items: center; gap: 6px; font-size: 13px; }

.btn-primary { background: #1565c0; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:hover { background: #0d47a1; }
.btn-link { background: none; border: none; cursor: pointer; font-size: 14px; margin-right: 4px; }
.btn-secondary { background: #eee; color: #333; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

table { width: 100%; border-collapse: collapse; margin-top: 10px; }
table th, table td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #eee; }
table th { background: #f5f5f5; font-weight: 600; }

.status-pill { padding: 2px 8px; border-radius: 3px; font-size: 12px; }
.st-geplant { background: #fff3e0; color: #e65100; }
.st-umgesetzt { background: #e8f5e9; color: #2e7d32; }
.st-review { background: #fff9c4; color: #f57f17; }

.risk-pill { padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: 600; }
.rsk-niedrig, .rsk-gering { background: #e8f5e9; color: #2e7d32; }
.rsk-mittel { background: #fff3e0; color: #e65100; }
.rsk-hoch { background: #ffcdd2; color: #b71c1c; }

.wizards { background: #f3e5f5; border-color: #ce93d8; }
.assistenten-pointer { margin: 0 0 12px; color: #4a148c; font-size: 13px; line-height: 1.55; }
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

.quick-actions {
  display: flex; align-items: center; gap: 12px; padding: 12px 16px;
  background: #e3f2fd; border-radius: 6px; margin-bottom: 12px;
}
.quick-actions .hint { color: #1565c0; font-size: 13px; }

.vvt-modal { max-width: 900px; }
.vvt-modal fieldset {
  border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px 16px;
  margin: 10px 0 14px;
}
.vvt-modal fieldset legend { color: #1565c0; font-weight: 600; padding: 0 8px; font-size: 14px; }
.vvt-modal label {
  display: flex; flex-direction: column; gap: 4px; font-size: 13px;
  font-weight: 600; color: #333; margin-bottom: 10px;
}
.vvt-modal label.full { width: 100%; }
.vvt-modal label small {
  font-weight: normal; color: #666; font-size: 12px; line-height: 1.4;
}
.vvt-modal input, .vvt-modal select, .vvt-modal textarea {
  font-weight: normal; padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px;
  font-size: 14px; font-family: inherit;
}
.vvt-modal textarea { min-height: 60px; resize: vertical; }
.vvt-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
.req { color: #c62828; }
.vvt-modal .modal-actions { border-top: 1px solid #e0e0e0; padding-top: 16px; }

/* #1101: Rollen-Toggle / -Filter, DSFA-Flag */
.rolle-toggle { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; }
.rolle-opt {
  flex-direction: row !important; align-items: center; gap: 6px;
  border: 1px solid #ccc; border-radius: 6px; padding: 8px 12px; cursor: pointer;
  font-weight: 500 !important; background: #fff; margin-bottom: 0 !important;
}
.rolle-opt.active { border-color: #1565c0; background: #e3f2fd; color: #1565c0; font-weight: 600 !important; }
.rolle-opt input { width: auto; }

.vvt-rolle-filter {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 4px 0 12px;
}
.vvt-rolle-filter .filter-label { font-weight: 600; color: #333; font-size: 13px; }
.pill-btn {
  border: 1px solid #c5cae9; background: #fff; color: #3949ab; border-radius: 999px;
  padding: 4px 12px; font-size: 12px; cursor: pointer;
}
.pill-btn.active { background: #1565c0; border-color: #1565c0; color: #fff; }

.rolle-pill {
  display: inline-block; border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: 600;
}
.rolle-pill.verantwortlicher { background: #e3f2fd; color: #1565c0; }
.rolle-pill.auftragsverarbeiter { background: #fff3e0; color: #e65100; }
.dsfa-flag { color: #c62828; font-weight: 600; font-size: 12px; }

.dsfa-trigger-row {
  flex-direction: row !important; align-items: flex-start; gap: 8px;
  background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px; padding: 10px 12px;
  font-weight: normal !important;
}
.dsfa-trigger-row input { width: auto; margin-top: 2px; }
</style>
