<template>
  <div class="wiba-sidebar">
    <div class="sidebar-header">
      <h2>WiBA-Projekte</h2>
    </div>

    <!-- #1710: Mandanten-Suche. -->
    <SidebarSearch
      v-if="!loading && store.projekte.length >= 8"
      v-model="suche"
      placeholder="Firma oder Projekt …"
      :treffer="trefferAnzahl"
      :gesamt="store.projekte.length"
      einheit="Projekten"
      zeige-aufklappen
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
import SidebarSearch from './SidebarSearch.vue'
import { useSidebarFilter } from '../../composables/useSidebarFilter'

const store = useWibaStore()
const loading = ref(false)
const { suche, matches, istEingeklappt, toggleGruppe, alleAufklappen } = useSidebarFilter('wiba')

const grouped = computed(() => {
  const map: Record<string, any[]> = {}
  for (const p of store.projekte as any[]) {
    const f = p.unternehmen || ''
    // #1710: Treffer auf Firmenebene behält die ganze Gruppe.
    if (!matches(f, p.name)) continue
    ;(map[f] ||= []).push(p)
  }
  return Object.keys(map)
    .sort((a, b) => a.localeCompare(b))
    .map((firma) => ({ firma, projekte: map[firma] }))
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
