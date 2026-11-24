/**
 * Nachrichten mit Platzhaltern — ohne `eval`, ohne Laufzeit-Compiler (#1954).
 *
 * WARUM ES DIESE DATEI GIBT
 * vue-i18n übersetzt Nachrichten normalerweise **zur Laufzeit** mit
 * `new Function()`. Die CSP dieser Anwendung ist `script-src 'self'` ohne
 * `unsafe-eval` (`docker/nginx.conf`, `server/app.py:_build_csp`) — der Aufruf
 * wird blockiert, und auf jeder Seite nach dem Login stand derselbe
 * Konsolenfehler. #1816 hat das gelöst, indem jede Nachricht als **fertige
 * Funktion** übergeben wird: `() => 'Speichern'`.
 *
 * Der Preis dieser Lösung war, dass eine fertige Funktion keinen Platzhalter
 * füllen kann. Für eine Handvoll Schlüssel ging das; für eine zweisprachige
 * Oberfläche geht es nicht — „Fassung 8.6.0 vom 4. November", „3 von 17
 * Anforderungen" und englische Pluralformen sind ohne Platzhalter nicht
 * formulierbar. Der Dateikopf von `index.ts` nannte als Ausweg die
 * Vorkompilierung über `@intlify/unplugin-vue-i18n`.
 *
 * WARUM ES DIE VORKOMPILIERUNG NICHT GEWORDEN IST
 * Sie hätte eine neue Abhängigkeit gebracht, die gegen **Vite 8/Rolldown** zu
 * erproben wäre, und sie hätte `alsFunktionen` entfernt — also genau die
 * Zusicherung, auf der `tests/test_funde_1814_1817.py` den CSP-Schutz
 * festmacht. Gebraucht wird aber nicht ein Compiler, sondern das, was er
 * erzeugt: je Nachricht eine Funktion. Das lässt sich in dreißig Zeilen
 * selbst bauen, und zwar **ohne jede Form von Codeerzeugung** — hier wird nur
 * eine Liste aus Textstücken und Platzhalternamen zusammengesetzt und von
 * einer Closure wieder verkettet. `new Function` und `eval` kommen in dieser
 * Datei nicht vor, und `tests/test_i18n_katalog_1954.py` wacht darüber.
 *
 * WAS UNTERSTÜTZT WIRD
 *   'Speichern'                      -> fester Text (eine Closure ohne Arbeit)
 *   'Fassung {v} vom {d}'            -> benannte Platzhalter, $t(k, {v, d})
 *   'Treffer {0} von {1}'            -> Positionsargumente, $t(k, [a, b])
 *   ['keine', 'eine', '{n} Stück']   -> Plural, $t(k, {n}, n)
 *
 * PLURAL IST EINE LISTE, KEIN SENKRECHTER STRICH
 * vue-i18n trennt Pluralformen üblicherweise mit `|` innerhalb einer
 * Zeichenkette. Das ist hier bewusst **nicht** übernommen: In dieser
 * Anwendung kommen senkrechte Striche in echten Beschriftungen vor
 * („Soll | Ist", Tabellenköpfe), und eine Nachricht, die sich je nach
 * Zeichen im Text anders verhält, ist eine Falle. Eine Liste ist
 * eindeutig — und im JSON-Katalog ohnehin die natürliche Form.
 *
 * EIN UNBEKANNTER PLATZHALTER BLEIBT SICHTBAR
 * Liefert der Aufrufer `{v}` nicht, erscheint `{v}` im Text statt
 * „undefined". Das hat zwei Gründe: Ein Tippfehler fällt dadurch auf (und
 * `strictTemplates` ist aus, prüft solche Aufrufe also nicht), und ein
 * Codebeispiel im Hilfetext, das zufällig `{risiken}` enthält, bleibt heil.
 */

/** Ein Textstück oder ein Platzhalter. */
type Stueck = string | { platz: string }

/** Das, was vue-i18n einer Nachrichten-Funktion übergibt (Teilmenge). */
export interface Kontext {
  named(key: string): unknown
  list(index: number): unknown
  plural(messages: string[]): string
}

export type Nachricht = (ctx: Kontext) => string

/** Erlaubt sind Buchstaben, Ziffern und `_` — damit `{"a": 1}` kein Treffer ist. */
const PLATZHALTER = /\{(\w+)\}/g

/** Zerlegt `'A {x} B'` in `['A ', {platz:'x'}, ' B']`. */
export function zerlege(muster: string): Stueck[] {
  const stuecke: Stueck[] = []
  let gelesen = 0
  let treffer: RegExpExecArray | null
  PLATZHALTER.lastIndex = 0
  while ((treffer = PLATZHALTER.exec(muster)) !== null) {
    if (treffer.index > gelesen) stuecke.push(muster.slice(gelesen, treffer.index))
    stuecke.push({ platz: treffer[1] })
    gelesen = treffer.index + treffer[0].length
  }
  if (gelesen < muster.length) stuecke.push(muster.slice(gelesen))
  return stuecke
}

function einsetzen(stuecke: Stueck[], ctx: Kontext): string {
  let text = ''
  for (const stueck of stuecke) {
    if (typeof stueck === 'string') {
      text += stueck
      continue
    }
    const name = stueck.platz
    // Rein numerisch -> Positionsargument, sonst benannt.
    const wert = /^\d+$/.test(name) ? ctx.list(Number(name)) : ctx.named(name)
    // Nicht geliefert: den Platzhalter stehen lassen, nicht "undefined".
    text += wert === undefined || wert === null ? `{${name}}` : String(wert)
  }
  return text
}

/** Baut aus einem Katalogwert die Nachrichten-Funktion. */
export function kompiliere(wert: string | string[]): Nachricht {
  if (Array.isArray(wert)) {
    const zweige = wert.map(zerlege)
    return (ctx) => ctx.plural(zweige.map((zweig) => einsetzen(zweig, ctx)))
  }
  const stuecke = zerlege(wert)
  // Der häufigste Fall: fester Text. Dann wird nichts verkettet.
  if (stuecke.length === 1 && typeof stuecke[0] === 'string') {
    const fest = stuecke[0]
    return () => fest
  }
  if (stuecke.length === 0) return () => ''
  return (ctx) => einsetzen(stuecke, ctx)
}

export type Baum = { [schluessel: string]: string | string[] | Baum }

/**
 * Wandelt einen Katalog in fertige Nachrichten-Funktionen.
 *
 * Der Name ist der aus #1816 und bleibt es: `tests/test_funde_1814_1817.py`
 * macht an ihm fest, dass kein Laufzeit-Compiler gebraucht wird.
 */
export function alsFunktionen(katalog: Baum): Record<string, unknown> {
  const fertig: Record<string, unknown> = {}
  for (const [schluessel, wert] of Object.entries(katalog)) {
    fertig[schluessel] =
      typeof wert === 'string' || Array.isArray(wert)
        ? kompiliere(wert)
        : alsFunktionen(wert as Baum)
  }
  return fertig
}
