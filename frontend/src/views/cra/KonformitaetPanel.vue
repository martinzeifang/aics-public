<template>
  <div class="konf-panel">
    <div class="panel-header">
      <h3>✅ Art. 32 / Annex VIII — Konformitätsbewertung & DoC/CE</h3>
      <p class="sub">Bewertungsweg (Modul A | B+C | H | EUCC) · NB-Kennnummer ·
        EU-Konformitätserklärung · CE-Kennzeichnung</p>
    </div>

    <FehlerHinweis :text="store.error" @close="store.error = ''" />

    <div class="form-card">
      <div class="form-row">
        <label>Bewertungsweg</label>
        <select v-model="form.bewertungsweg">
          <option v-for="w in store.wege" :key="w" :value="w">{{ wegLabel(w) }}</option>
        </select>
      </div>
      <div class="form-row">
        <label>Nachweis-Checkliste (Modul {{ form.bewertungsweg }})</label>
        <div class="checkliste">
          <label v-for="n in sollNachweise" :key="n" class="check-item">
            <input type="checkbox" v-model="form.checkliste[n]" /> {{ nachweisLabel(n) }}
          </label>
        </div>
      </div>
      <div class="form-row">
        <label>Notified-Body-Kennnummer</label>
        <input v-model="form.nb_kennnummer" placeholder="z.B. 0123" />
      </div>
      <div class="form-row" v-if="form.bewertungsweg === 'EUCC'">
        <label>EUCC-Level</label>
        <input v-model="form.eucc_level" placeholder="z.B. EAL4+" />
      </div>
      <div class="form-row">
        <label>CE-Status</label>
        <select v-model="form.ce_status">
          <option v-for="s in store.ceStatus" :key="s" :value="s">{{ ceLabel(s) }}</option>
        </select>
      </div>
      <!-- #1805: Der Haken trägt Freigabe, DoC und CE — und er gilt für das
           PRODUKT, nicht je Release. Ohne diesen Satz suchte der Anwender ihn
           im Release-Vorgang, wo es ihn nie gab. -->
      <div class="form-row">
        <label class="check-item">
          <input type="checkbox" v-model="form.bewertung_abgeschlossen" />
          Bewertungsweg abgeschlossen
        </label>
        <p class="hint small">Gilt für das Produkt: Jedes Release übernimmt diesen
          Stand (Art. 32 / Anhang VIII wird für das Produkt durchlaufen, eine
          Sicherheitsaktualisierung löst nach Erwägungsgrund 39 keine neue
          Bewertung aus). Ohne den Haken lässt sich <strong>kein</strong> Release
          einreichen oder freigeben und keine EU-Konformitätserklärung ausstellen.</p>
      </div>
      <button class="btn-primary" @click="save">Speichern</button>
    </div>

    <!-- #1753: Anhang V verlangt mehr als „Modell + Hersteller". Jedes Feld
         trägt seine Nummer, weil eine Erklärung ohne diese Angaben unwirksam
         ist — und weil die Nummer sagt, warum das Feld nicht verhandelbar ist. -->
    <div class="form-card doc">
      <h4>EU-Konformitätserklärung (Anhang V)</h4>
      <p class="hint">Aus diesen Angaben entsteht das Dokument, das der Hersteller
        unterschreibt (Art.&nbsp;28 i.V.m. Anhang&nbsp;V). Download im Reiter
        „📄 Berichte" → „EU-Konformitätserklärung". Der Satz zur alleinigen
        Verantwortung (Nr.&nbsp;3) und die Konformitätsaussage (Nr.&nbsp;5) sind
        Gesetzesformeln und werden vom Dokument selbst gesetzt.</p>
      <p v-if="!form.bewertung_abgeschlossen" class="hint warn">
        DoC erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist.
      </p>

      <h5>Nr. 1 — Produktidentifikation</h5>
      <div class="form-row">
        <label>Produktname *</label>
        <input v-model="docForm.produkt_name" placeholder="Vorbelegung: Produkt des Projekts" />
      </div>
      <div class="form-row">
        <label>Typ / Modell *</label>
        <input v-model="docForm.produkt_typ" />
      </div>
      <div class="form-row">
        <label>Charge, Serie oder Version *</label>
        <input v-model="docForm.produkt_charge" placeholder="z. B. Version 7.4.8" />
      </div>

      <h5>Nr. 2 — Hersteller</h5>
      <div class="form-row">
        <label>Name *</label>
        <input v-model="docForm.hersteller" placeholder="Vorbelegung: Unternehmen des Projekts" />
      </div>
      <div class="form-row">
        <label>Anschrift *</label>
        <textarea v-model="docForm.hersteller_adresse" rows="2"
                  placeholder="Straße, PLZ Ort, Land"></textarea>
      </div>
      <div class="form-row">
        <label>EU-Bevollmächtigter (falls vorhanden)</label>
        <input v-model="docForm.bevollmaechtigter" />
      </div>

      <h5>Nr. 4 — Gegenstand der Erklärung</h5>
      <div class="form-row">
        <label>Beschreibung zur Rückverfolgbarkeit *</label>
        <textarea v-model="docForm.gegenstand" rows="2"></textarea>
      </div>

      <h5>Nr. 5 — Weiteres Unionsrecht</h5>
      <div class="form-row">
        <label>Weitere Rechtsakte, die die Erklärung mit abdeckt</label>
        <input v-model="docForm.weiteres_unionsrecht"
               placeholder="z. B. Richtlinie 2014/53/EU (RED)" />
      </div>

      <h5>Nr. 6 — Angewandte Normen und Spezifikationen</h5>
      <!-- #1763: Dass es für die CRA noch keine harmonisierten Normen gibt,
           wusste bisher nur der Quelltext (cra/doc_export.py). Als Leerfeld
           sieht die Angabe nach einer Lücke aus; als Hinweis ist sie ein
           Beleg, dass das Werkzeug den Stand kennt. -->
      <p class="hint">
        Für die Verordnung (EU) 2024/2847 sind bislang <strong>keine
        harmonisierten Normen</strong> im Amtsblatt veröffentlicht. Diese
        Angabe ist deshalb keine Pflichtangabe; üblich ist die Nennung
        angewandter Spezifikationen (etwa IEC 62443-4-1/-4-2, ETSI EN 303 645)
        mit dem Hinweis, dass sie den Stand der Technik abbilden.
      </p>
      <div class="form-row">
        <label>Eine Norm je Zeile</label>
        <textarea v-model="docForm.normen" rows="3"
                  placeholder="EN 18031-1&#10;ETSI EN 303 645"></textarea>
      </div>

      <h5>Nr. 7 — Notifizierte Stelle und Zertifikat
        <span class="small">(soweit zutreffend)</span></h5>
      <p class="hint small">Pflicht, sobald der Bewertungsweg eine notifizierte Stelle
        einschließt (B+C, H, EUCC).</p>
      <div class="form-row">
        <label>Name der Stelle</label>
        <input v-model="docForm.nb_name" />
      </div>
      <div class="form-row">
        <label>Kennnummer</label>
        <input v-model="docForm.nb_kennnummer" placeholder="Vorbelegung: aus der Bewertung" />
      </div>
      <div class="form-row">
        <label>Zertifikat (Nummer / Bezeichnung)</label>
        <input v-model="docForm.nb_zertifikat" />
      </div>
      <div class="form-row">
        <label>Durchgeführtes Verfahren (Anhang VIII)</label>
        <input v-model="docForm.nb_verfahren" placeholder="Vorbelegung: gewählter Bewertungsweg" />
      </div>

      <h5>Nr. 8 — Zusatzangaben, Ort und Datum, Unterzeichner</h5>
      <div class="form-row">
        <label>Zusatzangaben</label>
        <textarea v-model="docForm.zusatzangaben" rows="2"></textarea>
      </div>
      <div class="form-row">
        <label>Ort der Ausstellung *</label>
        <input v-model="docForm.ort" />
      </div>
      <div class="form-row">
        <label>Datum der Ausstellung *</label>
        <input type="date" v-model="docForm.datum" />
      </div>
      <div class="form-row">
        <label>Unterzeichner — Name *</label>
        <input v-model="docForm.unterzeichner_name" />
      </div>
      <div class="form-row">
        <label>Unterzeichner — Funktion *</label>
        <input v-model="docForm.unterzeichner_funktion"
               placeholder="z. B. Geschäftsführer, Head of Product Security" />
      </div>

      <p v-if="fehlendePflicht.length" class="hint warn">
        ⚠️ Pflichtangaben fehlen — es entsteht nur ein als ENTWURF
        gekennzeichnetes Dokument:
        {{ fehlendePflicht.map(f => `Nr. ${f.nr}: ${f.bezeichnung}`).join('; ') }}
      </p>
      <button class="btn-primary"
              :disabled="!form.bewertung_abgeschlossen || fehlendePflicht.length > 0"
              @click="issueDoc">
        Erklärung ausstellen
      </button>
      <p v-if="store.record.doc_ausgestellt" class="hint ok">
        ✓ Fassung {{ store.record.doc_version }} ausgestellt am
        {{ (store.record.doc_ausgestellt_am || '').slice(0, 10) }}
      </p>
    </div>

    <!-- #1671: CE-Kennzeichnung (Modul A: Hersteller bringt selbst an) -->
    <div class="form-card ce">
      <h4>CE-Kennzeichnung</h4>
      <p class="hint">Bei Modul A (Selbstbewertung) bringst du das CE-Zeichen nach Ausstellung der
        EU-Konformitätserklärung in Eigenverantwortung an. Es wird nicht beantragt.</p>
      <div class="ce-logo-row">
        <div class="ce-preview" v-html="CE_SVG"></div>
        <div>
          <button class="btn-secondary" @click="downloadCeLogo">⬇️ CE-Logo (SVG) herunterladen</button>
          <p class="hint small">Referenzdarstellung. Beim Skalieren Proportionen beibehalten,
            Mindesthöhe 5&nbsp;mm, sichtbar/lesbar/dauerhaft (Reg. (EG) 765/2008 Art.&nbsp;30).</p>
        </div>
      </div>
      <ul class="ce-check">
        <li>EU-Konformitätserklärung ausgestellt (Voraussetzung)</li>
        <li>CE am Produkt bzw. — falls nicht möglich — auf Verpackung/Begleitunterlagen angebracht</li>
        <li>Mindesthöhe 5&nbsp;mm, Proportionen gewahrt, dauerhaft &amp; gut sichtbar</li>
        <li>Bei Software: z.&nbsp;B. im Info-/Über-Dialog und in der Dokumentation</li>
      </ul>
      <div class="form-row">
        <label>Angebracht am</label>
        <input type="date" v-model="form.ce_angebracht_am" />
      </div>
      <div class="form-row">
        <label>Ort der Anbringung</label>
        <input v-model="form.ce_ort" placeholder="z. B. Info-Dialog, Handbuch S. 1, Verpackung" />
      </div>
      <div class="form-row">
        <label>Nachweis / Bemerkung</label>
        <textarea v-model="form.ce_nachweis" rows="2" placeholder="Beleg, Screenshot-Referenz, Verantwortliche/r …"></textarea>
      </div>
      <button class="btn-primary" @click="save">CE-Kennzeichnung speichern</button>
    </div>

    <!-- #1763: Die wesentliche Änderung war ZWEIMAL gebaut — hier mit eigenem
         Formular und eigener Begründung, und im Release-Vorgang (#1755), wo sie
         seit v8.0.0 wirklich etwas auslöst (Einfrieren des Vorstands, vier
         Neubewertungs-Punkte, rote Ampel). Zwei Eingabestellen für dieselbe
         Frage bedeuten zwei Begründungen und zwei Audit-Spuren; welche im
         Nachweis gilt, wäre nicht mehr zu sagen. Hier steht deshalb nur noch
         der Stand mit dem Weg dorthin. -->
    <div class="form-card release">
      <h4>Wesentliche Änderung (Art. 3 Nr. 30)</h4>
      <p class="hint">Aktuelle Version: <strong>{{ releaseStore.release.aktuelle_version || 'v1.0' }}</strong></p>
      <p class="hint">
        Erfasst wird die wesentliche Änderung im Release-Vorgang — dort löst sie
        das Einfrieren des bisherigen Stands und die vier Neubewertungs-Punkte
        aus (Art. 32/Anhang VIII, Anhang VII, Art. 28, Art. 13 Abs. 1–3).
      </p>
      <button class="btn-secondary" @click="$emit('goto', 'releases')">
        → Im Release-Vorgang erfassen
      </button>
      <div v-if="releaseStore.snapshots.length" class="snapshots">
        <h5>Eingefrorene Vorgänger-Versionen</h5>
        <ul>
          <li v-for="s in releaseStore.snapshots" :key="s.id">
            {{ s.version }} — {{ s.grund }} ({{ (s.eingefroren_am || '').slice(0, 10) }})
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useCraKonformitaetStore } from '../../stores/craKonformitaet'
import { useCraReleaseStore } from '../../stores/craRelease'
import { useCraStore } from '../../stores/cra'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'

const props = defineProps<{ projekt: string }>()
const store = useCraKonformitaetStore()
// Nur lesend: Hersteller und Produkt stehen schon in den Projekt-Stammdaten und
// werden für die Erklärung vorbelegt, statt sie zweimal erfassen zu lassen.
defineEmits<{ (e: 'goto', ziel: string): void }>()
const craStore = useCraStore()
const releaseStore = useCraReleaseStore()
// #1763: Formular, Reassess-Haken und `doSubstantialMod` sind hier entfallen —
// die wesentliche Änderung wird im Release-Vorgang erfasst (#1755). Der Store
// behält seine Funktionen; sie werden nur von dieser Ansicht nicht mehr
// aufgerufen.

const form = ref<any>({ bewertungsweg: 'A', checkliste: {}, nb_kennnummer: '',
  eucc_level: '', ce_status: 'offen', bewertung_abgeschlossen: false,
  ce_ort: '', ce_angebracht_am: '', ce_nachweis: '' })
// #1753: die Anhang-V-Felder. ``modell`` bleibt als Altfeld erhalten und wird
// beim Laden auf ``produkt_typ`` abgebildet — Bestandsdaten gehen nicht verloren.
const DOC_FELDER = [
  'produkt_name', 'produkt_typ', 'produkt_charge',
  'hersteller', 'hersteller_adresse', 'bevollmaechtigter',
  'gegenstand', 'weiteres_unionsrecht', 'normen',
  'nb_name', 'nb_kennnummer', 'nb_zertifikat', 'nb_verfahren',
  'zusatzangaben', 'ort', 'datum', 'unterzeichner_name', 'unterzeichner_funktion',
] as const

// Pflichtangaben für die Anzeige. Maßgeblich bleibt der Renderer
// (``cra/doc_export.py``: ANHANG_V) — er prüft dieselben Angaben, bevor eine
// ausgestellte Fassung entsteht. Hier stehen sie nur, damit der Anwender die
// Lücke sieht, bevor er auf „ausstellen" drückt.
const DOC_PFLICHT: { nr: number; bezeichnung: string; felder: string[] }[] = [
  { nr: 1, bezeichnung: 'Produktname und Typ', felder: ['produkt_name', 'produkt_typ'] },
  { nr: 1, bezeichnung: 'Charge, Serie oder Version', felder: ['produkt_charge'] },
  { nr: 2, bezeichnung: 'Name des Herstellers', felder: ['hersteller'] },
  { nr: 2, bezeichnung: 'Anschrift des Herstellers', felder: ['hersteller_adresse'] },
  { nr: 4, bezeichnung: 'Gegenstand der Erklärung', felder: ['gegenstand'] },
  { nr: 8, bezeichnung: 'Ort und Datum', felder: ['ort', 'datum'] },
  { nr: 8, bezeichnung: 'Unterzeichner mit Name und Funktion',
    felder: ['unterzeichner_name', 'unterzeichner_funktion'] },
]
// Nr. 7 nur, wenn eine notifizierte Stelle beteiligt ist („soweit zutreffend").
const WEGE_MIT_NB = ['B+C', 'H', 'EUCC']

const docForm = ref<any>(Object.fromEntries(DOC_FELDER.map(f => [f, ''])))

const fehlendePflicht = computed(() => {
  const pflicht = [...DOC_PFLICHT]
  if (WEGE_MIT_NB.includes(form.value.bewertungsweg)) {
    pflicht.push({ nr: 7, bezeichnung: 'Notifizierte Stelle und Zertifikat',
      felder: ['nb_name', 'nb_kennnummer', 'nb_zertifikat'] })
  }
  return pflicht.filter(p => p.felder.some(f => !String(docForm.value[f] || '').trim()))
})

const sollNachweise = computed(() => store.checkliste[form.value.bewertungsweg] || [])

function wegLabel(w: string) {
  return ({ A: 'Modul A (Selbstbewertung)', 'B+C': 'Modul B+C (Baumusterprüfung)',
    H: 'Modul H (Umfassendes QM)', EUCC: 'EUCC-Zertifizierung' } as Record<string, string>)[w] || w
}
function ceLabel(s: string) {
  return ({ offen: 'Offen', in_bewertung: 'In Bewertung',
    bewertung_abgeschlossen: 'Bewertung abgeschlossen', doc_ausgestellt: 'DoC ausgestellt',
    ce_angebracht: 'CE angebracht' } as Record<string, string>)[s] || s
}
function nachweisLabel(n: string) {
  return n.replace(/_/g, ' ')
}

function loadFromRecord() {
  const r = store.record as any
  if (r && r.bewertungsweg) {
    form.value = {
      bewertungsweg: r.bewertungsweg, checkliste: { ...(r.checkliste || {}) },
      nb_kennnummer: r.nb_kennnummer || '', eucc_level: r.eucc_level || '',
      ce_status: r.ce_status || 'offen',
      bewertung_abgeschlossen: !!r.bewertung_abgeschlossen,
      ce_ort: r.ce_ort || '', ce_angebracht_am: (r.ce_angebracht_am || '').slice(0, 10),
      ce_nachweis: r.ce_nachweis || '',
    }
  }
  loadDocFromRecord(r)
}

// #1753: Erfasste Anhang-V-Angaben zurück ins Formular. Vorbelegt wird nur,
// was ohnehin in den Stammdaten steht (Hersteller, Produkt, NB-Kennnummer) —
// erfunden wird nichts, fehlende Angaben bleiben sichtbar leer.
function loadDocFromRecord(r: any) {
  const d = (r && r.doc) || {}
  const proj: any = craStore.selectedProjektObj || {}
  const werte: Record<string, string> = {}
  for (const feld of DOC_FELDER) werte[feld] = String(d[feld] ?? '')
  if (Array.isArray(d.normen)) werte.normen = d.normen.join('\n')
  if (!werte.produkt_typ) werte.produkt_typ = String(d.modell ?? '')   // Altfeld
  if (!werte.produkt_name) werte.produkt_name = String(proj.produkt || proj.name || '')
  if (!werte.hersteller) werte.hersteller = String(proj.unternehmen || '')
  if (!werte.nb_kennnummer) werte.nb_kennnummer = String((r && r.nb_kennnummer) || '')
  docForm.value = werte
}

// #1671: konformes CE-Logo als SVG herunterladen (Proportionen nach Reg. (EG) 765/2008).
// #1671/#1758: Proportionen nach Verordnung (EG) Nr. 765/2008, Anhang II.
// EINE Quelle: identisch zu `cra/assets/ce_kennzeichen.svg`; ein Test hält
// beide zusammen. Der Mittelbalken des E ist ein eigenes Element — im
// selben Pfad hebt ihn die Füllregel im Überlappungsbereich auf, und in
// der ersten Fassung stand er zudem frei in der Luft (kein E).
const CE_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 228 128" width="228" height="128">
<g fill="#000">
  <path d="M64 8 A56 56 0 1 0 64 120 A56 56 0 0 0 112 92 L96 83 A38 38 0 1 1 96 45 L112 36 A56 56 0 0 0 64 8 Z"/>
  <path d="M172 8 A56 56 0 1 0 172 120 A56 56 0 0 0 220 92 L204 83 A38 38 0 1 1 204 45 L220 36 A56 56 0 0 0 172 8 Z"/>
  <rect x="130" y="55" width="66" height="18"/>
</g>
</svg>`
function downloadCeLogo() {
  const blob = new Blob([CE_SVG], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'CE-Kennzeichen.svg'; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

async function save() {
  await store.save(props.projekt, { ...form.value })
  loadFromRecord()
}
async function issueDoc() {
  if (await store.issueDoc(props.projekt, { ...docForm.value })) loadFromRecord()
}

async function load() {
  await store.fetch(props.projekt)
  loadFromRecord()
  await releaseStore.fetch(props.projekt)
}

onMounted(async () => { await store.fetchConstants(); await load() })
watch(() => props.projekt, load)
</script>

<style scoped>
.panel-header h3 { color: #1565c0; margin-bottom: 4px; }
.panel-header .sub { color: #607d8b; font-size: 13px; }
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; }
.checkliste { display: flex; flex-direction: column; gap: 4px; }
.check-item { flex-direction: row; align-items: center; gap: 6px; }
.hint.warn { color: #c62828; }
.hint.ok { color: #2e7d32; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.reassess { margin: 6px 0 0 18px; font-size: 12px; }
.reassess .offen { color: #c62828; font-weight: 600; }
.reassess .ok { color: #2e7d32; }
.snapshots { margin-top: 10px; font-size: 12px; }
.snapshots h5 { margin: 4px 0; color: #455a64; }
/* #1671: CE-Kennzeichnung */
.ce-logo-row { display: flex; gap: 16px; align-items: center; margin: 8px 0; }
.ce-preview { width: 72px; flex: 0 0 72px; }
.ce-preview :deep(svg) { width: 72px; height: auto; }
.ce-check { margin: 8px 0 12px 18px; font-size: 12px; color: #455a64; }
.ce-check li { margin: 2px 0; }
.hint.small { font-size: 11px; }
/* #1753: Anhang-V-Abschnitte in der Erklärung */
.doc h5 { margin: 14px 0 4px; color: #1565c0; font-size: 13px; }
.doc h5 .small { color: #607d8b; font-weight: 400; font-size: 11px; }
</style>
