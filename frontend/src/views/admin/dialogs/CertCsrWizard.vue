<template>
  <div class="modal-overlay" @mousedown.self="close">
    <div class="modal">
      <header class="modal-head">
        <h3>{{ $t('admin.certCsrWizard.zertifikatsantragCSRFurPKIV0', { v0: step }) }}</h3>
        <button class="x" @click="close">✕</button>
      </header>

      <div class="modal-body">
        <!-- Step 1: Antragsdaten -->
        <div v-if="step === 1">
          <p class="muted">{{ $t('admin.certCsrWizard.erzeugtSchlusselpaarCSRPKCSZurEinrei') }}</p>
          <div class="row">
            <label>{{ $t('admin.certCsrWizard.hostnameIPCN') }}</label>
            <input v-model="cn" placeholder="z.B. aics.example.com" />
            <button class="btn-mini" @click="loadSuggest" :disabled="busy">{{ $t('admin.certCsrWizard.vorschlagLaden') }}</button>
          </div>
          <div class="row">
            <label>{{ $t('admin.certCsrWizard.weitereNamenIPsSANEineProZeile') }}</label>
            <textarea v-model="sansText" rows="3"></textarea>
          </div>
          <div class="row three">
            <div><label>{{ $t('admin.certCsrWizard.organisationO') }}</label><input v-model="org" /></div>
            <div><label>{{ $t('admin.certCsrWizard.abteilungOU') }}</label><input v-model="ou" /></div>
            <div><label>{{ $t('admin.certCsrWizard.landC') }}</label><input v-model="country" maxlength="2" placeholder="DE" /></div>
          </div>
          <div class="row three">
            <div><label>{{ $t('admin.certCsrWizard.bundeslandST') }}</label><input v-model="state" /></div>
            <div><label>{{ $t('admin.certCsrWizard.ortL') }}</label><input v-model="locality" /></div>
            <div>
              <label>{{ $t('admin.certCsrWizard.schlussellange') }}</label>
              <select v-model.number="keySize">
                <option :value="2048">2048</option>
                <option :value="3072">3072</option>
                <option :value="4096">4096</option>
              </select>
            </div>
          </div>
          <div class="row"><label>{{ $t('auth.email') }}</label><input v-model="email" /></div>
        </div>

        <!-- Step 2: CSR erzeugt -->
        <div v-if="step === 2 && result">
          <div class="ok-box">{{ $t('admin.certCsrWizard.cSRErzeugtIDV0', { v0: result.csr_id }) }}</div>
          <ul class="info">
            <li><strong>CN:</strong> {{ result.info.common_name }}</li>
            <li><strong>{{ $t('admin.certCsrWizard.sANs') }}</strong> {{ (result.info.sans || []).join(', ') }}</li>
          </ul>
          <div class="dl-row">
            <button class="btn-secondary" @click="download('request.csr', result.csr_pem)">{{ $t('admin.certCsrWizard.cSRCsrBeiPKIEinreichen') }}</button>
            <button class="btn-secondary" @click="download('request.key', result.key_pem)">{{ $t('admin.certCsrWizard.schlusselKeySicherAufbewahren') }}</button>
          </div>
          <p class="hint">{{ $t('admin.certCsrWizard.reicheDie') }} <strong>.csr</strong> {{ $t('admin.certCsrWizard.beiEurerPKIEinSobaldDasSignierteZert') }}</p>
        </div>

        <!-- Step 3: Signiertes Cert importieren -->
        <div v-if="step === 3">
          <p class="muted">{{ $t('admin.certCsrWizard.vonDerPKISigniertesZertifikatPEMEinf') }}</p>
          <div class="row">
            <label>{{ $t('admin.certCsrWizard.signiertesZertifikatPEM') }}</label>
            <textarea v-model="signedPem" rows="7"
                      :placeholder="$t('admin.certCsrWizard.bEGINCERTIFICATEENDCERTIFICATE')"></textarea>
          </div>
          <button class="btn-primary" @click="importSigned" :disabled="busy || !signedPem">
            {{ busy ? $t('admin.certCsrWizard.prufe') : $t('admin.certCsrWizard.prufenImportieren') }}
          </button>
          <div v-if="importResult" class="ok-box" style="margin-top:12px;">
            {{ $t('admin.certCsrWizard.passtZumSchlusselGultigBisV0', { v0: (importResult.info.not_after || '').slice(0,10) }) }}
            <div style="margin-top:8px;">
              <button class="btn-primary" @click="applyImported" :disabled="busy">
                {{ $t('admin.certCsrWizard.aufServerAnwenden') }}
              </button>
            </div>
          </div>
          <div v-if="applyResult" class="ok-box" style="margin-top:12px;">
            {{ $t('admin.certCsrWizard.angewendetV0', { v0: applyResult.cert_dir }) }}
            <span v-if="applyResult.reloaded">{{ $t('admin.certCsrWizard.nginxNeuGeladen') }}</span>
            <span v-else>{{ applyResult.note }}</span>
          </div>
        </div>

        <div v-if="error" class="err">⚠ {{ error }}</div>
      </div>

      <footer class="modal-foot">
        <button class="btn-secondary" @click="close">{{ $t('common.close') }}</button>
        <button v-if="step > 1 && !applyResult" class="btn-secondary" @click="step--">{{ $t('common.zuruck2') }}</button>
        <button v-if="step === 1" class="btn-primary" @click="generate" :disabled="busy || !cn">
          {{ busy ? $t('admin.certCsrWizard.erzeuge') : $t('admin.certCsrWizard.cSRErzeugen') }}
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
const org = ref('')
const ou = ref('')
const country = ref('')
const state = ref('')
const locality = ref('')
const email = ref('')
const keySize = ref(2048)
const result = ref<any>(null)
const signedPem = ref('')
const importResult = ref<any>(null)
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
    sansText.value = Array.from(new Set([...sansList(), ...hosts, ...ips].filter(x => x && x !== cn.value))).join('\n')
  } catch (e: any) {
    error.value = e?.response?.data?.error || t('admin.certCsrWizard.vorschlagKonnteNichtGeladenWerden')
  } finally { busy.value = false }
}

const generate = async () => {
  busy.value = true; error.value = ''
  try {
    const r = await axios.post('/api/admin/certificates/csr/generate', {
      common_name: cn.value, sans: sansList(), key_size: keySize.value,
      organization: org.value, organizational_unit: ou.value, country: country.value,
      state: state.value, locality: locality.value, email: email.value,
    })
    result.value = r.data
    step.value = 2
  } catch (e: any) {
    error.value = e?.response?.data?.error || t('admin.certCsrWizard.cSRErzeugungFehlgeschlagen')
  } finally { busy.value = false }
}

const importSigned = async () => {
  busy.value = true; error.value = ''; importResult.value = null
  try {
    const r = await axios.post('/api/admin/certificates/csr/import-signed', {
      cert_pem: signedPem.value, csr_id: result.value?.csr_id,
    })
    importResult.value = r.data
  } catch (e: any) {
    error.value = e?.response?.data?.error || t('admin.certCsrWizard.importFehlgeschlagen')
  } finally { busy.value = false }
}

const applyImported = async () => {
  busy.value = true; error.value = ''
  try {
    // #742: privater Schlüssel bleibt serverseitig im Store; Anwenden per store_id.
    const r = await axios.post(`/api/admin/certificates/store/${importResult.value.store_id}/apply`, {})
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
.modal { background: #fff; border-radius: 10px; width: min(680px, 94vw); max-height: 90vh;
  display: flex; flex-direction: column; }
.modal-head { display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #e0e0e0; }
.modal-head h3 { margin: 0; font-size: 17px; }
.x { background: none; border: none; font-size: 18px; cursor: pointer; }
.modal-body { padding: 18px 20px; overflow: auto; }
.modal-foot { display: flex; gap: 8px; justify-content: flex-end; padding: 14px 20px;
  border-top: 1px solid #e0e0e0; }
.row { margin-bottom: 14px; }
.row.three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
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
.ok-box { background: #e8f5e9; color: #2e7d32; padding: 10px 12px; border-radius: 6px; }
.info { list-style: none; padding: 0; margin: 0 0 12px; font-size: 13px; }
.info li { padding: 3px 0; }
.dl-row { display: flex; gap: 8px; flex-wrap: wrap; }
.err { color: #c62828; font-size: 13px; margin-top: 10px; }
</style>
