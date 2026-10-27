<template>
  <FirmenSidebarModul
    title="DSGVO-Bewertungen"
    module-label="DSGVO"
    :items="store.projekte"
    :loading="loading"
    :selected-key="store.selectedProjekt"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import FirmenSidebarModul from './FirmenSidebarModul.vue'

// Issue #434: DSGVO ist firmenbezogen (1:1). Sidebar zeigt Firmen,
// nicht Projekte. Anlage ueber Firmenverwaltung (Auto-Anlage in #430).
const store = useDsgvoStore()
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
    store.fetchAnforderungen?.(key)
  }
}
</script>
