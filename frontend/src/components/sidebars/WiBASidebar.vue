<template>
  <div class="wiba-sidebar">
    <div class="sidebar-header">
      <h2>WiBA-Projekte</h2>
    </div>

    <!-- #1710/#1856: Suche, Sortierung und Filter aus dem gemeinsamen
         Baustein — dieselbe Leiste wie in CRA und der Risikobewertung. Die
         Schwelle lag hier bei 8; bei drei Projekten gab es damit **kein**
         Bedienelement. -->
    <SidebarWerkzeuge
      v-model:suche="suche"
      :eintraege="store.projekte"
      :sortierung="sortierung"
      :sort-optionen="SORT_OPTIONEN"
      :filter="filter"
      :filter-felder="FILTER_FELDER"
      :treffer="trefferAnzahl"
      platzhalter="Firma oder Projekt …"
      einheit="Projekten"
      zeige-aufklappen
      :laedt="loading"
      @update:sortierung="setSortierung"
      @auswahl="setFilter($event.key, $event.wert)"
      @reset="resetFilter"
      @expand-all="alleAufklappen"
    />

    <div v-if="loading" class="sidebar-loading">Lädt…</div>

    <div v-else class="sidebar-list">
      <template v-for="group in grouped" :key="group.firma || '__none__'">
        <div class="firma-header">
          <button type="button" class="toggle" :aria-expanded="!istEingeklappt(group.firma)"
                  :title="istEingeklappt(group.firma) ? 'Projekte zeigen' : 'Projekte verbergen'"
                  @click="toggleGruppe(group.firma)">
            {{ istEingeklappt(group.firma) ? '▸' : '▾' }}
          </button>
          <span class="firma-name">{{ group.firma || '— Ohne Firma —' }}</span>
          <span class="firma-count">{{ group.projekte.length }}</span>
        </div>
        <template v-if="!istEingeklappt(group.firma)">
          <div
            v-for="p in group.projekte"
            :key="p.name"
            @click="onSelect(p)"
            :class="['sidebar-item', { active: store.selectedProjekt === p.name }]"
          >
            <div class="proj-name">{{ p.name }}</div>
            <div v-if="p.unternehmen" class="proj-produkt">{{ p.unternehmen }}</div>
          </div>
        </template>
      </template>

      <div v-if="store.projekte.length > 0 && grouped.length === 0" class="sidebar-empty">
        Kein Treffer für „{{ suche }}"
      </div>

      <div v-if="store.projekte.length === 0" class="sidebar-empty">
        <p>Keine WiBA-Projekte.</p>
        <p class="hint-text">Lege im WiBA-Modul ein Projekt an und ordne es einer Firma zu.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useWibaStore } from '../../stores/wiba'
import SidebarWerkzeuge from './SidebarWerkzeuge.vue'
import { useSidebarFilter } from '../../composables/useSidebarFilter'

const SORT_OPTIONEN = [
  { wert: 'name', label: 'Name A–Z' },
  { wert: 'geaendert', label: 'Zuletzt geändert' },
]

// #1856: WiBA führt keine fachliche Klasse am Projekt — der Berater ist das
// einzige Feld, das hier wirklich etwas eingrenzt. Erfunden wird nichts: Ein
// Zustandsfilter („offene Prüffragen") bräuchte Kennzahlen, die die
// Projektliste nicht liefert, und sie je Projekt nachzuladen wären Dutzende
// Requests für eine Seitenleiste.
const FILTER_FELDER = [{ key: 'berater', label: 'Berater' }]

const store = useWibaStore()
const loading = ref(false)
const {
  suche, matches, istEingeklappt, toggleGruppe, alleAufklappen,
  sortierung, setSortierung, filter, setFilter, resetFilter,
} = useSidebarFilter('wiba', {
  sortierung: 'name',
  sortSchluessel: SORT_OPTIONEN.map((o) => o.wert),
  filter: { berater: '' },
})

/** Zeitstempel für „zuletzt geändert"; fehlt er, zählt der Eintrag als ältester. */
const zeit = (p: any) => Date.parse(p?.updated_at || p?.created_at || '') || 0

const passtZuFiltern = (p: any) =>
  FILTER_FELDER.every(({ key }) => {
    const gewaehlt = filter.value?.[key]
    return !gewaehlt || String(p?.[key] ?? '') === gewaehlt
  })

const grouped = computed(() => {
  const map: Record<string, any[]> = {}
  for (const p of store.projekte as any[]) {
    const f = p.unternehmen || ''
    // #1710: Treffer auf Firmenebene behält die ganze Gruppe.
    if (!matches(f, p.name)) continue
    if (!passtZuFiltern(p)) continue
    ;(map[f] ||= []).push(p)
  }
  // #1856: Die Gruppen folgen der Sortierung mit — sonst stünde die zuletzt
  // angefasste Bewertung weit unten in einer alphabetischen Firmenliste
  // (dieselbe Überlegung wie in #1764).
  const firmen = Object.keys(map)
  if (sortierung.value === 'geaendert') {
    for (const f of firmen) map[f].sort((a, b) => zeit(b) - zeit(a))
    firmen.sort((a, b) => zeit(map[b][0]) - zeit(map[a][0]))
  } else {
    for (const f of firmen) map[f].sort((a, b) => String(a.name).localeCompare(String(b.name)))
    firmen.sort((a, b) => a.localeCompare(b))
  }
  return firmen.map((firma) => ({ firma, projekte: map[firma] }))
})

const trefferAnzahl = computed(() =>
  grouped.value.reduce((n, g) => n + g.projekte.length, 0),
)

const onSelect = async (p: any) => {
  store.selectedProjekt = p.name
  await store.fetchControls(p.name)
}

onMounted(async () => {
  loading.value = true
  try {
    await store.fetchProjekte()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.wiba-sidebar { display: flex; flex-direction: column; height: 100%; }
.sidebar-header { padding: 16px; border-bottom: 1px solid #e0e0e0; }
.sidebar-header h2 { font-size: 16px; margin: 0; color: #1565c0; }
.sidebar-loading, .sidebar-empty { padding: 16px; color: #666; font-size: 14px; }
.sidebar-list { overflow-y: auto; flex: 1; }
.firma-header {
  display: flex; justify-content: space-between; padding: 8px 16px;
  background: #f5f5f5; font-size: 12px; font-weight: 600; color: #555;
  position: sticky; top: 0;
}
.firma-count { color: #999; }
/* #1710: Einklapp-Pfeil */
.toggle {
  flex: none; border: none; background: transparent; color: #888; font-size: 11px;
  line-height: 1; cursor: pointer; padding: 2px 4px; border-radius: 3px; margin-right: 4px;
}
.toggle:hover { background: #e0e0e0; color: #333; }
.sidebar-item { padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
.sidebar-item:hover { background: #e3f2fd; }
.sidebar-item.active { background: #bbdefb; border-left: 3px solid #1565c0; }
.proj-name { font-size: 14px; font-weight: 500; }
.proj-produkt { font-size: 12px; color: #777; }
.hint-text { font-size: 12px; color: #999; }
</style>
