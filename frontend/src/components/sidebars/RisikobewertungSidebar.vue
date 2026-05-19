<template>
  <div class="rb-sidebar">
    <div class="sidebar-header">
      <h2>Risikobewertung</h2>
    </div>

    <div v-if="loading" class="sidebar-loading">Lädt…</div>

    <div v-else class="sidebar-list">
      <div
        @click="onSelect(null)"
        :class="['sidebar-item all-item', { active: rb.selectedProjekt === null }]"
      >
        <div class="proj-name">— Alle Projekte —</div>
        <div class="proj-meta">{{ totalCount }} {{ totalCount === 1 ? 'Projekt' : 'Projekte' }}</div>
      </div>

      <!-- Issue #433: Gruppierung nach Kunde -->
      <template v-for="group in grouped" :key="group.kunde || '__none__'">
        <div class="kunde-header">
          <span class="kunde-name">{{ group.kunde || '— Ohne Kunde —' }}</span>
          <span class="kunde-count">{{ group.projekte.length }}</span>
        </div>
        <div
          v-for="p in group.projekte"
          :key="p.name"
          @click="onSelect(p)"
          :class="['sidebar-item', { active: rb.selectedProjekt === p.name }]"
        >
          <div class="proj-name">{{ p.name }}</div>
          <div v-if="p.produkt" class="proj-produkt">{{ p.produkt }}</div>
          <div class="proj-meta">
            {{ p.framework }} · {{ p.count }} {{ p.count === 1 ? 'Risiko' : 'Risiken' }}
          </div>
        </div>
      </template>

      <div v-if="rb.projekte.length === 0" class="sidebar-empty">
        Keine Projekte
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRisikobewertungStore } from '../../stores/risikobewertung'

const rb = useRisikobewertungStore()
const loading = ref(false)

// Issue #433: Projekte nach Kunde (unternehmen) gruppieren.
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
    const kunde = (p as any).unternehmen || (p as any).company || ''
    const list = groupsMap.get(kunde) ?? []
    list.push({
      name: p.name,
      framework: p.framework,
      produkt: (p as any).produkt || '',
      count: counts.get(p.name) ?? p.risiken_count ?? 0,
    })
    groupsMap.set(kunde, list)
  }

  // Innerhalb jeder Gruppe sortieren
  const result = Array.from(groupsMap.entries()).map(([kunde, projekte]) => ({
    kunde,
    projekte: projekte.sort((a, b) => a.name.localeCompare(b.name)),
  }))
  // Kunden alphabetisch, leere Gruppe nach hinten
  result.sort((a, b) => {
    if (!a.kunde && b.kunde) return 1
    if (a.kunde && !b.kunde) return -1
    return a.kunde.localeCompare(b.kunde)
  })
  return result
})

const totalCount = computed(() => rb.projekte.length)

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([rb.fetchProjekte(), rb.fetchRisiken()])
  } finally {
    loading.value = false
  }
})

const onSelect = (proj: any) => {
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

.kunde-header {
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

.kunde-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.kunde-count {
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
