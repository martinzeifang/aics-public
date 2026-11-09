import { getLocale, SPRACHEN, STANDARD, type LocaleCode } from '../i18n'
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

/**
 * Registry der Modul-Hilfe (#926/#927), zweisprachig seit #1954.
 *
 * DIE INHALTE LIEGEN ALS JSON, NICHT ALS TYPESCRIPT
 * Bis 8.3.4 stand jedes Modul als `help/<modul>.ts` da — acht davon mit dem
 * Kopf „Auto-generiert (#926)" und einem reinen Datenobjekt darin. Das waren
 * **1.353 Texte**, der größte einzelne Posten der Übersetzung, und sie sind
 * fachlicher Inhalt: Rechtsgrundlagen, Pflichtfelder, Anleitungen. Für so
 * etwas ist TypeScript das falsche Format, aus demselben Grund wie in
 * `i18n/index.ts`: **ein Wächtertest muss die Inhalte lesen können**, um
 * Parität und Struktur zwischen den Sprachen zu halten.
 *
 * WARUM NICHT ÜBER vue-i18n
 * Das wäre der naheliegende Weg und der falsche. Die Hilfe ist kein Vorrat von
 * Beschriftungen, sondern ein **Dokument** mit Listen beliebiger Länge
 * (`bullets`, `pflichtfelder`, `tipps`, `areas`). Über `t()` bräuchte jeder
 * Eintrag einen eigenen Schlüssel — 1.353 davon —, und die Länge einer Liste
 * ließe sich nicht mehr aus den Daten ablesen, sondern nur noch erraten. Die
 * Struktur gehört hier zum Inhalt; sie darf nicht in Schlüsselnamen zerfallen.
 *
 * RÜCKFALL JE MODUL, NICHT JE TEXT
 * Fehlt eine Sprachfassung, gilt die deutsche — **ganz**, nicht gemischt. Ein
 * Dokument, dessen Abschnitte in zwei Sprachen stehen, liest sich wie ein
 * Fehler; eine durchgehend deutsche Hilfe in einer englischen Oberfläche liest
 * sich wie eine fehlende Übersetzung, und genau das wäre dann der Fall.
 * `fehlendeSprachfassungen()` benennt die Lücke, statt sie zu verbergen.
 */

type Rohdaten = Record<string, unknown>

/**
 * Die Kataloge einsammeln. `eager` ist Absicht: Die Hilfe wird aus dem Dialog
 * **synchron** gelesen, und ein Modul, dessen Datei erst nachgeladen wird,
 * zeigt beim ersten Öffnen eine leere Hilfe.
 */
const KATALOGE: Record<LocaleCode, Record<string, Rohdaten>> = {
  de: sammle(import.meta.glob('./de/*.json', { eager: true, import: 'default' })),
  en: sammle(import.meta.glob('./en/*.json', { eager: true, import: 'default' })),
}

function sammle(gruppen: Record<string, unknown>): Record<string, Rohdaten> {
  const out: Record<string, Rohdaten> = {}
  for (const [pfad, inhalt] of Object.entries(gruppen)) {
    const name = pfad.split('/').pop()!.replace(/\.json$/, '')
    out[name] = inhalt as Rohdaten
  }
  return out
}

/** Dateiname im Katalog → Modulschlüssel der Anwendung. */
const DATEI_JE_MODUL: Record<string, string> = {
  cra: 'cra',
  nis2: 'nis2',
  aiact: 'aiact',
  dsgvo: 'dsgvo',
  gutachten: 'gutachten',
  'compliance-audit': 'complianceAudit',
  risikobewertung: 'risikobewertung',
  firmen: 'firmen',
  wiba: 'wiba',
}

/** Alle Module, für die es überhaupt eine Hilfe gibt. */
export const HELP_MODULE = Object.keys(DATEI_JE_MODUL)

/**
 * `"docs:/modules/wiba/"` → die öffentliche Doku-Adresse.
 *
 * Im Katalog steht nur der Pfad: Sonst stünde die Domain neunmal im
 * Datenbestand und müsste bei einem Umzug an neun Stellen nachgezogen werden
 * (#1731/#1735). `docsUrl` ist weiter die einzige Stelle, die sie kennt.
 */
const DOCS_MARKE = 'docs:'

function adressen(wert: unknown): unknown {
  if (typeof wert === 'string') {
    return wert.startsWith(DOCS_MARKE)
      ? docsUrl(wert.slice(DOCS_MARKE.length))
      : wert
  }
  if (Array.isArray(wert)) return wert.map(adressen)
  if (wert && typeof wert === 'object') {
    const out: Rohdaten = {}
    for (const [k, v] of Object.entries(wert as Rohdaten)) out[k] = adressen(v)
    return out
  }
  return wert
}

/**
 * Die Hilfe eines Moduls in der Anzeigesprache.
 *
 * Die Sprache wird **beim Aufruf** gelesen und nicht beim Laden des Moduls —
 * sonst zeigte der Dialog die Sprache, die beim ersten Import galt. Der
 * Aufrufer muss den Aufruf in ein `computed` legen, damit der Wechsel ohne
 * Neuladen ankommt; `ModuleHelpDialog` tut das.
 */
export function getModuleHelp(module: string,
                              sprache?: LocaleCode): ModuleHelp | null {
  const datei = DATEI_JE_MODUL[module]
  if (!datei) return null
  const code = sprache || getLocale()
  const roh = KATALOGE[code]?.[datei] || KATALOGE[STANDARD]?.[datei]
  if (!roh) return null
  return adressen(roh) as ModuleHelp
}

/**
 * Welche Module haben für welche Sprache noch keine Fassung?
 *
 * Eine benannte Lücke ist etwas anderes als eine stillschweigende: Der
 * Wächtertest liest das hier und lässt rot werden, was **unerwartet** fehlt
 * (die Lehre aus #1878 — eine Positivliste braucht einen Prüfer in beide
 * Richtungen).
 */
export function fehlendeSprachfassungen(): Record<LocaleCode, string[]> {
  const out = {} as Record<LocaleCode, string[]>
  for (const code of SPRACHEN) {
    out[code] = HELP_MODULE.filter(
      (m) => !KATALOGE[code]?.[DATEI_JE_MODUL[m]])
  }
  return out
}

// Öffentliche Doku-URL + Helper (#1011) — hier erneut herausgegeben.
//
// **Nicht** als `export { docsUrl } from './docsUrl'`: Das reicht den Namen
// durch und legt in dieser Datei **keine** Bindung an — `adressen()` benutzt
// ihn aber, und das wäre zur Laufzeit ein ReferenceError. Der Build bleibt
// dabei grün (die Lehre aus #1854); gefunden hat es
// `test_reexport_ohne_bindung_1854`.
export { PUBLIC_DOCS_BASE_URL } from './docsUrl'
export { docsUrl }

export type { ModuleHelp } from './types'
