import { t } from '../i18n'
import { fehlerText, type FehlerFall } from './fehler'

/**
 * Zeitgrenzen und Meldungen für lange Läufe (#1940, #1943).
 *
 * DER BEFUND, DER DAS HIER NÖTIG MACHT
 * `collect_issue_feedback` holt je verknüpftem Issue Beschreibung **und alle
 * Kommentare**. Gemessen auf Produktiv am 02.11.2026: 1,4 s bei einem kurzen
 * Issue, **38,9 s** bei einem Issue mit viel Rückmeldung — und das bei *einer*
 * Verknüpfung. Projektweit über 77 Objekte: **312,5 s**.
 *
 * Dagegen stand die Vorgabe des `apiClient`: **30 000 ms**. Der Einzel-Import
 * setzte gar keine eigene Grenze, die projektweiten Läufe 120–180 s. nginx
 * protokollierte **499** („client closed request"), der Server arbeitete
 * weiter und schrieb — die Oberfläche meldete „fehlgeschlagen", und der
 * Revisionspfad belegt für denselben Klick `imported, fehlgeschlagen: 0`.
 *
 * DIE REGEL, DIE DARAUS FOLGT
 * **Der Client darf nie vor dem Server aufgeben.** Dieselbe Lehre wie #1903,
 * wo ein zu kleines Client-Timeout einen LibreOffice-Prozess verwaisen ließ
 * und damit die ganze Installation beschädigte. Ein zu kleiner Wert ist keine
 * Einstellung, sondern ein Defekt mit Folgen.
 *
 * Und: Ein Zeitüberlauf ist der **einzige** Fehlerfall, in dem der Anwender
 * nichts falsch gemacht hat und nichts nachholen muss. Er braucht deshalb eine
 * eigene Meldung — `e?.response?.data?.error || ersatz` liefert bei einem
 * Abbruch gar keine `response` und fällt auf den Ersatztext zurück, der dann
 * „fehlgeschlagen" behauptet.
 */

/** Grenze für einen Lauf an **einem** Objekt. Gemessener Höchstwert 49 s. */
export const OBJEKT_LAUF_MS = 120_000

/**
 * Grenze für einen projektweiten Lauf über die Sammel-Endpunkte.
 *
 * Gemessen 312 s bei 77 Objekten. Die 900 s sind kein geschätzter Puffer,
 * sondern das Dreifache des Gemessenen — die Dauer hängt an der Antwortzeit
 * von GitHub, und die ist nicht unsere. Wer Fortschritt will, nimmt den
 * schrittweisen Weg (`LaufFortschritt`), nicht eine größere Zahl.
 */
export const PROJEKT_LAUF_MS = 900_000

/**
 * Grenze für einen **synchronen KI-Lauf** über mehrere Scheiben (#1978).
 *
 * Gemessen auf Produktiv am 06.11.2026 für den Erschließungslauf eines
 * Dokuments gegen den WiBA-Katalog: 257 Prüffragen (31 509 Zeichen) ergeben bei
 * `MAX_KATALOG_ZEICHEN` **3 Katalog-Scheiben**, das Dokument (7 Abschnitte)
 * **1 Dok-Scheibe** — also **3 KI-Läufe nacheinander**, zusammen **114 s**.
 *
 * Die Zahl ist nicht das Dreifache davon, sondern bewusst dieselbe wie
 * `PROJEKT_LAUF_MS`: Die Scheibenzahl wächst mit der Größe des Dokuments
 * (50 Abschnitte × WiBA = 12 Läufe ≈ 8 Minuten), und sie hängt an der
 * Antwortzeit des Providers, nicht an uns. Oberhalb davon ist eine größere Zahl
 * die falsche Antwort — dann gehört der Lauf schrittweise mit Fortschritt
 * (`LaufFortschritt`, #1944), und dafür braucht es eine Route je Scheibe.
 *
 * Beide Schichten des Servers liegen darüber (gunicorn `--timeout 1800`, nginx
 * `proxy_read_timeout 1800s`) — das ist die Bedingung, unter der diese Grenze
 * richtig ist, und nicht nur größer.
 */
export const KI_LAUF_MS = 900_000

/**
 * Hat axios wegen der eigenen Zeitgrenze abgebrochen?
 *
 * Geprüft werden drei Formen, weil axios sie je nach Fassung und Umgebung
 * unterschiedlich setzt: `code`, `message` und das Fehlen einer `response`
 * bei gesetztem `config.timeout`. Die letzte Form allein wäre zu grob — sie
 * trifft auch einen Netzabbruch; deshalb steht sie hinten und nur zusammen
 * mit einer gesetzten Grenze.
 */
export function istZeitueberlauf(e: any): boolean {
  if (!e) return false
  if (e.code === 'ECONNABORTED' || e.code === 'ETIMEDOUT') return true
  if (typeof e.message === 'string' && /timeout|timed out/i.test(e.message)) return true
  return !e.response && !!e.config?.timeout
}

/**
 * Was der Anwender nach dem Zeitüberlauf tun soll — es hängt daran, was der
 * Lauf hinterlässt, und das ist drei verschiedene Dinge:
 *
 * - `idempotent`: Der Lauf **schreibt**, und ein zweiter Lauf schreibt nicht
 *   doppelt → Ansicht neu laden, Wiederholung gefahrlos.
 * - `pruefen`: Der Lauf schreibt, eine Wiederholung ist aber nicht folgenlos
 *   → erst den Stand ansehen.
 * - `ohneStand`: Der Lauf **schreibt nichts** (#1978, Aktenprüfung). Dann gibt
 *   es keinen Stand zum Nachladen, und das Ergebnis ist wirklich fort — ein
 *   „Lade die Ansicht neu" wäre hier eine Wegbeschreibung ins Leere.
 */
export type Rat = 'idempotent' | 'pruefen' | 'ohneStand'

/**
 * Meldung für einen Zeitüberlauf.
 *
 * Sie sagt drei Dinge, und alle drei sind wichtiger als das Wort „Fehler":
 * dass der Server weiterarbeitet, dass der Stand deshalb unbekannt und nicht
 * leer ist, und — je nach `rat` — was nun zu tun ist. Ohne den dritten Satz
 * klickt niemand noch einmal, und genau das wäre meist richtig.
 *
 * `boolean` bleibt zulässig, weil die drei Aufrufer aus #1943 so rufen; ein
 * Sweep über sie hätte dem Fix nichts hinzugefügt und Verhalten an Stellen
 * angefasst, die niemand gemeldet hat.
 */
export function zeitueberlaufText(wasSchluessel = 'vorgang',
                                  rat: Rat | boolean = true): string {
  const was = t(`langlauf.was.${wasSchluessel}`)
  const schluessel: Rat = typeof rat === 'boolean'
    ? (rat ? 'idempotent' : 'pruefen') : rat
  // Die Schlüssel stehen als Literale da, damit der Katalog-Wächter (#1964)
  // sie findet — zusammengesetzt wären sie für ihn unsichtbar.
  const rattext = schluessel === 'idempotent' ? t('langlauf.ratIdempotent')
    : schluessel === 'pruefen' ? t('langlauf.ratPruefen')
    : t('langlauf.ratOhneStand')
  return t('langlauf.kern', { was }) + rattext
}

/**
 * Ein Fehlertext, der den Zeitüberlauf von allem anderen unterscheidet.
 *
 * Reihenfolge mit Absicht: Erst der Zeitüberlauf (er hat keine `response` und
 * würde sonst im Ersatztext verschwinden), dann die Meldung des Servers, dann
 * der Ersatz. Ersetzt das verbreitete `e?.response?.data?.error || ersatz`.
 */
export function laufFehlerText(e: any, fall: FehlerFall = 'allgemein',
                               wasSchluessel?: string,
                               rat: Rat | boolean = true): string {
  if (istZeitueberlauf(e)) return zeitueberlaufText(wasSchluessel, rat)
  return fehlerText(e, fall)
}
