<template>
  <div class="gutachten-sidebar">
    <ProjektSidebar
      title="Gutachten"
      :items="ggStore.projekte"
      :loading="ggLoading"
      :selected-key="ggStore.aktuell?.name"
      empty-text="Keine Gutachten"
      :get-key="(p: any) => p.name"
      :get-name="(p: any) => p.name"
      :get-company="(p: any) => p.aktenzeichen || '(ohne AZ)'"
      :on-select="onSelectGerichts"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useGerichtsgutachtenStore } from '../../stores/gerichtsgutachten'
import ProjektSidebar from './ProjektSidebar.vue'

const ggStore = useGerichtsgutachtenStore()
const ggLoading = ref(false)

onMounted(async () => {
  ggLoading.value = true
  try { await ggStore.fetchProjekte() } finally { ggLoading.value = false }
})

const onSelectGerichts = (p: any) => { if (p) ggStore.fetchProjekt(p.name) }
</script>

<style scoped>
.gutachten-sidebar { display: flex; flex-direction: column; gap: 12px; }
</style>
