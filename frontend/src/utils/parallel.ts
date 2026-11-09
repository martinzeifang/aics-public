/**
 * Nebenläufige Abrufe **begrenzen** (#2087/4).
 *
 * `Promise.all(liste.map(...))` hat keine Grenze: Bei 10 CRA-Produkten sind
 * das 10 gleichzeitige `/reifegrad`-Anfragen — serverseitig 50 Verbindungen
 * und ~200 Roundtrips, dazu 10 der 24 Worker-Threads aus **einem**
 * Browser-Tab. Bei 20 Produkten 20 parallel.
 *
 * Die Gegenentscheidung steht im Haus: #1764 hält ausdrücklich fest, dass die
 * Seitenleiste **keine** Kennzahlen je Projekt nachlädt („Dutzende Abfragen
 * für eine Seitenleiste"). Dieselbe Ansicht eine Ebene darüber tat es doch.
 *
 * Hier wird nicht weggelassen, sondern **gedrosselt**: Die Zahlen gehören in
 * die Übersicht, nur nicht alle auf einmal. Die Reihenfolge der Ergebnisse
 * bleibt die der Eingabe — sonst müsste jeder Aufrufer selbst zuordnen.
 */

/** Wie viele Abrufe gleichzeitig laufen dürfen. */
export const PARALLEL_GRENZE = 4

/**
 * Führt `aufgaben` mit höchstens `grenze` gleichzeitig aus.
 *
 * Ein Fehlschlag **bricht nicht ab**: Die Aufrufer behandeln ihre Fehler
 * selbst (`try/catch` je Aufgabe), und ein abgebrochener Durchlauf hinterließe
 * eine halb gefüllte Übersicht ohne Hinweis darauf.
 */
export async function parallelBegrenzt<T>(
  aufgaben: Array<() => Promise<T>>,
  grenze: number = PARALLEL_GRENZE,
): Promise<T[]> {
  const ergebnisse: T[] = new Array(aufgaben.length)
  let naechste = 0
  const arbeiter = async () => {
    for (;;) {
      const i = naechste++
      if (i >= aufgaben.length) return
      ergebnisse[i] = await aufgaben[i]()
    }
  }
  await Promise.all(
    Array.from({ length: Math.max(1, Math.min(grenze, aufgaben.length)) },
               arbeiter))
  return ergebnisse
}
