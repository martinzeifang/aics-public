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

    <!-- Brücke: aus einem Audit lässt sich ein Gutachten ableiten (#1713) -->
    <button class="bruecke" @click="router.push('/gutachten/gerichts')">
      ⚖ Zu den Gutachten →
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useComplianceAuditStore } from '../../stores/complianceAudit'
import ProjektSidebar from './ProjektSidebar.vue'

const router = useRouter()
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
.bruecke { padding: 8px 12px; background: white; border: 1px solid #ddd; border-radius: 4px;
           cursor: pointer; text-align: left; font-size: 13px; }
.bruecke:hover { border-color: #5d4037; }
</style>
