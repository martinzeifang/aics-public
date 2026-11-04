<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <h2>{{ title }}</h2>
      <button v-if="onNew" class="btn-new" @click="onNew" title="Neu anlegen">+</button>
    </div>

    <!-- #1710: Suche ab einer Handvoll Einträgen — bei vielen Mandanten ist
         eine ungefilterte Liste nicht mehr bedienbar.
         #1856: Suche und Sortierung aus dem gemeinsamen Baustein, damit die
         Leiste in allen Modulen gleich aussieht. Einen Filter bringt diese
         allgemeine Leiste nicht mit: Sie kennt ihre Einträge nur über die
         `get*`-Funktionen und wüsste nicht, wonach sie filtern soll. -->
    <SidebarWerkzeuge
      v-model:suche="suche"
      :eintraege="items"
      :sortierung="sortierung"
      :sort-optionen="SORT_OPTIONEN"
      :treffer="gefiltert.length"
      :platzhalter="searchPlaceholder || 'Name oder Firma …'"
      :einheit="countLabel || 'Einträgen'"
      :schwelle="searchThreshold"
      :laedt="loading"
      @update:sortierung="setSortierung"
      @reset="resetFilter"
    />

    <div v-if="loading" class="sidebar-loading">Lädt…</div>

    <div v-else class="sidebar-list">
      <div
        v-if="showAllOption && !suchtGerade"
        @click="select(null)"
        :class="['sidebar-item', { active: isSelected(null) }]"
      >
        <div class="proj-name">— Alle Projekte —</div>
      </div>

      <div
        v-for="item in gefiltert"
        :key="getKey(item)"
        @click="select(item)"
        :class="['sidebar-item', { active: isSelected(item) }]"
      >
        <div class="proj-name">{{ getName(item) }}</div>
        <div v-if="getCompany && getCompany(item)" class="proj-company">{{ getCompany(item) }}</div>
        <div v-if="getMeta && getMeta(item)" class="proj-meta">{{ getMeta(item) }}</div>
      </div>

      <div v-if="items.length === 0" class="sidebar-empty">
        {{ emptyText || 'Keine Einträge' }}
      </div>
      <div v-else-if="gefiltert.length === 0" class="sidebar-empty">
        Kein Treffer für „{{ suche }}"
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SidebarWerkzeuge from './SidebarWerkzeuge.vue'
import { SIDEBAR_WERKZEUGE_AB, useSidebarFilter } from '../../composables/useSidebarFilter'

const props = withDefaults(defineProps<{
  title: string
  items: any[]
  loading?: boolean
  selectedKey: string | number | null
  showAllOption?: boolean
  emptyText?: string
  getKey: (item: any) => string | number
  getName: (item: any) => string
  getCompany?: (item: any) => string | undefined
  getMeta?: (item: any) => string | undefined
  onSelect: (item: any | null) => void
  onNew?: () => void
  /** Ab wie vielen Einträgen die Werkzeuge erscheinen (#1710/#1856). */
  searchThreshold?: number
  searchPlaceholder?: string
  countLabel?: string
}>(), {
  searchThreshold: SIDEBAR_WERKZEUGE_AB,
})

const SORT_OPTIONEN = [
  { wert: 'name', label: 'Name A–Z' },
  { wert: 'geaendert', label: 'Zuletzt geändert' },
]

const { suche, suchtGerade, matches, sortierung, setSortierung, resetFilter } =
  useSidebarFilter(`projekt.${props.title}`, {
    sortierung: 'name',
    sortSchluessel: SORT_OPTIONEN.map((o) => o.wert),
  })

/** Zeitstempel für „zuletzt geändert"; fehlt er, zählt der Eintrag als ältester. */
const zeit = (e: any) => Date.parse(e?.updated_at || e?.created_at || e?.geaendert_am || '') || 0

const gefiltert = computed(() => {
  const liste = props.items.filter((item) =>
    matches(props.getName(item), props.getCompany?.(item), props.getMeta?.(item)))
  // Die Reihenfolge der Aufrufer bleibt die Vorgabe: `name` sortiert **nicht**
  // um, sondern lässt sie, wie sie kommt. Ein Umsortieren hätte in Gutachten
  // und SOC eine fachliche Reihenfolge überschrieben, die dort Absicht ist.
  if (sortierung.value === 'geaendert') return [...liste].sort((a, b) => zeit(b) - zeit(a))
  return liste
})

const isSelected = (item: any): boolean => {
  if (item === null) return props.selectedKey === null || props.selectedKey === ''
  return props.getKey(item) === props.selectedKey
}

const select = (item: any | null) => {
  props.onSelect(item)
}
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.sidebar-header h2 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.btn-new {
  background: var(--color-primary);
  color: white;
  border: none;
  width: 26px;
  height: 26px;
  border-radius: 4px;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-new:hover {
  background: #0d47a1;
}

.sidebar-loading {
  text-align: center;
  color: #999;
  font-size: 13px;
  padding: 20px;
}

.sidebar-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  flex: 1;
}

.sidebar-item {
  padding: 10px 12px;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.sidebar-item:hover {
  background: #f5f5f5;
  border-left-color: var(--color-primary);
}

.sidebar-item.active {
  background: #e3f2fd;
  border-left-color: var(--color-primary);
}

.proj-name {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.proj-company {
  font-size: 11px;
  color: #888;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.proj-meta {
  font-size: 10px;
  color: #1565c0;
  margin-top: 2px;
  font-weight: 600;
  text-transform: uppercase;
}

.sidebar-empty {
  text-align: center;
  color: #999;
  padding: 20px;
  font-size: 13px;
  font-style: italic;
}
</style>
