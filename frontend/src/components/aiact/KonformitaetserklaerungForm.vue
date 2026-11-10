<!--
  EU-Konformitätserklärung nach Art. 47 i.V.m. Anhang V der KI-VO (#1889).

  WARUM DIESE DATEI EXISTIERT
  Die Erklärung gab es bis v8.2.3 **nur als Prompt** (Assistent A8): kein
  Datensatz, keine Felder, kein Ausstellen, kein Archiv — obwohl Art. 47 Abs. 1
  sie für jedes Hochrisiko-KI-System verlangt und Abs. 2 zehn Jahre
  Bereithaltung. Der Anwender bekam einen KI-Entwurf und verarbeitete ihn
  außerhalb weiter; der strukturierte Nachweis fehlte.

  WARUM SIE NICHT DIE CRA-KOMPONENTE IST
  Anhang V der KI-VO ist ein **anderer** Katalog: eigene Nummerierung, eine
  Datenschutz-Erklärung (Nr. 5), die die CRA nicht kennt, und kein
  Artefakt-Gegenstand mit Image und Digest. Eine Komponente für beide hätte
  entweder Felder gezeigt, die es nicht gibt, oder Nummern verwechselt — und
  Nummern landen hier in einem unterschriebenen Dokument (#1763/#1792).

  Geteilt sind die **Bausteine**, nicht die Maske: `QuellenLeiste`,
  `BefundListe` und `useFormularVorschlag` (#1893). Welche Felder die KI setzen
  darf, entscheidet der Server (`ai_act/doc_vorschlag.KI_FELDER`).
-->
<template>
  <section class="card doc">
    <h4>
      {{ $t('aiact.konformitaetserklaerungForm.eUKonformitatserklarungArtAnhangV') }}
      <span v-if="docVersion" class="pille">{{ $t('aiact.konformitaetserklaerungForm.fassungV0', { v0: docVersion }) }}</span>
    </h4>
    <p class="hint">
      {{ $t('aiact.konformitaetserklaerungForm.ausDiesenAngabenEntstehtDasDokumentD') }} <strong>{{ $t('aiact.konformitaetserklaerungForm.zehnJahre') }}</strong> {{ $t('aiact.konformitaetserklaerungForm.nachDemInverkehrbringenFurDieZustand') }}
    </p>
    <p v-if="!docAllowed" class="hint warn">
      {{ $t('aiact.konformitaetserklaerungForm.erstAusstellbarWennDieKonformitatsbe') }}
    </p>
    <!-- #1894: Die Nummerierung von Anhang V ist gegen zwei unabhängige
         Wiedergaben geprüft; maßgeblich bleibt das Amtsblatt. Wer eine Angabe
         nachlesen will, soll sehen, ob der Text zur Hand ist. -->
    <p v-if="!verordnungLiegtVor" class="hint small">
      {{ $t('aiact.konformitaetserklaerungForm.iDieAmtlicheFassungDerVerordnungEULi') }}
    </p>

    <FehlerHinweis v-if="fehler" :text="fehler" @close="fehler = ''" />

    <QuellenLeiste :anzahl="anzahlFuellbar" @alle="alleFuellen">
      <template #eigene>
        <button class="btn-secondary" @click="emit('assistent')">{{ $t('aiact.konformitaetserklaerungForm.assistent') }}</button>
      </template>
    </QuellenLeiste>
    <BefundListe :befunde="befunde" :titel="$t('aiact.konformitaetserklaerungForm.vorDemAusstellenZuKlaren')" />

    <h5>{{ $t('aiact.konformitaetserklaerungForm.nrBezeichnungDesKISystems') }}</h5>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.nameDesKISystems') }}<QuelleKnopf feld="system_name" v-bind="knopf" /></label>
      <input v-model="werte.system_name" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.typ') }}<QuelleKnopf feld="system_typ" v-bind="knopf" /></label>
      <input v-model="werte.system_typ" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.eindeutigeKennungZurRuckverfolgbarke') }}
        <QuelleKnopf feld="system_kennung" v-bind="knopf" /></label>
      <input v-model="werte.system_kennung"
             :placeholder="$t('aiact.konformitaetserklaerungForm.zBBezeichnungMitFassungOderSeriennum')" />
    </div>

    <h5>{{ $t('aiact.konformitaetserklaerungForm.nrAnbieter') }}</h5>
    <div class="form-row">
      <label>{{ $t('common.name') }}<QuelleKnopf feld="anbieter" v-bind="knopf" /></label>
      <input v-model="werte.anbieter" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.anschrift') }}<QuelleKnopf feld="anbieter_adresse" v-bind="knopf" /></label>
      <textarea v-model="werte.anbieter_adresse" rows="2"></textarea>
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.eUBevollmachtigterFallsVorhanden') }}
        <QuelleKnopf feld="bevollmaechtigter" v-bind="knopf" /></label>
      <input v-model="werte.bevollmaechtigter" />
    </div>
    <p v-if="firma" class="hint small">
      {{ $t('aiact.konformitaetserklaerungForm.anschriftUndUnterzeichnerKommenAusDe', { v0: firma }) }}
    </p>

    <h5>{{ $t('aiact.konformitaetserklaerungForm.nrWeiteresUnionsrecht') }}</h5>
    <p class="hint small">
      {{ $t('aiact.konformitaetserklaerungForm.nurRechtsakteNennenDieEbenfallsEineE') }}
    </p>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.weitereRechtsakte') }}</label>
      <input v-model="werte.weiteres_unionsrecht" />
    </div>
    <div v-if="unionsrecht.length" class="katalog">
      <button v-for="e in unionsrecht" :key="e.id" class="chip" :title="e.zweck"
              @click="dazu('weiteres_unionsrecht', e.bezeichnung, '; ')">
        + {{ e.bezeichnung }}
      </button>
    </div>

    <h5>{{ $t('aiact.konformitaetserklaerungForm.nrDatenschutzrecht') }}</h5>
    <!-- Der Schalter ist der Punkt: „nicht entschieden" und „nein" sind im
         Datensatz nicht unterscheidbar (#1805). Gedruckt wird die Erklärung
         nur bei „ja" — eine Aussage über etwas, das nicht stattfindet, wäre
         eine Aussage ohne Gegenstand. -->
    <label class="schalter">
      <input type="checkbox" v-model="werte.personenbezogene_daten" />
      {{ $t('aiact.konformitaetserklaerungForm.dasKISystemVerarbeitet') }} <strong>{{ $t('aiact.konformitaetserklaerungForm.personenbezogeneDaten') }}</strong> {{ $t('aiact.konformitaetserklaerungForm.dannErklartDasDokumentDieEinhaltungD') }}
    </label>

    <h5>{{ $t('aiact.konformitaetserklaerungForm.nrAngewandteNormenUndSpezifikationen') }}</h5>
    <p class="hint">{{ harmonisiertHinweis }}</p>
    <label class="schalter">
      <input type="checkbox" v-model="werte.keine_harmonisierten" />
      {{ $t('aiact.konformitaetserklaerungForm.esWurden') }} <strong>{{ $t('aiact.konformitaetserklaerungForm.keineHarmonisiertenNormen') }}</strong> {{ $t('aiact.konformitaetserklaerungForm.nachArtAngewandtAusdrucklicheFestste') }}
    </label>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.angewandteSpezifikationenEineJeZeile') }}</label>
      <textarea v-model="werte.normen" rows="3"></textarea>
    </div>
    <details v-if="normenGruppen.length" class="katalog-liste">
      <summary>{{ $t('aiact.konformitaetserklaerungForm.katalogOffnenStandV0', { v0: katalogStand }) }}</summary>
      <div v-for="g in normenGruppen" :key="g.id" class="gruppe">
        <h6>{{ g.titel }}</h6>
        <p class="hint small">{{ g.hinweis }}</p>
        <div v-if="g.normen.length" class="katalog">
          <button v-for="n in g.normen" :key="n.id" class="chip" :title="n.zweck"
                  @click="dazu('normen', n.bezeichnung, '\n')">
            + {{ n.bezeichnung }}
          </button>
        </div>
        <p v-else class="hint small">{{ $t('aiact.konformitaetserklaerungForm.keineEintrage') }}</p>
      </div>
    </details>

    <h5>{{ $t('aiact.konformitaetserklaerungForm.nrNotifizierteStelleUndBescheinigung') }}
      <span class="small">{{ $t('aiact.konformitaetserklaerungForm.soweitZutreffend') }}</span></h5>
    <p class="hint small">
      {{ $t('aiact.konformitaetserklaerungForm.pflichtBeimVerfahrenNachAnhangVIIBei') }}
    </p>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.nameDerStelle') }}<QuelleKnopf feld="nb_name" v-bind="knopf" /></label>
      <input v-model="werte.nb_name" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.kennnummer') }}<QuelleKnopf feld="nb_kennnummer" v-bind="knopf" /></label>
      <input v-model="werte.nb_kennnummer" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.durchgefuhrtesVerfahren') }}
        <QuelleKnopf feld="nb_verfahren" v-bind="knopf" /></label>
      <input v-model="werte.nb_verfahren" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.bescheinigungNummerBezeichnung') }}</label>
      <input v-model="werte.nb_bescheinigung" />
    </div>

    <h5>{{ $t('aiact.konformitaetserklaerungForm.nrZusatzangabenOrtUndDatumUnterzeich') }}</h5>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.zusatzangaben') }}<QuelleKnopf feld="zusatzangaben" v-bind="knopf" /></label>
      <textarea v-model="werte.zusatzangaben" rows="2"
                :disabled="werte.zusatzangaben_keine"></textarea>
    </div>
    <label class="schalter">
      <input type="checkbox" v-model="werte.zusatzangaben_keine" />
      {{ $t('aiact.konformitaetserklaerungForm.esSind') }} <strong>{{ $t('aiact.konformitaetserklaerungForm.keineWeiterenAngaben') }}</strong> {{ $t('aiact.konformitaetserklaerungForm.aufzunehmen') }}
    </label>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.ort') }}<QuelleKnopf feld="ort" v-bind="knopf" /></label>
      <input v-model="werte.ort" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.datum') }}<QuelleKnopf feld="datum" v-bind="knopf" /></label>
      <input type="date" v-model="werte.datum" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.unterzeichnerName') }}
        <QuelleKnopf feld="unterzeichner_name" v-bind="knopf" /></label>
      <input v-model="werte.unterzeichner_name" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.unterzeichnerFunktion') }}
        <QuelleKnopf feld="unterzeichner_funktion" v-bind="knopf" /></label>
      <input v-model="werte.unterzeichner_funktion" />
    </div>
    <div class="form-row">
      <label>{{ $t('aiact.konformitaetserklaerungForm.unterzeichnetFurAnbieter') }}
        <QuelleKnopf feld="unterzeichner_fuer" v-bind="knopf" /></label>
      <input v-model="werte.unterzeichner_fuer" />
    </div>

    <!-- #1898: Hier stand „es entsteht nur ein als ENTWURF gekennzeichnetes
         Dokument". Den Entwurfsvermerk setzt der Download, nicht das
         Ausstellen — ausstellen geht mit Lücken gar nicht. Der Satz beschrieb
         also eine andere Handlung als der Knopf darunter. -->
    <p v-if="fehlend.length" class="hint warn">
      {{ $t('aiact.konformitaetserklaerungForm.pflichtangabenFehlen') }} <strong>{{ $t('aiact.konformitaetserklaerungForm.ausstellenIstDamitNichtMoglich') }}</strong>
      (Art. 47 i.V.m. Anhang V der Verordnung (EU) 2024/1689):
      {{ fehlend.map((f: any) => `Nr. ${f.nr}: ${f.bezeichnung}`).join('; ') }}.
      Mit „Entwurf speichern“ geht nichts verloren; der Download liefert
      solange ein als ENTWURF gekennzeichnetes Dokument.
    </p>
    <p v-if="blockierend.length" class="hint warn">
      {{ $t('aiact.konformitaetserklaerungForm.dieErklarungTragtEineAngabeDieDerAkt') }}
    </p>
    <!-- #1898: Der Grund gehört dorthin, wo der Knopf ist — der Hinweis zur
         Freigabe steht am Anfang dieser Maske. -->
    <p v-if="sperrgruende.length" class="hint warn gesperrt">
      {{ $t('aiact.konformitaetserklaerungForm.erklarungAusstellenIstGesperrtV0', { v0: sperrgruende.join(' · ') }) }}
    </p>
    <div class="aktionen">
      <button class="btn-secondary" @click="entwurfSpeichern">{{ $t('aiact.konformitaetserklaerungForm.entwurfSpeichern') }}</button>
      <button class="btn-primary" :disabled="sperrgruende.length > 0"
              :title="sperrgruende.length
                ? $t('aiact.konformitaetserklaerungForm.gesperrt') + sperrgruende.join(' · ')
                : $t('aiact.konformitaetserklaerungForm.dieErklarungAusstellenUndAlsFassungF')"
              @click="ausstellen([])">
        {{ $t('aiact.konformitaetserklaerungForm.erklarungAusstellen') }}
      </button>
      <button v-if="bestaetigungNoetig.length" class="btn-secondary"
              @click="ausstellen(bestaetigungNoetig)">
        {{ $t('aiact.konformitaetserklaerungForm.trotzdemAusstellenIchVerantworteDas') }}
      </button>
      <button class="btn-secondary" @click="herunterladen('docx')">{{ $t('aiact.konformitaetserklaerungForm.dOCX') }}</button>
      <button class="btn-secondary" @click="herunterladen('pdf')">{{ $t('common.pDF') }}</button>
    </div>
    <p v-if="docAusgestellt" class="hint ok">
      {{ $t('aiact.konformitaetserklaerungForm.fassungV0AusgestelltAmV1', { v0: docVersion, v1: ausgestelltAm.slice(0, 10) }) }}
    </p>

    <!--
      #2038: Drei Zustände statt zwei. Dies ist der Träger der zehnjährigen
      Bereithaltung nach Art. 47 Abs. 2 KI-VO — wer prüfen will, ob eine
      Erklärung je ausgestellt wurde, darf bei einem Netzaussetzer nicht
      „gibt es nicht" angezeigt bekommen.
    -->
    <details class="archiv" :open="archivFehler">
      <summary v-if="archivFehler">
        ⚠️ {{ $t('aiact.konformitaetserklaerungForm.ausgestellteFassungen') }}
      </summary>
      <summary v-else-if="archiv.length">
        {{ $t('aiact.konformitaetserklaerungForm.ausgestellteFassungenV0', { v0: archiv.length }) }}
      </summary>
      <summary v-else>{{ $t('aiact.konformitaetserklaerungForm.ausgestellteFassungen') }}</summary>
      <p v-if="archivFehler" class="hint warn">
        {{ $t('aiact.konformitaetserklaerungForm.archivNichtAbrufbar') }}
      </p>
      <p v-else-if="!archiv.length" class="hint muted">
        {{ $t('aiact.konformitaetserklaerungForm.archivLeer') }}
      </p>
      <ul v-else>
        <li v-for="a in archiv" :key="a.id">
          {{ $t('aiact.konformitaetserklaerungForm.fassungV0V1V2SHAV3', { v0: a.doc_version, v1: (a.ausgestellt_am || '').slice(0, 10), v2: a.ausgestellt_von || '—', v3: (a.sha256 || '').slice(0, 12) }) }}
        </li>
      </ul>
    </details>
  </section>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from 'vue'
import apiClient from '../../api/client'
import FehlerHinweis from '../shared/FehlerHinweis.vue'
import QuellenLeiste from '../shared/QuellenLeiste.vue'
import BefundListe from '../shared/BefundListe.vue'
import { blockierende, useFormularVorschlag } from '../../composables/useFormularVorschlag'
import QuellenKnopf from '../shared/QuellenKnopf.vue'
import { t } from '../../i18n'

const props = defineProps<{ projekt: string }>()
// #1889: Der A8-Wizard erreicht die Felder jetzt. Übernommen wird nur, was
// `ai_act/doc_vorschlag.KI_FELDER` freigibt — die Grenze zieht der Server.
const emit = defineEmits<{
  (e: 'ausgestellt'): void
  (e: 'assistent'): void
}>()

const BASE = '/aiact-conformity'
const FELDER = [
  'system_name', 'system_typ', 'system_kennung',
  'anbieter', 'anbieter_adresse', 'bevollmaechtigter',
  'weiteres_unionsrecht', 'normen',
  'nb_name', 'nb_kennnummer', 'nb_verfahren', 'nb_bescheinigung',
  'zusatzangaben', 'ort', 'datum',
  'unterzeichner_name', 'unterzeichner_funktion', 'unterzeichner_fuer',
] as const
const SCHALTER = ['keine_harmonisierten', 'zusatzangaben_keine',
                  'personenbezogene_daten'] as const

const werte = ref<any>({
  ...Object.fromEntries(FELDER.map(f => [f, ''])),
  ...Object.fromEntries(SCHALTER.map(f => [f, false])),
})
const vorschlaege = ref<Record<string, any>>({})
const befunde = ref<any[]>([])
const fehlend = ref<any[]>([])
const bestaetigungNoetig = ref<string[]>([])
const archiv = ref<any[]>([])
/** #2038: dritter Zustand — der Abruf ist gescheitert, nicht die Liste leer. */
const archivFehler = ref(false)
const fehler = ref('')
const docAllowed = ref(false)
const docVersion = ref(0)
const docAusgestellt = ref(false)
const ausgestelltAm = ref('')
const katalog = ref<any>({})
const verordnungLiegtVor = ref(true)   // #1894 — bis die Antwort da ist kein Hinweis

const blockierend = computed(() => blockierende(befunde.value))

/**
 * #1898: Warum „Erklärung ausstellen“ nicht geht — als Text. Dieselbe
 * Bedingung steuert Knopf, `title` und die Zeile darüber.
 */
const sperrgruende = computed<string[]>(() => {
  const g: string[] = []
  if (!docAllowed.value) g.push(t('aiact.konformitaetserklaerungForm.dieKonformitatsbewertungIstNichtAbge'))
  if (fehlend.value.length) {
    g.push(`${fehlend.value.length} Pflichtangabe(n) nach Anhang V fehlen`)
  }
  if (blockierend.value.length) g.push(t('aiact.konformitaetserklaerungForm.dieErklarungWidersprichtDerAkte'))
  return g
})
const firma = computed(() => String(katalog.value.firma || ''))
const normenGruppen = computed<any[]>(() => katalog.value.katalog?.gruppen || [])
const katalogStand = computed(() => String(katalog.value.katalog?.stand || ''))
const unionsrecht = computed<any[]>(() => katalog.value.unionsrecht?.eintraege || [])
const harmonisiertHinweis = computed(() =>
  String(normenGruppen.value.find((g: any) => g.id === 'harmonisiert')?.hinweis
    || t('aiact.konformitaetserklaerungForm.zurKIVerordnungIstBislangKeineHarmon')
       + t('aiact.konformitaetserklaerungForm.veroffentlichtArt')))

const { anzahlFuellbar, feldFuellen, alleFuellen, istGefuellt } =
  useFormularVorschlag(werte, vorschlaege as any)

/** Kleiner „⚙"-Knopf am Feld — nur, wenn es dafür eine Quelle gibt.
 *  #1900: Knopf und Styling liegen in `shared/QuellenKnopf.vue`; diese Hülle
 *  bleibt, weil sie die Vorschlags-Auflösung je Feld kapselt. */
const QuelleKnopf = (p: any) => {
  const v = p.vorschlaege?.[p.feld]
  if (!v) return null
  return h(QuellenKnopf, {
    quelle: v.quelle,
    gefuellt: p.gefuellt?.(p.feld),
    onFuellen: () => p.fuellen(p.feld, true),
  })
}
const knopf = computed(() => ({
  vorschlaege: vorschlaege.value,
  gefuellt: (f: string) => istGefuellt(werte.value[f]),
  fuellen: feldFuellen,
}))

function dazu(feld: string, text: string, trenner: string) {
  const teile = String(werte.value[feld] || '').split(trenner)
    .map(z => z.trim()).filter(Boolean)
  if (!teile.includes(text)) teile.push(text)
  werte.value[feld] = teile.join(trenner)
}

function nutzlast() {
  const n: any = { ...werte.value }
  n.normen = String(werte.value.normen || '').split('\n')
    .map((z: string) => z.trim()).filter(Boolean)
  return n
}

function uebernehmen(d: any) {
  const doc = d?.doc || {}
  const neu: any = {}
  for (const f of FELDER) neu[f] = String(doc[f] ?? '')
  if (Array.isArray(doc.normen)) neu.normen = doc.normen.join('\n')
  for (const s of SCHALTER) neu[s] = !!doc[s]
  werte.value = neu
  fehlend.value = d?.fehlend || []
  befunde.value = d?.befunde || []
  docAllowed.value = !!d?.doc_allowed
  docVersion.value = Number(d?.doc_version || 0)
  docAusgestellt.value = !!d?.doc_ausgestellt
  ausgestelltAm.value = String(d?.ausgestellt_am || '')
  verordnungLiegtVor.value = d?.verordnung_liegt_vor !== false
}

async function laden() {
  if (!props.projekt) return
  fehler.value = ''
  const p = encodeURIComponent(props.projekt)
  try {
    uebernehmen((await apiClient.get(`${BASE}/projekte/${p}/doc`)).data)
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || t('aiact.konformitaetserklaerungForm.erklarungKonnteNichtGeladenWerden')
  }
  try {
    const { data } = await apiClient.get(`${BASE}/projekte/${p}/doc/vorschlag`)
    katalog.value = data || {}
    vorschlaege.value = data?.felder || {}
  } catch { /* ohne Vorschläge bleibt das Formular bedienbar */ }
  // #2038: wie im CRA-Register — `catch` und `?.archiv || []` verschluckten
  // beide denselben Fehler und machten daraus „noch nie ausgestellt".
  try {
    const eintraege = (await apiClient.get(`${BASE}/projekte/${p}/doc/archiv`)).data?.archiv
    if (!Array.isArray(eintraege)) throw new Error('Antwort ohne archiv')
    archiv.value = eintraege
    archivFehler.value = false
  } catch {
    archiv.value = []
    archivFehler.value = true
  }
}

async function entwurfSpeichern() {
  fehler.value = ''
  try {
    await apiClient.put(
      `${BASE}/projekte/${encodeURIComponent(props.projekt)}/doc`,
      { doc: nutzlast() })
    await laden()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || t('aiact.konformitaetserklaerungForm.entwurfKonnteNichtGespeichertWerden')
  }
}

async function ausstellen(bestaetigt: string[]) {
  fehler.value = ''
  bestaetigungNoetig.value = []
  try {
    await apiClient.post(
      `${BASE}/projekte/${encodeURIComponent(props.projekt)}/doc`,
      { doc: nutzlast(), bestaetigt })
    emit('ausgestellt')
    await laden()
  } catch (e: any) {
    const d = e?.response?.data || {}
    // #1885: 428 heißt „ein Mensch muss das verantworten", 409 „nachweislich
    // falsch". Die Befunde gehören in die Maske, nicht in eine Fehlerzeile.
    if (Array.isArray(d.befunde) && d.befunde.length) befunde.value = d.befunde
    if (Array.isArray(d.fehlend) && d.fehlend.length) fehlend.value = d.fehlend
    if (e?.response?.status === 428) bestaetigungNoetig.value = d.bestaetigung || []
    fehler.value = d.error || t('aiact.konformitaetserklaerungForm.erklarungKonnteNichtAusgestelltWerde')
  }
}

async function herunterladen(fmt: 'docx' | 'pdf') {
  try {
    const res = await apiClient.get(
      `${BASE}/projekte/${encodeURIComponent(props.projekt)}/doc/export`,
      { params: { format: fmt }, responseType: 'blob' })
    const url = URL.createObjectURL(res.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `EU-Konformitaetserklaerung_${props.projekt}.${fmt}`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || t('common.downloadFehlgeschlagen')
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

onMounted(laden)
watch(() => props.projekt, laden)
</script>

<style scoped>
.card { background: #f5f8fc; border: 1px solid #cfd8e3; border-radius: 8px; padding: 16px; margin: 12px 0; }
.form-row { display: flex; flex-direction: column; margin-bottom: 8px; }
.form-row label { font-size: 12px; color: #455a64; margin-bottom: 2px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.doc h5 { margin: 14px 0 4px; color: #1565c0; font-size: 13px; }
.doc h5 .small, .small { font-size: 11px; }
.hint { color: #607d8b; font-size: 12px; }
.hint.warn { color: #c62828; }
.hint.warn.gesperrt { font-weight: 600; margin-top: 6px; }
.hint.ok { color: #2e7d32; }
.pille { background: #1565c0; color: #fff; border-radius: 10px; padding: 1px 8px; font-size: 11px; margin-left: 8px; vertical-align: middle; }
.schalter { display: flex; gap: 6px; align-items: flex-start; font-size: 12px; color: #455a64; margin: 6px 0; }
.katalog { display: flex; gap: 6px; flex-wrap: wrap; margin: 4px 0 8px; }
.chip { border: 1px solid #b0bec5; background: #fff; border-radius: 12px; padding: 1px 9px; font-size: 11px; cursor: pointer; color: #37474f; }
.chip:hover { border-color: #1565c0; color: #1565c0; }
.gruppe h6 { margin: 8px 0 2px; font-size: 12px; color: #37474f; }
.katalog-liste summary, .archiv summary { cursor: pointer; font-size: 12px; color: #1565c0; margin: 6px 0; }
.archiv ul { margin: 4px 0 0 18px; font-size: 12px; }
.aktionen { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 8px; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
