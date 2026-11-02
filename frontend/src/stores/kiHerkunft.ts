/**
 * KI-Herkunft-Store (#1765) — Anzeige und fachliche Prüfung KI-erzeugter Inhalte.
 *
 * Bis v8.0.0 stand der Vorbehalt „— 🤖 KI-generiert (…) — fachlich zu prüfen."
 * **im gespeicherten Text** und damit in jedem Bericht, bis hin zur
 * Konformitätserklärung. Seit #1765 liegt die Herkunft in einem eigenen
 * Register (`shared/ki_herkunft.py`); die Prüfung findet **in der Anwendung**
 * statt. Dieser Store ist die Frontend-Seite davon.
 *
 * WARUM EINE KARTE JE (MODUL, PROJEKT, ART)
 * Der Hinweis hängt an jeder einzelnen Anforderung/Prüffrage/Risiko. Würde
 * jede Zeile ihren Status selbst holen, wären das bei 32 CRA-Anforderungen 32
 * Abfragen für eine Information, die das Backend in einem Zug liefert. Der
 * Store lädt deshalb die ganze Karte einmal und aktualisiert nach einer
 * Prüfung nur den einen Eintrag.
 *
 * Objekte ohne Eintrag fehlen in `items` — das heißt „nicht KI-erzeugt", also
 * nichts anzuzeigen.
 */
import { defineStore } from 'pinia'
import apiClient from '../api/client'

/** Objektarten, über die das Register adressiert wird. */
export type KiArt = 'requirement' | 'owasp' | 'owasp_llm' | 'wiba_control' | 'risk'

/** Herkunfts-/Prüfstatus eines einzelnen Objekts. */
export interface KiHerkunftStatus {
  /** Immer true, wenn ein Eintrag existiert (= der Inhalt kam von einer KI). */
  ki: boolean
  /** Hat ein Mensch die fachliche Prüfung bestätigt? */
  geprueft: boolean
  /** Anbieter, der den Inhalt erzeugt hat (z. B. „ollama", „cloud"). */
  provider: string
  erzeugt_am: string
  geprueft_von: string
  geprueft_am: string | null
}

/** Pro-Schlüssel-State (modul:projekt:art). */
interface KeyState {
  items: Record<string, KiHerkunftStatus>
  loading: boolean
  /** Einmal geladen? Verhindert erneutes Laden je Zeile. */
  loaded: boolean
  /** Zeitpunkt des letzten Ladens (ms) — für das Verfallsalter. */
  stand: number
  error: string | null
}

/**
 * Verfallsalter der Karte in Millisekunden.
 *
 * „Einmal laden" darf nicht „nie wieder laden" heißen: eine Massenbewertung
 * erzeugt Einträge, von denen eine für die ganze Sitzung gecachte Karte nichts
 * wüsste — der Hinweis fehlte dann genau dort, wo er am nötigsten ist. Mit dem
 * Verfallsalter revalidiert die Karte beim nächsten Öffnen eines Objekts; die
 * gleichzeitig mountenden Badges einer Liste teilen sich weiter eine Abfrage.
 */
const MAX_ALTER_MS = 15_000

interface KiHerkunftState {
  byKey: Record<string, KeyState>
}

function makeKey(modul: string, projekt: string, art: string): string {
  return `${modul}:${projekt}:${art}`
}

function emptyKeyState(): KeyState {
  return { items: {}, loading: false, loaded: false, stand: 0, error: null }
}

/**
 * Laufende Abfragen je Schlüssel. Bewusst **außerhalb** des Pinia-State:
 * Promises gehören nicht in reaktive Daten, und mehrere gleichzeitig
 * gemountete Badges derselben Karte sollen sich eine Abfrage teilen.
 */
const inFlight = new Map<string, Promise<void>>()

function base(modul: string, projekt: string): string {
  return `/${modul}/projekte/${encodeURIComponent(projekt)}/ki-herkunft`
}

function extractError(e: any, fallback: string): string {
  return e?.response?.data?.error || e?.message || fallback
}

export const useKiHerkunftStore = defineStore('kiHerkunft', {
  state: (): KiHerkunftState => ({ byKey: {} }),

  getters: {
    /** Liefert (ohne Seiteneffekt) den State-Slice für modul:projekt:art. */
    keyState: (state) => {
      return (modul: string, projekt: string | null, art: string): KeyState => {
        if (!projekt) return emptyKeyState()
        return state.byKey[makeKey(modul, projekt, art)] ?? emptyKeyState()
      }
    },

    /** Status eines einzelnen Objekts — `null` heißt „nicht KI-erzeugt". */
    statusFor: (state) => {
      return (
        modul: string,
        projekt: string | null,
        art: string,
        objektId: string,
      ): KiHerkunftStatus | null => {
        if (!projekt || !objektId) return null
        const slice = state.byKey[makeKey(modul, projekt, art)]
        return slice?.items?.[objektId] ?? null
      }
    },
  },

  actions: {
    /** Stellt sicher, dass ein State-Slice existiert, und gibt ihn zurück. */
    _ensure(modul: string, projekt: string, art: string): KeyState {
      const key = makeKey(modul, projekt, art)
      if (!this.byKey[key]) this.byKey[key] = emptyKeyState()
      return this.byKey[key]
    },

    /** Holt die Karte vom Backend (ohne Cache-Prüfung). */
    async _laden(modul: string, projekt: string, art: string): Promise<void> {
      const slice = this._ensure(modul, projekt, art)
      slice.loading = true
      slice.error = null
      try {
        const r = await apiClient.get(base(modul, projekt), { params: { art } })
        const items = r.data?.items
        slice.items = items && typeof items === 'object' ? items : {}
        slice.loaded = true
        slice.stand = Date.now()
      } catch (e: any) {
        slice.error = extractError(e, 'KI-Herkunft konnte nicht geladen werden.')
      } finally {
        slice.loading = false
      }
    },

    /**
     * Lädt die Karte **einmal** je (modul, projekt, art). Gleichzeitige
     * Aufrufe (ein Badge je Zeile) teilen sich dieselbe Abfrage; eine noch
     * frische Karte (siehe `MAX_ALTER_MS`) wird gar nicht erst abgefragt.
     */
    async ensureKarte(modul: string, projekt: string, art: string): Promise<void> {
      if (!modul || !projekt || !art) return
      const key = makeKey(modul, projekt, art)
      const slice = this._ensure(modul, projekt, art)
      if (slice.loaded && Date.now() - slice.stand < MAX_ALTER_MS) return
      const laufend = inFlight.get(key)
      if (laufend) return laufend
      const p = this._laden(modul, projekt, art).finally(() => inFlight.delete(key))
      inFlight.set(key, p)
      return p
    },

    /**
     * Lädt die Karte neu. Nach einer frisch gespeicherten KI-Bewertung nötig,
     * damit der Hinweis ohne Neuladen der Seite erscheint.
     */
    async reload(modul: string, projekt: string | null, art: string): Promise<void> {
      if (!modul || !projekt || !art) return
      const key = makeKey(modul, projekt, art)
      const slice = this._ensure(modul, projekt, art)
      slice.loaded = false
      const laufend = inFlight.get(key)
      if (laufend) return laufend
      const p = this._laden(modul, projekt, art).finally(() => inFlight.delete(key))
      inFlight.set(key, p)
      return p
    },

    /**
     * Bestätigt die fachliche Prüfung eines Objekts.
     *
     * Aktualisiert bei Erfolg nur den einen Eintrag — die Karte wird nicht
     * neu geladen, weil das Backend den fertigen Status zurückgibt.
     * Liefert `null` bei Fehler; die Meldung steht in `keyState(...).error`.
     */
    async alsGeprueftMarkieren(
      modul: string,
      projekt: string,
      art: string,
      objektId: string,
    ): Promise<KiHerkunftStatus | null> {
      const slice = this._ensure(modul, projekt, art)
      slice.error = null
      try {
        const url =
          `${base(modul, projekt)}/${encodeURIComponent(art)}` +
          `/${encodeURIComponent(objektId)}/geprueft`
        const r = await apiClient.post(url, {})
        const status: KiHerkunftStatus | null = r.data?.status ?? null
        if (status) {
          slice.items = { ...slice.items, [objektId]: status }
        } else {
          // Kein Status in der Antwort (soll nicht vorkommen) → Karte neu holen,
          // damit die Anzeige nicht auf einem veralteten Stand stehen bleibt.
          await this.reload(modul, projekt, art)
        }
        return status
      } catch (e: any) {
        if (e?.response?.status === 404) {
          // Kein Eintrag (mehr) — es gibt nichts zu prüfen. Eintrag entfernen,
          // damit der Hinweis verschwindet statt endlos zu scheitern.
          const { [objektId]: _weg, ...rest } = slice.items
          slice.items = rest
          return null
        }
        slice.error = extractError(e, 'Prüfung konnte nicht bestätigt werden.')
        return null
      }
    },
  },
})
