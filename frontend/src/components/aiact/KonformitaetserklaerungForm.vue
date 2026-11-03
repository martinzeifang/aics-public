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
      EU-Konformitätserklärung (Art. 47 · Anhang V)
      <span v-if="docVersion" class="pille">Fassung {{ docVersion }}</span>
    </h4>
    <p class="hint">
      Aus diesen Angaben entsteht das Dokument, das der Anbieter unterschreibt.
      Es ist <strong>zehn Jahre</strong> nach dem Inverkehrbringen für die
      zuständigen Behörden bereitzuhalten (Art. 47 Abs. 2).
    </p>
    <p v-if="!docAllowed" class="hint warn">
      🔒 Erst ausstellbar, wenn die Konformitätsbewertung abgeschlossen ist
      (Art. 43).
    </p>
    <!-- #1894: Die Nummerierung von Anhang V ist gegen zwei unabhängige
         Wiedergaben geprüft; maßgeblich bleibt das Amtsblatt. Wer eine Angabe
         nachlesen will, soll sehen, ob der Text zur Hand ist. -->
    <p v-if="!verordnungLiegtVor" class="hint small">
      ℹ Die amtliche Fassung der Verordnung (EU) 2024/1689 liegt nicht in
      dieser Installation. Administration → Einstellungen → Verordnungstexte
      holt sie; bis dahin sind die Fundstellen unten nicht am Original
      nachlesbar.
    </p>

    <FehlerHinweis v-if="fehler" :text="fehler" @close="fehler = ''" />

    <QuellenLeiste :anzahl="anzahlFuellbar" @alle="alleFuellen">
      <template #eigene>
        <button class="btn-secondary" @click="emit('assistent')">🤖 Assistent</button>
      </template>
    </QuellenLeiste>
    <BefundListe :befunde="befunde" titel="Vor dem Ausstellen zu klären" />

    <h5>Nr. 1 — Bezeichnung des KI-Systems</h5>
    <div class="form-row">
      <label>Name des KI-Systems *<QuelleKnopf feld="system_name" v-bind="knopf" /></label>
      <input v-model="werte.system_name" />
    </div>
    <div class="form-row">
      <label>Typ *<QuelleKnopf feld="system_typ" v-bind="knopf" /></label>
      <input v-model="werte.system_typ" />
    </div>
    <div class="form-row">
      <label>Eindeutige Kennung zur Rückverfolgbarkeit *
        <QuelleKnopf feld="system_kennung" v-bind="knopf" /></label>
      <input v-model="werte.system_kennung"
             placeholder="z. B. Bezeichnung mit Fassung oder Seriennummer" />
    </div>

    <h5>Nr. 2 — Anbieter</h5>
    <div class="form-row">
      <label>Name *<QuelleKnopf feld="anbieter" v-bind="knopf" /></label>
      <input v-model="werte.anbieter" />
    </div>
    <div class="form-row">
      <label>Anschrift *<QuelleKnopf feld="anbieter_adresse" v-bind="knopf" /></label>
      <textarea v-model="werte.anbieter_adresse" rows="2"></textarea>
    </div>
    <div class="form-row">
      <label>EU-Bevollmächtigter (falls vorhanden)
        <QuelleKnopf feld="bevollmaechtigter" v-bind="knopf" /></label>
      <input v-model="werte.bevollmaechtigter" />
    </div>
    <p v-if="firma" class="hint small">
      Anschrift und Unterzeichner kommen aus den Stammdaten des Mandanten
      ({{ firma }}) — dort einmal erfasst, gelten sie für alle KI-Systeme
      dieses Anbieters.
    </p>

    <h5>Nr. 4 — Weiteres Unionsrecht</h5>
    <p class="hint small">
      Nur Rechtsakte nennen, die ebenfalls eine EU-Konformitätserklärung
      vorsehen und für dieses System gelten. Ob ein Rechtsakt greift, hängt vom
      System ab und wird nicht hergeleitet.
    </p>
    <div class="form-row">
      <label>Weitere Rechtsakte</label>
      <input v-model="werte.weiteres_unionsrecht" />
    </div>
    <div v-if="unionsrecht.length" class="katalog">
      <button v-for="e in unionsrecht" :key="e.id" class="chip" :title="e.zweck"
              @click="dazu('weiteres_unionsrecht', e.bezeichnung, '; ')">
        + {{ e.bezeichnung }}
      </button>
    </div>

    <h5>Nr. 5 — Datenschutzrecht</h5>
    <!-- Der Schalter ist der Punkt: „nicht entschieden" und „nein" sind im
         Datensatz nicht unterscheidbar (#1805). Gedruckt wird die Erklärung
         nur bei „ja" — eine Aussage über etwas, das nicht stattfindet, wäre
         eine Aussage ohne Gegenstand. -->
    <label class="schalter">
      <input type="checkbox" v-model="werte.personenbezogene_daten" />
      Das KI-System verarbeitet <strong>personenbezogene Daten</strong> —
      dann erklärt das Dokument die Einhaltung der Verordnung (EU) 2016/679,
      der Verordnung (EU) 2018/1725 und der Richtlinie (EU) 2016/680.
    </label>

    <h5>Nr. 6 — Angewandte Normen und Spezifikationen</h5>
    <p class="hint">{{ harmonisiertHinweis }}</p>
    <label class="schalter">
      <input type="checkbox" v-model="werte.keine_harmonisierten" />
      Es wurden <strong>keine harmonisierten Normen</strong> nach Art. 40
      angewandt (ausdrückliche Feststellung für Nr. 6)
    </label>
    <div class="form-row">
      <label>Angewandte Spezifikationen — eine je Zeile</label>
      <textarea v-model="werte.normen" rows="3"></textarea>
    </div>
    <details v-if="normenGruppen.length" class="katalog-liste">
      <summary>Katalog öffnen (Stand {{ katalogStand }})</summary>
      <div v-for="g in normenGruppen" :key="g.id" class="gruppe">
        <h6>{{ g.titel }}</h6>
        <p class="hint small">{{ g.hinweis }}</p>
        <div v-if="g.normen.length" class="katalog">
          <button v-for="n in g.normen" :key="n.id" class="chip" :title="n.zweck"
                  @click="dazu('normen', n.bezeichnung, '\n')">
            + {{ n.bezeichnung }}
          </button>
        </div>
        <p v-else class="hint small">— keine Einträge —</p>
      </div>
    </details>

    <h5>Nr. 7 — Notifizierte Stelle und Bescheinigung
      <span class="small">(soweit zutreffend)</span></h5>
    <p class="hint small">
      Pflicht beim Verfahren nach Anhang VII. Bei interner Kontrolle nach
      Anhang VI bleibt der Block leer.
    </p>
    <div class="form-row">
      <label>Name der Stelle<QuelleKnopf feld="nb_name" v-bind="knopf" /></label>
      <input v-model="werte.nb_name" />
    </div>
    <div class="form-row">
      <label>Kennnummer<QuelleKnopf feld="nb_kennnummer" v-bind="knopf" /></label>
      <input v-model="werte.nb_kennnummer" />
    </div>
    <div class="form-row">
      <label>Durchgeführtes Verfahren
        <QuelleKnopf feld="nb_verfahren" v-bind="knopf" /></label>
      <input v-model="werte.nb_verfahren" />
    </div>
    <div class="form-row">
      <label>Bescheinigung (Nummer / Bezeichnung)</label>
      <input v-model="werte.nb_bescheinigung" />
    </div>

    <h5>Nr. 8 — Zusatzangaben, Ort und Datum, Unterzeichner</h5>
    <div class="form-row">
      <label>Zusatzangaben<QuelleKnopf feld="zusatzangaben" v-bind="knopf" /></label>
      <textarea v-model="werte.zusatzangaben" rows="2"
                :disabled="werte.zusatzangaben_keine"></textarea>
    </div>
    <label class="schalter">
      <input type="checkbox" v-model="werte.zusatzangaben_keine" />
      Es sind <strong>keine weiteren Angaben</strong> aufzunehmen
    </label>
    <div class="form-row">
      <label>Ort *<QuelleKnopf feld="ort" v-bind="knopf" /></label>
      <input v-model="werte.ort" />
    </div>
    <div class="form-row">
      <label>Datum *<QuelleKnopf feld="datum" v-bind="knopf" /></label>
      <input type="date" v-model="werte.datum" />
    </div>
    <div class="form-row">
      <label>Unterzeichner — Name *
        <QuelleKnopf feld="unterzeichner_name" v-bind="knopf" /></label>
      <input v-model="werte.unterzeichner_name" />
    </div>
    <div class="form-row">
      <label>Unterzeichner — Funktion *
        <QuelleKnopf feld="unterzeichner_funktion" v-bind="knopf" /></label>
      <input v-model="werte.unterzeichner_funktion" />
    </div>
    <div class="form-row">
      <label>Unterzeichnet für (Anbieter) *
        <QuelleKnopf feld="unterzeichner_fuer" v-bind="knopf" /></label>
      <input v-model="werte.unterzeichner_fuer" />
    </div>

    <!-- #1898: Hier stand „es entsteht nur ein als ENTWURF gekennzeichnetes
         Dokument". Den Entwurfsvermerk setzt der Download, nicht das
         Ausstellen — ausstellen geht mit Lücken gar nicht. Der Satz beschrieb
         also eine andere Handlung als der Knopf darunter. -->
    <p v-if="fehlend.length" class="hint warn">
      ⚠️ Pflichtangaben fehlen — <strong>ausstellen ist damit nicht möglich</strong>
      (Art. 47 i.V.m. Anhang V der Verordnung (EU) 2024/1689):
      {{ fehlend.map((f: any) => `Nr. ${f.nr}: ${f.bezeichnung}`).join('; ') }}.
      Mit „Entwurf speichern“ geht nichts verloren; der Download liefert
      solange ein als ENTWURF gekennzeichnetes Dokument.
    </p>
    <p v-if="blockierend.length" class="hint warn">
      ⛔ Die Erklärung trägt eine Angabe, die der Akte widerspricht — siehe oben.
    </p>
    <!-- #1898: Der Grund gehört dorthin, wo der Knopf ist — der Hinweis zur
         Freigabe steht am Anfang dieser Maske. -->
    <p v-if="sperrgruende.length" class="hint warn gesperrt">
      ⛔ „Erklärung ausstellen“ ist gesperrt: {{ sperrgruende.join(' · ') }}
    </p>
    <div class="aktionen">
      <button class="btn-secondary" @click="entwurfSpeichern">Entwurf speichern</button>
      <button class="btn-primary" :disabled="sperrgruende.length > 0"
              :title="sperrgruende.length
                ? 'Gesperrt: ' + sperrgruende.join(' · ')
                : 'Die Erklärung ausstellen und als Fassung festschreiben'"
              @click="ausstellen([])">
        Erklärung ausstellen
      </button>
      <button v-if="bestaetigungNoetig.length" class="btn-secondary"
              @click="ausstellen(bestaetigungNoetig)">
        Trotzdem ausstellen — ich verantworte das
      </button>
      <button class="btn-secondary" @click="herunterladen('docx')">⬇️ DOCX</button>
      <button class="btn-secondary" @click="herunterladen('pdf')">⬇️ PDF</button>
    </div>
    <p v-if="docAusgestellt" class="hint ok">
      ✓ Fassung {{ docVersion }} ausgestellt am {{ ausgestelltAm.slice(0, 10) }}
    </p>

    <details v-if="archiv.length" class="archiv">
      <summary>Ausgestellte Fassungen ({{ archiv.length }})</summary>
      <ul>
        <li v-for="a in archiv" :key="a.id">
          Fassung {{ a.doc_version }} · {{ (a.ausgestellt_am || '').slice(0, 10) }}
          · {{ a.ausgestellt_von || '—' }}
          · SHA-256 {{ (a.sha256 || '').slice(0, 12) }}…
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
  if (!docAllowed.value) g.push('die Konformitätsbewertung ist nicht abgeschlossen')
  if (fehlend.value.length) {
    g.push(`${fehlend.value.length} Pflichtangabe(n) nach Anhang V fehlen`)
  }
  if (blockierend.value.length) g.push('die Erklärung widerspricht der Akte')
  return g
})
const firma = computed(() => String(katalog.value.firma || ''))
const normenGruppen = computed<any[]>(() => katalog.value.katalog?.gruppen || [])
const katalogStand = computed(() => String(katalog.value.katalog?.stand || ''))
const unionsrecht = computed<any[]>(() => katalog.value.unionsrecht?.eintraege || [])
const harmonisiertHinweis = computed(() =>
  String(normenGruppen.value.find((g: any) => g.id === 'harmonisiert')?.hinweis
    || 'Zur KI-Verordnung ist bislang keine harmonisierte Norm im Amtsblatt '
       + 'veröffentlicht (Art. 40).'))

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
    fehler.value = e?.response?.data?.error || 'Erklärung konnte nicht geladen werden'
  }
  try {
    const { data } = await apiClient.get(`${BASE}/projekte/${p}/doc/vorschlag`)
    katalog.value = data || {}
    vorschlaege.value = data?.felder || {}
  } catch { /* ohne Vorschläge bleibt das Formular bedienbar */ }
  try {
    archiv.value = (await apiClient.get(`${BASE}/projekte/${p}/doc/archiv`))
      .data?.archiv || []
  } catch { archiv.value = [] }
}

async function entwurfSpeichern() {
  fehler.value = ''
  try {
    await apiClient.put(
      `${BASE}/projekte/${encodeURIComponent(props.projekt)}/doc`,
      { doc: nutzlast() })
    await laden()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Entwurf konnte nicht gespeichert werden'
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
    fehler.value = d.error || 'Erklärung konnte nicht ausgestellt werden'
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
    fehler.value = e?.response?.data?.error || 'Download fehlgeschlagen'
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
