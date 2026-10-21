import { createI18n } from 'vue-i18n'
import de from './de'
import en from './en'

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
  messages: { de, en },
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
