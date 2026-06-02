<template>
  <div class="gg-view">
    <div class="header">
      <h2>⚖ Gerichtsgutachten (BISG-konform)</h2>
      <p>Sachverständigengutachten nach DIN EN 16775 · ISO/IEC 27037 · ZPO §§ 406, 407, 407a, 411</p>
      <router-link to="/gutachten" class="back-link">← zum Compliance-Audit-Bericht</router-link>
      <ModuleHelpButton module="gutachten" class="header-help" />
    </div>

    <div v-if="store.error" class="alert alert-error" @click="store.error = ''">{{ store.error }}</div>

    <!-- Projekt-Auswahl -->
    <div v-if="!aktuell && !creating" class="card">
      <h3>Verfahren wählen</h3>
      <p v-if="store.projekte.length === 0">Noch keine Gerichtsgutachten angelegt.</p>
      <div v-else class="proj-list">
        <button v-for="p in store.projekte" :key="p.name" class="proj-tile" @click="selectProjekt(p.name)">
          <strong>{{ p.name }}</strong>
          <span class="proj-az">{{ p.aktenzeichen || '(ohne AZ)' }}</span>
          <span class="proj-status" :class="`status-${p.status}`">{{ p.status }}</span>
        </button>
      </div>
      <button class="btn-primary" @click="startNew">+ Neues Gerichtsgutachten</button>
    </div>

    <!-- Anlegen-Form -->
    <div v-else-if="creating" class="card">
      <h3>Neues Gutachten anlegen</h3>

      <!-- #663 Toggle Gericht / Privat -->
      <div class="art-toggle">
        <label :class="['toggle-opt', { active: newForm.gutachten_art === 'gericht' }]">
          <input type="radio" value="gericht" v-model="newForm.gutachten_art" />
          ⚖ <strong>Gerichtsgutachten</strong> — gerichtsbestellt mit Beweisbeschluss
        </label>
        <label :class="['toggle-opt', { active: newForm.gutachten_art === 'privat' }]">
          <input type="radio" value="privat" v-model="newForm.gutachten_art" />
          📋 <strong>Privatgutachten</strong> — Mandanten-Auftrag (kein Gericht)
        </label>
      </div>

      <p class="hint" v-if="newForm.gutachten_art === 'gericht'">
        Pflicht: Name + Gericht + Aktenzeichen + SV-Name
      </p>
      <p class="hint" v-else>
        Pflicht: Name + Auftraggeber + Auftragsart + SV-Name
      </p>

      <div class="form-grid">
        <label>Projekt-Name * <input v-model="newForm.name"
               :placeholder="newForm.gutachten_art === 'gericht' ? 'z.B. GG-2026-007' : 'z.B. PG-2026-007'" />
          <span v-if="nameError" class="field-error">{{ nameError }}</span>
        </label>

        <!-- Gerichts-Felder -->
        <template v-if="newForm.gutachten_art === 'gericht'">
          <label>Gericht * <input v-model="newForm.gericht" placeholder="Landgericht ..." /></label>
          <label>Kammer <input v-model="newForm.kammer" placeholder="3. Zivilkammer" /></label>
          <label>Aktenzeichen * <input v-model="newForm.aktenzeichen" placeholder="X 0815/26" /></label>
          <label>Beweisbeschluss vom <input v-model="newForm.beweisbeschluss_datum" placeholder="03.03.2026" /></label>
          <label>Kläger <input v-model="newForm.klaeger_name" /></label>
          <label>Anwalt Kläger <input v-model="newForm.klaeger_anwalt" /></label>
          <label>Beklagter <input v-model="newForm.beklagter_name" /></label>
          <label>Anwalt Beklagter <input v-model="newForm.beklagter_anwalt" /></label>
        </template>

        <!-- Privat-Felder -->
        <template v-else>
          <label>Auftraggeber * <input v-model="newForm.auftraggeber" placeholder="ACME GmbH" /></label>
          <label>Auftrags-Art *
            <select v-model="newForm.auftrags_art">
              <option value="">— wählen —</option>
              <option value="Beweissicherung">Beweissicherung</option>
              <option value="Tauglichkeitsprüfung">Tauglichkeitsprüfung</option>
              <option value="Schaden-Gutachten">Schaden-Gutachten</option>
              <option value="Wertgutachten">Wertgutachten</option>
              <option value="Kaufberatung">Kaufberatung</option>
              <option value="Sonstiges">Sonstiges</option>
            </select>
          </label>
          <label>Auftrags-Datum <input v-model="newForm.auftrags_datum" placeholder="2026-05-27" /></label>
          <label>Auftrags-Nummer <input v-model="newForm.auftrags_nummer" placeholder="freier Code" /></label>
          <label>Honorarvereinbarung <input v-model="newForm.honorarvereinbarung" placeholder="z.B. 650€ Tagessatz" /></label>
        </template>

        <!-- Gemeinsam -->
        <label>Vertraulichkeit <input v-model="newForm.vertraulichkeit" /></label>
        <label>Thema <textarea v-model="newForm.thema" rows="2"></textarea></label>

        <label>SV-Name * <input v-model="newForm.sv_name" /></label>
        <label>SV-Zertifizierung <input v-model="newForm.sv_zertifizierung" placeholder="Zertifizierter IT-SV (BISG)" /></label>
        <label>SV-Anschrift <input v-model="newForm.sv_anschrift" /></label>
        <label>SV-Kontakt <input v-model="newForm.sv_kontakt" /></label>
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
          ℹ Dies ist eine <strong>automatische Namensprüfung</strong> auf Vorbefassung.
          Den vollständigen Befangenheits-Selbstcheck (Fragebogen § 406 ZPO) findest du
          nach dem Speichern im Reiter <strong>„Selbstcheck (§ 406)"</strong>.
        </p>
      </div>

      <div class="actions">
        <button class="btn-secondary" @click="cancelNew">Abbrechen</button>
        <button class="btn-link" :disabled="!befangReady" @click="runBefangCheck">⚠ Befangenheits-Check</button>
        <button class="btn-primary" :disabled="!validNewForm" @click="createProjekt">Anlegen</button>
      </div>
      <p v-if="!validNewForm" class="hint missing-hint">
        Noch erforderlich: <strong>{{ missingFields.join(', ') }}</strong>
      </p>
    </div>

    <!-- Editor -->
    <div v-else-if="aktuell" class="editor">
      <div class="editor-header">
        <h3>{{ aktuell.name }} <small>({{ aktuell.aktenzeichen }})</small></h3>
        <div class="header-actions">
          <button class="btn-link" @click="closeProjekt">← Liste</button>
          <button class="btn-secondary" @click="openPreview">👁 Vorschau</button>
          <button class="btn-secondary" @click="exportDocx">📄 DOCX</button>
          <button class="btn-secondary" @click="exportArchiv">📦 Archiv-ZIP</button>
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
          {{ aktuell.gutachten_art === 'privat' ? '📋 Privatgutachten' : '⚖ Gerichtsgutachten' }}
        </div>
        <!-- Phase H-A — Audit-Source-Banner (#681) -->
        <div v-if="auditSource && auditSource.audit_projekt" class="result-card status-ok" style="margin: 12px 0; border-left: 4px solid #1565c0;">
          <strong>📋 Aus Compliance-Audit-Bericht abgeleitet</strong>
          <ul style="margin: 8px 0; padding-left: 20px; font-size: 13px;">
            <li>Audit-Projekt: <code>{{ auditSource.audit_projekt }}</code></li>
            <li>Audit-Datum: {{ (auditSource.audit_datum || '').slice(0, 10) }}</li>
            <li>Audit-Kunde: {{ auditSource.audit_kunde }}</li>
            <li>Snapshot-SHA-256: <code style="font-size: 11px;">{{ (auditSource.snapshot_sha256 || '').slice(0, 24) }}…</code></li>
            <li>Konvertiert am: {{ (auditSource.konvertiert_am || '').slice(0, 16) }} von {{ auditSource.konvertiert_von }}</li>
          </ul>
          <p style="font-size: 12px; color: #c62828;"><strong>⚠ § 407a ZPO:</strong> Übernommene Befund-Skeletons sind LEER und müssen persönlich neu formuliert werden!</p>
        </div>
        <div class="form-grid">
          <template v-if="(aktuell.gutachten_art || 'gericht') === 'gericht'">
            <label>Gericht <input v-model="aktuell.gericht" /></label>
            <label>Kammer <input v-model="aktuell.kammer" /></label>
            <label>Aktenzeichen <input v-model="aktuell.aktenzeichen" /></label>
            <label>Beweisbeschluss vom <input v-model="aktuell.beweisbeschluss_datum" /></label>
            <label>Kläger <input v-model="aktuell.klaeger_name" /></label>
            <label>Beklagter <input v-model="aktuell.beklagter_name" /></label>
          </template>
          <template v-else>
            <label>Auftraggeber <input v-model="aktuell.auftraggeber" /></label>
            <label>Auftrags-Art <input v-model="aktuell.auftrags_art" /></label>
            <label>Auftrags-Datum <input v-model="aktuell.auftrags_datum" /></label>
            <label>Auftrags-Nummer <input v-model="aktuell.auftrags_nummer" /></label>
            <label>Honorarvereinbarung <input v-model="aktuell.honorarvereinbarung" /></label>
          </template>
          <label>Thema <textarea v-model="aktuell.thema" rows="2"></textarea></label>
          <label>SV-Name <input v-model="aktuell.sv_name" /></label>
          <label>Status
            <select v-model="aktuell.status">
              <option value="in_bearbeitung">in Bearbeitung</option>
              <option value="finalisiert">finalisiert</option>
              <option value="eingereicht">eingereicht</option>
            </select>
          </label>
        </div>
        <button class="btn-primary" @click="saveStammdaten">Speichern</button>
      </div>

      <!-- Tab: Selbstcheck -->
      <div v-if="tab === 'selbstcheck'" class="tab-content">
        <h4>G2-1 — Befangenheits-Selbstcheck (§ 406 ZPO)
          <button class="help-btn" @click="showHelp('selbstcheck.vorbefassung')" title="Hilfe">ℹ</button>
        </h4>
        <!-- #692 + #696 + #699 — Selbstcheck + EDITIERBARER Fließtext -->
        <div v-if="lastSelbstcheck" class="result-card status-ok" style="margin-bottom: 12px;">
          📌 <strong>Letzter Selbstcheck:</strong> {{ lastSelbstcheck.ereignis_datum }}
          <br/><small>{{ lastSelbstcheck.titel }}</small>
          <div class="fliesstext-block">
            <strong>Befangenheits-Fließtext (geht in DOCX Kap. III):</strong>
            <textarea v-model="fliesstextEdit" rows="9" class="fliesstext-edit"
                      placeholder="Generierten Fließtext hier bearbeiten..."></textarea>
            <div class="row" style="justify-content: flex-end; gap: 6px; margin-top: 6px;">
              <span v-if="fliesstextSaveStatus" class="hint" style="align-self: center;">{{ fliesstextSaveStatus }}</span>
              <button class="btn-link" @click="resetFliesstext">↺ Original wiederherstellen</button>
              <button class="btn-primary" :disabled="!fliesstextEdit.trim()" @click="saveFliesstext">💾 Speichern</button>
            </div>
          </div>
        </div>
        <div v-for="f in store.selbstcheckFragen" :key="f.key" class="check-row">
          <strong>{{ f.frage }}</strong>
          <div class="ja-nein">
            <label><input type="radio" :value="'ja'" v-model="selbstcheckAntw[f.key]" /> Ja</label>
            <label><input type="radio" :value="'nein'" v-model="selbstcheckAntw[f.key]" /> Nein</label>
            <label><input type="radio" :value="'unklar'" v-model="selbstcheckAntw[f.key]" /> Unklar</label>
          </div>
        </div>
        <button class="btn-primary" @click="runSelbstcheck">Auswerten</button>
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
        <h4>II. Beweisfragen</h4>
        <!-- Phase H-B — KI-Generator für Beweisfragen aus Audit-Quelle (#684) -->
        <div v-if="auditSource && auditSource.audit_projekt" class="add-form" style="background: #e3f2fd; border-left: 4px solid #1565c0; margin-bottom: 16px;">
          <strong>🤖 Beweisfragen aus Audit-Quelle generieren (Phase H-B)</strong>
          <p class="hint">Lass ChatGPT Beweisfragen aus dem Audit-Kontext vorschlagen (5 Kategorien: Compliance, Prio, Stand der Technik, Wirkung, Empfehlung).</p>
          <div class="row" style="gap: 8px; flex-wrap: wrap;">
            <button class="btn-secondary" @click="generatePgQuestions">📝 Prompt generieren</button>
            <button v-if="pgQuestionsPrompt" class="btn-secondary" @click="copyToClipboard(pgQuestionsPrompt)">📋 Copy</button>
          </div>
          <textarea v-if="pgQuestionsPrompt" v-model="pgQuestionsPrompt" rows="8" style="width:100%; font-family: monospace; font-size: 11px;" readonly></textarea>
          <textarea v-if="pgQuestionsPrompt" v-model="pgQuestionsResponse" rows="6" style="width:100%; margin-top: 8px;"
                    placeholder="ChatGPT-JSON-Antwort hier einfügen…"></textarea>
          <div v-if="pgQuestionsPrompt" class="row" style="justify-content: flex-end;">
            <button class="btn-primary" :disabled="!pgQuestionsResponse" @click="importPgQuestions">📥 Antwort importieren</button>
          </div>
          <div v-if="pgQuestionsImportMsg" class="hint ok">{{ pgQuestionsImportMsg }}</div>
        </div>
        <!-- Phase H-C — Smart Suggestions (Top-3-Lows-Analyse, #688) -->
        <div v-if="auditSource && auditSource.audit_projekt" class="add-form" style="background: #f3e5f5; border-left: 4px solid #6a1b9a; margin-bottom: 16px;">
          <strong>💡 Smart Suggestions zu Top-3-Audit-Lows</strong>
          <button class="btn-secondary" @click="generateSmartSuggestionsPrompt" style="margin-top: 6px;">🧠 Prompt generieren</button>
          <textarea v-if="smartPrompt" v-model="smartPrompt" rows="6" style="width:100%; font-family: monospace; font-size: 11px;" readonly></textarea>
          <textarea v-if="smartPrompt" v-model="smartResponse" rows="5" style="width:100%;"
                    placeholder="ChatGPT-Antwort hier einfügen…"></textarea>
          <button v-if="smartPrompt" class="btn-primary" :disabled="!smartResponse" @click="parseSmartSuggestions">📊 Parsen</button>
          <pre v-if="smartParsed" style="background:#fff;padding:8px;font-size:12px;">{{ JSON.stringify(smartParsed, null, 2) }}</pre>
        </div>
        <table class="tbl">
          <thead><tr><th>Nr</th><th>Frage</th><th>Antwort kurz</th><th>Antwort</th><th></th></tr></thead>
          <tbody>
            <tr v-for="f in store.beweisfragen" :key="f.id">
              <td>{{ f.nr }}</td>
              <td>{{ f.frage_text }}</td>
              <td>{{ f.antwort_kurz }}</td>
              <td>{{ f.antwort_text }}</td>
              <td>
                <button class="btn-link" @click="editBF(f)" title="Bearbeiten">✏</button>
                <button class="btn-link" @click="store.deleteBeweisfrage(f.id, aktuell.name)" title="Löschen">🗑</button>
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
            <label style="flex:1;">Antwort (kurz):
              <select v-model="newBF.antwort_kurz" style="width:100%">
                <option value="">— wählen —</option>
                <option value="ja">ja</option>
                <option value="nein">nein</option>
                <option value="teilweise">teilweise</option>
                <option value="non-liquet">non-liquet</option>
              </select>
            </label>
          </div>
          <label>Frage (wörtlich aus Beweisbeschluss):
            <textarea v-model="newBF.frage_text" rows="3"
                      placeholder="z.B. 'Weist das gelieferte Softwaresystem einen technischen Mangel auf?'"
                      style="width:100%; resize:vertical;"></textarea>
          </label>
          <label>Antwort (ausführlich, 2-3 Sätze, mit Verweis zu Beurteilungen Kap. V):
            <textarea v-model="newBF.antwort_text" rows="4"
                      placeholder="Ja. Aus informationstechnischer Sicht weist das System ... (siehe Beurteilung 5.1)"
                      style="width:100%; resize:vertical;"></textarea>
          </label>
          <div class="row" style="justify-content: flex-end;">
            <button v-if="editId.bf" class="btn-secondary" @click="cancelEdit('bf')">Abbrechen</button>
            <button class="btn-primary" :disabled="!newBF.frage_text" @click="addBF">
              {{ editId.bf ? '💾 Speichern' : '+ Hinzu' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Tab: Befunde -->
      <div v-if="tab === 'befunde'" class="tab-content">
        <h4>IV. Befunderhebung — nur Tatsachen!
          <button class="help-btn" @click="showHelp('befund.intro')" title="Hilfe">ℹ</button>
        </h4>
        <table class="tbl">
          <thead><tr><th>Nr</th><th>Titel</th><th>Methode</th><th>Werkzeug</th><th></th></tr></thead>
          <tbody>
            <tr v-for="b in store.befunde" :key="b.id" :class="{ nonliquet: b.non_liquet }">
              <td>{{ b.nr }}</td>
              <td>{{ b.titel }}</td>
              <td>{{ b.methode }}</td>
              <td>{{ b.werkzeug_name }} {{ b.werkzeug_version }}</td>
              <td>
                <button class="btn-link" @click="editBefund(b)" title="Bearbeiten">✏</button>
                <button class="btn-link" @click="store.deleteBefund(b.id, aktuell.name)" title="Löschen">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <input v-model="newBefund.nr" placeholder="Nr (z.B. 4.1)" />
          <input v-model="newBefund.titel" placeholder="Titel" />
          <div class="row">
            <select v-model="newBefund.methode" style="flex:1">
              <option value="">— Methode —</option>
              <option value="statisch">statisch</option>
              <option value="dynamisch">dynamisch</option>
              <option value="db">db</option>
              <option value="netzwerk">netzwerk</option>
              <option value="interview">interview</option>
              <option value="live-forensik">live-forensik</option>
            </select>
            <button class="help-btn" @click="showHelp('befund.methode')">ℹ</button>
          </div>
          <div class="row">
            <input v-model="newBefund.werkzeug_name" placeholder="Werkzeug" style="flex:1" />
            <input v-model="newBefund.werkzeug_version" placeholder="Version" style="flex:1" />
            <button class="help-btn" @click="showHelp('befund.werkzeug')">ℹ</button>
          </div>
          <label>Beschreibung (Tatsachen-only)</label>
          <RichEditor v-model="newBefund.beschreibung_text"
                      @update:modelValue="validateBefundLive" />
          <div v-if="befundLinterHints.length" class="linter-warn">
            ⚠ {{ befundLinterHints.length }} Linter-Hinweis(e):
            <ul><li v-for="h in befundLinterHints.slice(0,5)" :key="h.pos_start">
              <strong>{{ h.term }}</strong>: {{ h.vorschlag }}
            </li></ul>
          </div>
          <button v-if="editId.befund" class="btn-secondary" @click="cancelEdit('befund')">Abbrechen</button>
          <button class="btn-primary" :disabled="!newBefund.titel" @click="addBefund">
            {{ editId.befund ? '💾 Speichern' : '+ Hinzu' }}
          </button>
        </div>
      </div>

      <!-- Tab: Beurteilungen -->
      <div v-if="tab === 'beurteilungen'" class="tab-content">
        <h4>V. Technische Beurteilung
          <button class="help-btn" @click="showHelp('beurteilung.intro')" title="Hilfe">ℹ</button>
        </h4>
        <table class="tbl">
          <thead><tr><th>Nr</th><th>Titel</th><th>Norm</th><th>Befunde</th><th></th></tr></thead>
          <tbody>
            <tr v-for="u in store.beurteilungen" :key="u.id" :class="{ nonliquet: u.non_liquet }">
              <td>{{ u.nr }}</td>
              <td>{{ u.titel }}</td>
              <td>{{ u.norm_referenz }}</td>
              <td>{{ (u.befund_ids || []).join(', ') }}</td>
              <td>
                <button class="btn-link" @click="editBeurt(u)" title="Bearbeiten">✏</button>
                <button class="btn-link" @click="store.deleteBeurteilung(u.id, aktuell.name)" title="Löschen">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div class="add-form column">
          <input v-model="newBeurt.nr" placeholder="Nr (z.B. 5.1)" />
          <input v-model="newBeurt.titel" placeholder="Titel" />
          <div class="row">
            <select v-model="newBeurt.norm_id" style="flex:1">
              <option value="">— Norm wählen —</option>
              <option v-for="n in store.normen" :key="n.id" :value="n.id">{{ n.titel }}</option>
            </select>
            <button class="help-btn" @click="showHelp('beurteilung.norm_referenz')">ℹ</button>
          </div>
          <input v-model="newBeurt.norm_referenz" placeholder="Norm-Referenz (z.B. ISO/IEC 25010 — Fault Tolerance)" />
          <label>Befund-IDs (kommagetrennt)
            <input v-model="newBeurt.befund_ids_str" placeholder="z.B. 1,2" />
          </label>

          <!-- Rich-Text-Editoren für Soll/Ist/Kausalität/Würdigung (#674) -->
          <label>Soll (was die Norm verlangt) <button class="help-btn" @click="showHelp('beurteilung.soll')">ℹ</button></label>
          <RichEditor v-model="newBeurt.soll_text" />
          <label>Ist (Befund-Vergleich) <button class="help-btn" @click="showHelp('beurteilung.ist')">ℹ</button></label>
          <RichEditor v-model="newBeurt.ist_text" />
          <label>Kausalität <button class="help-btn" @click="showHelp('beurteilung.kausalitaet')">ℹ</button></label>
          <RichEditor v-model="newBeurt.kausalitaet_text" />
          <label>Würdigung (Jura-Sperre!) <button class="help-btn" @click="showHelp('beurteilung.wuerdigung')">ℹ</button></label>
          <RichEditor v-model="newBeurt.bewertung_text" />
          <div class="actions">
            <button class="btn-link" :disabled="!newBeurt.norm_id" @click="openBeurteilungsWizard">🤖 KI-Vorschlag generieren</button>
            <button v-if="editId.beurt" class="btn-secondary" @click="cancelEdit('beurt')">Abbrechen</button>
            <button class="btn-primary" :disabled="!newBeurt.titel" @click="addBeurteilung">
              {{ editId.beurt ? '💾 Speichern' : '+ Hinzu' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Tab: Asservaten -->
      <div v-if="tab === 'assets'" class="tab-content">
        <h4>Asservaten (Chain of Custody nach ISO/IEC 27037)</h4>
        <table class="tbl">
          <thead><tr><th>Bezeichnung</th><th>SHA-256</th><th>Akquisition</th><th>Werkzeug</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in store.assets" :key="a.id">
              <td>{{ a.bezeichnung }}</td>
              <td><code class="hash">{{ (a.sha256 || '').slice(0, 16) }}…</code></td>
              <td>{{ a.akquisitions_utc }}</td>
              <td>{{ a.werkzeug_name }} {{ a.werkzeug_version }}</td>
              <td>
                <button class="btn-link" @click="editAsset(a)" title="Bearbeiten">✏</button>
                <a :href="`/api/gutachten/gerichts/assets/${a.id}/sicherungsprotokoll.pdf`"
                   target="_blank" rel="noopener noreferrer" class="btn-link" title="Sicherungsprotokoll">📄</a>
                <button class="btn-link" @click="store.deleteAsset(a.id, aktuell.name)" title="Löschen">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <input v-model="newAsset.bezeichnung" placeholder="Bezeichnung" />
          <input type="file" @change="onAssetFile" />
          <div v-if="newAsset.sha256" class="sha-display">SHA-256: <code>{{ newAsset.sha256 }}</code></div>
          <input v-model="newAsset.akquisitions_utc" placeholder="UTC (YYYY-MM-DDTHH:MM:SSZ)" />
          <input v-model="newAsset.akquisitions_ort" placeholder="Ort" />
          <input v-model="newAsset.werkzeug_name" placeholder="Werkzeug" />
          <input v-model="newAsset.werkzeug_version" placeholder="Version" />
          <input v-model="newAsset.gegengezeichnet_von" placeholder="Gegengezeichnet von" />
          <button v-if="editId.asset" class="btn-secondary" @click="cancelEdit('asset')">Abbrechen</button>
          <button class="btn-primary" :disabled="!newAsset.bezeichnung || !newAsset.sha256" @click="addAsset">
            {{ editId.asset ? '💾 Speichern' : '+ Hinzu' }}
          </button>
        </div>
      </div>

      <!-- Tab: Verfahren -->
      <div v-if="tab === 'verfahren'" class="tab-content">
        <h4>III. Verfahrensgang + Symmetrie-Check</h4>
        <button class="btn-secondary" @click="runSymmetrieCheck">🔍 Symmetrie prüfen</button>
        <div v-if="symResult" :class="['result-card', symResult.ok ? 'status-ok' : 'status-blockiert']">
          <strong v-if="symResult.ok">✓ Alle {{ symResult.kommunikationen_anzahl }} Parteikommunikationen symmetrisch</strong>
          <strong v-else>⚠ {{ symResult.verletzungen.length }} Symmetrieverletzungen</strong>
          <ul v-if="symResult.verletzungen?.length">
            <li v-for="v in symResult.verletzungen" :key="v.ereignis_id">
              {{ v.datum }} — {{ v.titel }} (fehlt: {{ v.fehlend.join(', ') }})
            </li>
          </ul>
        </div>
        <table class="tbl">
          <thead><tr><th>Datum</th><th>Typ</th><th>Titel</th><th>Empfänger</th><th></th></tr></thead>
          <tbody>
            <tr v-for="e in store.verfahrensereignisse" :key="e.id">
              <td>{{ (e.ereignis_datum || '').slice(0, 16) }}</td>
              <td>{{ e.ereignis_typ }}</td>
              <td>{{ e.titel }}</td>
              <td>{{ (e.empfaenger || []).join(', ') }}</td>
              <td>
                <button class="btn-link" @click="editVerf(e)" title="Bearbeiten">✏</button>
                <button class="btn-link" @click="deleteVerf(e.id)" title="Löschen">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <select v-model="newVerf.ereignis_typ">
            <option value="">— Typ —</option>
            <option v-for="t in ereignisTypen" :key="t" :value="t">{{ t }}</option>
          </select>
          <input v-model="newVerf.titel" placeholder="Titel" />
          <textarea v-model="newVerf.beschreibung" placeholder="Beschreibung" rows="2"></textarea>
          <label>Empfänger
            <div>
              <label><input type="checkbox" v-model="newVerfEmp.klaeger" /> Kläger</label>
              <label><input type="checkbox" v-model="newVerfEmp.beklagter" /> Beklagter</label>
              <label><input type="checkbox" v-model="newVerfEmp.gericht" /> Gericht</label>
            </div>
          </label>
          <button v-if="editId.verf" class="btn-secondary" @click="cancelEdit('verf')">Abbrechen</button>
          <button class="btn-primary" :disabled="!newVerf.titel" @click="addVerf">
            {{ editId.verf ? '💾 Speichern' : '+ Hinzu' }}
          </button>
        </div>
      </div>

      <!-- Tab: Honorar -->
      <div v-if="tab === 'honorar'" class="tab-content">
        <h4>G0-4 — Honorar-Tracker (Zeitbuch)</h4>
        <div v-if="store.honorarSummary" class="hon-summary">
          <span>📊 {{ store.honorarSummary.total_stunden }}h</span>
          <span>💶 Honorar: {{ store.honorarSummary.honorar_eur }}€</span>
          <span>🧾 Auslagen: {{ store.honorarSummary.auslagen_eur }}€</span>
          <span>📥 Offen: {{ store.honorarSummary.offen_eur }}€</span>
        </div>
        <a :href="`/api/gutachten/gerichts/${encodeURIComponent(aktuell.name)}/rechnung.pdf?auftraggeber=${encodeURIComponent(aktuell.gericht)}`"
           target="_blank" rel="noopener noreferrer" class="btn-secondary">📄 Rechnung-PDF</a>
        <table class="tbl">
          <thead><tr><th>Datum</th><th>Kategorie</th><th>Min</th><th>Satz</th><th>Beschreibung</th></tr></thead>
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
          <input v-model.number="newHon.dauer_minuten" type="number" placeholder="Dauer (Min)" />
          <input v-model.number="newHon.stundensatz_eur" type="number" step="5" placeholder="Stundensatz €" />
          <input v-model="newHon.beschreibung" placeholder="Beschreibung" />
          <button class="btn-primary" :disabled="!newHon.dauer_minuten" @click="addHon">+ Eintrag</button>
        </div>
      </div>

      <!-- Tab: Forensik (G4) -->
      <div v-if="tab === 'forensik'" class="tab-content">
        <h4>G4 — Forensik-Werkzeuge</h4>

        <!-- G4-2 Werkzeug-Validator -->
        <div class="sub-card">
          <strong>Werkzeug-Validator (G4-2)</strong>
          <button class="btn-link" @click="runToolValidator">🔍 Prüfen</button>
          <div v-if="store.werkzeugValidator">
            <div :class="['result-card', store.werkzeugValidator.ok ? 'status-ok' : 'status-blockiert']">
              <strong v-if="store.werkzeugValidator.ok">✓ Alle Werkzeuge im Register</strong>
              <strong v-else>⚠ {{ store.werkzeugValidator.unknown_tools.length }} Werkzeug(e) nicht im SV-Register</strong>
            </div>
            <ul v-if="store.werkzeugValidator.unknown_tools?.length">
              <li v-for="t in store.werkzeugValidator.unknown_tools" :key="t.befund_id">
                Befund {{ t.befund_nr }}: <code>{{ t.tool_name }} {{ t.tool_version }}</code>
              </li>
            </ul>
          </div>
        </div>

        <!-- G4-3 MACB-Timeline -->
        <div class="sub-card">
          <strong>MACB-Zeitstempel-Tabelle (G4-3)</strong>
          <table class="tbl">
            <thead><tr><th>Datei</th><th>Modified</th><th>Accessed</th><th>Changed</th><th>Born</th><th></th></tr></thead>
            <tbody>
              <tr v-for="m in store.macbEintraege" :key="m.id" :class="{ 'risk-row': m.timestomping_risk }">
                <td>{{ m.datei_pfad }}</td>
                <td>{{ m.modified_at }}</td>
                <td>{{ m.accessed_at }}</td>
                <td>{{ m.changed_at }}</td>
                <td>{{ m.born_at }}</td>
                <td>
                  <span v-if="m.timestomping_risk" class="risk-badge">⚠ Timestomping?</span>
                  <button class="btn-link" @click="editMacb(m)" title="Bearbeiten">✏</button>
                  <button class="btn-link" @click="store.deleteMacb(m.id, aktuell.name)" title="Löschen">🗑</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="add-form">
            <input v-model="newMacb.datei_pfad" placeholder="Pfad" style="flex:2" />
            <input v-model="newMacb.modified_at" placeholder="M" />
            <input v-model="newMacb.accessed_at" placeholder="A" />
            <input v-model="newMacb.changed_at" placeholder="C" />
            <input v-model="newMacb.born_at" placeholder="B" />
            <button v-if="editId.macb" class="btn-secondary" @click="cancelEdit('macb')">Abbrechen</button>
            <button class="btn-primary" :disabled="!newMacb.datei_pfad" @click="addMacb">
              {{ editId.macb ? '💾 Speichern' : '+ Hinzu' }}
            </button>
          </div>
        </div>

        <!-- G4-4 Volatility-Checklist -->
        <div class="sub-card">
          <strong>Order of Volatility (G4-4)</strong>
          <p class="hint">Pflicht bei Methode 'live-forensik' — Reihenfolge der Beweissicherung.</p>
          <ol>
            <li v-for="v in store.volatilityChecklist" :key="v.key">
              <strong>{{ v.reihenfolge }}.</strong> {{ v.name }}
            </li>
          </ol>
        </div>

        <!-- G4-5 Log-Klassifikator -->
        <div class="sub-card">
          <strong>Log-Klassifikator (G4-5)</strong>
          <input type="file" @change="onLogClassify" />
          <div v-if="logClassResult" :class="`log-class log-${logClassResult.klasse}`">
            <code>{{ logClassResult.filename }}</code> → <strong>{{ logClassResult.klasse }}</strong>
          </div>
        </div>
      </div>

      <!-- Tab: Hypothesen-Tree (G6-1) + Drittgutachter (G6-2) -->
      <div v-if="tab === 'hypothesen'" class="tab-content">
        <h4>G6-1 Hypothesen-Tree — alternative Erklärungen sammeln + begründet verwerfen</h4>
        <table class="tbl">
          <thead><tr><th>Beurteilung-ID</th><th>Hypothese</th><th>Status</th><th>Begründung</th><th></th></tr></thead>
          <tbody>
            <tr v-for="h in store.hypothesen" :key="h.id" :class="`hyp-${h.status}`">
              <td>{{ h.beurteilung_id }}</td>
              <td>{{ h.hypothese_text }}</td>
              <td>
                <select :value="h.status" @change="updateHyp(h, ($event.target as HTMLSelectElement).value)">
                  <option value="offen">offen</option>
                  <option value="verworfen">verworfen</option>
                  <option value="akzeptiert">akzeptiert</option>
                </select>
              </td>
              <td>{{ h.begruendung }}</td>
              <td>
                <button class="btn-link" @click="editHyp(h)" title="Bearbeiten">✏</button>
                <button class="btn-link" @click="store.deleteHypothese(h.id, aktuell.name)" title="Löschen">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="add-form column">
          <select v-model.number="newHyp.beurteilung_id">
            <option v-for="u in store.beurteilungen" :key="u.id" :value="u.id">{{ u.nr }} {{ u.titel }}</option>
          </select>
          <input v-model="newHyp.hypothese_text" placeholder="Alternative Erklärung..." />
          <select v-model="newHyp.status">
            <option value="offen">offen</option>
            <option value="verworfen">verworfen</option>
            <option value="akzeptiert">akzeptiert</option>
          </select>
          <input v-model="newHyp.begruendung" placeholder="Begründung (warum verworfen/akzeptiert)" />
          <button v-if="editId.hyp" class="btn-secondary" @click="cancelEdit('hyp')">Abbrechen</button>
          <button class="btn-primary" :disabled="!newHyp.hypothese_text" @click="addHyp">
            {{ editId.hyp ? '💾 Speichern' : '+ Hinzu' }}
          </button>
        </div>

        <h4 style="margin-top: 24px">G6-2 Drittgutachter-Simulator (DIN EN 16775)</h4>
        <div class="add-form">
          <select v-model.number="drittBefundId">
            <option v-for="b in store.befunde" :key="b.id" :value="b.id">{{ b.nr }} {{ b.titel }}</option>
          </select>
          <button class="btn-primary" :disabled="!drittBefundId" @click="openDrittPrompt">📝 Prompt für Reproduktionsanleitung</button>
        </div>

        <h4 style="margin-top: 24px">G6-6 Cross-Reference-Linter</h4>
        <button class="btn-secondary" @click="runCrossRef">🔍 Struktur prüfen</button>
        <div v-if="crossRefResult" :class="['result-card', crossRefResult.ok ? 'status-ok' : 'status-blockiert']">
          <strong v-if="crossRefResult.ok">✓ Struktur sauber</strong>
          <strong v-else>⚠ {{ crossRefResult.errors.length }} Fehler · {{ crossRefResult.warnings.length }} Warnungen</strong>
          <ul><li v-for="(h, i) in crossRefResult.hints" :key="i">
            <strong>{{ h.level }}</strong>: {{ h.message }}
          </li></ul>
        </div>
      </div>

      <!-- Tab: Peer-Review + Aufbewahrung -->
      <div v-if="tab === 'peer'" class="tab-content">
        <h4>G5-2 Peer-Review</h4>
        <div class="add-form">
          <input v-model="newReviewer" placeholder="Reviewer-Name" />
          <button class="btn-primary" :disabled="!newReviewer" @click="requestPeer">📨 Review anfordern</button>
        </div>
        <div v-for="r in store.peerReviews" :key="r.id" class="sub-card">
          <strong>{{ r.reviewer_name }}</strong>
          <span :class="`status-${r.status}`" class="status-badge">{{ r.status }}</span>
          <span class="hint">angefordert: {{ r.angefordert_am }}</span>
          <button v-if="r.status !== 'abgeschlossen'" class="btn-link" @click="closePeerReview(r.id)">✓ Abschließen</button>
          <ul>
            <li v-for="(k, i) in r.kommentare" :key="i">
              <strong>{{ k.kapitel }}</strong> ({{ k.author }}): {{ k.text }}
            </li>
          </ul>
          <div v-if="r.status !== 'abgeschlossen'" class="add-form">
            <input v-model="peerKomm[r.id].kapitel" placeholder="Kapitel (II/IV/V/VI/...)" style="width:140px" />
            <input v-model="peerKomm[r.id].text" placeholder="Kommentar" style="flex:1" />
            <input v-model="peerKomm[r.id].author" placeholder="Author" style="width:160px" />
            <button class="btn-primary" :disabled="!peerKomm[r.id].text" @click="addKomm(r.id)">+ Kommentar</button>
          </div>
        </div>

        <h4 style="margin-top: 24px">G5-5 10-Jahre-Aufbewahrung</h4>
        <div v-if="store.aufbewahrung">
          <strong>Archiv bis:</strong> {{ store.aufbewahrung.archiv_bis_datum }}
          ({{ store.aufbewahrung.tage_verbleibend }} Tage verbleibend)
        </div>
        <button class="btn-secondary" @click="setAufbew">📅 10 Jahre aktivieren</button>

        <h4 style="margin-top: 24px">G6-7 Anonymisierte Vorschau</h4>
        <button class="btn-secondary" @click="loadAnon">👤 Anonymisieren</button>
        <pre v-if="anonResult" class="mono" style="max-height:400px; overflow:auto; background:#f5f5f5; padding:8px">{{ JSON.stringify(anonResult, null, 2) }}</pre>
      </div>

      <!-- Tab: Validator -->
      <div v-if="tab === 'validator'" class="tab-content">
        <h4>G5-1 — Pre-Export-Validator + Sprach-Linter</h4>
        <div class="row">
          <button class="btn-primary" @click="runValidator">🔍 Validator ausführen</button>
          <button class="btn-secondary" @click="openPreview">👁 DOCX-Vorschau</button>
        </div>
        <div v-if="validatorResult">
          <div :class="['result-card', validatorResult.release_ready ? 'status-ok' : 'status-blockiert']">
            <strong v-if="validatorResult.release_ready">✓ Release-Ready</strong>
            <strong v-else>⛔ NICHT release-ready — {{ validatorResult.errors_count }} Fehler</strong>
            <span> · {{ validatorResult.warnings_count }} Sprach-Warnungen</span>
          </div>
          <!-- #693 nur sichtbar wenn Inhalt -->
          <div v-if="!validatorResult.errors?.length && !validatorResult.sprach_warnings?.length"
               class="status-ok" style="padding:12px; margin-top:8px; border-radius:4px;">
            ✓ Keine Fehler, keine Sprach-Warnungen — alles in Ordnung.
          </div>
          <div v-if="validatorResult.errors?.length">
            <h5>Errors ({{ validatorResult.errors.length }})</h5>
            <ul><li v-for="(e, i) in validatorResult.errors" :key="i">{{ e.message }}</li></ul>
          </div>
          <div v-if="validatorResult.sprach_warnings?.length">
            <h5>Sprach-Warnungen ({{ validatorResult.sprach_warnings.length }})</h5>
            <ul><li v-for="(w, i) in validatorResult.sprach_warnings.slice(0, 30)" :key="i">
              <strong>{{ w.scope }}</strong> — <em>{{ w.term }}</em>: {{ w.vorschlag }}
            </li></ul>
          </div>
        </div>
      </div>
    </div>

    <!-- #690 DOCX-Vorschau -->
    <div v-if="previewOpen" class="modal-bg" @mousedown.self="previewOpen = false">
      <div class="modal preview-modal">
        <div class="preview-header">
          <h3>👁 DOCX-Vorschau</h3>
          <div>
            <button class="btn-secondary" @click="previewOpen = false">Schließen</button>
            <button class="btn-primary" @click="() => { previewOpen = false; exportDocx(); }">📄 In Word exportieren</button>
          </div>
        </div>
        <div class="preview-body word-page">
          <p class="vertraulichkeit">[{{ aktuell.vertraulichkeit || 'STRENG VERTRAULICH' }}]</p>
          <h1 class="doc-title">{{ aktuell.gutachten_art === 'privat' ? 'PRIVATGUTACHTEN' : 'SACHVERSTÄNDIGENGUTACHTEN' }}</h1>

          <!-- Gerichtsgutachten-Deckblatt -->
          <template v-if="(aktuell.gutachten_art || 'gericht') === 'gericht'">
            <p><strong>Gericht:</strong> {{ aktuell.gericht }}<br/>
              <span v-if="aktuell.kammer">{{ aktuell.kammer }}<br/></span>
              Aktenzeichen {{ aktuell.aktenzeichen }}
            </p>
            <p><strong>In dem Rechtsstreit:</strong></p>
            <p class="parteien">
              {{ aktuell.klaeger_name }}<span class="dots">............................................</span> Kläger<br/>
              <span v-if="aktuell.klaeger_anwalt">Prozessbevollmächtigter: {{ aktuell.klaeger_anwalt }}<br/></span>
              <span class="gegen">gegen</span><br/>
              {{ aktuell.beklagter_name }}<span class="dots">............................................</span> Beklagte<br/>
              <span v-if="aktuell.beklagter_anwalt">Prozessbevollmächtigte: {{ aktuell.beklagter_anwalt }}</span>
            </p>
            <p><strong>Thema des Gutachtens:</strong><br/>{{ aktuell.thema }}</p>
            <p><strong>Beweisbeschluss vom:</strong> {{ aktuell.beweisbeschluss_datum }}</p>
          </template>

          <!-- Privatgutachten-Deckblatt -->
          <template v-else>
            <p><strong>Auftraggeber:</strong> {{ aktuell.auftraggeber }}</p>
            <p><strong>Auftragsart:</strong> {{ aktuell.auftrags_art }}</p>
            <p v-if="aktuell.auftrags_nummer"><strong>Auftrags-Nummer:</strong> {{ aktuell.auftrags_nummer }}</p>
            <p v-if="aktuell.auftrags_datum"><strong>Auftragsdatum:</strong> {{ aktuell.auftrags_datum }}</p>
            <p v-if="aktuell.honorarvereinbarung"><strong>Honorarvereinbarung:</strong> {{ aktuell.honorarvereinbarung }}</p>
            <p><strong>Thema:</strong><br/>{{ aktuell.thema }}</p>
          </template>

          <p><strong>Sachverständiger:</strong><br/>
            {{ aktuell.sv_name }}<br/>
            <span v-if="aktuell.sv_zertifizierung">{{ aktuell.sv_zertifizierung }}<br/></span>
            <span v-if="aktuell.sv_anschrift">{{ aktuell.sv_anschrift }}<br/></span>
            <span v-if="aktuell.sv_kontakt">{{ aktuell.sv_kontakt }}</span>
          </p>
          <p><strong>Datum:</strong> {{ new Date().toLocaleDateString('de-DE') }}</p>

          <hr/>
          <h2>II. Untersuchungsauftrag</h2>
          <ol>
            <li v-for="f in store.beweisfragen" :key="f.id">{{ f.frage_text }}</li>
          </ol>

          <h2>III. Verfahrensgang</h2>
          <ul>
            <li v-for="e in store.verfahrensereignisse" :key="e.id">
              <strong>{{ (e.ereignis_datum || '').slice(0, 10) }} — {{ e.titel }}</strong>
              <div v-if="e.empfaenger?.length">(an: {{ (e.empfaenger || []).join(', ') }})</div>
              <div v-if="e.beschreibung">{{ e.beschreibung }}</div>
            </li>
          </ul>

          <h2>IV. Befunderhebung</h2>
          <div v-for="b in store.befunde" :key="b.id" style="margin: 12px 0;">
            <h3>{{ b.nr }} {{ b.titel }}</h3>
            <p v-if="b.methode"><strong>Methode:</strong> {{ b.methode }}</p>
            <p v-if="b.werkzeug_name"><strong>Werkzeug:</strong> {{ b.werkzeug_name }} {{ b.werkzeug_version }}</p>
            <div v-html="sanitizeHtml(b.beschreibung_text)"></div>
          </div>

          <h2>V. Technische Beurteilung</h2>
          <div v-for="u in store.beurteilungen" :key="u.id" style="margin: 12px 0;">
            <h3>{{ u.nr }} {{ u.titel }}</h3>
            <p v-if="u.norm_referenz"><strong>Norm:</strong> {{ u.norm_referenz }}</p>
            <p v-if="u.soll_text"><strong>Soll:</strong></p>
            <div v-html="sanitizeHtml(u.soll_text)"></div>
            <p v-if="u.ist_text"><strong>Ist:</strong></p>
            <div v-html="sanitizeHtml(u.ist_text)"></div>
            <p v-if="u.kausalitaet_text"><strong>Kausalität:</strong></p>
            <div v-html="sanitizeHtml(u.kausalitaet_text)"></div>
            <p v-if="u.bewertung_text"><strong>Würdigung:</strong></p>
            <div v-html="sanitizeHtml(u.bewertung_text)"></div>
          </div>

          <h2>VI. Beantwortung der Beweisfragen</h2>
          <div v-for="f in store.beweisfragen" :key="`a-${f.id}`" style="margin: 8px 0;">
            <p><strong>Frage {{ f.nr }}:</strong> {{ f.frage_text }}</p>
            <p><strong>Antwort:</strong> {{ f.antwort_kurz }} — {{ f.antwort_text }}</p>
          </div>

          <h2>VII. Schlussformel</h2>
          <p>Der Unterzeichnende versichert, das Gutachten unparteiisch, nach bestem Wissen und Gewissen,
            persönlich und nach dem aktuellen Stand der Technik erstellt zu haben.</p>
          <p>{{ aktuell.sv_anschrift?.split(',').pop()?.trim() || '' }}, {{ new Date().toLocaleDateString('de-DE') }}</p>
          <p>_______________________________<br/><strong>{{ aktuell.sv_name }}</strong></p>

          <h2>VIII. Anhang (Asservaten)</h2>
          <table v-if="store.assets.length" border="1" cellspacing="0" cellpadding="4">
            <thead><tr><th>Bezeichnung</th><th>SHA-256</th><th>Akquisition</th></tr></thead>
            <tbody>
              <tr v-for="a in store.assets" :key="a.id">
                <td>{{ a.bezeichnung }}</td>
                <td><code>{{ (a.sha256 || '').slice(0, 16) }}…</code></td>
                <td>{{ a.akquisitions_utc }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Help-Modal (#671) -->
    <div v-if="helpModal.open" class="modal-bg" @mousedown.self="closeHelp">
      <div class="modal help-modal">
        <h3>ℹ {{ helpModal.data?.title || 'Hilfe' }}</h3>
        <p v-if="helpModal.data?.norm" class="help-norm">📜 <strong>Norm:</strong> {{ helpModal.data.norm }}</p>
        <div v-if="helpModal.data?.was" class="help-section">
          <strong>Was die Norm verlangt:</strong>
          <p>{{ helpModal.data.was }}</p>
        </div>
        <div v-if="helpModal.data?.fallstrick" class="help-section help-fallstrick">
          <strong>⚠ Typischer Fallstrick:</strong>
          <p>{{ helpModal.data.fallstrick }}</p>
        </div>
        <div v-if="helpModal.data?.beispiel" class="help-section help-beispiel">
          <strong>✓ Beispiel:</strong>
          <p>{{ helpModal.data.beispiel }}</p>
        </div>
        <div class="modal-actions">
          <button class="btn-primary" @click="closeHelp">Schließen</button>
        </div>
      </div>
    </div>

    <!-- #866/#868/#869/#870: gemeinsames KI-Wizard-Modal (Beurteilung/Drittgutachter) -->
    <WizardPromptModal
      v-if="wizardModal.open"
      :title="wizardModal.title || 'KI-Vorschlag'"
      :prompt="wizardModal.prompt"
      schema-hint="ChatGPT-Antwort als JSON einfügen."
      :busy="wizardModal.busy"
      @apply="onApplyWizard"
      @close="closeWizard"
    >
      <template #before>
        <!-- §407a-Hinweis ist rechtlich bindend und bleibt erhalten -->
        <div class="disclaimer-407a">⚠ KI-Vorschlag — finale Beurteilung erfolgt durch den Sachverständigen persönlich (§ 407a Abs. 2 ZPO).</div>
        <DataPreviewWarning
          :fields="wizardPreviewFields"
          :provider="aiProvider"
          @confirm="wizardModal.confirmed = true"
        />
      </template>
      <template #after>
        <OutputDestinationHint
          destination="Übernimmt die Felder der Beurteilung in den Editor."
          impact="Der Sachverständige prüft und finalisiert die Beurteilung persönlich."
        />
      </template>
    </WizardPromptModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useGerichtsgutachtenStore } from '../../stores/gerichtsgutachten'
import RichEditor from '../../components/RichEditor.vue'
import { sanitizeHtml } from '../../utils/sanitizeHtml'
import WizardPromptModal from '../../components/shared/WizardPromptModal.vue'
import ModuleHelpButton from '../../components/shared/ModuleHelpButton.vue'
import DataPreviewWarning from '../../components/shared/DataPreviewWarning.vue'
import OutputDestinationHint from '../../components/shared/OutputDestinationHint.vue'

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
  { id: 'stammdaten', label: 'Deckblatt' },
  { id: 'selbstcheck', label: 'Selbstcheck (§ 406)' },
  { id: 'beweisfragen', label: 'II. Beweisfragen' },
  { id: 'befunde', label: 'IV. Befunde' },
  { id: 'beurteilungen', label: 'V. Beurteilungen' },
  { id: 'assets', label: 'Asservaten' },
  { id: 'verfahren', label: 'III. Verfahren' },
  { id: 'forensik', label: 'Forensik (MACB/Tools)' },
  { id: 'hypothesen', label: 'Hypothesen-Tree' },
  { id: 'peer', label: 'Peer-Review' },
  { id: 'honorar', label: 'Honorar' },
  { id: 'validator', label: 'Validator + Export' },
]

const newForm = ref<any>({ name: '', gutachten_art: 'gericht',
  gericht: '', kammer: '', aktenzeichen: '', beweisbeschluss_datum: '',
  auftraggeber: '', auftrags_art: '', auftrags_datum: '', auftrags_nummer: '', honorarvereinbarung: '',
  vertraulichkeit: 'STRENG VERTRAULICH', thema: '',
  klaeger_name: '', klaeger_anwalt: '', beklagter_name: '', beklagter_anwalt: '',
  sv_name: '', sv_zertifizierung: '', sv_anschrift: '', sv_kontakt: '' })

const newBF = ref<any>({ nr: 1, frage_text: '', antwort_kurz: '', antwort_text: '' })
const newBefund = ref<any>({ nr: '4.1', titel: '', methode: '', werkzeug_name: '',
  werkzeug_version: '', beschreibung_text: '' })
const newBeurt = ref<any>({ nr: '5.1', titel: '', norm_id: '', norm_referenz: '',
  befund_ids_str: '', soll_text: '', ist_text: '', kausalitaet_text: '', bewertung_text: '' })
const newAsset = ref<any>({ bezeichnung: '', sha256: '', akquisitions_utc: '',
  akquisitions_ort: '', werkzeug_name: '', werkzeug_version: '', gegengezeichnet_von: '' })
const newVerf = ref<any>({ ereignis_typ: 'akteneinsicht', titel: '', beschreibung: '' })
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
const newReviewer = ref('')
const peerKomm = ref<Record<number, any>>({})
const crossRefResult = ref<any>(null)
const logClassResult = ref<any>(null)
const anonResult = ref<any>(null)

const wizardModal = ref<any>({ open: false, prompt: '', title: 'KI-Vorschlag', busy: false, confirmed: false })
// #867/#877: aktiver KI-Provider für die Daten-Transparenz
const aiProvider = ref<'on_prem' | 'cloud'>('on_prem')
const wizardPreviewFields = computed(() => [
  { label: 'Projekt', value: aktuell.value?.name },
  { label: 'Norm', value: newBeurt.value?.norm_id },
  { label: 'Befund-IDs', value: newBeurt.value?.befund_ids_str },
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
    fliesstextSaveStatus.value = r ? '✓ gespeichert' : '⛔ Fehler'
    if (r) {
      lastSelbstcheck.value.beschreibung = fliesstextEdit.value
      fliesstextOriginal.value = fliesstextEdit.value
      setTimeout(() => { fliesstextSaveStatus.value = '' }, 3000)
    }
  } catch (e) { fliesstextSaveStatus.value = '⛔ Fehler' }
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
    ? 'Projekt-Name darf keinen Schrägstrich (/ oder \\) enthalten — Aktenzeichen/Auftrags-Nr. dafür nutzen.'
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
  if (!newForm.value.name) m.push('Projekt-Name')
  if (newForm.value.gutachten_art === 'privat') {
    if (!newForm.value.auftraggeber) m.push('Auftraggeber')
    if (!newForm.value.auftrags_art) m.push('Auftrags-Art')
  } else {
    if (!newForm.value.gericht) m.push('Gericht')
    if (!newForm.value.aktenzeichen) m.push('Aktenzeichen')
  }
  if (!newForm.value.sv_name) m.push('SV-Name')
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
    fetchAuditSource(name),
  ])
  tab.value = 'stammdaten'
}

// ============================================================
// Phase H — Audit-Source Anzeige + Beweisfragen-Generator + Smart Suggestions
// ============================================================
import apiClient from '../../api/client'
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
  try { await navigator.clipboard.writeText(text); alert('Kopiert.') } catch {}
}

const generatePgQuestions = async () => {
  if (!auditSource.value?.audit_projekt) return
  pgQuestionsImportMsg.value = ''
  try {
    const r = await apiClient.post(
      `/gutachten/${encodeURIComponent(auditSource.value.audit_projekt)}/build-pg-questions-prompt`,
      { auftrags_art: aktuell.value?.auftrags_art || 'Tauglichkeitsprüfung' },
    )
    pgQuestionsPrompt.value = r.data?.prompt || ''
  } catch (e: any) {
    alert('Konnte Prompt nicht erstellen: ' + (e?.response?.data?.error || e.message))
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
    alert('Fehler: ' + (e?.response?.data?.error || e.message))
  }
}

const parseSmartSuggestions = async () => {
  try {
    const r = await apiClient.post('/gutachten/parse-smart-suggestions', { raw_response: smartResponse.value })
    smartParsed.value = r.data
  } catch (e: any) {
    alert('Parse-Fehler: ' + (e?.response?.data?.error || e.message))
  }
}
const closeProjekt = () => { store.aktuell = null }
const saveStammdaten = () => store.updateProjekt(aktuell.value.name, aktuell.value)
const deleteProjekt = async () => {
  if (!confirm('Wirklich löschen?')) return
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
  if (!confirm('Verfahrensereignis löschen?')) return
  try { await fetch(`/api/gutachten/gerichts/verfahren/${id}`, { method: 'DELETE',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}` } })
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
  if (newVerfEmp.value.klaeger) emp.push('Kläger')
  if (newVerfEmp.value.beklagter) emp.push('Beklagter')
  if (newVerfEmp.value.gericht) emp.push('Gericht')
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
  wizardModal.value = { open: true, prompt, title: '🤖 Beurteilungs-Wizard', busy: false, confirmed: false }
}
const closeWizard = () => { wizardModal.value = { open: false, prompt: '', title: 'KI-Vorschlag', busy: false, confirmed: false } }
const onApplyWizard = async (rawText: string) => {
  if (!rawText) return
  wizardModal.value.busy = true
  try {
    const parsed = await store.beurteilungParse(aktuell.value.name, rawText, newBeurt.value.norm_id, null)
    if (parsed?.parsed) {
      Object.assign(newBeurt.value, parsed.parsed)
      closeWizard()
    }
  } finally {
    wizardModal.value.busy = false
  }
}

const exportDocx = () => store.downloadDocx(aktuell.value.name)
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
  wizardModal.value = { open: true, prompt, title: '📝 Reproduktionsanleitung (Drittgutachter)', busy: false, confirmed: false }
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
.header-actions { display: flex; gap: 8px; }
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
.modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: white; padding: 20px; border-radius: 8px; max-width: 800px; width: 90%; max-height: 90vh; overflow-y: auto; }
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
