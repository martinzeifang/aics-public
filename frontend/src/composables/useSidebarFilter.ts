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
 *
 * Bei aktiver Suche sind alle Gruppen zwangsweise offen — sonst versteckt ein
 * eingeklappter Zustand genau den Treffer, den man sucht.
 */
import { ref, computed, type Ref } from 'vue'

const STORAGE_PREFIX = 'aics.sidebar.collapsed.'

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
}

/**
 * @param storageKey stabiler Schlüssel je Sidebar (z. B. `'cra'`), damit sich
 *                   die Module den Einklapp-Zustand nicht gegenseitig überschreiben.
 */
export function useSidebarFilter(storageKey: string): SidebarFilter {
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

  return { suche, suchtGerade, matches, istEingeklappt, toggleGruppe, alleAufklappen, alleEinklappen }
}
