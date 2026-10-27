<template>
  <div class="rb-sidebar">
    <div class="sidebar-header">
      <h2>Risikobewertung</h2>
    </div>

    <!-- #1710: Suche über Firma, Projekt und Produkt.
         #1764: Schwelle von 8 auf 5 gesenkt — ab einer Handvoll Bewertungen
         sucht man schon, und eine unsichtbare Funktion gilt als nicht vorhanden. -->
    <SidebarSearch
      v-if="werkzeugeSichtbar"
      v-model="suche"
      placeholder="Firma, Produkt oder Bewertung …"
      :treffer="trefferAnzahl"
      :gesamt="totalCount"
      einheit="Bewertungen"
      zeige-aufklappen
      @expand-all="alleAufklappen"
    />

    <!-- #1764: Sortierung (zuletzt geändert / Name / offene Risiken) und
         Filter nach Framework bzw. Zustand. -->
    <SidebarSortFilter
      v-if="werkzeugeSichtbar"
      :sortierung="sortierung"
      :sort-optionen="SORT_OPTIONEN"
      :auswahlen="auswahlFilter"
      :schalter="schalterFilter"
      :aktiv="filterAktiv"
      @update:sortierung="setSortierung"
      @auswahl="setFilter($event.key, $event.wert)"
      @schalter="toggleFilter"
      @reset="resetFilter"
    />

    <div v-if="loading" class="sidebar-loading">Lädt…</div>

    <div v-else class="sidebar-list">
      <div
        v-if="!suchtGerade"
        @click="onSelect(null)"
        :class="['sidebar-item all-item', { active: rb.selectedProjekt === null && !rb.selectedFirma }]"
      >
        <div class="proj-name">— Alle Projekte —</div>
        <div class="proj-meta">{{ totalCount }} {{ totalCount === 1 ? 'Projekt' : 'Projekte' }}</div>
      </div>

      <!-- Issue #433: Gruppierung nach Firma.
           #1569: Firma anklickbar → Firmen-Übersicht (Produkte + Risiko-Cockpit).
           #1710: Gruppen einklappbar + Suche. -->
      <template v-for="group in grouped" :key="group.firma || '__none__'">
        <div
          v-if="group.firma"
          @click="rb.openFirma(group.firma)"
          :class="['sidebar-item', 'firma-item', { active: rb.selectedFirma === group.firma && !rb.selectedProjekt }]"
        >
          <div class="firma-row">
            <button type="button" class="toggle" :aria-expanded="!istEingeklappt(group.firma)"
                    :title="istEingeklappt(group.firma) ? 'Bewertungen zeigen' : 'Bewertungen verbergen'"
                    @click.stop="toggleGruppe(group.firma)">
              {{ istEingeklappt(group.firma) ? '▸' : '▾' }}
            </button>
            <div class="proj-name">🏢 {{ group.firma }}</div>
          </div>
          <div class="proj-meta">Firma · {{ group.projekte.length }} {{ group.projekte.length === 1 ? 'Bewertung' : 'Bewertungen' }}</div>
        </div>
        <div v-else class="firma-header">
          <span class="firma-name">— Ohne Firma —</span>
          <span class="firma-count">{{ group.projekte.length }}</span>
        </div>
        <template v-if="!istEingeklappt(group.firma)">
          <div
            v-for="p in group.projekte"
            :key="p.name"
            @click="onSelect(p)"
            :class="['sidebar-item', 'produkt-item', { active: rb.selectedProjekt === p.name }]"
          >
            <div class="proj-name">📦 {{ p.produkt || p.name }}</div>
            <div v-if="p.produkt && p.produkt !== p.name" class="proj-produkt">{{ p.name }}</div>
            <div class="proj-meta">
              {{ p.framework }} · {{ p.count }} {{ p.count === 1 ? 'Risiko' : 'Risiken' }}
              <!-- #1764: offene Risiken nur nennen, wenn sie von der Gesamtzahl
                   abweichen — sonst steht zweimal dieselbe Zahl. -->
              <template v-if="p.offen < p.count"> · {{ p.offen }} offen</template>
              <span v-if="p.reassess > 0" class="reassess" title="Neubewertung erforderlich">⚠️</span>
            </div>
          </div>
        </template>
      </template>
      <div v-if="rb.projekte.length === 0" class="sidebar-empty">
        Keine Projekte
      </div>
      <div v-else-if="grouped.length === 0" class="sidebar-empty">
        <template v-if="suchtGerade">Kein Treffer für „{{ suche }}"</template>
        <template v-else>Keine Bewertung passt zum Filter</template>
        <div v-if="filterAktiv" class="empty-aktion">
          <button type="button" class="link" @click="resetFilter">Filter zurücksetzen</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRisikobewertungStore } from '../../stores/risikobewertung'
import SidebarSearch from './SidebarSearch.vue'
import SidebarSortFilter from './SidebarSortFilter.vue'
import { useSidebarFilter } from '../../composables/useSidebarFilter'

const rb = useRisikobewertungStore()
const loading = ref(false)

/**
 * #1764: Ab dieser Zahl erscheinen Suche, Sortierung und Filter. Vorher lag die
 * Schwelle bei 8 — bei einer Handvoll Bewertungen hielt man die Funktionen
 * daher für nicht vorhanden.
 */
const MIN_WERKZEUGE = 5

/** #1764: Sortierkriterien. „Zuletzt geändert" ist bei vielen Bewertungen das
 *  nützlichste, alphabetisch bleibt der Default (unverändertes Verhalten). */
const SORT_OPTIONEN = [
  { wert: 'name', label: 'Name A–Z' },
  { wert: 'geaendert', label: 'Zuletzt geändert' },
  { wert: 'offen', label: 'Offene Risiken' },
]

const {
  suche, suchtGerade, matches, istEingeklappt, toggleGruppe, alleAufklappen,
  sortierung, setSortierung, filter, setFilter, toggleFilter, filterAktiv, resetFilter,
} = useSidebarFilter('risikobewertung', {
  sortierung: 'name',
  sortSchluessel: SORT_OPTIONEN.map((o) => o.wert),
  filter: { framework: '', offen: '', reassess: '' },
})

/** Leiste sichtbar? (Steuert auch, ob gemerkte Filter überhaupt wirken.) */
const werkzeugeSichtbar = computed(() => !loading.value && rb.projekte.length >= MIN_WERKZEUGE)

/**
 * Wirksame Filter. Ist die Leiste ausgeblendet (wenige Bewertungen), gilt kein
 * Filter — sonst würde ein aus einem größeren Bestand gemerkter Filter Einträge
 * verbergen, ohne dass es eine sichtbare Stelle gäbe, ihn zurückzunehmen.
 */
const aktiveFilter = computed(() =>
  werkzeugeSichtbar.value ? filter.value : { framework: '', offen: '', reassess: '' },
)

interface Eintrag {
  name: string
  firma: string
  framework: string
  produkt: string
  count: number
  offen: number
  reassess: number
  /** Zeitstempel als Rohtext — ISO-artige Werte sortieren als Text korrekt
   *  und wir umgehen die Parser-Eigenheiten bei „YYYY-MM-DD HH:MM:SS". */
  geaendert: string
}

/** Alle Bewertungen mit den Kennzahlen aus dem Store (ein Request, #1764). */
const eintraege = computed<Eintrag[]>(() =>
  rb.projekte.map((p) => {
    const s = rb.risikoStats[p.name]
    const gesamt = s?.gesamt ?? p.risiken_count ?? 0
    return {
      name: p.name,
      firma: (p as any).unternehmen || (p as any).company || '',
      framework: p.framework || '',
      produkt: (p as any).produkt || '',
      count: gesamt,
      // Ohne geladene Kennzahlen gelten alle Risiken als offen — das ist die
      // vorsichtige Annahme; ein Projekt ohne Risiken bleibt bei 0.
      offen: s?.offen ?? gesamt,
      reassess: s?.reassess ?? 0,
      geaendert: String(p.updated_at || p.created_at || ''),
    }
  }),
)

/** Framework-Auswahl aus dem Bestand — keine leeren Optionen anbieten. */
const frameworkOptionen = computed(() => {
  const set = new Set<string>()
  for (const e of eintraege.value) if (e.framework) set.add(e.framework)
  return [...set].sort((a, b) => a.localeCompare(b)).map((f) => ({ wert: f, label: f }))
})

const auswahlFilter = computed(() => [
  {
    key: 'framework',
    label: 'Framework',
    wert: filter.value.framework || '',
    optionen: frameworkOptionen.value,
  },
])

/** Basis für die Chip-Zähler: Suche + Framework, aber ohne die Chips selbst. */
const basisFuerChips = computed(() =>
  eintraege.value.filter(
    (e) =>
      matches(e.firma, e.name, e.produkt, e.framework) &&
      (!aktiveFilter.value.framework || e.framework === aktiveFilter.value.framework),
  ),
)

const schalterFilter = computed(() => [
  {
    key: 'offen',
    label: 'offene Risiken',
    aktiv: !!filter.value.offen,
    anzahl: basisFuerChips.value.filter((e) => e.offen > 0).length,
    titel: 'Nur Bewertungen mit mindestens einem offenen Risiko',
  },
  {
    key: 'reassess',
    label: '⚠️ Neubewertung',
    aktiv: !!filter.value.reassess,
    anzahl: basisFuerChips.value.filter((e) => e.reassess > 0).length,
    titel: 'Nur Bewertungen mit mindestens einem Risiko „Neubewertung erforderlich"',
  },
])

const gefiltert = computed(() =>
  basisFuerChips.value.filter(
    (e) =>
      (!aktiveFilter.value.offen || e.offen > 0) &&
      (!aktiveFilter.value.reassess || e.reassess > 0),
  ),
)

/** Reihenfolge innerhalb einer Firma; Name ist immer der letzte Tiebreaker. */
const vergleiche = (a: Eintrag, b: Eintrag): number => {
  if (sortierung.value === 'geaendert') {
    const d = b.geaendert.localeCompare(a.geaendert) // neueste zuerst
    if (d !== 0) return d
  } else if (sortierung.value === 'offen') {
    const d = b.offen - a.offen
    if (d !== 0) return d
  }
  return a.name.localeCompare(b.name)
}

// Issue #433: Projekte nach Firma (unternehmen) gruppieren.
// #1764: Die Gruppen folgen derselben Sortierung wie ihr Inhalt — sonst stünde
// die zuletzt angefasste Bewertung weit unten in einer alphabetischen Firmenliste.
const grouped = computed(() => {
  const groupsMap = new Map<string, Eintrag[]>()
  for (const e of gefiltert.value) {
    // #1710: Treffer auf Firmenebene behält die ganze Gruppe.
    const list = groupsMap.get(e.firma) ?? []
    list.push(e)
    groupsMap.set(e.firma, list)
  }

  const result = Array.from(groupsMap.entries()).map(([firma, projekte]) => ({
    firma,
    projekte: [...projekte].sort(vergleiche),
  }))

  result.sort((a, b) => {
    // Gruppe „ohne Firma" bleibt immer am Ende.
    if (!a.firma && b.firma) return 1
    if (a.firma && !b.firma) return -1
    if (sortierung.value === 'geaendert') {
      const neueste = (g: typeof a) => g.projekte.reduce((m, p) => (p.geaendert > m ? p.geaendert : m), '')
      const d = neueste(b).localeCompare(neueste(a))
      if (d !== 0) return d
    } else if (sortierung.value === 'offen') {
      const summe = (g: typeof a) => g.projekte.reduce((n, p) => n + p.offen, 0)
      const d = summe(b) - summe(a)
      if (d !== 0) return d
    }
    return a.firma.localeCompare(b.firma)
  })
  return result
})

const totalCount = computed(() => rb.projekte.length)

const trefferAnzahl = computed(() =>
  grouped.value.reduce((n, g) => n + g.projekte.length, 0),
)

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([rb.fetchProjekte(), rb.fetchRisiken()])
  } finally {
    loading.value = false
  }
})

const onSelect = (proj: any) => {
  rb.selectedFirma = null
  rb.selectedProjekt = proj?.name ?? null
}
</script>

<style scoped>
.rb-sidebar {
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

.firma-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-secondary, #666);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-top: 6px;
}

.firma-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.firma-count {
  background: var(--color-background, #f5f5f5);
  color: var(--color-text-secondary, #666);
  padding: 2px 7px;
  border-radius: 9px;
  font-size: 10px;
  font-weight: 600;
}

.sidebar-item {
  padding: 10px 12px;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.sidebar-item.all-item {
  border-bottom: 1px solid var(--color-border);
  border-radius: 4px;
  padding-bottom: 12px;
  margin-bottom: 4px;
}

.firma-item { margin-top: 6px; }

/* #1710: Einklapp-Pfeil in der Firmenzeile */
.firma-row { display: flex; align-items: center; gap: 6px; }

.toggle {
  flex: none; border: none; background: transparent; color: #888;
  font-size: 11px; line-height: 1; cursor: pointer; padding: 2px 3px; border-radius: 3px;
}

.toggle:hover { background: #e0e0e0; color: #333; }

.produkt-item { margin-left: 12px; padding: 8px 12px; }

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

.proj-produkt {
  font-size: 11px;
  color: #666;
  margin-top: 2px;
  font-style: italic;
}

.proj-meta {
  font-size: 10px;
  color: var(--color-primary);
  margin-top: 2px;
  font-weight: 600;
}

.sidebar-empty {
  text-align: center;
  color: #999;
  padding: 20px;
  font-size: 13px;
  font-style: italic;
}

/* #1764: Hinweis auf „Neubewertung erforderlich" in der Meta-Zeile */
.reassess { margin-left: 4px; }

.empty-aktion { margin-top: 8px; }

.empty-aktion .link {
  border: none;
  background: none;
  padding: 0;
  font-size: 11px;
  font-style: normal;
  color: var(--color-primary, #1565c0);
  cursor: pointer;
  text-decoration: underline;
}
</style>
