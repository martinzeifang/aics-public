<template>
  <div class="ollama-models">
    <header class="page-header">
      <h1>🧠 KI-Modelle (Ollama)</h1>
      <div class="actions">
        <button class="btn-secondary" @click="loadModels" :disabled="loading">
          {{ loading ? 'Lädt…' : '↻ Aktualisieren' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="banner banner-error">
      ⚠ {{ error }}
    </div>

    <section class="card">
      <h2>Installierte Modelle ({{ installed.length }})</h2>
      <div v-if="installed.length === 0" class="muted">Keine Modelle installiert.</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Familie</th>
            <th>Größe</th>
            <th>Parameter</th>
            <th>Aktionen</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in installed" :key="m.name">
            <td><code>{{ m.name }}</code></td>
            <td>{{ m.family || '—' }}</td>
            <td>{{ formatBytes(m.size_bytes) }}</td>
            <td>{{ m.parameter_size || '—' }}</td>
            <td>
              <button class="btn-danger small" @click="del(m.name)" :disabled="busy === m.name">
                {{ busy === m.name ? 'Lösche…' : 'Löschen' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <h2>Empfehlungen</h2>
      <div class="recos">
        <div v-for="r in recommended" :key="r.name" class="reco">
          <div class="reco-head">
            <strong>{{ r.name }}</strong>
            <span class="size-pill">{{ r.size_label }}</span>
          </div>
          <p class="muted">{{ r.description }}</p>
          <button
            class="btn-primary small"
            :disabled="isInstalled(r.name) || pulling === r.name"
            @click="pull(r.name)"
          >
            {{ isInstalled(r.name) ? '✓ Installiert' : (pulling === r.name ? `Pull… ${pullPct}%` : '⬇ Pull') }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="pullLog.length" class="card">
      <h2>Pull-Log</h2>
      <pre class="log">{{ pullLog.join('\n') }}</pre>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

interface InstalledModel {
  name: string
  size_bytes: number
  modified_at?: string
  family: string
  parameter_size: string
}
interface RecommendedModel {
  name: string
  size_label: string
  description: string
}

const installed = ref<InstalledModel[]>([])
const recommended = ref<RecommendedModel[]>([])
const loading = ref(false)
const error = ref('')
const busy = ref('')
const pulling = ref('')
const pullPct = ref(0)
const pullLog = ref<string[]>([])

async function loadModels() {
  loading.value = true
  error.value = ''
  try {
    const r = await axios.get('/api/admin/ollama/models')
    installed.value = r.data?.installed || []
    recommended.value = r.data?.recommended || []
    if (r.data?.error) error.value = r.data.error
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Konnte Modellliste nicht laden.'
  } finally {
    loading.value = false
  }
}

function isInstalled(name: string) {
  return installed.value.some((m) => m.name === name || m.name === `${name}:latest`)
}

function formatBytes(n: number) {
  if (!n) return '—'
  const gb = n / 1024 / 1024 / 1024
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = n / 1024 / 1024
  return `${mb.toFixed(0)} MB`
}

async function del(name: string) {
  if (!confirm(`Modell "${name}" wirklich löschen?`)) return
  busy.value = name
  try {
    await axios.delete(`/api/admin/ollama/models/${encodeURIComponent(name)}`)
    await loadModels()
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen.'
  } finally {
    busy.value = ''
  }
}

function pull(name: string) {
  pulling.value = name
  pullPct.value = 0
  pullLog.value = []
  // SSE via fetch
  const url = '/api/admin/ollama/pull'
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${sessionStorage.getItem('auth_token') || ''}` },
    body: JSON.stringify({ model: name }),
  }).then(async (res) => {
    const reader = res.body!.getReader()
    const dec = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const events = buf.split('\n\n')
      buf = events.pop() || ''
      for (const ev of events) {
        const m = ev.match(/^event: (\w+)\ndata: (.*)/s)
        if (!m) continue
        const [, name2, payload] = m
        try {
          const data = JSON.parse(payload)
          if (name2 === 'progress') pullPct.value = data.percent ?? pullPct.value
          if (name2 === 'status') pullLog.value.push(data.message || '')
          if (name2 === 'done') {
            pullLog.value.push(data.ok ? '✓ done' : `✗ ${data.error}`)
            pulling.value = ''
            loadModels()
          }
        } catch {}
      }
    }
  }).catch((e) => {
    pullLog.value.push(`✗ ${e.message}`)
    pulling.value = ''
  })
}

onMounted(loadModels)
</script>

<style scoped>
.ollama-models { padding: 24px; max-width: 1100px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.card { background: var(--color-surface, #fff); padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); margin-bottom: 16px; }
.banner { padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; }
.banner-error { background: #ffebee; color: #c62828; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { padding: 8px 12px; border-bottom: 1px solid var(--color-border, #e0e0e0); text-align: left; }
.data-table th { font-weight: 600; color: var(--color-text-muted, #666); }
.muted { color: var(--color-text-muted, #666); }
.recos { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.reco { border: 1px solid var(--color-border, #e0e0e0); border-radius: 6px; padding: 12px; }
.reco-head { display: flex; justify-content: space-between; margin-bottom: 6px; }
.size-pill { padding: 2px 6px; background: #e3f2fd; color: #1565c0; border-radius: 4px; font-size: 11px; }
.btn-primary { background: var(--color-primary, #1565c0); color: #fff; border: 0; padding: 8px 12px; border-radius: 6px; cursor: pointer; }
.btn-secondary { background: var(--color-surface-alt, #f3f5f9); border: 1px solid var(--color-border, #d0d4dc); padding: 8px 12px; border-radius: 6px; cursor: pointer; }
.btn-danger { background: #c62828; color: #fff; border: 0; padding: 6px 10px; border-radius: 6px; cursor: pointer; }
.btn-primary:disabled, .btn-danger:disabled, .btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.small { font-size: 12px; }
.log { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; font-size: 12px; max-height: 240px; overflow: auto; }
</style>
