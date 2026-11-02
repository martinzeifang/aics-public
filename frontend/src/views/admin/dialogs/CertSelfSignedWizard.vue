<template>
  <div class="modal-overlay" @mousedown.self="close">
    <div class="modal">
      <header class="modal-head">
        <h3>🔐 Self-Signed-Zertifikat erstellen ({{ step }}/3)</h3>
        <button class="x" @click="close">✕</button>
      </header>

      <div class="modal-body">
        <!-- Step 1: Eingaben -->
        <div v-if="step === 1">
          <p class="muted">Für Hostname und/oder IP. Dieses Zertifikat importierst du
            anschließend in deinen Vertrauensspeicher.</p>
          <div class="row">
            <label>Hostname oder IP (CN) *</label>
            <input v-model="cn" placeholder="z.B. aics.intern.local oder aics.example.com" />
          </div>
          <div class="row">
            <label>Weitere Namen / IPs (SAN) — eine pro Zeile</label>
            <textarea v-model="sansText" rows="4"
                      placeholder="www.aics.intern.local&#10;aics.example.com"></textarea>
            <button class="btn-mini" @click="loadSuggest" :disabled="busy">🔎 Vorschlag laden</button>
          </div>
          <div class="row two">
            <div>
              <label>Gültigkeit (Tage)</label>
              <input type="number" v-model.number="validity" min="1" max="3650" />
            </div>
            <div>
              <label>Schlüssellänge</label>
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
          <div class="ok-box">✓ Zertifikat erzeugt.</div>
          <ul class="info">
            <li><strong>CN:</strong> {{ result.info.common_name }}</li>
            <li><strong>SANs:</strong> {{ (result.info.sans || []).join(', ') }}</li>
            <li><strong>Gültig bis:</strong> {{ (result.info.not_after || '').slice(0,10) }}</li>
            <li><strong>SHA-256:</strong> <code class="fp">{{ result.info.sha256_fingerprint }}</code></li>
          </ul>
          <div class="dl-row">
            <button class="btn-secondary" @click="download('certificate.crt', result.cert_pem)">⬇ Zertifikat (.crt)</button>
            <button class="btn-secondary" @click="download('private.key', result.key_pem)">⬇ Schlüssel (.key)</button>
          </div>
          <p class="hint">Importiere die <strong>.crt</strong> in den Vertrauensspeicher deines
            Betriebssystems/Browsers, damit der Server als vertrauenswürdig gilt.</p>
        </div>

        <!-- Step 3: Anwenden -->
        <div v-if="step === 3">
          <p class="muted">Optional: das erzeugte Zertifikat direkt als aktives TLS-Zertifikat
            des Servers setzen.</p>
          <div v-if="!applyResult">
            <button class="btn-primary" @click="apply" :disabled="busy">
              {{ busy ? 'Wende an…' : '✓ Auf Server anwenden' }}
            </button>
          </div>
          <div v-else class="ok-box">
            ✓ Angewendet ({{ applyResult.cert_dir }}).<br>
            <span v-if="applyResult.reloaded">nginx neu geladen.</span>
            <span v-else>{{ applyResult.note }}</span>
          </div>
        </div>

        <div v-if="error" class="err">⚠ {{ error }}</div>
      </div>

      <footer class="modal-foot">
        <button class="btn-secondary" @click="close">Schließen</button>
        <button v-if="step > 1" class="btn-secondary" @click="step--">⟵ Zurück</button>
        <button v-if="step === 1" class="btn-primary" @click="generate" :disabled="busy || !cn">
          {{ busy ? 'Erzeuge…' : 'Erzeugen ⟶' }}
        </button>
        <button v-if="step === 2" class="btn-primary" @click="step = 3">Weiter ⟶</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'

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
    error.value = e?.response?.data?.error || 'Vorschlag konnte nicht geladen werden'
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
    error.value = e?.response?.data?.error || 'Erzeugung fehlgeschlagen'
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
    error.value = e?.response?.data?.error || 'Anwenden fehlgeschlagen'
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
