<template>
  <div class="login-split">
    <aside class="login-brand">
      <div class="login-brand-grid" aria-hidden="true"></div>
      <div class="login-brand-glow" aria-hidden="true"></div>
      <div class="login-brand-top">
        <div class="brand-lockup">
          <span class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 28 28" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2.5 L23 6 V14 C23 19 19 23.5 14 25.5 C9 23.5 5 19 5 14 V6 Z" />
              <path d="M9.5 13.5 L13 17 L18.5 10.5" />
            </svg>
          </span>
          <div>
            <div class="brand-name">AI Compliance Suite</div>
            <div class="brand-tag">Compliance Management Platform</div>
          </div>
        </div>
      </div>
      <div class="login-brand-mid">
        <div class="login-eyebrow">Sicher · Auditierbar · Multi-Framework</div>
        <h2 class="login-headline">
          Compliance, in einer einzigen <span class="hl">souveränen</span> Plattform.
        </h2>
        <p class="login-sub">
          CRA, NIS2, EU AI Act, DSGVO und Risikobewertung — strukturiert nach Reifegradmodellen,
          mit voller Audit-Spur und KI-gestützter Bearbeitung.
        </p>
        <ul class="login-frameworks">
          <li v-for="f in frameworks" :key="f">{{ f }}</li>
        </ul>
      </div>
      <div class="login-brand-foot">
        <div class="trust-row">
          <span class="trust-pill"><span class="dot" /> ISO 27001 Hosting</span>
          <span class="trust-pill"><span class="dot" /> EU-DSGVO konform</span>
          <span v-if="publicCfg.sso_enabled" class="trust-pill"><span class="dot" /> SSO-ready</span>
        </div>
      </div>
    </aside>

    <main class="login-pane">
      <div class="login-pane-top">
        <span class="env-pill">{{ publicCfg.env === 'production' ? 'Produktiv-System' : 'Test-Umgebung' }}</span>
        <a v-if="publicCfg.demo_users_enabled" class="login-link" href="#" @click.prevent>Status&nbsp;↗</a>
      </div>

      <form v-if="step === 'password'" class="login-form2" @submit.prevent="handleLogin">
        <header class="login-form-hdr">
          <h1>Willkommen zurück</h1>
          <p>Bitte melden Sie sich mit Ihren Zugangsdaten an.</p>
        </header>

        <label class="field">
          <span class="field-label">E-Mail-Adresse</span>
          <span class="field-input">
            <span class="field-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <path d="M3.5 6.5 L12 13 L20.5 6.5" />
              </svg>
            </span>
            <input
              v-model="email"
              type="email"
              placeholder="benutzer@unternehmen.de"
              autocomplete="email"
              required
            />
          </span>
        </label>

        <label class="field">
          <span class="field-label">
            Passwort
            <a class="field-meta" href="#" @click.prevent>Vergessen?</a>
          </span>
          <span class="field-input">
            <span class="field-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <rect x="4.5" y="10.5" width="15" height="10" rx="1.75" />
                <path d="M7.5 10.5 V7 a4.5 4.5 0 0 1 9 0 V10.5" />
              </svg>
            </span>
            <input
              v-model="password"
              :type="showPw ? 'text' : 'password'"
              placeholder="••••••••"
              autocomplete="current-password"
              required
            />
            <button
              type="button"
              class="field-toggle"
              :aria-label="showPw ? 'Passwort verbergen' : 'Passwort anzeigen'"
              @click="showPw = !showPw"
            >
              {{ showPw ? 'Verbergen' : 'Anzeigen' }}
            </button>
          </span>
        </label>

        <div class="login-row">
          <label class="check">
            <input v-model="remember" type="checkbox" />
            <span>Auf diesem Gerät angemeldet bleiben</span>
          </label>
          <router-link class="login-link" to="/account/forgot">Passwort vergessen?</router-link>
        </div>

        <div v-if="error" class="form-error" role="alert">⚠ {{ error }}</div>

        <button type="submit" class="btn-cta" :disabled="loading">
          <span>{{ loading ? 'Melde an…' : 'Anmelden' }}</span>
          <svg v-if="!loading" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12 H19 M13 6 L19 12 L13 18" />
          </svg>
        </button>

        <template v-if="passkeySupported">
          <div class="sso-divider"><span>oder</span></div>
          <button type="button" class="btn-sso" @click="handlePasskeyLogin" :disabled="loading">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="9" cy="9" r="4" />
              <path d="M9 13 v8 M9 17 h4 M13 13 l3 -3 m0 0 l2 2 m-2 -2 l2 -2" />
            </svg>
            Mit Passkey anmelden
          </button>
        </template>

        <template v-if="publicCfg.sso_enabled">
          <div class="sso-divider"><span>oder</span></div>
          <button type="button" class="btn-sso" @click.prevent>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2 H6 a2 2 0 0 0-2 2 V20 a2 2 0 0 0 2 2 H18 a2 2 0 0 0 2-2 V8 Z" />
              <path d="M14 2 V8 H20" />
              <path d="M9 14 H15 M9 17 H13" />
            </svg>
            Mit Unternehmens-SSO fortfahren
          </button>
        </template>

        <footer v-if="publicCfg.demo_users_enabled" class="login-form-foot">
          <span>Demo:</span>
          <button type="button" class="demo-chip" @click="fillDemo('admin')">Admin</button>
          <button type="button" class="demo-chip" @click="fillDemo('editor')">Editor</button>
        </footer>
      </form>

      <form v-else class="login-form2" @submit.prevent="handleTotpVerify">
        <header class="login-form-hdr">
          <h1>🔐 Authenticator-Code</h1>
          <p>
            Ihr Konto ist mit 2-Faktor-Authentifizierung geschützt.
            Geben Sie den 6-stelligen Code aus Ihrer Authenticator-App ein
            <small>(oder einen Backup-Code im Format <code>XXXX-XXXX</code>)</small>.
          </p>
        </header>

        <label class="field">
          <span class="field-label">Code</span>
          <span class="field-input">
            <span class="field-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <rect x="4.5" y="3.5" width="15" height="17" rx="2" />
                <path d="M9 7 H15 M9 11 H15 M9 15 H13" />
              </svg>
            </span>
            <input
              v-model="totpCode"
              type="text"
              inputmode="numeric"
              placeholder="123456"
              autocomplete="one-time-code"
              maxlength="9"
              ref="totpInputRef"
              required
            />
          </span>
        </label>

        <div v-if="error" class="form-error" role="alert">⚠ {{ error }}</div>

        <button type="submit" class="btn-cta" :disabled="loading || totpCode.length < 6">
          <span>{{ loading ? 'Prüfe…' : 'Bestätigen & anmelden' }}</span>
        </button>

        <template v-if="totpMethods.includes('passkey') && passkeySupported">
          <div class="sso-divider"><span>oder</span></div>
          <button type="button" class="btn-sso" @click="handlePasskeyVerify" :disabled="loading">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="9" cy="9" r="4" />
              <path d="M9 13 v8 M9 17 h4 M13 13 l3 -3 m0 0 l2 2 m-2 -2 l2 -2" />
            </svg>
            Stattdessen mit Passkey bestätigen
          </button>
        </template>

        <button type="button" class="btn-link-line" @click="resetToPassword">
          ← Zurück zur Anmeldung
        </button>
      </form>

      <div class="login-pane-foot">
        <span>© 2026 AI Compliance Suite</span>
        <span class="dotsep">·</span>
        <a href="#" class="login-link" @click.prevent>Datenschutz</a>
        <span class="dotsep">·</span>
        <a href="#" class="login-link" @click.prevent>Impressum</a>
        <span class="dotsep">·</span>
        <span class="mono-tiny">v1.4.2</span>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const frameworks = ['CRA', 'NIS2', 'AI Act', 'DSGVO']

// #417: Public-Config bestimmt was im Login angezeigt wird
interface PublicCfg { demo_users_enabled: boolean; sso_enabled: boolean; env: string }
const publicCfg = ref<PublicCfg>({ demo_users_enabled: false, sso_enabled: false, env: 'production' })

onMounted(async () => {
  try {
    const r = await axios.get('/api/auth/public-config', { timeout: 5000 })
    publicCfg.value = { ...publicCfg.value, ...r.data }
  } catch {
    // best-effort; bei Fehler bleibt der konservative Default (production, alles aus)
  }
})

const step = ref<'password' | 'totp'>('password')
const email = ref('')
const password = ref('')
const showPw = ref(false)
const remember = ref(true)
const loading = ref(false)
const error = ref('')

const totpCode = ref('')
const totpChallenge = ref('')
const totpMethods = ref<string[]>([])
const totpInputRef = ref<HTMLInputElement | null>(null)
const passkeySupported = authStore.passkeySupported()

const fillDemo = (kind: 'admin' | 'editor') => {
  if (kind === 'admin') {
    email.value = 'admin@example.com'
    password.value = 'admin-password'
  } else {
    email.value = 'editor@example.com'
    password.value = 'editor-password'
  }
}

// Sprint ε Phase D — nach erfolgreichem Login ggf. MFA-Einrichtung erzwingen
const routeAfterLogin = () => {
  if (authStore.mfaStatus?.setup_required) {
    router.push('/account/security')
  } else {
    router.push('/')
  }
}

const handleLogin = async () => {
  loading.value = true
  error.value = ''

  const result = await authStore.login(email.value, password.value)

  if (result.ok === true) {
    routeAfterLogin()
  } else if (result.ok === 'totp_required') {
    totpChallenge.value = result.challenge
    totpMethods.value = result.methods || ['totp']
    step.value = 'totp'
    totpCode.value = ''
    await nextTick()
    totpInputRef.value?.focus()
  } else {
    error.value = result.error || 'E-Mail oder Passwort ungültig.'
  }

  loading.value = false
}

const handlePasskeyLogin = async () => {
  loading.value = true
  error.value = ''
  const result = await authStore.loginWithPasskey()
  if (result.ok) routeAfterLogin()
  else error.value = result.error
  loading.value = false
}

const handlePasskeyVerify = async () => {
  loading.value = true
  error.value = ''
  const result = await authStore.verifyPasskey(totpChallenge.value)
  if (result.ok) routeAfterLogin()
  else error.value = result.error
  loading.value = false
}

const handleTotpVerify = async () => {
  loading.value = true
  error.value = ''
  const result = await authStore.verifyTotp(totpChallenge.value, totpCode.value)
  if (result.ok) {
    routeAfterLogin()
  } else {
    error.value = result.error
  }
  loading.value = false
}

const resetToPassword = () => {
  step.value = 'password'
  totpCode.value = ''
  totpChallenge.value = ''
  totpMethods.value = []
  error.value = ''
}
</script>

<style scoped>
:root {
  --login-mono: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
}

* {
  box-sizing: border-box;
}

.login-split {
  display: grid;
  grid-template-columns: 1.05fr 1fr;
  min-height: 100vh;
  background: #fff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: #212121;
}

.login-brand {
  position: relative;
  overflow: hidden;
  background: linear-gradient(140deg, #0a2a5e 0%, #1565c0 55%, #1d8a5e 130%);
  color: #fff;
  padding: 44px 56px;
  display: flex;
  flex-direction: column;
  isolation: isolate;
}

.login-brand-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 56px 56px;
  -webkit-mask-image: radial-gradient(ellipse at 30% 40%, #000 30%, transparent 75%);
  mask-image: radial-gradient(ellipse at 30% 40%, #000 30%, transparent 75%);
  pointer-events: none;
  z-index: 0;
}

.login-brand-glow {
  position: absolute;
  right: -180px;
  top: -120px;
  width: 520px;
  height: 520px;
  background: radial-gradient(circle, rgba(29, 138, 94, 0.55) 0%, rgba(29, 138, 94, 0) 70%);
  filter: blur(8px);
  pointer-events: none;
  z-index: 0;
}

.login-brand-top,
.login-brand-mid,
.login-brand-foot {
  position: relative;
  z-index: 1;
}

.login-brand-mid {
  margin-top: 56px;
}

.login-brand-foot {
  margin-top: auto;
  padding-top: 40px;
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.25);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(8px);
}

.brand-name {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.1;
}

.brand-tag {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.72);
  margin-top: 3px;
  letter-spacing: 0.2px;
}

.login-eyebrow {
  display: inline-block;
  font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 11px;
  letter-spacing: 1.4px;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.78);
  padding: 5px 10px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 999px;
  margin-bottom: 22px;
}

.login-headline {
  font-size: 38px;
  line-height: 1.12;
  font-weight: 600;
  margin: 0 0 18px;
  max-width: 14ch;
  letter-spacing: -0.5px;
  color: #fff;
}

.login-headline .hl {
  background: linear-gradient(90deg, #b9e6cb 0%, #7fd3a8 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-style: italic;
  font-weight: 600;
}

.login-sub {
  font-size: 15px;
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.82);
  max-width: 46ch;
  margin: 0 0 28px;
}

.login-frameworks {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.login-frameworks li {
  font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 11px;
  letter-spacing: 0.6px;
  padding: 6px 11px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.92);
}

.trust-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.trust-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.82);
  padding: 6px 11px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
}

.trust-pill .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #7fd3a8;
  box-shadow: 0 0 8px #7fd3a8;
}

.login-pane {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 32px 56px;
  background: #fff;
}

.login-pane-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.env-pill {
  font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 11px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  padding: 4px 9px;
  background: #e8f5e9;
  color: #2e7d32;
  border-radius: 4px;
  border: 1px solid #c8e6c9;
}

.login-link {
  font-size: 13px;
  color: #1565c0;
  text-decoration: none;
}

.login-link:hover {
  text-decoration: underline;
}

.login-form2 {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  max-width: 420px;
  margin: auto 0;
}

.login-form-hdr h1 {
  font-size: 26px;
  font-weight: 600;
  color: #1a1a1a;
  letter-spacing: -0.4px;
  margin: 0 0 6px;
}

.login-form-hdr p {
  font-size: 14px;
  color: #757575;
  margin: 0 0 8px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 13px;
  font-weight: 500;
  color: #1a1a1a;
}

.field-meta {
  font-size: 12px;
  color: #1565c0;
  text-decoration: none;
}

.field-meta:hover {
  text-decoration: underline;
}

.field-input {
  display: flex;
  align-items: center;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.field-input:focus-within {
  border-color: #1565c0;
  box-shadow: 0 0 0 4px rgba(21, 101, 192, 0.12);
}

.field-icon {
  padding: 0 4px 0 12px;
  color: #9aa0a6;
  display: inline-flex;
  align-items: center;
}

.field-input input {
  flex: 1;
  border: none;
  outline: none;
  padding: 12px 12px 12px 8px;
  font-size: 14px;
  background: transparent;
  font-family: inherit;
  color: inherit;
}

.field-toggle {
  background: none;
  border: none;
  padding: 0 14px;
  height: 100%;
  font-size: 12px;
  color: #757575;
  cursor: pointer;
  font-family: inherit;
}

.field-toggle:hover {
  color: #1565c0;
}

.login-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: -2px 0 6px;
}

.check {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #757575;
  cursor: pointer;
  user-select: none;
}

.check input {
  accent-color: #1565c0;
  width: 15px;
  height: 15px;
}

.form-error {
  display: flex;
  gap: 8px;
  align-items: center;
  background: #ffebee;
  color: #d32f2f;
  padding: 10px 12px;
  border-radius: 8px;
  border-left: 3px solid #d32f2f;
  font-size: 13px;
}

.btn-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 14px 18px;
  background: linear-gradient(135deg, #1565c0 0%, #0d47a1 100%);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(13, 71, 161, 0.3), 0 4px 12px rgba(21, 101, 192, 0.25);
  transition: transform 0.1s, box-shadow 0.15s;
  font-family: inherit;
}

.btn-cta:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(13, 71, 161, 0.35), 0 8px 20px rgba(21, 101, 192, 0.3);
}

.btn-cta:active:not(:disabled) {
  transform: translateY(0);
}

.btn-cta:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.sso-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: #9aa0a6;
  text-transform: uppercase;
  letter-spacing: 1.2px;
}

.sso-divider::before,
.sso-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e0e0e0;
}

.btn-sso {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 12px 18px;
  background: #fff;
  color: #1a1a1a;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  font-family: inherit;
}

.btn-sso:hover {
  background: #fafafa;
  border-color: #c4c4c4;
}

.btn-sso svg {
  color: #1565c0;
}

.login-form-foot {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: #757575;
  padding-top: 4px;
}

.demo-chip {
  font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 11px;
  padding: 4px 10px;
  background: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 999px;
  color: #212121;
  cursor: pointer;
}

.demo-chip:hover {
  background: #e3f2fd;
  border-color: #1565c0;
  color: #1565c0;
}

.btn-link-line {
  align-self: center;
  background: none;
  border: none;
  color: #1565c0;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  padding: 8px 4px;
  margin-top: 4px;
}

.btn-link-line:hover {
  text-decoration: underline;
}

.login-pane-foot {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: #757575;
}

.dotsep {
  opacity: 0.5;
}

.mono-tiny {
  font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 11px;
}

@media (max-width: 900px) {
  .login-split {
    grid-template-columns: 1fr;
  }
  .login-brand {
    padding: 28px 24px;
    min-height: 320px;
  }
  .login-headline {
    font-size: 28px;
  }
  .login-pane {
    padding: 24px;
  }
}
</style>
