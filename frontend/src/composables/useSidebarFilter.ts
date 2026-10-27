/**
 * Geteilte Such-/Gruppierungs-Logik für die Modul-Sidebars (#1710).
 *
 * Die Sidebars waren flache, ungefilterte Listen. Bei einem Wholesale-Bestand
 * mit 50+ Mandanten und mehreren Projekten je Mandant ist das nicht mehr
 * bedienbar: man scrollt an jedem Projekt vorbei, das man nicht sucht.
 *
 * Diese Composable liefert beides zentral:
 *  - `suche`      — Freitext, mehrere Begriffe werden UND-verknüpft
 *  - `matches()`  — prüft beliebig viele Felder eines Eintrags gegen die Suche
 *  - Einklappen je Firmen-Gruppe, **persistiert** in localStorage, damit die
 *    gewohnte Arbeitsansicht einen Reload übersteht.
 *  - `sortierung` + `filter` (#1764) — ebenfalls persistiert: wer nach „zuletzt
 *    geändert" sortiert, will das beim nächsten Öffnen wieder so haben.
 *
 * Bei aktiver Suche sind alle Gruppen zwangsweise offen — sonst versteckt ein
 * eingeklappter Zustand genau den Treffer, den man sucht.
 *
 * Die Composable wird von neun Sidebars genutzt — Erweiterungen sind daher
 * **additiv**: `sortierung`/`filter` sind optional und wirken nur dort, wo eine
 * Sidebar sie tatsächlich auswertet.
 */
import { ref, computed, type Ref } from 'vue'

const STORAGE_PREFIX = 'aics.sidebar.collapsed.'
const SORT_PREFIX = 'aics.sidebar.sort.'
const FILTER_PREFIX = 'aics.sidebar.filter.'

/** Normalisiert für den Vergleich: klein, getrimmt, Mehrfach-Leerzeichen weg. */
export function normalizeSuche(value: unknown): string {
  return String(value ?? '')
    .toLocaleLowerCase('de-DE')
    .replace(/\s+/g, ' ')
    .trim()
}

/** True, wenn **alle** Suchbegriffe in mindestens einem der Felder vorkommen. */
export function matchesSuche(needle: string, ...felder: unknown[]): boolean {
  const q = normalizeSuche(needle)
  if (!q) return true
  const haystack = felder.map((f) => normalizeSuche(f)).join(' \u0001 ')
  return q.split(' ').every((term) => haystack.includes(term))
}

function ladeEingeklappt(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + key)
    const parsed = raw ? JSON.parse(raw) : null
    return new Set(Array.isArray(parsed) ? parsed.map(String) : [])
  } catch {
    // Private-Mode / blockierte Site-Daten → einfach alles offen.
    return new Set()
  }
}

function speichereEingeklappt(key: string, werte: Set<string>): void {
  try {
    localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify([...werte]))
  } catch {
    /* ignorieren — die Ansicht funktioniert auch ohne Persistenz */
  }
}

/** Liest einen persistierten Rohwert; jeder Fehler bedeutet „nichts gemerkt". */
function ladeRoh(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    // Privates Fenster / blockierte Site-Daten → Default verwenden.
    return null
  }
}

function speichereRoh(key: string, wert: string): void {
  try {
    localStorage.setItem(key, wert)
  } catch {
    /* ignorieren — die Ansicht funktioniert auch ohne Persistenz */
  }
}

/**
 * Gemerkte Sortierung laden. `erlaubt` schützt vor Altlasten: verschwindet ein
 * Sortier-Schlüssel wieder aus dem Code, fällt die Sidebar auf den Default
 * zurück statt nach einem unbekannten Kriterium zu sortieren.
 */
function ladeSortierung(key: string, standard: string, erlaubt: string[]): string {
  const roh = ladeRoh(SORT_PREFIX + key)
  if (!roh) return standard
  if (erlaubt.length > 0 && !erlaubt.includes(roh)) return standard
  return roh
}

/** Gemerkte Filter laden; nur die im Code bekannten Schlüssel werden übernommen. */
function ladeFilter(key: string, standard: Record<string, string>): Record<string, string> {
  const roh = ladeRoh(FILTER_PREFIX + key)
  const out: Record<string, string> = { ...standard }
  if (!roh) return out
  try {
    const parsed = JSON.parse(roh)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      for (const k of Object.keys(standard)) {
        const v = (parsed as Record<string, unknown>)[k]
        if (typeof v === 'string') out[k] = v
      }
    }
  } catch {
    /* defekter Eintrag → Default */
  }
  return out
}

export interface SidebarSortFilterOptionen {
  /** Vorbelegte Sortierung (Default-Reihenfolge der Sidebar). */
  sortierung?: string
  /** Erlaubte Sortier-Schlüssel — alles andere fällt auf den Default zurück. */
  sortSchluessel?: string[]
  /** Bekannte Filter-Schlüssel mit Default-Wert (`''` = kein Filter aktiv). */
  filter?: Record<string, string>
}

export interface SidebarFilter {
  /** Freitext-Suche (v-model-fähig). */
  suche: Ref<string>
  /** True, solange ein Suchbegriff aktiv ist. */
  suchtGerade: Ref<boolean>
  /** Prüft einen Eintrag gegen die Suche. */
  matches: (...felder: unknown[]) => boolean
  /** Ist diese Gruppe eingeklappt? (bei aktiver Suche immer `false`) */
  istEingeklappt: (gruppe: string) => boolean
  /** Gruppe auf-/zuklappen. */
  toggleGruppe: (gruppe: string) => void
  /** Alle Gruppen aufklappen. */
  alleAufklappen: () => void
  /** Die genannten Gruppen einklappen. */
  alleEinklappen: (gruppen: string[]) => void
  /** Gewählte Sortierung (#1764), persistiert. */
  sortierung: Ref<string>
  /** Sortierung setzen (ungültige Werte werden ignoriert). */
  setSortierung: (wert: string) => void
  /** Gewählte Filter (Schlüssel → Wert, `''` = aus), persistiert. */
  filter: Ref<Record<string, string>>
  /** Einen Filter setzen. */
  setFilter: (key: string, wert: string) => void
  /** Einen Ja/Nein-Filter umschalten (`''` ↔ `'1'`). */
  toggleFilter: (key: string) => void
  /** True, wenn mindestens ein Filter vom Default abweicht. */
  filterAktiv: Ref<boolean>
  /** Alle Filter auf den Default zurücksetzen (Sortierung bleibt). */
  resetFilter: () => void
}

/**
 * @param storageKey stabiler Schlüssel je Sidebar (z. B. `'cra'`), damit sich
 *                   die Module den Einklapp-Zustand nicht gegenseitig überschreiben.
 * @param optionen   optionale Sortier-/Filter-Defaults (#1764). Ohne Angabe
 *                   verhält sich die Composable genau wie vorher.
 */
export function useSidebarFilter(
  storageKey: string,
  optionen: SidebarSortFilterOptionen = {},
): SidebarFilter {
  const suche = ref('')
  const eingeklappt = ref<Set<string>>(ladeEingeklappt(storageKey))
  const suchtGerade = computed(() => normalizeSuche(suche.value).length > 0)

  const matches = (...felder: unknown[]) => matchesSuche(suche.value, ...felder)

  const istEingeklappt = (gruppe: string) =>
    !suchtGerade.value && eingeklappt.value.has(gruppe)

  const toggleGruppe = (gruppe: string) => {
    const next = new Set(eingeklappt.value)
    if (next.has(gruppe)) next.delete(gruppe)
    else next.add(gruppe)
    eingeklappt.value = next
    speichereEingeklappt(storageKey, next)
  }

  const alleAufklappen = () => {
    eingeklappt.value = new Set()
    speichereEingeklappt(storageKey, eingeklappt.value)
  }

  const alleEinklappen = (gruppen: string[]) => {
    const next = new Set(gruppen.map(String))
    eingeklappt.value = next
    speichereEingeklappt(storageKey, next)
  }

  // ---- Sortierung + Filter (#1764) ----

  const sortStandard = optionen.sortierung ?? ''
  const sortErlaubt = optionen.sortSchluessel ?? []
  const filterStandard = optionen.filter ?? {}

  const sortierung = ref(ladeSortierung(storageKey, sortStandard, sortErlaubt))
  const filter = ref<Record<string, string>>(ladeFilter(storageKey, filterStandard))

  const setSortierung = (wert: string) => {
    if (sortErlaubt.length > 0 && !sortErlaubt.includes(wert)) return
    sortierung.value = wert
    speichereRoh(SORT_PREFIX + storageKey, wert)
  }

  const setFilter = (key: string, wert: string) => {
    // Unbekannte Schlüssel ignorieren — sonst wandert Müll in localStorage.
    if (!(key in filterStandard)) return
    filter.value = { ...filter.value, [key]: wert }
    speichereRoh(FILTER_PREFIX + storageKey, JSON.stringify(filter.value))
  }

  const toggleFilter = (key: string) => {
    setFilter(key, filter.value[key] ? '' : '1')
  }

  const filterAktiv = computed(() =>
    Object.keys(filterStandard).some((k) => (filter.value[k] ?? '') !== (filterStandard[k] ?? '')),
  )

  const resetFilter = () => {
    filter.value = { ...filterStandard }
    speichereRoh(FILTER_PREFIX + storageKey, JSON.stringify(filter.value))
  }

  return {
    suche,
    suchtGerade,
    matches,
    istEingeklappt,
    toggleGruppe,
    alleAufklappen,
    alleEinklappen,
    sortierung,
    setSortierung,
    filter,
    setFilter,
    toggleFilter,
    filterAktiv,
    resetFilter,
  }
}
