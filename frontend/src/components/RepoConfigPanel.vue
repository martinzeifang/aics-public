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
  <div class="repo-config-panel" :class="{ collapsed: !expanded }">
    <!-- #1252: ein-/ausklappbar, default eingeklappt -->
    <button type="button" class="rcp-head rcp-head-toggle" :aria-expanded="expanded"
            @click="expanded = !expanded">
      <span class="rcp-caret">{{ expanded ? '▾' : '▸' }}</span>
      <span class="rcp-title">{{ $t('geteilt.repoConfigPanel.repositoryProProjekt') }}</span>
      <span v-if="!expanded" class="rcp-summary">{{ vcs.repo || $t('geteilt.repoConfigPanel.nichtKonfiguriert') }}</span>
      <span v-if="hasToken" class="rcp-token-ok">{{ $t('geteilt.repoConfigPanel.tokenGespeichert') }}</span>
    </button>

    <template v-if="expanded">
    <p class="rcp-hint">
      {{ $t('geteilt.repoConfigPanel.diesesRepositoryWirdFurIssueErstellu') }}
    </p>

    <div class="rcp-grid">
      <label>{{ $t('common.provider') }}
        <select v-model="vcs.provider">
          <option value="github">{{ $t('common.gitHub') }}</option>
          <option value="gitlab">{{ $t('common.gitLab') }}</option>
        </select>
      </label>
      <label>{{ $t('common.repository') }}
        <input v-model="vcs.repo" :placeholder="$t('geteilt.repoConfigPanel.ownerRepoOderURL')" />
      </label>
      <label v-if="vcs.provider === 'gitlab'">{{ $t('common.baseURL') }}
        <input v-model="vcs.base_url" placeholder="https://gitlab.com" />
      </label>
      <label>{{ $t('geteilt.repoConfigPanel.accessTokenOptional') }}
        <input v-model="tokenInput" type="password" autocomplete="off"
               :placeholder="hasToken ? $t('geteilt.repoConfigPanel.gespeichertLeerLassenZumBeibehalten') : $t('geteilt.repoConfigPanel.personalAccessTokenOptional')" />
      </label>
    </div>

    <div class="rcp-actions">
      <button type="button" class="btn-primary" @click="save" :disabled="!!busy">{{ busy === 'save' ? $t('geteilt.repoConfigPanel.speichern') : $t('geteilt.repoConfigPanel.speichern2') }}</button>
      <button type="button" class="btn-secondary" @click="test" :disabled="!!busy || !vcs.repo">{{ busy === 'test' ? $t('geteilt.repoConfigPanel.test') : $t('geteilt.repoConfigPanel.zugriffTesten') }}</button>
      <span v-if="msg" :class="['rcp-msg', msgKind]">{{ msg }}</span>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch, onMounted } from 'vue'
import { t } from '../i18n'

const props = defineProps<{ apiBase: string; projektName: string }>()

const expanded = ref(false)   // #1252: default eingeklappt
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
  if (!props.projektName) { setMsg(t('geteilt.repoConfigPanel.keinProjektAusgewahltBitteZuerstEinP'), 'err'); return }
  if (!(vcs.repo || '').trim()) { setMsg(t('geteilt.repoConfigPanel.bitteEinRepositoryAngebenOwnerRepoOd'), 'err'); return }
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
    // Persistenz sichtbar bestätigen: frisch vom Server nachladen.
    await load()
    setMsg(t('geteilt.repoConfigPanel.repositoryEinstellungenGespeichert'))
  } catch (e: any) {
    // Immer eine Meldung zeigen — auch bei Netzwerk-/Auth-/Chunk-Fehlern ohne response.
    const status = e?.response?.status
    setMsg(
      e?.response?.data?.error
        || (status === 401 ? t('geteilt.repoConfigPanel.nichtAngemeldetSitzungAbgelaufenBitt')
            : `Speichern fehlgeschlagen${status ? ' (HTTP ' + status + ')' : ''}: ${e?.message || 'unbekannter Fehler'}`),
      'err',
    )
  } finally { busy.value = '' }
}

async function test() {
  if (!props.projektName) { setMsg(t('geteilt.repoConfigPanel.keinProjektAusgewahlt'), 'err'); return }
  if (!(vcs.repo || '').trim()) { setMsg(t('geteilt.repoConfigPanel.bitteZuerstEinRepositoryAngeben'), 'err'); return }
  busy.value = 'test'; setMsg('')
  try {
    const { default: api } = await import('../api/client')
    await api.post(
      `${props.apiBase}/projekte/${encodeURIComponent(props.projektName)}/repo-context`,
      { repo: vcs.repo.trim() },
    )
    setMsg(t('geteilt.repoConfigPanel.repositoryZugriffErfolgreich'))
  } catch (e: any) {
    const status = e?.response?.status
    setMsg(
      e?.response?.data?.error
        || (status === 401 ? t('geteilt.repoConfigPanel.nichtAngemeldetSitzungAbgelaufenBitt')
            : `Repository-Zugriff fehlgeschlagen${status ? ' (HTTP ' + status + ')' : ''}: ${e?.message || 'unbekannter Fehler'}`),
      'err',
    )
  } finally { busy.value = '' }
}

watch(() => props.projektName, load)
onMounted(load)
</script>

<style scoped>
.repo-config-panel { border: 1px solid #d0d7de; border-radius: 8px; padding: 14px 16px; background: #fafbfc; margin: 12px 0; }
.repo-config-panel.collapsed { padding: 8px 12px; }
.rcp-head { display: flex; align-items: center; gap: 12px; }
/* #1252: Kopfzeile als Klapp-Schalter */
.rcp-head-toggle { width: 100%; background: none; border: none; cursor: pointer; padding: 0; text-align: left; font: inherit; }
.rcp-head-toggle:hover .rcp-title { text-decoration: underline; }
.rcp-caret { color: #1565c0; font-size: 0.8rem; width: 1rem; flex: 0 0 auto; }
.rcp-title { font-weight: 600; color: #1565c0; }
.rcp-summary { font-size: 0.82rem; color: #607d8b; font-family: monospace; }
.rcp-token-ok { font-size: 0.82rem; color: #2e7d32; margin-left: auto; }
.rcp-hint { font-size: 0.82rem; color: #57606a; margin: 4px 0 10px; }
.rcp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.rcp-grid label { display: flex; flex-direction: column; font-size: 0.82rem; color: #424a53; gap: 4px; }
.rcp-grid input, .rcp-grid select { padding: 6px 8px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 0.9rem; }
.rcp-actions { display: flex; align-items: center; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
.rcp-msg { font-size: 0.85rem; }
.rcp-msg.ok { color: #2e7d32; }
.rcp-msg.err { color: #c62828; }
</style>
