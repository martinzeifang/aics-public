<template>
  <ProjektSidebar
    title="NIS2 Projekte"
    :items="store.projekte"
    :loading="loading"
    :selected-key="store.selectedProjekt"
    empty-text="Keine NIS2-Projekte"
    :get-key="(p: any) => p.name || p.id"
    :get-name="(p: any) => p.name"
    :get-company="(p: any) => p.company || p.unternehmen"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useNis2Store } from '../../stores/nis2'
import ProjektSidebar from './ProjektSidebar.vue'

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

const onSelect = (proj: any) => {
  if (proj) {
    store.selectedProjekt = proj.name || proj.id
    store.fetchMassnahmen?.(proj.name)
  }
}
</script>
