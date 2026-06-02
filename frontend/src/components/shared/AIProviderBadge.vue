<template>
  <router-link
    to="/admin/settings"
    class="ai-provider-badge"
    :class="statusClass"
    :title="tooltip"
    role="status"
    aria-live="polite"
  >
    <span class="apb-icon" aria-hidden="true">{{ icon }}</span>
    <span class="apb-label">{{ label }}</span>
    <span class="apb-status">{{ statusText }}</span>
  </router-link>
</template>

<script setup lang="ts">
/**
 * AIProviderBadge — zeigt den aktiven KI-Provider in der Topbar (#867).
 *
 * Liest den read-only Status von GET /api/ai/provider-status:
 *   { provider: 'on_prem'|'cloud'|'none', label, configured, allow_data_egress }
 *
 * - 🏠 Lokal (Ollama): keine Daten verlassen das Netzwerk.
 * - ☁️ Cloud: Egress-Status (erlaubt/blockiert) wird sichtbar gemacht (#877).
 *
 * Klick führt zu den Admin-Einstellungen. Teil von #865.
 */
import { ref, computed, onMounted } from 'vue'
import apiClient from '../../api/client'

interface ProviderStatus {
  provider: 'on_prem' | 'cloud' | 'none'
  label: string
  configured: boolean
  allow_data_egress: boolean
}

const status = ref<ProviderStatus | null>(null)
const loadError = ref(false)

const provider = computed(() => status.value?.provider ?? 'none')
const configured = computed(() => !!status.value?.configured)
const allowEgress = computed(() => !!status.value?.allow_data_egress)

const icon = computed(() => {
  if (provider.value === 'cloud') return '☁️'
  if (provider.value === 'on_prem') return '🏠'
  return '🤖'
})

const label = computed(() => {
  if (loadError.value) return 'KI-Status'
  if (provider.value === 'cloud') return 'Cloud'
  if (provider.value === 'on_prem') return 'Lokal (Ollama)'
  return status.value?.label || 'Kein Provider'
})

const statusText = computed(() => {
  if (loadError.value) return 'nicht verfügbar'
  if (!status.value) return '…'
  if (provider.value === 'cloud') {
    if (!allowEgress.value) return 'Egress blockiert'
    return configured.value ? 'konfiguriert' : 'nicht konfiguriert'
  }
  return configured.value ? 'konfiguriert' : 'nicht konfiguriert'
})

const statusClass = computed(() => ({
  'apb-cloud': provider.value === 'cloud',
  'apb-local': provider.value === 'on_prem',
  'apb-none': provider.value === 'none' || loadError.value,
  'apb-unconfigured': !configured.value && !loadError.value,
}))

const tooltip = computed(() => {
  if (loadError.value) return 'KI-Provider-Status konnte nicht geladen werden.'
  if (provider.value === 'on_prem') {
    return (
      'Aktiver KI-Provider: Lokal (Ollama).\n'
      + 'Daten werden lokal verarbeitet und verlassen dein Netzwerk nicht.\n'
      + (configured.value ? 'Status: konfiguriert.' : 'Status: kein Modell konfiguriert.')
      + '\nKlicken für Einstellungen.'
    )
  }
  if (provider.value === 'cloud') {
    return (
      'Aktiver KI-Provider: Cloud.\n'
      + (allowEgress.value
        ? 'Achtung: Daten können dein Netzwerk verlassen (Egress erlaubt).'
        : 'Egress blockiert: Cloud-Nutzung erfordert Zustimmung (allow_data_egress).')
      + '\nKlicken für Einstellungen.'
    )
  }
  return 'Kein KI-Provider konfiguriert. Klicken für Einstellungen.'
})

async function loadStatus() {
  try {
    const { data } = await apiClient.get<ProviderStatus>('/ai/provider-status')
    status.value = data
    loadError.value = false
  } catch (e) {
    loadError.value = true
  }
}

onMounted(loadStatus)

defineExpose({ loadStatus })
</script>

<style scoped>
.ai-provider-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  text-decoration: none;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.35);
  white-space: nowrap;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.ai-provider-badge:hover {
  background: rgba(255, 255, 255, 0.28);
}

.apb-icon {
  font-size: 13px;
}

.apb-label {
  font-weight: 600;
}

.apb-status {
  opacity: 0.85;
  font-size: 11px;
}

/* Lokal: dezent grünlich — Daten bleiben lokal. */
.apb-local {
  background: rgba(76, 175, 80, 0.28);
  border-color: rgba(165, 214, 167, 0.6);
}

/* Cloud (Egress erlaubt): deutlicher Hinweis (amber). */
.apb-cloud {
  background: rgba(255, 152, 0, 0.32);
  border-color: rgba(255, 224, 130, 0.6);
}

/* Nicht konfiguriert / Egress blockiert / unbekannt: gedämpft. */
.apb-unconfigured,
.apb-none {
  background: rgba(255, 255, 255, 0.12);
}
</style>
