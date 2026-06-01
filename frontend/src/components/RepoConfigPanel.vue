<!--
  Wiederverwendbares Panel zur pro-Projekt-Repository-Konfiguration (#862).

  Speichert GitHub/GitLab-Repo (+ optionalen Token) pro Projekt über die
  modul-eigenen Endpoints `GET/PUT <apiBase>/projekte/<name>/repo-config`.
  Der Token wird serverseitig verschlüsselt abgelegt und nie ausgeliefert
  (nur `has_token`-Flag). Genutzt von CRA, NIS2, AI-Act und DSGVO.

  Props:
    apiBase     z.B. "/cra" | "/nis2" | "/aiact" | "/dsgvo"
    projektName aktueller Projektname
-->
<template>
  <div class="repo-config-panel">
    <div class="rcp-head">
      <span class="rcp-title">🔗 Repository (pro Projekt)</span>
      <span v-if="hasToken" class="rcp-token-ok">✓ Token gespeichert</span>
    </div>
    <p class="rcp-hint">
      Dieses Repository wird für Issue-Erstellung, Massenanlage und Sync dieses
      Projekts verwendet. Keine globale Einstellung.
    </p>

    <div class="rcp-grid">
      <label>Provider
        <select v-model="vcs.provider">
          <option value="github">GitHub</option>
          <option value="gitlab">GitLab</option>
        </select>
      </label>
      <label>Repository
        <input v-model="vcs.repo" placeholder="owner/repo oder URL" />
      </label>
      <label v-if="vcs.provider === 'gitlab'">Base-URL
        <input v-model="vcs.base_url" placeholder="https://gitlab.com" />
      </label>
      <label>Access-Token (optional)
        <input v-model="tokenInput" type="password" autocomplete="off"
               :placeholder="hasToken ? '•••••• gespeichert — leer lassen zum Beibehalten' : 'Personal Access Token (optional)'" />
      </label>
    </div>

    <div class="rcp-actions">
      <button class="btn-primary" @click="save" :disabled="busy">{{ busy === 'save' ? '⏳ Speichern…' : '💾 Speichern' }}</button>
      <button class="btn-secondary" @click="test" :disabled="busy || !vcs.repo">{{ busy === 'test' ? '⏳ Test…' : '🔍 Zugriff testen' }}</button>
      <span v-if="msg" :class="['rcp-msg', msgKind]">{{ msg }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch, onMounted } from 'vue'

const props = defineProps<{ apiBase: string; projektName: string }>()

const vcs = reactive<Record<string, string>>({ provider: 'github', repo: '', base_url: '' })
const tokenInput = ref('')
const hasToken = ref(false)
const busy = ref<'' | 'save' | 'test'>('')
const msg = ref('')
const msgKind = ref<'ok' | 'err'>('ok')

function setMsg(text: string, kind: 'ok' | 'err' = 'ok') {
  msg.value = text; msgKind.value = kind
}

async function load() {
  if (!props.projektName) return
  setMsg('')
  try {
    const { default: api } = await import('../api/client')
    const r = await api.get(`${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/repo-config`)
    const v = r.data?.vcs_publish || {}
    vcs.provider = v.provider || 'github'
    vcs.repo = v.repo || ''
    vcs.base_url = v.base_url || ''
    hasToken.value = !!v.has_token
    tokenInput.value = ''
  } catch {
    /* Projekt evtl. ohne Repo-Config — leeres Panel ist ok */
  }
}

async function save() {
  if (!props.projektName) return
  busy.value = 'save'; setMsg('')
  try {
    const { default: api } = await import('../api/client')
    const payload: Record<string, string> = { provider: vcs.provider, repo: (vcs.repo || '').trim() }
    if (vcs.provider === 'gitlab' && vcs.base_url) payload.base_url = vcs.base_url.trim()
    if (tokenInput.value.trim()) payload.token = tokenInput.value.trim()
    const r = await api.put(
      `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/repo-config`,
      { vcs_publish: payload },
    )
    hasToken.value = !!r.data?.vcs_publish?.has_token
    tokenInput.value = ''
    setMsg('Repository-Einstellungen gespeichert.')
  } catch (e: any) {
    setMsg(e?.response?.data?.error || 'Speichern fehlgeschlagen.', 'err')
  } finally { busy.value = '' }
}

async function test() {
  if (!props.projektName || !vcs.repo) return
  busy.value = 'test'; setMsg('')
  try {
    const { default: api } = await import('../api/client')
    await api.post(
      `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/repo-context`,
      { repo: vcs.repo.trim() },
    )
    setMsg('Repository-Zugriff erfolgreich.')
  } catch (e: any) {
    setMsg(e?.response?.data?.error || 'Repository-Zugriff fehlgeschlagen.', 'err')
  } finally { busy.value = '' }
}

watch(() => props.projektName, load)
onMounted(load)
</script>

<style scoped>
.repo-config-panel { border: 1px solid #d0d7de; border-radius: 8px; padding: 14px 16px; background: #fafbfc; margin: 12px 0; }
.rcp-head { display: flex; align-items: center; gap: 12px; }
.rcp-title { font-weight: 600; color: #1565c0; }
.rcp-token-ok { font-size: 0.82rem; color: #2e7d32; }
.rcp-hint { font-size: 0.82rem; color: #57606a; margin: 4px 0 10px; }
.rcp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.rcp-grid label { display: flex; flex-direction: column; font-size: 0.82rem; color: #424a53; gap: 4px; }
.rcp-grid input, .rcp-grid select { padding: 6px 8px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 0.9rem; }
.rcp-actions { display: flex; align-items: center; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
.rcp-msg { font-size: 0.85rem; }
.rcp-msg.ok { color: #2e7d32; }
.rcp-msg.err { color: #c62828; }
</style>
