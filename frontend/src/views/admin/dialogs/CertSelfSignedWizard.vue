<template>
  <div class="modal-overlay" @mousedown.self="close">
    <div class="modal">
      <header class="modal-head">
        <h3>{{ $t('admin.certSelfSignedWizard.selfSignedZertifikatErstellenV0', { v0: step }) }}</h3>
        <button class="x" @click="close">✕</button>
      </header>

      <div class="modal-body">
        <!-- Step 1: Eingaben -->
        <div v-if="step === 1">
          <p class="muted">{{ $t('admin.certSelfSignedWizard.furHostnameUndOderIPDiesesZertifikat') }}</p>
          <div class="row">
            <label>{{ $t('admin.certSelfSignedWizard.hostnameOderIPCN') }}</label>
            <input v-model="cn" :placeholder="$t('admin.certSelfSignedWizard.zBAicsInternLocalOder')" />
          </div>
          <div class="row">
            <label>{{ $t('admin.certSelfSignedWizard.weitereNamenIPsSANEineProZeile') }}</label>
            <textarea v-model="sansText" rows="4"
                      placeholder="www.aics.intern.local&#10;aics.example.com"></textarea>
            <button class="btn-mini" @click="loadSuggest" :disabled="busy">{{ $t('admin.certSelfSignedWizard.vorschlagLaden') }}</button>
          </div>
          <div class="row two">
            <div>
              <label>{{ $t('admin.certSelfSignedWizard.gultigkeitTage') }}</label>
              <input type="number" v-model.number="validity" min="1" max="3650" />
            </div>
            <div>
              <label>{{ $t('admin.certSelfSignedWizard.schlussellange') }}</label>
              <select v-model.number="keySize">
                <option :value="2048">2048</option>
                <option :value="3072">3072</option>
                <option :value="4096">4096</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Step 2: Erzeugt -->
        <div v-if="step === 2 && result">
          <div class="ok-box">{{ $t('admin.certSelfSignedWizard.zertifikatErzeugt') }}</div>
          <ul class="info">
            <li><strong>CN:</strong> {{ result.info.common_name }}</li>
            <li><strong>{{ $t('admin.certSelfSignedWizard.sANs') }}</strong> {{ (result.info.sans || []).join(', ') }}</li>
            <li><strong>{{ $t('admin.certSelfSignedWizard.gultigBis') }}</strong> {{ (result.info.not_after || '').slice(0,10) }}</li>
            <li><strong>SHA-256:</strong> <code class="fp">{{ result.info.sha256_fingerprint }}</code></li>
          </ul>
          <div class="dl-row">
            <button class="btn-secondary" @click="download('certificate.crt', result.cert_pem)">{{ $t('admin.certSelfSignedWizard.zertifikatCrt') }}</button>
            <button class="btn-secondary" @click="download('private.key', result.key_pem)">{{ $t('admin.certSelfSignedWizard.schlusselKey') }}</button>
          </div>
          <p class="hint">{{ $t('admin.certSelfSignedWizard.importiereDie') }} <strong>.crt</strong> {{ $t('admin.certSelfSignedWizard.inDenVertrauensspeicherDeinesBetrieb') }}</p>
        </div>

        <!-- Step 3: Anwenden -->
        <div v-if="step === 3">
          <p class="muted">{{ $t('admin.certSelfSignedWizard.optionalDasErzeugteZertifikatDirektA') }}</p>
          <div v-if="!applyResult">
            <button class="btn-primary" @click="apply" :disabled="busy">
              {{ busy ? $t('admin.certSelfSignedWizard.wendeAn') : $t('admin.certSelfSignedWizard.aufServerAnwenden') }}
            </button>
          </div>
          <div v-else class="ok-box">
            {{ $t('admin.certSelfSignedWizard.angewendetV0', { v0: applyResult.cert_dir }) }}<br>
            <span v-if="applyResult.reloaded">{{ $t('admin.certSelfSignedWizard.nginxNeuGeladen') }}</span>
            <span v-else>{{ applyResult.note }}</span>
          </div>
        </div>

        <div v-if="error" class="err">⚠ {{ error }}</div>
      </div>

      <footer class="modal-foot">
        <button class="btn-secondary" @click="close">{{ $t('common.close') }}</button>
        <button v-if="step > 1" class="btn-secondary" @click="step--">{{ $t('common.zuruck2') }}</button>
        <button v-if="step === 1" class="btn-primary" @click="generate" :disabled="busy || !cn">
          {{ busy ? $t('admin.certSelfSignedWizard.erzeuge') : $t('admin.certSelfSignedWizard.erzeugen') }}
        </button>
        <button v-if="step === 2" class="btn-primary" @click="step = 3">{{ $t('common.weiter2') }}</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { t } from '../../../i18n'

const emit = defineEmits(['close', 'applied'])

const step = ref(1)
const busy = ref(false)
const error = ref('')
const cn = ref('')
const sansText = ref('')
const validity = ref(825)
const keySize = ref(2048)
const result = ref<any>(null)
const applyResult = ref<any>(null)

const close = () => emit('close')

const sansList = () => sansText.value.split(/[\n,]/).map(s => s.trim()).filter(Boolean)

const loadSuggest = async () => {
  busy.value = true; error.value = ''
  try {
    const r = await axios.get('/api/admin/certificates/suggest')
    const hosts = r.data.hostnames || []
    const ips = r.data.ip_addresses || []
    if (!cn.value && (hosts[0] || ips[0])) cn.value = hosts[0] || ips[0]
    const extra = [...hosts, ...ips].filter(x => x !== cn.value)
    sansText.value = Array.from(new Set([...sansList(), ...extra])).join('\n')
  } catch (e: any) {
    error.value = e?.response?.data?.error || t('admin.certSelfSignedWizard.vorschlagKonnteNichtGeladenWerden')
  } finally { busy.value = false }
}

const generate = async () => {
  busy.value = true; error.value = ''
  try {
    const r = await axios.post('/api/admin/certificates/self-signed/generate', {
      common_name: cn.value, sans: sansList(),
      validity_days: validity.value, key_size: keySize.value,
    })
    result.value = r.data
    step.value = 2
  } catch (e: any) {
    error.value = e?.response?.data?.error || t('admin.certSelfSignedWizard.erzeugungFehlgeschlagen')
  } finally { busy.value = false }
}

const apply = async () => {
  busy.value = true; error.value = ''
  try {
    const r = await axios.post('/api/admin/certificates/apply', {
      cert_pem: result.value.cert_pem, key_pem: result.value.key_pem,
    })
    applyResult.value = r.data
    emit('applied')
  } catch (e: any) {
    error.value = e?.response?.data?.error || t('common.anwendenFehlgeschlagen')
  } finally { busy.value = false }
}

const download = (filename: string, content: string) => {
  const blob = new Blob([content], { type: 'application/x-pem-file' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex;
  align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 10px; width: min(620px, 94vw); max-height: 90vh;
  display: flex; flex-direction: column; }
.modal-head { display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #e0e0e0; }
.modal-head h3 { margin: 0; font-size: 17px; }
.x { background: none; border: none; font-size: 18px; cursor: pointer; }
.modal-body { padding: 18px 20px; overflow: auto; }
.modal-foot { display: flex; gap: 8px; justify-content: flex-end; padding: 14px 20px;
  border-top: 1px solid #e0e0e0; }
.row { margin-bottom: 14px; }
.row.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.row input, .row select, .row textarea { width: 100%; padding: 8px 10px;
  border: 1px solid #d0d0d0; border-radius: 6px; font-size: 14px; font-family: inherit; }
.muted { color: #666; font-size: 13px; margin: 0 0 12px; }
.hint { color: #666; font-size: 12px; margin-top: 10px; }
.btn-mini { margin-top: 6px; font-size: 12px; padding: 4px 10px; border: 1px solid #d0d0d0;
  border-radius: 6px; background: #f7f7f7; cursor: pointer; }
.btn-primary { padding: 9px 16px; background: #1565c0; color: #fff; border: none;
  border-radius: 7px; cursor: pointer; font-size: 14px; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-secondary { padding: 9px 16px; background: #f2f2f2; border: 1px solid #d8d8d8;
  border-radius: 7px; cursor: pointer; font-size: 14px; }
.ok-box { background: #e8f5e9; color: #2e7d32; padding: 10px 12px; border-radius: 6px;
  margin-bottom: 12px; }
.info { list-style: none; padding: 0; margin: 0 0 12px; font-size: 13px; }
.info li { padding: 3px 0; }
.fp { font-size: 11px; word-break: break-all; }
.dl-row { display: flex; gap: 8px; flex-wrap: wrap; }
.err { color: #c62828; font-size: 13px; margin-top: 10px; }
</style>
