<template>
  <div class="admin-settings">
    <header class="page-header">
      <h1>⚙️ Einstellungen</h1>
      <p class="muted">
        KI-Provider, GitHub-Integration, Module, Backup, Erscheinungsbild —
        alles an einem Ort. Änderungen werden persistent im Server-Volume gespeichert.
      </p>
    </header>

    <SettingsDialog :open="true" :embedded="true" @close="onClose" />
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import SettingsDialog from '../../components/SettingsDialog.vue'

const router = useRouter()
function onClose() {
  router.push('/admin')
}
</script>

<style scoped>
.admin-settings { max-width: 1200px; padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0 0 4px; }
.muted { color: var(--color-text-muted, #666); margin: 0; }
</style>
