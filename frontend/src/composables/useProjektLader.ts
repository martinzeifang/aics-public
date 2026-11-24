import { ref } from 'vue'

/**
 * Projektweites Nachladen — entprellt und gegen Überholer gesichert
 * (#2025/#2044).
 *
 * ## Was gemessen wurde
 *
 * Am nginx-Zugriffslog von aics-demo (09.11.2026, 1 347 API-Anfragen des
 * Browsers): **37 Schwälle** von ≥ 10 Anfragen in ≤ 4 Sekunden, die drei
 * größten mit 56, 55 und 52 Anfragen. Und darin wird **dieselbe Anfrage drei-
 * bis viermal** wiederholt — nicht einmal zu viel.
 *
 * Die Ursache ist in allen sechs Modul-Views dieselbe Form: `reloadProjekt`
 * startet 2–6 parallele Lader und wird aus 5–10 Stellen gerufen, ohne
 * Entprellung. Ein Tab-Wechsel, ein gespeicherter Wert und ein geschlossenes
 * Modal in derselben Sekunde ergeben drei vollständige Ladungen.
 *
 * ## Zwei Dinge, nicht eines
 *
 * 1. **Entprellen** (#2025): Mehrere Anforderungen innerhalb von `warte`
 *    Millisekunden werden zu **einer** zusammengefasst. Das ist der Schwall.
 *
 * 2. **Der zuletzt gestartete Lauf gewinnt** (#2044): Vorher gewann der
 *    zuletzt **antwortende**. Wer Projekt A öffnet und sofort zu B wechselt,
 *    sah B's Daten — oder A's, wenn A langsamer war. Jeder Lauf bekommt eine
 *    Nummer; eine Antwort, die nicht mehr die aktuelle ist, wird verworfen.
 *    Das ist der gefährlichere der beiden Punkte: Der Schwall kostet Last, der
 *    Überholer zeigt **fremde Daten unter dem Namen des gewählten Projekts**.
 *
 * ## Was es nicht tut
 *
 * Es fasst keine Endpunkte zusammen und ändert keine Reihenfolge. Welche Lader
 * laufen, entscheidet weiter die View — dieses Modul entscheidet nur, **wann**
 * und **ob das Ergebnis noch gilt**.
 */
export function useProjektLader(
  laden: (projekt: string) => Promise<unknown>,
  { warte = 150 }: { warte?: number } = {},
) {
  /** Läuft gerade eine Ladung? (für Spinner) */
  const laedt = ref(false)
  /** Laufende Nummer: nur die höchste darf ihr Ergebnis übernehmen. */
  let generation = 0
  let timer: number | undefined
  let wartend: Promise<void> | undefined
  let aufloesen: (() => void) | undefined

  /**
   * Prüft, ob dieser Lauf noch der aktuelle ist. Die View ruft das **nach**
   * jedem `await`, bevor sie etwas in den Zustand schreibt.
   */
  const istAktuell = (nummer: number) => nummer === generation

  const nachladen = (projekt: string | null | undefined): Promise<void> => {
    if (!projekt) return Promise.resolve()
    if (timer) window.clearTimeout(timer)
    if (!wartend) {
      wartend = new Promise<void>(r => { aufloesen = r })
    }
    timer = window.setTimeout(async () => {
      timer = undefined
      const fertig = aufloesen
      wartend = undefined
      aufloesen = undefined
      const nummer = ++generation
      laedt.value = true
      try {
        await laden(projekt)
      } finally {
        // Nur der aktuelle Lauf darf den Spinner ausschalten — sonst löscht
        // ein überholter Lauf die Anzeige des neuen.
        if (istAktuell(nummer)) laedt.value = false
        fertig?.()
      }
    }, warte)
    return wartend
  }

  /** Alle noch nicht gestarteten Ladungen verwerfen (z. B. beim Unmount). */
  const abbrechen = () => {
    if (timer) window.clearTimeout(timer)
    timer = undefined
    generation += 1
    aufloesen?.()
    wartend = undefined
    aufloesen = undefined
  }

  return { laedt, nachladen, abbrechen, istAktuell, aktuelleNummer: () => generation }
}
