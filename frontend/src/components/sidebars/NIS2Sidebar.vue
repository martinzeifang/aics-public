<template>
  <FirmenSidebarModul
    title="NIS2-Bewertungen"
    module-label="NIS2"
    :items="store.projekte"
    :loading="loading"
    :selected-key="store.selectedProjekt"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNis2Store } from '../../stores/nis2'
import FirmenSidebarModul from './FirmenSidebarModul.vue'

// Issue #434: NIS2 ist firmenbezogen (1:1). Sidebar zeigt Firmen,
// nicht Projekte. Anlage ueber Firmenverwaltung (Auto-Anlage in #430).
const store = useNis2Store()
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    await store.fetchProjekte()
  } finally {
    loading.value = false
  }
})

const onSelect = (key: string | null) => {
  if (key) {
    store.selectedProjekt = key
    store.fetchMassnahmen?.(key)
  }
}
</script>
