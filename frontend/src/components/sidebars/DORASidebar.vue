<template>
  <ProjektSidebar
    title="DORA Projekte"
    :items="store.projekte"
    :loading="loading"
    :selected-key="store.selectedProjekt"
    empty-text="DORA-Modul noch nicht angelegt – siehe Issue #286"
    :get-key="(p: any) => p.name || p.id"
    :get-name="(p: any) => p.name"
    :get-company="(p: any) => p.company || p.organisation"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDoraStore } from '../../stores/dora'
import ProjektSidebar from './ProjektSidebar.vue'

const store = useDoraStore()
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
    store.fetchAnforderungen(proj.name || proj.id)
  }
}
</script>
