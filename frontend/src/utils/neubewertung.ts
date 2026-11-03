/**
 * Die „Neubewertung erforderlich"-Markierung — eine Stelle fürs ganze Frontend (#1850).
 *
 * Der Marker steht im Freitext des Objekts (Kommentar einer Anforderung, Notiz
 * einer Prüffrage, Bemerkung eines Risikos, Triage-Kommentar einer
 * Schwachstelle); geschrieben hat ihn `shared/issue_abgleich` im Backend.
 * Das Frontend erkennt ihn am **Präfix** und nicht am ganzen Satz: Der
 * Wortlaut nennt seit #1850 den Anlass („Issue geschlossen", „2 neue
 * Kommentare") und das Ticket („#101"), Bestandstexte tragen noch den alten
 * („verknüpftes Issue geändert").
 *
 * Die Zeichenkette stand vorher fünfmal im Frontend verteilt
 * (`RequirementActions`, `OwaspLlmPanel`, `PrueffragenPanel`,
 * `massAdapters`, `stores/risikobewertung`). Fünf Kopien derselben
 * Zeichenkette sind fünf Gelegenheiten, bei einer Wortlaut-Änderung eine zu
 * vergessen — und eine vergessene Stelle zeigt die Markierung einfach nicht
 * mehr an, ohne Fehler (die Fehlerklasse aus #1731/#1735).
 */

/** Stabiler Präfix; identisch mit `shared.issue_abgleich.MARKER`. */
export const NEUBEWERTUNG_MARKER = 'Neubewertung erforderlich'

/** Trägt dieser Text die Markierung? */
export function hatNeubewertung(...texte: unknown[]): boolean {
  return texte.some((t) => String(t ?? '').includes(NEUBEWERTUNG_MARKER))
}

/**
 * Die Markerzeile selbst — als Tooltip. Sie nennt Anlass und Ticket; das ist
 * mehr, als ein allgemeiner Hinweis sagen kann, und kommt aus den Daten.
 */
export function neubewertungAnlass(...texte: unknown[]): string {
  for (const t of texte) {
    for (const zeile of String(t ?? '').split('\n')) {
      if (zeile.includes(NEUBEWERTUNG_MARKER)) return zeile.trim()
    }
  }
  return ''
}

/**
 * Der Hinweistext für die Oberfläche. Pentest-Befunde setzen denselben Marker
 * (#1584) — die Herkunft steht im Text, nicht im Code.
 */
export function neubewertungTitel(...texte: unknown[]): string {
  const anlass = neubewertungAnlass(...texte)
  if (anlass) return `${anlass} — bitte neu bewerten`
  return 'Ein verknüpftes Issue oder ein Pentest-Befund verlangt eine Neubewertung'
}

/**
 * Stabiler Präfix der Bestätigung; identisch mit
 * `shared.issue_abgleich.BESTAETIGT` (#1868).
 */
export const BESTAETIGT_MARKER = 'Neubewertung bestätigt'

/** Hat jemand die Bewertung angesehen und bestätigt? */
export function istBestaetigt(...texte: unknown[]): boolean {
  return texte.some((t) => String(t ?? '').includes(BESTAETIGT_MARKER))
}

/**
 * Die Bestätigungszeile — als Tooltip.
 *
 * Sie nennt Person und Datum. Das ist in einer Nachweisakte die
 * interessantere Aussage als die Markierung selbst: Dass jemand hingesehen
 * hat, beantwortet die Frage, die ein Prüfer stellt.
 */
export function bestaetigungTitel(...texte: unknown[]): string {
  for (const t of texte) {
    for (const zeile of String(t ?? '').split('\n')) {
      if (zeile.includes(BESTAETIGT_MARKER)) return zeile.trim()
    }
  }
  return ''
}
