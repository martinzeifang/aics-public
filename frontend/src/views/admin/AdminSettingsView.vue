<template>
  <div class="admin-settings">
    <header class="page-header">
      <h1>⚙️ Einstellungen</h1>
      <p class="muted">Jede Option als eigene Kachel — wähle einen Bereich.</p>
    </header>

    <!-- KI-Provider-Status (Sprint #16, #877): read-only Transparenz Lokal/Cloud + Egress -->
    <div class="ki-status-card">
      <div class="ki-status-head">
        <h2>🤖 Aktiver KI-Provider</h2>
        <AIProviderBadge />
      </div>
      <p class="muted">Aktueller Provider und Daten-Egress-Status (read-only).</p>
      <dl v-if="kiStatus" class="ki-dl">
        <div class="ki-dl-row">
          <dt>Provider</dt>
          <dd>{{ kiStatus.label }} <span class="ki-mono">({{ kiStatus.provider }})</span></dd>
        </div>
        <div class="ki-dl-row">
          <dt>Status</dt>
          <dd>{{ kiStatus.configured ? 'konfiguriert' : 'nicht konfiguriert' }}</dd>
        </div>
        <div class="ki-dl-row">
          <dt>Daten-Egress</dt>
          <dd :class="{ 'ki-warn': kiStatus.allow_data_egress }">
            {{ kiStatus.allow_data_egress
              ? '⚠️ erlaubt — Daten können dein Netzwerk verlassen'
              : 'blockiert — Daten bleiben lokal' }}
          </dd>
        </div>
      </dl>
      <p v-else-if="kiError" class="err">KI-Provider-Status konnte nicht geladen werden.</p>
      <p class="muted ki-help">
        Mehr dazu:
        <a href="/docs/ki-funktionen/" target="_blank" rel="noopener">
          Wie funktionieren die KI-Funktionen?</a>
      </p>
    </div>

    <!-- Kachel-Grid: eine Kachel pro Option -->
    <div class="tile-grid">
      <button v-for="t in tiles" :key="t.key" class="settings-tile" @click="openTile(t.key)">
        <span class="tile-icon">{{ t.icon }}</span>
        <span class="tile-title">{{ t.title }}</span>
        <span class="tile-desc">{{ t.desc }}</span>
      </button>
    </div>

    <!-- SettingsDialog (fokussiert) für ai/github/modules/appearance/backup -->
    <SettingsDialog v-if="dialogOnly" :open="true" :only="dialogOnly" @close="dialogOnly = null" />

    <!-- Passkey / WebAuthn -->
    <div v-if="panel === 'passkey'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>🔑 Passkey / WebAuthn</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">
            Damit Passkeys funktionieren, müssen RP-ID und Origin zur aufgerufenen URL passen.
            <strong>RP-ID = vollständiger Hostname (keine IP, kein Schema/Port).</strong>
          </p>
          <div v-if="waLoading" class="muted">Lade Konfiguration…</div>
          <template v-else>
            <div class="btn-row" style="margin-bottom:8px;">
              <button class="btn-secondary" @click="loadWebauthnSuggest" :disabled="waSaving">🔎 Vorschlag laden (erkannter Host)</button>
            </div>
            <div class="form-row">
              <label>RP-ID (vollständiger Hostname)</label>
              <input v-model="waConfig.rp_id" placeholder="z.B. compliancesuite.c99781.intern" />
              <small v-if="rpIdHint" class="err">⚠ {{ rpIdHint }}</small>
              <small v-else class="muted" style="font-size:12px;">Muss der volle Hostname der aufgerufenen URL sein (oder ein registrierbares Suffix).</small>
            </div>
            <div class="form-row">
              <label>RP-Name</label>
              <input v-model="waConfig.rp_name" placeholder="AI Compliance Suite" />
            </div>
            <div class="form-row">
              <label>Origin(s) — komma-separiert</label>
              <input v-model="waConfig.rp_origin" placeholder="https://compliancesuite.c99781.intern:8443" />
            </div>
            <p class="muted" style="font-size:12px;">
              Quelle aktuell: {{ waConfig.from_settings ? 'Web-Einstellungen' : 'ENV/Default (noch nicht über Web gesetzt)' }}
            </p>
            <div class="btn-row">
              <button class="btn-primary" @click="saveWebauthn" :disabled="waSaving || !!rpIdHint">
                {{ waSaving ? 'Speichert…' : 'Speichern' }}
              </button>
              <span v-if="waSavedMsg" class="ok">{{ waSavedMsg }}</span>
              <span v-if="waError" class="err">⚠ {{ waError }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- MFA-Richtlinie -->
    <div v-if="panel === 'mfa'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>🛡️ MFA-Richtlinie</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">Mehr-Faktor-Authentifizierung (TOTP oder Passkey) ist für alle Benutzer verfügbar. Hier legen Sie fest, ob sie verpflichtend ist.</p>
          <div v-if="mfaLoading" class="muted">Lade Richtlinie…</div>
          <template v-else>
            <div class="form-row">
              <label>Modus</label>
              <select v-model="mfaPolicy.mode">
                <option value="optional">Optional — jeder kann MFA selbst aktivieren</option>
                <option value="required_all">Pflicht für alle Benutzer</option>
                <option value="required_roles">Pflicht für bestimmte Rollen</option>
              </select>
            </div>
            <div v-if="mfaPolicy.mode === 'required_roles'" class="form-row">
              <label>Betroffene Rollen</label>
              <div class="role-checks">
                <label v-for="r in knownRoles" :key="r" class="role-check">
                  <input type="checkbox" :value="r" :checked="mfaPolicy.required_roles.includes(r)" @change="toggleRole(r, $event)" />
                  {{ r }}
                </label>
              </div>
            </div>
            <div v-if="mfaPolicy.mode !== 'optional'" class="form-row">
              <label>Übergangsfrist (Tage bis Einrichtung erzwungen wird)</label>
              <input type="number" min="0" max="90" v-model.number="mfaPolicy.grace_days" />
            </div>
            <div class="btn-row">
              <button class="btn-primary" @click="saveMfaPolicy" :disabled="mfaSaving">
                {{ mfaSaving ? 'Speichert…' : 'Richtlinie speichern' }}
              </button>
              <span v-if="mfaSavedMsg" class="ok">{{ mfaSavedMsg }}</span>
              <span v-if="mfaError" class="err">⚠ {{ mfaError }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Zertifikate -->
    <div v-if="panel === 'certs'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>📜 Zertifikate (TLS)</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">
            Self-Signed-Zertifikat für Hostname/IP, Zertifikatsantrag (CSR) für eure PKI,
            und Verwaltung aller gespeicherten Zertifikate.
          </p>
          <div v-if="certCurrent" class="cert-current">
            <strong>Aktives Zertifikat:</strong>
            <span v-if="certCurrent.present">
              {{ certCurrent.common_name || '—' }}
              <span class="muted">· gültig bis {{ (certCurrent.not_after || '').slice(0,10) }}</span>
            </span>
            <span v-else class="muted">keines gefunden</span>
          </div>
          <div class="btn-row">
            <button class="btn-primary" @click="showManager = true">🗂 Zertifikate verwalten</button>
            <button class="btn-secondary" @click="showSelfSigned = true">＋ Self-Signed</button>
            <button class="btn-secondary" @click="showCsr = true">📜 CSR für PKI</button>
          </div>
        </div>
      </div>
    </div>

    <CertManager v-if="showManager" @close="showManager = false" @applied="onCertApplied" />
    <CertSelfSignedWizard v-if="showSelfSigned" @close="showSelfSigned = false" @applied="onCertApplied" />
    <CertCsrWizard v-if="showCsr" @close="showCsr = false" @applied="onCertApplied" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import axios from 'axios'
import SettingsDialog from '../../components/SettingsDialog.vue'
import AIProviderBadge from '../../components/shared/AIProviderBadge.vue'
import { useAiProviderStore } from '../../stores/aiProvider'
import CertSelfSignedWizard from './dialogs/CertSelfSignedWizard.vue'
import CertCsrWizard from './dialogs/CertCsrWizard.vue'
import CertManager from './dialogs/CertManager.vue'

// ── Kachel-Hub-Navigation ──────────────────────────────────────
const tiles = [
  { key: 'ai', icon: '🤖', title: 'KI-Provider', desc: 'On-Prem (Ollama) oder Cloud-Modell' },
  { key: 'github', icon: '🔗', title: 'GitHub-Integration', desc: 'Token & Repo für Issue-Erstellung' },
  { key: 'modules', icon: '🧩', title: 'Module', desc: 'Reihenfolge & Aktivierung der Module' },
  { key: 'appearance', icon: '🎨', title: 'Erscheinungsbild', desc: 'Darstellung / Theme' },
  { key: 'backup', icon: '💾', title: 'Backup-Einstellungen', desc: 'Backup-on-Exit & Aufbewahrung' },
  { key: 'passkey', icon: '🔑', title: 'Passkey / WebAuthn', desc: 'RP-ID & Origin für Passkeys' },
  { key: 'mfa', icon: '🛡️', title: 'MFA-Richtlinie', desc: 'TOTP/Passkey optional oder Pflicht' },
  { key: 'certs', icon: '📜', title: 'Zertifikate (TLS)', desc: 'Self-Signed, CSR & Verwaltung' },
] as const

const dialogOnly = ref<string | null>(null)   // SettingsDialog-Sektion (ai/github/modules/appearance/backup)
const panel = ref<string | null>(null)         // eigene Panels (passkey/mfa/certs)

const openTile = (key: string) => {
  if (['ai', 'github', 'modules', 'appearance', 'backup'].includes(key)) {
    dialogOnly.value = key
  } else {
    panel.value = key
    if (key === 'certs') loadCurrentCert()
  }
}

// ── Zertifikate ────────────────────────────────────────────────
const showSelfSigned = ref(false)
const showCsr = ref(false)
const showManager = ref(false)
const certCurrent = ref<any>(null)

const loadCurrentCert = async () => {
  try {
    const r = await axios.get('/api/admin/certificates/current')
    certCurrent.value = r.data
  } catch { certCurrent.value = null }
}
const onCertApplied = () => { loadCurrentCert() }

// ── Passkey / WebAuthn RP-Config (über Web) ────────────────────
interface WaConfig { rp_id: string; rp_name: string; rp_origin: string; from_settings: boolean }
const waConfig = ref<WaConfig>({ rp_id: '', rp_name: '', rp_origin: '', from_settings: false })
const waLoading = ref(true)
const waSaving = ref(false)
const waSavedMsg = ref('')
const waError = ref('')

const rpIdHint = computed(() => {
  const id = (waConfig.value.rp_id || '').trim().toLowerCase().replace(/\.$/, '')
  const origin = (waConfig.value.rp_origin || '').trim()
  if (!id || !origin) return ''
  let host = ''
  try { host = new URL(origin.split(',')[0]).hostname.toLowerCase().replace(/\.$/, '') } catch { return '' }
  if (!host) return ''
  if (host === id || host.endsWith('.' + id)) return ''
  return `RP-ID passt nicht zum Origin-Host „${host}". Nutze „${host}" (oder ein Suffix davon).`
})

const loadWebauthnSuggest = async () => {
  waError.value = ''
  try {
    const r = await axios.get('/api/admin/certificates/suggest')
    const host = (r.data.hostnames || [])[0]
    if (host) {
      waConfig.value.rp_id = host
      if (!waConfig.value.rp_origin) waConfig.value.rp_origin = `https://${host}:8443`
    } else {
      waError.value = 'Kein Hostname erkannt — bitte manuell eintragen.'
    }
  } catch (e: any) {
    waError.value = e?.response?.data?.error || 'Vorschlag konnte nicht geladen werden'
  }
}

const loadWebauthn = async () => {
  waLoading.value = true
  try {
    const r = await axios.get('/api/admin/webauthn-config')
    waConfig.value = {
      rp_id: r.data.rp_id || '',
      rp_name: r.data.rp_name || '',
      rp_origin: r.data.rp_origin || '',
      from_settings: !!r.data.from_settings,
    }
  } catch (e: any) {
    waError.value = e?.response?.data?.error || 'Konfiguration konnte nicht geladen werden'
  } finally {
    waLoading.value = false
  }
}

const saveWebauthn = async () => {
  waSaving.value = true
  waError.value = ''
  waSavedMsg.value = ''
  try {
    await axios.put('/api/admin/webauthn-config', {
      rp_id: waConfig.value.rp_id,
      rp_name: waConfig.value.rp_name,
      rp_origin: waConfig.value.rp_origin,
    })
    waConfig.value.from_settings = true
    waSavedMsg.value = '✓ Gespeichert'
    setTimeout(() => { waSavedMsg.value = '' }, 3000)
  } catch (e: any) {
    waError.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
  } finally {
    waSaving.value = false
  }
}

// ── MFA-Policy (Sprint ε Phase D) ──────────────────────────────
interface MfaPolicy { mode: string; required_roles: string[]; grace_days: number }
const knownRoles = ['admin', 'cra_editor', 'cra_viewer', 'auditor', 'manager']
const mfaPolicy = ref<MfaPolicy>({ mode: 'optional', required_roles: [], grace_days: 7 })
const mfaLoading = ref(true)
const mfaSaving = ref(false)
const mfaSavedMsg = ref('')
const mfaError = ref('')

const toggleRole = (role: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  const list = mfaPolicy.value.required_roles
  if (checked && !list.includes(role)) list.push(role)
  else if (!checked) mfaPolicy.value.required_roles = list.filter(r => r !== role)
}

const loadMfaPolicy = async () => {
  mfaLoading.value = true
  try {
    const r = await axios.get('/api/admin/mfa-policy')
    mfaPolicy.value = {
      mode: r.data.mode || 'optional',
      required_roles: r.data.required_roles || [],
      grace_days: r.data.grace_days ?? 7,
    }
  } catch (e: any) {
    mfaError.value = e?.response?.data?.error || 'Richtlinie konnte nicht geladen werden'
  } finally {
    mfaLoading.value = false
  }
}

const saveMfaPolicy = async () => {
  mfaSaving.value = true
  mfaError.value = ''
  mfaSavedMsg.value = ''
  try {
    await axios.put('/api/admin/mfa-policy', mfaPolicy.value)
    mfaSavedMsg.value = '✓ Gespeichert'
    setTimeout(() => { mfaSavedMsg.value = '' }, 3000)
  } catch (e: any) {
    mfaError.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
  } finally {
    mfaSaving.value = false
  }
}

// ── KI-Provider-Status (Sprint #16, #877) ──────────────────────
// #1342 Defekt A: read-only Status aus dem Pinia-Store (Single Source of Truth),
// damit die Karte nach einem Provider-Wechsel ohne Reload aktualisiert.
const aiProviderStore = useAiProviderStore()
const { status: kiStatus, error: kiError } = storeToRefs(aiProviderStore)

onMounted(() => { loadWebauthn(); loadMfaPolicy(); aiProviderStore.loadStatus() })
</script>

<style scoped>
.admin-settings { max-width: 1200px; padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0 0 4px; }
.muted { color: var(--color-text-muted, #666); margin: 0 0 12px; }

/* Kachel-Grid */
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.settings-tile {
  display: flex; flex-direction: column; gap: 6px; text-align: left;
  background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 10px; padding: 18px 20px; cursor: pointer; font-family: inherit;
  transition: border-color .15s, box-shadow .15s, transform .1s;
}
.settings-tile:hover { border-color: #1565c0; box-shadow: 0 2px 10px rgba(21,101,192,.12); transform: translateY(-1px); }
.tile-icon { font-size: 30px; }
.tile-title { font-size: 16px; font-weight: 600; color: var(--color-primary, #1565c0); }
.tile-desc { font-size: 13px; color: var(--color-text-secondary, #777); line-height: 1.4; }

/* Hub-Modals (Passkey/MFA/Zertifikate) */
.hub-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex;
  align-items: center; justify-content: center; z-index: 1000; }
.hub-modal { background: #fff; border-radius: 10px; width: min(640px, 94vw); max-height: 90vh;
  display: flex; flex-direction: column; }
.hub-head { display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #e0e0e0; }
.hub-head h2 { margin: 0; font-size: 18px; }
.hub-body { padding: 18px 20px; overflow: auto; }
.x { background: none; border: none; font-size: 18px; cursor: pointer; }

.form-row { margin-bottom: 14px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row select, .form-row input {
  width: 100%; padding: 8px 10px; border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px; font-size: 14px;
}
.role-checks { display: flex; flex-wrap: wrap; gap: 12px; }
.role-check { display: inline-flex; align-items: center; gap: 6px; font-weight: 400; font-size: 13px; }
.btn-row { display: flex; align-items: center; gap: 12px; margin-top: 8px; flex-wrap: wrap; }
.btn-primary { padding: 10px 16px; background: #1565c0; color: #fff; border: none;
  border-radius: 8px; font-size: 14px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { padding: 10px 16px; background: #f2f2f2; border: 1px solid #d8d8d8;
  border-radius: 8px; font-size: 14px; cursor: pointer; }
.ok { color: #2e7d32; font-size: 13px; }
.err { color: #c62828; font-size: 13px; }
.cert-current { font-size: 13px; margin-bottom: 12px; padding: 8px 10px;
  background: var(--color-background, #fafafa); border-radius: 6px; }

/* KI-Provider-Status-Karte (#877) */
.ki-status-card {
  background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 10px; padding: 18px 20px; margin-bottom: 20px;
}
.ki-status-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ki-status-head h2 { margin: 0; font-size: 18px; }
.ki-dl { margin: 8px 0 0; }
.ki-dl-row { display: flex; gap: 12px; padding: 4px 0; border-bottom: 1px solid var(--border-color, #eee); }
.ki-dl-row dt { width: 140px; flex-shrink: 0; font-weight: 600; color: var(--color-text-secondary, #777); }
.ki-dl-row dd { margin: 0; }
.ki-mono { font-family: Consolas, monospace; font-size: 12px; color: var(--color-text-secondary, #999); }
.ki-warn { color: #e65100; font-weight: 600; }
.ki-help { margin-top: 12px; }
</style>
