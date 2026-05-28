<template>
  <KundenSidebarModul
    title="AI-Act-Bewertungen"
    module-label="AI Act"
    :items="itemsNormalized"
    :loading="loading"
    :selected-key="store.selectedProjekt"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import KundenSidebarModul from './KundenSidebarModul.vue'

// Issue #434: AI Act ist kundenbezogen (1:1). Sidebar zeigt Kunden,
// nicht Projekte. Anlage ueber Kundenverwaltung (Auto-Anlage in #430).
// AI Act nutzt 'organisation' statt 'unternehmen' — wir normalisieren.
const store = useAiActStore()
const loading = ref(false)

const itemsNormalized = computed(() =>
  store.projekte.map((p: any) => ({
    ...p,
    unternehmen: p.unternehmen || p.company || p.organisation || '',
  })),
)

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
