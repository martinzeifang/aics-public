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
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useAiProviderStore } from '../../stores/aiProvider'
import { t } from '../../i18n'

// #1342 Defekt A: Status kommt jetzt aus dem Pinia-Store (Single Source of
// Truth), damit die Badge nach einem Provider-Wechsel ohne Reload aktualisiert.
const aiProviderStore = useAiProviderStore()
const { status, error } = storeToRefs(aiProviderStore)

const loadError = computed(() => !!error.value)

const provider = computed(() => status.value?.provider ?? 'none')
const configured = computed(() => !!status.value?.configured)
const allowEgress = computed(() => !!status.value?.allow_data_egress)

const icon = computed(() => {
  if (provider.value === 'cloud') return '☁️'
  if (provider.value === 'on_prem') return '🏠'
  return '🤖'
})

const label = computed(() => {
  if (loadError.value) return t('geteilt.aIProviderBadge.kIStatus')
  if (provider.value === 'cloud') return t('common.cloud')
  if (provider.value === 'on_prem') return t('geteilt.aIProviderBadge.lokalOllama')
  return status.value?.label || t('geteilt.aIProviderBadge.keinProvider')
})

const statusText = computed(() => {
  if (loadError.value) return t('geteilt.aIProviderBadge.nichtVerfugbar')
  if (!status.value) return '…'
  if (provider.value === 'cloud') {
    if (!allowEgress.value) return t('geteilt.aIProviderBadge.egressBlockiert')
    return configured.value ? 'konfiguriert' : t('geteilt.aIProviderBadge.nichtKonfiguriert')
  }
  return configured.value ? 'konfiguriert' : t('geteilt.aIProviderBadge.nichtKonfiguriert')
})

const statusClass = computed(() => ({
  'apb-cloud': provider.value === 'cloud',
  'apb-local': provider.value === 'on_prem',
  'apb-none': provider.value === 'none' || loadError.value,
  'apb-unconfigured': !configured.value && !loadError.value,
}))

const tooltip = computed(() => {
  if (loadError.value) return t('geteilt.aIProviderBadge.kIProviderStatusKonnteNichtGeladenWe')
  if (provider.value === 'on_prem') {
    return (
      'Aktiver KI-Provider: Lokal (Ollama).\n'
      + t('geteilt.aIProviderBadge.datenWerdenLokalVerarbeitetUndVerlas')
      + (configured.value ? 'Status: konfiguriert.' : t('geteilt.aIProviderBadge.statusKeinModellKonfiguriert'))
      + t('geteilt.aIProviderBadge.nKlickenFurEinstellungen')
    )
  }
  if (provider.value === 'cloud') {
    return (
      'Aktiver KI-Provider: Cloud.\n'
      + (allowEgress.value
        ? t('geteilt.aIProviderBadge.achtungDatenKonnenDeinNetzwerkVerlas')
        : t('geteilt.aIProviderBadge.egressBlockiertCloudNutzungErfordert'))
      + t('geteilt.aIProviderBadge.nKlickenFurEinstellungen')
    )
  }
  return t('geteilt.aIProviderBadge.keinKIProviderKonfiguriertKlickenFur')
})

// Beim ersten Mount laden — nur wenn noch nicht geladen (Store ist persistent,
// die Badge wird im AppLayout nie unmountet). Spätere Aktualisierungen stößt
// der Settings-Speichern-Flow über aiProviderStore.loadStatus() an.
onMounted(() => {
  if (!aiProviderStore.loaded) aiProviderStore.loadStatus()
})

defineExpose({ loadStatus: aiProviderStore.loadStatus })
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
