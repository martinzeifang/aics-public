<template>
  <div v-if="open" :class="[embedded ? 'settings-embedded' : 'modal-overlay']" @mousedown.self="!embedded && onClose()">
    <div :class="['modal-content', 'settings-modal', { embedded }]">
      <div v-if="!embedded" class="modal-header">
        <h2>{{ $t('app.settings') }}</h2>
        <button class="btn-close" @click="onClose">✕</button>
      </div>

      <div v-if="adminStore.loading && !adminStore.settings" class="loading">
        {{ $t('geteilt.settingsDialog.einstellungenWerdenGeladen') }}
      </div>

      <!-- #1827: Nur wenn gar kein Formular da ist, tritt der Fehler an seine
           Stelle — beim Laden gibt es sonst nichts zu zeigen. Ein Fehler beim
           *Speichern* gehört dagegen NEBEN das Formular: Vorher ersetzte er es,
           und der Anwender stand vor einem Dialog aus Titel, Schließen-Knopf
           und Meldung. Genau der Haken, auf den die Meldung verweist, war damit
           nicht mehr erreichbar. -->
      <FehlerHinweis v-else-if="adminStore.error && !form" :text="adminStore.error"
                     @close="adminStore.error = ''" />

      <div v-else-if="form" class="modal-body">
        <FehlerHinweis v-if="adminStore.error" :text="adminStore.error"
                       @close="adminStore.error = ''" />
        <!-- Tabs (im fokussierten only-Modus ausgeblendet) -->
        <div v-if="!only" class="tabs">
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
            <label>{{ $t('geteilt.settingsDialog.kIProvider') }}</label>
            <div class="radio-group">
              <label>
                <input type="radio" value="on_prem" v-model="form.ai.provider" />
                {{ $t('geteilt.settingsDialog.onPremOllamaLokal') }}
              </label>
              <label>
                <input type="radio" value="cloud" v-model="form.ai.provider" />
                {{ $t('geteilt.settingsDialog.cloudOpenAIAnthropic') }}
              </label>
            </div>
          </div>

          <!-- #1485/#1486 (Sprint #40): App-Nachweise in die KI-Bewertung einbeziehen -->
          <div class="form-group">
            <label class="chk-inline">
              <input type="checkbox" v-model="form.ai.include_app_evidence" />
              {{ $t('geteilt.settingsDialog.nachweiseAusDerAnwendungInDieKIBewer') }}
            </label>
            <small class="hint">
              {{ $t('geteilt.settingsDialog.beziehtDenOperativenZustandSchwachst') }}
            </small>
          </div>

          <fieldset v-if="form.ai.provider === 'on_prem'">
            <legend>{{ $t('geteilt.settingsDialog.onPremOllama') }}</legend>
            <div class="form-group">
              <label>{{ $t('common.baseURL') }}</label>
              <input v-model="form.ai.on_prem.base_url" placeholder="http://127.0.0.1:11434" />
              <p class="hint">
                <strong>{{ $t('geteilt.settingsDialog.lokalDesktopDev') }}</strong> <code>http://127.0.0.1:11434</code><br />
                <strong>{{ $t('geteilt.settingsDialog.docker') }}</strong> <code>http://ollama:11434</code> {{ $t('geteilt.settingsDialog.serviceNameImComposeNetzNiemals') }} <code>localhost</code> {{ $t('geteilt.settingsDialog.oder') }} <code>127.0.0.1</code> {{ $t('geteilt.settingsDialog.ausDemContainerDasZeigtAufDenContain') }}
              </p>
            </div>
            <div class="form-group">
              <label>{{ $t('geteilt.settingsDialog.model') }}</label>
              <select v-model="form.ai.on_prem.model" style="width: 100%;">
                <option value="">{{ $t('geteilt.settingsDialog.manuellEintragenUnten') }}</option>
                <optgroup v-if="ollamaModels.installed.length" :label="$t('geteilt.settingsDialog.installiert')">
                  <option v-for="m in ollamaModels.installed" :key="m.name" :value="m.name">
                    {{ m.name }} ({{ formatGB(m.size_bytes) }})
                  </option>
                </optgroup>
                <optgroup :label="$t('geteilt.settingsDialog.empfehlungenNochNichtInstalliert')">
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
                {{ ollamaModels.loading ? $t('geteilt.settingsDialog.lade') : $t('geteilt.settingsDialog.modelleVomServerNeuLaden') }}
              </button>
              <input v-model="form.ai.on_prem.model" :placeholder="$t('geteilt.settingsDialog.oderManuellLlama3B')"
                     style="margin-top: 6px;" />
              <p v-if="ollamaModels.error" class="hint" style="color: #c62828">
                {{ $t('geteilt.settingsDialog.modellListeKonnteNichtGeladenWerdenV', { v0: ollamaModels.error }) }}
              </p>
              <p v-else-if="ollamaModels.installed.length === 0" class="hint" style="color: #f57c00">
                {{ $t('geteilt.settingsDialog.keineModelleInstalliertWahleEineEmpf') }}
              </p>
              <p v-else class="hint">
                {{ $t('geteilt.settingsDialog.v0ModelleInstalliertEinesAuswahlenOd', { v0: ollamaModels.installed.length }) }}
              </p>
            </div>
            <div class="form-group">
              <label>{{ $t('geteilt.settingsDialog.timeoutSekunden') }}</label>
              <input v-model.number="form.ai.on_prem.timeout_s" type="number" min="5" max="600" />
            </div>

            <!-- Ollama-Diagnose-Suite -->
            <div class="ollama-diagnose">
              <div style="display:flex; gap:8px; align-items:center; margin-top:14px; flex-wrap: wrap;">
                <button type="button" class="btn btn-primary" @click="onOllamaDiagnose"
                        :disabled="ollamaDiag.running">
                  {{ ollamaDiag.running ? $t('geteilt.settingsDialog.teste') : $t('geteilt.settingsDialog.diagnoseAusfuhren') }}
                </button>
                <button type="button" class="btn btn-secondary" @click="onOllamaPullDefault"
                        :disabled="ollamaPull.running || !form.ai.on_prem.model">
                  {{ ollamaPull.running ? $t('geteilt.settingsDialog.lade2') : `⬇ ${form.ai.on_prem.model || 'Modell'} pullen` }}
                </button>
                <button type="button" class="btn btn-secondary" @click="onOllamaEchoTest"
                        :disabled="ollamaEcho.running || !form.ai.on_prem.model">
                  {{ ollamaEcho.running ? $t('geteilt.settingsDialog.streamt') : $t('geteilt.settingsDialog.echoTestHelloWorld') }}
                </button>
              </div>

              <!-- Echo-Test Live-Anzeige -->
              <div v-if="ollamaEcho.shown" class="ollama-echo">
                <div class="ollama-echo-head">
                  <span class="spinner-tiny" v-if="ollamaEcho.running"></span>
                  <strong>{{ ollamaEcho.status }}</strong>
                  <span v-if="ollamaEcho.ttftMs" class="muted" style="margin-left: 8px;">
                    {{ $t('geteilt.settingsDialog.tokenNachV0Ms', { v0: ollamaEcho.ttftMs }) }}
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
                    {{ $t('geteilt.settingsDialog.antwortVomModell') }}
                  </div>
                  <pre>{{ ollamaEcho.chunks }}</pre>
                </div>
                <FehlerHinweis :text="ollamaEcho.error"
                               @close="ollamaEcho.error = ''" />
              </div>
              <div v-if="ollamaPull.result" class="ollama-pull-status">
                <div v-if="ollamaPull.result.running" class="muted">
                  <span class="spinner-tiny"></span>
                  {{ ollamaPull.result.status || $t('geteilt.settingsDialog.lade3') }}
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
                  {{ $t('geteilt.settingsDialog.pullAbgeschlossenFur') }} <code>{{ ollamaPull.result.model }}</code>
                </div>
                <div v-if="ollamaPull.result.ok === false" style="color:#c62828">
                  ✗ {{ ollamaPull.result.error }}
                </div>
              </div>

              <div v-if="ollamaDiag.result" class="ollama-checks">
                <div class="ollama-config-line">
                  <strong>{{ ollamaDiag.result.config.base_url }}</strong>
                  {{ $t('geteilt.settingsDialog.modell') }} <code>{{ ollamaDiag.result.config.model || '(keins)' }}</code>
                  {{ $t('geteilt.settingsDialog.quelle') }} <em>{{ ollamaDiag.result.config.source }}</em>
                </div>
                <div v-for="(c, i) in ollamaDiag.result.checks" :key="i"
                     class="ollama-check" :class="{ ok: c.ok, fail: !c.ok }">
                  <div class="ollama-check-head">
                    <span class="icon">{{ c.ok ? '✓' : '✗' }}</span>
                    <strong>{{ c.name }}</strong>
                  </div>
                  <div class="ollama-check-detail">{{ c.detail }}</div>
                  <div v-if="c.meta?.install_hint" class="ollama-check-hint">
                    {{ $t('geteilt.settingsDialog.tipp') }} <code>{{ c.meta.install_hint }}</code>
                  </div>
                  <div v-if="(c.meta?.installed?.length || c.meta?.models?.length)" class="ollama-check-hint">
                    <details>
                      <summary>{{ $t('geteilt.settingsDialog.installierteModelleV0', { v0: (c.meta.installed || c.meta.models).length }) }}</summary>
                      <ul style="margin: 4px 0 0 16px;">
                        <li v-for="m in (c.meta.installed || c.meta.models)" :key="m">
                          <code>{{ m }}</code>
                        </li>
                      </ul>
                    </details>
                  </div>
                  <div v-if="c.meta?.tokens_per_second" class="ollama-check-hint">
                    {{ $t('geteilt.settingsDialog.performance') }} <strong>{{ c.meta.tokens_per_second }}</strong> {{ $t('geteilt.settingsDialog.tokenS') }}
                    <strong>{{ c.meta.eval_count }}</strong> {{ $t('geteilt.settingsDialog.tokenOutput') }}
                  </div>
                </div>
              </div>
            </div>
          </fieldset>

          <fieldset v-if="form.ai.provider === 'cloud'">
            <legend>{{ $t('common.cloud') }}</legend>
            <!-- #1409: Anbieter-Auswahl mit Auto-Konfiguration (Base-URL) -->
            <div class="form-group">
              <label>{{ $t('geteilt.settingsDialog.cloudAnbieter') }}</label>
              <select :value="cloudPreset" @change="applyCloudPreset(($event.target as HTMLSelectElement).value)" style="width:100%;">
                <option value="anthropic">{{ $t('geteilt.settingsDialog.anthropicClaude') }}</option>
                <option value="openai">{{ $t('geteilt.settingsDialog.openAIGPT') }}</option>
                <option value="google">{{ $t('geteilt.settingsDialog.googleGeminiOpenAIKompatibel') }}</option>
                <option value="other">{{ $t('geteilt.settingsDialog.andereBenutzerdefiniert') }}</option>
              </select>
              <p class="hint">{{ $t('geteilt.settingsDialog.wahltDenAnbieterUndSetztDieBaseURLAu') }}</p>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="form.ai.cloud.allow_data_egress" />
                {{ $t('geteilt.settingsDialog.datenausgangErlaubenPflichtFurCloud') }}
              </label>
              <p class="hint">{{ $t('geteilt.settingsDialog.datenVerlassenDenLokalenRechnerNurAk') }}</p>
              <!-- #1827: Der Haken ist Voraussetzung, nicht Zusatz — das soll
                   hier stehen und nicht erst in der Fehlermeldung nach dem
                   Speichern. -->
              <p v-if="egressFehlt" class="hint hint-warn">
                {{ $t('geteilt.settingsDialog.ohneDiesenHakenLasstSichDerCloudProv') }}
              </p>
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="form.ai.cloud.redact" />
                {{ $t('geteilt.settingsDialog.sensitiveFelderVorVersandRedigieren') }}
              </label>
            </div>
            <div class="form-group">
              <label>{{ $t('common.baseURL') }}</label>
              <input v-model="form.ai.cloud.base_url" />
            </div>
            <div class="form-group">
              <label>{{ $t('geteilt.settingsDialog.model') }}</label>
              <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <input v-model="form.ai.cloud.model" placeholder="z. B. claude-haiku-4-5-20251001"
                       style="flex:1; min-width:220px;" />
                <button type="button" class="btn-secondary" :disabled="modelsLoading" @click="fetchModels">
                  {{ modelsLoading ? $t('geteilt.settingsDialog.ladt') : $t('geteilt.settingsDialog.modelleAbrufen') }}
                </button>
              </div>
              <select v-if="availableModels.length" class="model-select"
                      :value="form.ai.cloud.model"
                      @change="form.ai.cloud.model = ($event.target as HTMLSelectElement).value"
                      style="width:100%; margin-top:6px;">
                <option value="" disabled>{{ $t('geteilt.settingsDialog.modellAuswahlen') }}</option>
                <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
              </select>
              <small v-if="modelsMsg" class="hint">{{ modelsMsg }}</small>
            </div>
            <div class="form-group">
              <label>{{ $t('geteilt.settingsDialog.aPIKeyDirekt') }}</label>
              <input type="password" v-model="form.ai.cloud.api_key"
                     autocomplete="off" :placeholder="$t('geteilt.settingsDialog.skWirdVerschlusseltInDerConfigGespei')" />
              <small class="hint">{{ $t('geteilt.settingsDialog.empfohlenKeyDirektHierEintragenWirdD') }}</small>
            </div>
            <div class="form-group">
              <label>{{ $t('geteilt.settingsDialog.aPIKeyEnvVariableAlternative') }}</label>
              <input v-model="form.ai.cloud.api_key_env"
                     :placeholder="$t('geteilt.settingsDialog.zBAICLOUDAPIKEYNAMEDerVariableNichtD')" />
            </div>
          </fieldset>
        </div>

        <!-- Tab: Module -->
        <div v-if="activeTab === 'modules'" class="tab-content">
          <p class="hint">
            {{ $t('geteilt.settingsDialog.welcheModuleInDerWebOberflacheErsche') }}
          </p>
          <div v-for="m in webModules" :key="m.id" class="module-row">
            <input
              type="checkbox"
              :id="`mod-${m.id}`"
              :checked="!isDisabled(m.id)"
              :disabled="m.fix"
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
              {{ $t('geteilt.settingsDialog.automatischesBackupBeimBeendenDerSui') }}
            </label>
          </div>
          <div class="form-group">
            <label>{{ $t('geteilt.settingsDialog.anzahlBehaltenerBackupsRetention') }}</label>
            <input v-model.number="form.backup.backup_retention_count" type="number" min="1" max="50" />
          </div>
          <div class="form-group">
            <p class="hint">
              {{ $t('geteilt.settingsDialog.backupsWerdenGespeichertIn') }} <code>out/backup/</code> {{ $t('geteilt.settingsDialog.alsZIPDateienDieVerwaltungErfolgtImB') }} <em>{{ $t('app.admin') }}</em>.
            </p>
          </div>
        </div>

        <!-- Tab: GitHub-Integration -->
        <div v-if="activeTab === 'github'" class="tab-content">
          <h3>{{ $t('geteilt.settingsDialog.gitHubIntegration') }}</h3>
          <p class="hint">
            {{ $t('geteilt.settingsDialog.wirdBenotigtFurIssueErstellungAusDen') }} <code>repo</code> {{ $t('geteilt.settingsDialog.lesenIssuesErstellen') }}
          </p>

          <div class="form-group">
            <label>{{ $t('geteilt.settingsDialog.personalAccessToken') }}</label>
            <div v-if="gh.token_set" class="gh-token-status">
              <span class="gh-token-badge">{{ $t('geteilt.settingsDialog.aktiv') }}</span>
              <code>{{ gh.token_masked }}</code>
              <span class="hint-inline">{{ $t('geteilt.settingsDialog.quelleV0', { v0: gh.source === 'env' ? $t('geteilt.settingsDialog.serverENV') : $t('geteilt.settingsDialog.konfiguration') }) }}</span>
            </div>
            <div v-else class="gh-token-status warn">
              <span class="gh-token-badge warn">{{ $t('geteilt.settingsDialog.nichtGesetzt') }}</span>
              <span class="hint-inline">{{ $t('geteilt.settingsDialog.gitHubFunktionenSindDeaktiviert') }}</span>
            </div>
            <div class="row" style="display:flex; gap:8px; margin-top: 8px;">
              <input
                v-model="gh.token"
                :placeholder="gh.token_set ? $t('geteilt.settingsDialog.neuenTokenEingebenUmZuAndern') : $t('geteilt.settingsDialog.ghpTokenEinfugen')"
                :type="ghShowToken ? 'text' : 'password'"
                autocomplete="new-password"
                style="flex: 1;"
              />
              <button type="button" class="btn btn-secondary" @click="ghShowToken = !ghShowToken">
                {{ ghShowToken ? '🙈' : '👁' }}
              </button>
            </div>
            <p class="hint">
              <a href="https://github.com/settings/tokens?type=beta" target="_blank" rel="noopener noreferrer">
                {{ $t('geteilt.settingsDialog.tokenAufGithubComErstellen') }}
              </a> {{ $t('geteilt.settingsDialog.scopeRepoReichtFurIssuesRepoScanAusS') }}
            </p>
            <p v-if="gh.source === 'env'" class="hint" style="color:#f57c00">
              {{ $t('geteilt.settingsDialog.aktiverTokenKommtAusDerServerENVWenn') }}
            </p>
          </div>

          <div class="form-group">
            <label>{{ $t('geteilt.settingsDialog.benutzernameOptional') }}</label>
            <input v-model="gh.username" placeholder="dein-github-username" />
          </div>

          <div class="form-group">
            <label>{{ $t('geteilt.settingsDialog.standardRepositoryOptional') }}</label>
            <input v-model="gh.default_repo" placeholder="owner/repo" />
            <p class="hint">
              {{ $t('geteilt.settingsDialog.wirdInModulenAlsVorbelegungVerwendet') }}
            </p>
          </div>

          <div class="row" style="display:flex; gap:10px; margin-top: 12px; align-items: center;">
            <button type="button" class="btn btn-primary" @click="onGithubSave" :disabled="ghSaving">
              {{ ghSaving ? '…' : $t('geteilt.settingsDialog.gitHubSpeichern') }}
            </button>
            <button type="button" class="btn btn-secondary" @click="onGithubTest" :disabled="ghTesting">
              {{ ghTesting ? $t('geteilt.settingsDialog.teste2') : $t('geteilt.settingsDialog.verbindungTesten') }}
            </button>
            <small style="color: #666; flex: 1;">
              {{ $t('geteilt.settingsDialog.tippDerGlobaleSpeichernButtonUntenUb') }}
            </small>
          </div>

          <div v-if="ghTestResult" class="github-test-result"
               :class="{ ok: ghTestResult.ok, fail: !ghTestResult.ok }"
               style="margin-top: 16px; padding: 12px; border-radius: 6px;">
            <div v-if="ghTestResult.ok">
              <strong>{{ $t('geteilt.settingsDialog.verbundenAlsV0', { v0: ghTestResult.login }) }}</strong>
              <span v-if="ghTestResult.name"> ({{ ghTestResult.name }})</span>
              <div v-if="ghTestResult.scopes?.length" style="margin-top: 6px;">
                {{ $t('geteilt.settingsDialog.scopes') }} <code>{{ ghTestResult.scopes.join(', ') }}</code>
              </div>
              <div v-if="ghTestResult.rate_limit_remaining" class="hint">
                {{ $t('geteilt.settingsDialog.rateLimitVerbleibendV0', { v0: ghTestResult.rate_limit_remaining }) }}
              </div>
              <div v-if="ghTestResult.default_repo_check" style="margin-top: 8px;">
                <strong>{{ $t('geteilt.settingsDialog.defaultRepo') }}</strong>
                <span v-if="ghTestResult.default_repo_check.exists">
                  ✓ <code>{{ ghTestResult.default_repo_check.repo }}</code> erreichbar
                </span>
                <span v-else style="color: #c62828">
                  ✗ <code>{{ ghTestResult.default_repo_check.repo }}</code> {{ $t('geteilt.settingsDialog.nichtErreichbar') }}
                </span>
              </div>
              <div v-if="ghTestResult.contents_permission" style="margin-top: 8px;">
                <strong>{{ $t('geteilt.settingsDialog.contentsPermission') }}</strong>
                <span v-if="ghTestResult.contents_permission.ok === true" style="color: #2e7d32">
                  {{ $t('geteilt.settingsDialog.repoScanPflichtDokuDetectFunktionier') }}
                </span>
                <span v-else-if="ghTestResult.contents_permission.ok === false" style="color: #c62828">
                  ✗ {{ ghTestResult.contents_permission.note }}
                </span>
                <span v-else style="color: #666">
                  {{ ghTestResult.contents_permission.note }}
                </span>
              </div>
            </div>
            <div v-else>
              <strong>{{ $t('geteilt.settingsDialog.verbindungFehlgeschlagen') }}</strong>
              <div>{{ ghTestResult.error }}</div>
              <div v-if="ghTestResult.hint" class="hint">{{ ghTestResult.hint }}</div>
            </div>
          </div>
        </div>

      </div>

      <div :class="['modal-footer', { 'sticky-footer': embedded }]">
        <button v-if="!embedded" class="btn btn-secondary" @click="onClose">{{ $t('common.cancel') }}</button>
        <button class="btn btn-primary" @click="onSave" :disabled="adminStore.loading">
          {{ adminStore.loading ? $t('geteilt.settingsDialog.speichert') : $t('geteilt.settingsDialog.speichern') }}
        </button>
      </div>

      <div v-if="successMessage" class="success-banner">{{ successMessage }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import FehlerHinweis from './shared/FehlerHinweis.vue'
import { ref, watch, computed } from 'vue'
import { useAdminStore } from '../stores/admin'
import { useAiProviderStore } from '../stores/aiProvider'
import apiClient from '../api/client'
import { bearerToken } from '../api/auth-token'
import { t } from '../i18n'

// `only`: zeigt fokussiert nur eine Sektion (ohne Tab-Leiste) — für den
// Settings-Kachel-Hub (#731), wo jede Kachel genau eine Option öffnet.
const props = defineProps<{ open: boolean; embedded?: boolean; only?: string }>()
const emit = defineEmits<{ close: [] }>()

const adminStore = useAdminStore()
const aiProviderStore = useAiProviderStore()
const activeTab = ref<'ai' | 'modules' | 'backup' | 'github'>(
  (['ai', 'modules', 'backup', 'github'].includes(props.only || '')
    ? (props.only as any) : 'ai'))
const form = ref<any>(null)
const successMessage = ref('')

// Cloud-Modell-Auswahl: verfügbare Modelle vom Provider abrufen (GET /ai/models).
// Nutzt die GESPEICHERTE Config → ggf. erst speichern, dann abrufen.
const availableModels = ref<string[]>([])
const modelsLoading = ref(false)
const modelsMsg = ref('')

// #1409: Cloud-Anbieter-Presets — Auto-Konfiguration der Base-URL
const CLOUD_PRESETS: Record<string, string> = {
  anthropic: 'https://api.anthropic.com/v1',
  openai: 'https://api.openai.com/v1',
  google: 'https://generativelanguage.googleapis.com/v1beta/openai',
}
const cloudPreset = computed(() => {
  const url = String(form.value?.ai?.cloud?.base_url || '').toLowerCase()
  if (url.includes('anthropic.com')) return 'anthropic'
  if (url.includes('googleapis.com') || url.includes('generativelanguage')) return 'google'
  if (url.includes('api.openai.com')) return 'openai'
  return 'other'
})
function applyCloudPreset(preset: string) {
  if (!form.value?.ai?.cloud) return
  if (preset in CLOUD_PRESETS) form.value.ai.cloud.base_url = CLOUD_PRESETS[preset]
  else if (cloudPreset.value !== 'other') form.value.ai.cloud.base_url = ''
  availableModels.value = []  // Anbieterwechsel → Modell-Liste neu abrufen
  modelsMsg.value = ''
}
async function fetchModels() {
  modelsLoading.value = true
  modelsMsg.value = ''
  try {
    // #1406: aktuelle Formularwerte mitschicken → Dropdown bereits VOR dem Speichern
    // befüllen (nicht erst die gespeicherte Config).
    const c = form.value?.ai?.cloud || {}
    const payload = form.value?.ai?.provider === 'cloud'
      ? { provider: 'cloud', base_url: c.base_url, api_key: c.api_key, api_key_env: c.api_key_env, model: c.model }
      : { provider: 'on_prem', base_url: form.value?.ai?.on_prem?.base_url }
    const r = await apiClient.post('/ai/models', payload, { timeout: 25000 })
    availableModels.value = r.data?.models || []
    modelsMsg.value = availableModels.value.length
      ? `${availableModels.value.length} Modelle abgerufen — im Feld auswählen.`
      : (r.data?.error || t('geteilt.settingsDialog.keineModelleGefunden'))
  } catch (e: any) {
    modelsMsg.value = e?.response?.data?.error
      || t('geteilt.settingsDialog.modelleNichtAbrufbarBitteEinstellung')
  } finally {
    modelsLoading.value = false
  }
}

const tabs = [
  { id: 'ai' as const, label: t('geteilt.settingsDialog.kIProvider') },
  { id: 'github' as const, label: t('common.gitHub') },
  { id: 'modules' as const, label: t('common.module') },
  { id: 'backup' as const, label: t('geteilt.settingsDialog.backup') },
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
      error: t('geteilt.settingsDialog.keinModellKonfiguriertWahleObenEinMo'),
    }
    return
  }
  ollamaEcho.value = {
    shown: true, running: true, status: t('geteilt.settingsDialog.starte'), chunks: '',
    ttftMs: 0, tokensPerSec: 0, totalMs: 0, error: '',
  }
  const token = bearerToken()  // #1190: zentraler Token-Zugriff
  if (!token) {
    ollamaEcho.value.error = t('geteilt.settingsDialog.keinAuthTokenImSessionStorageBitteNe')
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
            ollamaEcho.value.status = t('geteilt.settingsDialog.echoTestErfolgreich')
            ollamaEcho.value.tokensPerSec = d.tokens_per_second || 0
            ollamaEcho.value.totalMs = d.total_duration_ms || 0
          } else {
            ollamaEcho.value.status = t('geteilt.settingsDialog.fehler')
            ollamaEcho.value.error = d.error || t('geteilt.settingsDialog.unbekannterFehler')
          }
        }
      }
    }
  } catch (e: any) {
    ollamaEcho.value.error = e?.message || t('geteilt.settingsDialog.streamFehler')
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
    ollamaModels.value.error = e?.response?.data?.error || e?.message || t('geteilt.settingsDialog.modellListeKonnteNichtGeladenWerden')
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
        detail: e?.message || t('geteilt.settingsDialog.fehlerBeimAufruf'),
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
  ollamaPull.value = { running: true, result: { status: t('geteilt.settingsDialog.starte') } }

  // Streaming-fetch (SSE) — nginx-Timeout & large-model-pull-friendly
  const token = bearerToken()  // #1190: zentraler Token-Zugriff
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
    ollamaPull.value.result = { ok: false, error: e?.message || t('geteilt.settingsDialog.pullFehlgeschlagen') }
  } finally {
    ollamaPull.value.running = false
  }
}

// #1712: Liste vollständig — WiBA fehlte, war also gar nicht
// ausblendbar. WiBA gehört zum Grundpreis (immer lizenziert), lässt sich hier
// aber wie jedes andere Modul aus der Oberfläche nehmen: Ausblenden ist eine
// Anzeige-Entscheidung, keine Lizenzfrage.
// 'firmen' ist das Master-Modul und bleibt immer sichtbar (sonst Lockout).
const webModules = [
  { id: 'firmen', label: t('nav.firmen.label'), tooltip: t('geteilt.settingsDialog.firmenverwaltungImmerSichtbar'), fix: true },
  { id: 'risikobewertung', label: t('nav.risikobewertung.label'), tooltip: 'Multi-Framework · im Grundpreis' },
  { id: 'wiba', label: t('nav.wiba.label'), tooltip: t('geteilt.settingsDialog.bSIWegInDieBasisAbsicherungImGrundpr') },
  { id: 'compliance-audit', label: t('nav.compliance-audit.label'),
    tooltip: t('geteilt.settingsDialog.standortbestimmungGegenEinFrameworkI') },
  { id: 'cra', label: t('nav.cra.label'), tooltip: t('common.cyberResilienceAct') },
  { id: 'nis2', label: 'NIS2', tooltip: 'NIS2-Richtlinie' },
  { id: 'aiact', label: 'AI Act', tooltip: 'EU AI Act' },
  { id: 'dsgvo', label: t('nav.dsgvo.label'), tooltip: 'GDPR / DSGVO' },
  { id: 'gutachten', label: t('nav.gutachten.label'), tooltip: t('geteilt.settingsDialog.expertOpinions') },
]

const isDisabled = (id: string): boolean => {
  return form.value?.modules?.disabled?.includes(id) ?? false
}

const toggleModule = (id: string) => {
  // #1712: 'firmen' ist das Master-Modul — ausblenden würde den Einstieg in
  // alle Mandanten nehmen.
  if (webModules.find(m => m.id === id)?.fix) return
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
    if (props.only && ['ai', 'modules', 'backup', 'github'].includes(props.only)) {
      activeTab.value = props.only as any
    }
    if (!adminStore.settings) await adminStore.fetchSettings()
    form.value = JSON.parse(JSON.stringify(adminStore.settings || {}))
    if (!form.value.ai) form.value.ai = { provider: 'on_prem', on_prem: {}, cloud: {} }
    if (!form.value.ai.on_prem) form.value.ai.on_prem = { base_url: '', model: '', timeout_s: 60 }
    if (!form.value.ai.cloud) form.value.ai.cloud = { allow_data_egress: false, redact: true, base_url: '', model: '', api_key_env: '', api_key: '' }
    if (!form.value.modules) form.value.modules = { order: [], disabled: [] }
    if (!form.value.backup) form.value.backup = { backup_on_exit: false, backup_retention_count: 5 }
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
      + t('geteilt.settingsDialog.fallsAutofillFeldLeerenTokenManuellA')
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
    successMessage.value = '⚠ ' + (errMsg || t('common.fehlerBeimSpeichern'))
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
    ghTestResult.value = { ok: false, error: e?.response?.data?.error || t('geteilt.settingsDialog.testFehlgeschlagen') }
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

/** #1827: Cloud ohne erlaubten Datenausgang gar nicht erst abschicken.
 *
 * Der Riegel im Backend bleibt (fail-closed), aber er gehört nicht an das Ende
 * der Strecke: Der Dialog lässt den Anwender den Provider auf „Cloud" stellen
 * und speichern, obwohl der Haken direkt darunter fehlt. Hier steht die
 * Meldung dort, wo sie etwas ändern kann — am Formular. */
const egressFehlt = computed(() =>
  form.value?.ai?.provider === 'cloud' && !form.value?.ai?.cloud?.allow_data_egress)

const onSave = async () => {
  if (egressFehlt.value) {
    adminStore.error = t('geteilt.settingsDialog.furDenCloudBetriebMussDerDatenausgan')
      + t('geteilt.settingsDialog.erlaubtSeinSetzenSieImAbschnittCloud')
      + t('geteilt.settingsDialog.erlaubenPflichtFurCloudOderWahlenSie')
      + t('geteilt.settingsDialog.kIProviderDabeiVerlassenDatenDenLoka')
    activeTab.value = 'ai'
    return
  }
  // #416: maskierte Werte aus dem Form-Object entfernen, sonst überschreiben
  // sie echte Tokens im Backend mit '***'.
  const cleaned = stripMaskedDeep(form.value)

  // #416 reopen: GitHub-Token aus separatem gh-State mit-übernehmen.
  // Sonst gehen Token verloren, wenn der User direkt den globalen Save klickt
  // statt den Tab-spezifischen "Speichern" in der GitHub-Tab.
  const pendingGhToken = (gh.value.token || '').trim()
  const ghChanged = pendingGhToken.length >= 20 || (
    !!gh.value.username && gh.value.username !== form.value?.integrations?.github?.username
  ) || (
    !!gh.value.default_repo && gh.value.default_repo !== form.value?.integrations?.github?.default_repo
  )
  if (ghChanged) {
    cleaned.integrations = cleaned.integrations || {}
    cleaned.integrations.github = cleaned.integrations.github || {}
    if (pendingGhToken.length >= 20) {
      cleaned.integrations.github.token = pendingGhToken
    }
    cleaned.integrations.github.username = gh.value.username || ''
    cleaned.integrations.github.default_repo = gh.value.default_repo || ''
  }

  const ok = await adminStore.saveSettings(cleaned)
  if (ok) {
    // #1342 Defekt A: KI-Provider-Badge ohne Reload aktualisieren, falls der
    // Provider/Egress-Status hier geändert wurde.
    aiProviderStore.loadStatus()
    if (pendingGhToken.length >= 20) {
      successMessage.value = `✓ Einstellungen gespeichert (inkl. GitHub-Token, ${pendingGhToken.length} Zeichen).`
      gh.value.token = ''  // Eingabefeld leeren
      await loadGithub()   // token_set neu laden
    } else {
      successMessage.value = '✓ Einstellungen gespeichert.'
    }
    setTimeout(() => emit('close'), 1500)
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

/* #1827: Voraussetzung, nicht Beiwerk — deshalb nicht im Grau der Hinweise. */
.hint-warn {
  color: #b26a00;
  font-weight: 600;
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
