import { createI18n } from 'vue-i18n'
import { alsFunktionen, type Baum } from './kompilierer'

/**
 * Die Zweisprachigkeit der Oberfläche (#1954).
 *
 * DIE TEXTE LIEGEN ALS JSON, NICHT ALS TYPESCRIPT
 * Bis 8.3.4 standen sie in `de.ts`/`en.ts` — je 62 Zeilen, fünf Gruppen, und
 * benutzt wurden sie von genau **einer** der 178 Masken (dem Umschalter
 * selbst). Für eine vollständige Übersetzung werden es einige Tausend; dafür
 * ist TypeScript das falsche Format, aus einem Grund, der nichts mit Geschmack
 * zu tun hat: **ein Wächtertest muss die Kataloge lesen können.**
 *
 * `strictTemplates` ist aus (`tsconfig.json` begründet das), also prüft
 * `vue-tsc` einen Aufruf `$t('cra.releases.titel')` **nicht** — ein Tippfehler
 * im Schlüssel und ein in der englischen Fassung fehlender Text sehen beide
 * gleich aus: In der Oberfläche steht der Rohschlüssel. Kein bestehender
 * Prüfer fängt das. `tests/test_i18n_katalog_1954.py` tut es, und zwar indem
 * er die JSON-Dateien beider Sprachen lädt und gegeneinander hält. Mit
 * TypeScript-Dateien hätte er parsen müssen, was auf Zeichenketten-Regeln
 * hinausläuft — dieselbe Schwäche, die der alte Platzhalter-Wächter hatte
 * (er sah nur Werte am Zeilenende).
 *
 * KEINE SPIEGEL-LISTE DER DATEINAMEN
 * Die Gruppen werden mit `import.meta.glob` eingesammelt, nicht einzeln
 * importiert. Eine neue Gruppe `de/pentest.json` ist damit sofort dabei, und
 * es gibt keine Liste, die beim nächsten Mal vergessen wird (#1731/#1735).
 * Der Dateiname **ist** der Namensraum: `de/cra.json` → `cra.*`.
 *
 * WARUM `alsFunktionen` BLEIBT
 * Die CSP ist `script-src 'self'` ohne `unsafe-eval`; vue-i18n würde
 * Nachrichten sonst zur Laufzeit mit `new Function()` übersetzen (#1816).
 * Die Nachrichten kommen deshalb als fertige Funktionen. Neu ist nur, dass
 * `kompilierer.ts` dabei **Platzhalter** beherrscht — ohne Codeerzeugung.
 * Der Alias auf `vue-i18n.runtime.esm-bundler.js` in `vite.config.ts` bleibt
 * notwendig und richtig.
 */

export type LocaleCode = 'de' | 'en'

/** Die Sprachen, die es gibt. Eine Stelle — Umschalter und Wächter lesen sie. */
export const SPRACHEN: readonly LocaleCode[] = ['de', 'en'] as const

/** Was gilt, wenn nichts gewählt und nichts erkennbar ist. */
export const STANDARD: LocaleCode = 'de'

const STORAGE_KEY = 'aics_locale'

/**
 * Baut aus den Dateien eines Sprachverzeichnisses den Nachrichtenbaum.
 *
 * `import.meta.glob` liefert `{'./de/cra.json': {...}, …}`; der Dateiname
 * ohne Endung wird der Namensraum.
 */
function katalog(gruppen: Record<string, unknown>): Baum {
  const baum: Baum = {}
  for (const [pfad, inhalt] of Object.entries(gruppen)) {
    const name = pfad.replace(/^.*\/([^/]+)\.json$/, '$1')
    baum[name] = inhalt as Baum
  }
  return baum
}

const de = katalog(import.meta.glob('./de/*.json', { eager: true, import: 'default' }))
const en = katalog(import.meta.glob('./en/*.json', { eager: true, import: 'default' }))

function istSprache(wert: unknown): wert is LocaleCode {
  return typeof wert === 'string' && (SPRACHEN as readonly string[]).includes(wert)
}

function erkenneSprache(): LocaleCode {
  let gespeichert: string | null = null
  try {
    gespeichert = localStorage.getItem(STORAGE_KEY)
  } catch {
    // Privates Fenster, gesperrte Website-Daten: dann eben die Erkennung.
  }
  if (istSprache(gespeichert)) return gespeichert
  const navigatorSprache = (navigator.language || STANDARD).slice(0, 2).toLowerCase()
  return istSprache(navigatorSprache) ? navigatorSprache : STANDARD
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: erkenneSprache(),
  fallbackLocale: STANDARD,
  // Ein fehlender Schlüssel ist ein Mangel, kein Betriebsereignis: Er soll in
  // der Entwicklung auffallen, aber im Betrieb nicht die Konsole fluten.
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
  messages: { de: alsFunktionen(de), en: alsFunktionen(en) } as never,
})

export function setLocale(code: LocaleCode) {
  // @ts-ignore — legacy: false → typisierte Ref
  i18n.global.locale.value = code
  try {
    localStorage.setItem(STORAGE_KEY, code)
  } catch {
    // Nicht speicherbar: die Wahl gilt für diese Sitzung. Besser als ein Fehler.
  }
  document.documentElement.setAttribute('lang', code)
}

export function getLocale(): LocaleCode {
  // @ts-ignore
  return i18n.global.locale.value as LocaleCode
}

/**
 * Übersetzt ausserhalb einer Komponente (Stores, Hilfsmodule, Abfangjäger).
 *
 * In einer Komponente gilt `$t(...)` im Template bzw. `useI18n()` im Skript —
 * nur dort wird die Anzeige bei einem Sprachwechsel neu gezeichnet. Diese
 * Funktion ist für die Stellen, die keine Komponente sind.
 */
export function t(schluessel: string, werte?: Record<string, unknown> | unknown[]): string {
  // @ts-ignore — die Überladungen von vue-i18n treffen diesen Aufruf nicht.
  return werte === undefined ? i18n.global.t(schluessel) : i18n.global.t(schluessel, werte)
}
