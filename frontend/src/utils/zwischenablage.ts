/**
 * Zwischenablage — eine Stelle fürs ganze Frontend (#1867).
 *
 * Der Copy/Paste-Weg ist der **Vorgabeweg** der Suite: Prompt in ChatGPT
 * einfügen, Antwort zurückholen. Trotzdem stand `navigator.clipboard` an 23
 * Stellen im Baum, und jede verhielt sich anders — mit „✓ Kopiert“, mit
 * `alert()`, mit verschlucktem Fehler und einmal (WiBA-Assistent) als
 * Einzeiler ohne `await` und ohne jede Rückmeldung. Schlug der Zugriff dort
 * fehl, passierte sichtbar nichts.
 *
 * Darum hier die Mechanik und **nur** die Mechanik: Was die Maske anzeigt,
 * entscheidet `components/shared/PromptAustausch.vue`.
 *
 * ZWEI RICHTUNGEN, ZWEI VERLÄSSLICHKEITEN
 * Schreiben gelingt fast immer und hat einen Rückfall, der ohne die
 * Clipboard-API auskommt. **Lesen nicht**: Firefox fragt den Anwender bei
 * jedem `readText()`, und in einem unsicheren Kontext (http) gibt es die
 * Funktion gar nicht. Ein Einfüge-Knopf muss deshalb sagen können, dass er
 * nicht konnte — sonst ist er ein Knopf ohne Wirkung (#1805/#1830), und das
 * ist die Fehlerklasse, die dieses Repo am häufigsten eingefangen hat.
 */

/**
 * Text in die Zwischenablage legen.
 *
 * @returns `true`, wenn es geklappt hat. Der Aufrufer sagt es dem Anwender —
 *   ein verworfenes `false` ist genau der stille Fehlschlag von vorher.
 */
export async function kopiere(text: string): Promise<boolean> {
  const inhalt = String(text ?? '')
  if (!inhalt) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(inhalt)
      return true
    }
  } catch {
    // Verweigert oder nicht verfügbar — unten der Rückfall.
  }
  return ueberHilfsfeld(inhalt)
}

/**
 * Rückfall ohne Clipboard-API: ein unsichtbares Feld, markieren, `copy`.
 *
 * `document.execCommand` ist abgekündigt und funktioniert weiterhin überall;
 * gebraucht wird es für Installationen, die über **http** erreicht werden —
 * dort ist `navigator.clipboard` nicht vorhanden, nicht etwa gesperrt. Ohne
 * diesen Zweig hätte der Kopier-Knopf dort nie funktioniert, und das wäre
 * nicht aufgefallen, weil niemand den Rückgabewert las.
 */
function ueberHilfsfeld(text: string): boolean {
  try {
    const feld = document.createElement('textarea')
    feld.value = text
    feld.setAttribute('readonly', '')
    feld.style.position = 'fixed'
    feld.style.top = '-1000px'
    feld.style.opacity = '0'
    document.body.appendChild(feld)
    feld.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(feld)
    return ok
  } catch {
    return false
  }
}

/** Warum das Einfügen nicht ging — der Aufrufer macht daraus einen Satz. */
export type EinfuegeFehler = 'nicht_verfuegbar' | 'verweigert' | 'leer'

export interface EinfuegeErgebnis {
  text: string
  /** Fehlt, wenn `text` gültig ist. */
  fehler?: EinfuegeFehler
}

/**
 * Text aus der Zwischenablage holen.
 *
 * Anders als beim Kopieren gibt es hier **keinen** Rückfall: Der Browser
 * schützt den Inhalt der Zwischenablage, und an diesem Schutz führt kein
 * Trick vorbei, der nicht selbst einer wäre. Stattdessen wird der Grund
 * benannt, damit die Maske den Anwender auf `Strg+V` verweisen kann.
 */
export async function einfuegen(): Promise<EinfuegeErgebnis> {
  if (!navigator.clipboard?.readText) {
    return { text: '', fehler: 'nicht_verfuegbar' }
  }
  try {
    const text = await navigator.clipboard.readText()
    if (!text.trim()) return { text: '', fehler: 'leer' }
    return { text }
  } catch {
    // Firefox fragt bei jedem Lesen nach; „Abbrechen" landet hier.
    return { text: '', fehler: 'verweigert' }
  }
}

/** Der Satz zum Fehler — damit er überall gleich lautet. */
export const EINFUEGE_HINWEIS: Record<EinfuegeFehler, string> = {
  nicht_verfuegbar: 'Dieser Browser gibt die Zwischenablage nicht heraus. '
    + 'Bitte mit Strg+V in das Feld einfügen.',
  verweigert: 'Der Zugriff auf die Zwischenablage wurde nicht erlaubt. '
    + 'Bitte mit Strg+V in das Feld einfügen.',
  leer: 'Die Zwischenablage ist leer.',
}
