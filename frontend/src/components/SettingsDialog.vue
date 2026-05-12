<template>
  <div v-if="open" :class="[embedded ? 'settings-embedded' : 'modal-overlay']" @click.self="!embedded && onClose()">
    <div :class="['modal-content', 'settings-modal', { embedded }]">
      <div v-if="!embedded" class="modal-header">
        <h2>Einstellungen</h2>
        <button class="btn-close" @click="onClose">✕</button>
      </div>

      <div v-if="adminStore.loading && !adminStore.settings" class="loading">
        Einstellungen werden geladen…
      </div>

      <div v-else-if="adminStore.error" class="alert alert-error">
        {{ adminStore.error }}
      </div>

      <div v-else-if="form" class="modal-body">
        <!-- Tabs -->
        <div class="tabs">
          <button
            v-for="t in tabs"
            :key="t.id"
            :class="['tab-btn', { active: activeTab === t.id }]"
            @click="activeTab = t.id"
          >
            {{ t.label }}
          </button>
        </div>

        <!-- Tab: KI -->
        <div v-if="activeTab === 'ai'" class="tab-content">
          <div class="form-group">
            <label>KI-Provider</label>
            <div class="radio-group">
              <label>
                <input type="radio" value="on_prem" v-model="form.ai.provider" />
                On-Prem (Ollama, lokal)
              </label>
              <label>
                <input type="radio" value="cloud" v-model="form.ai.provider" />
                Cloud (OpenAI / Anthropic)
              </label>
            </div>
          </div>

          <fieldset v-if="form.ai.provider === 'on_prem'">
            <legend>On-Prem (Ollama)</legend>
            <div class="form-group">
              <label>Base-URL</label>
              <input v-model="form.ai.on_prem.base_url" placeholder="http://127.0.0.1:11434" />
              <p class="hint">
                <strong>Lokal (Desktop/Dev):</strong> <code>http://127.0.0.1:11434</code><br />
                <strong>Docker:</strong> <code>http://ollama:11434</code> ← Service-Name im Compose-Netz!
                Niemals <code>localhost</code> oder <code>127.0.0.1</code> aus dem Container,
                das zeigt auf den Container selbst.
              </p>
            </div>
            <div class="form-group">
              <label>Model</label>
              <select v-model="form.ai.on_prem.model" style="width: 100%;">
                <option value="">— manuell eintragen unten —</option>
                <optgroup v-if="ollamaModels.installed.length" label="Installiert">
                  <option v-for="m in ollamaModels.installed" :key="m.name" :value="m.name">
                    {{ m.name }} ({{ formatGB(m.size_bytes) }})
                  </option>
                </optgroup>
                <optgroup label="Empfehlungen (noch nicht installiert)">
                  <option
                    v-for="r in ollamaModels.recommendations.filter(r => !ollamaModels.installed.find(m => m.name.startsWith(r.tag.split(':')[0])))"
                    :key="r.tag"
                    :value="r.tag">
                    {{ r.tag }} (~{{ r.size_gb }} GB) — {{ r.desc }}
                  </option>
                </optgroup>
              </select>
              <button type="button" class="btn btn-secondary" style="margin-top: 8px;"
                      @click="loadOllamaModels" :disabled="ollamaModels.loading">
                {{ ollamaModels.loading ? '⏳ Lade…' : '🔄 Modelle vom Server neu laden' }}
              </button>
              <input v-model="form.ai.on_prem.model" placeholder="oder manuell: llama3.1:8b"
                     style="margin-top: 6px;" />
              <p v-if="ollamaModels.error" class="hint" style="color: #c62828">
                Modell-Liste konnte nicht geladen werden: {{ ollamaModels.error }}
              </p>
              <p v-else-if="ollamaModels.installed.length === 0" class="hint" style="color: #f57c00">
                ⚠ Keine Modelle installiert. Wähle eine Empfehlung und klicke unten „Modell pullen".
              </p>
              <p v-else class="hint">
                {{ ollamaModels.installed.length }} Modelle installiert.
                Eines auswählen oder manuell eingeben.
              </p>
            </div>
            <div class="form-group">
              <label>Timeout (Sekunden)</label>
              <input v-model.number="form.ai.on_prem.timeout_s" type="number" min="5" max="600" />
            </div>

            <!-- Ollama-Diagnose-Suite -->
            <div class="ollama-diagnose">
              <div style="display:flex; gap:8px; align-items:center; margin-top:14px; flex-wrap: wrap;">
                <button type="button" class="btn btn-primary" @click="onOllamaDiagnose"
                        :disabled="ollamaDiag.running">
                  {{ ollamaDiag.running ? '⏳ Teste …' : '🔬 Diagnose ausführen' }}
                </button>
                <button type="button" class="btn btn-secondary" @click="onOllamaPullDefault"
                        :disabled="ollamaPull.running || !form.ai.on_prem.model">
                  {{ ollamaPull.running ? '⏳ Lade …' : `⬇ ${form.ai.on_prem.model || 'Modell'} pullen` }}
                </button>
                <button type="button" class="btn btn-secondary" @click="onOllamaEchoTest"
                        :disabled="ollamaEcho.running || !form.ai.on_prem.model">
                  {{ ollamaEcho.running ? '⏳ Streamt …' : '💬 Echo-Test (Hello World)' }}
                </button>
              </div>

              <!-- Echo-Test Live-Anzeige -->
              <div v-if="ollamaEcho.shown" class="ollama-echo">
                <div class="ollama-echo-head">
                  <span class="spinner-tiny" v-if="ollamaEcho.running"></span>
                  <strong>{{ ollamaEcho.status }}</strong>
                  <span v-if="ollamaEcho.ttftMs" class="muted" style="margin-left: 8px;">
                    · 1. Token nach {{ ollamaEcho.ttftMs }} ms
                  </span>
                  <span v-if="ollamaEcho.tokensPerSec" class="muted">
                    · {{ ollamaEcho.tokensPerSec }} Token/s
                  </span>
                  <span v-if="ollamaEcho.totalMs" class="muted">
                    · gesamt {{ ollamaEcho.totalMs }} ms
                  </span>
                </div>
                <div v-if="ollamaEcho.chunks" class="ollama-echo-response">
                  <div style="font-size:11px; color:#666; margin-bottom:4px;">
                    Antwort vom Modell:
                  </div>
                  <pre>{{ ollamaEcho.chunks }}</pre>
                </div>
                <div v-if="ollamaEcho.error" class="alert alert-error" style="margin-top: 6px;">
                  ⚠ {{ ollamaEcho.error }}
                </div>
              </div>
              <div v-if="ollamaPull.result" class="ollama-pull-status">
                <div v-if="ollamaPull.result.running" class="muted">
                  <span class="spinner-tiny"></span>
                  {{ ollamaPull.result.status || 'Lade …' }}
                  <span v-if="ollamaPull.result.percent !== undefined">
                    · {{ ollamaPull.result.percent }} %
                    ({{ Math.round((ollamaPull.result.completed || 0) / 1024 / 1024) }}
                    / {{ Math.round((ollamaPull.result.total || 0) / 1024 / 1024) }} MB)
                  </span>
                </div>
                <div v-if="ollamaPull.result.percent !== undefined && ollamaPull.result.running"
                     class="pull-bar-wrap">
                  <div class="pull-bar" :style="{ width: (ollamaPull.result.percent || 0) + '%' }"></div>
                </div>
                <div v-if="ollamaPull.result.ok === true" style="color:#2e7d32">
                  ✓ Pull abgeschlossen für <code>{{ ollamaPull.result.model }}</code>
                </div>
                <div v-if="ollamaPull.result.ok === false" style="color:#c62828">
                  ✗ {{ ollamaPull.result.error }}
                </div>
              </div>

              <div v-if="ollamaDiag.result" class="ollama-checks">
                <div class="ollama-config-line">
                  <strong>{{ ollamaDiag.result.config.base_url }}</strong>
                  · Modell <code>{{ ollamaDiag.result.config.model || '(keins)' }}</code>
                  · Quelle: <em>{{ ollamaDiag.result.config.source }}</em>
                </div>
                <div v-for="(c, i) in ollamaDiag.result.checks" :key="i"
                     class="ollama-check" :class="{ ok: c.ok, fail: !c.ok }">
                  <div class="ollama-check-head">
                    <span class="icon">{{ c.ok ? '✓' : '✗' }}</span>
                    <strong>{{ c.name }}</strong>
                  </div>
                  <div class="ollama-check-detail">{{ c.detail }}</div>
                  <div v-if="c.meta?.install_hint" class="ollama-check-hint">
                    💡 Tipp: <code>{{ c.meta.install_hint }}</code>
                  </div>
                  <div v-if="(c.meta?.installed?.length || c.meta?.models?.length)" class="ollama-check-hint">
                    <details>
                      <summary>Installierte Modelle ({{ (c.meta.installed || c.meta.models).length }})</summary>
                      <ul style="margin: 4px 0 0 16px;">
                        <li v-for="m in (c.meta.installed || c.meta.models)" :key="m">
                          <code>{{ m }}</code>
                        </li>
                      </ul>
                    </details>
                  </div>
                  <div v-if="c.meta?.tokens_per_second" class="ollama-check-hint">
                    Performance: <strong>{{ c.meta.tokens_per_second }}</strong> Token/s ·
                    <strong>{{ c.meta.eval_count }}</strong> Token Output
                  </div>
                </div>
              </div>
            </div>
          </fieldset>

          <fieldset v-if="form.ai.provider === 'cloud'">
            <legend>Cloud</legend>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="form.ai.cloud.allow_data_egress" />
                Datenausgang erlauben (Pflicht für Cloud)
              </label>
              <p class="hint">Daten verlassen den lokalen Rechner. Nur aktivieren, wenn rechtlich freigegeben.</p>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="form.ai.cloud.redact" />
                Sensitive Felder vor Versand redigieren
              </label>
            </div>
            <div class="form-group">
              <label>Base-URL</label>
              <input v-model="form.ai.cloud.base_url" />
            </div>
            <div class="form-group">
              <label>Model</label>
              <input v-model="form.ai.cloud.model" />
            </div>
            <div class="form-group">
              <label>API-Key Env-Variable</label>
              <input v-model="form.ai.cloud.api_key_env" />
            </div>
          </fieldset>
        </div>

        <!-- Tab: Module -->
        <div v-if="activeTab === 'modules'" class="tab-content">
          <p class="hint">Reihenfolge und Aktivierung der Module in der Web-Oberfläche.</p>
          <div v-for="m in webModules" :key="m.id" class="module-row">
            <input
              type="checkbox"
              :id="`mod-${m.id}`"
              :checked="!isDisabled(m.id)"
              @change="toggleModule(m.id)"
            />
            <label :for="`mod-${m.id}`">{{ m.label }}</label>
            <span class="muted">{{ m.tooltip }}</span>
          </div>
        </div>

        <!-- Tab: Backup -->
        <div v-if="activeTab === 'backup'" class="tab-content">
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="form.backup.backup_on_exit" />
              Automatisches Backup beim Beenden der Suite
            </label>
          </div>
          <div class="form-group">
            <label>Anzahl behaltener Backups (Retention)</label>
            <input v-model.number="form.backup.backup_retention_count" type="number" min="1" max="50" />
          </div>
          <div class="form-group">
            <p class="hint">
              Backups werden gespeichert in <code>out/backup/</code> als ZIP-Dateien.
              Die Verwaltung erfolgt im Backup-Tab unter <em>Administration</em>.
            </p>
          </div>
        </div>

        <!-- Tab: GitHub-Integration -->
        <div v-if="activeTab === 'github'" class="tab-content">
          <h3>🐙 GitHub-Integration</h3>
          <p class="hint">
            Wird benötigt für: Issue-Erstellung aus den Modulen, Issue-Inhalt
            importieren (Risikobewertung), CRA Full-Repo-Scan.
            Token-Scope: <code>repo</code> (lesen + Issues erstellen).
          </p>

          <div class="form-group">
            <label>Personal Access Token</label>
            <div v-if="gh.token_set" class="gh-token-status">
              <span class="gh-token-badge">✓ aktiv</span>
              <code>{{ gh.token_masked }}</code>
              <span class="hint-inline">(Quelle: {{ gh.source === 'env' ? 'Server-ENV' : 'Konfiguration' }})</span>
            </div>
            <div v-else class="gh-token-status warn">
              <span class="gh-token-badge warn">✗ nicht gesetzt</span>
              <span class="hint-inline">— GitHub-Funktionen sind deaktiviert</span>
            </div>
            <div class="row" style="display:flex; gap:8px; margin-top: 8px;">
              <input
                v-model="gh.token"
                :placeholder="gh.token_set ? 'Neuen Token eingeben um zu ändern' : 'ghp_… (Token einfügen)'"
                :type="ghShowToken ? 'text' : 'password'"
                autocomplete="new-password"
                style="flex: 1;"
              />
              <button type="button" class="btn btn-secondary" @click="ghShowToken = !ghShowToken">
                {{ ghShowToken ? '🙈' : '👁' }}
              </button>
            </div>
            <p class="hint">
              <a href="https://github.com/settings/tokens?type=beta" target="_blank" rel="noopener">
                Token auf github.com erstellen ↗
              </a> · Scope „repo" reicht für Issues + Repo-Scan.
              Aus Sicherheitsgründen wird das Feld nach dem Speichern geleert — der Token bleibt auf dem Server.
            </p>
            <p v-if="gh.source === 'env'" class="hint" style="color:#f57c00">
              ⚠ Aktiver Token kommt aus der Server-ENV. Wenn du im UI einen Token speicherst, gewinnt dieser ab dann.
            </p>
          </div>

          <div class="form-group">
            <label>Benutzername (optional)</label>
            <input v-model="gh.username" placeholder="dein-github-username" />
          </div>

          <div class="form-group">
            <label>Standard-Repository (optional)</label>
            <input v-model="gh.default_repo" placeholder="owner/repo" />
            <p class="hint">
              Wird in Modulen als Vorbelegung verwendet, wenn ein Issue
              angelegt wird.
            </p>
          </div>

          <div class="row" style="display:flex; gap:10px; margin-top: 12px;">
            <button type="button" class="btn btn-secondary" @click="onGithubSave" :disabled="ghSaving">
              {{ ghSaving ? '…' : '💾 Speichern' }}
            </button>
            <button type="button" class="btn btn-primary" @click="onGithubTest" :disabled="ghTesting">
              {{ ghTesting ? '⏳ Teste…' : '🔌 Verbindung testen' }}
            </button>
          </div>

          <div v-if="ghTestResult" class="github-test-result"
               :class="{ ok: ghTestResult.ok, fail: !ghTestResult.ok }"
               style="margin-top: 16px; padding: 12px; border-radius: 6px;">
            <div v-if="ghTestResult.ok">
              <strong>✓ Verbunden als {{ ghTestResult.login }}</strong>
              <span v-if="ghTestResult.name"> ({{ ghTestResult.name }})</span>
              <div v-if="ghTestResult.scopes?.length" style="margin-top: 6px;">
                Scopes: <code>{{ ghTestResult.scopes.join(', ') }}</code>
              </div>
              <div v-if="ghTestResult.rate_limit_remaining" class="hint">
                Rate-Limit verbleibend: {{ ghTestResult.rate_limit_remaining }}
              </div>
              <div v-if="ghTestResult.default_repo_check" style="margin-top: 8px;">
                <strong>Default-Repo:</strong>
                <span v-if="ghTestResult.default_repo_check.exists">
                  ✓ <code>{{ ghTestResult.default_repo_check.repo }}</code> erreichbar
                </span>
                <span v-else style="color: #c62828">
                  ✗ <code>{{ ghTestResult.default_repo_check.repo }}</code> nicht erreichbar
                </span>
              </div>
            </div>
            <div v-else>
              <strong>✗ Verbindung fehlgeschlagen</strong>
              <div>{{ ghTestResult.error }}</div>
              <div v-if="ghTestResult.hint" class="hint">{{ ghTestResult.hint }}</div>
            </div>
          </div>
        </div>

        <!-- Tab: Aussehen -->
        <div v-if="activeTab === 'appearance'" class="tab-content">
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="form.appearance.dark_mode" />
              Dark Mode (zukünftig)
            </label>
            <p class="hint">Hinweis: Dark-Mode ist für eine spätere Phase geplant.</p>
          </div>
        </div>
      </div>

      <div :class="['modal-footer', { 'sticky-footer': embedded }]">
        <button v-if="!embedded" class="btn btn-secondary" @click="onClose">Abbrechen</button>
        <button class="btn btn-primary" @click="onSave" :disabled="adminStore.loading">
          {{ adminStore.loading ? 'Speichert…' : 'Speichern' }}
        </button>
      </div>

      <div v-if="successMessage" class="success-banner">{{ successMessage }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAdminStore } from '../stores/admin'
import apiClient from '../api/client'

const props = defineProps<{ open: boolean; embedded?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const adminStore = useAdminStore()
const activeTab = ref<'ai' | 'modules' | 'backup' | 'appearance' | 'github'>('ai')
const form = ref<any>(null)
const successMessage = ref('')

const tabs = [
  { id: 'ai' as const, label: 'KI-Provider' },
  { id: 'github' as const, label: 'GitHub' },
  { id: 'modules' as const, label: 'Module' },
  { id: 'backup' as const, label: 'Backup' },
  { id: 'appearance' as const, label: 'Aussehen' },
]

// GitHub-Integration State
const gh = ref({
  token: '',
  token_set: false,
  token_masked: '',
  username: '',
  default_repo: '',
  source: '',
})
const ghTesting = ref(false)
const ghTestResult = ref<any>(null)
const ghSaving = ref(false)

// Ollama-Diagnose
const ollamaDiag = ref<{ running: boolean; result: any | null }>({ running: false, result: null })
const ollamaPull = ref<{ running: boolean; result: any | null }>({ running: false, result: null })
const ollamaModels = ref<{
  loading: boolean; installed: any[]; recommendations: any[]; error: string;
}>({ loading: false, installed: [], recommendations: [], error: '' })

const ollamaEcho = ref<{
  shown: boolean; running: boolean; status: string; chunks: string;
  ttftMs: number; tokensPerSec: number; totalMs: number; error: string;
}>({
  shown: false, running: false, status: '', chunks: '',
  ttftMs: 0, tokensPerSec: 0, totalMs: 0, error: '',
})

async function onOllamaEchoTest() {
  const baseUrl = form.value?.ai?.on_prem?.base_url || ''
  const model = form.value?.ai?.on_prem?.model || ''
  console.info('[Ollama-Echo] Start', { baseUrl, model })
  if (!model) {
    ollamaEcho.value = {
      shown: true, running: false, status: '',
      chunks: '', ttftMs: 0, tokensPerSec: 0, totalMs: 0,
      error: 'Kein Modell konfiguriert — wähle oben ein Modell aus der Liste.',
    }
    return
  }
  ollamaEcho.value = {
    shown: true, running: true, status: 'Starte …', chunks: '',
    ttftMs: 0, tokensPerSec: 0, totalMs: 0, error: '',
  }
  const token = sessionStorage.getItem('auth_token') || ''
  if (!token) {
    ollamaEcho.value.error = 'Kein Auth-Token im sessionStorage — bitte neu einloggen.'
    ollamaEcho.value.running = false
    return
  }
  try {
    console.info('[Ollama-Echo] POST /api/admin/ollama/echo-test')
    const resp = await fetch('/api/admin/ollama/echo-test', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({ base_url: baseUrl, model }),
    })
    console.info('[Ollama-Echo] Response', resp.status, 'ok=', resp.ok, 'body=', !!resp.body)
    if (!resp.ok || !resp.body) {
      let detail = ''
      try { detail = (await resp.text()).slice(0, 300) } catch {}
      ollamaEcho.value.error = `HTTP ${resp.status} ${resp.statusText}${detail ? ' — ' + detail : ''}`
      ollamaEcho.value.running = false
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const raw = buf.slice(0, idx); buf = buf.slice(idx + 2)
        let ev = '', dataStr = ''
        for (const ln of raw.split('\n')) {
          if (ln.startsWith('event: ')) ev = ln.slice(7)
          else if (ln.startsWith('data: ')) dataStr += ln.slice(6)
        }
        if (!ev) continue
        let d: any = {}
        try { d = JSON.parse(dataStr) } catch { d = {} }

        if (ev === 'status') {
          ollamaEcho.value.status = d.message || ''
        } else if (ev === 'first-token') {
          ollamaEcho.value.ttftMs = d.ttft_ms || 0
          ollamaEcho.value.status = `Erstes Token nach ${d.ttft_ms} ms — empfange Antwort …`
        } else if (ev === 'chunk') {
          ollamaEcho.value.chunks += d.text || ''
        } else if (ev === 'done') {
          ollamaEcho.value.running = false
          if (d.ok) {
            ollamaEcho.value.status = '✓ Echo-Test erfolgreich'
            ollamaEcho.value.tokensPerSec = d.tokens_per_second || 0
            ollamaEcho.value.totalMs = d.total_duration_ms || 0
          } else {
            ollamaEcho.value.status = '✗ Fehler'
            ollamaEcho.value.error = d.error || 'Unbekannter Fehler'
          }
        }
      }
    }
  } catch (e: any) {
    ollamaEcho.value.error = e?.message || 'Stream-Fehler'
    ollamaEcho.value.running = false
  }
}

function formatGB(bytes: number): string {
  if (!bytes) return ''
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

async function loadOllamaModels() {
  ollamaModels.value.loading = true
  ollamaModels.value.error = ''
  try {
    const params = new URLSearchParams()
    if (form.value?.ai?.on_prem?.base_url) params.set('base_url', form.value.ai.on_prem.base_url)
    const r = await apiClient.get(`/admin/ollama/models?${params}`, { timeout: 10000 })
    ollamaModels.value.installed = r.data.installed || []
    ollamaModels.value.recommendations = r.data.recommendations || []
    ollamaModels.value.error = r.data.error || ''
  } catch (e: any) {
    ollamaModels.value.error = e?.response?.data?.error || e?.message || 'Modell-Liste konnte nicht geladen werden'
  } finally {
    ollamaModels.value.loading = false
  }
}

async function onOllamaDiagnose() {
  ollamaDiag.value = { running: true, result: null }
  try {
    const params = new URLSearchParams()
    if (form.value?.ai?.on_prem?.base_url) params.set('base_url', form.value.ai.on_prem.base_url)
    if (form.value?.ai?.on_prem?.model) params.set('model', form.value.ai.on_prem.model)
    if (form.value?.ai?.on_prem?.timeout_s) params.set('gen_timeout', String(form.value.ai.on_prem.timeout_s))
    const r = await apiClient.get(`/admin/ollama/diagnose?${params}`, { timeout: 180_000 })
    ollamaDiag.value.result = r.data
  } catch (e: any) {
    ollamaDiag.value.result = {
      config: { base_url: form.value?.ai?.on_prem?.base_url, model: form.value?.ai?.on_prem?.model, source: 'request', override: true },
      checks: [{
        name: 'Diagnose-Aufruf',
        ok: false,
        detail: e?.message || 'Fehler beim Aufruf',
        meta: { http_status: e?.response?.status },
      }],
    }
  } finally {
    ollamaDiag.value.running = false
  }
}

async function onOllamaPullDefault() {
  const model = form.value?.ai?.on_prem?.model
  if (!model) return
  ollamaPull.value = { running: true, result: { status: 'Starte …' } }

  // Streaming-fetch (SSE) — nginx-Timeout & large-model-pull-friendly
  const token = sessionStorage.getItem('auth_token') || ''
  try {
    const resp = await fetch('/api/admin/ollama/pull', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({ model }),
    })
    if (!resp.ok || !resp.body) {
      ollamaPull.value.result = { ok: false, error: `HTTP ${resp.status}` }
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const raw = buf.slice(0, idx); buf = buf.slice(idx + 2)
        let ev = '', dataStr = ''
        for (const ln of raw.split('\n')) {
          if (ln.startsWith('event: ')) ev = ln.slice(7)
          else if (ln.startsWith('data: ')) dataStr += ln.slice(6)
        }
        if (!ev) continue
        let d: any = {}
        try { d = JSON.parse(dataStr) } catch { d = { _raw: dataStr } }

        if (ev === 'status') {
          ollamaPull.value.result = { running: true, status: d.message }
        } else if (ev === 'progress') {
          ollamaPull.value.result = {
            running: true,
            status: d.status,
            percent: d.percent,
            completed: d.completed,
            total: d.total,
          }
        } else if (ev === 'done') {
          ollamaPull.value.result = d
          if (d.ok) await loadOllamaModels()
        }
      }
    }
  } catch (e: any) {
    ollamaPull.value.result = { ok: false, error: e?.message || 'Pull fehlgeschlagen' }
  } finally {
    ollamaPull.value.running = false
  }
}

const webModules = [
  { id: 'kunden', label: 'Kunden', tooltip: 'Kundenverwaltung' },
  { id: 'risikobewertung', label: 'Risikobewertung', tooltip: 'Multi-Framework' },
  { id: 'cra', label: 'CRA', tooltip: 'Cyber Resilience Act' },
  { id: 'nis2', label: 'NIS2', tooltip: 'NIS2-Richtlinie' },
  { id: 'dora', label: 'DORA', tooltip: 'Digital Operational Resilience Act' },
  { id: 'aiact', label: 'AI Act', tooltip: 'EU AI Act' },
  { id: 'dsgvo', label: 'DSGVO', tooltip: 'GDPR / DSGVO' },
  { id: 'gutachten', label: 'Gutachten', tooltip: 'Expert Opinions' },
]

const isDisabled = (id: string): boolean => {
  return form.value?.modules?.disabled?.includes(id) ?? false
}

const toggleModule = (id: string) => {
  if (!form.value.modules) form.value.modules = { order: [], disabled: [] }
  if (!form.value.modules.disabled) form.value.modules.disabled = []
  const idx = form.value.modules.disabled.indexOf(id)
  if (idx >= 0) {
    form.value.modules.disabled.splice(idx, 1)
  } else {
    form.value.modules.disabled.push(id)
  }
}

watch(() => props.open, async (open) => {
  if (open) {
    successMessage.value = ''
    if (!adminStore.settings) await adminStore.fetchSettings()
    form.value = JSON.parse(JSON.stringify(adminStore.settings || {}))
    if (!form.value.ai) form.value.ai = { provider: 'on_prem', on_prem: {}, cloud: {} }
    if (!form.value.ai.on_prem) form.value.ai.on_prem = { base_url: '', model: '', timeout_s: 60 }
    if (!form.value.ai.cloud) form.value.ai.cloud = { allow_data_egress: false, redact: true, base_url: '', model: '', api_key_env: '' }
    if (!form.value.modules) form.value.modules = { order: [], disabled: [] }
    if (!form.value.backup) form.value.backup = { backup_on_exit: false, backup_retention_count: 5 }
    if (!form.value.appearance) form.value.appearance = { dark_mode: false }
    await loadGithub()
    // Ollama-Modelle laden — best-effort, blockiert das Modal nicht
    loadOllamaModels().catch(() => {})
  }
}, { immediate: true })

const ghShowToken = ref(false)

async function loadGithub() {
  try {
    const r = await apiClient.get('/admin/github')
    gh.value = { ...gh.value, ...r.data, token: '' }
    ghTestResult.value = null
  } catch { /* ignore */ }
}

async function onGithubSave() {
  // Trim + Whitespace entfernen — Copy/Paste-Reste oder Browser-Autofill abfangen
  const tokenTrimmed = (gh.value.token || '').trim()
  const sendingToken = tokenTrimmed.length > 0

  if (sendingToken && tokenTrimmed.length < 20) {
    successMessage.value = `⚠ Token ist nur ${tokenTrimmed.length} Zeichen — das ist kein gültiger GitHub-Token. `
      + 'Falls Autofill: Feld leeren, Token manuell aus github.com einfügen.'
    return
  }
  if (sendingToken && /\s/.test(tokenTrimmed)) {
    successMessage.value = '⚠ Token enthält Whitespace — bitte sauber einfügen.'
    return
  }

  ghSaving.value = true
  try {
    const body: any = { username: gh.value.username, default_repo: gh.value.default_repo }
    if (sendingToken) body.token = tokenTrimmed
    const r = await apiClient.put('/admin/github', body)
    const ok = r.data?.token_set ?? gh.value.token_set
    const serverTokenLen = r.data?.token_len
    console.info('[GH-Save] sent token_len=%d server_token_len=%s', tokenTrimmed.length, serverTokenLen)

    if (sendingToken && ok) {
      successMessage.value = `✓ GitHub-Token gespeichert (${tokenTrimmed.length} Zeichen) und aktiv.`
    } else if (sendingToken && !ok) {
      successMessage.value = '⚠ Server akzeptierte Token, aber token_set=false — bitte Logs prüfen.'
    } else {
      successMessage.value = '✓ Einstellungen gespeichert (Token unverändert).'
    }
    gh.value.token = ''
    await loadGithub()
  } catch (e: any) {
    console.error('[GH-Save] Fehler', e)
    const errMsg = e?.response?.data?.message || e?.response?.data?.error || e?.message
    successMessage.value = '⚠ ' + (errMsg || 'Fehler beim Speichern')
  } finally {
    ghSaving.value = false
  }
}

async function onGithubTest() {
  ghTesting.value = true
  ghTestResult.value = null
  try {
    const body: any = {}
    if (gh.value.token) body.token = gh.value.token
    if (gh.value.default_repo) body.default_repo = gh.value.default_repo
    const r = await apiClient.post('/admin/github/test', body)
    ghTestResult.value = r.data
  } catch (e: any) {
    ghTestResult.value = { ok: false, error: e?.response?.data?.error || 'Test fehlgeschlagen' }
  } finally {
    ghTesting.value = false
  }
}

const onClose = () => {
  emit('close')
}

function stripMaskedDeep(o: any): any {
  if (Array.isArray(o)) return o.map(stripMaskedDeep)
  if (o && typeof o === 'object') {
    const out: any = {}
    for (const k of Object.keys(o)) {
      if (o[k] === '***') continue  // #416: maskierte Werte nicht zurücksenden
      out[k] = stripMaskedDeep(o[k])
    }
    return out
  }
  return o
}

const onSave = async () => {
  // #416: maskierte Werte aus dem Form-Object entfernen, sonst überschreiben
  // sie echte Tokens im Backend mit '***'.
  const cleaned = stripMaskedDeep(form.value)
  const ok = await adminStore.saveSettings(cleaned)
  if (ok) {
    successMessage.value = '✓ Einstellungen gespeichert.'
    setTimeout(() => emit('close'), 1000)
  }
}
</script>

<style scoped>
.gh-token-status {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 10px; background: #e8f5e9; border: 1px solid #a5d6a7;
  border-radius: 6px; font-size: 13px;
}
.gh-token-status.warn { background: #fff3e0; border-color: #ffcc80; }
.gh-token-badge {
  font-weight: 600; color: #2e7d32; padding: 2px 8px;
  background: #c8e6c9; border-radius: 12px; font-size: 12px;
}
.gh-token-badge.warn { color: #ef6c00; background: #ffe0b2; }
.gh-token-status code { font-size: 12px; color: #555; }
.hint-inline { font-size: 12px; color: #666; }

.github-test-result.ok {
  background: #e8f5e9;
  border: 1px solid #c8e6c9;
  color: #2e7d32;
}
.github-test-result.fail {
  background: #ffebee;
  border: 1px solid #ffcdd2;
  color: #c62828;
}
.github-test-result code {
  background: rgba(0,0,0,0.06);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
}

.ollama-checks { margin-top: 16px; display: flex; flex-direction: column; gap: 8px; }
.ollama-config-line {
  font-size: 12px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
  border-left: 3px solid #1565c0;
}
.ollama-config-line code, .ollama-checks code {
  background: rgba(0,0,0,0.06);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
}
.ollama-check {
  border-left: 3px solid;
  padding: 8px 12px;
  border-radius: 4px;
  background: #fafafa;
}
.ollama-check.ok    { border-color: #2e7d32; background: #f1f8e9; }
.ollama-check.fail  { border-color: #c62828; background: #ffebee; }
.ollama-check-head { display: flex; gap: 8px; align-items: center; font-size: 13px; }
.ollama-check.ok    .icon { color: #2e7d32; font-weight: bold; }
.ollama-check.fail  .icon { color: #c62828; font-weight: bold; }
.ollama-check-detail { font-size: 12px; color: #555; margin-top: 2px; }
.ollama-check-hint { font-size: 11px; margin-top: 4px; color: #666; }

.ollama-pull-status {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 6px;
  font-size: 12px;
}
.pull-bar-wrap {
  margin-top: 6px;
  background: #e0e0e0;
  border-radius: 999px;
  height: 8px;
  overflow: hidden;
}
.pull-bar {
  background: linear-gradient(90deg, #1565c0, #4caf50);
  height: 100%;
  transition: width 0.3s;
}
.ollama-echo {
  margin-top: 12px;
  padding: 10px 14px;
  background: #f8f9fa;
  border-left: 3px solid #1565c0;
  border-radius: 4px;
}
.ollama-echo-head { display: flex; align-items: center; gap: 6px; font-size: 13px; flex-wrap: wrap; }
.ollama-echo-response {
  margin-top: 8px; padding: 8px 12px;
  background: white; border: 1px solid #e0e0e0; border-radius: 4px;
}
.ollama-echo-response pre {
  font-family: 'SF Mono', Consolas, monospace; font-size: 12px;
  white-space: pre-wrap; margin: 0; word-break: break-word;
}
.spinner-tiny {
  display: inline-block;
  width: 10px; height: 10px; border-radius: 50%;
  border: 2px solid #1565c0; border-top-color: transparent;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }



.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 720px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 24px;
  border-bottom: 1px solid var(--color-border);
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
  color: var(--color-primary);
}

.btn-close {
  background: none;
  border: none;
  font-size: 22px;
  color: #999;
  cursor: pointer;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.tabs {
  display: flex;
  gap: 2px;
  background: #f5f5f5;
  border-bottom: 1px solid var(--color-border);
  padding: 0 24px;
}

.tab-btn {
  background: none;
  border: none;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #666;
  cursor: pointer;
  border-bottom: 3px solid transparent;
}

.tab-btn.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  background: white;
}

.tab-content {
  padding: 20px 24px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500 !important;
  cursor: pointer;
}

.checkbox-label input {
  margin: 0;
}

.form-group input[type="text"],
.form-group input[type="number"],
.form-group input:not([type]) {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.radio-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: normal;
}

fieldset {
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

fieldset legend {
  padding: 0 8px;
  font-weight: 600;
  font-size: 13px;
  color: var(--color-primary);
}

.module-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
}

.module-row label {
  font-weight: 500;
  margin: 0;
  min-width: 130px;
}

.muted {
  color: #888;
  font-size: 12px;
}

.hint {
  font-size: 12px;
  color: #888;
  margin: 4px 0 0 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0d47a1;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}

.alert {
  padding: 10px 16px;
  margin: 16px 24px;
  border-radius: 4px;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef5350;
}

.success-banner {
  position: absolute;
  bottom: 70px;
  left: 50%;
  transform: translateX(-50%);
  background: #e8f5e9;
  color: #2e7d32;
  padding: 8px 16px;
  border-radius: 4px;
  font-size: 13px;
  border: 1px solid #81c784;
}

.loading {
  padding: 40px;
  text-align: center;
  color: #888;
}

/* Embedded-Modus (in Admin-View statt Modal) */
.settings-embedded {
  width: 100%;
}
.modal-content.embedded {
  position: relative;
  max-width: none;
  width: 100%;
  margin: 0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  max-height: none;
  height: auto;
}
.sticky-footer {
  position: sticky; bottom: 0;
  background: white;
  border-top: 1px solid var(--color-border, #e0e0e0);
  padding: 12px 20px;
  display: flex; justify-content: flex-end; gap: 8px;
  z-index: 5;
}
</style>
