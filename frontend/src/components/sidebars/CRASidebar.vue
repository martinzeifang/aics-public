<template>
  <div class="cra-sidebar">
    <div class="sidebar-header">
      <h2>CRA-Projekte</h2>
    </div>

    <!-- #1710: Suche über Firma, Projekt und Produkt.
         #1764: Schwelle von 8 auf 5 gesenkt (wie Risikobewertung). -->
    <SidebarSearch
      v-if="werkzeugeSichtbar"
      v-model="suche"
      placeholder="Firma, Produkt oder Projekt …"
      :treffer="trefferAnzahl"
      :gesamt="craStore.projekte.length"
      einheit="Projekten"
      zeige-aufklappen
      @expand-all="alleAufklappen"
    />

    <!-- #1764: Sortierung + Filter nach Produktklasse. Zustandsfilter („offene
         Risiken") fehlen hier bewusst: die CRA-Projektliste liefert keine
         Kennzahlen, und ein Nachladen je Projekt wären Dutzende Requests. -->
    <SidebarSortFilter
      v-if="werkzeugeSichtbar"
      :sortierung="sortierung"
      :sort-optionen="SORT_OPTIONEN"
      :auswahlen="auswahlFilter"
      :aktiv="filterAktiv"
      @update:sortierung="setSortierung"
      @auswahl="setFilter($event.key, $event.wert)"
      @reset="resetFilter"
    />

    <div v-if="loading" class="sidebar-loading">Lädt…</div>

    <div v-else class="sidebar-list">
      <!-- Issue #435: Gruppierung nach Firma, 1 CRA-Projekt je Produkt.
           #1569: Firma ist selbst anklickbar → Firmen-Übersicht (Produkte +
           Risiko-Cockpit), analog AI-Act-Organisation (#1562).
           #1710: Gruppen einklappbar (Zustand bleibt über Reloads erhalten). -->
      <template v-for="group in grouped" :key="group.firma || '__none__'">
        <div
          v-if="group.firma"
          @click="onSelectFirma(group.firma)"
          :class="['sidebar-item', 'firma-item', { active: craStore.selectedFirma === group.firma && !selectedKey }]"
        >
          <div class="firma-row">
            <button type="button" class="toggle" :aria-expanded="!istEingeklappt(group.firma)"
                    :title="istEingeklappt(group.firma) ? 'Produkte zeigen' : 'Produkte verbergen'"
                    @click.stop="toggleGruppe(group.firma)">
              {{ istEingeklappt(group.firma) ? '▸' : '▾' }}
            </button>
            <div class="proj-name">🏢 {{ group.firma }}</div>
          </div>
          <div class="proj-meta">Firma · {{ group.projekte.length }} {{ group.projekte.length === 1 ? 'Produkt' : 'Produkte' }}</div>
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
            :class="['sidebar-item', 'produkt-item', { active: selectedKey === p.name }]"
          >
            <div class="proj-name">📦 {{ p.produkt || p.name }}</div>
            <div v-if="p.produkt && p.produkt !== p.name" class="proj-produkt">{{ p.name }}</div>
            <div v-if="p.produktklasse && p.produktklasse !== 'default'" class="proj-meta">
              {{ produktklasseLabel(p.produktklasse) }}
            </div>
          </div>
        </template>
      </template>

      <div v-if="craStore.projekte.length > 0 && grouped.length === 0" class="sidebar-empty">
        <p v-if="suchtGerade">Kein Treffer für „{{ suche }}"</p>
        <p v-else>Kein Projekt passt zum Filter</p>
        <button v-if="filterAktiv" type="button" class="link" @click="resetFilter">
          Filter zurücksetzen
        </button>
      </div>

      <div v-if="craStore.projekte.length === 0" class="sidebar-empty">
        <p>Keine CRA-Projekte.</p>
        <p class="hint-text">
          CRA-Projekte werden automatisch angelegt, wenn du in der
          Firmenverwaltung Produkte hinzufügst (1 Projekt pro Produkt).
        </p>
        <router-link to="/firmen" class="link-btn">→ Zur Firmenverwaltung</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useCraStore } from '../../stores/cra'
import SidebarSearch from './SidebarSearch.vue'
import SidebarSortFilter from './SidebarSortFilter.vue'
import { useSidebarFilter } from '../../composables/useSidebarFilter'

const craStore = useCraStore()
const loading = ref(false)

/** #1764: Ab dieser Zahl erscheinen Suche, Sortierung und Filter (vorher 8). */
const MIN_WERKZEUGE = 5

/** #1764: Sortierkriterien. Mehr gibt die Projektliste nicht her — ohne
 *  Kennzahlen je Projekt ist „offene Punkte" nicht berechenbar. */
const SORT_OPTIONEN = [
  { wert: 'name', label: 'Name A–Z' },
  { wert: 'geaendert', label: 'Zuletzt geändert' },
]

const {
  suche, suchtGerade, matches, istEingeklappt, toggleGruppe, alleAufklappen,
  sortierung, setSortierung, filter, setFilter, filterAktiv, resetFilter,
} = useSidebarFilter('cra', {
  sortierung: 'name',
  sortSchluessel: SORT_OPTIONEN.map((o) => o.wert),
  filter: { produktklasse: '' },
})

/** Leiste sichtbar? (Steuert auch, ob gemerkte Filter überhaupt wirken.) */
const werkzeugeSichtbar = computed(() => !loading.value && craStore.projekte.length >= MIN_WERKZEUGE)

/**
 * Wirksame Filter. Ohne sichtbare Leiste gilt kein Filter — sonst würde ein aus
 * einem größeren Bestand gemerkter Filter Projekte verbergen, ohne dass es eine
 * sichtbare Stelle gäbe, ihn zurückzunehmen.
 */
const aktiveFilter = computed(() =>
  werkzeugeSichtbar.value ? filter.value : { produktklasse: '' },
)

const selectedKey = computed(() => {
  if (typeof craStore.selectedProjekt === 'string') return craStore.selectedProjekt
  return (craStore.selectedProjekt as any)?.name ?? null
})

const produktklasseLabel = (k: string): string => {
  const labels: Record<string, string> = {
    important_i: 'Important Class I',
    important_ii: 'Important Class II',
    critical_i: 'Critical Class I',
    critical_ii: 'Critical Class II',
  }
  return labels[k] || k
}

/** #1764: Produktklassen aus dem Bestand — nur anbieten, was vorkommt. */
const produktklasseOptionen = computed(() => {
  const set = new Set<string>()
  for (const p of craStore.projekte) {
    const k = (p as any).produktklasse || ''
    if (k && k !== 'default') set.add(k)
  }
  const liste = [...set].sort((a, b) => produktklasseLabel(a).localeCompare(produktklasseLabel(b)))
  const optionen = liste.map((k) => ({ wert: k, label: produktklasseLabel(k) }))
  // „default" nur als Option, wenn es solche Projekte überhaupt gibt.
  if (craStore.projekte.some((p) => !((p as any).produktklasse) || (p as any).produktklasse === 'default')) {
    optionen.push({ wert: 'default', label: 'Ohne Klasse' })
  }
  return optionen
})

const auswahlFilter = computed(() => [
  {
    key: 'produktklasse',
    label: 'Klasse',
    wert: filter.value.produktklasse || '',
    optionen: produktklasseOptionen.value,
  },
])

/** Zeitstempel als Rohtext vergleichen — ISO-artige Werte sortieren als Text
 *  korrekt, ohne die Parser-Eigenheiten von „YYYY-MM-DD HH:MM:SS". */
const stempel = (p: any): string => String(p?.updated_at || p?.created_at || '')

const vergleiche = (a: any, b: any): number => {
  if (sortierung.value === 'geaendert') {
    const d = stempel(b).localeCompare(stempel(a)) // neueste zuerst
    if (d !== 0) return d
  }
  return String(a.name).localeCompare(String(b.name))
}

const grouped = computed(() => {
  const groupsMap = new Map<string, any[]>()
  for (const p of craStore.projekte) {
    const firma = (p as any).unternehmen || (p as any).company || ''
    // #1710: Treffer auf Firmenebene behält die ganze Gruppe — man sucht meist
    // den Mandanten und will dann dessen Produkte sehen.
    if (!matches(firma, p.name, (p as any).produkt)) continue
    // #1764: Filter nach Produktklasse; „default" steht für „ohne Klasse".
    if (aktiveFilter.value.produktklasse) {
      const k = (p as any).produktklasse || 'default'
      if (k !== aktiveFilter.value.produktklasse) continue
    }
    const list = groupsMap.get(firma) ?? []
    list.push(p)
    groupsMap.set(firma, list)
  }
  const result = Array.from(groupsMap.entries()).map(([firma, projekte]) => ({
    firma,
    projekte: [...projekte].sort(vergleiche),
  }))
  // #1764: Gruppen folgen derselben Sortierung wie ihr Inhalt.
  result.sort((a, b) => {
    if (!a.firma && b.firma) return 1
    if (a.firma && !b.firma) return -1
    if (sortierung.value === 'geaendert') {
      const neueste = (g: typeof a) =>
        g.projekte.reduce((m: string, p: any) => (stempel(p) > m ? stempel(p) : m), '')
      const d = neueste(b).localeCompare(neueste(a))
      if (d !== 0) return d
    }
    return a.firma.localeCompare(b.firma)
  })
  return result
})

const trefferAnzahl = computed(() =>
  grouped.value.reduce((n, g) => n + g.projekte.length, 0),
)

onMounted(async () => {
  loading.value = true
  try {
    await craStore.fetchProjekte()
  } finally {
    loading.value = false
  }
})

const onSelectFirma = (firma: string) => {
  craStore.openFirma(firma)
}

const onSelect = (proj: any) => {
  if (proj) {
    craStore.selectedProjekt = proj.name
    craStore.fetchAnforderungen(proj.name)
    craStore.fetchOwaspControls?.(proj.name)
  }
}
</script>

<style scoped>
.cra-sidebar {
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

.firma-item { margin-top: 6px; }

/* #1710: Einklapp-Pfeil in der Firmenzeile */
.firma-row { display: flex; align-items: center; gap: 6px; }

.toggle {
  flex: none;
  border: none;
  background: transparent;
  color: #888;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  padding: 2px 3px;
  border-radius: 3px;
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

/* #1764: „Filter zurücksetzen" im leeren Zustand */
.sidebar-empty .link {
  border: none;
  background: none;
  padding: 0;
  font-size: 11px;
  color: var(--color-primary, #1565c0);
  cursor: pointer;
  text-decoration: underline;
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
</style>
