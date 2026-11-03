/**
 * Adapter für den geteilten KI-Bewertungs-Baustein (#1848).
 *
 * DER ECHTE UNTERSCHIED IST DER WERTETYP — Score 0–5 (CRA/NIS2/AI-Act/DSGVO,
 * OWASP, OWASP-LLM) gegen ja/nein/nicht relevant (WiBA) gegen Risikowert
 * (Risikobewertung). Den **parametrisiert** der Adapter, er vereinheitlicht
 * ihn nicht: Eine Prüffrage mit „3/5" zu beantworten wäre keine Vereinfachung,
 * sondern eine falsche Aussage.
 *
 * Dasselbe gilt für die **Einstiege**: `einstiege` sagt ausdrücklich, was eine
 * Maske hat. Ein per-Objekt-Prompt gibt es für die OWASP-LLM-Kontrollen des
 * AI-Act nicht (dort ist der Wizard registerweit, `…/owasp-llm/wizard/prompt`)
 * — also wird der Knopf dort **abgeschaltet** und nicht angezeigt und ins 404
 * laufen gelassen. Das ist die Lehre aus #1846: Ein sichtbarer Knopf ohne
 * Route ist ein Defekt, und ein Schalter ist eine Aussage, eine fehlende Route
 * ist ein Zufall.
 *
 * Muster: `utils/massAdapters.ts` (#1573) — derselbe Zuschnitt, dieselbe
 * Begründung.
 */
import type { KiArt } from '../stores/kiHerkunft'

const enc = encodeURIComponent

/** Welche Einstiege eine Maske hat — ausdrücklich, nicht abgeleitet. */
export interface KiEinstiege {
  /** „🤖 KI-Bewertung (Prompt → Antwort)" — braucht `prompt` + `parse-response`. */
  prompt: boolean
  /** „🤖 Automatische Bewertung" — braucht den SSE-Stream. */
  auto: boolean
  /** „🔄 Neubewertung mit Issue-Feedback" — braucht den Stream + Issue-Feedback. */
  neubewertung: boolean
}

export interface KiBewertungsAdapter {
  /** Modulschlüssel für Herkunfts-Register und gespeicherte Hinweise (#1835/#1765). */
  modul: string
  /** Objektart im Herkunfts-Register; leer, wo es keine gibt. */
  herkunftArt: KiArt | ''
  /**
   * URL-Segment der Objektart — für das Bestätigen der Neubewertung (#1868).
   *
   * Ausdrücklich und **nicht** aus `herkunftArt` abgeleitet: Das AI-Act-Register
   * heißt im Pfad `owasp-llm` und als Objektart `owasp_llm`. Eine Ableitung
   * bricht genau dort (dieselbe Trennung wie `ObjektArt.art`/`.pfad` im Backend).
   */
  objektPfad: string
  /** Beschriftung des Hauptwerts: „Bewertung" | „Antwort" | „Risiko". */
  wertLabel: string
  /** Wie der Freitext in dieser Maske heißt (wohin das Ergebnis schreibt). */
  freitext: string
  /** Erwartete Antwortform für den Copy/Paste-Weg. */
  schemaHinweis: string
  /** Beispiel für das Hinweis-Feld (#1834) — passend zum Gegenstand. */
  zusatzBeispiel: string
  /** Felder, die in der Daten-Vorschau als sensibel gelten (#868). */
  sensibel: string[]
  einstiege: KiEinstiege
  /** Wohin das Ergebnis geht + was es überschreibt (#870). */
  ziel: string
  wirkung: string
  promptMethode: 'get' | 'post'
  promptUrl: (id: string | number) => string
  parseUrl: (id: string | number) => string
  /** Absoluter SSE-Pfad **inklusive** `/api`. */
  streamUrl: (id: string | number) => string
  /** Die Daten, die in den Prompt einfließen — aus dem vorliegenden Objekt. */
  vorschau: (objekt: any) => { label: string; value: any }[]
}

/** Die Score-0–5-Module: Anforderungen (CRA, NIS2, AI Act, DSGVO) und OWASP. */
export function anforderungKiAdapter(
  apiBase: string, projekt: string,
  pfad: 'anforderungen' | 'owasp' = 'anforderungen',
): KiBewertungsAdapter {
  const basis = (id: string | number) =>
    `${apiBase}/projekte/${enc(projekt)}/${pfad}/${enc(String(id))}`
  return {
    modul: apiBase.replace(/^\/+|\/+$/g, ''),
    herkunftArt: pfad === 'owasp' ? 'owasp' : 'requirement',
    objektPfad: pfad,
    wertLabel: 'Bewertung',
    freitext: 'den Kommentar',
    schemaHinweis: 'Antwort als JSON: { "score": 0-5, "kommentar": "…", "massnahme": "…" }',
    zusatzBeispiel: 'z. B. „Der Schwerpunkt liegt in der Fertigung, die IT ist ausgelagert."',
    sensibel: ['Repository'],
    einstiege: { prompt: true, auto: true, neubewertung: true },
    ziel: 'Befüllt Bewertung (Score), Kommentar und Maßnahme.',
    wirkung: 'Überschreibt die aktuelle Bewertung nach dem Übernehmen.',
    promptMethode: 'get',
    promptUrl: id => `${basis(id)}/prompt`,
    parseUrl: id => `${basis(id)}/parse-response`,
    streamUrl: id => `/api${basis(id)}/auto-bewertung/stream`,
    vorschau: o => [
      { label: 'Projekt', value: projekt },
      { label: 'Anforderung', value: o?.id },
      { label: 'Titel', value: o?.titel || o?.title },
      { label: 'Kapitel', value: o?.kapitel },
      { label: 'Aktuelle Bewertung', value: o?.bewertung ?? o?.score ?? o?.status },
    ],
  }
}

/**
 * OWASP-LLM (AI Act). **Ohne** Prompt-Einstieg: Der Wizard ist dort
 * registerweit und bleibt es — ein Prompt für zehn Kontrollen ist eine andere
 * Handlung als einer für eine.
 */
export function owaspLlmKiAdapter(projekt: string): KiBewertungsAdapter {
  const basis = (id: string | number) =>
    `/aiact/projekte/${enc(projekt)}/owasp-llm/${enc(String(id))}`
  return {
    modul: 'aiact',
    herkunftArt: 'owasp_llm',
    objektPfad: 'owasp-llm',
    wertLabel: 'Bewertung',
    freitext: 'den Kommentar',
    schemaHinweis: '',
    zusatzBeispiel: 'z. B. „Das System nutzt ausschließlich lokale Modelle."',
    sensibel: ['Repository'],
    einstiege: { prompt: false, auto: true, neubewertung: true },
    ziel: 'Befüllt Status und Kommentar der OWASP-LLM-Kontrolle.',
    wirkung: 'Überschreibt den aktuellen Status.',
    promptMethode: 'get',
    promptUrl: id => `${basis(id)}/prompt`,
    parseUrl: id => `${basis(id)}/parse-response`,
    streamUrl: id => `/api${basis(id)}/auto-bewertung/stream`,
    vorschau: o => [
      { label: 'Projekt', value: projekt },
      { label: 'Kontrolle', value: o?.id },
      { label: 'Titel', value: o?.title || o?.titel },
      { label: 'Aktueller Status', value: o?.status },
    ],
  }
}

/** BSI-Antwortmodell in Worten — wie `wiba/constants.py` es beschriftet. */
const WIBA_ANTWORT: Record<string, string> = {
  offen: 'Offen', ja: 'Ja', nein: 'Nein', nicht_relevant: 'Nicht relevant',
}

/** WiBA-Prüffragen — BSI-Antwortmodell, kein Score. */
export function wibaKiAdapter(projekt: string): KiBewertungsAdapter {
  const basis = (id: string | number) =>
    `/wiba/projekte/${enc(projekt)}/controls/${enc(String(id))}`
  return {
    modul: 'wiba',
    herkunftArt: 'wiba_control',
    objektPfad: 'controls',
    wertLabel: 'Antwort',
    freitext: 'die Notiz',
    schemaHinweis:
      'Antwort als JSON: { "status": "ja|nein|nicht_relevant", "notiz": "…", "empfehlung": "…" }',
    zusatzBeispiel: 'z. B. „Der Betrieb ist ausgelagert, Nachweise liegen beim Dienstleister."',
    sensibel: [],
    einstiege: { prompt: true, auto: true, neubewertung: true },
    ziel: 'Befüllt Antwort und Notiz der Prüffrage.',
    wirkung: 'Überschreibt die aktuelle Antwort nach dem Übernehmen.',
    // WiBA baut den Prompt serverseitig aus Nachweisen — deshalb POST mit Body.
    promptMethode: 'post',
    promptUrl: id => `${basis(id)}/prompt`,
    parseUrl: id => `${basis(id)}/parse-response`,
    streamUrl: id => `/api${basis(id)}/auto-bewertung/stream`,
    vorschau: o => [
      { label: 'Projekt', value: projekt },
      { label: 'Prüffrage', value: o?.control_id || o?.id },
      { label: 'Frage', value: o?.frage },
      // Das Label, nicht den Rohwert: In der Daten-Vorschau steht, was der
      // Anwender in seiner Maske sieht, nicht was in der Spalte steht.
      { label: 'Aktuelle Antwort', value: WIBA_ANTWORT[String(o?.status || 'offen')]
        ?? o?.status },
      // Die Vorschau ist das Egress-Tor (#868/#1840) — sie muss nennen, dass
      // **Firmen-Nachweise** mitgehen, nicht nur die Frage. Der Prompt wird
      // serverseitig aus ihnen gebaut, der Anwender sieht sie hier zuerst.
      { label: 'Nachweise', value: 'Bei der Firma hochgeladene Nachweise (Auszüge)' },
    ],
  }
}

/** Risikobewertung — Risikowert statt Score, eigener Stream-Pfad. */
export function risikoKiAdapter(projekt: string): KiBewertungsAdapter {
  const basis = (id: string | number) =>
    `/risikobewertung/projekte/${enc(projekt)}/risiken/${enc(String(id))}`
  return {
    modul: 'risikobewertung',
    herkunftArt: 'risk',
    objektPfad: 'risiken',
    wertLabel: 'Risiko',
    freitext: 'die Bewertung',
    schemaHinweis: 'Antwort als JSON: { "felder": { … }, "bewertung": "…" }',
    zusatzBeispiel: 'z. B. „Die Anlage ist nicht aus dem Internet erreichbar."',
    sensibel: ['Beschreibung'],
    // `neubewertung` ist hier **aus**, und das ist kein Rückschritt: Die
    // Risikobewertung hat einen **eigenen**, reicheren Weg
    // (`…/re-assessment/stream` mit `build_re_assessment_prompt`, dazu
    // Risikoveränderung, Begründung, Empfehlungen und CRA-Bezug im Ergebnis,
    // plus einen Copy/Paste-Zweig über `re-assessment-prompt`). Der gemeinsame
    // Weg schickt `{use_issue_feedback: true}` an `ollama/stream` — und
    // **dieser Endpunkt liest das Feld nicht**. Der Knopf hätte also gestartet,
    // sauber durchgelaufen und das Issue-Feedback stillschweigend weggelassen:
    // genau der „Zustand, den niemand liest" aus #1840. Der Name kommt
    // trotzdem aus dem Katalog, die Maske behält nur ihre Mechanik.
    einstiege: { prompt: true, auto: true, neubewertung: false },
    ziel: 'Befüllt die Bewertungsfelder, den Risikowert und die Bewertung.',
    wirkung: 'Überschreibt die aktuelle Risikobewertung nach dem Übernehmen.',
    promptMethode: 'get',
    promptUrl: id => `${basis(id)}/prompt`,
    parseUrl: id => `${basis(id)}/parse-response`,
    // Historisch `ollama/stream` — der Pfad ist älter als die Engine (#1841).
    streamUrl: id => `/api${basis(id)}/ollama/stream`,
    vorschau: o => [
      { label: 'Projekt', value: projekt },
      { label: 'Risiko', value: o?.nr ? `#${o.nr}` : o?.id },
      { label: 'Bezeichnung', value: o?.risk_name },
      { label: 'Beschreibung', value: o?.beschreibung },
      { label: 'Aktueller Risikowert', value: o?.risikowert ?? '—' },
    ],
  }
}
