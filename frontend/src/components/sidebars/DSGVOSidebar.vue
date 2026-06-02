<template>
  <KundenSidebarModul
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
import KundenSidebarModul from './KundenSidebarModul.vue'

// Issue #434: DSGVO ist kundenbezogen (1:1). Sidebar zeigt Kunden,
// nicht Projekte. Anlage ueber Kundenverwaltung (Auto-Anlage in #430).
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
