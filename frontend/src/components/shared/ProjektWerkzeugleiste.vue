<!--
  ProjektWerkzeugleiste (#1851) — die sieben projektweiten Handlungen, in
  allen sechs Modulen gleich benannt, gleich angeordnet, gleich bedient.

  DER BEFUND
  Dieselbe Handlung trug drei Namen, und zwei Handlungen fehlten in fünf von
  sechs Modulen. Dazu lagen die Knöpfe an **zwei** Orten: die Issue-Aktionen in
  der Projekt-Leiste, die Massenbewertung in der Werkzeugleiste des
  Anforderungs-Tabs — und in der Risikobewertung alles im Tab. WiBA hatte
  „Issues anlegen" gar nicht, weil die **Route** fehlte (sie kommt jetzt aus
  der Fabrik), und das Audit-Log gab es nur in der Risikobewertung.

  WARUM ALLES IN DIE PROJEKT-LEISTE
  Alle sieben Handlungen gelten dem **Projekt**, nicht der Liste, die gerade
  offen ist. In der Leiste sind sie aus jedem Tab erreichbar; vorher lag das
  Audit-Log hinter dem Risiken-Tab und WiBAs Massenbewertung hinter dem
  Prüffragen-Tab. Die Massenbewertungs-Dialoge holen ihre Objekte selbst über
  den Adapter — sie hängen nicht an der sichtbaren Liste.

  CRAs Klappmenü entfällt (Vorgabe aus #1851). Es war das einzige im Haus,
  und es ließ sich weder mit Escape noch durch einen Klick daneben schließen.

  WAS NICHT HIERHER GEHÖRT
  Fachlich modul-eigene Knöpfe („➕ KI-System anlegen", „🔍 Repo-Scan",
  „🪄 Risiken-Assistent", „+ Custom", „🗑️ Projekt löschen"). Sie stehen im
  Slot `eigene`. Eine Leiste, die alles aufnimmt, ordnet nichts.
-->
<template>
  <div class="pw-leiste">
    <!-- Bewerten -->
    <button v-if="massAdapter && !nurLesend" class="pw-knopf" type="button"
            :disabled="gesperrt" :title="A.massenAuto.titel"
            @click="autoMassOffen = true">
      {{ A.massenAuto.text }}
    </button>
    <button v-if="massAdapter && mitSammelPrompt && !nurLesend" class="pw-knopf" type="button"
            :disabled="gesperrt" :title="A.massenPrompt.titel"
            @click="massOffen = true">
      {{ A.massenPrompt.text }}
    </button>

    <span v-if="massAdapter && !nurLesend" class="pw-trenner" aria-hidden="true"></span>

    <!-- Issues -->
    <button v-if="!nurLesend" class="pw-knopf" type="button"
            :disabled="gesperrt"
            :title="A.issuesAnlegen.titel" @click="stapelAnlegen">
      {{ knopf(A.issuesAnlegen, busy === 'stapel') }}
    </button>
    <button class="pw-knopf" type="button" :disabled="gesperrt"
            :title="A.statusAbgleichen.titel" @click="abgleichen">
      {{ knopf(A.statusAbgleichen, busy === 'abgleich') }}
    </button>
    <button v-if="!nurLesend" class="pw-knopf" type="button"
            :disabled="gesperrt"
            :title="A.feedbackUebernehmen.titel" @click="uebernehmen">
      {{ knopf(A.feedbackUebernehmen, busy === 'uebernahme') }}
    </button>
    <button class="pw-knopf" type="button" :disabled="gesperrt"
            :title="A.neubewertung.titel" @click="neubewertungOffen = true">
      {{ A.neubewertung.text }}
    </button>

    <span class="pw-trenner" aria-hidden="true"></span>

    <!-- Nachweis -->
    <button class="pw-knopf" type="button" :disabled="gesperrt"
            :title="A.auditLog.titel" @click="auditOffen = true">
      {{ A.auditLog.text }}
    </button>
    <!-- #1864/A: gerechnet, kein KI-Lauf — deshalb auch bei `nurLesend`
         erlaubt: Die Liste liest nur und bewertet nichts. -->
    <button class="pw-knopf" type="button" :disabled="gesperrt"
            :title="A.ueberholt.titel" @click="ueberholtOffen = true">
      {{ A.ueberholt.text }}
    </button>

    <!-- Modul-eigene Knöpfe -->
    <slot name="eigene" />
  </div>

  <LaufFortschritt :offen="lauf.offen" :titel="lauf.titel" :zeilen="lauf.zeilen"
                   :laeuft="lauf.laeuft" :abgebrochen="lauf.abgebrochen"
                   :dauer="lauf.dauer" :warnung="lauf.warnung"
                   @abbrechen="laufAbbrechen" @close="lauf.offen = false" />
  <FehlerHinweis :text="fehler" @close="fehler = ''" />
  <FehlerHinweis v-if="meldung" :text="meldung" art="erfolg" @close="meldung = ''" />

  <!-- #1573: die beiden geteilten Massenbewertungs-Dialoge -->
  <MassAssessmentModal v-if="massOffen && massAdapter && projektName"
                       :projekt-name="projektName" :adapter="massAdapter"
                       @close="massOffen = false" @applied="$emit('reload')" />
  <AutoMassBewertungModal v-if="autoMassOffen && massAdapter && projektName"
                          :projekt-name="projektName" :adapter="massAdapter"
                          @close="autoMassOffen = false" @done="$emit('reload')" />

  <IssueNeubewertungModal v-if="neubewertungOffen && projektName"
                          :api-base="apiBase" :projekt-name="projektName"
                          @close="neubewertungOffen = false" />
  <UeberholtModal v-if="ueberholtOffen && projektName"
                  :api-base="apiBase" :projekt-name="projektName"
                  @close="ueberholtOffen = false"
                  @massenlauf="ueberholtOffen = false; autoMassOffen = true" />
  <AuditLogModal v-if="auditOffen && projektName"
                 :api-base="apiBase" :projekt-name="projektName"
                 @close="auditOffen = false" />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import apiClient from '../../api/client'
import { PROJEKT_AKTIONEN as A, knopf } from '../../utils/aktionen'
import type { MassAdapter } from '../../utils/massAdapters'
import AuditLogModal from './AuditLogModal.vue'
import UeberholtModal from './UeberholtModal.vue'
import AutoMassBewertungModal from './AutoMassBewertungModal.vue'
import FehlerHinweis from './FehlerHinweis.vue'
import LaufFortschritt, { type LaufZeile } from './LaufFortschritt.vue'
import { OBJEKT_LAUF_MS, laufFehlerText } from '../../utils/langlauf'
import IssueNeubewertungModal from './IssueNeubewertungModal.vue'
import MassAssessmentModal from './MassAssessmentModal.vue'
import { type FehlerFall } from '../../utils/fehler'
import { t } from '../../i18n'

const props = withDefaults(defineProps<{
  /** Modul-Prefix: `/cra`, `/nis2`, `/aiact`, `/dsgvo`, `/wiba`, `/risikobewertung`. */
  apiBase: string
  projektName: string
  /** Adapter der Massenbewertung; ohne ihn entfallen die beiden Knöpfe. */
  massAdapter?: MassAdapter | null
  /**
   * Hat das Modul einen Sammel-Prompt-Endpunkt? Für OWASP-Kontrollen gibt es
   * keinen, und ein sichtbarer Knopf ohne Route ist ein Defekt (#1846).
   */
  mitSammelPrompt?: boolean
  /** Wie die Objekte dieses Moduls heißen („Anforderungen", „Prüffragen"). */
  objektWort?: string
  /** Was der Abgleich **nicht** verändert („Bewertungen", „Antworten"). */
  wertWort?: string
  /**
   * Nur die lesenden Handlungen zeigen.
   *
   * Für eine AI-Act-Organisation mit mindestens einem KI-System sperrt
   * `make_org_write_guard` (#1562) die Register-Schreibwege mit 409
   * `org_controls_locked` — ausdrücklich **erlaubt** sind dort der
   * Issue-Abgleich und, weil der Guard GETs durchlässt, die
   * Neubewertungs-Übersicht und das Audit-Log. Die ganze Leiste
   * auszublenden wäre der bequeme Weg und nähme dem Anwender genau die drei
   * Handlungen, die er dort haben darf; vier sichtbare Knöpfe vor einem 409
   * wären die andere Hälfte desselben Fehlers (#1846).
   */
  nurLesend?: boolean
}>(), {
  massAdapter: null,
  mitSammelPrompt: true,
  objektWort: t('geteilt.projektWerkzeugleiste.objekte'),
  wertWort: t('geteilt.projektWerkzeugleiste.bewertungen'),
  nurLesend: false,
})

const emit = defineEmits<{
  /** Nach jeder Handlung, die Daten verändert hat. */
  reload: []
}>()

type Busy = '' | 'stapel' | 'abgleich' | 'uebernahme'
const busy = ref<Busy>('')
/**
 * #1944: Die drei langen Handlungen setzen `busy` nicht mehr - sie laufen
 * schrittweise und zeigen ihren Stand im Dialog. Gesperrt werden die
 * Knoepfe trotzdem, sonst startet ein zweiter Lauf neben dem ersten und
 * beide schreiben in dieselben Freitexte.
 */
const gesperrt = computed(() => !props.projektName || !!busy.value
                                || lauf.value.laeuft)
const fehler = ref('')
const meldung = ref('')

const massOffen = ref(false)
const autoMassOffen = ref(false)
const neubewertungOffen = ref(false)
const auditOffen = ref(false)
const ueberholtOffen = ref(false)

/**
 * Die beiden Massenbewertungen auch von außen öffnen.
 *
 * Der Framework-Wechsel der Risikobewertung (#1577) bietet sie als
 * Folgeschritt an („Felder zurückgesetzt — jetzt neu bewerten"). Ohne diesen
 * Weg bräuchte die View eine **zweite** Instanz derselben Dialoge, nur um
 * denselben Knopf zu haben — und zwei Instanzen eines Dialogs sind zwei
 * Zustände, die auseinanderlaufen können.
 */
defineExpose({
  oeffneMassenAuto: () => { autoMassOffen.value = true },
  oeffneMassenPrompt: () => { massOffen.value = true },
})

const basis = () => `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}`
// #1940: Ein Zeitueberlauf ist der einzige Fehlerfall, in dem der Anwender
// nichts nachholen muss - er braucht deshalb eine eigene Meldung.
const text = (e: any, fall: FehlerFall = 'allgemein', was?: string) =>
  laufFehlerText(e, fall, was)

/**
 * Meldungen stehen in `FehlerHinweis`, nicht in `alert()`.
 *
 * Der Bestand nutzte `alert()` — ein Fenster, das den Browser anhält und das
 * der Anwender wegklicken muss, bevor er das Ergebnis in der Liste ansehen
 * kann. Dazu waren die Texte je Modul verschieden formuliert, obwohl sie
 * dasselbe meldeten.
 */
/**
 * #1944: Ein projektweiter Lauf, schrittweise über die **vorhandenen**
 * Einzel-Routen (seit #1846 gibt es sie für jede Objektart).
 *
 * Warum nicht einfach die Sammel-Route mit größerer Zeitgrenze: Sie antwortet
 * erst am Ende. Bei 312 s (gemessen, #1940) sieht der Anwender fünf Minuten
 * ausgegraute Knöpfe, hat keinen Abbruch, und bei einem Zeitüberlauf bleibt
 * ein halb geschriebener Stand, von dem niemand weiß, wie weit er reicht.
 * Schrittweise ist der Teilstand **bekannt**.
 *
 * Die Objektliste holt der **Server** (`issues/objekte`). Sie aus dem
 * Massen-Adapter zu bauen hätte den Umfang stillschweigend verengt — der
 * projektweite Lauf fasst in CRA vier Objektarten an, der Adapter kennt eine.
 */
const lauf = ref({
  offen: false, titel: '', laeuft: false, abgebrochen: false,
  dauer: 0, warnung: '',
  zeilen: [] as LaufZeile[],
})
let abbruch: AbortController | null = null
let uhr: ReturnType<typeof setInterval> | null = null

const laufBeenden = () => {
  lauf.value.laeuft = false
  if (uhr) { clearInterval(uhr); uhr = null }
  abbruch = null
  emit('reload')
}

const laufAbbrechen = () => {
  lauf.value.abgebrochen = true
  try { abbruch?.abort() } catch { /* bereits beendet */ }
}

type Schritt = (o: { art: string; pfad: string; id: string }) => Promise<void>

const laufStarten = async (titel: string, zweck: string, schritt: Schritt,
                           warnung = '') => {
  if (!props.projektName) return
  fehler.value = ''
  meldung.value = ''
  let objekte: { art: string; pfad: string; id: string; titel?: string }[] = []
  try {
    const res = await apiClient.get(`${basis()}/issues/objekte`,
                                    { params: { zweck } })
    objekte = res.data?.objekte || []
  } catch (e: any) {
    fehler.value = text(e, 'laden')
    return
  }
  if (!objekte.length) {
    meldung.value = t('geteilt.projektWerkzeugleiste.esGibtDafurDerzeitNichtsZuTun')
    return
  }
  lauf.value = {
    offen: true, titel, laeuft: true, abgebrochen: false, dauer: 0, warnung,
    zeilen: objekte.map(o => ({ art: o.art, id: o.id, titel: o.titel,
                                zustand: 'offen' as const })),
  }
  abbruch = new AbortController()
  const start = Date.now()
  uhr = setInterval(() => { lauf.value.dauer = (Date.now() - start) / 1000 }, 1000)

  for (let i = 0; i < objekte.length; i++) {
    if (lauf.value.abgebrochen) {
      // Die übrigen bleiben „offen" und nicht „übersprungen": Sie wurden
      // nicht geprüft und nicht verworfen — niemand hat über sie entschieden.
      break
    }
    lauf.value.zeilen[i].zustand = 'laeuft'
    try {
      await schritt(objekte[i])
      lauf.value.zeilen[i].zustand = 'ok'
    } catch (e: any) {
      if (lauf.value.abgebrochen) { lauf.value.zeilen[i].zustand = 'offen'; break }
      lauf.value.zeilen[i].zustand = 'fehler'
      lauf.value.zeilen[i].meldung = text(e, 'allgemein')
    }
  }
  laufBeenden()
}

const objektUrl = (o: { pfad: string; id: string }) =>
  `${basis()}/${o.pfad}/${encodeURIComponent(o.id)}`

const stapelAnlegen = () => laufStarten(
  A.issuesAnlegen.text, 'anlegen',
  async (o) => {
    await apiClient.post(`${objektUrl(o)}/issues`, {},
                         { timeout: OBJEKT_LAUF_MS, signal: abbruch?.signal })
  },
  // Die Nebenwirkung steht VOR dem Start und nicht in einer Meldung danach:
  // Ein Abbruch hinterlässt angelegte Tickets im fremden Repository, und das
  // kann von hier niemand zurücknehmen.
  'Hier entstehen Issues im verknüpften Repository. Ein Abbruch nimmt die '
  + t('geteilt.projektWerkzeugleiste.bereitsAngelegtenNichtZuruckDasKannD'))

const abgleichen = () => laufStarten(
  A.statusAbgleichen.text, 'abgleich',
  async (o) => {
    await apiClient.post(`${objektUrl(o)}/issues/sync`, {},
                         { timeout: OBJEKT_LAUF_MS, signal: abbruch?.signal })
  },
  `${props.wertWort} werden dabei NICHT verändert — ein geschlossenes Issue `
  + t('geteilt.projektWerkzeugleiste.istKeinNachweisBetroffeneObjekteWerd')
  + t('geteilt.projektWerkzeugleiste.neubewertungErforderlichMarkiert'))

const uebernehmen = () => laufStarten(
  A.feedbackUebernehmen.text, 'import',
  async (o) => {
    await apiClient.post(`${objektUrl(o)}/import-issue`, {},
                         { timeout: OBJEKT_LAUF_MS, signal: abbruch?.signal })
  },
  `${props.wertWort} bleiben unverändert; ein früher übernommener Block wird `
  + t('geteilt.projektWerkzeugleiste.ersetztEinErneuterLaufIstGefahrlos'))
</script>

<style scoped>
.pw-leiste { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }

.pw-trenner {
  width: 1px; align-self: stretch; min-height: 20px;
  background: var(--color-border); margin: 0 2px;
}

.pw-knopf {
  background: white; border: 1px solid #b3d4f5; color: #1565c0;
  padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;
  white-space: nowrap;
}

.pw-knopf:hover:not(:disabled) { background: #1565c0; color: white; }
.pw-knopf:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
