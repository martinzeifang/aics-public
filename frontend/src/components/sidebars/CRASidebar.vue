<template>
  <ProjektSidebar
    title="CRA Projekte"
    :items="craStore.projekte"
    :loading="loading"
    :selected-key="selectedKey"
    empty-text="Keine CRA-Projekte"
    :get-key="(p: any) => p.name"
    :get-name="(p: any) => p.name"
    :get-company="(p: any) => p.company || p.unternehmen"
    :on-select="onSelect"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useCraStore } from '../../stores/cra'
import ProjektSidebar from './ProjektSidebar.vue'

const craStore = useCraStore()
const loading = ref(false)

const selectedKey = computed(() => {
  if (typeof craStore.selectedProjekt === 'string') return craStore.selectedProjekt
  return craStore.selectedProjekt?.name ?? null
})

onMounted(async () => {
  loading.value = true
  try {
    await craStore.fetchProjekte()
  } finally {
    loading.value = false
  }
})

const onSelect = (proj: any) => {
  if (proj) {
    craStore.selectedProjekt = proj.name
    craStore.fetchAnforderungen(proj.name)
    craStore.fetchOwaspControls?.(proj.name)
  }
}
</script>
