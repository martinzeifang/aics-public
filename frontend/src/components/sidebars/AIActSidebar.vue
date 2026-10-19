<template>
  <div class="aiact-sidebar">
    <div class="sidebar-header">
      <h2>AI-Act-Bewertungen</h2>
    </div>

    <div v-if="loading" class="sidebar-loading">Lädt…</div>

    <div v-else class="sidebar-list">
      <!-- #1543: hybrides Modell (Epic #1540) — je Firma die Organisation
           (firmenweite Pflichten, z. B. Art. 4) + ihre KI-Systeme (je Produkt). -->
      <template v-for="group in grouped" :key="group.firma || '__none__'">
        <div class="firma-header">
          <span class="firma-name">{{ group.firma || '— Ohne Firma —' }}</span>
          <span class="firma-count" :title="`${group.systeme.length} KI-System(e)`">{{ group.systeme.length }}</span>
        </div>
        <div
          v-for="p in group.orgs"
          :key="p.name"
          @click="onSelect(p.name)"
          :class="['sidebar-item', { active: store.selectedProjekt === p.name }]"
        >
          <div class="proj-name">🏢 {{ p.name }}</div>
          <div class="proj-meta">Organisation</div>
        </div>
        <div
          v-for="p in group.systeme"
          :key="p.name"
          @click="onSelect(p.name)"
          :class="['sidebar-item', 'system', { active: store.selectedProjekt === p.name }]"
        >
          <div class="proj-name">🤖 {{ p.produkt || p.name }}</div>
          <div class="proj-produkt">KI-System</div>
        </div>
      </template>

      <div v-if="store.projekte.length === 0" class="sidebar-empty">
        <p>Keine AI-Act-Bewertungen.</p>
        <p class="hint-text">
          Die Organisations-Bewertung entsteht automatisch, wenn in der
          Firmenverwaltung das AI-Act-Modul aktiv ist. KI-Systeme legst du
          danach je Produkt in der Bewertung an.
        </p>
        <router-link to="/firmen" class="link-btn">→ Zur Firmenverwaltung</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAiActStore } from '../../stores/aiact'

const store = useAiActStore()
const loading = ref(false)

const grouped = computed(() => {
  const map = new Map<string, { firma: string; orgs: any[]; systeme: any[] }>()
  for (const p of store.projekte as any[]) {
    const firma = p.organisation || p.company || p.unternehmen || ''
    const g = map.get(firma) ?? { firma, orgs: [], systeme: [] }
    ;(p.scope === 'system' ? g.systeme : g.orgs).push(p)
    map.set(firma, g)
  }
  const byName = (a: any, b: any) => String(a.produkt || a.name).localeCompare(String(b.produkt || b.name))
  const result = Array.from(map.values()).map(g => ({
    ...g, orgs: g.orgs.sort(byName), systeme: g.systeme.sort(byName),
  }))
  result.sort((a, b) => {
    if (!a.firma && b.firma) return 1
    if (a.firma && !b.firma) return -1
    return a.firma.localeCompare(b.firma)
  })
  return result
})

onMounted(async () => {
  loading.value = true
  try {
    await store.fetchProjekte()
  } finally {
    loading.value = false
  }
})

const onSelect = (key: string) => {
  store.selectedProjekt = key
  store.fetchAnforderungen?.(key)
}
</script>

<style scoped>
.aiact-sidebar { display: flex; flex-direction: column; gap: 8px; height: 100%; overflow: hidden; }
.sidebar-header { padding-bottom: 8px; border-bottom: 1px solid var(--color-border); }
.sidebar-header h2 {
  margin: 0; font-size: 13px; font-weight: 700; color: var(--color-primary);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.sidebar-loading { text-align: center; color: #999; font-size: 13px; padding: 20px; }
.sidebar-list { display: flex; flex-direction: column; gap: 2px; overflow-y: auto; flex: 1; }
.firma-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 10px 4px; font-size: 11px; font-weight: 700;
  color: var(--color-text-secondary, #666); text-transform: uppercase;
  letter-spacing: 0.4px; margin-top: 6px;
}
.firma-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.firma-count {
  background: var(--color-background, #f5f5f5); color: var(--color-text-secondary, #666);
  padding: 2px 7px; border-radius: 9px; font-size: 10px; font-weight: 600;
}
.sidebar-item {
  padding: 10px 12px; background: white; border-radius: 4px; cursor: pointer;
  border-left: 3px solid transparent; transition: all 0.15s;
}
.sidebar-item.system { margin-left: 12px; padding: 8px 12px; }
.sidebar-item:hover { background: #f5f5f5; border-left-color: var(--color-primary); }
.sidebar-item.active { background: #e3f2fd; border-left-color: var(--color-primary); }
.proj-name { font-size: 13px; font-weight: 500; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.proj-produkt { font-size: 11px; color: #666; margin-top: 2px; font-style: italic; }
.proj-meta { font-size: 10px; color: var(--color-primary); margin-top: 2px; font-weight: 600; }
.sidebar-empty { padding: 16px 12px; text-align: center; color: #888; }
.sidebar-empty p { font-size: 12px; margin: 0 0 8px 0; }
.hint-text { font-size: 11px; color: #888; line-height: 1.45; }
.link-btn {
  display: inline-block; margin-top: 12px; padding: 6px 12px; background: var(--color-primary);
  color: white; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: 500;
}
</style>
