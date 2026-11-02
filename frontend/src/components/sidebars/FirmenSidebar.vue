<template>
  <ProjektSidebar
    title="Firmen"
    :items="firmenStore.firmen"
    :loading="loading"
    :selected-key="firmenStore.selectedFirma?.id ?? null"
    empty-text="Keine Firmen"
    :get-key="(k: any) => k.id"
    :get-name="(k: any) => k.name"
    :get-company="(k: any) => k.unternehmen"
    :on-select="onSelect"
    :on-new="onNew"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useFirmenStore } from '../../stores/firmen'
import ProjektSidebar from './ProjektSidebar.vue'

const router = useRouter()
const firmenStore = useFirmenStore()
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    await firmenStore.fetchFirmen()
  } finally {
    loading.value = false
  }
})

const onSelect = (firma: any) => {
  if (firma) firmenStore.selectedFirma = firma
}

const onNew = () => {
  router.push('/firmen?new=true')
}
</script>
