<template>
  <div class="import-btn-wrap">
    <input
      ref="fileInput"
      type="file"
      accept=".xlsx"
      :multiple="multiple"
      style="display:none"
      @change="onFile"
    />
    <button
      :class="['btn-' + variant]"
      :disabled="busy || disabled"
      @click="(fileInput as any)?.click()"
    >
      {{ busy ? 'Importiere…' : (label || '⬆️ Excel importieren') }}
    </button>
    <span v-if="msg" :class="['hint', errorState ? 'err' : 'ok']">{{ msg }}</span>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import apiClient from '../../api/client'

const props = defineProps<{
  endpoint: string
  label?: string
  multiple?: boolean
  variant?: 'primary' | 'secondary'
  disabled?: boolean
}>()

const emit = defineEmits<{ (e: 'imported', payload: any): void }>()

const fileInput = ref<HTMLInputElement | null>(null)
const busy = ref(false)
const msg = ref('')
const errorState = ref(false)

const onFile = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return

  busy.value = true
  msg.value = ''
  errorState.value = false
  try {
    const fd = new FormData()
    for (const f of files) fd.append('file', f)
    const res = await apiClient.post(props.endpoint, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const n = res.data?.imported ?? files.length
    msg.value = `${n} Einträge importiert.`
    emit('imported', res.data)
  } catch (err: any) {
    errorState.value = true
    msg.value = `Fehler: ${err.response?.data?.error || err.message}`
  } finally {
    busy.value = false
    input.value = ''
  }
}
</script>

<style scoped>
.import-btn-wrap {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}
.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  padding: 8px 14px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary {
  background: var(--color-background);
  color: var(--color-primary);
  border: 1px solid var(--color-border);
  padding: 8px 14px;
  border-radius: 4px;
  cursor: pointer;
}
.hint { font-size: 13px; color: var(--color-text-secondary); }
.hint.err { color: var(--color-error); }
.hint.ok { color: var(--color-success); }
</style>
