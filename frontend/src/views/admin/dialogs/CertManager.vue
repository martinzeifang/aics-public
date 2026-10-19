<template>
  <div class="modal-overlay" @mousedown.self="close">
    <div class="modal">
      <header class="modal-head">
        <h3>🗂 Zertifikatsmanager</h3>
        <button class="x" @click="close">✕</button>
      </header>

      <div class="modal-body">
        <p class="muted">Alle gespeicherten Zertifikate. Wähle eines aus, um es als aktives
          TLS-Zertifikat anzuwenden.</p>

        <div v-if="loading" class="muted">Lade…</div>
        <div v-else-if="certs.length === 0" class="empty">
          Noch keine Zertifikate. Erzeuge eines über „Self-Signed-Zertifikat" oder „CSR".
        </div>

        <table v-else class="tbl">
          <thead>
            <tr><th></th><th>Bezeichnung / CN</th><th>SANs</th><th>Gültig bis</th><th>Quelle</th><th>Aktionen</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in certs" :key="c.id" :class="{ active: c.active }">
              <td>
                <span v-if="c.active" class="badge-active">● aktiv</span>
              </td>
              <td>
                <strong>{{ c.label || c.common_name }}</strong>
                <div class="fp">{{ (c.sha256_fingerprint || '').slice(0, 24) }}…</div>
              </td>
              <td class="sans">{{ (c.sans || []).join(', ') || '—' }}</td>
              <td>{{ (c.not_after || '').slice(0, 10) }}</td>
              <td><span class="src">{{ sourceLabel(c.source) }}</span></td>
              <td class="actions">
                <button class="btn-mini" :disabled="c.active || busyId === c.id" @click="applyCert(c)">
                  {{ busyId === c.id ? '…' : 'Anwenden' }}
                </button>
                <button class="btn-mini" @click="downloadCert(c)">⬇</button>
                <button class="btn-mini danger" :disabled="c.active" @click="deleteCert(c)">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="msg" class="ok-box">{{ msg }}</div>
        <div v-if="error" class="err">⚠ {{ error }}</div>
      </div>

      <footer class="modal-foot">
        <button class="btn-secondary" @click="reload" :disabled="loading">↻ Aktualisieren</button>
        <button class="btn-secondary" @click="close">Schließen</button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const emit = defineEmits(['close', 'applied'])

const certs = ref<any[]>([])
const loading = ref(true)
const busyId = ref('')
const msg = ref('')
const error = ref('')

const close = () => emit('close')

const sourceLabel = (s: string) => ({
  'self-signed': 'Self-Signed', 'csr-signed': 'PKI-signiert', 'imported': 'Importiert',
}[s] || s)

const reload = async () => {
  loading.value = true; error.value = ''
  try {
    const r = await axios.get('/api/admin/certificates/store')
    certs.value = r.data.certificates || []
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Laden fehlgeschlagen'
  } finally { loading.value = false }
}

const applyCert = async (c: any) => {
  busyId.value = c.id; error.value = ''; msg.value = ''
  try {
    const r = await axios.post(`/api/admin/certificates/store/${c.id}/apply`)
    msg.value = r.data.reloaded
      ? `„${c.label}" angewendet, nginx neu geladen.`
      : `„${c.label}" angewendet. ${r.data.note || ''}`
    await reload()
    emit('applied')
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Anwenden fehlgeschlagen'
  } finally { busyId.value = '' }
}

const deleteCert = async (c: any) => {
  if (!window.confirm(`Zertifikat „${c.label}" löschen?`)) return
  error.value = ''; msg.value = ''
  try {
    await axios.delete(`/api/admin/certificates/store/${c.id}`)
    await reload()
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Löschen fehlgeschlagen'
  }
}

const downloadCert = async (c: any) => {
  try {
    const r = await axios.get(`/api/admin/certificates/store/${c.id}/download`)
    const blob = new Blob([r.data.cert_pem], { type: 'application/x-pem-file' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${(c.label || c.common_name || 'cert').replace(/[^\w.-]/g, '_')}.crt`; a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Download fehlgeschlagen'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex;
  align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 10px; width: min(820px, 96vw); max-height: 90vh;
  display: flex; flex-direction: column; }
.modal-head { display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #e0e0e0; }
.modal-head h3 { margin: 0; font-size: 17px; }
.x { background: none; border: none; font-size: 18px; cursor: pointer; }
.modal-body { padding: 18px 20px; overflow: auto; }
.modal-foot { display: flex; gap: 8px; justify-content: flex-end; padding: 14px 20px;
  border-top: 1px solid #e0e0e0; }
.muted { color: #666; font-size: 13px; margin: 0 0 12px; }
.empty { color: #666; padding: 20px; text-align: center; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; vertical-align: top; }
.tbl tr.active { background: #f1f8e9; }
.badge-active { color: #2e7d32; font-weight: 600; font-size: 12px; white-space: nowrap; }
.fp { color: #999; font-size: 11px; font-family: monospace; }
.sans { max-width: 220px; word-break: break-word; }
.src { font-size: 12px; background: #eef2f7; color: #555; padding: 2px 8px; border-radius: 999px; }
.actions { white-space: nowrap; }
.btn-mini { font-size: 12px; padding: 4px 9px; border: 1px solid #d0d0d0; border-radius: 6px;
  background: #f7f7f7; cursor: pointer; margin-right: 4px; }
.btn-mini:disabled { opacity: .5; cursor: not-allowed; }
.btn-mini.danger { color: #c62828; border-color: #ffcdd2; }
.btn-secondary { padding: 9px 16px; background: #f2f2f2; border: 1px solid #d8d8d8;
  border-radius: 7px; cursor: pointer; font-size: 14px; }
.ok-box { background: #e8f5e9; color: #2e7d32; padding: 10px 12px; border-radius: 6px; margin-top: 12px; }
.err { color: #c62828; font-size: 13px; margin-top: 10px; }
</style>
