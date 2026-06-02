<template>
  <ProjektSidebar
    title="Kunden"
    :items="kundenStore.kunden"
    :loading="loading"
    :selected-key="kundenStore.selectedKunde?.id ?? null"
    empty-text="Keine Kunden"
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
import { useKundenStore } from '../../stores/kunden'
import ProjektSidebar from './ProjektSidebar.vue'

const router = useRouter()
const kundenStore = useKundenStore()
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    await kundenStore.fetchKunden()
  } finally {
    loading.value = false
  }
})

const onSelect = (kunde: any) => {
  if (kunde) kundenStore.selectedKunde = kunde
}

const onNew = () => {
  router.push('/kunden?new=true')
}
</script>
