import { computed } from 'vue'
import { t } from '../i18n'

/**
 * Ein Name je Handlung — für alle sechs Module (#1851/#1847/#1848/#1954).
 *
 * DER BEFUND
 * Dieselbe Handlung trug bis v8.2.0 bis zu vier Beschriftungen. Der
 * Status-Abgleich hieß „🔄 Issues synchronisieren" (CRA, NIS2, AI Act, DSGVO,
 * WiBA), „🔄 Issue-Status abgleichen" (Risikobewertung), „🔄 Synchronisieren"
 * (OWASP-LLM), „🔄 Sync" (WiBA-Prüffragen) und „🔄 Status synchronisieren"
 * (Anforderungen). Der Ladezustand dazu: „⏳ Sync…", „⏳ Abgleich…", „⏳…"
 * und in einem Fall gar keiner.
 *
 * WARUM EIN KATALOG UND NICHT SORGFALT
 * Beschriftungen als Zeichenketten in 30 Templates sind genau die
 * Spiegel-Liste, die das erzeugt hat (die Fehlerklasse aus #1731/#1735): Beim
 * nächsten Modul schreibt jemand die naheliegende Variante hin, und niemandem
 * fällt es auf, weil nichts fehlschlägt. Hier ist eine Abweichung eine
 * Änderung an **einer** Stelle — und `tests/test_aktionen_katalog_1851.py`
 * lässt rot werden, wer eine dieser Beschriftungen wieder ins Template
 * schreibt.
 *
 * DIE TEXTE LIEGEN SEIT #1954 IM SPRACHKATALOG
 * `i18n/{de,en}/aktionen.json`. Diese Datei führt weiter, **welche** Handlungen
 * es gibt, wie sie heißen (der Schlüssel) und was zusammengehört — sie führt
 * nur nicht mehr die Wörter. Das ist dieselbe Trennung wie im Rest des
 * Vorhabens: Die Struktur gehört dem Programm, der Wortlaut dem Katalog.
 *
 * WARUM GETTER UND KEINE SCHLÜSSEL IN DEN AUFRUFSTELLEN
 * Der naheliegende Weg wäre, hier `'aktionen.projekt.massenAuto.text'` zu
 * hinterlegen und in den ~60 Aufrufstellen `t(...)` darumzulegen. Das wäre
 * **still gefährlich**: `strictTemplates` ist in diesem Projekt bewusst aus
 * (#1858), also beanstandet niemand ein vergessenes `t()` — im Knopf stünde
 * dann wörtlich `aktionen.projekt.massenAuto.text`, und auffallen würde das
 * erst dem Anwender. Dieselbe Klasse wie #1830/#1854: nichts schlägt fehl.
 *
 * Mit Gettern bleibt `A.massenAuto.text` unverändert und löst beim Lesen auf.
 * Dass der Wechsel dabei **ohne Neuladen** ankommt, hängt daran, dass Vue
 * jeden Ref liest, der während des Renderns berührt wird — `t()` liest
 * `locale`. Das ist eine Zusicherung über fremden Code, deshalb ist sie
 * nachgewiesen, bevor sie hier verwendet wurde, und ein Test hält sie fest.
 *
 * „SYNC" KOMMT IN DER OBERFLÄCHE NICHT MEHR VOR
 * Es ist Fachjargon für „abgleichen" und sagt dem Anwender nicht, was
 * passiert. Im Code darf `sync` stehen (so heißen die Endpunkte), in der
 * Oberfläche nicht — auch nicht im englischen Katalog, wo „Sync" die
 * naheliegende Wahl gewesen wäre. Es heißt dort „Reconcile".
 *
 * WAS HIER NICHT HINEINGEHÖRT
 * Fachlich modul-eigene Knöpfe („➕ KI-System anlegen", „🔍 Repo-Scan",
 * „🪄 Risiken-Assistent"). Sie stehen weiter in ihrer View bzw. im Slot der
 * `ProjektWerkzeugleiste` — ein Katalog, der alles aufnimmt, ordnet nichts.
 */

/** Eine Handlung: Beschriftung, Erklärung (Tooltip), Ladezustand. */
export interface Aktion {
  /** Die Beschriftung auf dem Knopf. */
  readonly text: string
  /** Der `title`-Text — sagt, was passiert, nicht wie der Knopf heißt. */
  readonly titel: string
  /** Beschriftung während der Ausführung. */
  readonly laufend: string
}

/**
 * Eine Handlung an den Katalog binden.
 *
 * Die drei Werte werden **beim Lesen** aufgelöst, nicht beim Laden des Moduls:
 * Sonst stünde die Sprache fest, die beim ersten Import galt, und ein Wechsel
 * wirkte erst nach dem Neuladen.
 */
function aktion(gruppe: 'projekt' | 'objekt', id: string): Aktion {
  const pfad = `aktionen.${gruppe}.${id}`
  return {
    get text() { return t(`${pfad}.text`) },
    get titel() { return t(`${pfad}.titel`) },
    get laufend() { return t(`${pfad}.laufend`) },
  }
}

/** Die projektweite Werkzeugleiste (acht Handlungen, #1851/#1864). */
export const PROJEKT_AKTIONEN = {
  massenAuto: aktion('projekt', 'massenAuto'),
  massenPrompt: aktion('projekt', 'massenPrompt'),
  issuesAnlegen: aktion('projekt', 'issuesAnlegen'),
  statusAbgleichen: aktion('projekt', 'statusAbgleichen'),
  feedbackUebernehmen: aktion('projekt', 'feedbackUebernehmen'),
  neubewertung: aktion('projekt', 'neubewertung'),
  auditLog: aktion('projekt', 'auditLog'),
  // #1864/A: gerechnet, kein KI-Lauf — deshalb kostenlos und ohne Rückfrage.
  ueberholt: aktion('projekt', 'ueberholt'),
} satisfies Record<string, Aktion>

/** Die Bausteine am einzelnen Objekt (#1847 Issues, #1848 KI-Bewertung). */
export const OBJEKT_AKTIONEN = {
  // ── 🔗 Verknüpfte Issues (#1847) ──────────────────────────────────────
  issueAnlegen: aktion('objekt', 'issueAnlegen'),
  issueVerknuepfen: aktion('objekt', 'issueVerknuepfen'),
  issueAbgleichen: aktion('objekt', 'issueAbgleichen'),
  issueEntknuepfen: aktion('objekt', 'issueEntknuepfen'),
  // ── 🤖 KI-Bewertung (#1848) ───────────────────────────────────────────
  kiPrompt: aktion('objekt', 'kiPrompt'),
  kiAuto: aktion('objekt', 'kiAuto'),
  issueImportieren: aktion('objekt', 'issueImportieren'),
  kiNeubewertung: aktion('objekt', 'kiNeubewertung'),
} satisfies Record<string, Aktion>

/** Abschnittstitel — damit auch die Überschriften nicht auseinanderlaufen. */
export const ABSCHNITTE = {
  get issues() { return t('aktionen.abschnitte.issues') },
  get kiBewertung() { return t('aktionen.abschnitte.kiBewertung') },
}

/**
 * Der Hinweis unter der KI-Bewertung. Stand als Zeichenkette in jeder Maske;
 * die Pflicht dazu steht in #1551/#1765 und gilt überall gleich.
 *
 * Als `computed` und nicht als Getter, weil es kein Objekt gibt, an dem einer
 * hängen könnte. In `<script setup>` entpackt Vue den Ref im Template, die
 * Aufrufstelle (`{{ KI_VORBEHALT }}`) bleibt also unverändert.
 *
 * DER WORTLAUT HAT SICH MIT #1954 GEÄNDERT: „🤖 Von der KI erzeugt" statt
 * „🤖 KI-generiert". Der zweite ist wörtlich `shared/ki_herkunft.ALTER_MARKER`
 * — eine Zeichenkette, die in die Datenbank geschrieben und per Präfix
 * zurückgelesen wird (`ohne_marker`, `ist_druckbar`). Dass sie hier nur
 * zufällig gleich lautete, half niemandem: Wer sie im Sprachkatalog sieht, kann
 * nicht erkennen, ob er eine Anzeige oder ein Datenformat übersetzt — und ein
 * übersetztes Datenformat wird nicht mehr erkannt. `test_i18n_katalog_1954.py`
 * hat das beim Umzug sofort beanstandet, zu Recht.
 */
export const KI_VORBEHALT = computed(() => t('aktionen.kiVorbehalt'))

export type ProjektAktion = keyof typeof PROJEKT_AKTIONEN
export type ObjektAktion = keyof typeof OBJEKT_AKTIONEN

/** Beschriftung je Zustand — damit `laufend` nicht am Aufrufer hängt. */
export function knopf(aktion: Aktion, laeuft = false): string {
  return laeuft ? aktion.laufend : aktion.text
}
