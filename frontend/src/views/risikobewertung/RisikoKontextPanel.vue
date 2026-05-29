<template>
  <div class="kontext-panel">
    <h3>Kontext-Quellen <small>(für die KI-Risiko-Discovery)</small></h3>

    <!-- Repository (GitHub/GitLab) — #764 -->
    <section class="block">
      <h4>Repository (GitHub / GitLab)</h4>
      <div class="grid">
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
        <label>Token-ENV (optional)
          <input v-model="vcs.token_env" placeholder="z.B. GITLAB_TOKEN" />
        </label>
      </div>
      <p class="hint">Es wird nur der <em>Name</em> der Umgebungsvariable gespeichert,
        niemals der Token selbst.</p>
      <div class="actions">
        <button class="btn-secondary" @click="saveRepo" :disabled="busy">Repo speichern</button>
        <button class="btn-secondary" @click="testRepo" :disabled="busy || !vcs.repo">
          Repo-Kontext testen
        </button>
      </div>
      <pre v-if="repoPreview" class="preview">{{ repoPreview }}</pre>
    </section>

    <!-- Software-Beschreibung + Doku-URLs — #766 -->
    <section class="block">
      <h4>Software-Beschreibung &amp; Doku-URLs</h4>
      <label>Beschreibung der Software
        <textarea v-model="software.description" rows="3"
                  placeholder="Kurzbeschreibung des bewerteten Systems"></textarea>
      </label>
      <label>Doku-URLs</label>
      <div v-for="(u, i) in software.doc_urls" :key="i" class="url-row">
        <input v-model="software.doc_urls[i]" placeholder="https://…/doku" />
        <button class="btn-icon" @click="software.doc_urls.splice(i, 1)" title="Entfernen">✕</button>
      </div>
      <button class="btn-link" @click="software.doc_urls.push('')">+ URL hinzufügen</button>
      <div class="actions">
        <button class="btn-secondary" @click="saveSoftware" :disabled="busy">
          Beschreibung &amp; URLs speichern
        </button>
      </div>
    </section>

    <!-- Anhänge — #765 -->
    <section class="block">
      <h4>Anhänge</h4>
      <div class="actions">
        <input ref="fileInput" type="file" @change="uploadFile"
               accept=".pdf,.docx,.txt,.md,.csv,.xlsx" />
      </div>
      <div class="url-row">
        <input v-model="newUrl" placeholder="URL als Anhang crawlen (https://…)" />
        <button class="btn-secondary" @click="addUrl" :disabled="busy || !newUrl">URL anhängen</button>
      </div>
      <ul class="attachments" v-if="attachments.length">
        <li v-for="a in attachments" :key="a.id">
          <span>{{ a.filename }}</span>
          <button class="btn-icon" @click="deleteAttachment(a.id)" title="Löschen">🗑</button>
        </li>
      </ul>
      <p v-else class="hint">Noch keine Anhänge.</p>
    </section>

    <p v-if="msg" :class="['msg', msgKind]">{{ msg }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import apiClient from '../../api/client'
import type { VcsPublish, SoftwareMeta, RBAttachment } from '../../stores/risikobewertung'

const props = defineProps<{ projektName: string }>()

const busy = ref(false)
const msg = ref('')
const msgKind = ref<'ok' | 'err'>('ok')
const repoPreview = ref('')
const newUrl = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const attachments = ref<RBAttachment[]>([])

const vcs = reactive<VcsPublish>({ provider: 'github', repo: '', base_url: '', token_env: '' })
const software = reactive<SoftwareMeta>({ description: '', doc_urls: [] })

const base = () => `/risikobewertung/projekte/${encodeURIComponent(props.projektName)}`

function flash(text: string, kind: 'ok' | 'err' = 'ok') {
  msg.value = text
  msgKind.value = kind
  setTimeout(() => { if (msg.value === text) msg.value = '' }, 4000)
}

async function load() {
  if (!props.projektName) return
  try {
    const p = await apiClient.get(base())
    Object.assign(vcs, { provider: 'github', repo: '', base_url: '', token_env: '', ...(p.data.vcs_publish || {}) })
    Object.assign(software, { description: '', doc_urls: [], ...(p.data.software || {}) })
    if (!Array.isArray(software.doc_urls)) software.doc_urls = []
  } catch { /* ignore */ }
  await loadAttachments()
}

async function loadAttachments() {
  try {
    const r = await apiClient.get(`${base()}/attachments`)
    attachments.value = r.data || []
  } catch { attachments.value = [] }
}

async function saveRepo() {
  busy.value = true
  try {
    await apiClient.put(`${base()}/repo-config`, { vcs_publish: { ...vcs } })
    flash('Repo-Einstellungen gespeichert.')
  } catch (e: any) {
    flash(e?.response?.data?.error || 'Fehler beim Speichern.', 'err')
  } finally { busy.value = false }
}

async function testRepo() {
  busy.value = true
  repoPreview.value = ''
  try {
    const r = await apiClient.post(`${base()}/repo-context`, { repo: vcs.repo })
    repoPreview.value = (r.data.repo_context || '').slice(0, 1500)
    flash('Repo-Kontext geladen.')
  } catch (e: any) {
    flash(e?.response?.data?.error || 'Repo-Kontext fehlgeschlagen.', 'err')
  } finally { busy.value = false }
}

async function saveSoftware() {
  busy.value = true
  try {
    const doc_urls = (software.doc_urls || []).map(u => u.trim()).filter(Boolean)
    await apiClient.put(base(), { software: { description: software.description, doc_urls } })
    software.doc_urls = doc_urls
    flash('Beschreibung & Doku-URLs gespeichert.')
  } catch (e: any) {
    flash(e?.response?.data?.error || 'Fehler beim Speichern.', 'err')
  } finally { busy.value = false }
}

async function uploadFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    await apiClient.post(`${base()}/attachments/file`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
    flash('Datei angehängt.')
    await loadAttachments()
  } catch (e: any) {
    flash(e?.response?.data?.error || 'Upload fehlgeschlagen.', 'err')
  } finally {
    busy.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function addUrl() {
  busy.value = true
  try {
    await apiClient.post(`${base()}/attachments/url`, { url: newUrl.value.trim() })
    flash('URL angehängt.')
    newUrl.value = ''
    await loadAttachments()
  } catch (e: any) {
    flash(e?.response?.data?.error || 'URL-Anhang fehlgeschlagen.', 'err')
  } finally { busy.value = false }
}

async function deleteAttachment(id: string) {
  busy.value = true
  try {
    await apiClient.delete(`${base()}/attachments/${id}`)
    await loadAttachments()
  } catch (e: any) {
    flash(e?.response?.data?.error || 'Löschen fehlgeschlagen.', 'err')
  } finally { busy.value = false }
}

onMounted(load)
watch(() => props.projektName, load)
</script>

<style scoped>
.kontext-panel { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 12px 0; }
.kontext-panel h3 { margin: 0 0 12px; color: #1565c0; font-size: 1.05rem; }
.kontext-panel h3 small { color: #64748b; font-weight: normal; font-size: .8rem; }
.block { border-top: 1px solid #e2e8f0; padding: 12px 0; }
.block h4 { margin: 0 0 8px; font-size: .95rem; color: #334155; }
.grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
label { display: flex; flex-direction: column; font-size: .8rem; color: #475569; gap: 2px; }
input, select, textarea { padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: .85rem; }
.url-row { display: flex; gap: 6px; align-items: center; margin: 4px 0; }
.url-row input { flex: 1; }
.actions { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.hint { font-size: .75rem; color: #64748b; margin: 4px 0; }
.preview { background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 4px; font-size: .72rem; max-height: 220px; overflow: auto; white-space: pre-wrap; }
.attachments { list-style: none; padding: 0; margin: 8px 0 0; }
.attachments li { display: flex; justify-content: space-between; align-items: center; padding: 4px 8px; background: #fff; border: 1px solid #e2e8f0; border-radius: 4px; margin-bottom: 4px; font-size: .85rem; }
.btn-icon { background: none; border: none; cursor: pointer; font-size: .9rem; }
.btn-link { background: none; border: none; color: #1565c0; cursor: pointer; padding: 4px 0; font-size: .8rem; }
.btn-secondary { background: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: .85rem; }
.btn-secondary:disabled { opacity: .5; cursor: not-allowed; }
.msg { margin-top: 10px; padding: 8px; border-radius: 4px; font-size: .85rem; }
.msg.ok { background: #dcfce7; color: #166534; }
.msg.err { background: #fee2e2; color: #991b1b; }
</style>
