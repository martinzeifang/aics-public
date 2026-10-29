<template>
  <div class="firmen-sidebar">
    <div class="sidebar-header">
      <h2>{{ title }}</h2>
    </div>

    <!-- #1710: Mandanten-Suche — DSGVO/NIS2 sind firmenbezogen, bei 50+
         Mandanten ist die Liste ohne Filter nicht mehr bedienbar.
         #1856: Suche, Sortierung und Filter kommen aus dem gemeinsamen
         Baustein, und die Schwelle ist einheitlich 5 (vorher 8 — darunter gab
         es hier **kein** Bedienelement, was auf einer Installation mit drei
         bis sieben Mandanten der Normalfall ist). -->
    <SidebarWerkzeuge
      v-model:suche="suche"
      :eintraege="projektListe"
      :sortierung="sortierung"
      :sort-optionen="SORT_OPTIONEN"
      :filter="filter"
      :filter-felder="FILTER_FELDER"
      :treffer="gefiltert.length"
      platzhalter="Mandant suchen …"
      einheit="Mandanten"
      :laedt="loading"
      @update:sortierung="setSortierung"
      @auswahl="setFilter($event.key, $event.wert)"
      @reset="resetFilter"
    />

    <div v-if="loading" class="sidebar-loading">Lädt…</div>

    <div v-else class="sidebar-list">
      <div
        v-for="p in gefiltert"
        :key="p.name"
        @click="onSelect(p.name)"
        :class="['sidebar-item', { active: selectedKey === p.name }]"
      >
        <div class="proj-name">{{ p.unternehmen || p.name }}</div>
        <!-- Wenn Projekt-Name != Firma, zeigen wir den Projekt-Namen als Sub-Zeile.
             Das passiert bei Altdaten oder wenn manuell mehrere Projekte je Firma
             angelegt wurden (technisch moeglich, fachlich aber 1:1 gemeint). -->
        <div v-if="p.unternehmen && p.unternehmen !== p.name" class="proj-sub">
          {{ p.name }}
        </div>
      </div>

      <div v-if="projektListe.length > 0 && gefiltert.length === 0" class="sidebar-empty">
        Kein Treffer für „{{ suche }}"
      </div>

      <div v-if="projektListe.length === 0" class="sidebar-empty">
        <p>Keine {{ moduleLabel }}-Bewertungen vorhanden.</p>
        <p class="hint-text">
          {{ moduleLabel }} ist <strong>firmenbezogen</strong> — pro Firma
          eine Bewertung. Lege eine Firma mit aktiviertem
          {{ moduleLabel }}-Modul in der Firmenverwaltung an.
        </p>
        <router-link to="/firmen" class="link-btn">→ Zur Firmenverwaltung</router-link>
      </div>
    </div>

    <div v-if="projektListe.length > 0" class="sidebar-footer">
      <small class="hint-text">
        Neue Firma? Lege sie in der <router-link to="/firmen">Firmenverwaltung</router-link>
        an — Modul-Projekt wird automatisch erzeugt.
      </small>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  title: string
  moduleLabel: string
  items: any[]
  loading?: boolean
  selectedKey: string | null
  onSelect: (key: string | null) => void
}>()

import { computed } from 'vue'
import SidebarWerkzeuge from './SidebarWerkzeuge.vue'
import { useSidebarFilter } from '../../composables/useSidebarFilter'

const SORT_OPTIONEN = [
  { wert: 'name', label: 'Name A–Z' },
  { wert: 'geaendert', label: 'Zuletzt geändert' },
]

/**
 * #1856: Die Filter kommen aus den Daten, nicht aus der Vorstellung.
 *
 * NIS2 liefert `einrichtungsklasse` (Art. 3 der Richtlinie — wesentlich oder
 * wichtig), DSGVO `organisationstyp`. `berater` gilt für beide und ist für
 * einen Dienstleister mit vielen Mandaten der naheliegende Schnitt. Felder,
 * die ein Modul nicht führt, fallen von selbst weg: `SidebarWerkzeuge` zeigt
 * ein Auswahlfeld erst ab **zwei** verschiedenen Werten.
 */
const FILTER_FELDER = [
  { key: 'einrichtungsklasse', label: 'Klasse',
    labels: { wesentlich: 'wesentlich', wichtig: 'wichtig' } },
  { key: 'organisationstyp', label: 'Rolle' },
  { key: 'berater', label: 'Berater' },
]

const { suche, matches, sortierung, setSortierung, filter, setFilter, resetFilter } =
  useSidebarFilter(`modul.${props.moduleLabel}`, {
    sortierung: 'name',
    sortSchluessel: SORT_OPTIONEN.map((o) => o.wert),
    filter: { einrichtungsklasse: '', organisationstyp: '', berater: '' },
  })

/** Zeitstempel für „zuletzt geändert"; fehlt er, zählt der Eintrag als ältester. */
const zeit = (p: any) => Date.parse(p?.updated_at || p?.created_at || '') || 0

// Sort: Firma (unternehmen) alphabetisch, ohne-Firma nach hinten
const projektListe = computed(() => {
  const liste = [...props.items]
  if (sortierung.value === 'geaendert') {
    return liste.sort((a, b) => zeit(b) - zeit(a))
  }
  return liste.sort((a: any, b: any) => {
    const ka = a.unternehmen || ''
    const kb = b.unternehmen || ''
    if (!ka && kb) return 1
    if (ka && !kb) return -1
    if (ka !== kb) return ka.localeCompare(kb)
    return a.name.localeCompare(b.name)
  })
})

/** Trifft der Eintrag die gesetzten Filter? Leerer Filter heißt „alle". */
const passtZuFiltern = (p: any) =>
  FILTER_FELDER.every(({ key }) => {
    const gewaehlt = filter.value?.[key]
    return !gewaehlt || String(p?.[key] ?? '') === gewaehlt
  })

const gefiltert = computed(() =>
  projektListe.value.filter((p: any) => matches(p.name, p.unternehmen) && passtZuFiltern(p)),
)
</script>

<style scoped>
.firmen-sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
  overflow: hidden;
}

.sidebar-header {
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

.proj-sub {
  font-size: 11px;
  color: #888;
  margin-top: 2px;
  font-style: italic;
}

.sidebar-empty {
  padding: 16px 12px;
  text-align: center;
  color: #888;
}

.sidebar-empty p {
  font-size: 12px;
  margin: 0 0 8px 0;
}

.hint-text {
  font-size: 11px;
  color: #888;
  line-height: 1.45;
}

.link-btn {
  display: inline-block;
  margin-top: 12px;
  padding: 6px 12px;
  background: var(--color-primary);
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.sidebar-footer {
  padding: 8px 4px;
  border-top: 1px solid var(--color-border);
}

.sidebar-footer a {
  color: var(--color-primary);
}
</style>
