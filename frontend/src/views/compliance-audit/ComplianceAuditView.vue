<template>
  <div class="compliance-audit-view">
    <div class="header">
      <h2>Compliance-Audit</h2>
      <p>Standortbestimmung gegen ein Framework · Fragen aus Regulierungstexten generieren ·
         Antworten erheben · Wasserstandsmeldung für den Kunden</p>
    </div>

    <FehlerHinweis :text="store.error" @close="store.error = ''" />

    <!-- Projekt-Auswahl/Anlegen -->
    <div v-if="!store.selectedProjektObj && !creating" class="empty-state">
      <h3>Compliance-Audit wählen</h3>
      <p v-if="store.projekte.length > 0">{{ store.projekte.length }} vorhandene Projekte:</p>
      <div v-if="store.projekte.length > 0" class="proj-list">
        <button v-for="p in store.projekte" :key="p.name" class="proj-tile"
                @click="store.selectedProjekt = p.name">
          <strong>{{ p.name }}</strong>
          <span class="proj-fw">{{ (p.frameworks || []).join(', ') }}</span>
        </button>
      </div>
      <button class="btn-primary" @click="startNew">+ Neues Compliance-Audit anlegen</button>
    </div>

    <!-- Anlegen-Form -->
    <div v-else-if="creating" class="form-card">
      <h3>Neues Compliance-Audit</h3>
      <div class="form-row">
        <label>Projektname *</label>
        <input v-model="newForm.name" placeholder="z.B. Acme Audit Q4 2026" />
      </div>
      <div class="form-row">
        <label>Firma</label>
        <select v-model="newForm.unternehmen">
          <option value="">— ohne Firma —</option>
          <option v-for="k in firmenStore.firmen" :key="k.name" :value="k.name">
            {{ k.name }}<span v-if="k.company"> ({{ k.company }})</span>
          </option>
        </select>
        <small class="hint">Verknüpft das Audit mit einer Firma aus der Firmenverwaltung.</small>
      </div>
      <div class="form-row">
        <label>Frameworks (Mehrfachauswahl)</label>
        <div class="fw-checks">
          <label v-for="fw in availableFrameworks" :key="fw.id" class="fw-row">
            <input type="checkbox" :value="fw.id"
                   :checked="newForm.frameworks.includes(fw.id)"
                   @change="toggleFw(newForm, fw.id, $event)" />
            <span class="fw-text">
              <span class="fw-code">{{ fw.id }}</span>
              <span class="fw-label">{{ kurzLabel(fw.label) }}</span>
            </span>
            <span class="fw-status" :class="fw.sections_count ? 'da' : 'leer'">
              {{ fw.sections_count ? fw.sections_count + ' Abschnitte' : 'nicht eingelesen' }}
            </span>
          </label>
        </div>
      </div>
      <div class="form-row">
        <label>Prüfungsfokus</label>
        <textarea v-model="newForm.pruefungsfokus" rows="3"
                  placeholder="Was ist Schwerpunkt des Audits? z.B. 'Schwerpunkt auf NIS2-Lieferantenrisiko und IKT-Drittparteien'"></textarea>
      </div>
      <div class="form-actions">
        <small v-if="!newForm.name || newForm.frameworks.length === 0" class="hint warn">
          {{ !newForm.name ? 'Projektname fehlt.' : '' }}
          {{ newForm.frameworks.length === 0 ? 'Mindestens ein Framework auswählen.' : '' }}
        </small>
        <button class="btn-secondary" @click="creating = false">Abbrechen</button>
        <button class="btn-primary" @click="onCreate"
                :disabled="!newForm.name || newForm.frameworks.length === 0">Anlegen</button>
      </div>
    </div>

    <!-- Aktives Projekt -->
    <template v-else-if="store.selectedProjektObj">
      <div class="proj-selector">
        <select v-model="store.selectedProjekt">
          <option v-for="p in store.projekte" :key="p.name" :value="p.name">
            {{ p.name }} — {{ (p.frameworks || []).join(', ') }}
          </option>
        </select>
        <FirmaSelector
          :model-value="(store.selectedProjektObj as any)?.unternehmen || ''"
          :saving="reassignSaving"
          :success-text="reassignMsg.ok"
          :error-text="reassignMsg.err"
          @save="onReassignFirma"
        />
        <button class="btn-secondary" @click="startNew">+ Neu</button>
        <button class="btn-secondary" @click="editProjektOpen = true">⚙️ Bearbeiten</button>
        <button class="btn-secondary" @click="openKonvertWizard" :title="'Audit→Privatgutachten — § 407a-konform'">
          📋 Als Privatgutachten weiterführen
        </button>
        <button class="btn-danger" @click="confirmDelete">🗑️ Löschen</button>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button v-for="t in tabs" :key="t.id"
                :class="['tab-btn', { active: activeTab === t.id }]"
                @click="activeTab = t.id">
          {{ t.label }}
          <span v-if="t.id === 'fragen' && store.fragen.length" class="badge">{{ store.fragen.length }}</span>
        </button>
      </div>

      <!-- TAB: Übersicht -->
      <div v-if="activeTab === 'overview'" class="tab-content">
        <div class="stat-grid">
          <div class="stat-card">
            <div class="stat-num">{{ store.fragen.length }}</div>
            <div class="stat-lbl">Fragen</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ answeredCount }}</div>
            <div class="stat-lbl">Beantwortet ({{ answeredPct }}%)</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ store.selectedProjektObj.frameworks?.length || 0 }}</div>
            <div class="stat-lbl">Frameworks</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{{ totalSectionsAvail }}</div>
            <div class="stat-lbl">Regulierungs-Abschnitte</div>
          </div>
        </div>

        <div class="info-card">
          <h4>📋 Workflow</h4>
          <ol>
            <li><strong>Fragen-Tab:</strong> ChatGPT-Prompts pro Framework generieren, in ChatGPT einfügen, Antworten zurück importieren</li>
            <li><strong>Fragen bearbeiten:</strong> Antworten und Bewertungen ergänzen</li>
            <li><strong>Berichte-Tab:</strong> Entwurf per KI formulieren, dann Bericht erzeugen (Gesamt, Fragen-Status, Maßnahmenplan) als DOCX/PDF</li>
            <li><strong>Export:</strong> Berichte über das Berichts-Center, Fragebogen als Excel im Fragen-Tab</li>
          </ol>
        </div>

        <div class="info-card">
          <h4>📌 Prüfungsfokus</h4>
          <p v-if="store.selectedProjektObj.pruefungsfokus">{{ store.selectedProjektObj.pruefungsfokus }}</p>
          <p v-else class="muted">Kein Prüfungsfokus gesetzt — über "⚙️ Bearbeiten" hinzufügen.</p>
        </div>
      </div>

      <!-- TAB: Fragen -->
      <div v-if="activeTab === 'fragen'" class="tab-content">
        <div class="fragen-toolbar">
          <button class="btn-primary" @click="generatePromptOpen = true">🤖 ChatGPT-Prompt generieren</button>
          <button class="btn-secondary" @click="importFragenOpen = true">📥 Antwort importieren</button>
          <button class="btn-secondary" @click="newFrageOpen = true">+ Manuelle Frage</button>
          <DownloadButton
            v-if="store.fragen.length > 0"
            :endpoint="`/compliance-audit/${encodeURIComponent(store.selectedProjekt || '')}/fragebogen/export`"
            label="📊 Excel-Fragebogen"
          />
          <ImportButton
            v-if="store.selectedProjekt"
            :endpoint="`/compliance-audit/${encodeURIComponent(store.selectedProjekt)}/fragebogen/import`"
            label="⬆️ Excel-Import"
            @imported="onExcelImported"
          />
          <input v-model="fragenSearch" placeholder="🔎 Fragen durchsuchen…" class="search-input" />
          <select v-model="fragenFilterFw">
            <option value="">Alle Frameworks</option>
            <option v-for="fw in fragenFrameworks" :key="fw" :value="fw">{{ fw }}</option>
          </select>
        </div>

        <div v-if="visibleFragen.length === 0" class="empty">
          Noch keine Fragen.
          <span v-if="store.fragen.length > 0">Filter prüfen.</span>
          <span v-else>Klick auf "ChatGPT-Prompt generieren" oben.</span>
        </div>

        <table v-else class="fragen-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Framework</th>
              <th>Section</th>
              <th>Thema</th>
              <th>Frage / Antwort</th>
              <th>Bewertung</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in visibleFragen" :key="f.id">
              <td>{{ f.question_num }}</td>
              <td><span class="fw-tag">{{ f.framework }}</span></td>
              <td><code class="ref">{{ f.section_ref }}</code></td>
              <!-- #1728: Thema umbrechen + nach 3 Zeilen kuerzen; voller Text als Tooltip. -->
              <td class="thema-cell"><span class="thema-text" :title="f.thema">{{ f.thema }}</span></td>
              <td class="frage-cell">
                <strong>{{ f.frage }}</strong>
                <p v-if="f.antwort" class="antwort-text">{{ f.antwort }}</p>
                <p v-else class="muted">— noch nicht beantwortet —</p>
              </td>
              <td>
                <span :class="['bw-pill', bewertungClass(f.bewertung)]">{{ f.bewertung || '?' }}</span>
              </td>
              <td>
                <button class="btn-icon" @click="editFrage(f)" title="Bearbeiten">✏️</button>
                <button class="btn-icon" @click="onDeleteFrage(f.id)" title="Löschen">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- TAB: Auditbericht -->
      <!-- TAB: Dashboard (#1726) — geteilte Komponente wie in CRA/NIS2/AI-Act/DSGVO.
           Gefuellt aus dem BERECHNETEN Compliance-Stand, nicht aus einem eigenen
           Reifegrad-Schema: Audit und Wasserstandsmeldung zeigen dieselbe Zahl. -->
      <div v-if="activeTab === 'dashboard'" class="tab-content">
        <ModuleDashboard
          :gesamt="{ percent: dashPercent, ampel: dashAmpel }"
          :gesamt-stats="dashStats"
          :bereiche="dashBereiche"
          :offene-punkte="dashLuecken"
          :schwelle="100"
          :mit-dokumente="false"
          :mit-risiken="false"
          @open-bereich="activeTab = 'fragen'"
          @open-luecken="activeTab = 'fragen'"
          @open-punkt="activeTab = 'fragen'"
        />
        <p v-if="!dashGeladen" class="hint">Compliance-Stand wird berechnet …</p>
      </div>

      <!-- TAB: Berichte (#1727) — EIN Tab.
           Vorher gab es "Bericht" und "Berichts-Center" nebeneinander: beide
           erzeugten einen Auditbericht als DOCX, nur mit verschiedenen Renderern.
           Eigenstaendig war daran nur der KI-Entwurf — der steht jetzt oben als
           Schritt 1, das Berichts-Center darunter als Schritt 2. -->
      <div v-if="activeTab === 'berichte'" class="tab-content">
        <section class="entwurf-box">
          <div class="entwurf-kopf">
            <div>
              <h3>1. Auditbericht-Entwurf</h3>
              <p class="hint">
                Formuliert Gesamtbewertung, Einordnung je Framework und Maßnahmen.
                Der Gesamtbericht unten übernimmt den Entwurf, wenn er vorliegt —
                ohne Entwurf entsteht er rein aus den Daten.
              </p>
            </div>
            <button class="btn-primary" @click="onBuildGutachtenPrompt"
                    :disabled="store.fragen.length === 0 || berichtBusy">
              {{ berichtBusy ? '⏳ erzeugt …' : '🤖 Entwurf erzeugen' }}
            </button>
          </div>

          <p v-if="!store.draftPayload" class="empty">
            Noch kein Entwurf.
            <span v-if="store.fragen.length === 0">Erst Fragen erstellen und beantworten.</span>
          </p>

          <div v-else class="bericht-preview">
            <div class="e-kopf">
              <p class="entwurf-stand"><strong>{{ store.draftPayload.gesamtbewertung }}</strong></p>
              <div class="e-aktionen">
                <button v-if="!entwurfBearbeiten" class="btn-secondary" @click="starteEntwurf">
                  ✏️ Entwurf überarbeiten
                </button>
                <template v-else>
                  <button class="btn-secondary" @click="entwurfBearbeiten = false">Abbrechen</button>
                  <button class="btn-primary" :disabled="entwurfSpeichert" @click="speichereEntwurf">
                    💾 Speichern
                  </button>
                </template>
              </div>
            </div>

            <!-- Ansicht -->
            <template v-if="!entwurfBearbeiten">
              <details open>
                <summary>Zusammenfassung</summary>
                <ProsaText :text="store.draftPayload.zusammenfassung || '—'" />
              </details>
              <details>
                <summary>Einordnung je Framework</summary>
                <div v-for="fw in (store.draftPayload.framework_bewertungen || [])"
                     :key="fw.framework" class="fw-block">
                  <strong>{{ fw.framework }}</strong>
                  <ProsaText v-if="fw.bewertung" :text="fw.bewertung" />
                  <p v-if="(fw.staerken || []).length"><em>Stärken:</em> {{ (fw.staerken || []).join(' · ') }}</p>
                  <p v-if="(fw.luecken || []).length"><em>Lücken:</em> {{ (fw.luecken || []).join(' · ') }}</p>
                </div>
              </details>
              <!-- #1783: Vorher stand die Begründung als <p> direkt hinter dem
                   Maßnahmentitel und der Prioritäts-Pille in derselben Zeile —
                   drei Dinge ohne Abstand, die wie ein Satz aussahen. -->
              <details>
                <summary>Handlungsempfehlungen</summary>
                <ol class="empfehlungen">
                  <li v-for="(m, i) in (store.draftPayload.handlungsempfehlungen || [])" :key="i">
                    <div class="e-zeile">
                      <strong class="e-titel">{{ m.massnahme }}</strong>
                      <span v-if="m.prioritaet" :class="'prio prio-' + m.prioritaet">
                        Priorität {{ m.prioritaet }}
                      </span>
                    </div>
                    <ProsaText v-if="m.begruendung" class="e-grund" :text="m.begruendung" eng />
                  </li>
                </ol>
              </details>
              <details>
                <summary>Fazit</summary>
                <ProsaText :text="store.draftPayload.fazit || '—'" />
              </details>
              <p class="ki-hinweis">
                🤖 KI-generiert, fachlich noch nicht geprüft — über „Entwurf überarbeiten“
                anpassen und damit übernehmen.
              </p>
            </template>

            <!-- Bearbeiten -->
            <template v-else>
              <label class="e-feld">Gesamtbewertung
                <input v-model="entwurf.gesamtbewertung" />
              </label>
              <label class="e-feld">Zusammenfassung
                <textarea v-model="entwurf.zusammenfassung" rows="5"></textarea>
              </label>

              <div v-for="(fw, fi) in entwurf.framework_bewertungen" :key="fi" class="fw-block">
                <strong>{{ fw.framework }}</strong>
                <label class="e-feld">Bewertung
                  <textarea v-model="fw.bewertung" rows="3"></textarea>
                </label>
                <label class="e-feld">Stärken <span class="e-klein">(eine je Zeile)</span>
                  <textarea :value="(fw.staerken || []).join('\n')" rows="2"
                            @input="fw.staerken = entwurfZeilen($event)"></textarea>
                </label>
                <label class="e-feld">Lücken <span class="e-klein">(eine je Zeile)</span>
                  <textarea :value="(fw.luecken || []).join('\n')" rows="2"
                            @input="fw.luecken = entwurfZeilen($event)"></textarea>
                </label>
              </div>

              <div class="empfehlungen-edit">
                <strong>Handlungsempfehlungen</strong>
                <div v-for="(m, mi) in entwurf.handlungsempfehlungen" :key="mi" class="e-edit">
                  <div class="e-edit-kopf">
                    <input v-model="m.massnahme" placeholder="Maßnahme" />
                    <select v-model="m.prioritaet">
                      <option value="hoch">Priorität hoch</option>
                      <option value="mittel">Priorität mittel</option>
                      <option value="niedrig">Priorität niedrig</option>
                    </select>
                    <button class="btn-icon" title="Empfehlung entfernen"
                            @click="entwurf.handlungsempfehlungen.splice(mi, 1)">🗑️</button>
                  </div>
                  <textarea v-model="m.begruendung" rows="2" placeholder="Begründung"></textarea>
                </div>
                <button class="btn-secondary" @click="entwurf.handlungsempfehlungen.push(
                  { massnahme: '', begruendung: '', prioritaet: 'mittel' })">
                  + Empfehlung
                </button>
              </div>

              <label class="e-feld">Fazit
                <textarea v-model="entwurf.fazit" rows="4"></textarea>
              </label>
            </template>
          </div>
        </section>

        <section>
          <h3>2. Bericht erzeugen</h3>
          <ReportCenterPanel
            v-if="store.selectedProjekt"
            :api-base="`/compliance-audit/projekte/${encodeURIComponent(store.selectedProjekt)}`"
            title="Audit-Berichts-Center"
          />
        </section>
      </div>

      <!-- TAB: Wasserstandsmeldung (v7.4.0) -->
      <div v-if="activeTab === 'wasserstand'" class="tab-content">
        <WasserstandPanel :projekt="store.selectedProjekt || ''" />
      </div>

    </template>

    <!-- ==== DIALOGE ==== -->

    <!-- Fragen generieren (#1723) — gemeinsame Komponente wie in allen anderen
         Modulen: Prompt anzeigen, "Direkt mit KI" oder Antwort einfuegen.
         Vorher zwei getrennte Dialoge, nur Copy/Paste. -->
    <div v-if="generatePromptOpen && generatedPrompts.length === 0" class="modal-overlay"
         @mousedown.self="generatePromptOpen = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>🤖 Fragen generieren</h3>
          <button class="btn-close" @click="generatePromptOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Anzahl Fragen pro Framework</label>
            <input type="number" v-model.number="promptBatchSize" min="3" max="50" />
          </div>
          <label class="check-row">
            <input type="checkbox" v-model="promptTestMode" />
            Test-Modus (nur 5 Fragen pro Framework)
          </label>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="generatePromptOpen = false">Abbrechen</button>
          <button class="btn-primary" @click="onBuildFragenPrompt" :disabled="promptBusy">
            {{ promptBusy ? 'Erstelle…' : 'Weiter' }}
          </button>
        </div>
      </div>
    </div>

    <WizardPromptModal
      v-if="generatedPrompts.length > 0"
      :title="`Fragen generieren — ${aktiverPrompt?.framework || ''}`"
      :prompt="aktiverPrompt?.content || ''"
      :busy="importBusy"
      schema-hint="Erwartet eine JSON-Liste von Fragen. Mehrere Frameworks werden einzeln abgearbeitet."
      @apply="onFragenAusKi"
      @close="closeFragenWizard"
    >
      <template #before>
        <div v-if="generatedPrompts.length > 1" class="fw-switch">
          <span class="muted">Framework:</span>
          <button v-for="(p, i) in generatedPrompts" :key="p.framework"
                  :class="['fw-chip', { active: i === promptIndex }]"
                  @click="promptIndex = i">
            {{ p.framework }}
          </button>
        </div>
      </template>
    </WizardPromptModal>

    <!-- Fragen importieren -->
    <div v-if="importFragenOpen" class="modal-overlay" @mousedown.self="importFragenOpen = false">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>📥 ChatGPT-Antwort importieren</h3>
          <button class="btn-close" @click="importFragenOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <p class="hint">Kopiere die JSON-Antwort von ChatGPT in das Feld unten.</p>
          <textarea v-model="importRaw" rows="14" class="prompt-textarea"
                    placeholder='[{"framework":"NIS2","section_ref":"Art. 21","thema":"...","frage":"..."}]'></textarea>
          <label class="check-row">
            <input type="checkbox" v-model="importReplace" />
            Bestehende Fragen ersetzen (sonst anhängen)
          </label>
          <span v-if="importResult" class="hint" :class="{ ok: importResult.ok }">{{ importResult.msg }}</span>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="importFragenOpen = false">Abbrechen</button>
          <button class="btn-primary" @click="onImportFragen" :disabled="!importRaw || importBusy">
            {{ importBusy ? 'Importiere…' : 'Importieren' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Frage editieren / Neu -->
    <div v-if="editingFrage || newFrageOpen" class="modal-overlay" @mousedown.self="closeFrageEditor">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>{{ editingFrage ? 'Frage bearbeiten' : 'Neue Frage' }}</h3>
          <button class="btn-close" @click="closeFrageEditor">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Framework</label>
            <select v-model="frageEditor.framework">
              <option v-for="fw in store.selectedProjektObj?.frameworks || []" :key="fw" :value="fw">{{ fw }}</option>
            </select>
          </div>
          <div class="form-row">
            <label>Section-Referenz</label>
            <input v-model="frageEditor.section_ref" placeholder="z.B. Art. 21 Abs. 2" />
          </div>
          <div class="form-row">
            <label>Thema</label>
            <input v-model="frageEditor.thema" placeholder="z.B. Lieferantenrisiko" />
          </div>
          <div class="form-row">
            <label>Frage *</label>
            <textarea v-model="frageEditor.frage" rows="3"></textarea>
          </div>
          <div class="form-row">
            <label>Antwort</label>
            <textarea v-model="frageEditor.antwort" rows="4"></textarea>
          </div>
          <div class="form-row">
            <label>Bewertung</label>
            <select v-model="frageEditor.bewertung">
              <option value="">— wählen —</option>
              <option value="ja">Ja (umgesetzt)</option>
              <option value="teilweise">Teilweise</option>
              <option value="nein">Nein (nicht umgesetzt)</option>
              <option value="unklar">Unklar</option>
              <option value="nicht_anwendbar">Nicht anwendbar</option>
            </select>
          </div>
          <div class="form-row">
            <label>Kommentar</label>
            <textarea v-model="frageEditor.kommentar" rows="2"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="closeFrageEditor">Abbrechen</button>
          <button class="btn-primary" @click="onSaveFrage" :disabled="!frageEditor.frage">Speichern</button>
        </div>
      </div>
    </div>

    <!-- Auditbericht (#1723): gemeinsame Komponente — Prompt, "Direkt mit KI"
         oder Antwort einfuegen. Vorher zwei Eigenbau-Dialoge mit Copy/Paste. -->
    <WizardPromptModal
      v-if="berichtPromptText"
      title="Auditbericht erzeugen"
      :prompt="berichtPromptText"
      :busy="berichtBusy"
      force-json
      schema-hint="Erwartet ein JSON-Objekt mit gesamtbewertung, zusammenfassung, framework_bewertungen, handlungsempfehlungen und fazit."
      @apply="onBerichtAusKi"
      @close="berichtPromptText = ''"
    />
    <!-- Phase H-A — Audit → PG Konversions-Wizard (4 Steps) -->
    <div v-if="konvertOpen" class="modal-overlay" @mousedown.self="closeKonvert">
      <div class="modal-content modal-wide">
        <div class="modal-header">
          <h3>📋 Audit-Bericht → Privatgutachten ({{ konvertStep }}/4)</h3>
          <button class="btn-close" @click="closeKonvert">✕</button>
        </div>
        <div class="modal-body">
          <!-- Step 1: Auftragsverhältnis + Vorbefassungs-Hinweis + Audit-Summary -->
          <div v-if="konvertStep === 1">
            <h4>Schritt 1 — Auftragsverhältnis &amp; Befangenheit (§ 406/407a ZPO)</h4>
            <!-- #705 — Variante wählen -->
            <div class="info-card" style="margin-bottom:12px;">
              <h4>In welchem Verhältnis steht der Audit zum Gutachten?</h4>
              <label class="check-row" style="align-items:flex-start;">
                <input type="radio" :value="false" v-model="konvertEinheitlich" @change="reloadWarning" />
                <span><strong>Separater Vor-Audit</strong> — Der Audit war eine eigenständige frühere Tätigkeit.
                  <em>(Vorbefassung i.S.d. § 406 ZPO → Befangenheit für späteres Gerichtsgutachten)</em></span>
              </label>
              <label class="check-row" style="align-items:flex-start; margin-top:8px;">
                <input type="radio" :value="true" v-model="konvertEinheitlich" @change="reloadWarning" />
                <span><strong>Audit ist Teil dieses Gutachtens</strong> — Einheitlicher Auftrag; der Audit bildet die Befundgrundlage.
                  <em>(Keine Vorbefassung i.S.d. § 406 ZPO, § 407a ZPO eigene Befunderhebung)</em></span>
              </label>
            </div>
            <div class="warning-box"
                 :style="`background:${konvertEinheitlich ? '#e8f5e9' : '#fff3e0'};border:1px solid ${konvertEinheitlich ? '#43a047' : '#ff9800'};padding:12px;border-radius:6px;white-space:pre-wrap;`">{{ konvertWarning?.warning || '' }}</div>
            <div class="info-card" style="margin-top:12px;">
              <h4>📊 Audit-Quelle</h4>
              <ul>
                <li><strong>Firma:</strong> {{ konvertSummary?.firma || '—' }}</li>
                <li><strong>Audit-Datum:</strong> {{ (konvertSummary?.created_at || '').slice(0,10) }}</li>
                <li><strong>Frameworks:</strong> {{ (konvertSummary?.frameworks || []).join(', ') || '—' }}</li>
                <li><strong>Anzahl Assessments:</strong> {{ konvertSummary?.anzahl_assessments || 0 }}</li>
                <li><strong>Avg/Min-Score:</strong> {{ konvertSummary?.avg_score ?? '—' }} / {{ konvertSummary?.min_score ?? '—' }}</li>
              </ul>
            </div>
            <label v-if="!konvertEinheitlich" class="check-row" style="margin-top:12px;">
              <input type="checkbox" v-model="konvertAcceptance" />
              <strong>Ich habe den Vorbefassungs-Hinweis verstanden und akzeptiere die Konsequenzen.</strong>
            </label>
            <p v-else class="hint ok" style="margin-top:12px;">
              ✓ Da der Audit Teil desselben Gutachtenauftrags ist, ist keine gesonderte Befangenheits-Akzeptanz erforderlich.
            </p>
          </div>

          <!-- Step 2: PG-Stammdaten -->
          <div v-if="konvertStep === 2">
            <h4>Schritt 2 — Privatgutachten-Stammdaten</h4>
            <div class="form-row">
              <label>PG-Name *</label>
              <input v-model="konvertForm.pg_name" placeholder="z.B. PG-2026-001" />
            </div>
            <div class="form-row">
              <label>Sachverständige(r) *</label>
              <input v-model="konvertForm.sv_name" placeholder="Vor- und Nachname" />
            </div>
            <div class="form-row">
              <label>Auftrags-Art</label>
              <select v-model="konvertForm.auftrags_art" @change="onAuftragsArtChange">
                <option>Tauglichkeitsprüfung</option>
                <option>Beweissicherung</option>
                <option>Schaden-Gutachten</option>
                <option>Wertgutachten</option>
                <option>Kaufberatung</option>
                <option>Sonstiges</option>
              </select>
            </div>
            <div class="form-row">
              <label>Auftrags-Datum</label>
              <input type="date" v-model="konvertForm.auftrags_datum" />
            </div>
            <div class="form-row">
              <label>Auftrags-Nummer</label>
              <input v-model="konvertForm.auftrags_nummer" />
            </div>
            <div class="form-row">
              <label>Thema (Auto-Vorschlag — editierbar)</label>
              <textarea v-model="konvertForm.thema" rows="3"></textarea>
              <button class="btn-mini" @click="loadAutoThema">🔄 Auto-Vorschlag neu laden</button>
            </div>
            <div class="form-row">
              <label>Honorarvereinbarung</label>
              <textarea v-model="konvertForm.honorarvereinbarung" rows="2"></textarea>
            </div>
          </div>

          <!-- Step 3: Befund-Kandidaten Auswahl (Score<70) -->
          <div v-if="konvertStep === 3">
            <h4>Schritt 3 — Befund-Kandidaten aus Audit (§ 407a — bitte persönlich formulieren!)</h4>
            <p class="hint">Die folgenden Audit-Sections mit Score &lt; 70 können als <strong>leere Befund-Skeletons</strong> ins PG übernommen werden. Die Befund-Texte bleiben LEER — Sie als SV müssen persönlich neu formulieren (§ 407a ZPO persönliche Leistungserbringung).</p>
            <div v-if="konvertGaps.length === 0" class="empty">Keine Gaps mit Score &lt; 70 gefunden.</div>
            <table v-else class="fragen-table">
              <thead><tr><th></th><th>Section</th><th>Score</th><th>Kommentar (Audit)</th></tr></thead>
              <tbody>
                <tr v-for="(g, i) in konvertGaps" :key="i">
                  <td><input type="checkbox" v-model="g._selected" /></td>
                  <td><code>{{ g.framework_section }}</code></td>
                  <td>{{ g.score }}/100</td>
                  <td class="thema-cell">{{ (g.comment || '').slice(0, 120) }}</td>
                </tr>
              </tbody>
            </table>
            <p class="hint">{{ selectedGapCount }} von {{ konvertGaps.length }} Gaps ausgewählt.</p>
          </div>

          <!-- Step 4: Zusammenfassung + Bestätigung -->
          <div v-if="konvertStep === 4">
            <h4>Schritt 4 — Zusammenfassung &amp; Konvertierung</h4>
            <div class="info-card">
              <h4>📋 Übernahme-Plan</h4>
              <ul>
                <li><strong>PG-Name:</strong> {{ konvertForm.pg_name }}</li>
                <li><strong>SV:</strong> {{ konvertForm.sv_name }}</li>
                <li><strong>Auftrags-Art:</strong> {{ konvertForm.auftrags_art }}</li>
                <li><strong>Thema:</strong> {{ konvertForm.thema }}</li>
                <li><strong>Befund-Kandidaten:</strong> {{ selectedGapCount }}</li>
                <li><strong>Audit-Snapshot:</strong> SHA-256-gesichert (Audit-Trail)</li>
                <li><strong>Auftragsverhältnis:</strong>
                  {{ konvertEinheitlich ? 'Audit ist Teil des Gutachtens — keine Vorbefassung (§ 406 ZPO)' : 'Separater Vor-Audit — Vorbefassung dokumentiert' }}</li>
                <li><strong>Beweisfragen-Generator:</strong> wird im PG-Tab verfügbar sein</li>
              </ul>
            </div>
            <p v-if="konvertResult" class="hint ok">
              ✓ Konversion erfolgreich. PG „{{ konvertResult.pg_name }}" wurde angelegt.<br>
              SHA-256: <code style="font-size:11px;">{{ konvertResult.audit_snapshot_sha256?.slice(0,32) }}…</code>
            </p>
            <p v-if="konvertError" class="hint" style="color:#c62828;">{{ konvertError }}</p>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="closeKonvert">Abbrechen</button>
          <button v-if="konvertStep > 1" class="btn-secondary" @click="konvertStep--">⟵ Zurück</button>
          <button v-if="konvertStep < 4" class="btn-primary" @click="nextKonvertStep" :disabled="!canAdvance">Weiter ⟶</button>
          <button v-if="konvertStep === 4 && !konvertResult" class="btn-primary" @click="executeKonvert" :disabled="konvertBusy">
            {{ konvertBusy ? 'Konvertiere…' : '✅ Privatgutachten anlegen' }}
          </button>
          <button v-if="konvertResult" class="btn-success" @click="goToPg">📂 PG öffnen</button>
        </div>
      </div>
    </div>

    <!-- Projekt bearbeiten -->
    <div v-if="editProjektOpen" class="modal-overlay" @mousedown.self="editProjektOpen = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Projekt bearbeiten</h3>
          <button class="btn-close" @click="editProjektOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>Frameworks</label>
            <div class="fw-checks">
              <label v-for="fw in availableFrameworks" :key="fw.id" class="fw-row">
                <input type="checkbox" :value="fw.id"
                       :checked="(editForm.frameworks || []).includes(fw.id)"
                       @change="toggleFw(editForm, fw.id, $event)" />
                <span class="fw-text">
                  <span class="fw-code">{{ fw.id }}</span>
                  <span class="fw-label">{{ kurzLabel(fw.label) }}</span>
                </span>
                <span class="fw-status" :class="fw.sections_count ? 'da' : 'leer'">
                  {{ fw.sections_count ? fw.sections_count + ' Abschnitte' : 'nicht eingelesen' }}
                </span>
              </label>
            </div>
          </div>
          <div class="form-row">
            <label>Prüfungsfokus</label>
            <textarea v-model="editForm.pruefungsfokus" rows="3"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="editProjektOpen = false">Abbrechen</button>
          <button class="btn-primary" @click="onUpdateProjekt">Speichern</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useComplianceAuditStore, type GutachtenFrage } from '../../stores/complianceAudit'
import { useFirmenStore } from '../../stores/firmen'
import FirmaSelector from '../../components/shared/FirmaSelector.vue'
import DownloadButton from '../../components/shared/DownloadButton.vue'
import ImportButton from '../../components/shared/ImportButton.vue'
import apiClient from '../../api/client'
import WasserstandPanel from '../../components/compliance-audit/WasserstandPanel.vue'
import WizardPromptModal from '../../components/shared/WizardPromptModal.vue'
import ModuleDashboard from '../../components/shared/ModuleDashboard.vue'
import ReportCenterPanel from '../../components/shared/ReportCenterPanel.vue'
import ProsaText from '../../components/shared/ProsaText.vue'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'

const store = useComplianceAuditStore()

// #1783: Der Entwurf war nur anzusehen. „Fachlich zu prüfen" ohne einen Weg,
// ihn zu ändern, ist eine Aufforderung ins Leere — gespeichert wird über den
// bereits vorhandenen PUT-Endpunkt (store.saveDraft).
const entwurfBearbeiten = ref(false)
const entwurfSpeichert = ref(false)
const entwurf = ref<any>({ gesamtbewertung: '', zusammenfassung: '',
                           framework_bewertungen: [], handlungsempfehlungen: [], fazit: '' })

function entwurfZeilen(e: Event): string[] {
  return (e.target as HTMLTextAreaElement).value
    .split('\n').map(z => z.trim()).filter(Boolean)
}

function starteEntwurf() {
  const d = store.draftPayload || {}
  entwurf.value = {
    ...d,
    gesamtbewertung: d.gesamtbewertung || '',
    zusammenfassung: d.zusammenfassung || '',
    framework_bewertungen: (d.framework_bewertungen || []).map((f: any) => ({
      ...f, staerken: [...(f.staerken || [])], luecken: [...(f.luecken || [])],
    })),
    handlungsempfehlungen: (d.handlungsempfehlungen || []).map((m: any) => ({ ...m })),
    fazit: d.fazit || '',
  }
  entwurfBearbeiten.value = true
}

async function speichereEntwurf() {
  if (!store.selectedProjekt) return
  entwurfSpeichert.value = true
  try {
    await store.saveDraft(store.selectedProjekt, entwurf.value)
    entwurfBearbeiten.value = false
  } finally {
    entwurfSpeichert.value = false
  }
}
const firmenStore = useFirmenStore()

type TabId = 'dashboard' | 'overview' | 'fragen' | 'wasserstand' | 'berichte'
const tabs: { id: TabId; label: string }[] = [
  { id: 'dashboard', label: '📊 Dashboard' },
  { id: 'overview', label: '📋 Übersicht' },
  { id: 'fragen', label: '❓ Fragen' },
  { id: 'wasserstand', label: '🌡️ Wasserstand' },
  { id: 'berichte', label: '📄 Berichte' },
]
const activeTab = ref<TabId>('dashboard')

// #1716: Kanonischer Katalog des Moduls — NICHT die Schlüssel von sectionsCount.
// Die zeigen nur, welche Texte schon eingelesen sind; ohne eingelesenen Korpus war
// die Auswahl leer und 'Anlegen' dadurch dauerhaft deaktiviert.
/** Katalog-Labels beginnen mit dem Code ("NIS2 – EU-Richtlinie + nationale
 *  Umsetzung"). Der Code steht in der Zeile schon als eigene Pille, also wird er
 *  hier abgeschnitten — sonst stand er doppelt und die Zeile lief ueber. */
const kurzLabel = (label: string) => (label || '').replace(/^[A-Z0-9_]+\s*[–-]\s*/, '')

// ── Dashboard (#1726) ───────────────────────────────────────────────────────
// Quelle ist der berechnete Compliance-Stand (/status) — dieselbe Zahl wie in der
// Wasserstandsmeldung. Ein zweites, eigenes Reifegrad-Schema waere eine zweite
// Wahrheit; im Audit ist die Erfuellungsquote der Reifegrad.
const dashStand = ref<any>(null)
const dashGeladen = ref(false)

const AMPEL: Record<string, string> = {
  vollstaendig: 'gruen', weitgehend: 'gelb', teilweise: 'orange',
  nicht: 'rot', unbewertet: 'grau',
}

const dashPercent = computed(() => Math.round(dashStand.value?.quote_prozent ?? 0))
const dashAmpel = computed(() => AMPEL[dashStand.value?.stufe] || 'grau')

const dashStats = computed(() => {
  const f = dashStand.value?.fragen
  if (!f) return []
  return [
    `${f.gesamt} Fragen`,
    `${f.erfuellt} erfüllt`,
    `${f.teilweise} teilweise`,
    `${f.nicht_erfuellt} nicht erfüllt`,
    `${f.offen} offen`,
    `Abdeckung ${dashStand.value.abdeckung_prozent ?? 0} %`,
  ]
})

/** Je Framework eine Bereichskarte — das Pendant zu den Kapitelkarten der anderen Module. */
const dashBereiche = computed(() =>
  (dashStand.value?.frameworks || []).map((fw: any) => ({
    id: fw.framework,
    label: fw.framework,
    percent: Math.round(fw.quote_prozent ?? 0),
    hint: `${fw.label} · ${fw.fragen?.offen ?? 0} von ${fw.fragen?.anwendbar ?? 0} offen`,
  })))

/** Offene Punkte = die Luecken des berechneten Stands, Dringlichkeit zuerst. */
const dashLuecken = computed(() =>
  (dashStand.value?.luecken || []).slice(0, 25).map((lk: any, i: number) => ({
    id: String(lk.question_num ?? i),
    label: `${lk.framework}${lk.section_ref ? ' ' + lk.section_ref : ''}: ${lk.frage}`,
    score: lk.erfuellung === 'nicht_erfuellt' ? 0 : lk.erfuellung === 'teilweise' ? 50 : 25,
  })))

const ladeDashboard = async () => {
  if (!store.selectedProjekt) { dashStand.value = null; return }
  dashGeladen.value = false
  try {
    const r = await apiClient.get(
      `/compliance-audit/${encodeURIComponent(store.selectedProjekt)}/status`)
    dashStand.value = r.data
  } catch { dashStand.value = null } finally { dashGeladen.value = true }
}

const availableFrameworks = computed(() =>
  store.frameworkKatalog.length
    ? store.frameworkKatalog
    : Object.keys(store.sectionsCount).sort().map(
        (id: string) => ({ id, label: id, sections_count: store.sectionsCount[id] || 0 })))
const totalSectionsAvail = computed(() => {
  const fws = store.selectedProjektObj?.frameworks || []
  return fws.reduce((sum, fw) => sum + (store.sectionsCount[fw] || 0), 0)
})

// Projekt-Anlegen / Bearbeiten
const creating = ref(false)
const newForm = reactive({ name: '', frameworks: [] as string[], pruefungsfokus: '', unternehmen: '' })
const editProjektOpen = ref(false)
const editForm = reactive({ frameworks: [] as string[], pruefungsfokus: '' })

const startNew = () => {
  newForm.name = ''
  newForm.frameworks = []
  newForm.pruefungsfokus = ''
  newForm.unternehmen = ''
  creating.value = true
  if (firmenStore.firmen.length === 0) firmenStore.fetchFirmen()
}

const onCreate = async () => {
  const created = await store.createProjekt(newForm)
  if (created) {
    store.selectedProjekt = created.name
    creating.value = false
  }
}

const onUpdateProjekt = async () => {
  if (!store.selectedProjekt) return
  await store.updateProjekt(store.selectedProjekt, {
    frameworks: editForm.frameworks,
    pruefungsfokus: editForm.pruefungsfokus,
  })
  editProjektOpen.value = false
}

// Issue #436: Firma des Projekts nachtraeglich aendern
const reassignSaving = ref(false)
const reassignMsg = ref<{ ok: string; err: string }>({ ok: '', err: '' })
const onReassignFirma = async (newFirma: string) => {
  if (!store.selectedProjekt) return
  reassignSaving.value = true
  reassignMsg.value = { ok: '', err: '' }
  try {
    await store.updateProjekt(store.selectedProjekt, { unternehmen: newFirma } as any)
    await store.fetchProjekte()
    reassignMsg.value.ok = newFirma ? `✓ Firma geändert auf „${newFirma}"` : '✓ Firmenzuordnung entfernt'
    setTimeout(() => { reassignMsg.value = { ok: '', err: '' } }, 4000)
  } catch (e: any) {
    reassignMsg.value.err = e?.response?.data?.error || 'Fehler beim Speichern'
  } finally {
    reassignSaving.value = false
  }
}

const confirmDelete = async () => {
  if (!store.selectedProjekt) return
  if (!confirm(`Projekt "${store.selectedProjekt}" wirklich löschen? (Inkl. aller Fragen)`)) return
  await store.deleteProjekt(store.selectedProjekt)
}

const toggleFw = (target: any, fw: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  if (!Array.isArray(target.frameworks)) target.frameworks = []
  if (checked && !target.frameworks.includes(fw)) target.frameworks.push(fw)
  else if (!checked) target.frameworks = target.frameworks.filter((f: string) => f !== fw)
}

// Fragen
const fragenSearch = ref('')
const fragenFilterFw = ref('')
const fragenFrameworks = computed(() => {
  const set = new Set<string>()
  store.fragen.forEach(f => f.framework && set.add(f.framework))
  return Array.from(set).sort()
})

const visibleFragen = computed(() => {
  let list = store.fragen
  if (fragenFilterFw.value) list = list.filter(f => f.framework === fragenFilterFw.value)
  if (fragenSearch.value) {
    const q = fragenSearch.value.toLowerCase()
    list = list.filter(f =>
      f.frage.toLowerCase().includes(q) ||
      (f.thema || '').toLowerCase().includes(q) ||
      (f.section_ref || '').toLowerCase().includes(q),
    )
  }
  return list
})

const answeredCount = computed(() => store.fragen.filter(f => f.antwort?.trim()).length)
const answeredPct = computed(() => {
  if (store.fragen.length === 0) return 0
  return Math.round((answeredCount.value / store.fragen.length) * 100)
})

const bewertungClass = (b: string): string => {
  const v = (b || '').toLowerCase()
  if (v === 'ja' || v === 'voll' || v === 'erfuellt') return 'ok'
  if (v === 'teilweise') return 'partial'
  if (v === 'nein' || v === 'nicht_erfuellt') return 'bad'
  return 'unknown'
}

// Frage-Editor
const editingFrage = ref<GutachtenFrage | null>(null)
const newFrageOpen = ref(false)
const frageEditor = reactive<Partial<GutachtenFrage>>({
  framework: '', section_ref: '', thema: '', frage: '', antwort: '', bewertung: '', kommentar: '',
})

const editFrage = (f: GutachtenFrage) => {
  editingFrage.value = f
  Object.assign(frageEditor, f)
}

const closeFrageEditor = () => {
  editingFrage.value = null
  newFrageOpen.value = false
  Object.assign(frageEditor, { framework: '', section_ref: '', thema: '', frage: '', antwort: '', bewertung: '', kommentar: '' })
}

const onSaveFrage = async () => {
  if (!frageEditor.frage || !store.selectedProjekt) return
  if (editingFrage.value) {
    await store.updateFrage(editingFrage.value.id, { ...frageEditor })
  } else {
    await store.addFrage(store.selectedProjekt, { ...frageEditor })
  }
  closeFrageEditor()
}

const onDeleteFrage = async (id: number) => {
  if (!confirm('Diese Frage wirklich löschen?')) return
  await store.deleteFrage(id)
}

const onExcelImported = async () => {
  if (store.selectedProjekt) await store.fetchFragen(store.selectedProjekt)
}

// Prompt-Generierung
const generatePromptOpen = ref(false)
const promptBatchSize = ref(15)
const promptTestMode = ref(false)
const promptBusy = ref(false)
const generatedPrompts = ref<any[]>([])
// Mehrere Frameworks ergeben mehrere Prompts; der Dialog arbeitet sie einzeln ab.
const promptIndex = ref(0)
const aktiverPrompt = computed(() => generatedPrompts.value[promptIndex.value] || null)

/** Antwort aus dem gemeinsamen Dialog in den bestehenden Import-Pfad geben. */
const onFragenAusKi = async (rawText: string) => {
  if (!rawText || !store.selectedProjekt) return
  importBusy.value = true
  try {
    const ok = await store.importFragen(store.selectedProjekt, rawText, false)
    if (ok) {
      await store.fetchFragen(store.selectedProjekt)
      await ladeDashboard()
      // Naechstes Framework, sonst fertig.
      if (promptIndex.value < generatedPrompts.value.length - 1) promptIndex.value += 1
      else closeFragenWizard()
    }
  } finally { importBusy.value = false }
}

const closeFragenWizard = () => {
  generatedPrompts.value = []
  promptIndex.value = 0
  generatePromptOpen.value = false
}

const onBuildFragenPrompt = async () => {
  if (!store.selectedProjekt) return
  promptBusy.value = true
  generatedPrompts.value = []
  const res = await store.buildFragenPrompt(store.selectedProjekt, promptBatchSize.value, promptTestMode.value)
  if (res) { generatedPrompts.value = res.prompts || []; promptIndex.value = 0 }
  promptBusy.value = false
}

// Fragen importieren
const importFragenOpen = ref(false)
const importRaw = ref('')
const importReplace = ref(false)
const importBusy = ref(false)
const importResult = ref<{ ok: boolean; msg: string } | null>(null)

const onImportFragen = async () => {
  if (!importRaw.value || !store.selectedProjekt) return
  importBusy.value = true
  importResult.value = null
  const r = await store.importFragen(store.selectedProjekt, importRaw.value, importReplace.value)
  if (r) {
    importResult.value = { ok: true, msg: `${r.imported} Fragen importiert.` }
    importRaw.value = ''
    setTimeout(() => importFragenOpen.value = false, 1500)
  } else {
    importResult.value = { ok: false, msg: store.error || 'Import fehlgeschlagen' }
  }
  importBusy.value = false
}

// Auditbericht (#1723)
const berichtPromptText = ref('')
const berichtBusy = ref(false)
// Der frühere Einzel-Export (/bericht/export) ist entfallen: Das Berichts-Center
// erzeugt den Gesamtbericht mit demselben Inhalt, dazu Fragen-Status und
// Maßnahmenplan, mit Historie und PDF. Zwei Renderer fuer dasselbe Dokument
// waeren zwei Wahrheiten (#1727).

// #1830: Beim Aufräumen der zwei Renderer sind diese beiden Handler mit
// verschwunden — Knopf und Modal blieben stehen. Vue löst einen unbekannten
// Namen im Template zu `undefined` auf, der Klick wurde also still geschluckt:
// keine Meldung, keine Anfrage, kein roter Test.
const onBuildGutachtenPrompt = async () => {
  if (!store.selectedProjekt) return
  berichtBusy.value = true
  try {
    const res = await store.buildGutachtenPrompt(store.selectedProjekt)
    // Nur öffnen, wenn ein Prompt zurückkam: Das Modal hängt an
    // `v-if="berichtPromptText"`, ein leerer Text ließe es gar nicht erst
    // erscheinen — und der Anwender stünde wieder vor einem Knopf ohne Wirkung.
    // Den Grund (keine Fragen, Projekt fehlt) hat der Store bereits in
    // `store.error` abgelegt.
    if (res?.prompt) berichtPromptText.value = res.prompt
  } finally {
    berichtBusy.value = false
  }
}

const onBerichtAusKi = async (rawText: string) => {
  if (!rawText || !store.selectedProjekt) return
  berichtBusy.value = true
  try {
    const entwurf = await store.importGutachten(store.selectedProjekt, rawText)
    // Das Modal bleibt bei einem Fehlschlag offen — sonst wäre die eingefügte
    // Antwort verloren und der Anwender müsste sie erneut besorgen.
    if (entwurf) berichtPromptText.value = ''
  } finally {
    berichtBusy.value = false
  }
}

// ============================================================
// Phase H-A — Audit-Bericht → Privatgutachten Konversion (Wizard)
// ============================================================
const konvertOpen = ref(false)
const konvertStep = ref(1)
const konvertBusy = ref(false)
const konvertAcceptance = ref(false)
const konvertEinheitlich = ref(false)  // #705: Audit ist Teil des Gutachtens
const konvertSummary = ref<any>(null)
const konvertWarning = ref<any>(null)
const konvertGaps = ref<any[]>([])
const konvertResult = ref<any>(null)
const konvertError = ref('')
const konvertForm = reactive({
  pg_name: '',
  sv_name: '',
  auftrags_art: 'Tauglichkeitsprüfung',
  auftrags_datum: new Date().toISOString().slice(0, 10),
  auftrags_nummer: '',
  thema: '',
  honorarvereinbarung: '',
})

const openKonvertWizard = async () => {
  if (!store.selectedProjekt) return
  konvertOpen.value = true
  konvertStep.value = 1
  konvertAcceptance.value = false
  konvertEinheitlich.value = false
  konvertResult.value = null
  konvertError.value = ''
  konvertForm.pg_name = `PG-${new Date().getFullYear()}-${(store.selectedProjekt || '').slice(0, 10)}`
  konvertForm.sv_name = ''
  konvertForm.auftrags_nummer = ''
  konvertForm.thema = ''
  konvertForm.honorarvereinbarung = ''
  // Lade Summary + Warning + Gaps
  try {
    const [s, w, g] = await Promise.all([
      apiClient.get(`/gutachten/${encodeURIComponent(store.selectedProjekt)}/audit-summary`).then(r => r.data),
      apiClient.get(`/gutachten/${encodeURIComponent(store.selectedProjekt)}/vorbefassung-warning`).then(r => r.data),
      apiClient.get(`/gutachten/${encodeURIComponent(store.selectedProjekt)}/audit-gaps`).then(r => r.data),
    ])
    konvertSummary.value = s
    konvertWarning.value = w
    konvertGaps.value = (g.gaps || []).map((x: any) => ({ ...x, _selected: true }))
    await loadAutoThema()
  } catch (e: any) {
    konvertError.value = e?.response?.data?.error || 'Konnte Audit-Daten nicht laden'
  }
}

const closeKonvert = () => { konvertOpen.value = false }

// #705 — Hinweistext neu laden, wenn Auftragsverhältnis-Variante geändert wird
const reloadWarning = async () => {
  if (!store.selectedProjekt) return
  konvertAcceptance.value = false
  try {
    const r = await apiClient.get(
      `/gutachten/${encodeURIComponent(store.selectedProjekt)}/vorbefassung-warning`,
      { params: { einheitlicher_auftrag: konvertEinheitlich.value ? '1' : '0' } },
    )
    konvertWarning.value = r.data
  } catch {}
}

const loadAutoThema = async () => {
  if (!store.selectedProjekt) return
  try {
    const r = await apiClient.get(`/gutachten/${encodeURIComponent(store.selectedProjekt)}/auto-thema`, {
      params: { auftrags_art: konvertForm.auftrags_art },
    })
    konvertForm.thema = r.data?.thema || ''
  } catch {}
}

const onAuftragsArtChange = () => { loadAutoThema() }

const selectedGapCount = computed(() => konvertGaps.value.filter(g => g._selected).length)

const canAdvance = computed(() => {
  // #705: bei einheitlichem Auftrag keine Akzeptanz nötig
  if (konvertStep.value === 1) return konvertEinheitlich.value || konvertAcceptance.value
  if (konvertStep.value === 2) return !!konvertForm.pg_name && !!konvertForm.sv_name
  return true
})

const nextKonvertStep = () => {
  if (canAdvance.value) konvertStep.value++
}

const executeKonvert = async () => {
  if (!store.selectedProjekt) return
  konvertBusy.value = true
  konvertError.value = ''
  try {
    const res = await apiClient.post(
      `/gutachten/${encodeURIComponent(store.selectedProjekt)}/konvertieren-zu-pg`,
      {
        ...konvertForm,
        befangenheits_akzeptanz: konvertAcceptance.value || konvertEinheitlich.value,
        audit_teil_des_gutachtens: konvertEinheitlich.value,
      },
    )
    konvertResult.value = res.data
    // Befund-Skeletons übernehmen für ausgewählte Gaps
    const selected = konvertGaps.value.filter(g => g._selected)
    for (let i = 0; i < selected.length; i++) {
      try {
        await apiClient.post(
          `/gutachten/gerichts/${encodeURIComponent(konvertForm.pg_name)}/befund-from-gap`,
          { gap: selected[i], nr: `B-${i + 1}` },
        )
      } catch {}
    }
  } catch (e: any) {
    konvertError.value = e?.response?.data?.error || 'Konversion fehlgeschlagen'
  } finally {
    konvertBusy.value = false
  }
}

const router = useRouter()

const goToPg = () => {
  // #746: Navigation über den Router statt window.location.hash (SPA-konform,
  // History-/Guard-tauglich, kein hartes Hash-Setzen).
  closeKonvert()
  if (konvertResult.value?.pg_name) {
    router.push({ path: '/gutachten/gerichts', query: { projekt: konvertResult.value.pg_name } })
  }
}

// Auf Projekt-Wechsel reagieren
const onProjektChange = async (n: string | null) => {
  if (!n) return
  await Promise.all([
    store.fetchFragen(n),
    store.fetchDraft(n),
    ladeDashboard(),
  ])
  // editForm vorbefüllen
  const p = store.selectedProjektObj
  if (p) {
    editForm.frameworks = [...(p.frameworks || [])]
    editForm.pruefungsfokus = p.pruefungsfokus || ''
  }
}

watch(() => store.selectedProjekt, onProjektChange, { immediate: false })

onMounted(async () => {
  await store.fetchSectionsCount()
  await store.fetchFrameworkKatalog()
  await store.fetchProjekte()
  if (!store.selectedProjekt && store.projekte.length > 0) {
    store.selectedProjekt = store.projekte[0].name
  }
  if (store.selectedProjekt) await onProjektChange(store.selectedProjekt)
})
</script>

<style scoped>
.compliance-audit-view { max-width: 1500px; }

.header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; font-size: 22px; }
.header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: 13px; }

.alert-error {
  background: #ffebee; color: #c62828; padding: 10px; border-radius: 4px;
  margin-bottom: 12px; border: 1px solid #ef5350; cursor: pointer;
}

.empty-state { background: var(--color-surface); padding: 32px; border-radius: 8px; border: 1px solid var(--color-border); text-align: center; }
.empty-state h3 { margin: 0 0 12px; }
.empty-state p { color: var(--color-text-secondary); margin-bottom: 20px; }
.proj-list { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 24px; }
.proj-tile {
  background: var(--color-background); border: 1px solid var(--color-border);
  padding: 12px 20px; border-radius: 6px; cursor: pointer;
  display: flex; flex-direction: column; gap: 4px; min-width: 220px;
}
.proj-tile:hover { background: var(--color-border); border-color: var(--color-primary); }
.proj-tile strong { font-size: 15px; }
.proj-fw { font-size: 11px; color: var(--color-text-secondary); }

.proj-selector { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; }
.proj-selector select { flex: 1; padding: 8px; border: 1px solid var(--color-border); border-radius: 4px; }

.form-card { background: var(--color-surface); padding: 24px; border-radius: 8px; border: 1px solid var(--color-border); max-width: 700px; }
.form-card h3 { margin: 0 0 16px; }
.form-row { margin-bottom: 12px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row select, .form-row textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: 4px;
  font-size: 13px; background: var(--color-surface); color: var(--color-text-primary);
}
.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.fw-checks { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
.check-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; cursor: pointer; }

/* Framework-Auswahl: Code als Pille, Beschreibung darf umbrechen, Status rechts.
   Vorher eine reine flex-Row mit langem Label + langem Zusatztext — das lief ueber. */
.fw-checks { display: flex; flex-direction: column; gap: 2px; }
.fw-row { display: grid; grid-template-columns: auto 1fr auto; align-items: baseline;
          gap: 10px; padding: 6px 8px; border-radius: 6px; cursor: pointer; }
.fw-row:hover { background: var(--color-bg-subtle, #f5f7f8); }
.fw-text { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; min-width: 0; }
.fw-code { font-weight: 600; font-family: Consolas, monospace; font-size: 13px; }
.fw-label { color: var(--color-text-secondary); font-size: 12px; }
.fw-status { font-size: 11px; border-radius: 10px; padding: 1px 8px; white-space: nowrap; }
.fw-status.da { background: #e8f5e9; color: #2e7d32; }
.fw-status.leer { background: #fff3e0; color: #ef6c00; }

/* Framework-Umschalter im Fragen-Wizard */
.fw-switch { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.fw-chip { border: 1px solid var(--color-border); background: #fff; border-radius: 12px;
           padding: 2px 10px; font-size: 12px; cursor: pointer; }
.fw-chip.active { background: #1565c0; color: #fff; border-color: #0d47a1; }
.muted { color: var(--color-text-secondary); font-size: 12px; }

.tabs { display: flex; gap: 0; border-bottom: 2px solid var(--color-border); margin-bottom: 16px; }
.tab-btn {
  background: none; border: none; padding: 10px 20px; cursor: pointer;
  font-size: 14px; color: var(--color-text-secondary);
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  display: inline-flex; gap: 6px; align-items: center;
}
.tab-btn:hover { color: var(--color-primary); }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }
.badge {
  background: var(--color-primary); color: #fff; padding: 1px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 600;
}

.tab-content { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 20px; }

.stat-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px; margin-bottom: 16px;
}
.stat-card {
  background: var(--color-background); padding: 16px; border-radius: 6px; text-align: center;
  border: 1px solid var(--color-border);
}
.stat-num { font-size: 32px; font-weight: 700; color: var(--color-primary); }
.stat-lbl { font-size: 12px; color: var(--color-text-secondary); }

.info-card {
  background: var(--color-background); padding: 14px 18px; border-radius: 6px;
  margin-bottom: 12px;
}
.info-card h4 { margin: 0 0 8px; font-size: 14px; }
.info-card ol { margin: 0; padding-left: 20px; line-height: 1.6; }
.info-card p { margin: 0; }

.fragen-toolbar {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border);
}
.search-input { padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 4px; flex: 1; min-width: 180px; }

.fragen-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.fragen-table th { text-align: left; padding: 8px; background: var(--color-background); font-weight: 600; border-bottom: 1px solid var(--color-border); }
.fragen-table td { padding: 8px; border-bottom: 1px solid var(--color-border); vertical-align: top; }
.fragen-table tr:hover { background: var(--color-background); }
.fw-tag { font-family: monospace; font-size: 11px; padding: 2px 6px; background: var(--color-background); border-radius: 3px; }
.ref { font-size: 11px; }
/* #1728: Ein langes Thema (haeufig aus eingelesenen Frameworks, teils ohne
   Leerzeichen) sprengte die Spalte trotz max-width und schob die ganze Tabelle
   in die Breite. 'anywhere' erzwingt den Umbruch, der Clamp begrenzt die Hoehe
   auf 3 Zeilen — der volle Text steht im title-Tooltip und im Bearbeiten-Dialog. */
.thema-cell { max-width: 180px; }
.thema-text {
  display: -webkit-box; -webkit-box-orient: vertical;
  -webkit-line-clamp: 3; line-clamp: 3;
  overflow: hidden; overflow-wrap: anywhere; hyphens: auto;
}
.frage-cell { max-width: 600px; }
.antwort-text { margin: 6px 0 0; padding: 6px 10px; background: var(--color-background); border-left: 3px solid var(--color-success); border-radius: 4px; font-size: 12px; }

.bw-pill { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.bw-pill.ok { background: #e8f5e9; color: #2e7d32; }
.bw-pill.partial { background: #fff3e0; color: #e65100; }
.bw-pill.bad { background: #ffebee; color: #c62828; }
.bw-pill.unknown { background: var(--color-background); color: var(--color-text-secondary); }

.btn-icon { background: none; border: none; cursor: pointer; padding: 4px 6px; font-size: 14px; }
.btn-icon:hover { background: var(--color-background); border-radius: 4px; }

.empty { padding: 32px; text-align: center; color: var(--color-text-secondary); }

.entwurf-box { border: 1px solid var(--color-border); border-radius: 8px; padding: 14px 16px; margin-bottom: 20px; }
.entwurf-kopf { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.entwurf-kopf h3 { margin: 0 0 4px; }
.entwurf-stand { background: #e3f2fd; border-radius: 6px; padding: 8px 12px; }
.ki-hinweis { font-size: 12px; color: var(--color-text-secondary); font-style: italic; }
.prio { border-radius: 10px; padding: 1px 8px; font-size: 11px; margin-left: 6px; }
.prio-hoch { background: #ffebee; color: #c62828; }
.prio-mittel { background: #fff8e1; color: #f57f17; }
.prio-niedrig { background: #e8f5e9; color: #2e7d32; }
.bericht-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.bericht-preview { background: var(--color-background); padding: 16px; border-radius: 6px; }
.bericht-preview h3 { margin: 0 0 12px; }
.bericht-preview details { margin-bottom: 8px; padding: 8px 12px; background: var(--color-surface); border-radius: 4px; }
.bericht-preview summary { cursor: pointer; font-weight: 600; }
.bericht-preview p, .bericht-preview ul, .bericht-preview ol { margin: 8px 0 0; }

/* Modals */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content {
  background: var(--color-surface); border-radius: 8px; max-width: 600px; width: 90%;
  max-height: 90vh; overflow: hidden; display: flex; flex-direction: column;
}
.modal-content.modal-wide { max-width: 1000px; }
.modal-header {
  background: var(--color-primary); color: #fff;
  padding: 14px 20px; display: flex; justify-content: space-between; align-items: center;
}
.modal-header h3 { margin: 0; font-size: 16px; }
.btn-close { background: none; border: none; color: #fff; font-size: 22px; cursor: pointer; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer {
  padding: 12px 20px; border-top: 1px solid var(--color-border);
  display: flex; gap: 8px; justify-content: flex-end;
}
.prompt-textarea {
  width: 100%; font-family: monospace; font-size: 12px; padding: 10px;
  border: 1px solid var(--color-border); border-radius: 4px;
  background: var(--color-background); color: var(--color-text-primary);
}
.prompts-result { margin-top: 16px; }
.prompts-result details { margin-bottom: 8px; background: var(--color-background); padding: 8px 12px; border-radius: 4px; }
.btn-mini {
  background: var(--color-background); border: 1px solid var(--color-border);
  padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px;
  margin-left: 8px;
}
.hint { font-size: 12px; color: var(--color-text-secondary); }
.hint.ok { color: var(--color-success); }

.btn-primary { background: var(--color-primary); color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 500; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-dark); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.hint.warn { color: #ef6c00; margin-right: auto; align-self: center; }
.muted.leer { color: #ef6c00; }
.btn-secondary { background: var(--color-background); color: var(--color-primary); border: 1px solid var(--color-border); padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary:hover { background: var(--color-border); }
.btn-danger { background: #ffebee; color: #c62828; border: 1px solid #ef5350; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-danger:hover { background: #ffcdd2; }
.btn-success { background: #2e7d32; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: 500; }
.btn-success:hover:not(:disabled) { background: #1b5e20; }

.gericht-link { display: inline-block; margin-top: 8px; padding: 6px 14px; background: #efebe9; color: #5d4037; border-radius: 4px; text-decoration: none; font-weight: 600; }
.gericht-link:hover { background: #d7ccc8; }
/* #1783: Entwurf überarbeiten + lesbare Handlungsempfehlungen */
.e-kopf { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.e-kopf .entwurf-stand { flex: 1; margin: 0; }
.e-aktionen { display: flex; gap: 8px; }
.empfehlungen { margin: 8px 0 0; padding-left: 20px; }
.empfehlungen li { margin-bottom: 10px; }
.e-zeile { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; }
.e-titel { flex: 1 1 18rem; }
.e-grund { font-size: 13px; color: var(--color-text-secondary); margin-top: 2px; }
.e-feld { display: block; margin: 10px 0; font-size: 12px; font-weight: 600;
  color: var(--color-text-secondary); }
.e-feld input, .e-feld textarea { display: block; width: 100%; box-sizing: border-box;
  margin-top: 4px; font: inherit; font-weight: 400; font-size: 13px; padding: 6px 8px;
  border: 1px solid var(--color-border); border-radius: 6px; resize: vertical; }
.e-klein { font-weight: 400; color: var(--color-text-secondary); }
.e-edit { border: 1px solid var(--color-border); border-radius: 6px; padding: 8px;
  margin-bottom: 8px; }
.e-edit-kopf { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.e-edit-kopf input { flex: 1 1 16rem; padding: 5px 8px; border: 1px solid var(--color-border);
  border-radius: 6px; font: inherit; }
.e-edit-kopf select { padding: 5px; border: 1px solid var(--color-border); border-radius: 6px; }
.e-edit textarea { width: 100%; box-sizing: border-box; margin-top: 6px; font: inherit;
  font-size: 13px; padding: 6px; border: 1px solid var(--color-border); border-radius: 6px;
  resize: vertical; }
.empfehlungen-edit { margin: 10px 0; }
</style>
