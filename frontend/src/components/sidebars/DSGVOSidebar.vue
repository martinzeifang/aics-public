<template>
  <ProjektSidebar
    title="DSGVO Projekte"
    :items="store.projekte"
    :loading="loading"
    :selected-key="store.selectedProjekt"
    empty-text="Keine DSGVO-Projekte"
    :get-key="(p: any) => p.name || p.id"
    :get-name="(p: any) => p.name"
    :get-company="(p: any) => p.company || p.unternehmen"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDsgvoStore } from '../../stores/dsgvo'
import ProjektSidebar from './ProjektSidebar.vue'

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

const onSelect = (proj: any) => {
  if (proj) {
    store.selectedProjekt = proj.name || proj.id
    store.fetchAnforderungen?.(proj.name)
  }
}
</script>
