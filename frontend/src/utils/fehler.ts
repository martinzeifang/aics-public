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
  // #2098: kein Server, sondern die Leitung — eine andere Aussage und eine
  // andere nächste Handlung.
  | 'kein_netz' | 'zeitueberschreitung'

/**
 * Ein Fehler ohne Server-Antwort — kein Netz, Zeitüberlauf, abgebrochen.
 *
 * #2098: Der Anwender liest sonst „Laden fehlgeschlagen" und sucht den Fehler
 * im falschen Haus. Ein Netzabbruch ist kein Anwendungsfehler, und die
 * nächste Handlung ist eine andere (nochmal versuchen statt melden).
 */
function netzfall(e: unknown): FehlerFall | null {
  const f = e as { code?: string; response?: unknown }
  if (f?.response) return null            // der Server hat geantwortet
  // **Nur der Code, nie `message`.** Der erste Anlauf prüfte zusätzlich
  // `/timeout/i.test(e.message)` — und `test_fehlermeldungen_1954` wurde
  // zu Recht rot: Diese Datei fasst `message` nicht an, damit daraus nie
  // „timeout of 30000ms exceeded" in einer deutschen Oberfläche wird. Ein
  // zweiter Weg zum selben Schluss war den Verlust dieser Zusage nicht wert;
  // axios setzt für eine Zeitüberschreitung ohnehin einen der beiden Codes.
  const code = String(f?.code || '')
  if (code === 'ECONNABORTED' || code === 'ETIMEDOUT') return 'zeitueberschreitung'
  if (code === 'ERR_NETWORK' || code === 'ERR_INTERNET_DISCONNECTED') return 'kein_netz'
  return null
}

/** Die Meldung des Servers — oder der übersetzte Rückfall zur Handlung.
 *
 * #2098: **Die Ursache geht nicht mehr verloren.** 440 Aufrufe in 51 Stores
 * machten aus jeder Ausnahme einen von 20 Sätzen, und `console.error` stand
 * in genau **einem** Store. Ein Fehler ohne Server-Antwort war damit in der
 * Oberfläche derselbe Satz und in der Konsole nichts: Wer ihn meldet, kann
 * nichts beitragen, und wer ihn sucht, findet nichts. Genau daran ist die
 * flüchtige DSGVO-Meldung des Schirmlaufs vom 09.11.2026 nicht nachstellbar
 * gewesen.
 *
 * Protokolliert wird in die **Konsole**, nicht in die Oberfläche: Ein
 * Stacktrace vor dem Anwender ist keine Hilfe, und Serverinterna gehören
 * seit #737 nicht dorthin.
 *
 * Die Reihenfolge der Meldungen bleibt unverändert — ohne Netzfall ist der
 * ausgegebene Text byte-identisch zu vorher, und jeder Bestandstest bleibt
 * Regressionsschutz.
 */
export function fehlerText(e: unknown, fall: FehlerFall = 'allgemein'): string {
  const vom_server = (e as { response?: { data?: { error?: unknown } } })
    ?.response?.data?.error
  if (typeof vom_server === 'string' && vom_server.trim()) {
    return vom_server
  }
  const netz = netzfall(e)
  try {
    // `console.warn`, nicht `error`: Ein abgebrochener Abruf ist kein Defekt
    // der Anwendung, und eine rote Konsole, die bei jedem Netzhüpfer anspringt,
    // wird nicht mehr gelesen (#1774/#1877).
    console.warn(`[${fall}] ${netz ? `${netz}: ` : ''}Anfrage fehlgeschlagen`, e)
  } catch { /* Konsole kann fehlen (Tests, eingebettete Sichten) */ }
  return t(`fehler.${netz || fall}`)
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
