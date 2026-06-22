<template>
  <div class="status-bar">
    <div class="status-left">
      <span class="status-item">
        <span class="status-dot" :class="{ online: connected, offline: !connected }"></span>
        {{ connected ? 'Verbunden' : 'Keine Verbindung' }}
      </span>
      <span class="status-divider">|</span>
      <span class="status-item">{{ currentModuleLabel }}</span>
    </div>

    <div class="status-right">
      <span class="status-item" v-if="authStore.user">
        Rolle: <strong>{{ authStore.user.roles?.[0] || 'user' }}</strong>
      </span>
      <span class="status-divider">|</span>
      <span class="status-item">v{{ appVersion }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import apiClient from '../api/client'
// #1050: angezeigte Version aus package.json (Single Source of Truth)
import { version as appVersion } from '../../package.json'

const authStore = useAuthStore()
const route = useRoute()
const connected = ref(true)

const moduleLabels: Record<string, string> = {
  firmen: 'Firmenverwaltung',
  risikobewertung: 'Risikobewertung',
  cra: 'Cyber Resilience Act',
  dsgvo: 'DSGVO',
  nis2: 'NIS2',
  gutachten: 'Gutachten',
  aiact: 'EU AI Act',
  admin: 'Administration',
}

const currentModuleLabel = computed(() => {
  const path = route.path.split('/')[1] || ''
  return moduleLabels[path] || 'Dashboard'
})

let interval: number | undefined

const ping = async () => {
  try {
    await apiClient.get('/health', { timeout: 3000 })
    connected.value = true
  } catch {
    connected.value = false
  }
}

onMounted(() => {
  ping()
  interval = window.setInterval(ping, 30000)
})

onUnmounted(() => {
  if (interval) window.clearInterval(interval)
})
</script>

<style scoped>
.status-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 28px;
  background: #1565c0;
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  font-size: 12px;
  z-index: 50;
  box-shadow: 0 -1px 3px rgba(0, 0, 0, 0.1);
}

.status-left,
.status-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-dot.online {
  background: #4caf50;
  box-shadow: 0 0 4px #4caf50;
}

.status-dot.offline {
  background: #f44336;
}

.status-divider {
  opacity: 0.5;
}

@media (max-width: 768px) {
  .status-bar {
    font-size: 11px;
    padding: 0 8px;
  }
  .status-divider {
    display: none;
  }
}
</style>
