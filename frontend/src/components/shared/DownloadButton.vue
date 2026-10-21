<template>
  <button
    :class="['download-btn', variant ? 'variant-' + variant : 'variant-default']"
    :disabled="busy || disabled"
    :title="title || ''"
    @click="onClick"
  >
    <slot>{{ busy ? 'Lädt…' : (label || 'Download') }}</slot>
  </button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import apiClient from '../../api/client'

const props = defineProps<{
  endpoint: string
  filename?: string
  label?: string
  variant?: string
  title?: string
  disabled?: boolean
  /** Long-running endpoints: report-generation can take a while */
  timeoutMs?: number
}>()

const emit = defineEmits<{
  (e: 'error', message: string): void
  (e: 'success'): void
}>()

const busy = ref(false)

function filenameFromHeaders(headers: any, fallback: string): string {
  const cd = (headers?.['content-disposition'] || headers?.['Content-Disposition'] || '') as string
  const m = /filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?/i.exec(cd)
  if (m && m[1]) {
    try {
      return decodeURIComponent(m[1])
    } catch {
      return m[1]
    }
  }
  return fallback
}

const onClick = async () => {
  busy.value = true
  try {
    const res = await apiClient.get(props.endpoint, {
      responseType: 'blob',
      timeout: props.timeoutMs ?? 120000,
    })
    const blob = res.data as Blob

    // Wenn Server JSON-Error zurückgegeben hat (z.B. 500): Blob enthält JSON
    if (blob.type && blob.type.includes('application/json')) {
      const text = await blob.text()
      try {
        const json = JSON.parse(text)
        throw new Error(json.error || `HTTP ${res.status}`)
      } catch {
        throw new Error(text || `HTTP ${res.status}`)
      }
    }

    const fname = filenameFromHeaders(res.headers, props.filename || 'download')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fname
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    emit('success')
  } catch (err: any) {
    let msg: string
    if (err?.response?.data instanceof Blob) {
      try {
        const text = await err.response.data.text()
        const json = JSON.parse(text)
        msg = json.error || json.message || `HTTP ${err.response.status}`
      } catch {
        msg = `HTTP ${err.response?.status || ''} ${err.message || ''}`.trim()
      }
    } else if (err?.code === 'ECONNABORTED') {
      msg = 'Download-Timeout — Bericht-Generierung dauert zu lange.'
    } else {
      msg = err?.response?.data?.error || err?.message || 'Download fehlgeschlagen'
    }
    console.error('Download failed:', msg, err)
    alert(`Download fehlgeschlagen:\n${msg}`)
    emit('error', msg)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.download-btn {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  color: var(--color-text-primary);
  text-decoration: none;
  transition: all 150ms;
}
.download-btn:hover:not(:disabled) {
  background: var(--color-background);
  border-color: var(--color-primary);
}
.download-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.variant-primary {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}
.variant-primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
}
</style>
