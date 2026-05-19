<template>
  <ProjektSidebar
    title="Gutachten Projekte"
    :items="store.projekte"
    :loading="loading"
    :selected-key="store.selectedProjekt"
    empty-text="Keine Gutachten"
    :get-key="(p: any) => p.name || p.id"
    :get-name="(p: any) => p.name"
    :get-company="(p: any) => (p.frameworks || []).join(', ')"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useGutachtenStore } from '../../stores/gutachten'
import ProjektSidebar from './ProjektSidebar.vue'

const store = useGutachtenStore()
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    await store.fetchProjekte()
  } finally {
    loading.value = false
  }
})

const onSelect = (p: any) => {
  if (p) store.selectedProjekt = p.name || p.id
}
</script>
