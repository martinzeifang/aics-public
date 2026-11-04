<template>
  <div class="security-view">
    <!-- #1183: Step-up-Re-Auth für sensible Account-Security-Aktionen -->
    <div v-if="reauth.open" class="reauth-overlay" @mousedown.self="cancelReauth">
      <div class="reauth-modal">
        <h3>🔐 Bestätigung erforderlich</h3>
        <p>Aus Sicherheitsgründen bitte erneut bestätigen — mit aktuellem Passwort
          <em>oder</em> einem TOTP-Code.</p>
        <label>Aktuelles Passwort
          <input type="password" v-model="reauth.password" autocomplete="current-password"
                 @keyup.enter="submitReauth" />
        </label>
        <label>oder TOTP-Code
          <input type="text" inputmode="numeric" maxlength="6" v-model="reauth.code"
                 placeholder="123456" @keyup.enter="submitReauth" />
        </label>
        <p v-if="reauth.error" class="reauth-error">{{ reauth.error }}</p>
        <div class="reauth-actions">
          <button class="btn btn-secondary" @click="cancelReauth">Abbrechen</button>
          <button class="btn btn-primary" :disabled="!reauth.password && !reauth.code"
                  @click="submitReauth">Bestätigen</button>
        </div>
      </div>
    </div>

    <div class="page-header">
      <h1>🔐 Sicherheit</h1>
      <p>Verwalten Sie Ihre Mehr-Faktor-Authentifizierung (MFA). Es stehen zwei Methoden zur
        Verfügung — Sie können eine oder beide aktivieren:
        <strong>Authenticator-App (TOTP)</strong> und <strong>Passkeys</strong>.</p>
    </div>

    <div v-if="mfaSetupRequired" class="mfa-enforce-banner">
      ⚠ Ihre Organisation verlangt MFA. Bitte richten Sie jetzt eine Methode ein
      (TOTP oder Passkey), um fortzufahren.
    </div>
    <div v-else-if="mfaRecommended" class="mfa-recommend-banner">
      ℹ Ihre Organisation empfiehlt MFA{{ mfaGraceText }}. Richten Sie jetzt eine Methode ein.
    </div>

    <section class="card">
      <header class="card-header">
        <div>
          <h2>Zwei-Faktor-Authentifizierung (TOTP)</h2>
          <p class="muted">
            Erhöht die Sicherheit Ihres Kontos: Nach dem Passwort wird zusätzlich ein
            6-stelliger Code aus einer Authenticator-App (z.B. Google Authenticator,
            Authy, 1Password) verlangt.
          </p>
        </div>
        <span class="status-pill" :class="{ enabled: status.enabled, disabled: !status.enabled }">
          {{ status.enabled ? '● Aktiviert' : '○ Deaktiviert' }}
        </span>
      </header>

      <div v-if="loading" class="info">Lade Status…</div>

      <!-- AKTIVIERT: Status + Backup-Codes verwalten + Deaktivieren -->
      <div v-else-if="status.enabled && !disableMode && !regenMode" class="card-body">
        <div class="info-row">
          <span class="info-label">Backup-Codes verfügbar:</span>
          <strong>{{ status.backup_codes_remaining }} / 10</strong>
        </div>
        <p v-if="status.backup_codes_remaining <= 2" class="warn">
          ⚠ Sie haben nur noch wenige Backup-Codes. Erzeugen Sie neue, bevor Sie keine mehr haben.
        </p>

        <div class="btn-row">
          <button class="btn btn-secondary" @click="regenMode = true">
            Neue Backup-Codes erzeugen
          </button>
          <button class="btn btn-danger" @click="disableMode = true">
            2FA deaktivieren
          </button>
        </div>
      </div>

      <!-- SETUP-FLOW: QR + Code-Verifikation -->
      <div v-else-if="!status.enabled && !setupData" class="card-body">
        <p>Aktivieren Sie 2FA, um Ihr Konto zusätzlich abzusichern.</p>
        <button class="btn btn-primary" @click="startSetup" :disabled="busy">
          {{ busy ? '…' : '2FA einrichten' }}
        </button>
      </div>

      <div v-else-if="setupData && !setupVerifiedCodes" class="setup-flow">
        <ol class="steps">
          <li>
            <strong>Authenticator-App öffnen</strong> (Google Authenticator, Authy, 1Password, …)
            und neuen Eintrag hinzufügen.
          </li>
          <li>
            <strong>QR-Code scannen</strong> oder Secret manuell eingeben:
            <div class="qr-row">
              <img :src="setupData.qr_code_data_url" alt="QR-Code" class="qr-img" />
              <div class="qr-side">
                <div class="secret-label">Secret (manuell):</div>
                <code class="secret-code">{{ setupData.secret }}</code>
                <button class="btn-tiny" @click="copySecret">📋 Kopieren</button>
              </div>
            </div>
          </li>
          <li>
            <strong>Bestätigung-Code</strong> aus der App eingeben:
            <div class="verify-row">
              <input
                v-model="verifyCode"
                type="text"
                inputmode="numeric"
                pattern="[0-9]{6}"
                maxlength="6"
                placeholder="123456"
                class="code-input"
                @keyup.enter="verifySetup"
              />
              <button class="btn btn-primary" @click="verifySetup" :disabled="busy || verifyCode.length !== 6">
                Bestätigen
              </button>
            </div>
            <div v-if="setupError" class="error">⚠ {{ setupError }}</div>
          </li>
        </ol>
        <button class="btn-link" @click="cancelSetup">Abbrechen</button>
      </div>

      <!-- BACKUP-CODES ANZEIGEN (einmalig nach setup oder regen) -->
      <div v-else-if="setupVerifiedCodes" class="backup-codes-box">
        <h3>🎉 2FA wurde aktiviert</h3>
        <p class="warn">
          ⚠ Bewahren Sie diese Backup-Codes sicher auf — sie werden nur <strong>einmal</strong>
          angezeigt und können verwendet werden, wenn Sie keinen Zugriff auf Ihre Authenticator-App
          haben. Jeder Code ist nur einmal gültig.
        </p>
        <ul class="codes-grid">
          <li v-for="c in setupVerifiedCodes" :key="c"><code>{{ c }}</code></li>
        </ul>
        <div class="btn-row">
          <button class="btn btn-secondary" @click="copyCodes">📋 Alle kopieren</button>
          <button class="btn btn-secondary" @click="downloadCodes">⬇ Als Datei speichern</button>
          <button class="btn btn-primary" @click="finishSetup">Verstanden, ich habe die Codes gesichert</button>
        </div>
      </div>

      <!-- DISABLE-FORM -->
      <div v-if="disableMode" class="disable-form">
        <h3>2FA deaktivieren</h3>
        <p>Bitte bestätigen Sie mit Ihrem Passwort und einem aktuellen Authenticator-Code.</p>
        <label class="field">
          <span>Passwort</span>
          <input v-model="disablePassword" type="password" autocomplete="current-password" />
        </label>
        <label class="field">
          <span>Aktueller Code (oder Backup-Code)</span>
          <input v-model="disableCode" type="text" inputmode="numeric" placeholder="123456 / XXXX-XXXX" />
        </label>
        <div v-if="disableError" class="error">⚠ {{ disableError }}</div>
        <div class="btn-row">
          <button class="btn btn-secondary" @click="cancelDisable">Abbrechen</button>
          <button class="btn btn-danger" @click="confirmDisable" :disabled="busy">
            {{ busy ? '…' : '2FA deaktivieren' }}
          </button>
        </div>
      </div>

      <!-- REGEN BACKUP CODES -->
      <div v-if="regenMode" class="disable-form">
        <h3>Neue Backup-Codes erzeugen</h3>
        <p class="warn">
          ⚠ Die alten Codes werden ungültig. Bestätigen Sie mit einem aktuellen Code.
        </p>
        <label class="field">
          <span>Aktueller Code</span>
          <input v-model="regenCode" type="text" inputmode="numeric" maxlength="6" placeholder="123456" />
        </label>
        <div v-if="regenError" class="error">⚠ {{ regenError }}</div>
        <div class="btn-row">
          <button class="btn btn-secondary" @click="regenMode = false; regenCode = ''; regenError = ''">Abbrechen</button>
          <button class="btn btn-primary" @click="confirmRegen" :disabled="busy">
            {{ busy ? '…' : 'Neue Codes erzeugen' }}
          </button>
        </div>
      </div>
    </section>

    <!-- ============ PASSKEYS (WebAuthn / FIDO2) — Sprint ε ============ -->
    <section class="card" style="margin-top: 24px;">
      <header class="card-header">
        <div>
          <h2>Passkeys (WebAuthn / FIDO2)</h2>
          <p class="muted">
            Melden Sie sich passwortlos und phishing-resistent an — per Fingerabdruck,
            Gesichtserkennung, Geräte-PIN oder Sicherheitsschlüssel. Ein Passkey kann
            das Passwort vollständig ersetzen oder als zweiter Faktor dienen.
          </p>
        </div>
        <span class="status-pill" :class="{ enabled: passkeys.length > 0, disabled: passkeys.length === 0 }">
          {{ passkeys.length > 0 ? `● ${passkeys.length} aktiv` : '○ Keine' }}
        </span>
      </header>

      <div v-if="!passkeySupported" class="warn">
        ⚠ Dieser Browser unterstützt keine Passkeys (WebAuthn). Bitte nutzen Sie einen aktuellen
        Browser über eine HTTPS-Verbindung.
      </div>

      <div v-else class="card-body">
        <div v-if="pkLoading" class="info">Lade Passkeys…</div>

        <ul v-else-if="passkeys.length" class="passkey-list">
          <li v-for="pk in passkeys" :key="pk.id" class="passkey-item">
            <div class="pk-info">
              <span class="pk-icon">🔑</span>
              <div>
                <template v-if="renameId === pk.id">
                  <input v-model="renameValue" class="pk-rename-input" @keyup.enter="confirmRename(pk.id)" />
                </template>
                <strong v-else>{{ pk.nickname }}</strong>
                <div class="pk-meta">
                  Hinzugefügt {{ formatDate(pk.created_at) }}
                  <span v-if="pk.last_used_at"> · zuletzt genutzt {{ formatDate(pk.last_used_at) }}</span>
                  <span v-if="pk.backup_state" class="pk-badge">synchronisiert</span>
                </div>
              </div>
            </div>
            <div class="pk-actions">
              <template v-if="renameId === pk.id">
                <button class="btn-tiny" @click="confirmRename(pk.id)">✓ Speichern</button>
                <button class="btn-tiny" @click="renameId = null">Abbrechen</button>
              </template>
              <template v-else>
                <button class="btn-tiny" @click="startRename(pk)">✏ Umbenennen</button>
                <button class="btn-tiny danger" @click="deletePasskey(pk.id)">🗑 Entfernen</button>
              </template>
            </div>
          </li>
        </ul>

        <p v-else class="info">Noch keine Passkeys registriert.</p>

        <div v-if="pkError" class="error">⚠ {{ pkError }}</div>
        <div v-if="pkSuccess" class="pk-success">✓ {{ pkSuccess }}</div>

        <div class="btn-row">
          <button class="btn btn-primary" @click="addPasskey" :disabled="pkBusy">
            {{ pkBusy ? '…' : '＋ Passkey hinzufügen' }}
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import {
  startRegistration,
  browserSupportsWebAuthn,
} from '@simplewebauthn/browser'
import { useAuthStore } from '../../stores/auth'

const authStore = useAuthStore()
const loading = ref(true)
const busy = ref(false)

// Sprint ε Phase D — MFA-Enforcement-Banner aus Login-Status
const mfaSetupRequired = ref(!!authStore.mfaStatus?.setup_required)
const mfaRecommended = ref(!!authStore.mfaStatus?.recommended)
const mfaGraceText = computed(() => {
  const until = authStore.mfaStatus?.grace_until
  if (!until) return ''
  const d = new Date(until * 1000)
  return isNaN(d.getTime()) ? '' : ` (bis ${d.toLocaleDateString('de-DE')})`
})

const status = ref<{ enabled: boolean; backup_codes_remaining: number }>({
  enabled: false,
  backup_codes_remaining: 0,
})

const setupData = ref<{ secret: string; otpauth_uri: string; qr_code_data_url: string } | null>(null)
const verifyCode = ref('')
const setupError = ref('')
const setupVerifiedCodes = ref<string[] | null>(null)

const disableMode = ref(false)
const disablePassword = ref('')
const disableCode = ref('')
const disableError = ref('')

const regenMode = ref(false)
const regenCode = ref('')
const regenError = ref('')

const headers = () => ({ Authorization: `Bearer ${authStore.token}` })

// #1183: Step-up — Re-Auth (aktuelles Passwort ODER TOTP-Code) für sensible
// Account-Security-Aktionen (TOTP-Setup, Passkey-Registrierung/-Löschung).
const reauth = ref<{ open: boolean; password: string; code: string; error: string;
                     resolve: ((v: any) => void) | null }>(
  { open: false, password: '', code: '', error: '', resolve: null })

const askStepUp = (): Promise<{ current_password?: string; totp_code?: string } | null> =>
  new Promise((resolve) => { reauth.value = { open: true, password: '', code: '', error: '', resolve } })

const submitReauth = () => {
  const r = reauth.value
  const creds: any = {}
  if (r.password) creds.current_password = r.password
  if (r.code) creds.totp_code = r.code
  r.resolve?.(creds)
  reauth.value = { open: false, password: '', code: '', error: '', resolve: null }
}
const cancelReauth = () => {
  reauth.value.resolve?.(null)
  reauth.value = { open: false, password: '', code: '', error: '', resolve: null }
}

const loadStatus = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/auth/2fa/status', { headers: headers() })
    status.value = res.data
  } catch (e: any) {
    console.error('2FA status failed:', e?.response?.data || e?.message)
  } finally {
    loading.value = false
  }
}

const startSetup = async () => {
  const creds = await askStepUp()
  if (!creds) return  // abgebrochen
  busy.value = true
  setupError.value = ''
  try {
    const res = await axios.post('/api/auth/2fa/setup', creds, { headers: headers() })
    setupData.value = res.data
  } catch (e: any) {
    setupError.value = e?.response?.data?.error || 'Setup fehlgeschlagen'
  } finally {
    busy.value = false
  }
}

const cancelSetup = () => {
  setupData.value = null
  verifyCode.value = ''
  setupError.value = ''
}

const verifySetup = async () => {
  if (verifyCode.value.length !== 6) return
  busy.value = true
  setupError.value = ''
  try {
    const res = await axios.post('/api/auth/2fa/verify', { code: verifyCode.value },
      { headers: headers() })
    setupVerifiedCodes.value = res.data.backup_codes
    setupData.value = null
    verifyCode.value = ''
  } catch (e: any) {
    setupError.value = e?.response?.data?.error || 'Verifizierung fehlgeschlagen'
  } finally {
    busy.value = false
  }
}

const finishSetup = async () => {
  setupVerifiedCodes.value = null
  await loadStatus()
}

const copySecret = () => {
  if (setupData.value) navigator.clipboard.writeText(setupData.value.secret)
}

const copyCodes = () => {
  if (setupVerifiedCodes.value) {
    navigator.clipboard.writeText(setupVerifiedCodes.value.join('\n'))
  }
}

const downloadCodes = () => {
  if (!setupVerifiedCodes.value) return
  const blob = new Blob(
    [`AI Compliance Suite — 2FA Backup-Codes\n\n${setupVerifiedCodes.value.join('\n')}\n\nGeneriert: ${new Date().toLocaleString('de-DE')}\nKonto: ${authStore.user?.email}\n`],
    { type: 'text/plain' }
  )
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `aics-backup-codes-${new Date().toISOString().slice(0, 10)}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

const cancelDisable = () => {
  disableMode.value = false
  disablePassword.value = ''
  disableCode.value = ''
  disableError.value = ''
}

const confirmDisable = async () => {
  busy.value = true
  disableError.value = ''
  try {
    await axios.post('/api/auth/2fa/disable',
      { password: disablePassword.value, code: disableCode.value },
      { headers: headers() })
    cancelDisable()
    await loadStatus()
  } catch (e: any) {
    disableError.value = e?.response?.data?.error || 'Deaktivierung fehlgeschlagen'
  } finally {
    busy.value = false
  }
}

const confirmRegen = async () => {
  busy.value = true
  regenError.value = ''
  try {
    const res = await axios.post('/api/auth/2fa/regenerate-backup-codes',
      { code: regenCode.value }, { headers: headers() })
    setupVerifiedCodes.value = res.data.backup_codes
    regenMode.value = false
    regenCode.value = ''
  } catch (e: any) {
    regenError.value = e?.response?.data?.error || 'Erzeugung fehlgeschlagen'
  } finally {
    busy.value = false
  }
}

// ============ PASSKEYS (WebAuthn) — Sprint ε ============
interface Passkey {
  id: number
  nickname: string
  transports: string[]
  aaguid: string
  backup_state: boolean
  created_at: string
  last_used_at: string | null
}

const passkeySupported = ref(true)
const passkeys = ref<Passkey[]>([])
const pkLoading = ref(true)
const pkBusy = ref(false)
const pkError = ref('')
const pkSuccess = ref('')
const renameId = ref<number | null>(null)
const renameValue = ref('')

const formatDate = (s: string | null): string => {
  if (!s) return '—'
  const d = new Date(s.includes('T') || s.includes('-') ? s.replace(' ', 'T') + (s.endsWith('Z') ? '' : 'Z') : s)
  return isNaN(d.getTime()) ? s : d.toLocaleDateString('de-DE')
}

const loadPasskeys = async () => {
  pkLoading.value = true
  try {
    const res = await axios.get('/api/auth/webauthn/credentials', { headers: headers() })
    passkeys.value = res.data.credentials || []
  } catch (e: any) {
    pkError.value = e?.response?.data?.error || 'Passkeys konnten nicht geladen werden'
  } finally {
    pkLoading.value = false
  }
}

const addPasskey = async () => {
  const creds = await askStepUp()
  if (!creds) return  // abgebrochen
  pkBusy.value = true
  pkError.value = ''
  pkSuccess.value = ''
  try {
    const optRes = await axios.post('/api/auth/webauthn/register/options', creds, { headers: headers() })
    const { challenge_id, options } = optRes.data
    const attResp = await startRegistration({ optionsJSON: options })
    const nickname = window.prompt('Name für diesen Passkey (z.B. „MacBook Touch ID"):', 'Passkey') || 'Passkey'
    await axios.post('/api/auth/webauthn/register/verify',
      { challenge_id, credential: attResp, nickname },
      { headers: headers() })
    pkSuccess.value = 'Passkey erfolgreich hinzugefügt.'
    await loadPasskeys()
  } catch (e: any) {
    if (e?.name === 'NotAllowedError' || e?.name === 'AbortError') {
      pkError.value = 'Vorgang abgebrochen.'
    } else {
      pkError.value = e?.response?.data?.error || e?.message || 'Passkey-Registrierung fehlgeschlagen'
    }
  } finally {
    pkBusy.value = false
  }
}

const startRename = (pk: Passkey) => {
  renameId.value = pk.id
  renameValue.value = pk.nickname
}

const confirmRename = async (id: number) => {
  const name = renameValue.value.trim()
  if (!name) { renameId.value = null; return }
  try {
    await axios.patch(`/api/auth/webauthn/credentials/${id}`, { nickname: name }, { headers: headers() })
    renameId.value = null
    await loadPasskeys()
  } catch (e: any) {
    pkError.value = e?.response?.data?.error || 'Umbenennen fehlgeschlagen'
  }
}

const deletePasskey = async (id: number) => {
  if (!window.confirm('Diesen Passkey wirklich entfernen? Sie können sich damit nicht mehr anmelden.')) return
  const creds = await askStepUp()
  if (!creds) return  // abgebrochen
  try {
    await axios.delete(`/api/auth/webauthn/credentials/${id}`, { headers: headers(), data: creds })
    pkSuccess.value = 'Passkey entfernt.'
    await loadPasskeys()
  } catch (e: any) {
    pkError.value = e?.response?.data?.error || 'Entfernen fehlgeschlagen'
  }
}

onMounted(async () => {
  await loadStatus()
  passkeySupported.value = browserSupportsWebAuthn()
  if (passkeySupported.value) await loadPasskeys()
  else pkLoading.value = false
})
</script>

<style scoped>
.security-view {
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
}

.page-header h1 {
  margin: 0 0 4px;
  font-size: 26px;
  color: var(--text-color, #1a1a1a);
}

.page-header p {
  margin: 0 0 24px;
  color: var(--text-muted, #757575);
}

/* #1183: Step-up-Re-Auth-Modal */
.reauth-overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 2000; padding: 16px;
}
.reauth-modal {
  background: #fff; border-radius: 10px; padding: 22px 24px; width: min(420px, 100%);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
}
.reauth-modal h3 { margin: 0 0 8px; color: #1565c0; }
.reauth-modal p { margin: 0 0 12px; font-size: 14px; color: #455; }
.reauth-modal label { display: flex; flex-direction: column; gap: 4px; font-size: 13px;
  color: #555; margin-bottom: 10px; }
.reauth-modal input { padding: 8px; border: 1px solid #cfd8dc; border-radius: 6px; font-size: 14px; }
.reauth-error { color: #b71c1c; font-size: 13px; }
.reauth-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }

.card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 10px;
  padding: 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 20px;
}

.card-header h2 {
  margin: 0 0 6px;
  font-size: 18px;
  color: var(--text-color, #1a1a1a);
}

.muted {
  color: var(--text-muted, #757575);
  font-size: 13px;
  margin: 0;
  line-height: 1.5;
}

.status-pill {
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
}

.status-pill.enabled {
  background: #e8f5e9;
  color: #2e7d32;
}

.status-pill.disabled {
  background: #fafafa;
  color: #757575;
  border: 1px solid #e0e0e0;
}

.info-row {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 8px;
}

.info-label {
  color: var(--text-muted, #757575);
  font-size: 13px;
}

.btn-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.btn {
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  font-family: inherit;
}

.btn-primary {
  background: #1565c0;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #0d47a1;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #f5f5f5;
  color: #1a1a1a;
  border-color: #e0e0e0;
}

.btn-secondary:hover {
  background: #eeeeee;
}

.btn-danger {
  background: #fff;
  color: #c62828;
  border-color: #ffcdd2;
}

.btn-danger:hover {
  background: #ffebee;
}

.btn-link {
  background: none;
  border: none;
  color: #1565c0;
  cursor: pointer;
  text-decoration: underline;
  padding: 4px 0;
  margin-top: 8px;
  font-size: 13px;
  font-family: inherit;
}

.steps {
  margin: 0;
  padding-left: 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.steps li {
  font-size: 14px;
  line-height: 1.5;
}

.qr-row {
  display: flex;
  gap: 24px;
  margin-top: 12px;
  align-items: flex-start;
}

.qr-img {
  width: 180px;
  height: 180px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 8px;
  background: #fff;
}

.qr-side {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.secret-label {
  font-size: 12px;
  color: var(--text-muted, #757575);
}

.secret-code {
  background: #f5f5f5;
  padding: 8px 12px;
  border-radius: 6px;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 13px;
  letter-spacing: 1px;
  word-break: break-all;
}

.btn-tiny {
  align-self: flex-start;
  font-size: 12px;
  padding: 4px 10px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}

.verify-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.code-input {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 18px;
  letter-spacing: 4px;
  text-align: center;
  padding: 10px 14px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  width: 160px;
}

.code-input:focus {
  border-color: #1565c0;
  outline: none;
  box-shadow: 0 0 0 3px rgba(21, 101, 192, 0.15);
}

.error {
  margin-top: 8px;
  font-size: 13px;
  color: #c62828;
}

.warn {
  background: #fff8e1;
  color: #8a6d3b;
  padding: 12px;
  border-left: 3px solid #ff9800;
  border-radius: 4px;
  font-size: 13px;
  margin: 12px 0;
}

.backup-codes-box {
  background: #f8f9fa;
  border: 1px dashed #1565c0;
  border-radius: 10px;
  padding: 20px;
  margin-top: 12px;
}

.backup-codes-box h3 {
  margin: 0 0 12px;
  color: #1565c0;
}

.codes-grid {
  list-style: none;
  margin: 16px 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.codes-grid li code {
  display: block;
  background: #fff;
  padding: 10px 14px;
  border-radius: 6px;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 14px;
  letter-spacing: 2px;
  text-align: center;
  border: 1px solid #e0e0e0;
}

.disable-form {
  margin-top: 20px;
  padding: 20px;
  background: var(--card-bg-alt, #fafafa);
  border-radius: 8px;
  border: 1px solid var(--border-color, #e0e0e0);
}

.disable-form h3 {
  margin: 0 0 8px;
  font-size: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.field span {
  font-size: 13px;
  font-weight: 500;
}

.field input {
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
}

.field input:focus {
  border-color: #1565c0;
  outline: none;
  box-shadow: 0 0 0 3px rgba(21, 101, 192, 0.15);
}

.info {
  color: var(--text-muted, #757575);
  padding: 12px 0;
}

.mfa-enforce-banner {
  background: #ffebee;
  color: #c62828;
  border: 1px solid #ef9a9a;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 20px;
  font-size: 14px;
}

.mfa-recommend-banner {
  background: #fff8e1;
  color: #8a6d3b;
  border: 1px solid #ffe082;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 20px;
  font-size: 14px;
}

/* Passkeys */
.passkey-list {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.passkey-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  background: var(--card-bg-alt, #fafafa);
}

.pk-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pk-icon {
  font-size: 22px;
}

.pk-meta {
  font-size: 12px;
  color: var(--text-muted, #757575);
  margin-top: 2px;
}

.pk-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: 999px;
  background: #e3f2fd;
  color: #1565c0;
  font-size: 11px;
}

.pk-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.btn-tiny.danger {
  color: #c62828;
  border-color: #ffcdd2;
}

.pk-rename-input {
  padding: 6px 10px;
  border: 1px solid #1565c0;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
}

.pk-success {
  margin-top: 8px;
  font-size: 13px;
  color: #2e7d32;
}
</style>
