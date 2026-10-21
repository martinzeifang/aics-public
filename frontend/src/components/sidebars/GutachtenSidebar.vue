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

    <!-- Das Compliance-Audit ist seit v7.4.0 ein eigenes Modul (#1713). -->
    <button class="bruecke" @click="router.push('/compliance-audit')">
      📊 Zu den Compliance-Audits →
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGerichtsgutachtenStore } from '../../stores/gerichtsgutachten'
import ProjektSidebar from './ProjektSidebar.vue'

const router = useRouter()
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
.bruecke { padding: 8px 12px; background: white; border: 1px solid #ddd; border-radius: 4px;
           cursor: pointer; text-align: left; font-size: 13px; }
.bruecke:hover { border-color: #5d4037; }
</style>
