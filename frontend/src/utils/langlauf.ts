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
 * Meldung für einen Zeitüberlauf.
 *
 * Sie sagt drei Dinge, und alle drei sind wichtiger als das Wort „Fehler":
 * dass der Server weiterarbeitet, dass der Stand deshalb unbekannt und nicht
 * leer ist, und — bei idempotenten Handlungen — dass ein erneuter Lauf
 * gefahrlos ist. Ohne den dritten Satz klickt niemand noch einmal, und genau
 * das wäre hier richtig.
 */
export function zeitueberlaufText(wasSchluessel = 'vorgang',
                                  idempotent = true): string {
  const was = t(`langlauf.was.${wasSchluessel}`)
  return t('langlauf.kern', { was })
    + t(idempotent ? 'langlauf.ratIdempotent' : 'langlauf.ratPruefen')
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
                               idempotent = true): string {
  if (istZeitueberlauf(e)) return zeitueberlaufText(wasSchluessel, idempotent)
  return fehlerText(e, fall)
}
