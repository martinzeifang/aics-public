<template>
  <div class="license-view">
    <h1>🔑 Lizenz-Verwaltung</h1>

    <div class="card">
      <h2>Status</h2>
      <div v-if="loading" class="muted">Lade …</div>
      <div v-else-if="status" class="status-grid">
        <div><strong>Zustand:</strong>
          <span :class="['state-pill', status.state]">{{ status.state }}</span>
        </div>
        <div v-if="status.license_key"><strong>Schlüssel:</strong> <code>{{ status.license_key }}</code></div>
        <div v-if="status.plan"><strong>Plan:</strong> {{ status.plan }}</div>
        <div v-if="status.customer"><strong>Kunde:</strong> {{ status.customer }}</div>
        <div v-if="status.modules && status.modules.length">
          <strong>Module:</strong>
          {{ status.modules.includes('*') ? 'alle' : status.modules.join(', ') }}
        </div>
        <div v-if="status.max_users"><strong>Named-User-Limit:</strong> {{ status.max_users }}</div>
        <div v-if="status.expires_at">
          <strong>Gültig bis:</strong>
          {{ new Date(status.expires_at * 1000).toLocaleString('de-DE') }}
        </div>
        <div v-if="status.over_limit" style="color:#c62828">
          ⚠ User-Limit überschritten
        </div>
        <div v-if="status.reason" class="muted"><strong>Hinweis:</strong> {{ status.reason }}</div>
      </div>
    </div>

    <div class="card">
      <h2>Lizenz-Server-Verbindung</h2>
      <div v-if="!editServer" class="server-summary">
        <div><strong>URL:</strong> <code>{{ serverCfg.server_url || '—' }}</code></div>
        <div><strong>TLS-Verify:</strong> {{ serverCfg.verify_tls ? 'aktiviert' : 'aus (Self-Signed OK)' }}</div>
        <div><strong>Timeout:</strong> {{ serverCfg.request_timeout || '—' }} s</div>
        <div v-if="serverCfg.has_file_override" class="hint">
          ✓ persistent in <code>data/license_server.json</code>
        </div>
        <div v-else class="hint">
          Default aus Code / ENV — noch keine eigene Konfiguration gespeichert.
        </div>
        <button class="btn-secondary" @click="startEditServer">✏ Bearbeiten</button>
      </div>
      <div v-else class="server-edit">
        <label>Lizenz-Server-URL
          <input v-model="serverDraft.server_url" placeholder="https://lic.example.de:8444" />
        </label>
        <label class="check">
          <input type="checkbox" v-model="serverDraft.verify_tls" />
          TLS-Zertifikat verifizieren (für Self-Signed: deaktiviert lassen)
        </label>
        <label>Request-Timeout (Sekunden)
          <input type="number" min="1" max="120" v-model.number="serverDraft.request_timeout" />
        </label>
        <div v-if="serverProbe" :class="['probe', serverProbe.reachable ? 'ok' : 'warn']">
          {{ serverProbe.reachable ? '✓ Server erreichbar' : `⚠ Probe fehlgeschlagen: ${serverProbe.probe_error}` }}
        </div>
        <div class="row">
          <button class="btn-primary" :disabled="busy === 'server-save'" @click="onSaveServer">
            {{ busy === 'server-save' ? '⏳' : '💾 Speichern' }}
          </button>
          <button class="btn-secondary" @click="editServer = false">Abbrechen</button>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Aktivierung</h2>
      <div class="row">
        <input v-model="activateKey" placeholder="License-Key (leer = Auto-Demo)" />
        <button class="btn-primary" @click="onActivate" :disabled="!!busy">
          {{ busy === 'activate' ? '⏳' : '🔓 Aktivieren' }}
        </button>
      </div>
      <p class="hint">Server-URL: <code>{{ serverCfg.server_url || '-' }}</code> — oben bearbeitbar</p>
      <div v-if="actError" class="error">{{ actError }}</div>
      <div v-if="status?.state === 'ok' || status?.state === 'demo'" class="row" style="gap:8px;">
        <button class="btn-secondary" @click="onRefresh" :disabled="!!busy">
          {{ busy === 'refresh' ? '⏳' : '🔄 Vom Server aktualisieren' }}
        </button>
        <button class="btn-secondary" @click="onDeactivate" :disabled="!!busy">
          {{ busy === 'deactivate' ? '⏳' : '🔒 Deaktivieren' }}
        </button>
      </div>
      <div v-if="refreshMsg" :class="['refresh-msg', refreshMsgKind]">{{ refreshMsg }}</div>
    </div>

    <div class="card">
      <h2>Offline-Aktivierung</h2>
      <p class="hint">
        Wenn der Server keinen Internet-Zugriff hat: Request-Datei generieren →
        per E-Mail an den Vertrieb senden → signierte <code>.aics-license</code>-
        Datei zurück bekommen und hier hochladen.
      </p>
      <div class="row">
        <input v-model="offlineKey" placeholder="License-Key für Request-Datei" />
        <button class="btn-secondary" @click="onDownloadRequest"
                :disabled="!offlineKey.trim() || busy === 'import'">
          {{ busy === 'import' ? '⏳ Generiere …' : '⬇ Request-Datei generieren' }}
        </button>
      </div>
      <div v-if="offlineMsg" :class="['refresh-msg', offlineMsgKind]">{{ offlineMsg }}</div>
      <div class="row" style="margin-top: 12px;">
        <input type="file" accept=".aics-license,.json" @change="onImportFile" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import apiClient from '../../api/client'

const loading = ref(true)
const status = ref<any>(null)
const busy = ref<'' | 'activate' | 'deactivate' | 'import' | 'server-save' | 'refresh'>('')
const refreshMsg = ref('')
const refreshMsgKind = ref<'ok' | 'warn'>('ok')
const offlineMsg = ref('')
const offlineMsgKind = ref<'ok' | 'warn'>('ok')
const activateKey = ref('')
const offlineKey = ref('')
const actError = ref('')

interface ServerCfg { server_url: string; verify_tls: boolean; request_timeout: number; has_file_override: boolean }
const serverCfg = ref<ServerCfg>({ server_url: '', verify_tls: false, request_timeout: 15, has_file_override: false })
const editServer = ref(false)
const serverDraft = ref<ServerCfg>({ server_url: '', verify_tls: false, request_timeout: 15, has_file_override: false })
const serverProbe = ref<{ reachable: boolean; probe_error: string } | null>(null)

async function load() {
  loading.value = true
  actError.value = ''
  try {
    const [s, sc] = await Promise.all([
      apiClient.get('/license/status').catch((e) => {
        actError.value = 'Lizenz-Status konnte nicht geladen werden: '
          + (e?.response?.data?.error || e?.message || e)
        return { data: null }
      }),
      apiClient.get('/license/server-config').catch(() => ({ data: null })),
    ])
    if (s.data) status.value = s.data
    if (sc.data) serverCfg.value = sc.data
  } finally {
    loading.value = false
  }
}

function startEditServer() {
  serverDraft.value = { ...serverCfg.value }
  serverProbe.value = null
  editServer.value = true
}

async function onSaveServer() {
  busy.value = 'server-save'
  serverProbe.value = null
  try {
    const r = await apiClient.put('/license/server-config', serverDraft.value)
    serverCfg.value = {
      server_url: r.data.server_url,
      verify_tls: r.data.verify_tls,
      request_timeout: serverDraft.value.request_timeout,
      has_file_override: true,
    }
    serverProbe.value = { reachable: r.data.reachable, probe_error: r.data.probe_error || '' }
    if (r.data.reachable) {
      editServer.value = false
    }
  } catch (e: any) {
    serverProbe.value = { reachable: false, probe_error: e?.response?.data?.error || String(e) }
  } finally {
    busy.value = ''
  }
}

async function onRefresh() {
  busy.value = 'refresh'
  actError.value = ''
  refreshMsg.value = ''
  try {
    const r = await apiClient.post('/license/refresh', {}, { timeout: 30000 })
    status.value = r.data.state
    const changes = r.data.changes || {}
    const keys = Object.keys(changes)
    if (keys.length === 0) {
      refreshMsgKind.value = 'ok'
      refreshMsg.value = '✓ Aktualisiert — keine Änderungen seit letztem Heartbeat.'
    } else {
      refreshMsgKind.value = 'ok'
      const parts = keys.map(k => `${k}: ${JSON.stringify(changes[k].from)} → ${JSON.stringify(changes[k].to)}`)
      refreshMsg.value = '✓ Aktualisiert — Änderungen: ' + parts.join(' · ')
    }
  } catch (e: any) {
    refreshMsgKind.value = 'warn'
    refreshMsg.value = '⚠ ' + (e?.response?.data?.message || e?.response?.data?.error || e?.message || 'Refresh fehlgeschlagen')
  } finally {
    busy.value = ''
  }
}

async function onActivate() {
  busy.value = 'activate'
  actError.value = ''
  try {
    const r = await apiClient.post('/license/activate',
      { license_key: activateKey.value },
      { timeout: 30000 })
    status.value = r.data
    activateKey.value = ''
  } catch (e: any) {
    actError.value =
      e?.response?.data?.message
      || e?.response?.data?.error
      || e?.message
      || 'Aktivierung fehlgeschlagen (Timeout?). Prüfe Server-URL/Erreichbarkeit oben.'
  } finally {
    busy.value = ''
  }
}

async function onDeactivate() {
  if (!confirm('Lizenz wirklich deaktivieren? Aktivierung wird am Server zurückgegeben.')) return
  busy.value = 'deactivate'
  actError.value = ''
  try {
    const r = await apiClient.post('/license/deactivate', {}, { timeout: 30000 })
    status.value = r.data
  } catch (e: any) {
    actError.value =
      e?.response?.data?.message
      || e?.response?.data?.error
      || e?.message
      || 'Deaktivierung fehlgeschlagen'
  } finally {
    busy.value = ''
  }
}

async function onDownloadRequest() {
  console.info('[Offline-Request] Klick, offlineKey=', offlineKey.value)
  offlineMsg.value = ''
  offlineMsgKind.value = 'ok'
  if (!offlineKey.value || !offlineKey.value.trim()) {
    offlineMsgKind.value = 'warn'
    offlineMsg.value = '⚠ Bitte zuerst einen License-Key eingeben.'
    return
  }
  busy.value = 'import'
  try {
    console.info('[Offline-Request] POST /api/license/offline-request')
    const r = await apiClient.post('/license/offline-request',
      { license_key: offlineKey.value.trim() },
      { responseType: 'blob', timeout: 30000 })
    console.info('[Offline-Request] Response OK', r.status, 'bytes=', (r.data as Blob)?.size)

    const cd = r.headers['content-disposition'] || ''
    const m = /filename="?([^"]+)"?/.exec(cd)
    const filename = m ? m[1] : `aics-request-${Date.now()}.json`
    const url = URL.createObjectURL(r.data as Blob)
    const a = document.createElement('a')
    a.style.display = 'none'
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    setTimeout(() => {
      try { document.body.removeChild(a) } catch {}
      URL.revokeObjectURL(url)
    }, 1500)
    offlineMsgKind.value = 'ok'
    offlineMsg.value = `✓ Datei "${filename}" heruntergeladen (${(r.data as Blob).size} Bytes). Per E-Mail an den Vertrieb senden.`
  } catch (e: any) {
    console.error('[Offline-Request] Fehler', e)
    let msg = e?.message || 'Request-Generierung fehlgeschlagen'
    const blob = e?.response?.data
    if (blob instanceof Blob) {
      try {
        const text = await blob.text()
        try {
          const j = JSON.parse(text)
          msg = j?.error || j?.message || text
        } catch {
          msg = text || msg
        }
      } catch { /* keep msg */ }
    } else if (e?.response?.status) {
      msg = `HTTP ${e.response.status} ${e.response.statusText || ''}`
    }
    offlineMsgKind.value = 'warn'
    offlineMsg.value = '⚠ ' + msg
    actError.value = msg  // auch oben sichtbar
  } finally {
    busy.value = ''
  }
}

async function onImportFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  busy.value = 'import'
  actError.value = ''
  const fd = new FormData()
  fd.append('file', file)
  try {
    const r = await apiClient.post('/license/import', fd)
    status.value = r.data
  } catch (e: any) {
    actError.value = e?.response?.data?.message || e?.response?.data?.error || 'Import fehlgeschlagen'
  } finally {
    busy.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.license-view { padding: 24px; max-width: 900px; }
.card { background: white; border: 1px solid #e0e0e0; border-radius: 10px; padding: 20px; margin-top: 16px; }
.card h2 { margin: 0 0 12px; font-size: 17px; }
.server-summary { display: grid; gap: 6px; margin-bottom: 8px; }
.server-edit { display: grid; gap: 10px; max-width: 600px; }
.server-edit label { display: block; }
.server-edit label.check { display: flex; align-items: center; gap: 8px; }
.server-edit input[type=text], .server-edit input:not([type]) { display: block; width: 100%; padding: 6px 8px; box-sizing: border-box; }
.server-edit input[type=number] { width: 120px; padding: 6px 8px; }
.probe.ok { color: #2e7d32; }
.probe.warn { color: #ef6c00; }
.status-grid { display: grid; gap: 8px; font-size: 14px; }
.state-pill { padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-left: 6px; }
.state-pill.ok { background: #e8f5e9; color: #2e7d32; }
.state-pill.demo { background: #e3f2fd; color: #1565c0; }
.state-pill.read-only { background: #ffebee; color: #c62828; }
.state-pill.no-license { background: #f5f5f5; color: #757575; }
.row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.row input[type="text"], .row input:not([type]) { flex: 1; padding: 8px 10px; border: 1px solid #e0e0e0; border-radius: 6px; }
.muted { color: #757575; font-size: 13px; }
.hint { font-size: 12px; color: #666; margin-top: 4px; }
.error { color: #c62828; background: #ffebee; padding: 10px; border-radius: 6px; margin-top: 8px; }
.refresh-msg { padding: 8px 12px; border-radius: 6px; margin-top: 8px; font-size: 13px; }
.refresh-msg.ok { color: #2e7d32; background: #e8f5e9; }
.refresh-msg.warn { color: #ef6c00; background: #fff3e0; }
.btn-primary { padding: 8px 14px; background: #1565c0; color: white; border: 0; border-radius: 6px; cursor: pointer; }
.btn-secondary { padding: 8px 14px; background: #f5f5f5; border: 1px solid #e0e0e0; border-radius: 6px; cursor: pointer; }
</style>
