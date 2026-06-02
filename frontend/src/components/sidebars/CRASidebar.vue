<template>
  <div class="cra-sidebar">
    <div class="sidebar-header">
      <h2>CRA-Projekte</h2>
    </div>

    <div v-if="loading" class="sidebar-loading">Lädt…</div>

    <div v-else class="sidebar-list">
      <!-- Issue #435: Gruppierung nach Kunde (analog RB).
           Pro Produkt eines Kunden ein eigenes CRA-Projekt. -->
      <template v-for="group in grouped" :key="group.kunde || '__none__'">
        <div class="kunde-header">
          <span class="kunde-name">{{ group.kunde || '— Ohne Kunde —' }}</span>
          <span class="kunde-count">{{ group.projekte.length }}</span>
        </div>
        <div
          v-for="p in group.projekte"
          :key="p.name"
          @click="onSelect(p)"
          :class="['sidebar-item', { active: selectedKey === p.name }]"
        >
          <div class="proj-name">{{ p.name }}</div>
          <div v-if="p.produkt" class="proj-produkt">{{ p.produkt }}</div>
          <div v-if="p.produktklasse && p.produktklasse !== 'default'" class="proj-meta">
            {{ produktklasseLabel(p.produktklasse) }}
          </div>
        </div>
      </template>

      <div v-if="craStore.projekte.length === 0" class="sidebar-empty">
        <p>Keine CRA-Projekte.</p>
        <p class="hint-text">
          CRA-Projekte werden automatisch angelegt, wenn du in der
          Kundenverwaltung Produkte hinzufügst (1 Projekt pro Produkt).
        </p>
        <router-link to="/kunden" class="link-btn">→ Zur Kundenverwaltung</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useCraStore } from '../../stores/cra'

const craStore = useCraStore()
const loading = ref(false)

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

const grouped = computed(() => {
  const groupsMap = new Map<string, any[]>()
  for (const p of craStore.projekte) {
    const kunde = (p as any).unternehmen || (p as any).company || ''
    const list = groupsMap.get(kunde) ?? []
    list.push(p)
    groupsMap.set(kunde, list)
  }
  const result = Array.from(groupsMap.entries()).map(([kunde, projekte]) => ({
    kunde,
    projekte: projekte.sort((a: any, b: any) => a.name.localeCompare(b.name)),
  }))
  result.sort((a, b) => {
    if (!a.kunde && b.kunde) return 1
    if (a.kunde && !b.kunde) return -1
    return a.kunde.localeCompare(b.kunde)
  })
  return result
})

onMounted(async () => {
  loading.value = true
  try {
    await craStore.fetchProjekte()
  } finally {
    loading.value = false
  }
})

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
