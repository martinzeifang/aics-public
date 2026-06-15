<template>
  <div class="risk-cockpit-panel">
    <div v-if="loading" class="hint">Lädt Risiko-Cockpit…</div>
    <div v-else-if="error" class="alert-error">{{ error }}</div>
    <RiskCockpit v-else-if="firmenId != null" :firmen-id="firmenId" />
    <div v-else class="hint unassigned">
      Projekt keiner Firma zugeordnet — im Admin zuordnen (Firmen-Zuordnung).
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import apiClient from '../../api/client'
import RiskCockpit from '../shared/RiskCockpit.vue'

const props = defineProps<{
  /** CRA-Projektname, dessen Firma aufgelöst werden soll. */
  projekt: string
}>()

const firmenId = ref<number | null>(null)
const loading = ref(false)
const error = ref('')

const resolve = async () => {
  firmenId.value = null
  error.value = ''
  if (!props.projekt) return
  loading.value = true
  try {
    const r = await apiClient.get(
      '/risk-cockpit/by-projekt/cra/' + encodeURIComponent(props.projekt),
    )
    const data = r.data || {}
    if (data.firmen_id != null && !data.unassigned) {
      firmenId.value = Number(data.firmen_id)
    } else {
      firmenId.value = null
    }
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Risiko-Cockpit konnte nicht geladen werden.'
  } finally {
    loading.value = false
  }
}

onMounted(resolve)
watch(() => props.projekt, resolve)
</script>

<style scoped>
.risk-cockpit-panel { padding: 8px 0; }
.hint { color: #666; font-size: 14px; padding: 16px 0; }
.unassigned {
  background: #fff8e1; color: #e65100; padding: 12px 16px;
  border: 1px solid #ffd54f; border-radius: 6px;
}
.alert-error {
  background: #ffebee; color: #c62828; padding: 10px 14px;
  border-radius: 4px; border: 1px solid #ef5350;
}
</style>
