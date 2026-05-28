<template>
  <div class="pflicht-doku">
    <div class="info-banner">
      <h3>📋 DSGVO-Pflicht-Doku — Start hier</h3>
      <p>Die DSGVO verlangt von Verantwortlichen einen festen Satz an dokumentierten Nachweisen.
        <strong>Diese Seite ist der erste Schritt</strong>.</p>
      <div class="workflow">
        <strong>Reihenfolge:</strong>
        <ol>
          <li><strong>D1 VVT</strong> (Art. 30) — Verarbeitungstätigkeiten erfassen</li>
          <li><strong>D2 TOM</strong> (Art. 32) — Schutzmaßnahmen dokumentieren</li>
          <li><strong>D3 DPIA</strong> (Art. 35) — Folgenabschätzung bei hohem Risiko</li>
          <li><strong>D4 AVV</strong> (Art. 28) — Auftragsverarbeiter tracken</li>
          <li><strong>D5 Datenpannen</strong> (Art. 33-34) — Register mit 72h-Meldung</li>
          <li>Wizards <strong>D6-D9</strong>: Rechtsgrundlage / Branchen-Template / Datenpannen-Meldung / Betroffenenrechte</li>
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
      <summary><strong>D1 — VVT (Art. 30)</strong> ({{ store.vvt.length }} Verarbeitungen)</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> Verzeichnis aller Verarbeitungstätigkeiten. Pro Verarbeitung:
          Zweck, Rechtsgrundlage (Art. 6), Betroffene, Datenkategorien, Empfänger, Drittland, Löschfrist.
          Wizard <strong>D6</strong> bestimmt automatisch die Rechtsgrundlage.
        </div>
        <div class="quick-actions">
          <button class="btn-primary" @click="openVvtWizard()">🪄 Neuen VVT-Eintrag erstellen</button>
          <small class="hint">Geführter Anlege-Assistent mit Erklärungen und großen Textfeldern.</small>
        </div>
        <table v-if="store.vvt.length">
          <thead><tr><th>ID</th><th>Name</th><th>Zweck</th><th>Rechtsgrundlage</th><th></th></tr></thead>
          <tbody>
            <tr v-for="v in store.vvt" :key="v.id">
              <td><code>{{ v.vvt_id }}</code></td>
              <td>{{ v.name }}</td>
              <td>{{ truncate(v.zweck, 80) }}</td>
              <td>{{ v.rechtsgrundlage }}</td>
              <td>
                <button class="btn-link" @click="openVvtWizard(v)" title="Bearbeiten">✏️</button>
                <button class="btn-link" @click="openRgWizard(v)" title="Rechtsgrundlage-Wizard">🤖</button>
                <button class="btn-link" @click="store.deleteVvt(v.id)" title="Löschen">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="hint" style="margin-top: 12px;">— Noch keine VVT-Einträge —</p>
      </div>
    </details>

    <!-- D2 TOM -->
    <details class="section">
      <summary><strong>D2 — TOM (Art. 32)</strong> ({{ store.tom.length }} Maßnahmen)</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> Technische und Organisatorische Maßnahmen pro Kategorie
          (Zutritts-/Zugangs-/Zugriffskontrolle, Pseudonymisierung, Verschlüsselung, Verfügbarkeit, …).
          Branchen-Templates legen Defaults an.
        </div>
        <div class="form-grid">
          <select v-model="tomForm.kategorie">
            <option value="zutrittskontrolle">Zutrittskontrolle</option>
            <option value="zugangskontrolle">Zugangskontrolle</option>
            <option value="zugriffskontrolle">Zugriffskontrolle</option>
            <option value="weitergabekontrolle">Weitergabekontrolle</option>
            <option value="eingabekontrolle">Eingabekontrolle</option>
            <option value="auftragskontrolle">Auftragskontrolle</option>
            <option value="verfuegbarkeit">Verfügbarkeit</option>
            <option value="datentrennung">Datentrennung</option>
            <option value="pseudonymisierung">Pseudonymisierung</option>
            <option value="verschluesselung">Verschlüsselung</option>
            <option value="integritaet">Integrität</option>
            <option value="loeschkonzept">Löschkonzept</option>
          </select>
          <input v-model="tomForm.massnahme" placeholder="Maßnahme" />
          <select v-model="tomForm.umsetzungsstatus">
            <option value="geplant">Geplant</option>
            <option value="umgesetzt">Umgesetzt</option>
            <option value="review">Review fällig</option>
          </select>
          <input v-model="tomForm.verantwortlich" placeholder="Verantwortlich" />
          <button class="btn-primary" @click="addTom">+ Hinzufügen</button>
        </div>
        <table>
          <thead><tr><th>Kategorie</th><th>Maßnahme</th><th>Status</th><th>Verantwortlich</th><th></th></tr></thead>
          <tbody>
            <tr v-for="t in store.tom" :key="t.id">
              <td>{{ t.kategorie }}</td>
              <td>{{ t.massnahme }}</td>
              <td><span :class="`status-pill st-${t.umsetzungsstatus}`">{{ t.umsetzungsstatus }}</span></td>
              <td>{{ t.verantwortlich }}</td>
              <td><button class="btn-link" @click="store.deleteTom(t.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- D3 DPIA -->
    <details class="section">
      <summary><strong>D3 — DPIA (Art. 35)</strong> ({{ store.dpia.length }})</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> Datenschutz-Folgenabschätzung bei Verarbeitungen mit hohem Risiko
          (systematische Überwachung, besondere Datenkategorien, Profiling, …).
          Bei hohem Restrisiko → Konsultation der Aufsichtsbehörde (Art. 36).
        </div>
        <div class="form-grid">
          <input v-model="dpiaForm.dpia_id" placeholder="DPIA-ID" />
          <input v-model="dpiaForm.bezug_vvt" placeholder="Bezug VVT-ID (optional)" />
          <input v-model="dpiaForm.titel" placeholder="Titel" />
          <input v-model="dpiaForm.notwendigkeit_grund" placeholder="Notwendigkeit (z.B. systematische Überwachung)" />
          <select v-model="dpiaForm.restrisiko">
            <option value="niedrig">Niedrig</option>
            <option value="mittel">Mittel</option>
            <option value="hoch">Hoch</option>
          </select>
          <label><input type="checkbox" v-model="dpiaForm.konsultation_aufsicht" /> Konsultation Aufsicht (Art. 36)</label>
          <button class="btn-primary" @click="addDpia">+ Hinzufügen</button>
        </div>
        <table>
          <thead><tr><th>ID</th><th>Titel</th><th>Restrisiko</th><th>Status</th><th></th></tr></thead>
          <tbody>
            <tr v-for="d in store.dpia" :key="d.id">
              <td><code>{{ d.dpia_id }}</code></td>
              <td>{{ d.titel }}</td>
              <td><span :class="`risk-pill rsk-${d.restrisiko}`">{{ d.restrisiko }}</span></td>
              <td>{{ d.status }}</td>
              <td><button class="btn-link" @click="store.deleteDpia(d.id)">🗑️</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <!-- D4 AVV -->
    <details class="section">
      <summary><strong>D4 — AVV-Tracker (Art. 28)</strong> ({{ store.avv.length }})</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> Auftragsverarbeitungs-Vertrag pro Dienstleister.
          Wichtig: Sub-Processor-Kette + Drittland-Garantien (SCC/BCR/Adäquanz).
        </div>
        <div class="form-grid">
          <input v-model="avvForm.auftragsverarbeiter" placeholder="Auftragsverarbeiter" />
          <input v-model="avvForm.leistung" placeholder="Leistung" />
          <label><input type="checkbox" v-model="avvForm.avv_vorhanden" /> AVV unterschrieben</label>
          <input v-model="avvForm.avv_url" placeholder="AVV-URL" />
          <input v-model="avvForm.avv_datum" type="date" />
          <label><input type="checkbox" v-model="avvForm.drittland" /> Drittland</label>
          <select v-model="avvForm.drittland_garantie">
            <option value="">— Garantie wählen —</option>
            <option value="adaequanz">Angemessenheitsbeschluss</option>
            <option value="SCC">Standardvertragsklauseln (SCC)</option>
            <option value="BCR">Binding Corporate Rules</option>
          </select>
          <button class="btn-primary" @click="addAvv">+ Hinzufügen</button>
        </div>
        <table>
          <thead><tr><th>Vendor</th><th>Leistung</th><th>AVV</th><th>Drittland</th><th></th></tr></thead>
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
      <summary><strong>D5 — Datenpannen (Art. 33-34)</strong> ({{ store.datenpannen.length }})</summary>
      <div class="section-body">
        <div class="help-box">
          <strong>Worum geht's?</strong> Register aller Datenpannen. Pflicht-Meldung an Aufsichtsbehörde
          innerhalb 72h (Art. 33) wenn Risiko, Information der Betroffenen bei hohem Risiko (Art. 34).
          Wizard <strong>D8</strong> generiert die Meldungstexte.
        </div>
        <div class="form-grid">
          <input v-model="panneForm.panne_id" placeholder="Panne-ID" />
          <input v-model="panneForm.titel" placeholder="Titel" />
          <input v-model="panneForm.festgestellt_am" type="date" />
          <select v-model="panneForm.art">
            <option value="vertraulichkeit">Vertraulichkeit</option>
            <option value="integritaet">Integrität</option>
            <option value="verfuegbarkeit">Verfügbarkeit</option>
          </select>
          <input v-model.number="panneForm.betroffene_anzahl" type="number" placeholder="Anzahl Betroffene" />
          <select v-model="panneForm.risikoeinschaetzung">
            <option value="gering">Gering</option>
            <option value="mittel">Mittel</option>
            <option value="hoch">Hoch</option>
          </select>
          <label><input type="checkbox" v-model="panneForm.meldung_aufsicht_pflicht" /> 72h-Meldung an Aufsicht</label>
          <button class="btn-primary" @click="addPanne">+ Hinzufügen</button>
        </div>
        <table>
          <thead><tr><th>ID</th><th>Titel</th><th>Festgestellt</th><th>Risiko</th><th>Status</th><th></th></tr></thead>
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

    <!-- Phase B: KI-Wizards -->
    <details class="section wizards" open>
      <summary><strong>🤖 KI-Assistenten</strong> — Rechtsgrundlage / Branchen / Datenpannen / Betroffenenrechte</summary>
      <div class="section-body">
        <div class="wizard-card">
          <h4>D7 — Branchen-Template anwenden</h4>
          <p>Legt TOM-Defaults für die Branche automatisch an (E-Commerce / B2B-SaaS / Healthcare / HR).</p>
          <div class="row">
            <select v-model="selectedBranche">
              <option value="">— Branche wählen —</option>
              <option v-for="t in store.branchenTemplates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
            <button class="btn-primary" :disabled="!selectedBranche" @click="applyBranche">⚡ Anwenden</button>
          </div>
          <p v-if="brancheApplied" class="hint">✅ {{ brancheAppliedMsg }}</p>
        </div>

        <div class="wizard-card">
          <h4>D9 — Betroffenenrechte-Antwort</h4>
          <p>Generiert Eingangsbestätigung + Antwort-Template für Auskunfts-/Löschungs-/Portabilitäts-Anträge (Art. 15/17/20).</p>
          <div class="form-grid">
            <select v-model="brAnfrage.antragsart">
              <option value="auskunft">Auskunft (Art. 15)</option>
              <option value="berichtigung">Berichtigung (Art. 16)</option>
              <option value="loeschung">Löschung (Art. 17)</option>
              <option value="einschraenkung">Einschränkung (Art. 18)</option>
              <option value="portabilitaet">Portabilität (Art. 20)</option>
              <option value="widerspruch">Widerspruch (Art. 21)</option>
            </select>
            <input v-model="brAnfrage.anfrage_datum" type="date" />
          </div>
          <button class="btn-primary" @click="openBrWizard">📝 Prompt generieren</button>
        </div>
      </div>
    </details>

    <!-- VVT-Anlege-Wizard (#587) -->
    <div v-if="vvtWizard.open" class="wizard-modal-overlay" @click.self="closeVvtWizard">
      <div class="wizard-modal vvt-modal">
        <h3>{{ vvtWizard.editing ? '✏️ VVT-Eintrag bearbeiten' : '🪄 Neuen VVT-Eintrag erstellen' }}</h3>
        <p class="hint">Verzeichnis nach Art. 30 DSGVO — Pflicht für alle Verantwortlichen (auch KMU mit > 250 MA oder besondere Datenkategorien).</p>

        <fieldset>
          <legend>📌 Grunddaten</legend>
          <div class="vvt-grid">
            <label>VVT-ID <span class="req">*</span>
              <small>Eindeutige Kennzeichnung, z.B. <code>VVT-001</code>. Wird in DPIA + AVV referenziert.</small>
              <input v-model="vvtWizard.data.vvt_id" placeholder="VVT-001" />
            </label>
            <label>Name der Verarbeitung <span class="req">*</span>
              <small>Kurze, sprechende Bezeichnung (z.B. „Kundenstammdaten-Verwaltung im CRM").</small>
              <input v-model="vvtWizard.data.name" placeholder="z.B. CRM-Kundenstammdaten" />
            </label>
          </div>
          <label class="full">Zweck der Verarbeitung <span class="req">*</span>
            <small>Warum werden diese Daten verarbeitet? Konkret beschreiben. Mehrere Zwecke einzeln aufzählen.</small>
            <textarea v-model="vvtWizard.data.zweck" rows="3"
              placeholder="z.B. Vertragsabwicklung mit Kunden, Rechnungserstellung, Kundenpflege per E-Mail." />
          </label>
        </fieldset>

        <fieldset>
          <legend>⚖️ Rechtsgrundlage (Art. 6 DSGVO)</legend>
          <small class="hint">Tipp: Wizard <strong>D6</strong> kann die passende Rechtsgrundlage automatisch bestimmen — speichere zuerst, dann „🤖 RG-Wizard" in der Tabelle.</small>
          <div class="vvt-grid">
            <label>Rechtsgrundlage
              <small>Welcher Buchstabe von Art. 6 (1)? Bei besonderen Datenkategorien zusätzlich Art. 9 (2).</small>
              <select v-model="vvtWizard.data.rechtsgrundlage">
                <option value="">— Wählen —</option>
                <option value="Art. 6(1)(a)">Art. 6(1)(a) — Einwilligung</option>
                <option value="Art. 6(1)(b)">Art. 6(1)(b) — Vertrag</option>
                <option value="Art. 6(1)(c)">Art. 6(1)(c) — Rechtliche Verpflichtung</option>
                <option value="Art. 6(1)(d)">Art. 6(1)(d) — Lebenswichtige Interessen</option>
                <option value="Art. 6(1)(e)">Art. 6(1)(e) — Öffentliches Interesse</option>
                <option value="Art. 6(1)(f)">Art. 6(1)(f) — Berechtigte Interessen</option>
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>👥 Betroffene & Datenkategorien</legend>
          <label class="full">Kategorien betroffener Personen
            <small>Wer ist betroffen? z.B. Kunden, Mitarbeiter, Interessenten, Bewerber, Lieferanten.</small>
            <textarea v-model="vvtWizard.data.betroffene_kategorien" rows="2"
              placeholder="Kunden (B2B + B2C), Interessenten, ehemalige Kunden für 6 Monate" />
          </label>
          <label class="full">Kategorien personenbezogener Daten
            <small>Welche Daten? Name/Adresse/Kontakt/Vertrag/Zahlungsdaten/Gesundheit/etc. — besondere Kategorien (Art. 9) gesondert kennzeichnen.</small>
            <textarea v-model="vvtWizard.data.datenkategorien" rows="2"
              placeholder="Name, Anschrift, E-Mail, Telefonnummer, Vertragsdaten, Zahlungsinformationen (verschlüsselt)" />
          </label>
        </fieldset>

        <fieldset>
          <legend>📤 Empfänger & Drittland</legend>
          <label class="full">Empfänger (intern + extern)
            <small>Wer bekommt die Daten? Interne Abteilungen + externe Stellen (Banken, Steuerberater, Auftragsverarbeiter).</small>
            <textarea v-model="vvtWizard.data.empfaenger" rows="2"
              placeholder="Vertrieb, Buchhaltung, Steuerberater XY GmbH, Payment-Provider Stripe (AVV vorhanden)" />
          </label>
          <label class="full">Drittlandtransfer
            <small>Werden Daten in Nicht-EU-Länder übermittelt? Wenn ja: welches Land + Garantie (Adäquanzbeschluss/SCC/BCR).</small>
            <textarea v-model="vvtWizard.data.drittland" rows="2"
              placeholder="z.B. USA via SCC (Stripe, Cloudflare) — siehe D4 AVV-Tracker" />
          </label>
        </fieldset>

        <fieldset>
          <legend>🗓️ Aufbewahrung & TOM</legend>
          <div class="vvt-grid">
            <label>Löschfrist <span class="req">*</span>
              <small>Wann werden Daten gelöscht? Frist gem. § 257 HGB / § 147 AO oder Zweckwegfall.</small>
              <input v-model="vvtWizard.data.loeschfrist" placeholder="z.B. 10 Jahre nach Vertragsende (§ 257 HGB)" />
            </label>
            <label>TOM-Referenz
              <small>Welche technisch-organisatorischen Maßnahmen schützen diese Verarbeitung? Siehe D2.</small>
              <input v-model="vvtWizard.data.tom_referenz" placeholder="z.B. TOM-Set 'Standard-CRM-Schutz'" />
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>👤 Verantwortlichkeit & Notizen</legend>
          <label class="full">Verantwortliche Person/Rolle
            <small>Wer ist intern verantwortlich? Name oder Rolle (z.B. „Leitung Vertrieb").</small>
            <input v-model="vvtWizard.data.verantwortlich" placeholder="z.B. Maria Müller (Datenschutzkoordinatorin)" />
          </label>
          <label class="full">Notizen
            <small>Sonstige relevante Informationen, Sonderfälle, Abhängigkeiten.</small>
            <textarea v-model="vvtWizard.data.notizen" rows="3"
              placeholder="z.B. Verzicht auf Einwilligungspflicht wegen Vertragserfüllung. DPIA durchgeführt (DPIA-001)." />
          </label>
        </fieldset>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeVvtWizard">Abbrechen</button>
          <button class="btn-primary" :disabled="!vvtWizardValid" @click="saveVvtWizard">
            {{ vvtWizard.editing ? '💾 Aktualisieren' : '+ Anlegen' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Wizard-Modal -->
    <div v-if="wizardModal.open" class="wizard-modal-overlay" @click.self="closeWizard">
      <div class="wizard-modal">
        <h3>🤖 {{ wizardModal.title }}</h3>
        <p class="hint">Prompt → ChatGPT → JSON-Antwort hier einfügen → Parsen+Anwenden</p>
        <label>Prompt</label>
        <textarea readonly :value="wizardModal.prompt" rows="8" class="mono"></textarea>
        <button class="btn-link" @click="copyPrompt">📋 Kopieren</button>
        <label>ChatGPT-Antwort (JSON)</label>
        <textarea v-model="wizardModal.response" rows="6" class="mono"></textarea>
        <div v-if="wizardModal.parsed" class="parsed-result">
          <strong v-if="wizardModal.parsed.applied" style="color: #2e7d32;">✓ Angewendet</strong>
          <strong v-else style="color: #e65100;">Geparsed</strong>
          <pre>{{ JSON.stringify(wizardModal.parsed, null, 2) }}</pre>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="closeWizard">Schließen</button>
          <button class="btn-primary" :disabled="!wizardModal.response" @click="parseAndApply">Parsen + Anwenden</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'

const store = useDsgvoStore()

const vvtForm = ref<any>({})
const tomForm = ref<any>({ kategorie: 'zugangskontrolle', umsetzungsstatus: 'geplant' })
const dpiaForm = ref<any>({ restrisiko: 'niedrig' })
const avvForm = ref<any>({})
const panneForm = ref<any>({ art: 'vertraulichkeit', risikoeinschaetzung: 'gering' })

const status = computed(() => store.pflichtDokuStatus)
const statusItems = computed(() => {
  const s = status.value
  if (!s) return []
  return [
    { key: 'vvt', label: 'VVT', ok: s.vvt?.ok, detail: `${s.vvt?.count || 0}` },
    { key: 'tom', label: 'TOM', ok: s.tom?.ok, detail: `${s.tom?.count || 0} (${s.tom?.open || 0} offen)` },
    { key: 'dpia', label: 'DPIA', ok: s.dpia?.ok, detail: `${s.dpia?.count || 0}` },
    { key: 'avv', label: 'AVV', ok: s.avv?.ok, detail: `${s.avv?.count || 0}` },
    { key: 'pannen', label: 'Datenpannen', ok: true, detail: `${s.datenpannen?.count || 0}` },
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
})
watch(() => store.selectedProjekt, reloadAll)

const truncate = (s: string, n: number) => (s || '').length > n ? `${(s || '').slice(0, n)}…` : (s || '')

// #587 VVT-Wizard
const vvtWizardEmpty = () => ({
  vvt_id: '', name: '', zweck: '', rechtsgrundlage: '', betroffene_kategorien: '',
  datenkategorien: '', empfaenger: '', drittland: '', loeschfrist: '',
  tom_referenz: '', verantwortlich: '', notizen: '',
})
const vvtWizard = ref<any>({ open: false, editing: false, data: vvtWizardEmpty() })
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
const addTom = async () => { if (await store.saveTom(tomForm.value)) { tomForm.value = { kategorie: 'zugangskontrolle', umsetzungsstatus: 'geplant' }; await store.fetchPflichtDokuStatus() } }
const addDpia = async () => { if (await store.saveDpia(dpiaForm.value)) { dpiaForm.value = { restrisiko: 'niedrig' }; await store.fetchPflichtDokuStatus() } }
const addAvv = async () => { if (await store.saveAvv(avvForm.value)) { avvForm.value = {}; await store.fetchPflichtDokuStatus() } }
const addPanne = async () => { if (await store.savePanne(panneForm.value)) { panneForm.value = { art: 'vertraulichkeit', risikoeinschaetzung: 'gering' }; await store.fetchPflichtDokuStatus() } }

// Wizards
const selectedBranche = ref('')
const brancheApplied = ref(false)
const brancheAppliedMsg = ref('')
const brAnfrage = ref<any>({ antragsart: 'auskunft', anfrage_datum: '', identitaet_verifiziert: 'ja' })
const wizardModal = ref<any>({ open: false, kind: '', title: '', prompt: '', response: '', parsed: null, extra: {} })

const applyBranche = async () => {
  if (!selectedBranche.value) return
  const res = await store.applyBranchenTemplate(selectedBranche.value)
  if (res) {
    brancheApplied.value = true
    brancheAppliedMsg.value = `Template "${res.template?.name}" angewendet — ${res.tom_added || 0} TOM-Defaults hinzugefügt.`
    await reloadAll()
    setTimeout(() => { brancheApplied.value = false }, 8000)
  }
}

const WIZARD_TITLES: Record<string, string> = {
  'rechtsgrundlage': 'D6 Rechtsgrundlagen-Klassifikator',
  'datenpanne-meldung': 'D8 Datenpannen-Meldung (72h)',
  'betroffenenrechte': 'D9 Betroffenenrechte-Workflow',
}

const openRgWizard = async (vvtItem: any) => {
  const prompt = await store.getWizardPrompt('rechtsgrundlage', vvtItem)
  wizardModal.value = {
    open: true, kind: 'rechtsgrundlage', title: WIZARD_TITLES['rechtsgrundlage'],
    prompt, response: '', parsed: null, extra: { vvt_id: vvtItem.id },
  }
}

const openPanneMeldungWizard = async (p: any) => {
  const prompt = await store.getWizardPrompt('datenpanne-meldung', p)
  wizardModal.value = {
    open: true, kind: 'datenpanne-meldung', title: WIZARD_TITLES['datenpanne-meldung'],
    prompt, response: '', parsed: null, extra: { panne_id_db: p.id },
  }
}

const openBrWizard = async () => {
  const prompt = await store.getWizardPrompt('betroffenenrechte', brAnfrage.value)
  wizardModal.value = {
    open: true, kind: 'betroffenenrechte', title: WIZARD_TITLES['betroffenenrechte'],
    prompt, response: '', parsed: null, extra: {},
  }
}

const closeWizard = () => { wizardModal.value = { open: false, kind: '', title: '', prompt: '', response: '', parsed: null, extra: {} } }
const copyPrompt = () => navigator.clipboard?.writeText(wizardModal.value.prompt)

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
</style>
