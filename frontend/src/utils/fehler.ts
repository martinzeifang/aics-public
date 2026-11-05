import { t } from '../i18n'

/**
 * Die Fehlermeldung eines fehlgeschlagenen Aufrufs (#1954).
 *
 * DER BEFUND
 * In den 51 Stores stand **420-mal** dieselbe Form:
 *
 *     error.value = e?.response?.data?.error || 'Laden fehlgeschlagen.'
 *
 * Mit **201 verschiedenen** Rückfalltexten, darunter vier Schreibweisen für
 * dasselbe („Fehler beim Löschen" · „Löschen fehlgeschlagen." · „Löschen
 * fehlgeschlagen" · „Fehler beim Löschen des Produkts") — und **93-mal** nur
 * das Wort „Fehler", das dem Anwender nichts sagt, nicht einmal welche
 * Handlung gescheitert ist.
 *
 * Das ist die Spiegel-Liste aus #1731/#1735 in ihrer leisesten Form: Niemandem
 * fällt es auf, weil nichts fehlschlägt — die Oberfläche sagt nur an jeder
 * Stelle etwas anderes. Und für eine zweite Sprache wären es 201 Texte, von
 * denen 185 dasselbe bedeuten.
 *
 * WARUM NUR EIN VERB UND KEIN OBJEKT
 * Der naheliegende Katalog hieße „{was} konnte nicht geladen werden". Das
 * bricht im Deutschen an der Grammatik („**Der** Antrag konnte" gegen „**Die**
 * Risiken konnten") und ergibt ohne Genus- und Numerus-Angabe je Objekt falsche
 * Sätze — eine Übersetzung, die schlechter liest als keine.
 *
 * Dazu lohnt es nicht: Dieser Text erscheint **nur**, wenn der Server gar keine
 * Meldung geschickt hat — also bei Netzausfall, Zeitüberlauf oder 502. In dem
 * Moment muss der Anwender wissen, *welche Handlung* gescheitert ist, nicht
 * welcher Datensatz. Sobald der Server etwas sagt, gilt seine Meldung.
 *
 * KEIN RÜCKFALL AUF `e.message`
 * Das wäre naheliegend und falsch: Daraus würde „Network Error" oder „timeout
 * of 30000ms exceeded" — englischer Technikjargon in einer deutschen
 * Oberfläche, und in einer englischen Oberfläche immer noch Jargon. Die
 * Reihenfolge bleibt genau die bisherige (Servermeldung, sonst Rückfall), damit
 * diese Umstellung das Verhalten nicht nebenbei ändert.
 */
export type FehlerFall =
  | 'laden' | 'speichern' | 'loeschen' | 'anlegen' | 'aktualisieren'
  | 'uebernehmen' | 'exportieren' | 'hochladen' | 'verknuepfen' | 'entfernen'
  | 'abgleichen' | 'erzeugen' | 'auswerten' | 'freigeben' | 'bewerten'
  | 'anmelden' | 'allgemein'

/** Die Meldung des Servers — oder der übersetzte Rückfall zur Handlung. */
export function fehlerText(e: unknown, fall: FehlerFall = 'allgemein'): string {
  const vom_server = (e as { response?: { data?: { error?: unknown } } })
    ?.response?.data?.error
  if (typeof vom_server === 'string' && vom_server.trim()) {
    return vom_server
  }
  return t(`fehler.${fall}`)
}

/**
 * Nur der übersetzte Rückfall, ohne Blick in den Fehler.
 *
 * Für die Stellen, die die Meldung des Servers **selbst** zusammensetzen —
 * `admin.ts` hängt einen `grund` an, `cra.ts` wertet `data.message` vor
 * `data.error` aus, weil der Server dort eine Anleitung ablegt (#1827). Diese
 * Reihenfolge ist Absicht und darf nicht in `fehlerText` verschwinden; gebraucht
 * wird dort nur das letzte Glied der Kette.
 */
export function fehlerRueckfall(fall: FehlerFall = 'allgemein'): string {
  return t(`fehler.${fall}`)
}
