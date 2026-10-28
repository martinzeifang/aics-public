import { createI18n } from 'vue-i18n'
import de from './de'
import en from './en'

/**
 * Nachrichten als fertige Funktionen übergeben (#1816).
 *
 * vue-i18n übersetzt Nachrichten sonst **zur Laufzeit** mit `new Function()`.
 * Die Content-Security-Policy der Anwendung ist `script-src 'self'` ohne
 * `unsafe-eval` — der Aufruf wird blockiert, und auf jeder Seite nach dem
 * Login stand derselbe Konsolenfehler. Betroffene Texte fielen still auf den
 * Rohwert zurück, und das Dauerrauschen verdeckte echte Fehler.
 *
 * `unsafe-eval` in die CSP aufzunehmen wäre die bequeme Lösung gewesen und
 * hätte eine Härtung aufgegeben, die überall sonst trägt. Stattdessen bekommt
 * vue-i18n, was es sonst selbst erzeugt: je Text eine Funktion. Das geht hier,
 * weil die Texte **keine Platzhalter** enthalten — `tests/test_funde_1814_1817.py`
 * wacht darüber. Kommt einmal ein `{name}` dazu, ist der
 * Weg die Vorkompilierung über `@intlify/unplugin-vue-i18n`.
 */
type Baum = { [k: string]: string | Baum }
function alsFunktionen(o: Baum): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(o)) {
    out[k] = typeof v === 'string' ? () => v : alsFunktionen(v as Baum)
  }
  return out
}

export type LocaleCode = 'de' | 'en'

const STORAGE_KEY = 'aics_locale'

function detectInitialLocale(): LocaleCode {
  const stored = localStorage.getItem(STORAGE_KEY) as LocaleCode | null
  if (stored === 'de' || stored === 'en') return stored
  const nav = (navigator.language || 'de').slice(0, 2).toLowerCase()
  return nav === 'en' ? 'en' : 'de'
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: detectInitialLocale(),
  fallbackLocale: 'de',
  messages: { de: alsFunktionen(de as Baum), en: alsFunktionen(en as Baum) } as never,
})

export function setLocale(code: LocaleCode) {
  // @ts-ignore — legacy: false → typed Ref
  i18n.global.locale.value = code
  localStorage.setItem(STORAGE_KEY, code)
  document.documentElement.setAttribute('lang', code)
}

export function getLocale(): LocaleCode {
  // @ts-ignore
  return i18n.global.locale.value as LocaleCode
}
