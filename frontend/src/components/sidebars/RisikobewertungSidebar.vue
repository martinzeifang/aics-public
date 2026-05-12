<template>
  <ProjektSidebar
    title="Risikobewertung"
    :items="projekteList"
    :loading="loading"
    :selected-key="rb.selectedProjekt"
    :show-all-option="true"
    empty-text="Keine Projekte"
    :get-key="(p: any) => p.name"
    :get-name="(p: any) => p.name"
    :get-meta="(p: any) => `${p.count} Risiken`"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRisikobewertungStore } from '../../stores/risikobewertung'
import ProjektSidebar from './ProjektSidebar.vue'

const rb = useRisikobewertungStore()
const loading = ref(false)

const projekteList = computed(() => {
  const map = new Map<string, number>()
  for (const r of rb.risiken) {
    if (!r.projekt) continue
    map.set(r.projekt, (map.get(r.projekt) ?? 0) + 1)
  }
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => a.name.localeCompare(b.name))
})

onMounted(async () => {
  loading.value = true
  try {
    await rb.fetchRisiken()
  } finally {
    loading.value = false
  }
})

const onSelect = (proj: any) => {
  rb.selectedProjekt = proj?.name ?? null
}
</script>
