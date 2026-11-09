/**
 * Escape schließt die oberste Schicht — **eine** Stelle für 43 Dialoge (#2045).
 *
 * DER BEFUND
 * ----------
 * Von 62 Dialogen schlossen **9** auf Escape. Alle neun waren die, die
 * ``ModalRahmen`` benutzen (#1849) — dort steht die Regel. Die übrigen 53
 * fingen den Tastendruck nicht, obwohl jeder von ihnen einen Klick auf den
 * Hintergrund schon als „schließen" versteht. Der Anwender drückt Escape,
 * nichts passiert, und er sucht den ✕ — bei einem Dialog über dem ganzen
 * Bildschirm ist das der häufigste Weg heraus.
 *
 * WARUM NICHT 43 EINZELNE EINBAUTEN
 * ---------------------------------
 * Das wäre die Spiegel-Liste aus #1731/#1735 in ihrer teuersten Form: eine
 * Regel, die in 43 Dateien noch einmal stehen muss, und beim 44. Dialog
 * fehlt sie, ohne dass etwas fehlschlägt. Dazu bräuchte jede Einbaustelle die
 * **Bedingung**, unter der *ihr* Dialog offen ist — ``AdminSettingsView`` führt
 * sieben Schichten in einer Datei, ``AdminTemplatesView`` drei.
 *
 * WAS STATTDESSEN PASSIERT
 * ------------------------
 * Escape wird als **Klick auf den Hintergrund** ausgeführt: Der Fallback
 * sucht die oberste sichtbare Schicht und schickt ihr ein ``mousedown`` und
 * ein ``click``, deren Ziel die Schicht selbst ist. Damit greift genau der
 * ``@mousedown.self``-Zuhörer, den der Dialog ohnehin hat, und die
 * **Entscheidung bleibt beim Dialog**:
 *
 * * Er schließt auf Klick daneben → er schließt auf Escape.
 * * Er schließt **nicht** (ungespeicherte Eingabe, ``!embedded &&``) → Escape
 *   tut auch nichts. Das ist richtig und keine Lücke: Die beiden Wege sollen
 *   nicht verschieden entscheiden.
 *
 * Damit kann diese Regel nicht von den Dialogen wegdriften — sie liest ihre
 * Antwort aus ihnen ab, statt sie zu wiederholen.
 *
 * DIE GRENZEN, DIE HIER BEWUSST GEZOGEN SIND
 * ------------------------------------------
 * * **Ein offener ``ModalRahmen`` hat Vorrang.** Er zählt sich in
 *   ``rahmenOffen`` mit und kennt seine eigene Ebene; zwei Zuhörer auf
 *   denselben Tastendruck schlössen sonst zwei Schichten auf einmal.
 * * **Der Zuhörer hängt an ``window``, nicht an ``document``.** Der Weg eines
 *   Tastendrucks läuft ``…  → document → window``; so kommt dieser Fallback
 *   garantiert **nach** jedem Dialog, der selbst zuhört, und ein bereits
 *   behandeltes Ereignis (``defaultPrevented``) wird übergangen.
 * * **Kein ``preventDefault`` auf dem Original.** Escape in einem Eingabefeld
 *   hat eigene Bedeutungen (Vorschlagsliste schließen), und die soll ein
 *   Dialog-Fallback nicht nehmen.
 */

/** Wie viele ``ModalRahmen`` gerade offen sind. Solange > 0 gehört Escape ihm. */
export const rahmenOffen = { anzahl: 0 }

/** Schichten, die ihren eigenen Escape-Anspruch haben (sie regeln ihn selbst). */
const EIGENER_ANSPRUCH = new Set(['mr-overlay'])

function sichtbar(el: HTMLElement): boolean {
  // ``offsetParent`` ist bei ``position: fixed`` null, deshalb zusätzlich die
  // Rechtecke: eine Schicht ohne Fläche ist nicht offen.
  if (el.getClientRects().length === 0) return false
  const stil = window.getComputedStyle(el)
  return stil.visibility !== 'hidden' && stil.display !== 'none'
}

function obersteSchicht(): HTMLElement | null {
  const alle = Array.from(
    document.querySelectorAll<HTMLElement>('[class*="overlay"]'),
  ).filter((el) => {
    if (!sichtbar(el)) return false
    for (const k of el.classList) if (EIGENER_ANSPRUCH.has(k)) return false
    // Eine Schicht **innerhalb** einer anderen ist deren Inhalt, nicht die
    // oberste Schicht.
    return true
  })
  if (!alle.length) return null
  // Oben liegt, was den höchsten z-index hat; bei Gleichstand das zuletzt
  // eingehängte (Teleport hängt an ``body``, die DOM-Reihenfolge entspricht
  // also der Reihenfolge des Öffnens).
  const z = (el: HTMLElement) => {
    const w = parseInt(window.getComputedStyle(el).zIndex || '', 10)
    return Number.isFinite(w) ? w : 0
  }
  return alle.reduce((oben, el) => (z(el) >= z(oben) ? el : oben), alle[0])
}

function alsHintergrundklick(el: HTMLElement): void {
  // Beide Ereignisse, weil beide Schreibweisen im Haus vorkommen
  // (``@mousedown.self`` und ``@click.self``). ``.self`` prüft
  // ``target === currentTarget`` — das gilt, weil wir auf der Schicht selbst
  // auslösen.
  for (const art of ['mousedown', 'click'] as const) {
    el.dispatchEvent(new MouseEvent(art, { bubbles: true, cancelable: true }))
  }
}

let verdrahtet = false

/** Einmal beim Start der Anwendung aufrufen (``App.vue``). */
export function escapeSchichtVerdrahten(): void {
  if (verdrahtet || typeof window === 'undefined') return
  verdrahtet = true
  window.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key !== 'Escape' || e.defaultPrevented) return
    if (rahmenOffen.anzahl > 0) return
    const schicht = obersteSchicht()
    if (schicht) alsHintergrundklick(schicht)
  })
}
