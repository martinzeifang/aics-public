/**
 * #1573: Einheitliches Ergebnis der automatischen KI-Bewertung — für ALLE Module.
 *
 * Die Stream-Endpunkte liefern modulabhängig unterschiedliche `done`-Payloads:
 *  - Anforderungen/OWASP/OWASP-LLM (CRA, NIS2, AI Act, DSGVO): bewertung, kommentar,
 *    massnahme(n), normbezug
 *  - Risikobewertung: risiko_label, risikowert, bewertung_text, empfehlungen, cra_referenz
 *  - WiBA: status, status_label, notiz/kommentar, massnahmen
 * `normalizeAutoResult` bildet sie auf eine gemeinsame Form ab, die
 * AutoBewertungErgebnis (Einzel) und AutoMassBewertungModal (Masse) anzeigen.
 */
export interface AutoResult {
  /** Hauptwert, z. B. "4 / 5", "Hoch (16)", "Ja (umgesetzt)" */
  wert: string
  /** Farbklasse für den Hauptwert */
  ton: 'gut' | 'mittel' | 'schlecht' | 'neutral'
  begruendung: string
  massnahmen: string[]
  normbezug: string
  provider: string
}

const asList = (v: any): string[] =>
  (Array.isArray(v) ? v : (v ? [v] : [])).map((x: any) => String(x || '').trim()).filter(Boolean)

export function normalizeAutoResult(p: any): AutoResult {
  p = p || {}
  const provider = String(p.provider || '')
  // Risikobewertung
  if (p.risiko_label !== undefined || p.risikowert !== undefined) {
    const label = String(p.risiko_label || '')
    const l = label.toLowerCase()
    return {
      wert: label ? `${label}${p.risikowert != null ? ` (${p.risikowert})` : ''}` : '— (unbewertet)',
      ton: /kritisch|hoch/.test(l) ? 'schlecht' : /mittel/.test(l) ? 'mittel' : label ? 'gut' : 'neutral',
      begruendung: String(p.bewertung_text || ''),
      massnahmen: asList(p.empfehlungen),
      normbezug: String(p.cra_referenz || p.normbezug || ''),
      provider,
    }
  }
  // WiBA (Antwortmodell ja/nein/nicht_relevant)
  if (p.status !== undefined && p.bewertung === undefined && p.score === undefined) {
    const s = String(p.status || 'offen')
    return {
      wert: String(p.status_label || s),
      ton: s === 'ja' ? 'gut' : s === 'nein' ? 'schlecht' : 'neutral',
      begruendung: String(p.kommentar || p.notiz || ''),
      massnahmen: asList(p.massnahmen ?? p.empfehlung),
      normbezug: String(p.normbezug || ''),
      provider,
    }
  }
  // Anforderungen / OWASP / OWASP-LLM (Score 0–5)
  const score = Number(p.bewertung ?? p.score ?? 0)
  const massnahmen = asList(p.massnahmen)
  return {
    wert: `${score} / 5`,
    ton: score >= 4 ? 'gut' : score >= 2 ? 'mittel' : 'schlecht',
    begruendung: String(p.kommentar || ''),
    massnahmen: massnahmen.length ? massnahmen : asList(p.massnahme),
    normbezug: String(p.normbezug || ''),
    provider,
  }
}

/** Eintrag der Massenbewertung (einheitlich für alle Module, siehe utils/massAdapters). */
export interface AutoMassItem {
  id: string | number
  /** Anzeige-ID (z. B. CRA-IMPL-01, #3, ORG-1) */
  code: string
  label: string
  /** aktueller Wert als Text (z. B. „2/5", „Hoch (16)", „Offen") */
  wert?: string
  /** noch nicht (ausreichend) bewertet */
  open: boolean
  /** verknüpftes Issue geändert → „Neubewertung erforderlich" */
  reassess?: boolean
}
