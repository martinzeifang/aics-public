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

    <!-- #1824: Anhang I Teil II Nr. 3 — „regelmäßig und wirksam testen".
         Hier und nicht am Release: Eine Teststrategie wird nicht je Release neu
         gewählt, und eine zweite Eingabestelle wäre die Falle aus #1805. -->
    <div class="form-card tests">
      <h4>🧪 Sicherheitstests (Anhang I Teil II Nr. 3)</h4>
      <p class="hint">Die Verordnung verlangt, die Sicherheit des Produkts
        <strong>regelmäßig und wirksam</strong> zu testen und zu überprüfen; die
        Berichte darüber gehören nach Anhang&nbsp;VII Nr.&nbsp;6 in die
        technische Dokumentation. Welches Verfahren, schreibt sie nicht vor —
        die Frage lautet deshalb, <em>womit</em> Sie die Pflicht belegen.</p>
      <div class="form-row">
        <label>Womit wird die Pflicht belegt?</label>
        <select v-model="testForm.testnachweis_art">
          <option value="">— nicht festgelegt —</option>
          <option v-for="a in store.testArten" :key="a.wert" :value="a.wert">
            {{ a.label }}
          </option>
        </select>
      </div>

      <!-- Nur beim Verzicht: Begründung und Wiedervorlage sind dann Pflicht. -->
      <template v-if="testForm.testnachweis_art === 'kein_test'">
        <p class="hint warn">Der Verzicht schließt diesen Punkt
          <strong>nicht</strong>: Anhang&nbsp;I Teil&nbsp;II Nr.&nbsp;3 ist dann
          nicht erfüllt, und das weist die Akte aus — im Release-Check, im
          Konformitätsnachweis und in der Kundenfassung. Die Entscheidung bleibt
          Ihre; sie steht mit Namen und Datum in der Akte.</p>
        <div class="form-row">
          <label>Begründung * (mindestens {{ store.testRegeln.min_begruendung }} Zeichen)</label>
          <textarea v-model="testForm.test_verzicht_begruendung" rows="3"
                    placeholder="Warum wird auf eigene Sicherheitstests verzichtet? Welche anderen Maßnahmen treten an ihre Stelle?"></textarea>
          <p class="hint small">{{ testForm.test_verzicht_begruendung.trim().length }} Zeichen</p>
        </div>
        <div class="form-row">
          <label>Wiedervorlage * — wann wird die Entscheidung erneut getroffen?</label>
          <input type="date" v-model="testForm.test_verzicht_review" />
          <p class="hint small">Ein Verzicht ohne Ablaufdatum ist eine
            Dauerentscheidung. Vorschlag: {{ reviewVorschlag }}</p>
        </div>
      </template>

      <button class="btn-primary" @click="saveTests">Sicherheitstests speichern</button>

      <!-- Der gerechnete Stand, nicht eine zweite Rechnung im Browser. -->
      <div v-if="testBefund.art !== undefined" class="tests-stand">
        <h5>Stand</h5>
        <p class="hint">
          Nachweise in der Akte: <strong>{{ testBefund.nachweis_count || 0 }}</strong>
          <template v-if="testBefund.juengster">
            · jüngster vom <strong>{{ testBefund.juengster }}</strong>
            ({{ testBefund.alter_tage }} Tage alt)
          </template>
          <template v-if="testBefund.bezug">
            · letzte Funktionsänderung: {{ testBefund.bezug }}
          </template>
        </p>
        <ul v-if="(testBefund.nachweise || []).length" class="nachweis-liste">
          <li v-for="(n, i) in testBefund.nachweise" :key="i">
            {{ n.quelle }} {{ n.label }}<span v-if="n.datum"> — {{ n.datum }}</span>
          </li>
        </ul>
        <p v-if="!(testBefund.maengel || []).length" class="hint ok">
          ✓ Keine Feststellungen.
        </p>
        <ul v-else class="mangel-liste">
          <li v-for="m in testBefund.maengel" :key="m.id"
              :class="m.wirkung === 'rot' ? 'rot' : 'bedingt'">
            {{ m.text }} <span class="small">— {{ m.hinweis }}</span>
          </li>
        </ul>
        <p v-if="testBefund.offene_befunde" class="hint small">
          {{ testBefund.offene_befunde }} schwere(r) offene(r) Befund(e) aus
          Testberichten. Gemeldet werden sie bei den offenen kritischen
          Schwachstellen — hier stehen sie nur als Zusammenhang.
        </p>
      </div>
    </div>

    <!-- #1886/#1887: Das Anhang-V-Formular liegt in einer eigenen Komponente
         und steht auch im Releases-Tab — dort mit gebundener Version. Zwei
         Eingabemasken für dieselbe Erklärung wären die Falle aus #1805: Welche
         gilt, wüsste hinterher niemand. Hier ohne `release`, also auf dem
         Produkt-Datensatz; ein Release-Vorgang erbt diesen Stand bis auf
         Version, Gegenstand und Datum (`NICHT_GEERBTE_DOC_FELDER`). -->
    <KonformitaetserklaerungForm
      ref="docForm"
      :projekt="projekt"
      :bewertung-abgeschlossen="form.bewertung_abgeschlossen"
      @assistent="oeffneAssistent"
      @ausgestellt="load" />

    <!-- #1887: Der Assistent kann sein Ergebnis jetzt in das Formular
         übernehmen — und zwar nur die Prosafelder, die der Server freigibt. -->
    <DocAssistentModal v-if="assistentOffen" :projekt="projekt"
                       :release="assistentRelease"
                       @uebernehmen="(f: any) => docForm?.uebernehmeAusKi(f)"
                       @close="assistentOffen = false" />
    <p class="hint small">
      Im Tagesgeschäft wird die Erklärung je Release ausgestellt — im Reiter
      „🚦 Releases" steht dasselbe Formular mit gebundener Version.
      <button class="btn-link" @click="$emit('goto', 'releases')">
        → Zu den Release-Vorgängen
      </button>
    </p>

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
import KonformitaetserklaerungForm from '../../components/cra/KonformitaetserklaerungForm.vue'
import DocAssistentModal from '../../components/cra/DocAssistentModal.vue'

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
// #1886/#1887: Die Anhang-V-Felder liegen in `KonformitaetserklaerungForm`.
// Sie standen hier und im Releases-Tab wäre eine zweite Maske entstanden —
// die Falle aus #1805. Mit der Komponente ist auch die zweite Pflichtfeld-
// Liste weg: Maßgeblich ist `doc_export.ANHANG_V` im Server.

// Der KI-Assistent für die Erklärung. Er lag bis v8.2.2 im Assistenten-Tab und
// konnte das Formular **nicht erreichen** (#1887) — sein Ergebnis wurde als
// Dokument gespeichert, die Felder blieben leer.
const assistentOffen = ref(false)
const assistentRelease = ref('')
const docForm = ref<any>(null)
function oeffneAssistent(release: string) {
  assistentRelease.value = String(release || '')
  assistentOffen.value = true
}

// #1824: Sicherheitstests. Eigenes Formular und eigener Endpunkt — Person und
// Zeitpunkt des Verzichts stempelt der Server (siehe put_sicherheitstests).
const testForm = ref({ testnachweis_art: '', test_verzicht_begruendung: '',
                       test_verzicht_review: '' })
const testBefund = computed<any>(() => store.testBefund || {})
const reviewVorschlag = computed(() => {
  const d = new Date()
  d.setMonth(d.getMonth() + 12)
  return d.toISOString().slice(0, 10)
})

async function saveTests() {
  if (testForm.value.testnachweis_art === 'kein_test'
      && !testForm.value.test_verzicht_review) {
    // Vorbelegen statt den Anwender raten lassen; verlangt wird es ohnehin
    // serverseitig.
    testForm.value.test_verzicht_review = reviewVorschlag.value
  }
  if (await store.saveSicherheitstests(props.projekt, { ...testForm.value })) {
    loadTestsFromRecord()
  }
}

function loadTestsFromRecord() {
  const r = store.record as any
  testForm.value = {
    testnachweis_art: r?.testnachweis_art || '',
    test_verzicht_begruendung: r?.test_verzicht_begruendung || '',
    test_verzicht_review: (r?.test_verzicht_review || '').slice(0, 10),
  }
}


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

async function load() {
  await store.fetch(props.projekt)
  loadFromRecord()
  loadTestsFromRecord()
  await store.fetchSicherheitstests(props.projekt)
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
/* #1824: Sicherheitstests */
.tests-stand { margin-top: 12px; border-top: 1px solid #cfd8e3; padding-top: 8px; }
.tests-stand h5 { margin: 0 0 4px; color: #455a64; font-size: 13px; }
.nachweis-liste, .mangel-liste { margin: 4px 0 8px 18px; font-size: 12px; }
.nachweis-liste li, .mangel-liste li { margin: 2px 0; }
.mangel-liste li.rot { color: #c62828; font-weight: 600; }
.mangel-liste li.bedingt { color: #ef6c00; }
.mangel-liste .small { font-weight: 400; color: #455a64; }
.doc h5 { margin: 14px 0 4px; color: #1565c0; font-size: 13px; }
.doc h5 .small { color: #607d8b; font-weight: 400; font-size: 11px; }
</style>
