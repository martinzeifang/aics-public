<template>
  <ProjektSidebar
    title="AI Act Projekte"
    :items="store.projekte"
    :loading="loading"
    :selected-key="store.selectedProjekt"
    empty-text="Keine AI-Act-Projekte"
    :get-key="(p: any) => p.name || p.id"
    :get-name="(p: any) => p.name"
    :get-company="(p: any) => p.company || p.unternehmen || p.organisation"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAiActStore } from '../../stores/aiact'
import ProjektSidebar from './ProjektSidebar.vue'

const store = useAiActStore()
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
    store.fetchAnforderungen?.(proj.name || proj.id)
  }
}
</script>
