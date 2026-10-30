/**
 * Ein Name je Handlung — für alle sechs Module (#1851/#1847/#1848).
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
 * „SYNC" KOMMT IN DER OBERFLÄCHE NICHT MEHR VOR
 * Es ist Fachjargon für „abgleichen" und sagt dem Anwender nicht, was
 * passiert. Im Code darf `sync` stehen (so heißen die Endpunkte), in der
 * Oberfläche nicht.
 *
 * WAS HIER NICHT HINEINGEHÖRT
 * Fachlich modul-eigene Knöpfe („➕ KI-System anlegen", „🔍 Repo-Scan",
 * „🪄 Risiken-Assistent"). Sie stehen weiter in ihrer View bzw. im Slot der
 * `ProjektWerkzeugleiste` — ein Katalog, der alles aufnimmt, ordnet nichts.
 */

/** Eine Handlung: Beschriftung, Erklärung (Tooltip), Ladezustand. */
export interface Aktion {
  /** Die Beschriftung auf dem Knopf. */
  text: string
  /** Der `title`-Text — sagt, was passiert, nicht wie der Knopf heißt. */
  titel: string
  /** Beschriftung während der Ausführung. */
  laufend: string
}

/** Die projektweite Werkzeugleiste (sieben Handlungen, #1851). */
export const PROJEKT_AKTIONEN = {
  massenAuto: {
    text: '🤖 Automatische Massenbewertung',
    titel: 'Mehrere Objekte auswählen und je Objekt von der KI bewerten lassen',
    laufend: '⏳ Bewerte…',
  },
  massenPrompt: {
    text: '🧮 Massenbewertung (Sammel-Prompt)',
    titel: 'Einen gemeinsamen Prompt für mehrere Objekte erzeugen und die Antwort übernehmen',
    laufend: '⏳ Lade…',
  },
  issuesAnlegen: {
    text: '🐙 Issues anlegen',
    titel: 'Für die offenen Punkte dieses Projekts GitHub-/GitLab-Issues im Stapel anlegen',
    laufend: '⏳ Lege an…',
  },
  statusAbgleichen: {
    text: '🔄 Issue-Status abgleichen',
    titel: 'Status und neue Kommentare aller verknüpften Issues dieses Projekts abrufen; '
      + 'Bewertungen werden dabei nicht verändert',
    laufend: '⏳ Gleiche ab…',
  },
  feedbackUebernehmen: {
    text: '📥 Issue-Feedback übernehmen',
    titel: 'Inhalt und Kommentare der verknüpften Issues in den Freitext übernehmen — '
      + 'die Bewertung bleibt unverändert',
    laufend: '⏳ Übernehme…',
  },
  neubewertung: {
    text: '🧪 Neubewertung aus Issues',
    titel: 'Die verknüpften Issues durchsehen und je Objekt zeigen, was eine Neubewertung verlangt',
    laufend: '⏳ Prüfe…',
  },
  auditLog: {
    text: '📜 Audit-Log',
    titel: 'Revisionspfad dieses Projekts — wer wann was geändert hat',
    laufend: '⏳ Lade…',
  },
  // #1864/A: gerechnet, kein KI-Lauf — deshalb kostenlos und ohne Rückfrage.
  ueberholt: {
    text: '🕒 Was ist überholt?',
    titel: 'Bewertungen zeigen, die älter sind als ein Ereignis in derselben '
      + 'Akte — neuer Nachweis, neue SBOM, Pentest-Bericht. Es wird nichts neu '
      + 'bewertet.',
    laufend: '⏳ Prüfe…',
  },
} as const satisfies Record<string, Aktion>

/** Die Bausteine am einzelnen Objekt (#1847 Issues, #1848 KI-Bewertung). */
export const OBJEKT_AKTIONEN = {
  // ── 🔗 Verknüpfte Issues (#1847) ──────────────────────────────────────
  issueAnlegen: {
    text: '➕ Issue anlegen',
    titel: 'Ein neues GitHub-/GitLab-Issue für dieses Objekt anlegen und verknüpfen',
    laufend: '⏳ Lege an…',
  },
  issueVerknuepfen: {
    text: '🔗 Bestehendes verknüpfen',
    titel: 'Ein vorhandenes Issue über seine URL mit diesem Objekt verknüpfen',
    laufend: '⏳ Verknüpfe…',
  },
  issueAbgleichen: {
    text: '🔄 Status abgleichen',
    titel: 'Status und neue Kommentare der verknüpften Issues abrufen; '
      + 'die Bewertung wird dabei nicht verändert',
    laufend: '⏳ Gleiche ab…',
  },
  issueEntknuepfen: {
    text: '✕',
    titel: 'Verknüpfung entfernen',
    laufend: '…',
  },
  // ── 🤖 KI-Bewertung (#1848) ───────────────────────────────────────────
  kiPrompt: {
    text: '🤖 KI-Bewertung (Prompt → Antwort)',
    titel: 'Prompt erzeugen, in die KI einfügen und die Antwort übernehmen',
    laufend: '⏳ Lade Prompt…',
  },
  kiAuto: {
    text: '🤖 Automatische Bewertung',
    titel: 'Die KI direkt aufrufen und das Ergebnis übernehmen',
    laufend: '⏳ Bewerte…',
  },
  issueImportieren: {
    text: '📥 Issue-Inhalt importieren',
    titel: 'Issue-Inhalt und Review-Feedback in den Freitext übernehmen — '
      + 'die Bewertung wird dabei nicht verändert',
    laufend: '⏳ Übernehme…',
  },
  kiNeubewertung: {
    text: '🔄 Neubewertung mit Issue-Feedback',
    titel: 'KI-Neubewertung unter Einbezug des Issue-/Review-Feedbacks',
    laufend: '⏳ Bewerte…',
  },
} as const satisfies Record<string, Aktion>

/** Abschnittstitel — damit auch die Überschriften nicht auseinanderlaufen. */
export const ABSCHNITTE = {
  issues: '🔗 Verknüpfte Issues',
  kiBewertung: '🤖 KI-Bewertung',
} as const

/**
 * Der Hinweis unter der KI-Bewertung. Stand als Zeichenkette in jeder Maske;
 * die Pflicht dazu steht in #1551/#1765 und gilt überall gleich.
 */
export const KI_VORBEHALT = '🤖 KI-generiert — fachlich zu prüfen.'

export type ProjektAktion = keyof typeof PROJEKT_AKTIONEN
export type ObjektAktion = keyof typeof OBJEKT_AKTIONEN

/** Beschriftung je Zustand — damit `laufend` nicht am Aufrufer hängt. */
export function knopf(aktion: Aktion, laeuft = false): string {
  return laeuft ? aktion.laufend : aktion.text
}
