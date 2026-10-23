<template>
  <div class="audit-sidebar">
    <ProjektSidebar
      title="Audits"
      :items="store.projekte"
      :loading="loading"
      :selected-key="store.selectedProjekt"
      empty-text="Keine Audits"
      :get-key="(p: any) => p.name || p.id"
      :get-name="(p: any) => p.name"
      :get-company="(p: any) => p.unternehmen || (p.frameworks || []).join(', ')"
      :on-select="onSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useComplianceAuditStore } from '../../stores/complianceAudit'
import ProjektSidebar from './ProjektSidebar.vue'

const store = useComplianceAuditStore()
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try { await store.fetchProjekte() } finally { loading.value = false }
})

const onSelect = (p: any) => { if (p) store.selectedProjekt = p.name || p.id }
</script>

<style scoped>
.audit-sidebar { display: flex; flex-direction: column; gap: 12px; }
</style>
