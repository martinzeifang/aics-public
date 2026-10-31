<!--
  EU-Konformitätserklärung nach Anhang V — EINE Maske, zwei Einstiege (#1886/#1887).

  WARUM DIESE KOMPONENTE EXISTIERT
  Das Formular stand bis v8.2.2 fest im Tab „✅ Konformität" und schrieb dort
  ausschließlich auf den Produkt-Datensatz. Im Tagesgeschäft wird die Erklärung
  aber je Release gebraucht, und die Version tippte ein Mensch — genau so
  entstand der Fall aus #1885 (Nr. 1 und der Image-Tag nannten 8.2.3, der Text
  von Nr. 4 noch 8.0.11).

  Eine **zweite** Eingabemaske am Release wäre die Falle aus #1805: zwei
  Stellen für denselben Sachverhalt, und welche gilt, weiß hinterher niemand.
  Deshalb diese Komponente: Sie steht im Konformitäts-Tab (ohne `release`) und
  im Releases-Tab (mit gebundener Version). Die Pflichtangaben und die
  Prüfungen sitzen im Server und wirken damit an beiden Einstiegen.

  DIE KNÖPFE FOLGEN DER FELDKLASSE (#1887)
  „⚙ Aus den Quellen" erscheint nur bei Feldern, zu denen der Server etwas
  sagen kann — gerechnete (Version, Gegenstand, Verfahren, Datum) und
  übernommene (Projekt, Mandant, Akteure, Bewertung). Ein gefülltes Feld wird
  nie ohne ausdrücklichen Klick ersetzt (#1769/#1773). Die KI formuliert nur
  Prosa; welche Felder sie setzen darf, entscheidet der Server
  (`doc_vorschlag.KI_FELDER`) und nicht diese Datei.
-->
<template>
  <div class="form-card doc">
    <h4>
      EU-Konformitätserklärung (Anhang V)
      <span v-if="release" class="version-pille">Release {{ release }}</span>
      <span v-else class="version-pille produkt">Produkt-Datensatz</span>
    </h4>
    <p class="hint">
      Aus diesen Angaben entsteht das Dokument, das der Hersteller unterschreibt
      (Art.&nbsp;28 i.V.m. Anhang&nbsp;V). Der Satz zur alleinigen Verantwortung
      (Nr.&nbsp;3) und die Konformitätsaussage (Nr.&nbsp;5) sind Gesetzesformeln
      und werden vom Dokument selbst gesetzt.
    </p>
    <p v-if="release" class="hint">
      Diese Fassung gilt für <strong>Release {{ release }}</strong>. Hersteller,
      Anschrift, Unterzeichner und die angewandten Spezifikationen werden vom
      Produkt-Datensatz übernommen; Version, Gegenstand und Datum beziehen sich
      auf diesen Stand.
    </p>
    <p v-if="!bewertungAbgeschlossen" class="hint warn">
      Erklärung erst ausstellbar, wenn der Bewertungsweg abgeschlossen ist.
    </p>

    <FehlerHinweis v-if="store.error" :text="store.error" @close="store.error = null" />

    <!-- #1893: Leiste und Befundliste sind geteilte Bausteine — dieselben
         benutzt die AI-Act-Erklärung. -->
    <QuellenLeiste :anzahl="anzahlFuellbar" @alle="alleFuellen">
      <template #eigene>
        <button class="btn-secondary" @click="emit('assistent', release)">
          🤖 Assistent
        </button>
      </template>
    </QuellenLeiste>
    <BefundListe :befunde="befunde" titel="Vor dem Ausstellen zu klären" />

    <h5>Nr. 1 — Produktidentifikation</h5>
    <FeldZeile label="Produktname *" feld="produkt_name" v-bind="zeile">
      <input v-model="werte.produkt_name" />
    </FeldZeile>
    <FeldZeile label="Typ / Modell *" feld="produkt_typ" v-bind="zeile">
      <input v-model="werte.produkt_typ" />
    </FeldZeile>
    <FeldZeile label="Charge, Serie oder Version *" feld="produkt_charge" v-bind="zeile">
      <input v-model="werte.produkt_charge" placeholder="wird aus der Release-Historie gefüllt" />
    </FeldZeile>

    <h5>Nr. 2 — Hersteller</h5>
    <FeldZeile label="Name *" feld="hersteller" v-bind="zeile">
      <input v-model="werte.hersteller" />
    </FeldZeile>
    <FeldZeile label="Anschrift *" feld="hersteller_adresse" v-bind="zeile">
      <textarea v-model="werte.hersteller_adresse" rows="2"
                placeholder="Straße, PLZ Ort, Land"></textarea>
    </FeldZeile>
    <FeldZeile label="EU-Bevollmächtigter (falls vorhanden)" feld="bevollmaechtigter"
               v-bind="zeile">
      <input v-model="werte.bevollmaechtigter" />
    </FeldZeile>

    <!-- #1887: Diese Angaben gehören dem Mandanten und nicht dem Produkt. Hier
         erfasst, weil der Anwender beim Ausfüllen der Erklärung merkt, dass sie
         fehlen — gespeichert wird sie an der Firma. -->
    <details class="stamm" :open="!stammVollstaendig">
      <summary>Herstellerangaben des Mandanten
        <span v-if="firma" class="small">({{ firma }})</span>
        <span v-if="!stammVollstaendig" class="offen">— unvollständig</span>
      </summary>
      <p class="hint small">
        Anschrift, Ort und Unterzeichner gelten für <strong>alle Produkte dieses
        Mandanten</strong>. Einmal erfasst, speisen sie jede Erklärung — statt
        je Produkt erneut getippt zu werden.
      </p>
      <div class="form-row">
        <label>Anschrift des Herstellers</label>
        <textarea v-model="stamm.anschrift" rows="2"
                  placeholder="Straße, PLZ Ort, Land"></textarea>
      </div>
      <div class="form-row">
        <label>Ort der Ausstellung</label>
        <input v-model="stamm.ort" />
      </div>
      <div class="form-row">
        <label>Unterzeichner — Name</label>
        <input v-model="stamm.unterzeichner_name" />
      </div>
      <div class="form-row">
        <label>Unterzeichner — Funktion</label>
        <input v-model="stamm.unterzeichner_funktion"
               placeholder="z. B. Geschäftsführer, Head of Product Security" />
      </div>
      <button class="btn-secondary" @click="stammSpeichern">
        Herstellerangaben des Mandanten speichern
      </button>
    </details>

    <h5>Nr. 4 — Gegenstand der Erklärung</h5>
    <FeldZeile label="Beschreibung zur Rückverfolgbarkeit *" feld="gegenstand"
               v-bind="zeile">
      <textarea v-model="werte.gegenstand" rows="5"></textarea>
    </FeldZeile>
    <details v-if="gegenstandQuellen.length || gegenstandFehlt.length" class="herkunft">
      <summary>Woraus der Vorschlag entsteht</summary>
      <ul class="small">
        <li v-for="(f, i) in gegenstandQuellen" :key="'q' + i">✓ {{ f.text }}</li>
        <li v-for="(f, i) in gegenstandFehlt" :key="'f' + i" class="offen">
          ✗ {{ f.text }}
        </li>
      </ul>
    </details>

    <h5>Nr. 5 — Weiteres Unionsrecht</h5>
    <p class="hint small">
      Nur Rechtsakte nennen, für die das Produkt tatsächlich eine
      Konformitätserklärung abgibt (Art.&nbsp;28 Abs.&nbsp;2 erlaubt eine
      gemeinsame Erklärung). Ob ein Rechtsakt greift, hängt vom Produkt ab und
      wird nicht hergeleitet.
    </p>
    <div class="form-row">
      <label>Weitere Rechtsakte</label>
      <input v-model="werte.weiteres_unionsrecht"
             placeholder="z. B. Richtlinie 2014/53/EU (RED)" />
    </div>
    <div v-if="unionsrecht.length" class="katalog">
      <button v-for="e in unionsrecht" :key="e.id" class="chip"
              :title="e.zweck" @click="unionsrechtDazu(e.bezeichnung)">
        + {{ e.bezeichnung }}
      </button>
    </div>

    <h5>Nr. 6 — Angewandte Normen und Spezifikationen</h5>
    <p class="hint">
      {{ harmonisiertHinweis }}
    </p>
    <!-- #1884: Der Schalter ist der Kern. Ohne ihn kannte der Datensatz nur
         „nichts erfasst", und das Dokument druckte dafür einen Gedankenstrich —
         der sagt weder, dass nichts angewandt wurde, noch dass die Angabe
         fehlt. -->
    <label class="schalter">
      <input type="checkbox" v-model="werte.keine_harmonisierten" />
      Es wurden <strong>keine harmonisierten Normen</strong> nach Art.&nbsp;27
      angewandt (ausdrückliche Feststellung für Nr.&nbsp;6)
    </label>
    <div class="form-row">
      <label>Angewandte Spezifikationen — eine je Zeile</label>
      <textarea v-model="werte.normen" rows="3"
                placeholder="IEC 62443-4-1&#10;ETSI EN 303 645"></textarea>
    </div>
    <div v-if="normenBelegt.length" class="belegt">
      <p class="hint small">Die Akte belegt diese Spezifikationen:</p>
      <button v-for="n in normenBelegt" :key="n.id" class="chip belegt-chip"
              :title="n.herkunft" @click="normDazu(n.bezeichnung)">
        + {{ n.bezeichnung }}
      </button>
    </div>
    <details v-if="normenGruppen.length" class="katalog-liste">
      <summary>Katalog öffnen (Stand {{ katalogStand }})</summary>
      <div v-for="g in normenGruppen" :key="g.id" class="gruppe">
        <h6>{{ g.titel }}</h6>
        <p class="hint small">{{ g.hinweis }}</p>
        <div v-if="g.normen.length" class="katalog">
          <button v-for="n in g.normen" :key="n.id" class="chip" :title="n.zweck"
                  @click="normDazu(n.bezeichnung)">+ {{ n.bezeichnung }}</button>
        </div>
        <p v-else class="hint small">— keine Einträge —</p>
      </div>
    </details>

    <h5>Nr. 7 — Notifizierte Stelle und Zertifikat
      <span class="small">(soweit zutreffend)</span></h5>
    <p class="hint small">Pflicht, sobald der Bewertungsweg eine notifizierte
      Stelle einschließt (B+C, H, EUCC).</p>
    <FeldZeile label="Name der Stelle" feld="nb_name" v-bind="zeile">
      <input v-model="werte.nb_name" />
    </FeldZeile>
    <FeldZeile label="Kennnummer" feld="nb_kennnummer" v-bind="zeile">
      <input v-model="werte.nb_kennnummer" />
    </FeldZeile>
    <FeldZeile label="Zertifikat (Nummer / Bezeichnung)" feld="nb_zertifikat"
               v-bind="zeile">
      <input v-model="werte.nb_zertifikat" />
    </FeldZeile>
    <FeldZeile label="Durchgeführtes Verfahren (Anhang VIII)" feld="nb_verfahren"
               v-bind="zeile">
      <input v-model="werte.nb_verfahren" />
    </FeldZeile>

    <h5>Nr. 8 — Zusatzangaben, Ort und Datum, Unterzeichner</h5>
    <FeldZeile label="Zusatzangaben" feld="zusatzangaben" v-bind="zeile">
      <textarea v-model="werte.zusatzangaben" rows="2"
                :disabled="werte.zusatzangaben_keine"></textarea>
    </FeldZeile>
    <label class="schalter">
      <input type="checkbox" v-model="werte.zusatzangaben_keine" />
      Es sind <strong>keine weiteren Angaben</strong> aufzunehmen
    </label>
    <FeldZeile label="Ort der Ausstellung *" feld="ort" v-bind="zeile">
      <input v-model="werte.ort" />
    </FeldZeile>
    <FeldZeile label="Datum der Ausstellung *" feld="datum" v-bind="zeile">
      <input type="date" v-model="werte.datum" />
    </FeldZeile>
    <FeldZeile label="Unterzeichner — Name *" feld="unterzeichner_name" v-bind="zeile">
      <input v-model="werte.unterzeichner_name" />
    </FeldZeile>
    <FeldZeile label="Unterzeichner — Funktion *" feld="unterzeichner_funktion"
               v-bind="zeile">
      <input v-model="werte.unterzeichner_funktion" />
    </FeldZeile>

    <!-- #1898: Hier stand „es entsteht nur ein als ENTWURF gekennzeichnetes
         Dokument". Das ist wahr — aber über eine ANDERE Handlung: Den
         Entwurfsvermerk setzt der Download (`cra/doc_export.ENTWURF_MARKER`).
         Ausstellen geht mit Lücken gar nicht (#1814), und der Knopf ist
         deshalb gesperrt. Der Satz las sich wie eine Beschreibung dessen, was
         der Knopf tut — der Anwender klickte, und nichts passierte. -->
    <p v-if="fehlendePflicht.length" class="hint warn">
      ⚠️ Pflichtangaben fehlen — <strong>ausstellen ist damit nicht möglich</strong>
      (Art. 28 i.V.m. Anhang V):
      {{ fehlendePflicht.map(f => `Nr. ${f.nr}: ${f.bezeichnung}`).join('; ') }}.
      Mit „Entwurf speichern“ geht nichts verloren; der Download liefert
      solange ein als ENTWURF gekennzeichnetes Dokument.
    </p>
    <p v-if="blockierend.length" class="hint warn">
      ⛔ Die Erklärung trägt eine Angabe, die der Akte widerspricht — sie kann
      nicht ausgestellt werden. Siehe oben „Vor dem Ausstellen zu klären".
    </p>
    <!-- #1898: Der Grund gehört dorthin, wo der Knopf ist. Der Hinweis zum
         Bewertungsweg steht am ANFANG dieser Maske — wer unten auf den Knopf
         drückt, hat ihn nicht im Blick. -->
    <p v-if="sperrgruende.length" class="hint warn gesperrt">
      ⛔ „Erklärung ausstellen“ ist gesperrt: {{ sperrgruende.join(' · ') }}
    </p>
    <div class="aktionen">
      <!-- #1887: Entwurf speichern. Bis v8.2.2 gab es nur „ausstellen", und
           das verlangt alle Pflichtangaben — wer nicht fertig wurde, verlor
           beim nächsten Laden alles. -->
      <button class="btn-secondary" @click="entwurfSpeichern">Entwurf speichern</button>
      <button class="btn-primary" :disabled="sperrgruende.length > 0"
              :title="sperrgruende.length
                ? 'Gesperrt: ' + sperrgruende.join(' · ')
                : 'Die Erklärung ausstellen und als Fassung festschreiben'"
              @click="ausstellen([])">
        Erklärung ausstellen
      </button>
      <button v-if="store.bestaetigungNoetig.length" class="btn-secondary"
              @click="ausstellen(store.bestaetigungNoetig)">
        Trotzdem ausstellen — ich verantworte das
      </button>
    </div>
    <p v-if="record?.doc_ausgestellt" class="hint ok">
      ✓ Fassung {{ record.doc_version }} ausgestellt am
      {{ (record.doc_ausgestellt_am || '').slice(0, 10) }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, h } from 'vue'
import { useCraKonformitaetStore } from '../../stores/craKonformitaet'
import FehlerHinweis from '../shared/FehlerHinweis.vue'
import QuellenLeiste from '../shared/QuellenLeiste.vue'
import BefundListe from '../shared/BefundListe.vue'
import { useFormularVorschlag, blockierende } from '../../composables/useFormularVorschlag'
import QuellenKnopf from '../shared/QuellenKnopf.vue'

const props = defineProps<{
  projekt: string
  /** Gebundene Release-Version; leer = Produkt-Datensatz. */
  release?: string
  bewertungAbgeschlossen?: boolean
}>()
const emit = defineEmits<{
  (e: 'assistent', release: string): void
  (e: 'ausgestellt'): void
}>()

const store = useCraKonformitaetStore()
const release = computed(() => String(props.release || ''))
const bewertungAbgeschlossen = computed(() => props.bewertungAbgeschlossen !== false)

// #1753: Die Felder. Maßgeblich bleibt `doc_export.ANHANG_V` im Server — er
// prüft dieselben Angaben, bevor eine ausgestellte Fassung entsteht.
const FELDER = [
  'produkt_name', 'produkt_typ', 'produkt_charge',
  'hersteller', 'hersteller_adresse', 'bevollmaechtigter',
  'gegenstand', 'weiteres_unionsrecht', 'normen',
  'nb_name', 'nb_kennnummer', 'nb_zertifikat', 'nb_verfahren',
  'zusatzangaben', 'ort', 'datum', 'unterzeichner_name', 'unterzeichner_funktion',
] as const
const SCHALTER = ['keine_harmonisierten', 'zusatzangaben_keine'] as const

const werte = ref<any>({
  ...Object.fromEntries(FELDER.map(f => [f, ''])),
  ...Object.fromEntries(SCHALTER.map(f => [f, false])),
})
const stamm = ref<any>({ anschrift: '', ort: '', unterzeichner_name: '',
                         unterzeichner_funktion: '' })

const record = computed<any>(() => store.record || {})
const vorschlag = computed<any>(() => store.vorschlag || {})
const feldVorschlaege = computed<Record<string, any>>(() => vorschlag.value.felder || {})
const befunde = computed<any[]>(() => store.befunde || [])
const blockierend = computed(() => blockierende(befunde.value))
const firma = computed(() => String(vorschlag.value.firma || ''))

const gegenstandQuellen = computed<any[]>(() => vorschlag.value.gegenstand?.fundstellen || [])
const gegenstandFehlt = computed<any[]>(() => vorschlag.value.gegenstand?.fehlend || [])
const normenBelegt = computed<any[]>(() => vorschlag.value.normen || [])
const normenGruppen = computed<any[]>(() => vorschlag.value.katalog?.gruppen || [])
const katalogStand = computed(() => String(vorschlag.value.katalog?.stand || ''))
const unionsrecht = computed<any[]>(() => vorschlag.value.unionsrecht?.eintraege || [])
const harmonisiertHinweis = computed(() =>
  String(normenGruppen.value.find((g: any) => g.id === 'harmonisiert')?.hinweis
    || 'Für die Verordnung (EU) 2024/2847 ist bislang keine harmonisierte Norm '
       + 'im Amtsblatt veröffentlicht.'))

const stammVollstaendig = computed(() =>
  ['anschrift', 'ort', 'unterzeichner_name', 'unterzeichner_funktion']
    .every(f => String(stamm.value[f] || '').trim()))

// #1893: Die Mechanik („nur leere Felder", Ersetzen als eigener Klick) liegt
// im Composable — dieselbe benutzt jede andere Maske dieser Art.
const { anzahlFuellbar, feldFuellen, alleFuellen, istGefuellt: _gefuellt } =
  useFormularVorschlag(werte, feldVorschlaege as any)
const istGefuellt = (feld: string) => _gefuellt(werte.value[feld])

// Pflichtangaben für die Anzeige. Der Server prüft dieselben, bevor eine
// Fassung entsteht (`doc_export.fehlende_pflichtfelder`); hier stehen sie nur,
// damit der Anwender die Lücke sieht, bevor er auf „ausstellen" drückt.
const PFLICHT: { nr: number; bezeichnung: string; felder: string[] }[] = [
  { nr: 1, bezeichnung: 'Produktname und Typ', felder: ['produkt_name', 'produkt_typ'] },
  { nr: 1, bezeichnung: 'Charge, Serie oder Version', felder: ['produkt_charge'] },
  { nr: 2, bezeichnung: 'Name des Herstellers', felder: ['hersteller'] },
  { nr: 2, bezeichnung: 'Anschrift des Herstellers', felder: ['hersteller_adresse'] },
  { nr: 4, bezeichnung: 'Gegenstand der Erklärung', felder: ['gegenstand'] },
  { nr: 8, bezeichnung: 'Ort und Datum', felder: ['ort', 'datum'] },
  { nr: 8, bezeichnung: 'Unterzeichner mit Name und Funktion',
    felder: ['unterzeichner_name', 'unterzeichner_funktion'] },
]
const WEGE_MIT_NB = ['B+C', 'H', 'EUCC']

/**
 * #1898: Warum „Erklärung ausstellen“ nicht geht — als Text, nicht als
 * `disabled` allein. Dieselbe Bedingung steuert den Knopf, sein `title` und
 * die Zeile darüber; drei Fassungen davon wären drei Gelegenheiten, sie
 * unterschiedlich falsch zu machen.
 */
const sperrgruende = computed<string[]>(() => {
  const g: string[] = []
  if (!bewertungAbgeschlossen.value) g.push('der Bewertungsweg ist nicht abgeschlossen')
  if (fehlendePflicht.value.length) {
    g.push(`${fehlendePflicht.value.length} Pflichtangabe(n) nach Anhang V fehlen`)
  }
  if (blockierend.value.length) g.push('die Erklärung widerspricht der Akte')
  return g
})
const fehlendePflicht = computed(() => {
  const pflicht = [...PFLICHT]
  if (WEGE_MIT_NB.includes(String(record.value.bewertungsweg || ''))) {
    pflicht.push({ nr: 7, bezeichnung: 'Notifizierte Stelle und Zertifikat',
      felder: ['nb_name', 'nb_kennnummer', 'nb_zertifikat'] })
  }
  return pflicht.filter(p => p.felder.some(f => !istGefuellt(f)))
})

/**
 * Kleine Zeile mit Beschriftung, Eingabe und — wenn es eine Quelle gibt —
 * dem „⚙"-Knopf. Als Render-Funktion, damit die achtzehn Aufrufe im Template
 * nicht achtzehnmal dieselben sechs Zeilen tragen.
 */
const FeldZeile = (p: any, { slots }: any) => {
  const v = p.vorschlaege?.[p.feld]
  const kinder: any[] = [
    h('label', {}, [
      p.label,
      // #1900: Der Knopf steckt in QuellenKnopf — feste Größe (die Zeile sprang
      // beim Tippen, wenn aus „füllen" ein „ersetzen" wurde) und nur noch an
      // einer Stelle gepflegt, statt hier und in aiact/ identisch doppelt.
      v ? h(QuellenKnopf, {
        quelle: v.quelle,
        gefuellt: p.istGefuellt?.(p.feld),
        onFuellen: () => p.fuellen(p.feld, true),
      }) : null,
    ]),
    slots.default?.(),
  ]
  return h('div', { class: 'form-row' }, kinder)
}
const zeile = computed(() => ({
  vorschlaege: feldVorschlaege.value,
  istGefuellt,
  fuellen: feldFuellen,
}))


function normDazu(bezeichnung: string) {
  const zeilen = String(werte.value.normen || '').split('\n')
    .map(z => z.trim()).filter(Boolean)
  if (!zeilen.includes(bezeichnung)) zeilen.push(bezeichnung)
  werte.value.normen = zeilen.join('\n')
}

function unionsrechtDazu(bezeichnung: string) {
  const teile = String(werte.value.weiteres_unionsrecht || '')
    .split(';').map(z => z.trim()).filter(Boolean)
  if (!teile.includes(bezeichnung)) teile.push(bezeichnung)
  werte.value.weiteres_unionsrecht = teile.join('; ')
}

async function stammSpeichern() {
  if (await store.saveHersteller(props.projekt, { ...stamm.value })) {
    await store.fetchVorschlag(props.projekt, release.value)
  }
}

function nutzlast() {
  const n: any = { ...werte.value }
  // Normen gehen als Liste; der Server nimmt beides, aber die Liste ist das,
  // was im Datensatz steht.
  n.normen = String(werte.value.normen || '').split('\n')
    .map((z: string) => z.trim()).filter(Boolean)
  return n
}

async function entwurfSpeichern() {
  if (await store.saveDoc(props.projekt, nutzlast(), release.value)) {
    await store.fetchVorschlag(props.projekt, release.value)
  }
}

async function ausstellen(bestaetigt: string[]) {
  if (await store.issueDoc(props.projekt, nutzlast(), release.value, bestaetigt)) {
    emit('ausgestellt')
    await laden()
  }
}

/** Die KI-Antwort — nur die Felder, die der Server freigegeben hat. */
function uebernehmeAusKi(felder: Record<string, string>) {
  for (const [feld, wert] of Object.entries(felder || {})) {
    if (!String(wert || '').trim()) continue
    werte.value[feld] = wert
  }
}
defineExpose({ uebernehmeAusKi })

function ausRecord() {
  const d = (record.value && record.value.doc) || {}
  const neu: any = {}
  for (const f of FELDER) neu[f] = String(d[f] ?? '')
  if (Array.isArray(d.normen)) neu.normen = d.normen.join('\n')
  if (!neu.produkt_typ) neu.produkt_typ = String(d.modell ?? '')   // Altfeld
  for (const s of SCHALTER) neu[s] = !!d[s]
  werte.value = neu
}

async function laden() {
  await store.fetch(props.projekt, release.value)
  ausRecord()
  await store.fetchVorschlag(props.projekt, release.value)
  stamm.value = { anschrift: '', ort: '', unterzeichner_name: '',
                  unterzeichner_funktion: '',
                  ...(store.vorschlag?.hersteller_stamm || {}) }
}

onMounted(laden)
watch(() => [props.projekt, release.value].join('|'), laden)
</script>

<style scoped>
.form-card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.doc h5 { margin: 14px 0 4px; color: #1565c0; font-size: 13px; }
.doc h5 .small, .small { font-size: 11px; }
.hint { color: #607d8b; font-size: 12px; }
.hint.warn { color: #c62828; }
.hint.warn.gesperrt { font-weight: 600; margin-top: 6px; }
.hint.ok { color: #2e7d32; }
.version-pille { background: #1565c0; color: #fff; border-radius: 10px; padding: 1px 8px; font-size: 11px; margin-left: 8px; vertical-align: middle; }
.version-pille.produkt { background: #607d8b; }
.quellen-leiste { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0 4px; }
.zaehler { background: #1565c0; color: #fff; border-radius: 9px; padding: 0 6px; font-size: 11px; margin-left: 4px; }
.befunde { border: 1px solid #ef9a9a; background: #fff5f5; border-radius: 6px; padding: 8px 10px; margin: 8px 0; }
.befunde h5 { margin: 0 0 4px; color: #c62828; font-size: 13px; }
.befunde ul { margin: 0 0 0 18px; font-size: 12px; }
.befunde li.blockiert { color: #c62828; font-weight: 600; }
.befunde li.bestaetigung { color: #ef6c00; }
.befunde li.hinweis { color: #455a64; }
.befunde .small { font-weight: 400; color: #607d8b; }
.schalter { display: flex; gap: 6px; align-items: flex-start; font-size: 12px; color: #455a64; margin: 6px 0; }
.katalog { display: flex; gap: 6px; flex-wrap: wrap; margin: 4px 0 8px; }
.chip { border: 1px solid #b0bec5; background: #fff; border-radius: 12px; padding: 1px 9px; font-size: 11px; cursor: pointer; color: #37474f; }
.chip:hover { border-color: #1565c0; color: #1565c0; }
.belegt-chip { border-color: #2e7d32; color: #2e7d32; }
.belegt { margin: 4px 0 8px; }
.gruppe h6 { margin: 8px 0 2px; font-size: 12px; color: #37474f; }
.katalog-liste summary, .herkunft summary, .stamm summary { cursor: pointer; font-size: 12px; color: #1565c0; margin: 6px 0; }
.herkunft ul { margin: 0 0 6px 18px; }
.herkunft li.offen, .offen { color: #ef6c00; }
.stamm { border: 1px dashed #b0bec5; border-radius: 6px; padding: 6px 10px; margin: 8px 0; }
.aktionen { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 8px; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
