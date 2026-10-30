/**
 * Formularfelder aus den Quellen füllen — die Mechanik, einmal (#1893).
 *
 * WARUM DIESE DATEI EXISTIERT
 * #1884–#1887 haben sie für die CRA-Konformitätserklärung gebaut. Dasselbe
 * braucht die AI-Act-Erklärung (#1889), das DSGVO-VVT (#1890) und die
 * Datenpanne (#1891). In jeder Maske nachgebaut wären das vier Kopien der
 * Regel „nur leere Felder füllen" — und in einer fehlt sie, ohne dass etwas
 * fehlschlägt (#1731/#1735).
 *
 * DIE REGELN STECKEN IM SERVER, NICHT HIER
 * Welche Felder eine Quelle haben, welcher Klasse sie angehören und was ein
 * Sprachmodell setzen darf, sagt der Vorschlags-Endpunkt. Diese Datei
 * **rechnet nichts nach** — sie bedient. Die Regeln im Frontend zu spiegeln
 * ist die Lehre aus #1703/S9.
 */
import { computed, type Ref } from 'vue'

export interface Feldvorschlag {
  wert: string | string[]
  quelle: string
  klasse: 'gerechnet' | 'uebernommen' | 'auswahl' | 'ki' | string
}

export interface Befund {
  id: string
  nr?: number
  feld?: string
  art?: string
  wirkung: 'blockiert' | 'bestaetigung' | 'hinweis' | string
  text: string
  hinweis?: string
  confirm?: string
}

/**
 * Trägt das Feld eine Angabe?
 *
 * `false` und `0` gelten als **nicht** gefüllt — ein Schalter in diesen
 * Formularen hält „nicht entschieden" und „nein" nicht auseinander (#1805).
 * Die Regel ist dieselbe wie in `shared/formular_vorschlag.ist_gefuellt`.
 */
export function istGefuellt(wert: unknown): boolean {
  if (Array.isArray(wert)) return wert.some(w => String(w ?? '').trim())
  if (typeof wert === 'boolean') return wert
  return String(wert ?? '').trim().length > 0
}

export function useFormularVorschlag(
  werte: Ref<Record<string, any>>,
  vorschlaege: Ref<Record<string, Feldvorschlag>>,
) {
  /** Leere Felder, zu denen der Server eine Quelle kennt. */
  const fuellbar = computed(() =>
    Object.keys(vorschlaege.value || {}).filter(f => !istGefuellt(werte.value[f])))

  const anzahlFuellbar = computed(() => fuellbar.value.length)

  /**
   * Ein Feld füllen.
   *
   * Ohne `ersetzen` bleibt ein gefülltes Feld unberührt: Es ist die Aussage
   * eines Menschen, und sie stillschweigend zu überschreiben ist der Fehler
   * aus #1769/#1773.
   */
  function feldFuellen(feld: string, ersetzen = false) {
    const v = vorschlaege.value?.[feld]
    if (!v) return
    if (istGefuellt(werte.value[feld]) && !ersetzen) return
    werte.value[feld] = Array.isArray(v.wert) ? v.wert.join('\n') : String(v.wert ?? '')
  }

  /** Alle leeren Felder mit Quelle. Nie die gefüllten. */
  function alleFuellen() {
    for (const feld of fuellbar.value) feldFuellen(feld, false)
  }

  function quelle(feld: string): string {
    return String(vorschlaege.value?.[feld]?.quelle || '')
  }

  function klasse(feld: string): string {
    return String(vorschlaege.value?.[feld]?.klasse || '')
  }

  return { fuellbar, anzahlFuellbar, feldFuellen, alleFuellen, quelle, klasse,
           istGefuellt }
}

/** Die Befunde, die ein Abschluss verhindern (#1885). */
export function blockierende(befunde: Befund[] | undefined): Befund[] {
  return (befunde || []).filter(b => b.wirkung === 'blockiert')
}

export function wirkungLabel(w: string): string {
  return ({ blockiert: '⛔ blockiert', bestaetigung: '✋ Bestätigung nötig',
    hinweis: 'ℹ Hinweis' } as Record<string, string>)[w] || w
}
