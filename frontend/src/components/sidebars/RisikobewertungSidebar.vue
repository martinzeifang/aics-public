<template>
  <div class="rb-sidebar">
    <div class="sidebar-header">
      <h2>Risikobewertung</h2>
    </div>

    <!-- #1710: Suche über Firma, Projekt und Produkt. -->
    <SidebarSearch
      v-if="!loading && rb.projekte.length >= 8"
      v-model="suche"
      placeholder="Firma, Produkt oder Bewertung …"
      :treffer="trefferAnzahl"
      :gesamt="totalCount"
      einheit="Bewertungen"
      zeige-aufklappen
      @expand-all="alleAufklappen"
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
            </div>
          </div>
        </template>
      </template>
      <div v-if="rb.projekte.length === 0" class="sidebar-empty">
        Keine Projekte
      </div>
      <div v-else-if="grouped.length === 0" class="sidebar-empty">
        Kein Treffer für „{{ suche }}"
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRisikobewertungStore } from '../../stores/risikobewertung'
import SidebarSearch from './SidebarSearch.vue'
import { useSidebarFilter } from '../../composables/useSidebarFilter'

const rb = useRisikobewertungStore()
const loading = ref(false)
const { suche, suchtGerade, matches, istEingeklappt, toggleGruppe, alleAufklappen } =
  useSidebarFilter('risikobewertung')

// Issue #433: Projekte nach Firma (unternehmen) gruppieren.
// Innerhalb einer Gruppe nach Projekt-Name sortiert.
const grouped = computed(() => {
  // Risiko-Counts aus rb.risiken aggregieren
  const counts = new Map<string, number>()
  for (const r of rb.risiken) {
    if (!r.projekt) continue
    counts.set(r.projekt, (counts.get(r.projekt) ?? 0) + 1)
  }

  const groupsMap = new Map<string, any[]>()
  for (const p of rb.projekte) {
    const firma = (p as any).unternehmen || (p as any).company || ''
    // #1710: Treffer auf Firmenebene behält die ganze Gruppe.
    if (!matches(firma, p.name, (p as any).produkt, p.framework)) continue
    const list = groupsMap.get(firma) ?? []
    list.push({
      name: p.name,
      framework: p.framework,
      produkt: (p as any).produkt || '',
      count: counts.get(p.name) ?? p.risiken_count ?? 0,
    })
    groupsMap.set(firma, list)
  }

  // Innerhalb jeder Gruppe sortieren
  const result = Array.from(groupsMap.entries()).map(([firma, projekte]) => ({
    firma,
    projekte: projekte.sort((a, b) => a.name.localeCompare(b.name)),
  }))
  // Firmen alphabetisch, leere Gruppe nach hinten
  result.sort((a, b) => {
    if (!a.firma && b.firma) return 1
    if (a.firma && !b.firma) return -1
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
</style>
