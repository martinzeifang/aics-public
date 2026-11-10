import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { getLocale } from '../i18n'

const apiClient = axios.create({
  baseURL: '/api',
  // 10s war zu knapp: das SPA feuert beim Projekt-/Tab-Wechsel ~10 parallele
  // Calls; unter Last (v.a. der Dev-Server) brauchen spätere Requests mehrere
  // Sekunden → liefen sonst in Status-0/Timeout (Dropdown/Nachweis lud nicht).
  // In Produktion sind Requests <1s, daher unkritisch.
  timeout: 30000,
})

// Request interceptor to add token
apiClient.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  // #1954: Die Sprachwahl des Anwenders mitschicken.
  //
  // Bis 8.3.4 verliess sie den Browser nie — sie stand in
  // `localStorage['aics_locale']` und wurde nur fürs `<html lang>`-Attribut
  // gelesen. Damit konnte der Server nicht wissen, in welcher Sprache er
  // antworten soll, und seine Meldungen waren zwangsläufig deutsch, auch in
  // einer englischen Oberfläche.
  //
  // `Accept-Language` und keine eigene Kopfzeile: Es ist die vorgesehene
  // Stelle, es ist CORS-safelisted (also ohne Vorabanfrage), und wer die API
  // mit `curl` bedient, bekommt dasselbe Verhalten ohne etwas über eine
  // hauseigene Kopfzeile zu wissen. Geschickt wird die **ausdrückliche Wahl**
  // des Anwenders, nicht die Browsereinstellung — wer auf EN umstellt, will
  // auch die Fehlermeldungen auf Englisch. Fehlt die Kopfzeile (alter
  // Bundle-Stand), liest der Server die Browsereinstellung und landet für
  // einen deutschen Anwender auf Deutsch; also derselbe Stand wie vorher.
  //
  // Das ist ausdrücklich die Sprache des **Bearbeiters**, nicht die des
  // Mandanten: Berichte, Dokumente und KI-Antworten folgen `firmen.sprache`
  // und werden serverseitig aufgelöst (`shared/sprache.py`).
  try {
    config.headers['Accept-Language'] = getLocale()
  } catch {
    // Eine fehlgeschlagene Spracherkennung darf keinen Request verhindern.
  }
  return config
}, (error) => {
  return Promise.reject(error)
})

// 401 wird global in main.ts via install401Interceptor() behandelt —
// hier nur Request-Header-Setup.

export default apiClient
