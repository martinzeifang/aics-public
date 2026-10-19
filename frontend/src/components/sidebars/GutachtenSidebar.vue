<template>
  <div class="gutachten-sidebar">
    <!-- Switcher zwischen den beiden Gutachten-Arten -->
    <div class="art-switcher">
      <button :class="['art-btn', { active: route.path === '/gutachten' }]"
              @click="goTo('/gutachten')">
        📊 Compliance-Audit
      </button>
      <button :class="['art-btn', { active: route.path.startsWith('/gutachten/gerichts') }]"
              @click="goTo('/gutachten/gerichts')">
        ⚖ Gerichtsgutachten (BISG)
      </button>
    </div>

    <ProjektSidebar
      v-if="route.path === '/gutachten'"
      title="Audit-Berichte"
      :items="store.projekte"
      :loading="loading"
      :selected-key="store.selectedProjekt"
      empty-text="Keine Audit-Berichte"
      :get-key="(p: any) => p.name || p.id"
      :get-name="(p: any) => p.name"
      :get-company="(p: any) => (p.frameworks || []).join(', ')"
      :on-select="onSelectAudit"
    />

    <ProjektSidebar
      v-else
      title="Gerichtsgutachten"
      :items="ggStore.projekte"
      :loading="ggLoading"
      :selected-key="ggStore.aktuell?.name"
      empty-text="Keine Gerichtsgutachten"
      :get-key="(p: any) => p.name"
      :get-name="(p: any) => p.name"
      :get-company="(p: any) => p.aktenzeichen || '(ohne AZ)'"
      :on-select="onSelectGerichts"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGutachtenStore } from '../../stores/gutachten'
import { useGerichtsgutachtenStore } from '../../stores/gerichtsgutachten'
import ProjektSidebar from './ProjektSidebar.vue'

const route = useRoute()
const router = useRouter()
const store = useGutachtenStore()
const ggStore = useGerichtsgutachtenStore()
const loading = ref(false)
const ggLoading = ref(false)

const loadAudit = async () => {
  loading.value = true
  try { await store.fetchProjekte() } finally { loading.value = false }
}
const loadGerichts = async () => {
  ggLoading.value = true
  try { await ggStore.fetchProjekte() } finally { ggLoading.value = false }
}

onMounted(() => {
  if (route.path.startsWith('/gutachten/gerichts')) loadGerichts()
  else loadAudit()
})

watch(() => route.path, (p) => {
  if (p.startsWith('/gutachten/gerichts')) loadGerichts()
  else if (p === '/gutachten') loadAudit()
})

const onSelectAudit = (p: any) => { if (p) store.selectedProjekt = p.name || p.id }
const onSelectGerichts = (p: any) => { if (p) ggStore.fetchProjekt(p.name) }
const goTo = (path: string) => router.push(path)
</script>

<style scoped>
.gutachten-sidebar { display: flex; flex-direction: column; gap: 12px; }
.art-switcher { display: flex; flex-direction: column; gap: 4px; padding: 8px; background: #f5f5f5; border-radius: 4px; }
.art-btn { padding: 8px 12px; background: white; border: 1px solid #ddd; border-radius: 4px;
           cursor: pointer; text-align: left; font-size: 13px; }
.art-btn:hover { border-color: #5d4037; }
.art-btn.active { background: #5d4037; color: white; border-color: #3e2723; font-weight: 600; }
</style>
