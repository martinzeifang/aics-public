<!--
  SidebarWerkzeuge (#1856) — Suche, Sortierung und Filter einer Modul-Seitenleiste.

  DER BEFUND
  Die Leiste sah in vier von sechs Modulen anders aus: CRA und die
  Risikobewertung hatten Suche (ab 5 Einträgen), Sortierung und Filter — AI
  Act, WiBA, NIS2 und DSGVO hatten **nur** eine Suche, und die erst ab **acht**
  Einträgen. Praktisch heißt das: Auf einer Installation mit drei bis sieben
  Mandanten gab es dort kein einziges Bedienelement. Genau so sah die
  WiBA-Leiste im Funktionstest aus.

  Die Schwelle 8 stammt aus #1703/S7; CRA und die Risikobewertung sind mit
  #1764 auf 5 gegangen und haben Sortierung und Filter bekommen. Die übrigen
  vier blieben zurück — nicht entschieden, sondern übersehen.

  WARUM EIN BAUSTEIN UND NICHT VIERMAL DASSELBE
  Die Zusammenstellung „Suchfeld über Sortierleiste, beide an denselben
  Zustand gehängt" stand zweimal da und hätte sechsmal dastehen müssen. Das
  ist die Spiegel-Liste aus #1731/#1735: Beim nächsten Modul schreibt jemand
  eine Variante, und es fällt nicht auf, weil nichts fehlschlägt.

  WAS DIE KOMPONENTE NICHT TUT
  Sie filtert nichts. Wie `SidebarSearch` ist sie dumm: Sie zeigt an und meldet
  zurück. Die Auswertung bleibt dort, wo die Datenstruktur bekannt ist — in der
  jeweiligen Leiste.

  FILTER KOMMEN AUS DEN DATEN
  `filterFelder` beschreibt, welches Feld filterbar ist; die **Werte** liest
  diese Komponente aus den übergebenen Einträgen. Ein Feld mit weniger als zwei
  verschiedenen Werten wird **nicht angezeigt** — ein Auswahlfeld mit einer
  Option ist ein Bedienelement ohne Wirkung.
-->
<template>
  <template v-if="sichtbar">
    <SidebarSearch
      v-model="sucheModell"
      :placeholder="platzhalter"
      :treffer="treffer"
      :gesamt="gesamt"
      :einheit="einheit"
      :zeige-aufklappen="zeigeAufklappen"
      @expand-all="$emit('expand-all')"
    />
    <SidebarSortFilter
      :sortierung="sortierung"
      :sort-optionen="sortOptionen"
      :auswahlen="auswahlFelder"
      :schalter="schalter"
      :aktiv="filterAktiv"
      @update:sortierung="$emit('update:sortierung', $event)"
      @auswahl="$emit('auswahl', $event)"
      @schalter="$emit('schalter', $event)"
      @reset="$emit('reset')"
    />
  </template>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SidebarSearch from './SidebarSearch.vue'
import SidebarSortFilter from './SidebarSortFilter.vue'
import { SIDEBAR_WERKZEUGE_AB } from '../../composables/useSidebarFilter'

/** Ein filterbares Feld der Einträge. */
export interface FilterFeld {
  /** Schlüssel im Filter-Zustand **und** Feldname im Eintrag. */
  key: string
  /** Beschriftung, z. B. „Klasse". */
  label: string
  /** Wert → Anzeigetext. Fehlt eine Zuordnung, wird der Rohwert gezeigt. */
  labels?: Record<string, string>
}

const props = withDefaults(defineProps<{
  /** Die Einträge **vor** dem Filtern — Quelle der Filterwerte. */
  eintraege: any[]
  /** Aktueller Suchtext (v-model). */
  suche: string
  sortierung: string
  sortOptionen: { wert: string; label: string }[]
  /** Aktueller Filterzustand (`{ feld: wert }`). */
  filter?: Record<string, string>
  filterFelder?: FilterFeld[]
  /**
   * Fertige Auswahlfelder — gewinnen über `filterFelder`.
   *
   * Der Ausweg für Leisten, die ihre Werte besser kennen als die Daten: CRA
   * führt die Produktklassen als **feste** Liste (eine Klasse, die noch kein
   * Projekt hat, soll trotzdem wählbar sein), die Risikobewertung baut die
   * Framework-Liste mit eigener Beschriftung. Ohne diesen Ausweg müssten die
   * beiden bei ihrer eigenen Zusammenstellung bleiben — und dann gäbe es die
   * Leiste wieder zweimal.
   */
  auswahlen?: { key: string; label: string; wert: string;
                optionen: { wert: string; label: string }[] }[] | null
  /** Zusätzliche Ein/Aus-Filter, die die Leiste selbst rechnet. */
  schalter?: { key: string; label: string; aktiv: boolean; titel?: string }[]
  treffer: number
  platzhalter?: string
  einheit?: string
  zeigeAufklappen?: boolean
  /** Ab wie vielen Einträgen die Werkzeuge erscheinen (Vorgabe: der
   *  gemeinsame Wert aus `useSidebarFilter`). */
  schwelle?: number
  /** Noch am Laden — dann gibt es nichts zu durchsuchen. */
  laedt?: boolean
}>(), {
  filter: () => ({}),
  filterFelder: () => [],
  auswahlen: null,
  schalter: () => [],
  platzhalter: 'Suchen …',
  einheit: 'Einträgen',
  zeigeAufklappen: false,
  schwelle: SIDEBAR_WERKZEUGE_AB,
  laedt: false,
})

const emit = defineEmits<{
  (e: 'update:suche', wert: string): void
  (e: 'update:sortierung', wert: string): void
  (e: 'auswahl', nutzlast: { key: string; wert: string }): void
  (e: 'schalter', key: string): void
  (e: 'reset'): void
  (e: 'expand-all'): void
}>()

const gesamt = computed(() => (props.eintraege || []).length)
const sichtbar = computed(() => !props.laedt && gesamt.value >= props.schwelle)

const sucheModell = computed({
  get: () => props.suche,
  set: (w: string) => emit('update:suche', w),
})

/**
 * Die Auswahlfelder — gebaut aus den **vorhandenen** Werten.
 *
 * Ein Feld mit weniger als zwei verschiedenen Werten entfällt: Es könnte
 * nichts eingrenzen, und ein Bedienelement ohne Wirkung ist schlimmer als
 * keines (die Lehre aus #1805/#1830 in ihrer harmlosen Form).
 */
const auswahlFelder = computed(() => {
  if (props.auswahlen) return props.auswahlen
  const gebaut = []
  for (const feld of props.filterFelder || []) {
    const werte = new Set<string>()
    for (const e of props.eintraege || []) {
      const w = String((e || {})[feld.key] ?? '').trim()
      if (w) werte.add(w)
    }
    if (werte.size < 2) continue
    gebaut.push({
      key: feld.key,
      label: feld.label,
      wert: props.filter?.[feld.key] || '',
      optionen: [...werte].sort((a, b) => a.localeCompare(b))
        .map((w) => ({ wert: w, label: feld.labels?.[w] || w })),
    })
  }
  return gebaut
})

const filterAktiv = computed(() =>
  !!props.suche
  || Object.values(props.filter || {}).some(Boolean)
  || (props.schalter || []).some((s) => s.aktiv))
</script>
